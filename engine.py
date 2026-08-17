import json
import random
from datetime import datetime, timezone
from pathlib import Path

import world

DISASTERS_DIR = Path(__file__).resolve().parent / "data" / "disasters"

DEFAULT_VICTORY_SHARE = 0.5
TIMER_DEFAULTS = {"turn_seconds_base": 45, "turn_seconds_per_unit": 4, "turn_seconds_per_territory": 2, "turn_seconds_min": 30, "turn_seconds_max": 300}
DISASTER_DEFAULTS = {"disaster_chance": 0.22, "disaster_first_turn": 3}
ABANDON_SECONDS = 900

PACT_KINDS = ("non_aggression", "alliance", "trade")
PACT_NAMES = {"non_aggression": "Non-aggression pact", "alliance": "Alliance", "trade": "Resource trade"}
PACT_COST = {"non_aggression": 20, "alliance": 40, "trade": 0}
BREACH_PENALTY = {"non_aggression": 15, "alliance": 25, "trade": 10}
MIN_PACT_TURNS = 2
MAX_PACT_TURNS = 20

_disasters = None


def setting(config, table, key):
	value = config.get(key)
	if isinstance(value, (int, float)) and value >= 0:
		return value
	return table[key]


def turn_seconds(db, game_id, config):
	standing = db.execute("SELECT COUNT(*) c FROM GamePlayer WHERE game_id = ? AND is_eliminated = 0", (game_id,)).fetchone()["c"]
	if not standing:
		return setting(config, TIMER_DEFAULTS, "turn_seconds_min")

	held = db.execute("SELECT COUNT(*) c FROM Territory WHERE game_id = ? AND owner_id IS NOT NULL", (game_id,)).fetchone()["c"]
	alive = db.execute("SELECT COUNT(*) c FROM Unit WHERE game_id = ?", (game_id,)).fetchone()["c"]

	seconds = setting(config, TIMER_DEFAULTS, "turn_seconds_base") + (alive / standing) * setting(config, TIMER_DEFAULTS, "turn_seconds_per_unit") + (held / standing) * setting(config, TIMER_DEFAULTS, "turn_seconds_per_territory")
	return int(round(max(setting(config, TIMER_DEFAULTS, "turn_seconds_min"), min(setting(config, TIMER_DEFAULTS, "turn_seconds_max"), seconds))))


def set_deadline(db, game_id, config):
	seconds = turn_seconds(db, game_id, config)
	db.execute("UPDATE Game SET turn_deadline = datetime('now', ?) WHERE game_id = ?", (f"+{seconds} seconds", game_id))
	return seconds


def seconds_left(game):
	if game["turn_deadline"] is None:
		return None
	deadline = datetime.strptime(game["turn_deadline"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
	return max(0, int((deadline - datetime.now(timezone.utc)).total_seconds()))


def load_disasters(force=False):
	global _disasters
	if _disasters is None or force:
		merged = {}
		for path in sorted(DISASTERS_DIR.glob("*.json")):
			with open(path, "r", encoding="utf-8") as handle:
				merged.update(json.load(handle))
		_disasters = merged
	return _disasters


def pick_disaster(rng, layers_present):
	pool = [(key, spec) for key, spec in load_disasters().items() if spec.get("weight", 0) > 0 and any(layer in layers_present for layer in spec.get("layers", []))]
	if not pool:
		return None, None
	roll, running = rng.uniform(0, sum(spec["weight"] for _key, spec in pool)), 0
	for key, spec in pool:
		running += spec["weight"]
		if roll <= running:
			return key, spec
	return pool[-1]


def blast_zone(centre_ref, radius, adjacency, allowed):
	seen, edge = {centre_ref}, [centre_ref]
	for _step in range(max(0, int(radius))):
		nxt = []
		for ref in edge:
			for neighbour in adjacency.get(ref, ()):
				if neighbour in allowed and neighbour not in seen:
					seen.add(neighbour)
					nxt.append(neighbour)
		edge = nxt
	return seen


def plural(number, singular, many):
	return f"{number} {singular if number == 1 else many}"


def strike_units(db, game, tile, spec):
	damage = int(spec.get("unit_damage", 0))
	if damage <= 0:
		return 0
	killed = 0
	for unit in db.execute("SELECT unit_id, health FROM Unit WHERE game_id = ? AND territory_id = ?", (game["game_id"], tile["territory_id"])).fetchall():
		left = unit["health"] - damage
		if left <= 0:
			db.execute("DELETE FROM Unit WHERE unit_id = ?", (unit["unit_id"],))
			killed += 1
		else:
			db.execute("UPDATE Unit SET health = ? WHERE unit_id = ?", (left, unit["unit_id"]))
	return killed


def scar_tile(db, tile, spec, rng):
	fog = min(1.0, max(0.0, spec.get("fog_modifier", 1.0)))
	if rng.random() < spec.get("destroy_chance", 0.0):
		had = db.execute("SELECT improvement FROM Territory WHERE territory_id = ?", (tile["territory_id"],)).fetchone()
		db.execute("UPDATE Territory SET terrain_type = 'destroyed', resource_value = 0, improvement = NULL, has_city = 0, owner_id = NULL, fog_modifier = ? WHERE territory_id = ?", (fog, tile["territory_id"]))
		db.execute("DELETE FROM Unit WHERE territory_id = ?", (tile["territory_id"],))
		return 1 if had and had["improvement"] else 0

	db.execute("UPDATE Territory SET resource_value = MAX(0, resource_value + ?), fog_modifier = ? WHERE territory_id = ?", (int(spec.get("resource_delta", 0)), fog, tile["territory_id"]))
	if spec.get("wrecks_improvement"):
		return db.execute("UPDATE Territory SET improvement = NULL WHERE territory_id = ? AND improvement IS NOT NULL", (tile["territory_id"],)).rowcount
	return 0


def enrich_ring(db, spec, hit_refs, adjacency, allowed, by_ref):
	bonus = int(spec.get("enriches_ring", 0))
	if bonus <= 0:
		return
	ring = {n for ref in hit_refs for n in adjacency.get(ref, ()) if n in allowed and n not in hit_refs}
	for ref in ring:
		tile = by_ref.get(ref)
		if tile is not None:
			db.execute("UPDATE Territory SET resource_value = resource_value + ? WHERE territory_id = ? AND terrain_type <> 'destroyed'", (bonus, tile["territory_id"]))


def roll_disaster(db, game, config, adjacency, log, rng=None):
	rng = rng or random
	if game["current_turn"] < setting(config, DISASTER_DEFAULTS, "disaster_first_turn") or rng.random() >= setting(config, DISASTER_DEFAULTS, "disaster_chance"):
		return None

	tiles = db.execute("SELECT territory_id, map_territory_ref, layer, terrain_type FROM Territory WHERE game_id = ? AND terrain_type <> 'destroyed'", (game["game_id"],)).fetchall()
	if not tiles:
		return None

	key, spec = pick_disaster(rng, {row["layer"] for row in tiles})
	if key is None:
		return None
	candidates = [row for row in tiles if row["layer"] in spec.get("layers", [])]
	if not candidates:
		return None

	centre = rng.choice(candidates)
	allowed = {row["map_territory_ref"] for row in candidates}
	by_ref = {row["map_territory_ref"]: row for row in candidates}
	hit_refs = blast_zone(centre["map_territory_ref"], spec.get("radius", 1), adjacency, allowed)
	hit = [by_ref[ref] for ref in hit_refs if ref in by_ref]

	disaster_id = db.execute("INSERT INTO DisasterEvent (game_id, turn_number, disaster_type) VALUES (?, ?, ?)", (game["game_id"], game["current_turn"], key)).lastrowid
	razed = sum(db.execute("UPDATE Territory SET has_city = 0 WHERE territory_id = ? AND has_city = 1", (tile["territory_id"],)).rowcount for tile in hit) if spec.get("razes_city") else 0

	killed = wrecked = 0
	for tile in hit:
		db.execute("INSERT OR IGNORE INTO DisasterTerritory (disaster_id, territory_id) VALUES (?, ?)", (disaster_id, tile["territory_id"]))
		killed += strike_units(db, game, tile, spec)
		wrecked += scar_tile(db, tile, spec, rng)
	enrich_ring(db, spec, hit_refs, adjacency, allowed, by_ref)

	parts = [f"{spec.get('name', key)}: {spec.get('message', '')}".strip(), plural(len(hit), "territory", "territories") + " hit"]
	if killed:
		parts.append(plural(killed, "unit", "units") + " lost")
	if wrecked:
		parts.append(plural(wrecked, "improvement", "improvements") + " wrecked")
	if razed:
		parts.append(plural(razed, "city", "cities") + " razed")
	log.append(" - ".join(parts) + ".")
	return {"key": key, "tiles": len(hit)}


def disaster_log(db, game_id, limit=5):
	roster = load_disasters()
	rows = db.execute("SELECT d.disaster_id, d.turn_number, d.disaster_type, COUNT(dt.territory_id) AS tiles FROM DisasterEvent d LEFT JOIN DisasterTerritory dt ON dt.disaster_id = d.disaster_id WHERE d.game_id = ? GROUP BY d.disaster_id ORDER BY d.turn_number DESC, d.disaster_id DESC LIMIT ?", (game_id, limit)).fetchall()
	return [dict(row, name=roster.get(row["disaster_type"], {}).get("name", row["disaster_type"]), message=roster.get(row["disaster_type"], {}).get("message", "")) for row in rows]


def cost_modifier(reputation):
	return round(2.0 - (max(0, min(100, reputation)) / 100.0), 2)


def pact_cost(kind, reputation):
	return int(round(PACT_COST.get(kind, 0) * cost_modifier(reputation)))


def purse(db, game_id, user_id):
	row = db.execute("SELECT resources FROM GamePlayer WHERE game_id = ? AND user_id = ?", (game_id, user_id)).fetchone()
	return row["resources"] if row else 0


def reputation_of(db, user_id):
	row = db.execute("SELECT reputation FROM User WHERE user_id = ?", (user_id,)).fetchone()
	return row["reputation"] if row else 50


def standing_pact(db, game_id, a, b):
	return db.execute("SELECT * FROM DiplomacyAgreement WHERE game_id = ? AND status = 'active' AND agreement_type IN ('non_aggression', 'alliance') AND ((proposer_id = ? AND recipient_id = ?) OR (proposer_id = ? AND recipient_id = ?)) ORDER BY CASE agreement_type WHEN 'alliance' THEN 0 ELSE 1 END LIMIT 1", (game_id, a, b, b, a)).fetchone()


def are_allied(db, game_id, a, b):
	pact = standing_pact(db, game_id, a, b)
	return pact is not None and pact["agreement_type"] == "alliance"


def propose_pact(db, game, proposer_id, recipient_id, kind, turns, offer=0, request=0):
	game_id = game["game_id"]
	if kind not in PACT_KINDS:
		return ["That is not a kind of agreement."]
	if proposer_id == recipient_id:
		return ["You cannot make an agreement with yourself."]

	other = db.execute("SELECT * FROM GamePlayer WHERE game_id = ? AND user_id = ?", (game_id, recipient_id)).fetchone()
	if other is None:
		return ["That player is not in this game."]
	if other["is_eliminated"]:
		return ["That player is out of the game."]

	problems = []
	if kind == "trade":
		if offer <= 0 and request <= 0:
			problems.append("A trade needs resources on at least one side.")
		if offer < 0 or request < 0:
			problems.append("Trade amounts cannot be negative.")
		if offer > purse(db, game_id, proposer_id):
			problems.append("You cannot offer more resources than you hold.")
		turns = 0
	else:
		if turns < MIN_PACT_TURNS or turns > MAX_PACT_TURNS:
			problems.append(f"Duration must be between {MIN_PACT_TURNS} and {MAX_PACT_TURNS} turns.")
		if standing_pact(db, game_id, proposer_id, recipient_id):
			problems.append("You already have a pact with that player.")

	if db.execute("SELECT 1 FROM DiplomacyAgreement WHERE game_id = ? AND status = 'proposed' AND agreement_type = ? AND proposer_id = ? AND recipient_id = ?", (game_id, kind, proposer_id, recipient_id)).fetchone():
		problems.append("You have already offered that player this deal.")
	if problems:
		return problems

	db.execute("INSERT INTO DiplomacyAgreement (game_id, proposer_id, recipient_id, agreement_type, status, turns_remaining, terms_json, created_turn) VALUES (?, ?, ?, ?, 'proposed', ?, ?, ?)", (game_id, proposer_id, recipient_id, kind, turns, json.dumps({"offer": int(offer), "request": int(request)}), game["current_turn"]))
	db.commit()
	return []


def answer_pact(db, game, agreement_id, user_id, accept):
	game_id = game["game_id"]
	deal = db.execute("SELECT * FROM DiplomacyAgreement WHERE agreement_id = ? AND game_id = ? AND status = 'proposed'", (agreement_id, game_id)).fetchone()
	if deal is None:
		return ["That offer is no longer on the table."]
	if deal["recipient_id"] != user_id:
		return ["That offer was not made to you."]

	if not accept:
		db.execute("UPDATE DiplomacyAgreement SET status = 'declined' WHERE agreement_id = ?", (agreement_id,))
		db.commit()
		return []

	terms = json.loads(deal["terms_json"] or "{}")
	offer, request = int(terms.get("offer", 0)), int(terms.get("request", 0))

	if deal["agreement_type"] == "trade":
		if purse(db, game_id, deal["proposer_id"]) < offer:
			return ["They can no longer afford their side of the trade."]
		if purse(db, game_id, user_id) < request:
			return ["You cannot afford your side of the trade."]
		db.execute("UPDATE GamePlayer SET resources = resources - ? + ? WHERE game_id = ? AND user_id = ?", (offer, request, game_id, deal["proposer_id"]))
		db.execute("UPDATE GamePlayer SET resources = resources - ? + ? WHERE game_id = ? AND user_id = ?", (request, offer, game_id, user_id))
	else:
		price = pact_cost(deal["agreement_type"], reputation_of(db, deal["proposer_id"]))
		if purse(db, game_id, deal["proposer_id"]) < price:
			return ["They can no longer afford to sign that agreement."]
		db.execute("UPDATE GamePlayer SET resources = resources - ? WHERE game_id = ? AND user_id = ?", (price, game_id, deal["proposer_id"]))

	db.execute("UPDATE DiplomacyAgreement SET status = 'active' WHERE agreement_id = ?", (agreement_id,))
	db.commit()
	return []


def withdraw_pact(db, game, agreement_id, user_id):
	deal = db.execute("SELECT * FROM DiplomacyAgreement WHERE agreement_id = ? AND game_id = ? AND status = 'proposed'", (agreement_id, game["game_id"])).fetchone()
	if deal is None or deal["proposer_id"] != user_id:
		return ["That offer cannot be withdrawn."]
	db.execute("UPDATE DiplomacyAgreement SET status = 'declined' WHERE agreement_id = ?", (agreement_id,))
	db.commit()
	return []


def other_party(deal, user_id):
	return deal["recipient_id"] if deal["proposer_id"] == user_id else deal["proposer_id"]


def usernames(db, ids):
	found = {}
	for user_id in set(ids):
		row = db.execute("SELECT username FROM User WHERE user_id = ?", (user_id,)).fetchone()
		found[user_id] = row["username"] if row else "A player"
	return found


def break_pact(db, game, deal, breacher_id, log):
	kind = deal["agreement_type"]
	penalty = BREACH_PENALTY.get(kind, 10)
	db.execute("UPDATE DiplomacyAgreement SET status = 'breached', breached_by = ?, breach_type = ?, breached_turn = ? WHERE agreement_id = ?", (breacher_id, kind, game["current_turn"], deal["agreement_id"]))
	db.execute("UPDATE User SET reputation = MAX(0, reputation - ?) WHERE user_id = ?", (penalty, breacher_id))
	partner = other_party(deal, breacher_id)
	names = usernames(db, [breacher_id, partner])
	log.append(f"{names[breacher_id]} broke their {PACT_NAMES[kind].lower()} with {names[partner]} and lost {penalty} reputation.")


def detect_breaches(db, game, valid_orders, log):
	for order in valid_orders:
		if order["order_type"] != "attack" or not order["target_territory"]:
			continue
		target = db.execute("SELECT owner_id FROM Territory WHERE territory_id = ?", (order["target_territory"],)).fetchone()
		if target is None or target["owner_id"] is None or target["owner_id"] == order["player_id"]:
			continue
		pact = standing_pact(db, game["game_id"], order["player_id"], target["owner_id"])
		if pact is not None:
			break_pact(db, game, pact, order["player_id"], log)


def age_pacts(db, game, log):
	for deal in db.execute("SELECT * FROM DiplomacyAgreement WHERE game_id = ? AND status = 'active'", (game["game_id"],)).fetchall():
		if deal["turns_remaining"] <= 0:
			db.execute("UPDATE DiplomacyAgreement SET status = 'expired' WHERE agreement_id = ?", (deal["agreement_id"],))
			if deal["agreement_type"] != "trade":
				names = usernames(db, [deal["proposer_id"], deal["recipient_id"]])
				log.append(f"The {PACT_NAMES[deal['agreement_type']].lower()} between {names[deal['proposer_id']]} and {names[deal['recipient_id']]} has expired.")
			continue
		db.execute("UPDATE DiplomacyAgreement SET turns_remaining = turns_remaining - 1 WHERE agreement_id = ?", (deal["agreement_id"],))

	db.execute("UPDATE DiplomacyAgreement SET status = 'declined' WHERE game_id = ? AND status = 'proposed' AND created_turn < ?", (game["game_id"], game["current_turn"]))


def pact_board(db, game, user_id):
	game_id = game["game_id"]
	rows = db.execute("SELECT d.*, p.username AS proposer_name, r.username AS recipient_name FROM DiplomacyAgreement d JOIN User p ON p.user_id = d.proposer_id JOIN User r ON r.user_id = d.recipient_id WHERE d.game_id = ? AND (d.proposer_id = ? OR d.recipient_id = ?) ORDER BY d.agreement_id DESC", (game_id, user_id, user_id)).fetchall()

	incoming, outgoing, active, past = [], [], [], []
	for row in rows:
		item = dict(row, terms=json.loads(row["terms_json"] or "{}"), kind_name=PACT_NAMES.get(row["agreement_type"], row["agreement_type"]), other_id=other_party(row, user_id))
		item["other_name"] = row["recipient_name"] if row["proposer_id"] == user_id else row["proposer_name"]
		if row["status"] == "proposed":
			(incoming if row["recipient_id"] == user_id else outgoing).append(item)
		elif row["status"] == "active":
			active.append(item)
		else:
			past.append(item)

	partners = db.execute("SELECT gp.user_id, u.username, u.reputation FROM GamePlayer gp JOIN User u ON u.user_id = gp.user_id WHERE gp.game_id = ? AND gp.user_id <> ? AND gp.is_eliminated = 0 ORDER BY u.username", (game_id, user_id)).fetchall()
	reputation = reputation_of(db, user_id)
	return {"incoming": incoming, "outgoing": outgoing, "active": active, "history": past[:8], "partners": [dict(row) for row in partners], "reputation": reputation, "cost_modifier": cost_modifier(reputation), "costs": {kind: pact_cost(kind, reputation) for kind in PACT_KINDS}, "min_turns": MIN_PACT_TURNS, "max_turns": MAX_PACT_TURNS}


def finish(db, game_id, winner_id=None, drawn=()):
	drawn = set(drawn)
	db.execute("UPDATE Game SET status = 'complete', winner_id = ?, completed_at = datetime('now'), turn_deadline = NULL WHERE game_id = ?", (winner_id, game_id))
	for row in db.execute("SELECT user_id FROM GamePlayer WHERE game_id = ?", (game_id,)).fetchall():
		outcome = "win" if winner_id is not None and row["user_id"] == winner_id else ("draw" if row["user_id"] in drawn else "loss")
		db.execute("UPDATE GamePlayer SET result = ? WHERE game_id = ? AND user_id = ?", (outcome, game_id, row["user_id"]))


def territory_leaders(db, game_id):
	rows = db.execute("SELECT gp.user_id, u.username, (SELECT COUNT(*) FROM Territory t WHERE t.game_id = gp.game_id AND t.owner_id = gp.user_id) AS held FROM GamePlayer gp JOIN User u ON u.user_id = gp.user_id WHERE gp.game_id = ? AND gp.is_eliminated = 0 ORDER BY held DESC", (game_id,)).fetchall()
	if not rows:
		return [], 0
	best = rows[0]["held"]
	return [dict(row) for row in rows if row["held"] == best], best


def abandon(db, game, log):
	leaders, held = territory_leaders(db, game["game_id"])
	if not leaders:
		finish(db, game["game_id"])
		log.append("Everyone left. The game ended with no result.")
		return
	if len(leaders) == 1:
		finish(db, game["game_id"], winner_id=leaders[0]["user_id"])
		log.append(f"Everyone left. {leaders[0]['username']} takes it on territory with {held} tiles.")
		return
	finish(db, game["game_id"], drawn=[row["user_id"] for row in leaders])
	log.append(f"Everyone left. Drawn between {', '.join(row['username'] for row in leaders)} on {held} tiles each.")


def sweep_abandoned(db, force=False):
	if force:
		rows = db.execute("SELECT game_id, join_code FROM Game WHERE status IN ('lobby', 'active')").fetchall()
	else:
		rows = db.execute("SELECT g.game_id, g.join_code, m.layout_json FROM Game g LEFT JOIN Map m ON m.map_id = g.map_id WHERE g.status = 'active' AND g.turn_deadline IS NOT NULL").fetchall()

	ended = []
	for row in rows:
		game = db.execute("SELECT * FROM Game WHERE game_id = ?", (row["game_id"],)).fetchone()
		if game is None or game["status"] == "complete":
			continue
		if not force:
			config = json.loads(row["layout_json"]) if row["layout_json"] else {}
			grace = int(setting(config, {"abandon_after_seconds": ABANDON_SECONDS}, "abandon_after_seconds"))
			if not db.execute("SELECT 1 WHERE ? <= datetime('now', ?)", (game["turn_deadline"], f"-{grace} seconds")).fetchone():
				continue

		log = []
		if game["status"] == "lobby":
			finish(db, game["game_id"])
			log.append("Lobby abandoned before it started.")
		else:
			abandon(db, game, log)
		ended.append({"game_id": game["game_id"], "join_code": game["join_code"], "log": log})

	if ended:
		db.commit()
	return ended


def order_fault(order, adjacency, by_ref, crossings):
	if order["order_type"] == "build":
		return "the ground was destroyed" if order["source_terrain"] == "destroyed" else None
	if order["unit_id"] is None or order["owner_id"] != order["player_id"]:
		return "the unit no longer exists"
	if order["unit_at"] != order["source_territory"]:
		return "the unit had already moved"
	if order["source_layer"] is not None and order["unit_layer"] != order["source_layer"]:
		return "the unit was not on that layer"
	if order["source_terrain"] == "destroyed":
		return "the ground it stood on was destroyed"
	if order["target_territory"] is None:
		return "it had nowhere to go"
	if order["target_terrain"] is None:
		return "the destination no longer exists"
	if order["target_terrain"] == "destroyed":
		return "the destination was destroyed"

	if adjacency is None or by_ref is None:
		return None

	source_ref, target_ref = order["source_ref"], order["target_ref"]
	if source_ref not in by_ref or target_ref not in by_ref:
		return "the destination no longer exists"

	spec = world.get_unit(order["unit_type"])
	if spec is None:
		return "that unit type no longer exists"

	if order["order_type"] == "layer_transition":
		if by_ref[source_ref]["layer"] == by_ref[target_ref]["layer"]:
			return "that was not a change of layer"
		if source_ref not in crossings or target_ref not in crossings:
			return "there was no crossing there"
		if target_ref not in adjacency.get(source_ref, ()):
			return "the far side was not connected"
		return None

	if order["order_type"] == "attack" and spec.get("range", 1) > 1:
		if target_ref in world.within_range(source_ref, spec["range"], by_ref, adjacency):
			return None

	if target_ref not in world.reachable(source_ref, spec.get("movement", 1), order["unit_type"], by_ref, adjacency):
		return "the destination was out of reach"
	return None


def validate(db, game, log, adjacency=None, by_ref=None, crossings=frozenset()):
	pending = db.execute("SELECT o.*, u.owner_id, u.unit_type, u.territory_id AS unit_at, u.layer AS unit_layer, s.layer AS source_layer, s.terrain_type AS source_terrain, s.map_territory_ref AS source_ref, t.terrain_type AS target_terrain, t.map_territory_ref AS target_ref, p.username AS player_name FROM Orders o LEFT JOIN Unit u ON u.unit_id = o.unit_id LEFT JOIN Territory s ON s.territory_id = o.source_territory LEFT JOIN Territory t ON t.territory_id = o.target_territory LEFT JOIN User p ON p.user_id = o.player_id WHERE o.game_id = ? AND o.turn_number = ? AND o.status = 'pending'", (game["game_id"], game["current_turn"])).fetchall()

	valid = []
	for order in pending:
		reason = order_fault(order, adjacency, by_ref, crossings)
		if reason is None:
			valid.append(order)
			continue
		log.append(f"{order['player_name'] or 'A player'} had an order invalidated: {reason}.")
		db.execute("UPDATE Orders SET status = 'cancelled' WHERE order_id = ?", (order["order_id"],))
	return valid


def charge(db, game, player_id, cost):
	row = db.execute("SELECT resources FROM GamePlayer WHERE game_id = ? AND user_id = ?", (game["game_id"], player_id)).fetchone()
	if row is None or row["resources"] < cost:
		return False
	db.execute("UPDATE GamePlayer SET resources = resources - ? WHERE game_id = ? AND user_id = ?", (cost, game["game_id"], player_id))
	return True


def apply_builds(db, game, orders, log):
	for order in orders:
		if order["order_type"] != "build":
			continue
		kind, _sep, key = (order["detail"] or "").partition(":")
		tile = db.execute("SELECT territory_id, layer, owner_id, terrain_type, improvement, resource_value FROM Territory WHERE territory_id = ?", (order["target_territory"],)).fetchone()
		if tile is None or tile["owner_id"] != order["player_id"]:
			log.append("A build order was invalidated: the tile was lost.")
			continue

		if kind == "unit":
			spec = world.get_unit(key)
			if spec is None:
				continue
			if occupant_of(db, game["game_id"], tile["territory_id"]) is not None:
				log.append(f"A {spec['name']} was not built: the tile is occupied.")
				continue
			if not charge(db, game, order["player_id"], spec["cost"]):
				log.append(f"A {spec['name']} was not built: not enough resources.")
				continue
			db.execute("INSERT INTO Unit (game_id, owner_id, territory_id, unit_type, attack, defence, health, layer) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (game["game_id"], order["player_id"], tile["territory_id"], key, spec["attack"], spec["defence"], spec["health"], tile["layer"]))
			log.append(f"A {spec['name']} was built.")
		elif kind == "improvement":
			spec = world.get_improvement(key)
			if spec is None or tile["improvement"] is not None:
				continue
			if not charge(db, game, order["player_id"], spec["cost"]):
				log.append(f"A {spec['name']} was not built: not enough resources.")
				continue
			db.execute("UPDATE Territory SET improvement = ?, resource_value = resource_value + ? WHERE territory_id = ?", (key, spec["resource_bonus"], tile["territory_id"]))
			log.append(f"A {spec['name']} was completed.")


def occupant_of(db, game_id, territory_id):
	return db.execute("SELECT unit_id, owner_id, unit_type, attack, defence, health FROM Unit WHERE game_id = ? AND territory_id = ? LIMIT 1", (game_id, territory_id)).fetchone()


def hurt(db, unit_id, health, amount):
	left = health - amount
	if left <= 0:
		db.execute("DELETE FROM Unit WHERE unit_id = ?", (unit_id,))
		return True
	db.execute("UPDATE Unit SET health = ? WHERE unit_id = ?", (left, unit_id))
	return False


def bombard(db, game, order, log):
	spec = world.get_unit(order["unit_type"])
	target = occupant_of(db, game["game_id"], order["target_territory"])
	if spec is None or target is None or target["owner_id"] == order["player_id"]:
		return
	if hurt(db, target["unit_id"], target["health"], spec["attack"]):
		log.append(f"{spec['name']} destroyed a {world.get_unit(target['unit_type'])['name'] if world.get_unit(target['unit_type']) else 'unit'} at range.")
	else:
		log.append(f"{spec['name']} struck a defender at range.")


def melee(db, game, order, log):
	attacker = db.execute("SELECT unit_id, owner_id, unit_type, attack, health FROM Unit WHERE unit_id = ?", (order["unit_id"],)).fetchone()
	if attacker is None:
		return
	defender = occupant_of(db, game["game_id"], order["target_territory"])
	if defender is None:
		db.execute("UPDATE Unit SET territory_id = ?, layer = (SELECT layer FROM Territory WHERE territory_id = ?) WHERE unit_id = ?", (order["target_territory"], order["target_territory"], attacker["unit_id"]))
		return
	if defender["owner_id"] == attacker["owner_id"] or are_allied(db, game["game_id"], attacker["owner_id"], defender["owner_id"]):
		return

	attacker_spec = world.get_unit(attacker["unit_type"])
	defender_spec = world.get_unit(defender["unit_type"])
	if attacker_spec is None or defender_spec is None:
		return

	defender_died = hurt(db, defender["unit_id"], defender["health"], attacker_spec["attack"])
	attacker_died = hurt(db, attacker["unit_id"], attacker["health"], defender_spec["attack"])

	if defender_died and not attacker_died:
		db.execute("UPDATE Unit SET territory_id = ?, layer = (SELECT layer FROM Territory WHERE territory_id = ?) WHERE unit_id = ?", (order["target_territory"], order["target_territory"], attacker["unit_id"]))
		db.execute("UPDATE Territory SET owner_id = ? WHERE territory_id = ?", (attacker["owner_id"], order["target_territory"]))
		log.append(f"{attacker_spec['name']} killed a {defender_spec['name']} and took the ground.")
	elif defender_died and attacker_died:
		log.append(f"{attacker_spec['name']} and {defender_spec['name']} destroyed each other.")
	elif attacker_died:
		log.append(f"{attacker_spec['name']} broke against a {defender_spec['name']} and was lost.")
	else:
		log.append(f"{attacker_spec['name']} traded blows with a {defender_spec['name']} and held position.")


def resolve_orders(db, game, orders, adjacency, ref_of, log):
	for order in orders:
		if order["order_type"] != "attack":
			continue
		spec = world.get_unit(order["unit_type"])
		source_ref, target_ref = ref_of.get(order["source_territory"]), ref_of.get(order["target_territory"])
		if spec and spec.get("range", 1) > 1 and target_ref not in adjacency.get(source_ref, ()):
			bombard(db, game, order, log)

	for order in orders:
		if order["order_type"] != "attack":
			continue
		spec = world.get_unit(order["unit_type"])
		source_ref, target_ref = ref_of.get(order["source_territory"]), ref_of.get(order["target_territory"])
		if spec and spec.get("range", 1) > 1 and target_ref not in adjacency.get(source_ref, ()):
			continue
		melee(db, game, order, log)

	for order in orders:
		if order["order_type"] not in ("move", "layer_transition"):
			continue
		if db.execute("SELECT 1 FROM Unit WHERE unit_id = ?", (order["unit_id"],)).fetchone() is None:
			continue
		if occupant_of(db, game["game_id"], order["target_territory"]) is not None:
			log.append("A move was blocked: the tile was already taken.")
			continue
		target = db.execute("SELECT territory_id, layer FROM Territory WHERE territory_id = ?", (order["target_territory"],)).fetchone()
		if target is not None:
			db.execute("UPDATE Unit SET territory_id = ?, layer = ? WHERE unit_id = ?", (target["territory_id"], target["layer"], order["unit_id"]))


def claim_empty(db, game):
	for row in db.execute("SELECT t.territory_id, MIN(u.owner_id) AS claimant, COUNT(DISTINCT u.owner_id) AS sides FROM Territory t JOIN Unit u ON u.territory_id = t.territory_id WHERE t.game_id = ? AND t.owner_id IS NULL GROUP BY t.territory_id HAVING sides = 1", (game["game_id"],)).fetchall():
		db.execute("UPDATE Territory SET owner_id = ? WHERE territory_id = ?", (row["claimant"], row["territory_id"]))


def pay_income(db, game, log):
	pool = db.execute("SELECT global_resources FROM Game WHERE game_id = ?", (game["game_id"],)).fetchone()["global_resources"]
	for row in db.execute("SELECT gp.user_id, COALESCE(SUM(t.resource_value), 0) AS income FROM GamePlayer gp LEFT JOIN Territory t ON t.game_id = gp.game_id AND t.owner_id = gp.user_id WHERE gp.game_id = ? AND gp.is_eliminated = 0 GROUP BY gp.user_id ORDER BY gp.user_id", (game["game_id"],)).fetchall():
		if pool <= 0:
			break
		paid = min(row["income"], pool)
		if paid > 0:
			db.execute("UPDATE GamePlayer SET resources = resources + ? WHERE game_id = ? AND user_id = ?", (paid, game["game_id"], row["user_id"]))
			pool -= paid

	db.execute("UPDATE Game SET global_resources = ? WHERE game_id = ?", (pool, game["game_id"]))
	if pool <= 0:
		log.append("The world's resources are exhausted. Income has stopped.")


def check_elimination(db, game, log):
	for player in db.execute("SELECT user_id FROM GamePlayer WHERE game_id = ? AND is_eliminated = 0", (game["game_id"],)).fetchall():
		held = db.execute("SELECT COUNT(*) c FROM Territory WHERE game_id = ? AND owner_id = ?", (game["game_id"], player["user_id"])).fetchone()["c"]
		alive = db.execute("SELECT COUNT(*) c FROM Unit WHERE game_id = ? AND owner_id = ?", (game["game_id"], player["user_id"])).fetchone()["c"]
		if held == 0 and alive == 0:
			db.execute("UPDATE GamePlayer SET is_eliminated = 1 WHERE game_id = ? AND user_id = ?", (game["game_id"], player["user_id"]))
			log.append("A player has been eliminated.")


def check_victory(db, game, victory_share, log):
	standing = db.execute("SELECT gp.user_id, u.username FROM GamePlayer gp JOIN User u ON u.user_id = gp.user_id WHERE gp.game_id = ? AND gp.is_eliminated = 0", (game["game_id"],)).fetchall()

	winner = None
	if len(standing) == 1:
		winner = standing[0]
		log.append(f"{winner['username']} is the last player standing.")
	else:
		total = db.execute("SELECT COUNT(*) c FROM Territory WHERE game_id = ?", (game["game_id"],)).fetchone()["c"]
		best = 0
		for player in standing:
			held = db.execute("SELECT COUNT(*) c FROM Territory WHERE game_id = ? AND owner_id = ?", (game["game_id"], player["user_id"])).fetchone()["c"]
			if total and held / total >= victory_share and held > best:
				winner, best = player, held
		if winner is not None:
			log.append(f"{winner['username']} controls {best} of {total} territories.")

	if winner is None:
		return None
	finish(db, game["game_id"], winner_id=winner["user_id"])
	return winner["user_id"]


def resolve_turn(db, game, map_row):
	log = []
	layout = world.get_layout(map_row, game)
	config = layout["config"]
	adjacency = world.build_adjacency(layout)

	by_ref = {row["map_territory_ref"]: dict(row) for row in db.execute("SELECT map_territory_ref, layer, terrain_type FROM Territory WHERE game_id = ?", (game["game_id"],))}
	crossings = world.transition_refs(layout)

	roll_disaster(db, game, config, adjacency, log)
	valid = validate(db, game, log, adjacency, by_ref, crossings)
	detect_breaches(db, game, valid, log)
	apply_builds(db, game, valid, log)
	ref_of = {row["territory_id"]: row["map_territory_ref"] for row in db.execute("SELECT territory_id, map_territory_ref FROM Territory WHERE game_id = ?", (game["game_id"],))}
	resolve_orders(db, game, valid, adjacency, ref_of, log)
	claim_empty(db, game)
	pay_income(db, game, log)
	check_elimination(db, game, log)
	winner_id = check_victory(db, game, config.get("victory_territory_share", DEFAULT_VICTORY_SHARE), log)

	db.execute("UPDATE Orders SET status = 'resolved' WHERE game_id = ? AND turn_number = ? AND status = 'pending'", (game["game_id"], game["current_turn"]))
	if winner_id is None:
		db.execute("UPDATE Game SET current_turn = current_turn + 1 WHERE game_id = ?", (game["game_id"],))
		db.execute("UPDATE GamePlayer SET submitted_turn = NULL WHERE game_id = ?", (game["game_id"],))
		age_pacts(db, game, log)
		if game["timer_on"]:
			set_deadline(db, game["game_id"], config)
	db.commit()

	log.append(f"Turn {game['current_turn']} resolved.")
	return {"log": log, "winner_id": winner_id}

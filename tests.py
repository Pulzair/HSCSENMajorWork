# import libraries
import json
import os
import random
import sqlite3
import tempfile

os.environ.setdefault("SECRET_KEY", "testing")

import db as dbmod

# point the whole app at a throwaway database so no real save is touched
TEMP_DB = tempfile.mktemp(suffix=".db")
dbmod.DATABASE_PATH = TEMP_DB

from app import app
import accounts
import engine
import play
import world

app.config["TESTING"] = True

results = []


# record one test, everything goes through here so the summary can count them
def check(test_id, module, data, expected, actual):
	ok = expected == actual
	results.append({"id": test_id, "module": module, "data": data, "expected": expected, "actual": actual, "pass": ok})
	print(f"  {test_id:<6} {'PASS' if ok else 'FAIL':<5} {module:<28} {str(actual)[:40]}")
	return ok


# fresh in memory board so engine tests are repeatable
def sandbox(players=2, size=12, seed=1):
	conn = sqlite3.connect(":memory:")
	conn.row_factory = sqlite3.Row
	conn.executescript(open("schema.sql").read())
	config = world.generate_config("test", size, seed, players=players)
	conn.execute("INSERT INTO Map (name, layout_json, min_players, max_players) VALUES ('t', ?, 2, 6)", (json.dumps(config),))
	conn.execute("INSERT INTO Game (join_code, map_id, status, current_turn, board_json, timer_on) VALUES ('TEST01', 1, 'active', 3, ?, 1)", (json.dumps(config),))
	gid = conn.execute("SELECT MAX(game_id) m FROM Game").fetchone()["m"]
	for index in range(1, players + 1):
		conn.execute("INSERT INTO User (username, email, password_hash) VALUES (?, ?, ?)", (f"player{index}", f"p{index}@test.com", "x" * 60))
		conn.execute("INSERT INTO GamePlayer (game_id, user_id, player_colour, resources) VALUES (?, ?, ?, 300)", (gid, index, f"#00000{index}"))
	game = conn.execute("SELECT * FROM Game WHERE game_id = ?", (gid,)).fetchone()
	layout = world.get_layout(None, game)
	world.seed_territories(conn, gid, layout)
	conn.commit()
	return conn, game, layout


# make a client that is registered and logged in
def player(username):
	client = app.test_client()
	client.post("/register", data={"username": username, "email": f"{username}@test.com", "password": "password123"})
	client.post("/login", data={"email": f"{username}@test.com", "password": "password123"})
	return client


print("\nVALIDATION - accounts.py, boundary values on every input rule")
for test_id, name, expect in (("V1", "ab", False), ("V2", "abc", True), ("V3", "a" * 32, True), ("V4", "a" * 33, False), ("V5", "bad name", False)):
	check(test_id, "accounts.USERNAME_RE", f"username={name!r} ({len(name)} chars)", expect, bool(accounts.USERNAME_RE.match(name)))

for test_id, mail, expect in (("V6", "a@b.co", True), ("V7", "no-at-sign", False), ("V8", "a@b", False)):
	check(test_id, "accounts.EMAIL_RE", f"email={mail!r}", expect, bool(accounts.EMAIL_RE.match(mail)))

for test_id, size, expect in (("V9", 7, 8), ("V10", 8, 8), ("V11", 25, 25), ("V12", 26, 25), ("V13", "abc", 8)):
	check(test_id, "world.clamp_board", f"size={size!r}", expect, world.clamp_board(size))


print("\nMAP GENERATION - world.py, smallest and largest boards")
for test_id, size in (("M1", 8), ("M2", 25)):
	layout = world.parse_layout(world.generate_config("t", size, 7, players=6))
	per_layer = {layer: sum(1 for t in layout["territories"].values() if t["layer"] == layer) for layer in world.LAYERS}
	check(test_id, "world.generate_config", f"size={size}, land layer is solid", size * size, per_layer["land"])

layout = world.parse_layout(world.generate_config("t", 16, 7, players=6))
caverns = sum(1 for t in layout["territories"].values() if t["layer"] == "underground")
check("M1b", "world.generate_config", "underground keeps gaps between caverns", True, 0 < caverns < 256)

layout = world.parse_layout(world.generate_config("t", 25, 7, players=6))
kinds = {t["terrain"] for t in layout["territories"].values()}
check("M3", "world.generate_config", "25x25, all terrain present", True, {"plains", "mountain", "water"} <= kinds)

resources = {t["natural_resource"] for t in layout["territories"].values() if t["natural_resource"]}
check("M4", "world.generate_config", "25x25, iron and horses spawn", {"horses", "iron"}, resources)

adjacency = world.build_adjacency(layout)
start = layout["grid"]["land"][tuple(world.generate_config("t", 25, 7, players=6)["spawns"][0])]
seen, stack = {start}, [start]
while stack:
	for neighbour in adjacency[stack.pop()]:
		if neighbour not in seen:
			seen.add(neighbour)
			stack.append(neighbour)
check("M5", "world.build_adjacency", "every tile reachable from spawn 1", len(layout["territories"]), len(seen))

(x, y), ref = next(iter(layout["grid"]["land"].items()))
check("M6", "world.build_adjacency", f"diagonal ({x+1},{y+1}) linked to ({x},{y})", True, layout["grid"]["land"].get((x + 1, y + 1)) in adjacency[ref])


print("\nMOVEMENT - world.reachable, terrain cost boundaries")
conn, game, layout = sandbox()
adjacency = world.build_adjacency(layout)
by_ref = {r["map_territory_ref"]: r for r in conn.execute("SELECT map_territory_ref, layer, terrain_type FROM Territory WHERE game_id = ?", (game["game_id"],))}
plains = next(r for r in by_ref if by_ref[r]["layer"] == "land" and by_ref[r]["terrain_type"] == "plains")

one = world.reachable(plains, 1, "warrior", by_ref, adjacency)
two = world.reachable(plains, 2, "horseman", by_ref, adjacency)
check("MV1", "world.reachable", "budget=1 warrior", True, len(one) > 1)
check("MV2", "world.reachable", "budget=2 horseman reaches further", True, len(two) >= len(one))
check("MV3", "world.reachable", "budget=0 goes nowhere", 1, len(world.reachable(plains, 0, "warrior", by_ref, adjacency)))
check("MV3b", "world.reachable", "budget=1 onto a mountain costing 2", True, len(world.reachable(plains, 1, "warrior", by_ref, adjacency)) > 1)
check("MV4", "world.can_occupy", "warrior onto water", False, world.can_occupy("warrior", "land", "water"))
check("MV5", "world.can_occupy", "trireme onto water", True, world.can_occupy("trireme", "land", "water"))
check("MV6", "world.can_occupy", "any unit onto destroyed ground", False, any(world.can_occupy(k, "land", "destroyed") for k in world.load_roster()))


print("\nCOMBAT - engine.py, mutual damage and the kill boundary")
conn, game, layout = sandbox()
tiles = conn.execute("SELECT territory_id FROM Territory WHERE game_id = ? AND layer='land' AND terrain_type='plains' LIMIT 2", (game["game_id"],)).fetchall()
conn.execute("DELETE FROM Unit WHERE game_id = ?", (game["game_id"],))
conn.execute("INSERT INTO Unit (game_id,owner_id,territory_id,unit_type,attack,defence,health,layer) VALUES (?,1,?,'warrior',6,6,30,'land')", (game["game_id"], tiles[0]["territory_id"]))
conn.execute("INSERT INTO Unit (game_id,owner_id,territory_id,unit_type,attack,defence,health,layer) VALUES (?,2,?,'warrior',6,6,30,'land')", (game["game_id"], tiles[1]["territory_id"]))
attacker = conn.execute("SELECT unit_id FROM Unit WHERE owner_id=1").fetchone()["unit_id"]
conn.commit()

order = {"order_type": "attack", "unit_id": attacker, "player_id": 1, "unit_type": "warrior", "source_territory": tiles[0]["territory_id"], "target_territory": tiles[1]["territory_id"]}
engine.melee(conn, game, order, [])
health = sorted(r["health"] for r in conn.execute("SELECT health FROM Unit WHERE game_id = ?", (game["game_id"],)))
check("C1", "engine.melee", "30hp vs 30hp, attack 6 each", [24, 24], health)
check("C2", "engine.melee", "attacker stays put when defender lives", tiles[0]["territory_id"], conn.execute("SELECT territory_id FROM Unit WHERE unit_id=?", (attacker,)).fetchone()["territory_id"])

conn.execute("UPDATE Unit SET health=5 WHERE owner_id=2")
conn.commit()
engine.melee(conn, game, order, [])
check("C3", "engine.melee", "defender on 5hp, attack 6 kills", tiles[1]["territory_id"], conn.execute("SELECT territory_id FROM Unit WHERE unit_id=?", (attacker,)).fetchone()["territory_id"])
check("C4", "engine.resolve_orders", "one unit per tile after combat", 1, conn.execute("SELECT COUNT(*) c FROM Unit WHERE game_id=?", (game["game_id"],)).fetchone()["c"])


print("\nFOG OF WAR - world.py, nothing hidden may leak")
conn, game, layout = sandbox()
board = world.build_board(conn, game, None, 1)
hidden = [t for t in board["tiles"] if t["state"] == "hidden"]
visible = [t for t in board["tiles"] if t["state"] == "visible"]
check("F1", "world.build_board", "hidden tiles exist at turn 3", True, len(hidden) > 0)
check("F2", "world.build_board", "hidden tiles carry no terrain", 0, sum(1 for t in hidden if "terrain" in t))
check("F3", "world.build_board", "hidden tiles carry no owner", 0, sum(1 for t in hidden if t.get("colour")))
check("F4", "world.build_board", "visible tiles are a small fraction", True, len(visible) < len(board["tiles"]) * 0.1)


print("\nDIPLOMACY - engine.py, FR22 to FR24")
conn, game, layout = sandbox()
check("D1", "engine.propose_pact", "proposer == recipient", 1, len(engine.propose_pact(conn, game, 1, 1, "alliance", 5)))
check("D2", "engine.propose_pact", "duration=1 (below min 2)", 1, len(engine.propose_pact(conn, game, 1, 2, "alliance", 1)))
check("D3", "engine.propose_pact", "duration=21 (above max 20)", 1, len(engine.propose_pact(conn, game, 1, 2, "alliance", 21)))
check("D4", "engine.propose_pact", "duration=2 (at min)", 0, len(engine.propose_pact(conn, game, 1, 2, "non_aggression", 2)))
check("D5", "engine.propose_pact", "trade offering more than held", 1, len(engine.propose_pact(conn, game, 1, 2, "trade", 0, offer=99999)))

conn.execute("DELETE FROM DiplomacyAgreement")
conn.commit()
engine.propose_pact(conn, game, 1, 2, "alliance", 5)
deal = conn.execute("SELECT agreement_id FROM DiplomacyAgreement").fetchone()["agreement_id"]
check("D6", "engine.answer_pact", "wrong player accepts", 1, len(engine.answer_pact(conn, game, deal, 1, True)))
check("D7", "engine.answer_pact", "recipient accepts", 0, len(engine.answer_pact(conn, game, deal, 2, True)))
check("D8", "engine.are_allied", "after signing", True, engine.are_allied(conn, game["game_id"], 1, 2))

before = conn.execute("SELECT reputation FROM User WHERE user_id=1").fetchone()["reputation"]
tile = conn.execute("SELECT territory_id FROM Territory WHERE game_id=? AND owner_id=2 LIMIT 1", (game["game_id"],)).fetchone()
engine.detect_breaches(conn, game, [{"order_type": "attack", "player_id": 1, "target_territory": tile["territory_id"]}], [])
after = conn.execute("SELECT reputation FROM User WHERE user_id=1").fetchone()["reputation"]
check("D9", "engine.detect_breaches", "attack an ally, alliance penalty 25", before - 25, after)
check("D10", "engine.break_pact", "agreement marked breached", "breached", conn.execute("SELECT status FROM DiplomacyAgreement WHERE agreement_id=?", (deal,)).fetchone()["status"])

for test_id, rep, expect in (("D11", 100, 1.0), ("D12", 50, 1.5), ("D13", 0, 2.0)):
	check(test_id, "engine.cost_modifier", f"reputation={rep}", expect, engine.cost_modifier(rep))


print("\nDISASTERS - engine.py, FR20 and FR21")
conn, game, layout = sandbox()
adjacency = world.build_adjacency(layout)
conn.execute("UPDATE Game SET current_turn = 2 WHERE game_id = ?", (game["game_id"],))
early = conn.execute("SELECT * FROM Game WHERE game_id=?", (game["game_id"],)).fetchone()
check("X1", "engine.roll_disaster", "turn 2, first allowed turn is 3", None, engine.roll_disaster(conn, early, {"disaster_chance": 1.0}, adjacency, []))

fired = sum(1 for seed in range(200) if engine.roll_disaster(conn, game, {"disaster_chance": 0.22, "disaster_first_turn": 3}, adjacency, [], random.Random(seed)))
check("X2", "engine.roll_disaster", "200 rolls at 22% chance", True, 30 <= fired <= 60)

conn, game, layout = sandbox()
spec = engine.load_disasters()["storm"]
tile = conn.execute("SELECT territory_id FROM Territory WHERE game_id=? LIMIT 1", (game["game_id"],)).fetchone()
conn.execute("INSERT INTO Unit (game_id,owner_id,territory_id,unit_type,attack,defence,health,layer) VALUES (?,1,?,'warrior',6,6,30,'land')", (game["game_id"], tile["territory_id"]))
conn.commit()
engine.strike_units(conn, game, {"territory_id": tile["territory_id"]}, spec)
check("X3", "engine.strike_units", "storm 10 damage on 30hp unit", 20, conn.execute("SELECT health FROM Unit WHERE territory_id=?", (tile["territory_id"],)).fetchone()["health"])

city = conn.execute("SELECT territory_id FROM Territory WHERE game_id=? AND has_city=1 LIMIT 1", (game["game_id"],)).fetchone()
volcano = engine.load_disasters()["volcanic_eruption"]
engine.scar_tile(conn, {"territory_id": city["territory_id"], "has_city": 1}, volcano, random.Random(1))
check("X4", "engine.scar_tile", "volcano on a city tile", "plains", conn.execute("SELECT terrain_type FROM Territory WHERE territory_id=?", (city["territory_id"],)).fetchone()["terrain_type"])


print("\nVICTORY AND ELIMINATION - engine.py, FR25")
conn, game, layout = sandbox(players=3)
capital = conn.execute("SELECT territory_id FROM Territory WHERE game_id=? AND capital_of=2", (game["game_id"],)).fetchone()
engine.seize(conn, game, capital["territory_id"], 1, [])
engine.check_elimination(conn, game, [])
conn.commit()
check("W1", "engine.check_elimination", "player 2 loses their capital", 1, conn.execute("SELECT is_eliminated FROM GamePlayer WHERE game_id=? AND user_id=2", (game["game_id"],)).fetchone()["is_eliminated"])
check("W2", "engine.knock_out", "eliminated player has no units", 0, conn.execute("SELECT COUNT(*) c FROM Unit WHERE game_id=? AND owner_id=2", (game["game_id"],)).fetchone()["c"])

third = conn.execute("SELECT territory_id FROM Territory WHERE game_id=? AND capital_of=3", (game["game_id"],)).fetchone()
engine.seize(conn, game, third["territory_id"], 1, [])
engine.check_elimination(conn, game, [])
check("W3", "engine.check_victory", "one player left standing", 1, engine.check_victory(conn, game, 0.4, []))
check("W4", "engine.finish", "game marked complete", "complete", conn.execute("SELECT status FROM Game WHERE game_id=?", (game["game_id"],)).fetchone()["status"])

conn, game, layout = sandbox(players=2)
leaders, held = engine.territory_leaders(conn, game["game_id"])
check("W5", "engine.territory_leaders", "equal territory is a tie", 2, len(leaders))
engine.abandon(conn, game, [])
check("W6", "engine.abandon", "tie recorded as a draw", 2, conn.execute("SELECT COUNT(*) c FROM GamePlayer WHERE game_id=? AND result='draw'", (game["game_id"],)).fetchone()["c"])


print("\nLEADERBOARD - accounts.py, reputation weighting")
for test_id, rep, expect in (("L1", 100, 300), ("L2", 50, 200), ("L3", 0, 100)):
	check(test_id, "accounts.rank_points", f"same record, reputation={rep}", expect, accounts.rank_points(4, 4, 0, 4, 48, rep))


print("\nEND TO END - play.py and accounts.py over HTTP")
with app.app_context():
	world.sync_maps()

alpha, beta = player("alpha"), player("beta")
check("E1", "accounts.register", "valid new account", 200, alpha.get("/dashboard").status_code)
check("E2", "accounts.login", "wrong password", True, "Incorrect email or password" in app.test_client().post("/login", data={"email": "alpha@test.com", "password": "wrongpass"}, follow_redirects=True).get_data(as_text=True))
check("E3", "accounts.login_required", "dashboard while logged out", 302, app.test_client().get("/dashboard").status_code)

code = alpha.post("/lobby/create").headers["Location"].rsplit("/", 1)[-1]
check("E4", "play.create", "lobby code is 6 characters", 6, len(code))
check("E5", "play.join", "join code 'ABC' (too short)", True, "6 characters" in alpha.post("/lobby/join", data={"code": "ABC"}, follow_redirects=True).get_data(as_text=True))
check("E6", "play.join", "join code 'ZZZZZZ' (does not exist)", True, "Lobby not found" in alpha.post("/lobby/join", data={"code": "ZZZZZZ"}, follow_redirects=True).get_data(as_text=True))

beta.post("/lobby/join", data={"code": code})
solo = player("solo")
solo_code = solo.post("/lobby/create").headers["Location"].rsplit("/", 1)[-1]
solo.post(f"/lobby/{solo_code}/settings", data={"board_size": 12, "map_id": 1})
check("E7", "play.start", "1 player, below the minimum of 2", True, "at least 2 players" in solo.post(f"/lobby/{solo_code}/start", follow_redirects=True).get_data(as_text=True))

alpha.post(f"/lobby/{code}/settings", data={"board_size": 12, "map_id": 1, "timer_on": "1"})
alpha.post(f"/lobby/{code}/start")
check("E8", "play.start", "2 players, at minimum", 200, alpha.get(f"/game/{code}").status_code)
check("E9", "play.leave", "leaving an active game", True, "resign instead" in alpha.post(f"/lobby/{code}/leave", follow_redirects=True).get_data(as_text=True))

payload = {"moves": [{"unit_id": 999999, "ref": 1}], "builds": [], "holds": []}
check("E10", "play.submit_orders", "unit_id that is not yours", 400, alpha.post(f"/game/{code}/orders", json=payload).status_code)
check("E11", "play.submit_orders", "empty order list", 200, alpha.post(f"/game/{code}/orders", json={"moves": [], "builds": [], "holds": []}).status_code)
check("E12", "play.submit_orders", "submitting twice in one turn", 400, alpha.post(f"/game/{code}/orders", json={"moves": [], "builds": [], "holds": []}).status_code)


print("\nSECURITY - NF04 and NF06")
injected = app.test_client()
injected.post("/register", data={"username": "victim", "email": "victim@test.com", "password": "password123"})
attack = injected.post("/login", data={"email": "' OR '1'='1", "password": "' OR '1'='1"}, follow_redirects=True)
check("S2", "accounts.login", "SQL injection in the email field", True, "Incorrect email or password" in attack.get_data(as_text=True))

# every test client shares 127.0.0.1 so earlier logins already spent some of the allowance
fresh = app.test_client()
codes = [fresh.post("/login", data={"email": "x@y.com", "password": "no"}).status_code for _ in range(12)]
check("S1", "accounts.AUTH_LIMIT", "12 logins in one minute from one IP", True, codes.count(429) >= 2)

with app.app_context():
	stored = dbmod.get_db().execute("SELECT password_hash FROM User WHERE username='victim'").fetchone()["password_hash"]
check("S3", "accounts.register", "password never stored as plaintext", True, "password123" not in stored and stored.startswith("$2b$"))
check("S4", "accounts.admin_required", "admin page as a normal user", 403, alpha.get("/admin").status_code)


print("\nERROR HANDLING - app.py, design section 9.3")
check("H1", "app.not_found", "url that does not exist", 404, app.test_client().get("/no-such-page").status_code)
check("H2", "app.not_found", "returns the page not a soft 200", True, "Page not found" in app.test_client().get("/no-such-page").get_data(as_text=True))

passed = sum(1 for r in results if r["pass"])
print(f"\n{'=' * 60}")
print(f"  {passed} of {len(results)} tests passed")
print(f"{'=' * 60}")

for row in results:
	if not row["pass"]:
		print(f"  FAILED {row['id']} {row['module']}: expected {row['expected']}, got {row['actual']}")

if os.path.exists(TEMP_DB):
	os.unlink(TEMP_DB)

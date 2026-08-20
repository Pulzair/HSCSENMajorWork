import json
import re
import secrets

from flask import Blueprint, flash, g, jsonify, redirect, render_template, request, session, url_for
from flask_socketio import join_room

import engine
import world
from accounts import login_required
from db import get_db
from extensions import socketio

bp = Blueprint("play", __name__)

MIN_PLAYERS = 2
MAX_PLAYERS = 6
CODE_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
CODE_RE = re.compile(r"^[A-Z0-9]{6}$")
COLOURS = ["#E63946", "#457B9D", "#2A9D8F", "#E9C46A", "#8338EC", "#F4A261"]
BOARD_CHOICES = (0, 12, 16, 20, 25)


# register the blueprint
def init_app(app):
	app.register_blueprint(bp)


# socketio room name for a game
def room_of(game_id):
	return f"game_{game_id}"


# random 6 character join code, retry until its unique
def new_code(db):
	for _try in range(20):
		code = "".join(secrets.choice(CODE_ALPHABET) for _char in range(6))
		if not db.execute("SELECT 1 FROM Game WHERE join_code = ?", (code,)).fetchone():
			return code
	raise RuntimeError("Could not generate a unique join code")


# first player colour not already taken in this lobby
def free_colour(db, game_id):
	taken = {row["player_colour"] for row in db.execute("SELECT player_colour FROM GamePlayer WHERE game_id = ?", (game_id,))}
	return next((colour for colour in COLOURS if colour not in taken), None)


# get a game row by its join code
def fetch_game(db, code):
	return db.execute("SELECT * FROM Game WHERE join_code = ?", (code,)).fetchone()


# everyone in a game with their username and reputation
def fetch_players(db, game_id):
	return db.execute("SELECT gp.*, u.username, u.reputation FROM GamePlayer gp JOIN User u ON u.user_id = gp.user_id WHERE gp.game_id = ? ORDER BY gp.gameplayer_id", (game_id,)).fetchall()


# pull one player out of the list
def find_player(players, user_id):
	return next((player for player in players if player["user_id"] == user_id), None)


# the preset map row if there is one
def fetch_map(db, game):
	return None if game["map_id"] is None else db.execute("SELECT * FROM Map WHERE map_id = ?", (game["map_id"],)).fetchone()


# max players, the map cap or 6 whichever is lower
def capacity(db, game):
	map_row = fetch_map(db, game)
	return MAX_PLAYERS if map_row is None else min(map_row["max_players"], MAX_PLAYERS)


# who has locked orders in, eliminated players dont count
def submission_status(db, game):
	rows = db.execute("SELECT gp.user_id, u.username, gp.is_eliminated, (gp.submitted_turn = ?) AS ready FROM GamePlayer gp JOIN User u ON u.user_id = gp.user_id WHERE gp.game_id = ? ORDER BY gp.gameplayer_id", (game["current_turn"], game["game_id"])).fetchall()
	active = [row for row in rows if not row["is_eliminated"]]
	return {"players": rows, "ready": sum(1 for row in active if row["ready"]), "total": len(active), "all_in": bool(active) and all(row["ready"] for row in active)}


# special resources you own, unlocks horseman and catapult
def held_resources(db, game_id, user_id):
	return {row["natural_resource"] for row in db.execute("SELECT DISTINCT natural_resource FROM Territory WHERE game_id = ? AND owner_id = ? AND natural_resource IS NOT NULL", (game_id, user_id))}


# every legal order for each of your units, sent to the browser
def legal_moves(db, game, user_id, layout, adjacency, visible):
	by_ref = {row["map_territory_ref"]: row for row in db.execute("SELECT territory_id, map_territory_ref, layer, terrain_type, natural_resource FROM Territory WHERE game_id = ?", (game["game_id"],))}
	occupants = {}
	for row in db.execute("SELECT t.map_territory_ref, u.owner_id FROM Unit u JOIN Territory t ON t.territory_id = u.territory_id WHERE u.game_id = ?", (game["game_id"],)):
		occupants.setdefault(row["map_territory_ref"], []).append(row["owner_id"])

	crossings = world.transition_refs(layout, world.gateway_refs(db, game["game_id"]))
	moves = {}
	for unit in db.execute("SELECT u.unit_id, u.unit_type, u.layer, u.health, t.map_territory_ref FROM Unit u JOIN Territory t ON t.territory_id = u.territory_id WHERE u.game_id = ? AND u.owner_id = ? ORDER BY u.unit_id", (game["game_id"], user_id)).fetchall():
		spec = world.get_unit(unit["unit_type"])
		if spec is None:
			continue

		here = unit["map_territory_ref"]
		reach = spec.get("range", 1)
		options = []
		taken = set()

		for ref, cost in world.reachable(here, spec.get("movement", 1), unit["unit_type"], by_ref, adjacency).items():
			if ref == here:
				continue
			here_owners = occupants.get(ref, [])
			enemies = [owner for owner in here_owners if owner != user_id]
			if here_owners and not enemies:
				continue
			if enemies and ref not in visible:
				continue
			options.append({"ref": ref, "kind": "attack" if enemies else "move", "cost": cost, "ranged": False})
			taken.add(ref)

		if reach > 1:
			for ref in world.within_range(here, reach, by_ref, adjacency):
				if ref in taken or ref not in visible:
					continue
				enemies = [owner for owner in occupants.get(ref, []) if owner != user_id]
				if not enemies:
					continue
				target = by_ref.get(ref)
				if target is None or not world.can_occupy(unit["unit_type"], target["layer"], target["terrain_type"]):
					continue
				options.append({"ref": ref, "kind": "attack", "cost": 0, "ranged": True})
				taken.add(ref)

		if world.can_transition(unit["unit_type"]) and here in crossings:
			for ref in adjacency.get(here, ()):
				target = by_ref.get(ref)
				if target is None or target["layer"] == unit["layer"] or ref in taken:
					continue
				if occupants.get(ref):
					continue
				if ref in crossings and world.can_occupy(unit["unit_type"], target["layer"], target["terrain_type"]):
					options.append({"ref": ref, "kind": "layer_transition", "cost": 1, "ranged": False})
					taken.add(ref)

		moves[unit["unit_id"]] = {"unit_id": unit["unit_id"], "type": unit["unit_type"], "name": spec["name"], "ref": here, "layer": unit["layer"], "health": unit["health"], "max_health": spec["health"], "movement": spec.get("movement", 1), "range": reach, "on_crossing": here in crossings, "can_transition": world.can_transition(unit["unit_type"]), "moves": options}
	return moves


# what each city or barracks can make, own tile or a neighbour
def production_menu(db, game, user_id, adjacency=None, by_ref=None):
	budget = db.execute("SELECT resources FROM GamePlayer WHERE game_id = ? AND user_id = ?", (game["game_id"], user_id)).fetchone()
	budget = budget["resources"] if budget else 0
	stock = held_resources(db, game["game_id"], user_id)
	filled = {row["map_territory_ref"] for row in db.execute("SELECT t.map_territory_ref FROM Unit u JOIN Territory t ON t.territory_id = u.territory_id WHERE u.game_id = ?", (game["game_id"],))}

	sites = {}
	for tile in db.execute("SELECT territory_id, map_territory_ref, layer, terrain_type, has_city, improvement FROM Territory WHERE game_id = ? AND owner_id = ? AND terrain_type <> 'destroyed'", (game["game_id"], user_id)).fetchall():
		entries = []
		produces = tile["has_city"] or world.allows_production(tile["improvement"])

		if produces:
			spots = [tile["map_territory_ref"]] + [ref for ref in adjacency.get(tile["map_territory_ref"], ()) if by_ref and ref in by_ref]
			for key in world.load_roster():
				spec = world.get_unit(key)
				landing = next((ref for ref in spots if ref not in filled and by_ref and world.can_occupy(key, by_ref[ref]["layer"], by_ref[ref]["terrain_type"])), None)
				if landing is None:
					continue
				needs = spec.get("requires")
				blocked = None
				if needs and needs not in stock:
					blocked = "needs " + needs
				elif spec["cost"] > budget:
					blocked = "too dear"
				entries.append({"token": f"unit:{key}", "label": spec["name"], "cost": spec["cost"], "blocked": blocked, "landing": landing, "away": landing != tile["map_territory_ref"]})

		if tile["improvement"] is None and not tile["has_city"]:
			for key in world.improvement_options(tile["layer"], tile["terrain_type"]):
				spec = world.get_improvement(key)
				entries.append({"token": f"improvement:{key}", "label": spec["name"], "cost": spec["cost"], "blocked": "too dear" if spec["cost"] > budget else None, "landing": tile["map_territory_ref"], "away": False})

		locked = []
		if produces:
			offered = {entry["token"].split(":")[1] for entry in entries if entry["token"].startswith("unit")}
			for layer in world.LAYERS:
				names = [world.get_unit(key)["name"] for key in world.buildable_in(layer) if key not in offered]
				if names and layer != tile["layer"]:
					locked.append({"layer": layer, "names": names})

		if entries:
			sites[tile["map_territory_ref"]] = {"tid": tile["territory_id"], "ref": tile["map_territory_ref"], "layer": tile["layer"], "options": entries, "locked": locked}
	return sites, budget


@bp.route("/lobby/create", methods=("POST",))
@login_required
# make a lobby and put the host in it
def create():
	db = get_db()
	code = new_code(db)
	preset = db.execute("SELECT map_id FROM Map ORDER BY map_id LIMIT 1").fetchone()
	cursor = db.execute("INSERT INTO Game (join_code, map_id) VALUES (?, ?)", (code, preset["map_id"] if preset else None))
	db.execute("INSERT INTO GamePlayer (game_id, user_id, player_colour, is_host) VALUES (?, ?, ?, 1)", (cursor.lastrowid, g.user["user_id"], COLOURS[0]))
	db.commit()
	return redirect(url_for("play.lobby", code=code))


@bp.route("/lobby/join", methods=("POST",))
@login_required
# join a lobby by code
def join():
	code = request.form.get("code", "").strip().upper()
	if not CODE_RE.match(code):
		flash("Join codes are 6 characters, letters and numbers only.", "error")
		return redirect(url_for("dashboard"))

	db = get_db()
	game = fetch_game(db, code)
	if game is None:
		flash("Lobby not found.", "error")
		return redirect(url_for("dashboard"))
	if game["status"] != "lobby":
		flash("That game has already started.", "error")
		return redirect(url_for("dashboard"))

	players = fetch_players(db, game["game_id"])
	if find_player(players, g.user["user_id"]):
		return redirect(url_for("play.lobby", code=code))

	colour = free_colour(db, game["game_id"])
	if len(players) >= capacity(db, game) or colour is None:
		flash("That lobby is full.", "error")
		return redirect(url_for("dashboard"))

	db.execute("INSERT INTO GamePlayer (game_id, user_id, player_colour) VALUES (?, ?, ?)", (game["game_id"], g.user["user_id"], colour))
	db.commit()
	socketio.emit("lobby_update", room=room_of(game["game_id"]))
	return redirect(url_for("play.lobby", code=code))


@bp.route("/lobby/<code>")
@login_required
# the waiting room page
def lobby(code):
	code = code.upper()
	db = get_db()
	game = fetch_game(db, code)
	if game is None:
		flash("Lobby not found.", "error")
		return redirect(url_for("dashboard"))

	players = fetch_players(db, game["game_id"])
	me = find_player(players, g.user["user_id"])
	if me is None:
		flash("You are not in that lobby.", "error")
		return redirect(url_for("dashboard"))
	if game["status"] != "lobby":
		return redirect(url_for("play.game", code=code))

	return render_template("lobby.html", game=game, players=players, is_host=bool(me["is_host"]), min_players=MIN_PLAYERS, max_players=capacity(db, game), game_map=fetch_map(db, game), all_maps=db.execute("SELECT * FROM Map ORDER BY name").fetchall(), board_choices=BOARD_CHOICES)


@bp.route("/lobby/<code>/settings", methods=("POST",))
@login_required
# host changes the map, board size and turn timer
def settings(code):
	code = code.upper()
	db = get_db()
	game = fetch_game(db, code)
	if game is None or game["status"] != "lobby":
		flash("Lobby not found.", "error")
		return redirect(url_for("dashboard"))

	players = fetch_players(db, game["game_id"])
	me = find_player(players, g.user["user_id"])
	if me is None or not me["is_host"]:
		flash("Only the host can change settings.", "error")
		return redirect(url_for("play.lobby", code=code))

	size = world.clamp_board(request.form.get("board_size", type=int) or 0) if request.form.get("board_size", type=int) else 0
	map_id = request.form.get("map_id", type=int)
	if map_id and db.execute("SELECT 1 FROM Map WHERE map_id = ?", (map_id,)).fetchone():
		db.execute("UPDATE Game SET map_id = ? WHERE game_id = ?", (map_id, game["game_id"]))
	db.execute("UPDATE Game SET board_size = ?, timer_on = ? WHERE game_id = ?", (size, 1 if request.form.get("timer_on") else 0, game["game_id"]))
	db.commit()
	socketio.emit("lobby_update", room=room_of(game["game_id"]))
	return redirect(url_for("play.lobby", code=code))


@bp.route("/lobby/<code>/start", methods=("POST",))
@login_required
# generate the board if needed then flip the game to active
def start(code):
	code = code.upper()
	db = get_db()
	game = fetch_game(db, code)
	if game is None:
		flash("Lobby not found.", "error")
		return redirect(url_for("dashboard"))

	players = fetch_players(db, game["game_id"])
	me = find_player(players, g.user["user_id"])
	if me is None or not me["is_host"]:
		flash("Only the host can start the game.", "error")
		return redirect(url_for("play.lobby", code=code))
	if game["status"] != "lobby":
		return redirect(url_for("play.game", code=code))

	map_row = fetch_map(db, game)
	if map_row is None and not game["board_size"]:
		flash("Choose a map or a board size before starting.", "error")
		return redirect(url_for("play.lobby", code=code))
	if len(players) < MIN_PLAYERS:
		flash(f"You need at least {MIN_PLAYERS} players to start.", "error")
		return redirect(url_for("play.lobby", code=code))

	if game["board_size"]:
		config = world.generate_config(f"Generated {game['board_size']}x{game['board_size']}", game["board_size"], secrets.randbelow(10 ** 9), players=max(len(players), MIN_PLAYERS))
		db.execute("UPDATE Game SET board_json = ? WHERE game_id = ?", (json.dumps(config), game["game_id"]))
		game = fetch_game(db, code)

	layout = world.get_layout(map_row, game)
	db.execute("UPDATE Game SET status = 'active' WHERE game_id = ?", (game["game_id"],))
	world.seed_territories(db, game["game_id"], layout)
	if game["timer_on"]:
		engine.set_deadline(db, game["game_id"], layout["config"])
	db.commit()
	socketio.emit("game_started", {"url": url_for("play.game", code=code)}, room=room_of(game["game_id"]))
	return redirect(url_for("play.game", code=code))


@bp.route("/lobby/<code>/leave", methods=("POST",))
@login_required
# lobby only, mid game you resign instead
def leave(code):
	code = code.upper()
	db = get_db()
	game = fetch_game(db, code)
	if game is None:
		return redirect(url_for("dashboard"))
	if game["status"] != "lobby":
		flash("The game has already started - resign instead.", "error")
		return redirect(url_for("play.game", code=code))

	me = find_player(fetch_players(db, game["game_id"]), g.user["user_id"])
	if me is None:
		return redirect(url_for("dashboard"))

	if me["is_host"]:
		db.execute("DELETE FROM Game WHERE game_id = ?", (game["game_id"],))
		flash("Lobby closed.", "success")
	else:
		db.execute("DELETE FROM GamePlayer WHERE game_id = ? AND user_id = ?", (game["game_id"], g.user["user_id"]))
		flash("You left the lobby.", "success")
	db.commit()
	socketio.emit("lobby_update", room=room_of(game["game_id"]))
	return redirect(url_for("dashboard"))


@bp.route("/game/<code>")
@login_required
# the main play page, or the summary if the game is over
def game(code):
	code = code.upper()
	db = get_db()
	row = fetch_game(db, code)
	if row is None:
		flash("Game not found.", "error")
		return redirect(url_for("dashboard"))

	players = fetch_players(db, row["game_id"])
	me = find_player(players, g.user["user_id"])
	if me is None:
		flash("You are not in that game.", "error")
		return redirect(url_for("dashboard"))
	if row["status"] == "lobby":
		return redirect(url_for("play.lobby", code=code))

	map_row = fetch_map(db, row)
	if row["status"] == "complete":
		champion = next((player for player in players if player["user_id"] == row["winner_id"]), None)
		return render_template("summary.html", game=row, players=sorted(players, key=lambda player: player["resources"], reverse=True), game_map=map_row, winner_name=champion["username"] if champion else None, standings=standings_for(db, row["game_id"]))

	layout = world.get_layout(map_row, row)
	adjacency = world.build_adjacency(layout)
	board = world.build_board(db, row, map_row, g.user["user_id"])
	sites, budget = production_menu(db, row, g.user["user_id"], adjacency, {r["map_territory_ref"]: r for r in db.execute("SELECT map_territory_ref, layer, terrain_type FROM Territory WHERE game_id = ?", (row["game_id"],))})

	return render_template(
		"game.html",
		game=row,
		players=players,
		me=me,
		game_map=map_row,
		board=board,
		moves=legal_moves(db, row, g.user["user_id"], layout, adjacency, board["visible"]),
		sites=sites,
		budget=budget,
		stock=sorted(held_resources(db, row["game_id"], g.user["user_id"])),
		status=submission_status(db, row),
		submitted=me["submitted_turn"] == row["current_turn"],
		seconds_left=engine.seconds_left(row),
		pacts=engine.pact_board(db, row, g.user["user_id"]),
		disasters=engine.disaster_log(db, row["game_id"]),
		unit_specs=world.load_roster(),
	)


# final scores for the summary page
def standings_for(db, game_id):
	return db.execute("SELECT u.username, gp.player_colour, gp.is_eliminated, gp.resources, gp.result, (SELECT COUNT(*) FROM Territory t WHERE t.game_id = gp.game_id AND t.owner_id = gp.user_id) AS territories, (SELECT COUNT(*) FROM Unit un WHERE un.game_id = gp.game_id AND un.owner_id = gp.user_id) AS units FROM GamePlayer gp JOIN User u ON u.user_id = gp.user_id WHERE gp.game_id = ? ORDER BY territories DESC, units DESC", (game_id,)).fetchall()


@bp.route("/game/<code>/orders", methods=("POST",))
@login_required
# take the browsers order list, check every one, then store them
def submit_orders(code):
	code = code.upper()
	db = get_db()
	row = fetch_game(db, code)
	if row is None or row["status"] != "active":
		return jsonify({"ok": False, "problems": ["That game is not running."]}), 400

	me = find_player(fetch_players(db, row["game_id"]), g.user["user_id"])
	if me is None or me["is_eliminated"]:
		return jsonify({"ok": False, "problems": ["You cannot give orders."]}), 403
	if me["submitted_turn"] == row["current_turn"]:
		return jsonify({"ok": False, "problems": ["Your orders are already locked in."]}), 400

	payload = request.get_json(silent=True) or {}
	map_row = fetch_map(db, row)
	layout = world.get_layout(map_row, row)
	adjacency = world.build_adjacency(layout)
	board = world.build_board(db, row, map_row, g.user["user_id"])
	moves = legal_moves(db, row, g.user["user_id"], layout, adjacency, board["visible"])
	sites, budget = production_menu(db, row, g.user["user_id"], adjacency, {r["map_territory_ref"]: r for r in db.execute("SELECT map_territory_ref, layer, terrain_type FROM Territory WHERE game_id = ?", (row["game_id"],))})

	problems, accepted, builds, spend = [], [], [], 0
	held = {entry for entry in payload.get("holds", []) if entry in moves}
	for entry in payload.get("moves", []):
		unit_id, ref = entry.get("unit_id"), entry.get("ref")
		if unit_id in held:
			continue
		option = moves.get(unit_id)
		if option is None:
			problems.append("You tried to order a unit that is not yours.")
			continue
		choice = next((move for move in option["moves"] if move["ref"] == ref), None)
		if choice is None:
			problems.append(f"{option['name']} cannot reach that tile.")
			continue
		accepted.append((choice["kind"], unit_id, ref))

	for entry in payload.get("builds", []):
		ref, token = entry.get("ref"), entry.get("token")
		site = sites.get(ref)
		if site is None:
			problems.append("You cannot produce there.")
			continue
		option = next((item for item in site["options"] if item["token"] == token), None)
		if option is None or option["blocked"]:
			problems.append("That cannot be produced there right now.")
			continue
		spend += option["cost"]
		builds.append((site["tid"], token, option.get("landing")))

	if spend > budget:
		problems.append(f"That costs {spend} but you only have {budget}.")
	if problems:
		return jsonify({"ok": False, "problems": problems}), 400

	turn = row["current_turn"]
	db.execute("DELETE FROM Orders WHERE game_id = ? AND player_id = ? AND turn_number = ?", (row["game_id"], g.user["user_id"], turn))
	ref_to_id = {item["map_territory_ref"]: item["territory_id"] for item in db.execute("SELECT territory_id, map_territory_ref FROM Territory WHERE game_id = ?", (row["game_id"],))}

	for kind, unit_id, ref in accepted:
		source = db.execute("SELECT territory_id FROM Unit WHERE unit_id = ?", (unit_id,)).fetchone()
		db.execute("INSERT INTO Orders (game_id, player_id, turn_number, order_type, unit_id, source_territory, target_territory) VALUES (?, ?, ?, ?, ?, ?, ?)", (row["game_id"], g.user["user_id"], turn, kind, unit_id, source["territory_id"], ref_to_id[ref]))
	for territory_id, token, landing in builds:
		db.execute("INSERT INTO Orders (game_id, player_id, turn_number, order_type, source_territory, target_territory, detail) VALUES (?, ?, ?, 'build', ?, ?, ?)", (row["game_id"], g.user["user_id"], turn, territory_id, ref_to_id.get(landing, territory_id), token))

	db.execute("UPDATE GamePlayer SET submitted_turn = ? WHERE game_id = ? AND user_id = ?", (turn, row["game_id"], g.user["user_id"]))
	db.commit()

	if submission_status(db, row)["all_in"]:
		result = engine.resolve_turn(db, row, map_row)
		socketio.emit("turn_resolved", {"log": result["log"]}, room=room_of(row["game_id"]))
	else:
		socketio.emit("orders_update", room=room_of(row["game_id"]))
	return jsonify({"ok": True})


@bp.route("/game/<code>/resolve", methods=("POST",))
@login_required
# called when the timer runs out, only one caller wins the race
def force_resolve(code):
	code = code.upper()
	db = get_db()
	row = fetch_game(db, code)
	if row is None or row["status"] != "active":
		return jsonify({"resolved": False})
	if find_player(fetch_players(db, row["game_id"]), g.user["user_id"]) is None:
		return jsonify({"resolved": False}), 403

	claimed = db.execute("UPDATE Game SET turn_deadline = NULL WHERE game_id = ? AND current_turn = ? AND turn_deadline IS NOT NULL AND turn_deadline <= datetime('now')", (row["game_id"], row["current_turn"])).rowcount
	db.commit()
	if not claimed:
		return jsonify({"resolved": False})

	result = engine.resolve_turn(db, row, fetch_map(db, row))
	socketio.emit("turn_resolved", {"log": ["Time ran out."] + result["log"]}, room=room_of(row["game_id"]))
	return jsonify({"resolved": True})


@bp.route("/game/<code>/resign", methods=("POST",))
@login_required
# quit an active game, units die and land goes neutral
def resign(code):
	code = code.upper()
	db = get_db()
	row = fetch_game(db, code)
	if row is None or row["status"] != "active":
		flash("You can only resign from a game in progress.", "error")
		return redirect(url_for("dashboard"))

	me = find_player(fetch_players(db, row["game_id"]), g.user["user_id"])
	if me is None:
		return redirect(url_for("dashboard"))
	if me["is_eliminated"]:
		flash("You are already out of this game.", "error")
		return redirect(url_for("play.game", code=code))

	game_id, user_id = row["game_id"], g.user["user_id"]
	db.execute("UPDATE GamePlayer SET is_eliminated = 1, submitted_turn = NULL WHERE game_id = ? AND user_id = ?", (game_id, user_id))
	db.execute("DELETE FROM Unit WHERE game_id = ? AND owner_id = ?", (game_id, user_id))
	db.execute("UPDATE Territory SET owner_id = NULL WHERE game_id = ? AND owner_id = ?", (game_id, user_id))
	db.execute("UPDATE Orders SET status = 'cancelled' WHERE game_id = ? AND player_id = ? AND status = 'pending'", (game_id, user_id))
	db.commit()

	standing = db.execute("SELECT gp.user_id, u.username FROM GamePlayer gp JOIN User u ON u.user_id = gp.user_id WHERE gp.game_id = ? AND gp.is_eliminated = 0", (game_id,)).fetchall()
	if len(standing) == 1:
		engine.finish(db, game_id, winner_id=standing[0]["user_id"])
		db.commit()
		socketio.emit("turn_resolved", {"log": [f"{me['username']} resigned.", f"{standing[0]['username']} wins by default."]}, room=room_of(game_id))
		flash("You resigned. The game is over.", "success")
		return redirect(url_for("dashboard"))

	if submission_status(db, row)["all_in"]:
		result = engine.resolve_turn(db, row, fetch_map(db, row))
		socketio.emit("turn_resolved", {"log": [f"{me['username']} resigned."] + result["log"]}, room=room_of(game_id))
	else:
		socketio.emit("orders_update", room=room_of(game_id))

	flash("You resigned from the game.", "success")
	return redirect(url_for("dashboard"))


@bp.route("/game/<code>/pact", methods=("POST",))
@login_required
# offer someone a deal
def propose_pact(code):
	code = code.upper()
	db = get_db()
	row = fetch_game(db, code)
	if row is None or row["status"] != "active":
		flash("Game not found.", "error")
		return redirect(url_for("dashboard"))

	problems = engine.propose_pact(db, row, g.user["user_id"], request.form.get("recipient_id", type=int), request.form.get("kind", ""), request.form.get("turns", type=int) or 0, request.form.get("offer", type=int) or 0, request.form.get("request", type=int) or 0)
	for problem in problems:
		flash(problem, "error")
	if not problems:
		flash("Offer sent.", "success")
		socketio.emit("orders_update", room=room_of(row["game_id"]))
	return redirect(url_for("play.game", code=code))


@bp.route("/game/<code>/pact/<int:agreement_id>", methods=("POST",))
@login_required
# accept decline or withdraw a deal
def answer_pact(code, agreement_id):
	code = code.upper()
	db = get_db()
	row = fetch_game(db, code)
	if row is None or row["status"] != "active":
		flash("Game not found.", "error")
		return redirect(url_for("dashboard"))

	answer = request.form.get("answer", "")
	if answer == "withdraw":
		problems, done = engine.withdraw_pact(db, row, agreement_id, g.user["user_id"]), "Offer withdrawn."
	else:
		problems = engine.answer_pact(db, row, agreement_id, g.user["user_id"], answer == "accept")
		done = "Agreement signed." if answer == "accept" else "Offer declined."

	for problem in problems:
		flash(problem, "error")
	if not problems:
		flash(done, "success")
		socketio.emit("orders_update", room=room_of(row["game_id"]))
	return redirect(url_for("play.game", code=code))


@socketio.on("join_game")
# put the socket in the games room so it gets updates
def on_join_game(data):
	if session.get("user_id") is None:
		return
	game_id = data.get("game_id")
	if game_id is not None:
		join_room(room_of(game_id))

import re
import secrets

from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for
)
from flask_socketio import join_room

import maps
import orders
import resolution
import units
from auth import login_required
from db import get_db
from extensions import socketio

bp = Blueprint("lobby", __name__)

MIN_PLAYERS = 2
MAX_PLAYERS = 6

JOIN_CODE_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
JOIN_CODE_RE = re.compile(r"^[A-Z0-9]{6}$")

PLAYER_COLOURS = [
    "#E63946",
    "#457B9D",
    "#2A9D8F",
    "#E9C46A",
    "#8338EC",
    "#F4A261",
]


def init_app(app):
    app.register_blueprint(bp)


def lobby_room(game_id):
    return f"lobby_{game_id}"


def generate_join_code(db):
    for _ in range(20):
        code = "".join(secrets.choice(JOIN_CODE_ALPHABET) for _ in range(6))
        if not db.execute("SELECT 1 FROM Game WHERE join_code = ?", (code,)).fetchone():
            return code
    raise RuntimeError("Could not generate a unique join code")


def next_colour(db, game_id):
    taken = {
        row["player_colour"]
        for row in db.execute(
            "SELECT player_colour FROM GamePlayer WHERE game_id = ?", (game_id,)
        )
    }
    for colour in PLAYER_COLOURS:
        if colour not in taken:
            return colour
    return None


def get_game(db, join_code):
    return db.execute("SELECT * FROM Game WHERE join_code = ?", (join_code,)).fetchone()


def get_players(db, game_id):
    return db.execute(
        """SELECT gp.*, u.username
             FROM GamePlayer gp
             JOIN User u ON u.user_id = gp.user_id
            WHERE gp.game_id = ?
         ORDER BY gp.gameplayer_id""",
        (game_id,),
    ).fetchall()


def find_player(players, user_id):
    for player in players:
        if player["user_id"] == user_id:
            return player
    return None


def get_map(db, game):
    if game["map_id"] is None:
        return None
    return db.execute("SELECT * FROM Map WHERE map_id = ?", (game["map_id"],)).fetchone()


def lobby_capacity(db, game):
    game_map = get_map(db, game)
    if game_map is None:
        return MAX_PLAYERS
    return min(game_map["max_players"], MAX_PLAYERS)


@bp.route("/lobby/create", methods=("POST",))
@login_required
def create():
    db = get_db()
    code = generate_join_code(db)
    default_map = db.execute("SELECT map_id FROM Map ORDER BY map_id LIMIT 1").fetchone()
    cursor = db.execute(
        "INSERT INTO Game (join_code, map_id) VALUES (?, ?)",
        (code, default_map["map_id"] if default_map else None),
    )
    db.execute(
        "INSERT INTO GamePlayer (game_id, user_id, player_colour, is_host)"
        " VALUES (?, ?, ?, 1)",
        (cursor.lastrowid, g.user["user_id"], PLAYER_COLOURS[0]),
    )
    db.commit()
    return redirect(url_for("lobby.view", join_code=code))


@bp.route("/lobby/join", methods=("POST",))
@login_required
def join():
    code = request.form.get("join_code", "").strip().upper()
    if not JOIN_CODE_RE.match(code):
        flash("Join codes are 6 characters, letters and numbers only.", "error")
        return redirect(url_for("dashboard"))

    db = get_db()
    game = get_game(db, code)
    if game is None:
        flash("Lobby not found.", "error")
        return redirect(url_for("dashboard"))
    if game["status"] != "lobby":
        flash("That game has already started. - You may resign only", "error")
        return redirect(url_for("lobby.game", join_code=code))

    players = get_players(db, game["game_id"])
    if find_player(players, g.user["user_id"]):
        return redirect(url_for("lobby.view", join_code=code))

    capacity = lobby_capacity(db, game)
    colour = next_colour(db, game["game_id"])
    if len(players) >= capacity or colour is None:
        flash(f"That lobby is full ({capacity} players).", "error")
        return redirect(url_for("dashboard"))

    db.execute(
        "INSERT INTO GamePlayer (game_id, user_id, player_colour) VALUES (?, ?, ?)",
        (game["game_id"], g.user["user_id"], colour),
    )
    db.commit()
    socketio.emit("lobby_update", room=lobby_room(game["game_id"]))
    return redirect(url_for("lobby.view", join_code=code))


@bp.route("/lobby/<join_code>")
@login_required
def view(join_code):
    code = join_code.upper()
    db = get_db()
    game = get_game(db, code)
    if game is None:
        flash("Lobby not found.", "error")
        return redirect(url_for("dashboard"))

    players = get_players(db, game["game_id"])
    me = find_player(players, g.user["user_id"])
    if me is None:
        flash("You are not in that lobby.", "error")
        return redirect(url_for("dashboard"))

    if game["status"] == "active":
        return redirect(url_for("lobby.game", join_code=code))

    return render_template(
        "lobby.html",
        game=game,
        players=players,
        is_host=bool(me["is_host"]),
        min_players=MIN_PLAYERS,
        max_players=lobby_capacity(db, game),
        game_map=get_map(db, game),
        all_maps=db.execute("SELECT * FROM Map ORDER BY name").fetchall(),
    )


@bp.route("/lobby/<join_code>/settings", methods=("POST",))
@login_required
def settings(join_code):
    code = join_code.upper()
    db = get_db()
    game = get_game(db, code)
    if game is None or game["status"] != "lobby":
        flash("Lobby not found.", "error")
        return redirect(url_for("dashboard"))

    players = get_players(db, game["game_id"])
    me = find_player(players, g.user["user_id"])
    if me is None or not me["is_host"]:
        flash("Only the host can change game settings.", "error")
        return redirect(url_for("lobby.view", join_code=code))

    map_id = request.form.get("map_id", type=int)
    chosen = db.execute("SELECT * FROM Map WHERE map_id = ?", (map_id,)).fetchone()
    if chosen is None:
        flash("That map does not exist.", "error")
        return redirect(url_for("lobby.view", join_code=code))
    if len(players) > chosen["max_players"]:
        flash(
            f"{chosen['name']} only supports {chosen['max_players']} players "
            f"and you have {len(players)}.",
            "error",
        )
        return redirect(url_for("lobby.view", join_code=code))

    db.execute(
        "UPDATE Game SET map_id = ? WHERE game_id = ?", (map_id, game["game_id"])
    )
    db.commit()
    socketio.emit("lobby_update", room=lobby_room(game["game_id"]))
    return redirect(url_for("lobby.view", join_code=code))


@bp.route("/lobby/<join_code>/start", methods=("POST",))
@login_required
def start(join_code):
    code = join_code.upper()
    db = get_db()
    game = get_game(db, code)
    if game is None:
        flash("Lobby not found.", "error")
        return redirect(url_for("dashboard"))

    players = get_players(db, game["game_id"])
    me = find_player(players, g.user["user_id"])
    if me is None or not me["is_host"]:
        flash("Only the host can start the game.", "error")
        return redirect(url_for("lobby.view", join_code=code))
    if game["status"] != "lobby":
        return redirect(url_for("lobby.game", join_code=code))

    game_map = get_map(db, game)
    if game_map is None:
        flash("Choose a map before starting the game.", "error")
        return redirect(url_for("lobby.view", join_code=code))

    required = max(MIN_PLAYERS, game_map["min_players"])
    if len(players) < required:
        flash(f"You need at least {required} players to start.", "error")
        return redirect(url_for("lobby.view", join_code=code))

    db.execute(
        "UPDATE Game SET status = 'active' WHERE game_id = ?", (game["game_id"],)
    )
    maps.seed_territories(db, game["game_id"], game_map)
    resolution.set_deadline(db, game["game_id"], maps.get_layout(game_map))
    db.commit()
    socketio.emit(
        "game_started",
        {"url": url_for("lobby.game", join_code=code)},
        room=lobby_room(game["game_id"]),
    )
    return redirect(url_for("lobby.game", join_code=code))


@bp.route("/lobby/<join_code>/kick/<int:user_id>", methods=("POST",))
@login_required
def kick(join_code, user_id):
    code = join_code.upper()
    db = get_db()
    game = get_game(db, code)
    if game is None or game["status"] != "lobby":
        flash("Lobby not found.", "error")
        return redirect(url_for("dashboard"))

    me = find_player(get_players(db, game["game_id"]), g.user["user_id"])
    if me is None or not me["is_host"]:
        flash("Only the host can remove players.", "error")
        return redirect(url_for("lobby.view", join_code=code))
    if user_id == g.user["user_id"]:
        flash("The host cannot remove themselves. Leave the lobby instead.", "error")
        return redirect(url_for("lobby.view", join_code=code))

    db.execute(
        "DELETE FROM GamePlayer WHERE game_id = ? AND user_id = ?",
        (game["game_id"], user_id),
    )
    db.commit()
    socketio.emit("lobby_update", room=lobby_room(game["game_id"]))
    return redirect(url_for("lobby.view", join_code=code))


@bp.route("/lobby/<join_code>/leave", methods=("POST",))
@login_required
def leave(join_code):
    code = join_code.upper()
    db = get_db()
    game = get_game(db, code)
    if game is None:
        return redirect(url_for("dashboard"))

    if game["status"] != "lobby":
        flash("The game has already started - resign instead.", "error")
        return redirect(url_for("lobby.game", join_code=code))

    me = find_player(get_players(db, game["game_id"]), g.user["user_id"])
    if me is None:
        return redirect(url_for("dashboard"))

    if me["is_host"]:
        db.execute("DELETE FROM Game WHERE game_id = ?", (game["game_id"],))
        flash("Lobby closed.", "success")
    else:
        db.execute(
            "DELETE FROM GamePlayer WHERE game_id = ? AND user_id = ?",
            (game["game_id"], g.user["user_id"]),
        )
        flash("You left the lobby.", "success")
    db.commit()
    socketio.emit("lobby_update", room=lobby_room(game["game_id"]))
    return redirect(url_for("dashboard"))


@bp.route("/game/<join_code>")
@login_required
def game(join_code):
    code = join_code.upper()
    db = get_db()
    game_row = get_game(db, code)
    if game_row is None:
        flash("Game not found.", "error")
        return redirect(url_for("dashboard"))

    players = get_players(db, game_row["game_id"])
    if find_player(players, g.user["user_id"]) is None:
        flash("You are not in that game.", "error")
        return redirect(url_for("dashboard"))
    if game_row["status"] == "lobby":
        return redirect(url_for("lobby.view", join_code=code))

    game_map = get_map(db, game_row)
    board = maps.build_board(db, game_row, game_map, g.user["user_id"])

    if game_row["status"] == "complete":
        champion = db.execute(
            "SELECT username FROM User WHERE user_id = ?", (game_row["winner_id"],)
        ).fetchone()
        return render_template(
            "summary.html",
            game=game_row,
            players=standings(db, game_row["game_id"]),
            game_map=game_map,
            winner_name=champion["username"] if champion else None,
        )

    layout = maps.get_layout(game_map)
    adjacency = maps.build_adjacency(layout)
    me = g.user["user_id"]

    unit_options = orders.legal_orders(
        db, game_row, me, layout, adjacency, board["visible"]
    )
    city_options, budget = orders.build_options(db, game_row, me)
    improve_options = orders.improvement_options(db, game_row, me)
    status = orders.submission_status(db, game_row)
    my_units = db.execute(
        """SELECT u.unit_id, u.unit_type, u.health, u.layer
             FROM Unit u WHERE u.game_id = ? AND u.owner_id = ? ORDER BY u.unit_id""",
        (game_row["game_id"], me),
    ).fetchall()

    return render_template(
        "game.html",
        game=game_row,
        players=players,
        game_map=game_map,
        board=board,
        layers=maps.LAYERS,
        my_units=my_units,
        unit_options=unit_options,
        city_options=city_options,
        improve_options=improve_options,
        tile_names=tile_labels(db, game_row["game_id"]),
        budget=budget,
        status=status,
        me_player=find_player(players, me),
        submitted=(find_player(players, me)["submitted_turn"] == game_row["current_turn"]),
        seconds_left=resolution.seconds_left(game_row),
        unit_specs=units.load_roster(),
    )


def tile_labels(db, game_id):
    rows = db.execute(
        """SELECT territory_id, layer, terrain_type, has_city, natural_resource
             FROM Territory WHERE game_id = ?""",
        (game_id,),
    ).fetchall()
    labels = {}
    for row in rows:
        name = f"{row['terrain_type']} ({row['layer']})"
        if row["has_city"]:
            name = f"City - {name}"
        if row["natural_resource"]:
            name += f" - {row['natural_resource']}"
        labels[row["territory_id"]] = name
    return labels


def standings(db, game_id):
    return db.execute(
        """SELECT u.username, gp.player_colour, gp.is_eliminated, gp.resources,
                  (SELECT COUNT(*) FROM Territory t
                    WHERE t.game_id = gp.game_id AND t.owner_id = gp.user_id) AS territories,
                  (SELECT COUNT(*) FROM Unit un
                    WHERE un.game_id = gp.game_id AND un.owner_id = gp.user_id) AS units
             FROM GamePlayer gp JOIN User u ON u.user_id = gp.user_id
            WHERE gp.game_id = ?
         ORDER BY territories DESC, units DESC""",
        (game_id,),
    ).fetchall()


@bp.route("/game/<join_code>/orders", methods=("POST",))
@login_required
def submit_orders(join_code):
    code = join_code.upper()
    db = get_db()
    game_row = get_game(db, code)
    if game_row is None or game_row["status"] != "active":
        flash("Game not found.", "error")
        return redirect(url_for("dashboard"))

    players = get_players(db, game_row["game_id"])
    me = find_player(players, g.user["user_id"])
    if me is None:
        flash("You are not in that game.", "error")
        return redirect(url_for("dashboard"))
    if me["submitted_turn"] == game_row["current_turn"]:
        flash("Your orders are already locked in for this turn.", "error")
        return redirect(url_for("lobby.game", join_code=code))

    game_map = get_map(db, game_row)
    layout = maps.get_layout(game_map)
    adjacency = maps.build_adjacency(layout)
    board = maps.build_board(db, game_row, game_map, g.user["user_id"])

    unit_choices = {
        int(key[5:]): value
        for key, value in request.form.items()
        if key.startswith("unit_")
    }
    city_choices = {
        int(key[5:]): value
        for key, value in request.form.items()
        if key.startswith("city_")
    }
    improve_choices = {
        int(key[8:]): value
        for key, value in request.form.items()
        if key.startswith("improve_")
    }

    problems = orders.save_orders(
        db, game_row, g.user["user_id"], unit_choices, city_choices,
        improve_choices, layout, adjacency, board["visible"],
    )
    if problems:
        for problem in problems:
            flash(problem, "error")
        return redirect(url_for("lobby.game", join_code=code))

    status = orders.submission_status(db, game_row)
    if status["all_in"]:
        result = resolution.resolve_turn(db, game_row, game_map)
        socketio.emit(
            "turn_resolved",
            {"log": result["log"]},
            room=lobby_room(game_row["game_id"]),
        )
    else:
        socketio.emit("orders_update", room=lobby_room(game_row["game_id"]))
        flash("Orders locked in. Waiting for the other players.", "success")
    return redirect(url_for("lobby.game", join_code=code))


@bp.route("/game/<join_code>/resolve", methods=("POST",))
@login_required
def force_resolve(join_code):
    code = join_code.upper()
    db = get_db()
    game_row = get_game(db, code)
    if game_row is None or game_row["status"] != "active":
        return {"resolved": False, "reason": "not active"}

    players = get_players(db, game_row["game_id"])
    if find_player(players, g.user["user_id"]) is None:
        return {"resolved": False, "reason": "not a player"}, 403

    claimed = db.execute(
        "UPDATE Game SET turn_deadline = NULL"
        " WHERE game_id = ? AND current_turn = ?"
        "   AND turn_deadline IS NOT NULL"
        "   AND turn_deadline <= datetime('now')",
        (game_row["game_id"], game_row["current_turn"]),
    ).rowcount
    if not claimed:
        db.commit()
        return {"resolved": False, "reason": "not due"}
    db.commit()

    result = resolution.resolve_turn(db, game_row, get_map(db, game_row))
    socketio.emit(
        "turn_resolved",
        {"log": ["Time ran out."] + result["log"]},
        room=lobby_room(game_row["game_id"]),
    )
    return {"resolved": True}


@bp.route("/game/<join_code>/resign", methods=("POST",))
@login_required
def resign(join_code):
    code = join_code.upper()
    db = get_db()
    game_row = get_game(db, code)
    if game_row is None:
        flash("Game not found.", "error")
        return redirect(url_for("dashboard"))

    if game_row["status"] != "active":
        flash("You can only resign from a game in progress.", "error")
        return redirect(url_for("dashboard"))

    me = find_player(get_players(db, game_row["game_id"]), g.user["user_id"])
    if me is None:
        flash("You are not in that game.", "error")
        return redirect(url_for("dashboard"))
    if me["is_eliminated"]:
        flash("You are already out of this game.", "error")
        return redirect(url_for("lobby.game", join_code=code))

    game_id = game_row["game_id"]
    user_id = g.user["user_id"]

    db.execute(
        "UPDATE GamePlayer SET is_eliminated = 1, submitted_turn = NULL"
        " WHERE game_id = ? AND user_id = ?",
        (game_id, user_id),
    )

    db.execute("DELETE FROM Unit WHERE game_id = ? AND owner_id = ?", (game_id, user_id))

    db.execute(
        "UPDATE Territory SET owner_id = NULL WHERE game_id = ? AND owner_id = ?",
        (game_id, user_id),
    )

    db.execute(
        "UPDATE Orders SET status = 'cancelled'"
        " WHERE game_id = ? AND player_id = ? AND status = 'pending'",
        (game_id, user_id),
    )
    db.commit()

    standing = db.execute(
        """SELECT gp.user_id, u.username FROM GamePlayer gp
             JOIN User u ON u.user_id = gp.user_id
            WHERE gp.game_id = ? AND gp.is_eliminated = 0""",
        (game_id,),
    ).fetchall()

    if len(standing) == 1:
        winner = standing[0]
        db.execute(
            "UPDATE Game SET status = 'complete', winner_id = ?,"
            " completed_at = datetime('now') WHERE game_id = ?",
            (winner["user_id"], game_id),
        )
        db.commit()
        socketio.emit(
            "turn_resolved",
            {"log": [f"{me['username']} resigned.",
                     f"{winner['username']} wins by default."]},
            room=lobby_room(game_id),
        )
        flash("You resigned. The game is over.", "success")
        return redirect(url_for("dashboard"))

    status = orders.submission_status(db, game_row)
    if status["all_in"]:
        result = resolution.resolve_turn(db, game_row, get_map(db, game_row))
        socketio.emit(
            "turn_resolved",
            {"log": [f"{me['username']} resigned."] + result["log"]},
            room=lobby_room(game_id),
        )
    else:
        socketio.emit("orders_update", room=lobby_room(game_id))

    flash("You resigned from the game.", "success")
    return redirect(url_for("dashboard"))


@socketio.on("join_lobby")
def on_join_lobby(data):
    if session.get("user_id") is None:
        return
    game_id = data.get("game_id")
    if game_id is not None:
        join_room(lobby_room(game_id))

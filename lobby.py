import re
import secrets

from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for
)
from flask_socketio import join_room

from auth import login_required
from db import get_db
from extensions import socketio

bp = Blueprint("lobby", __name__)

MIN_PLAYERS = 2
MAX_PLAYERS = 6

JOIN_CODE_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
JOIN_CODE_RE = re.compile(r"^[A-Z0-9]{6}$")

# One colour per player slot
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


@bp.route("/lobby/create", methods=("POST",))
@login_required
def create():
    db = get_db()
    code = generate_join_code(db)
    cursor = db.execute("INSERT INTO Game (join_code) VALUES (?)", (code,))
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
        flash("That game has already started.", "error")
        return redirect(url_for("dashboard"))

    # Already a member: just take them to the lobby.
    if find_player(get_players(db, game["game_id"]), g.user["user_id"]):
        return redirect(url_for("lobby.view", join_code=code))

    colour = next_colour(db, game["game_id"])
    if colour is None:
        flash(f"That lobby is full ({MAX_PLAYERS} players).", "error")
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
        max_players=MAX_PLAYERS,
    )


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
    if len(players) < MIN_PLAYERS:
        flash(f"You need at least {MIN_PLAYERS} players to start.", "error")
        return redirect(url_for("lobby.view", join_code=code))

    db.execute(
        "UPDATE Game SET status = 'active' WHERE game_id = ?", (game["game_id"],)
    )
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
    """Leave a lobby. If the host leaves, the lobby is disbanded."""
    code = join_code.upper()
    db = get_db()
    game = get_game(db, code)
    if game is None:
        return redirect(url_for("dashboard"))

    me = find_player(get_players(db, game["game_id"]), g.user["user_id"])
    if me is None:
        return redirect(url_for("dashboard"))

    if me["is_host"]:
        # Deleting the game cascades to its GamePlayer rows.
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

    return render_template("game.html", game=game_row, players=players)


@socketio.on("join_lobby")
def on_join_lobby(data):
    if session.get("user_id") is None:
        return
    game_id = data.get("game_id")
    if game_id is not None:
        join_room(lobby_room(game_id))

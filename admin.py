import functools

import click
from flask import Blueprint, abort, flash, g, redirect, render_template, url_for
from flask_bcrypt import Bcrypt

from db import get_db

bp = Blueprint("admin", __name__, url_prefix="/admin")
bcrypt = Bcrypt()

TESTER_PASSWORD = "password123"
TESTERS = [
    ("tester1", "tester1@battley.test"),
    ("tester2", "tester2@battley.test"),
    ("tester3", "tester3@battley.test"),
    ("tester4", "tester4@battley.test"),
]


def init_app(app):
    bcrypt.init_app(app)
    app.register_blueprint(bp)
    app.cli.add_command(make_admin_command)
    app.cli.add_command(seed_testers_command)


def admin_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for("auth.login"))
        if not g.user["is_admin"]:
            abort(403)
        return view(**kwargs)
    return wrapped_view


def sweep_orphan_games(db):
    db.execute("DELETE FROM Game WHERE game_id NOT IN (SELECT game_id FROM GamePlayer)")


@bp.route("/")
@admin_required
def dashboard():
    db = get_db()
    sessions = db.execute(
        """SELECT g.game_id, g.join_code, g.status, g.current_turn, g.created_at,
                  g.global_resources, m.name AS map_name,
                  (SELECT COUNT(*) FROM GamePlayer gp WHERE gp.game_id = g.game_id)
                      AS player_count,
                  w.username AS winner
             FROM Game g
        LEFT JOIN Map m ON m.map_id = g.map_id
        LEFT JOIN User w ON w.user_id = g.winner_id
         ORDER BY g.created_at DESC""",
    ).fetchall()

    accounts = db.execute(
        """SELECT u.user_id, u.username, u.email, u.created_at, u.reputation,
                  u.is_admin,
                  (SELECT COUNT(*) FROM GamePlayer gp WHERE gp.user_id = u.user_id)
                      AS games
             FROM User u ORDER BY u.created_at""",
    ).fetchall()

    return render_template("admin.html", sessions=sessions, accounts=accounts)


@bp.route("/game/<int:game_id>/delete", methods=("POST",))
@admin_required
def delete_game(game_id):
    db = get_db()
    game = db.execute("SELECT join_code FROM Game WHERE game_id = ?", (game_id,)).fetchone()
    if game is None:
        flash("That session no longer exists.", "error")
        return redirect(url_for("admin.dashboard"))

    db.execute("DELETE FROM Game WHERE game_id = ?", (game_id,))
    db.commit()
    flash(f"Session {game['join_code']} deleted.", "success")
    return redirect(url_for("admin.dashboard"))


@bp.route("/user/<int:user_id>/delete", methods=("POST",))
@admin_required
def delete_user(user_id):
    db = get_db()
    if user_id == g.user["user_id"]:
        flash("You cannot delete your own account from here.", "error")
        return redirect(url_for("admin.dashboard"))

    account = db.execute("SELECT username FROM User WHERE user_id = ?", (user_id,)).fetchone()
    if account is None:
        flash("That account no longer exists.", "error")
        return redirect(url_for("admin.dashboard"))

    db.execute("DELETE FROM User WHERE user_id = ?", (user_id,))
    sweep_orphan_games(db)
    db.commit()
    flash(f"Account {account['username']} and all of its data deleted.", "success")
    return redirect(url_for("admin.dashboard"))


@bp.route("/user/<int:user_id>/toggle-admin", methods=("POST",))
@admin_required
def toggle_admin(user_id):
    db = get_db()
    if user_id == g.user["user_id"]:
        flash("You cannot change your own admin rights.", "error")
        return redirect(url_for("admin.dashboard"))

    account = db.execute(
        "SELECT username, is_admin FROM User WHERE user_id = ?", (user_id,)
    ).fetchone()
    if account is None:
        flash("That account no longer exists.", "error")
        return redirect(url_for("admin.dashboard"))

    now = 0 if account["is_admin"] else 1
    db.execute("UPDATE User SET is_admin = ? WHERE user_id = ?", (now, user_id))
    db.commit()
    flash(f"{account['username']} is {'now' if now else 'no longer'} an administrator.", "success")
    return redirect(url_for("admin.dashboard"))


@click.command("make-admin")
@click.argument("username")
def make_admin_command(username):
    db = get_db()
    account = db.execute("SELECT user_id FROM User WHERE username = ?", (username,)).fetchone()
    if account is None:
        click.echo(f"No account called {username!r}.")
        return
    db.execute("UPDATE User SET is_admin = 1 WHERE user_id = ?", (account["user_id"],))
    db.commit()
    click.echo(f"{username} is now an administrator.")


@click.command("seed-testers")
def seed_testers_command():
    db = get_db()
    made = []
    for username, email in TESTERS:
        exists = db.execute(
            "SELECT 1 FROM User WHERE username = ? OR email = ?", (username, email)
        ).fetchone()
        if exists:
            continue
        db.execute(
            "INSERT INTO User (username, email, password_hash) VALUES (?, ?, ?)",
            (username, email, bcrypt.generate_password_hash(TESTER_PASSWORD).decode("utf-8")),
        )
        made.append(username)
    db.commit()
    if made:
        click.echo(f"Created: {', '.join(made)} (password: {TESTER_PASSWORD})")
    else:
        click.echo("Tester accounts already exist.")

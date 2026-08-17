import functools
import re
import sqlite3

from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for
from flask_bcrypt import Bcrypt

from db import get_db
from extensions import limiter

bp = Blueprint("accounts", __name__)
bcrypt = Bcrypt()

USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,32}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_PASSWORD = 8
MAX_BIO = 160
AUTH_LIMIT = "10 per minute"

DETAIL_LIMIT = 3
POINTS = {"win": 25, "draw": 12, "played": 5, "survived": 8, "per_turn": 1}
MAX_TURN_POINTS = 15
RANKED_FLOOR = 3


def init_app(app):
	bcrypt.init_app(app)
	app.register_blueprint(bp)


@bp.before_app_request
def load_logged_in_user():
	user_id = session.get("user_id")
	g.user = None if user_id is None else get_db().execute("SELECT user_id, username, email, bio, reputation, created_at, is_admin FROM User WHERE user_id = ?", (user_id,)).fetchone()


def login_required(view):
	@functools.wraps(view)
	def wrapped(**kwargs):
		if g.user is None:
			return redirect(url_for("accounts.login"))
		return view(**kwargs)
	return wrapped


def admin_required(view):
	@functools.wraps(view)
	def wrapped(**kwargs):
		if g.user is None:
			return redirect(url_for("accounts.login"))
		if not g.user["is_admin"]:
			from flask import abort
			abort(403)
		return view(**kwargs)
	return wrapped


@bp.route("/register", methods=("GET", "POST"))
@limiter.limit(AUTH_LIMIT, methods=["POST"])
def register():
	if g.user:
		return redirect(url_for("dashboard"))

	if request.method == "POST":
		username = request.form.get("username", "").strip()
		email = request.form.get("email", "").strip().lower()
		password = request.form.get("password", "")

		errors = []
		if not USERNAME_RE.match(username):
			errors.append("Usernames are 3 to 32 letters, numbers or underscores.")
		if not EMAIL_RE.match(email) or len(email) > 254:
			errors.append("That does not look like an email address.")
		if len(password) < MIN_PASSWORD:
			errors.append(f"Passwords must be at least {MIN_PASSWORD} characters.")

		if not errors:
			db = get_db()
			try:
				db.execute("INSERT INTO User (username, email, password_hash) VALUES (?, ?, ?)", (username, email, bcrypt.generate_password_hash(password).decode("utf-8")))
				db.commit()
			except sqlite3.IntegrityError:
				errors.append("That username or email is already taken.")
			else:
				flash("Account created. Log in to start playing.", "success")
				return redirect(url_for("accounts.login"))

		for error in errors:
			flash(error, "error")

	return render_template("account.html", mode="register")


@bp.route("/login", methods=("GET", "POST"))
@limiter.limit(AUTH_LIMIT, methods=["POST"])
def login():
	if g.user:
		return redirect(url_for("dashboard"))

	if request.method == "POST":
		email = request.form.get("email", "").strip().lower()
		user = get_db().execute("SELECT * FROM User WHERE email = ?", (email,)).fetchone()
		if user is None or not bcrypt.check_password_hash(user["password_hash"], request.form.get("password", "")):
			flash("Incorrect email or password.", "error")
		else:
			session.clear()
			session["user_id"] = user["user_id"]
			session.permanent = True
			return redirect(url_for("dashboard"))

	return render_template("account.html", mode="login")


@bp.route("/logout")
def logout():
	session.clear()
	flash("You have been logged out.", "success")
	return redirect(url_for("index"))


@bp.route("/profile", methods=("GET", "POST"))
@login_required
def profile():
	if request.method == "POST":
		db = get_db()
		username = request.form.get("username", "").strip()
		email = request.form.get("email", "").strip().lower()
		bio = request.form.get("bio", "").strip()
		new_password = request.form.get("new_password", "")

		errors = []
		if not USERNAME_RE.match(username):
			errors.append("Usernames are 3 to 32 letters, numbers or underscores.")
		if not EMAIL_RE.match(email) or len(email) > 254:
			errors.append("That does not look like an email address.")
		if len(bio) > MAX_BIO:
			errors.append(f"Your bio must be {MAX_BIO} characters or fewer.")
		if new_password and len(new_password) < MIN_PASSWORD:
			errors.append(f"Passwords must be at least {MIN_PASSWORD} characters.")

		changed = username != g.user["username"] or email != g.user["email"]
		if changed or new_password:
			stored = db.execute("SELECT password_hash FROM User WHERE user_id = ?", (g.user["user_id"],)).fetchone()
			if not bcrypt.check_password_hash(stored["password_hash"], request.form.get("current_password", "")):
				errors.append("Enter your current password to change those details.")

		if errors:
			for error in errors:
				flash(error, "error")
			return render_template("account.html", mode="profile")

		try:
			db.execute("UPDATE User SET username = ?, email = ?, bio = ? WHERE user_id = ?", (username, email, bio, g.user["user_id"]))
			if new_password:
				db.execute("UPDATE User SET password_hash = ? WHERE user_id = ?", (bcrypt.generate_password_hash(new_password).decode("utf-8"), g.user["user_id"]))
			db.commit()
		except sqlite3.IntegrityError:
			db.rollback()
			flash("That username or email is already taken.", "error")
			return render_template("account.html", mode="profile")

		flash("Profile updated.", "success")
		return redirect(url_for("accounts.profile"))

	return render_template("account.html", mode="profile")


@bp.route("/admin")
@admin_required
def admin():
	db = get_db()
	games = db.execute("SELECT g.game_id, g.join_code, g.status, g.current_turn, g.created_at, m.name AS map_name, COUNT(gp.gameplayer_id) AS players FROM Game g LEFT JOIN Map m ON m.map_id = g.map_id LEFT JOIN GamePlayer gp ON gp.game_id = g.game_id GROUP BY g.game_id ORDER BY g.created_at DESC LIMIT 40").fetchall()
	users = db.execute("SELECT user_id, username, email, created_at, reputation, is_admin FROM User ORDER BY created_at DESC").fetchall()
	counts = {"users": db.execute("SELECT COUNT(*) c FROM User").fetchone()["c"], "active": db.execute("SELECT COUNT(*) c FROM Game WHERE status = 'active'").fetchone()["c"], "total": db.execute("SELECT COUNT(*) c FROM Game").fetchone()["c"]}
	return render_template("admin.html", games=games, users=users, counts=counts)


def summary(db, user_id):
	row = db.execute("SELECT COUNT(*) AS played, SUM(CASE WHEN gp.result = 'win' THEN 1 ELSE 0 END) AS won, SUM(CASE WHEN gp.result = 'draw' THEN 1 ELSE 0 END) AS drawn, SUM(g.current_turn) AS turns FROM GamePlayer gp JOIN Game g ON g.game_id = gp.game_id WHERE gp.user_id = ? AND g.status = 'complete'", (user_id,)).fetchone()

	played, won, drawn = row["played"] or 0, row["won"] or 0, row["drawn"] or 0
	credit = won + drawn * 0.5
	live = db.execute("SELECT COUNT(*) AS c FROM GamePlayer gp JOIN Game g ON g.game_id = gp.game_id WHERE gp.user_id = ? AND g.status = 'active'", (user_id,)).fetchone()["c"]
	banked = db.execute("SELECT COALESCE(SUM(gp.resources), 0) AS total FROM GamePlayer gp JOIN Game g ON g.game_id = gp.game_id WHERE gp.user_id = ? AND g.status = 'active'", (user_id,)).fetchone()["total"]
	reputation = db.execute("SELECT reputation FROM User WHERE user_id = ?", (user_id,)).fetchone()["reputation"]

	return {"played": played, "won": won, "drawn": drawn, "lost": played - won - drawn, "credit": credit, "win_rate": round((credit / played) * 100) if played else 0, "avg_turns": round((row["turns"] or 0) / played) if played else 0, "in_progress": live, "resources": banked, "reputation": reputation}


def running(db, user_id):
	return db.execute("SELECT g.join_code, g.current_turn, g.board_size, gp.resources, m.name AS map_name, (SELECT COUNT(*) FROM Territory t WHERE t.game_id = g.game_id AND t.owner_id = gp.user_id) AS territories, (SELECT COUNT(*) FROM Unit un WHERE un.game_id = g.game_id AND un.owner_id = gp.user_id) AS units FROM GamePlayer gp JOIN Game g ON g.game_id = gp.game_id LEFT JOIN Map m ON m.map_id = g.map_id WHERE gp.user_id = ? AND g.status = 'active' ORDER BY g.game_id DESC", (user_id,)).fetchall()


def recent(db, user_id, limit=DETAIL_LIMIT):
	out = []
	for game in db.execute("SELECT g.game_id, g.join_code, g.current_turn, g.completed_at, g.winner_id, m.name AS map_name, w.username AS winner_name FROM GamePlayer gp JOIN Game g ON g.game_id = gp.game_id LEFT JOIN Map m ON m.map_id = g.map_id LEFT JOIN User w ON w.user_id = g.winner_id WHERE gp.user_id = ? AND g.status = 'complete' ORDER BY g.completed_at DESC, g.game_id DESC LIMIT ?", (user_id, limit)).fetchall():
		standings = db.execute("SELECT u.user_id, u.username, gp.player_colour, gp.is_eliminated, gp.resources, gp.result, (SELECT COUNT(*) FROM Territory t WHERE t.game_id = gp.game_id AND t.owner_id = gp.user_id) AS territories, (SELECT COUNT(*) FROM Unit un WHERE un.game_id = gp.game_id AND un.owner_id = gp.user_id) AS units FROM GamePlayer gp JOIN User u ON u.user_id = gp.user_id WHERE gp.game_id = ? ORDER BY territories DESC, units DESC, gp.resources DESC", (game["game_id"],)).fetchall()
		deals = db.execute("SELECT COUNT(*) AS signed, SUM(CASE WHEN status = 'breached' THEN 1 ELSE 0 END) AS broken FROM DiplomacyAgreement WHERE game_id = ? AND (proposer_id = ? OR recipient_id = ?) AND status IN ('active', 'expired', 'breached')", (game["game_id"], user_id, user_id)).fetchone()

		mine = next((row for row in standings if row["user_id"] == user_id), None)
		item = dict(game, standings=[dict(row) for row in standings], deals_signed=deals["signed"] or 0, deals_broken=deals["broken"] or 0)
		item["result"] = mine["result"] if mine else None
		item["won"] = item["result"] == "win"
		item["drawn"] = item["result"] == "draw"
		item["placing"] = next((place for place, row in enumerate(standings, 1) if row["user_id"] == user_id), None)
		out.append(item)
	return out


def rank_points(played, won, drawn, survived, turn_credit, reputation):
	base = won * POINTS["win"] + drawn * POINTS["draw"] + played * POINTS["played"] + survived * POINTS["survived"] + turn_credit * POINTS["per_turn"]
	return int(round(base * (0.5 + (max(0, min(100, reputation)) / 100.0))))


def standings(db):
	table = []
	for row in db.execute("SELECT u.user_id, u.username, u.reputation, u.bio, COUNT(g.game_id) AS played, SUM(CASE WHEN gp.result = 'win' THEN 1 ELSE 0 END) AS won, SUM(CASE WHEN gp.result = 'draw' THEN 1 ELSE 0 END) AS drawn, SUM(CASE WHEN gp.is_eliminated = 0 THEN 1 ELSE 0 END) AS survived, SUM(MIN(g.current_turn, ?)) AS turn_credit FROM User u JOIN GamePlayer gp ON gp.user_id = u.user_id JOIN Game g ON g.game_id = gp.game_id AND g.status = 'complete' GROUP BY u.user_id", (MAX_TURN_POINTS,)).fetchall():
		played, won, drawn = row["played"] or 0, row["won"] or 0, row["drawn"] or 0
		table.append({"user_id": row["user_id"], "username": row["username"], "reputation": row["reputation"], "bio": row["bio"], "played": played, "won": won, "drawn": drawn, "lost": played - won - drawn, "win_rate": round(((won + drawn * 0.5) / played) * 100) if played else 0, "points": rank_points(played, won, drawn, row["survived"] or 0, row["turn_credit"] or 0, row["reputation"])})

	table.sort(key=lambda row: (-row["points"], -row["win_rate"], row["username"].lower()))

	place, previous = 0, None
	for index, row in enumerate(table, 1):
		if row["points"] != previous:
			place, previous = index, row["points"]
		row["place"] = place
	return table


def my_rank(db, user_id):
	return next((row for row in standings(db) if row["user_id"] == user_id), None)

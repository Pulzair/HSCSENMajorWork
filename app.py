import os
import secrets
from datetime import timedelta

from dotenv import load_dotenv
from flask import Flask, g, render_template, request

import accounts
import db
import engine
import play
import world
from extensions import limiter, socketio

load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=24)

socketio.init_app(app)
limiter.init_app(app)
db.init_app(app)
accounts.init_app(app)
play.init_app(app)
world.init_app(app)


@app.errorhandler(403)
def forbidden(error):
	return render_template("error.html", code=403, title="Not allowed", message="You do not have permission to view that page."), 403


@app.errorhandler(404)
def not_found(error):
	return render_template("error.html", code=404, title="Page not found", message="That page does not exist. It may have been a mistyped address, or a game that has since finished."), 404


@app.errorhandler(429)
def too_many_requests(error):
	return render_template("error.html", code=429, title="Too many attempts", message="That was a lot of tries in a short space of time. Wait a minute and go again."), 429


@app.route("/")
def index():
	return render_template("index.html")


@app.route("/dashboard")
@accounts.login_required
def dashboard():
	conn = db.get_db()
	engine.sweep_abandoned(conn)
	return render_template("dashboard.html", stats=accounts.summary(conn, g.user["user_id"]), recent=accounts.recent(conn, g.user["user_id"]), running=accounts.running(conn, g.user["user_id"]))


@app.route("/leaderboard")
def rankings():
	conn = db.get_db()
	engine.sweep_abandoned(conn)
	return render_template("leaderboard.html", table=accounts.standings(conn), floor=accounts.RANKED_FLOOR, me=accounts.my_rank(conn, g.user["user_id"]) if g.user else None)


@app.route("/guide")
def guide():
	return render_template("guide.html", roster=world.roster_by_layer(), improvements=world.catalogue_by_layer(), disasters=engine.load_disasters())


if __name__ == "__main__":
	host = os.environ.get("FLASK_HOST", "127.0.0.1")
	port = int(os.environ.get("FLASK_PORT", 5000))
	debug = os.environ.get("FLASK_DEBUG", "").lower() in ("1", "true", "yes", "on")
	socketio.run(app, host=host, port=port, debug=debug, allow_unsafe_werkzeug=True)

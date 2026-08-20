# import libraries
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

#load enviroment file
load_dotenv()

#initialise app with secret key + flask
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=24)

# more app init with all the libraries
socketio.init_app(app)
limiter.init_app(app)
db.init_app(app)
accounts.init_app(app)
play.init_app(app)
world.init_app(app)

# build the database from schema.sql on a fresh clone, then load the map files, so a new
# machine only needs the requirements installed and nothing else
if db.ensure_database(app):
	with app.app_context():
		world.sync_maps()

# handle 403 erros (Standard)
@app.errorhandler(403)
def forbidden(error):
	return render_template("error.html", code=403, title="Not allowed", message="You do not have permission to view that page."), 403

# handle 404 erros (standard + updated for game)
@app.errorhandler(404)
def not_found(error):
	return render_template("error.html", code=404, title="Page not found", message="That page does not exist. It may have been a mistyped address, or a game that has since finished."), 404

# handle 429 errors (standard)
@app.errorhandler(429)
def too_many_requests(error):
	return render_template("error.html", code=429, title="Too many attempts", message="That was a lot of tries in a short space of time. Wait a minute and go again."), 429

# base route
@app.route("/")
def index():
	# this line same as all similar ones call the html file to render
	return render_template("index.html")

# dashboard
@app.route("/dashboard")
@accounts.login_required # security req
def dashboard():
	# connect to the databse at login / accessing dashboard
	conn = db.get_db()
	engine.sweep_abandoned(conn)
	return render_template("dashboard.html", stats=accounts.summary(conn, g.user["user_id"]), recent=accounts.recent(conn, g.user["user_id"]), running=accounts.running(conn, g.user["user_id"]))

#leaderboard
@app.route("/leaderboard")
def rankings():
	conn = db.get_db()
	# checks for old databases / game abandon
	engine.sweep_abandoned(conn)
	return render_template("leaderboard.html", table=accounts.standings(conn), floor=accounts.RANKED_FLOOR, me=accounts.my_rank(conn, g.user["user_id"]) if g.user else None)

# guide page for internal help, can access without terminating current game window
@app.route("/guide")
def guide():
	return render_template("guide.html", roster=world.roster_by_layer(), improvements=world.catalogue_by_layer(), disasters=engine.load_disasters())

# if --name-- run stuff
if __name__ == "__main__":
	host = os.environ.get("FLASK_HOST", "127.0.0.1")
	port = int(os.environ.get("FLASK_PORT", 5000))
	debug = os.environ.get("FLASK_DEBUG", "").lower() in ("1", "true", "yes", "on")
	socketio.run(app, host=host, port=port, debug=debug, allow_unsafe_werkzeug=True)
	# non hardocded values (fixes old bug as specified in build log document)

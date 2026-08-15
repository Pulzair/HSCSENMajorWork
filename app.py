import os
import secrets
from datetime import timedelta
from dotenv import load_dotenv
from flask import Flask, render_template

import db
import admin
import auth
import lobby
import maps
import units
from extensions import socketio

load_dotenv()

app = Flask(__name__)

app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY") or secrets.token_hex(32)

app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=24)

socketio.init_app(app)

db.init_app(app)

auth.init_app(app)

lobby.init_app(app)

maps.init_app(app)

admin.init_app(app)


@app.errorhandler(403)
def forbidden(error):
    return render_template("403.html"), 403


@app.errorhandler(404)
def not_found(error):
    return render_template("404.html"), 404


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/dashboard")
@auth.login_required
def dashboard():
    return render_template("dashboard.html")


@app.route("/units")
def unit_roster():
    return render_template("units.html", grouped=units.roster_by_layer())

if __name__ == "__main__":
    host = os.environ.get("FLASK_HOST", "127.0.0.1")
    port = int(os.environ.get("FLASK_PORT", 5000))

    debug = os.environ.get("FLASK_DEBUG", "").lower() in ("1", "true", "yes", "on")

    socketio.run(app, host=host, port=port, debug=debug)

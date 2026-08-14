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

# Load variables from the .env file
load_dotenv()

app = Flask(__name__)

# SECRET_KEY to sign Flasks session cookies for security requirements
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY") or secrets.token_hex(32)

# Sessions expire after 24 hours of inactivity (design section 9.4).
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=24)

#Utilise socketio for later real time features - init command
socketio.init_app(app)


db.init_app(app)

# Register the authentication blueprint (register / login / logout).
auth.init_app(app)

# Register the lobby blueprint (create / join / start games).
lobby.init_app(app)

# Register the `flask load-maps` command.
maps.init_app(app)

# Register the admin dashboard + its CLI commands (make-admin, seed-testers).
admin.init_app(app)


@app.errorhandler(403)
def forbidden(error):
    # Unauthorised action: return 403 and show a notification (section 9.3).
    return render_template("403.html"), 403

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/dashboard")
@auth.login_required
def dashboard():
    return render_template("dashboard.html")


@app.route("/units")
def unit_roster():
    # Public on purpose, it's just reference info, no login needed
    return render_template("units.html", grouped=units.roster_by_layer())


if __name__ == "__main__":
    host = os.environ.get("FLASK_HOST", "127.0.0.1")
    port = int(os.environ.get("FLASK_PORT", 5000))

    debug = os.environ.get("FLASK_DEBUG", "").lower() in ("1", "true", "yes", "on")

    socketio.run(app, host=host, port=port, debug=debug)

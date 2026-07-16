"""
Battley 
"""
import os
import secrets
from datetime import timedelta
from dotenv import load_dotenv
from flask import Flask, render_template

import db
import auth
import lobby
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


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/dashboard")
@auth.login_required
def dashboard():
    return render_template("dashboard.html")


if __name__ == "__main__":
    # allow_unsafe_werkzeug for ease of dev testing
    socketio.run(app, host="127.0.0.1", port=5000, debug=True, allow_unsafe_werkzeug=True)

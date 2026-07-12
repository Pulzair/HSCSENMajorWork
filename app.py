"""
Battley 
"""
import os
import secrets
from dotenv import load_dotenv
from flask import Flask, render_template
from flask_socketio import SocketIO

import db

# Load variables from the .env file
load_dotenv()

app = Flask(__name__)

# SECRET_KEY to sign Flasks session cookies for security requirements
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY") or secrets.token_hex(32)

#Utilise socketio for later real time features - init command
socketio = SocketIO(app, async_mode="threading")

db.init_app(app)


@app.route("/")
def index():
    return render_template("index.html")


if __name__ == "__main__":
    # allow_unsafe_werkzeug for ease of dev testing
    socketio.run(app, host="127.0.0.1", port=5000, debug=True, allow_unsafe_werkzeug=True)

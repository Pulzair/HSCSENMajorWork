import functools
import re
import sqlite3

from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for
)
from flask_bcrypt import Bcrypt

from db import get_db

bp = Blueprint("auth", __name__)

bcrypt = Bcrypt()

USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,32}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_PASSWORD_LENGTH = 8


def init_app(app):
    bcrypt.init_app(app)
    app.register_blueprint(bp)


@bp.before_app_request
def load_logged_in_user():
    user_id = session.get("user_id")
    if user_id is None:
        g.user = None
    else:
        g.user = get_db().execute(
            "SELECT user_id, username, email, is_admin FROM User WHERE user_id = ?",
            (user_id,),
        ).fetchone()


def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for("auth.login"))
        return view(**kwargs)
    return wrapped_view


@bp.route("/register", methods=("GET", "POST"))
def register():
    if g.user:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        errors = []

        if not USERNAME_RE.match(username):
            errors.append("Username must be 3-32 characters: letters, numbers or underscores only.")
        if len(email) > 254 or not EMAIL_RE.match(email):
            errors.append("Please enter a valid email address.")
        if len(password) < MIN_PASSWORD_LENGTH:
            errors.append(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")

        db = get_db()

        if not errors:
            if db.execute("SELECT 1 FROM User WHERE username = ?", (username,)).fetchone():
                errors.append("That username is already taken.")
            if db.execute("SELECT 1 FROM User WHERE email = ?", (email,)).fetchone():
                errors.append("An account with that email already exists.")

        if not errors:
            password_hash = bcrypt.generate_password_hash(password).decode("utf-8")
            try:
                db.execute(
                    "INSERT INTO User (username, email, password_hash) VALUES (?, ?, ?)",
                    (username, email, password_hash),
                )
                db.commit()
            except sqlite3.IntegrityError:
                errors.append("Could not create the account. Please try again.")
            else:
                flash("Account created. Please log in.", "success")
                return redirect(url_for("auth.login"))

        for error in errors:
            flash(error, "error")

    return render_template("auth/register.html")


@bp.route("/login", methods=("GET", "POST"))
def login():
    if g.user:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = get_db().execute(
            "SELECT * FROM User WHERE email = ?", (email,)
        ).fetchone()

        if user is None or not bcrypt.check_password_hash(user["password_hash"], password):
            flash("Incorrect email or password.", "error")
        else:
            session.clear()
            session["user_id"] = user["user_id"]
            session.permanent = True  
            return redirect(url_for("dashboard"))

    return render_template("auth/login.html")


@bp.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("index"))

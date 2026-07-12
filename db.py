import sqlite3
from pathlib import Path

import click
from flask import g
# g is like a temporary storage box from flask, used to store the db for individual requests

# Find the database please
BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "data" / "database.db"
SCHEMA_PATH = BASE_DIR / "schema.sql"

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db

def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()

def init_db():
    db = get_db()
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        db.executescript(f.read())
    db.commit()

#click is flask's terminal wrapper for commands essentially
@click.command("init-db")
def init_db_command():
    init_db()
    click.echo(f"Initialised the database at {DATABASE_PATH}") #debug stuff

def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)

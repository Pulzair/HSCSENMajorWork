import sqlite3

import click
from flask import current_app, g

from pathlib import Path

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
	conn = g.pop("db", None)
	if conn is not None:
		conn.close()


def init_db():
	conn = get_db()
	with open(SCHEMA_PATH, "r", encoding="utf-8") as handle:
		conn.executescript(handle.read())
	conn.commit()


@click.command("init-db")
def init_db_command():
	init_db()
	click.echo(f"Initialised the database at {DATABASE_PATH}")


def init_app(app):
	app.teardown_appcontext(close_db)
	app.cli.add_command(init_db_command)

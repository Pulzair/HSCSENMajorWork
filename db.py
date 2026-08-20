# import libraries
import sqlite3

import click
from flask import current_app, g

from pathlib import Path

# setup base directory and database locations
BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "data" / "database.db"
SCHEMA_PATH = BASE_DIR / "schema.sql"


# get database
def get_db():
	if "db" not in g:
		g.db = sqlite3.connect(DATABASE_PATH)
		g.db.row_factory = sqlite3.Row
		g.db.execute("PRAGMA foreign_keys = ON")
	return g.db


# close database
def close_db(exception=None):
	conn = g.pop("db", None)
	if conn is not None:
		conn.close()


# initialise database using the schema so that it matches requirements
def init_db():
	conn = get_db()
	with open(SCHEMA_PATH, "r", encoding="utf-8") as handle:
		conn.executescript(handle.read())
	conn.commit()


# link init_db command to the comand with a debugging message
@click.command("init-db")
def init_db_command():
	init_db()
	click.echo(f"Initialised the database at {DATABASE_PATH}")


# check if the database file is actually there yet, Path() so a plain string still works
def database_missing():
	return not Path(DATABASE_PATH).exists()


# build the database on a fresh machine so a clone just runs, only when the file is
# missing because schema.sql drops every table first and would wipe a real save
def ensure_database(app):
	if not database_missing():
		return False
	Path(DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)
	with app.app_context():
		init_db()
	return True


# initialise the app with the db
def init_app(app):
	app.teardown_appcontext(close_db)
	app.cli.add_command(init_db_command)

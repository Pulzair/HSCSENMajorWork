# HSCSENMajorWork aka Battley
Browser-Based Multiplayer Turn-Based Territory Strategy Game

# What is this Project:
The proposed solution is a web-based multiplayer turn-based territory strategy game targeting high school students aged 13 to 18. The system includes five key innovations, the combination of which is currently absent from market competitors:
1. Simultaneously delayed orders: rather than alternating turns, all players submit their moves secretly. Orders are revealed and resolved simultaneously, eliminating the information advantage of moving second and rewarding strategic prediction over reaction speed.
2. Layered map system: the game world consists of three distinct explorable layers — land, underground and sky. Each layer has unique properties. Units on different layers cannot engage directly unless specific mechanics are used.
3. Finite resource pool: fixed total resources on the map. Aggressive expansion depletes the global supply, creating strategic tension between early aggression and long-term sustainability.
4. Diplomacy system: players may form alliances, trade resources and sign non-aggression agreements enforced by the game engine. Breaking agreements affects reputation stats. This directly simulates negotiation and civic responsibility.
5. Dynamic natural events: random natural disaster events that shift the fog of war, destroy terrain, block movement and redistribute resources.

# Setup on a new machine
Run these from the project folder, in order.

1. Make the virtual environment:
		python3 -m venv .venv

2. Activate it.
	macOS and Linux:
		source .venv/bin/activate
	Windows PowerShell:
		.venv\Scripts\Activate.ps1
	The prompt should now start with `(.venv)`. If it does not, the next step installs to
	the wrong Python and the app will fail with `ModuleNotFoundError: No module named 'dotenv'`.

3. Install the dependencies into that environment:
		pip install -r requirements.txt
	If `pip` is not found use `pip3`. Do not run this without activating first.

4. Make a `.env` file in the project folder:
		SECRET_KEY=change_this_to_anything_long_and_random
		FLASK_HOST=127.0.0.1
		FLASK_PORT=5000
		FLASK_DEBUG=0
	`.env.example` has the same keys to copy from. The file is gitignored on purpose so the
	secret key is kept well a secret (shocker).

# Running Commands
	.venv/bin/python app.py
Then open http://127.0.0.1:5000

The database builds itself from `schema.sql` the first time the app starts.

To wipe it and start over, delete `data/database.db` and start the app again, or run:
	.venv/bin/flask --app app init-db

# If port conflict:
	lsof -nP -iTCP@127.0.0.1:5000 -sTCP:LISTEN
	pkill -f "app.py"
On macOS port 5000 is often taken by AirPlay Receiver. Either turn it off in System Settings,
or set `FLASK_PORT=5001` in `.env`.
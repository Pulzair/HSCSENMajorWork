# HSCSENMajorWork aka Battley
Browser-Based Multiplayer Turn-Based Territory Strategy Game

# What is this Project:
The proposed solution is a web-based multiplayer turn-based territory strategy game targeting high school students aged 13 to 18. The system includes five key innovations, the combination of which is currently absent from market competitors:
1. Simultaneously delayed orders: rather than alternating turns, all players submit their moves secretly. Orders are revealed and resolved simultaneously, eliminating the information advantage of moving second and rewarding strategic prediction over reaction speed.
2. Layered map system: the game world consists of three distinct explorable layers — land, underground and sky. Each layer has unique properties. Units on different layers cannot engage directly unless specific mechanics are used.
3. Finite resource pool: fixed total resources on the map. Aggressive expansion depletes the global supply, creating strategic tension between early aggression and long-term sustainability.
4. Diplomacy system: players may form alliances, trade resources and sign non-aggression agreements enforced by the game engine. Breaking agreements affects reputation stats. This directly simulates negotiation and civic responsibility.
5. Dynamic natural events: random natural disaster events that shift the fog of war, destroy terrain, block movement and redistribute resources.

# Setting up Dependencies
Install requirements.txt

# Running Commands
.venv/bin/python app.py
http://127.0.0.1:5000 

# If port conflict:
lsof -nP -iTCP@127.0.0.1:5000 -sTCP:LISTEN
pkill -f "app.py"
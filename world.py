import json
import random
from pathlib import Path

import click

from db import get_db

DATA_DIR = Path(__file__).resolve().parent / "data"
MAPS_DIR = DATA_DIR / "maps"
UNITS_DIR = DATA_DIR / "units"
IMPROVEMENTS_DIR = DATA_DIR / "improvements"

LAYERS = ("land", "underground", "sky")
TERRAINS = ("plains", "mountain", "water", "destroyed")
CITY_VISION = 1
MOVE_COST = {"plains": 1, "water": 1, "mountain": 2, "destroyed": 99}
NEIGHBOURS = ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1))

MIN_BOARD = 8
MAX_BOARD = 25

_roster = None
_catalogue = None


# read every json file in a folder and merge them into one dict
def _load_dir(folder):
	merged = {}
	for path in sorted(folder.glob("*.json")):
		with open(path, "r", encoding="utf-8") as handle:
			merged.update(json.load(handle))
	return merged


# load the unit types from data/units, cached after the first read
def load_roster(force=False):
	global _roster
	if _roster is None or force:
		_roster = _load_dir(UNITS_DIR)
	return _roster


# grab one unit spec by its key
def get_unit(kind):
	return load_roster().get(kind)


# first layer in the list is the units native one
def home_layer(kind):
	spec = get_unit(kind)
	return spec["layers"][0] if spec else None


# more than one layer means it can cross between them
def can_transition(kind):
	spec = get_unit(kind)
	return bool(spec) and len(spec["layers"]) > 1


# unit types that can be built on a layer, cheapest first
def buildable_in(layer):
	roster = load_roster()
	kinds = [key for key, spec in roster.items() if layer in spec["layers"]]
	return sorted(kinds, key=lambda key: roster[key]["cost"])


# checks both the layer and the terrain, water blocks land units etc
def can_occupy(kind, layer, terrain):
	spec = get_unit(kind)
	if spec is None:
		return False
	return layer in spec["layers"] and terrain in spec["terrain"]


# whole roster grouped by layer for the guide page
def roster_by_layer():
	roster = load_roster()
	return {layer: [dict(roster[key], key=key) for key in buildable_in(layer)] for layer in LAYERS}


# load the tile improvements from data/improvements
def load_catalogue(force=False):
	global _catalogue
	if _catalogue is None or force:
		_catalogue = _load_dir(IMPROVEMENTS_DIR)
	return _catalogue


# grab one improvement spec
def get_improvement(key):
	return load_catalogue().get(key)


# improvement has to match both layer and terrain
def improvement_fits(key, layer, terrain):
	spec = get_improvement(key)
	if spec is None:
		return False
	return layer in spec["layers"] and terrain in spec["terrain"]


# improvements you could build on a tile, cheapest first
def improvement_options(layer, terrain):
	catalogue = load_catalogue()
	keys = [key for key in catalogue if improvement_fits(key, layer, terrain)]
	return sorted(keys, key=lambda key: catalogue[key]["cost"])


# barracks is the only one that lets you produce units
def allows_production(key):
	spec = get_improvement(key)
	return bool(spec) and spec.get("allows_production", False)


# improvements grouped by layer for the guide page
def catalogue_by_layer():
	catalogue = load_catalogue()
	grouped = {}
	for layer in LAYERS:
		keys = sorted(catalogue, key=lambda key: catalogue[key]["cost"])
		grouped[layer] = [dict(catalogue[key], key=key) for key in keys if layer in catalogue[key]["layers"]]
	return grouped


# read all the map json files
def read_config_files():
	configs = []
	for path in sorted(MAPS_DIR.glob("*.json")):
		with open(path, "r", encoding="utf-8") as handle:
			configs.append((path.name, json.load(handle)))
	return configs


# keep the board size between the min and max so the lobby cant break it
def clamp_board(size):
	try:
		size = int(size)
	except (TypeError, ValueError):
		return MIN_BOARD
	return max(MIN_BOARD, min(MAX_BOARD, size))


# cellular automata pass, makes the random noise clump into blobs
def _smooth(cells, width, height, passes, birth, keep):
	for _pass in range(passes):
		nxt = {}
		for y in range(height):
			for x in range(width):
				near = sum(1 for dx in (-1, 0, 1) for dy in (-1, 0, 1) if (dx or dy) and cells.get((x + dx, y + dy)))
				nxt[(x, y)] = near >= (keep if cells.get((x, y)) else birth)
		cells = nxt
	return cells


# random noise then smoothed, gives lakes and mountain ranges not static
def _blobs(rng, width, height, density, passes=3, birth=5, keep=4):
	cells = {(x, y): rng.random() < density for y in range(height) for x in range(width)}
	return _smooth(cells, width, height, passes, birth, keep)


# build a whole random map, terrain then transitions then spawns
def generate_config(name, size, seed, players=6):
	size = clamp_board(size)
	rng = random.Random(seed)
	width = height = size

	water = _blobs(rng, width, height, 0.44, passes=2, birth=4, keep=3)
	mountain = _blobs(rng, width, height, 0.36, passes=2, birth=4, keep=3)
	caverns = _blobs(rng, width, height, 0.60, birth=4, keep=3)
	islands = _blobs(rng, width, height, 0.52, birth=4, keep=3)

	legend = {
		".": None,
		"P": {"terrain": "plains", "resources": 10},
		"M": {"terrain": "mountain", "resources": 6},
		"W": {"terrain": "water", "resources": 0},
		"R": {"terrain": "plains", "resources": 25},
		"I": {"terrain": "mountain", "resources": 6, "natural_resource": "iron"},
		"H": {"terrain": "plains", "resources": 10, "natural_resource": "horses"},
	}

	land_rows, under_rows, sky_rows = [], [], []
	for y in range(height):
		land, under, sky = "", "", ""
		for x in range(width):
			if water.get((x, y)) and not mountain.get((x, y)):
				land += "W"
			elif mountain.get((x, y)):
				land += "I" if rng.random() < 0.12 else "M"
			elif rng.random() < 0.08:
				land += "R"
			elif rng.random() < 0.22:
				land += "H"
			else:
				land += "P"
			if caverns.get((x, y)):
				under += "I" if rng.random() < 0.08 else ("M" if rng.random() < 0.26 else ("R" if rng.random() < 0.10 else "P"))
			else:
				under += "."
			sky += "M" if rng.random() < 0.14 else "P"
		land_rows.append(land)
		under_rows.append(under)
		sky_rows.append(sky)

	transitions = []
	for _try in range(size * 20):
		x, y = rng.randrange(width), rng.randrange(height)
		if [x, y] in transitions or land_rows[y][x] == "W":
			continue
		if under_rows[y][x] != "." or sky_rows[y][x] != ".":
			transitions.append([x, y])
		if len(transitions) >= max(10, size * 2):
			break

	spawns = []
	margin = max(1, size // 8)
	for _attempt in range(400):
		if len(spawns) >= players:
			break
		x, y = rng.randrange(margin, width - margin), rng.randrange(margin, height - margin)
		if land_rows[y][x] in "WM":
			continue
		if all(abs(x - sx) + abs(y - sy) >= max(4, size // 3) for sx, sy in spawns):
			spawns.append([x, y])
	while len(spawns) < players:
		x, y = rng.randrange(width), rng.randrange(height)
		if land_rows[y][x] not in "W":
			spawns.append([x, y])

	rows_list = [list(row) for row in land_rows]
	for sx, sy in spawns:
		rows_list[sy][sx] = "P"
		near = [(sx + dx, sy + dy) for dx, dy in NEIGHBOURS if 0 <= sx + dx < width and 0 <= sy + dy < height]
		rng.shuffle(near)
		for symbol, spot in zip(("H", "I", "R"), near):
			nx, ny = spot
			if rows_list[ny][nx] not in "W":
				rows_list[ny][nx] = symbol
		for nx, ny in near[:2]:
			if [nx, ny] not in transitions and (under_rows[ny][nx] != "." or sky_rows[ny][nx] != "."):
				transitions.append([nx, ny])
	land_rows = ["".join(row) for row in rows_list]

	return {
		"name": name,
		"description": f"A generated {size} by {size} world across three layers.",
		"generated": True,
		"seed": seed,
		"min_players": 2,
		"max_players": players,
		"width": width,
		"height": height,
		"starting_resources": 120,
		"starting_units": ["warrior", "warrior", "archer"],
		"victory_territory_share": 0.4,
		"legend": legend,
		"layers": {"land": land_rows, "underground": under_rows, "sky": sky_rows},
		"transitions": transitions,
		"spawns": spawns,
	}


# turn the letter grid into numbered territories with x y and layer
def parse_layout(config):
	legend = config["legend"]
	territories = {}
	grid = {layer: {} for layer in LAYERS}
	ref = 0

	for layer in LAYERS:
		for y, row in enumerate(config["layers"].get(layer, [])):
			for x, symbol in enumerate(row):
				spec = legend.get(symbol)
				if spec is None:
					continue
				ref += 1
				territories[ref] = {"ref": ref, "layer": layer, "x": x, "y": y, "terrain": spec["terrain"], "resources": spec["resources"], "natural_resource": spec.get("natural_resource")}
				grid[layer][(x, y)] = ref

	return {"config": config, "width": config["width"], "height": config["height"], "territories": territories, "grid": grid}


# which tiles touch which, 8 directions plus the layer crossings
def build_adjacency(layout):
	grid = layout["grid"]
	adjacency = {ref: set() for ref in layout["territories"]}

	for layer in LAYERS:
		for (x, y), ref in grid[layer].items():
			for dx, dy in NEIGHBOURS:
				neighbour = grid[layer].get((x + dx, y + dy))
				if neighbour is not None:
					adjacency[ref].add(neighbour)

	for x, y in layout["config"].get("transitions", []):
		land, under, sky = grid["land"].get((x, y)), grid["underground"].get((x, y)), grid["sky"].get((x, y))
		for a, b in ((land, under), (land, sky)):
			if a is not None and b is not None:
				adjacency[a].add(b)
				adjacency[b].add(a)

	return {ref: sorted(neighbours) for ref, neighbours in adjacency.items()}


# walk out from a tile spending the movement budget on terrain costs
def reachable(start_ref, budget, kind, by_ref, adjacency):
	home = by_ref[start_ref]["layer"]
	best = {start_ref: 0}
	frontier = [start_ref]
	while frontier:
		ref = frontier.pop()
		for neighbour in adjacency.get(ref, ()):
			target = by_ref.get(neighbour)
			if target is None or target["layer"] != home:
				continue
			if not can_occupy(kind, target["layer"], target["terrain_type"]):
				continue
			cost = MOVE_COST.get(target["terrain_type"], 99)
			if cost >= 99:
				continue
			total = best[ref] + cost
			if ref == start_ref and total > budget and budget >= 1:
				total = budget
			if total <= budget and total < best.get(neighbour, 999):
				best[neighbour] = total
				frontier.append(neighbour)
	return best


# tiles within x steps ignoring cost, used for ranged attacks
def within_range(start_ref, reach, by_ref, adjacency):
	home = by_ref[start_ref]["layer"]
	seen, frontier = {start_ref}, [start_ref]
	for _step in range(max(1, reach)):
		nxt = []
		for ref in frontier:
			for neighbour in adjacency.get(ref, ()):
				target = by_ref.get(neighbour)
				if target is not None and target["layer"] == home and neighbour not in seen:
					seen.add(neighbour)
					nxt.append(neighbour)
		frontier = nxt
	seen.discard(start_ref)
	return seen


# every tile you can change layer on, includes built gateways
def transition_refs(layout, extra=()):
	refs = set()
	for x, y in layout["config"].get("transitions", []):
		for layer in LAYERS:
			ref = layout["grid"][layer].get((x, y))
			if ref is not None:
				refs.add(ref)
	refs.update(extra)
	return refs


# tiles where someone built a gateway improvement
def gateway_refs(db, game_id):
	rows = db.execute("SELECT map_territory_ref FROM Territory WHERE game_id = ? AND improvement IN (SELECT 'gateway')", (game_id,)).fetchall()
	return {row["map_territory_ref"] for row in rows}


# generated board if the game has one, otherwise the preset map
def get_layout(map_row, game=None):
	if game is not None and game["board_json"]:
		return parse_layout(json.loads(game["board_json"]))
	return parse_layout(json.loads(map_row["layout_json"]))


# load the map files into the Map table, update if already there
def sync_maps():
	db = get_db()
	names = []
	for _filename, config in read_config_files():
		parse_layout(config)
		payload = (config.get("description"), config["min_players"], config["max_players"], json.dumps(config))
		existing = db.execute("SELECT map_id FROM Map WHERE name = ?", (config["name"],)).fetchone()
		if existing:
			db.execute("UPDATE Map SET description = ?, min_players = ?, max_players = ?, layout_json = ? WHERE map_id = ?", payload + (existing["map_id"],))
		else:
			db.execute("INSERT INTO Map (name, description, min_players, max_players, layout_json) VALUES (?, ?, ?, ?, ?)", (config["name"],) + payload)
		names.append(config["name"])
	db.commit()
	return names


# fill the board at game start and put everyone on their capital
def seed_territories(db, game_id, layout):
	for territory in layout["territories"].values():
		db.execute("INSERT INTO Territory (game_id, map_territory_ref, layer, terrain_type, resource_value, natural_resource) VALUES (?, ?, ?, ?, ?, ?)", (game_id, territory["ref"], territory["layer"], territory["terrain"], territory["resources"], territory["natural_resource"]))

	config = layout["config"]
	players = db.execute("SELECT user_id FROM GamePlayer WHERE game_id = ? ORDER BY gameplayer_id", (game_id,)).fetchall()

	adjacency = build_adjacency(layout)
	seeded = set()

	for player, (x, y) in zip(players, config.get("spawns", [])):
		ref = layout["grid"]["land"].get((x, y))
		if ref is None:
			continue
		db.execute("UPDATE Territory SET owner_id = ?, has_city = 1, is_capital = 1, capital_of = ? WHERE game_id = ? AND map_territory_ref = ?", (player["user_id"], player["user_id"], game_id, ref))
		spawn = db.execute("SELECT territory_id, layer FROM Territory WHERE game_id = ? AND map_territory_ref = ?", (game_id, ref)).fetchone()

		for kind in config.get("starting_units", []):
			spec = get_unit(kind)
			if spec is None:
				continue
			home = None
			for neighbour in adjacency.get(ref, ()):
				if neighbour in seeded:
					continue
				tile = layout["territories"].get(neighbour)
				if tile is None or tile["layer"] != spawn["layer"]:
					continue
				if not can_occupy(kind, tile["layer"], tile["terrain"]):
					continue
				home = neighbour
				break
			if home is None:
				continue
			seeded.add(home)
			db.execute("UPDATE Territory SET owner_id = ? WHERE game_id = ? AND map_territory_ref = ?", (player["user_id"], game_id, home))
			landing = db.execute("SELECT territory_id, layer FROM Territory WHERE game_id = ? AND map_territory_ref = ?", (game_id, home)).fetchone()
			db.execute("INSERT INTO Unit (game_id, owner_id, territory_id, unit_type, attack, defence, health, layer) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (game_id, player["user_id"], landing["territory_id"], kind, spec["attack"], spec["defence"], spec["health"], landing["layer"]))

		db.execute("UPDATE GamePlayer SET resources = ? WHERE game_id = ? AND user_id = ?", (config.get("starting_resources", 0), game_id, player["user_id"]))

	total = sum(t["resources"] for t in layout["territories"].values())
	db.execute("UPDATE Game SET global_resources = ? WHERE game_id = ?", (total, game_id))


# every tile you can see from and how far it sees
def vision_sources(db, game_id, user_id):
	sources = {}
	for row in db.execute("SELECT map_territory_ref FROM Territory WHERE game_id = ? AND owner_id = ?", (game_id, user_id)).fetchall():
		sources[row["map_territory_ref"]] = max(sources.get(row["map_territory_ref"], 0), CITY_VISION)

	for row in db.execute("SELECT u.unit_type, t.map_territory_ref FROM Unit u JOIN Territory t ON t.territory_id = u.territory_id WHERE u.game_id = ? AND u.owner_id = ?", (game_id, user_id)).fetchall():
		spec = get_unit(row["unit_type"])
		reach = spec.get("vision", 1) if spec else 1
		sources[row["map_territory_ref"]] = max(sources.get(row["map_territory_ref"], 0), reach)

	return sources


# spread out from each vision source, fog modifiers block sight
def compute_visible(db, game_id, user_id, adjacency, fog_modifiers):
	visible = set()
	for origin, reach in vision_sources(db, game_id, user_id).items():
		visible.add(origin)
		frontier, walked = {origin}, {origin}
		for _step in range(reach):
			nxt = set()
			for ref in frontier:
				for neighbour in adjacency.get(ref, ()):
					if neighbour in walked:
						continue
					walked.add(neighbour)
					nxt.add(neighbour)
					if fog_modifiers.get(neighbour, 1.0) >= 1.0:
						visible.add(neighbour)
			frontier = nxt
	return visible


# tiles this player has seen at some point
def explored_refs(db, game_id, user_id):
	rows = db.execute("SELECT t.map_territory_ref FROM TerritorySeen s JOIN Territory t ON t.territory_id = s.territory_id WHERE s.game_id = ? AND s.user_id = ?", (game_id, user_id)).fetchall()
	return {row["map_territory_ref"] for row in rows}


# remember tiles so terrain stays visible after units move away
def record_seen(db, game, user_id, visible, ref_to_id):
	rows = [(game["game_id"], user_id, ref_to_id[ref], game["current_turn"]) for ref in visible if ref in ref_to_id]
	if not rows:
		return
	db.executemany("INSERT OR IGNORE INTO TerritorySeen (game_id, user_id, territory_id, first_seen_turn) VALUES (?, ?, ?, ?)", rows)
	db.commit()


# visible now, explored before, or never seen
def fog_state(ref, visible, explored):
	if ref in visible:
		return "visible"
	if ref in explored:
		return "explored"
	return "hidden"


# everything the browser needs to draw the map, already fogged
def build_board(db, game, map_row, viewer_id):
	layout = get_layout(map_row, game)
	rows = db.execute("SELECT t.territory_id, t.map_territory_ref, t.terrain_type, t.resource_value, t.has_city, t.is_capital, t.fog_modifier, t.improvement, t.natural_resource, t.owner_id, gp.player_colour, u.username AS owner_name FROM Territory t LEFT JOIN GamePlayer gp ON gp.game_id = t.game_id AND gp.user_id = t.owner_id LEFT JOIN User u ON u.user_id = t.owner_id WHERE t.game_id = ?", (game["game_id"],)).fetchall()
	state = {row["map_territory_ref"]: row for row in rows}

	adjacency = build_adjacency(layout)
	crossings = transition_refs(layout)
	visible = compute_visible(db, game["game_id"], viewer_id, adjacency, {r["map_territory_ref"]: r["fog_modifier"] for r in rows})
	record_seen(db, game, viewer_id, visible, {r["map_territory_ref"]: r["territory_id"] for r in rows})
	explored = explored_refs(db, game["game_id"], viewer_id) | visible

	garrisons = {}
	for row in db.execute("SELECT t.map_territory_ref, u.unit_id, u.owner_id, u.unit_type, u.health, gp.player_colour, usr.username AS owner_name FROM Unit u JOIN Territory t ON t.territory_id = u.territory_id LEFT JOIN GamePlayer gp ON gp.game_id = u.game_id AND gp.user_id = u.owner_id LEFT JOIN User usr ON usr.user_id = u.owner_id WHERE u.game_id = ?", (game["game_id"],)).fetchall():
		spec = get_unit(row["unit_type"])
		garrisons.setdefault(row["map_territory_ref"], []).append({"unit_id": row["unit_id"], "owner_id": row["owner_id"], "type": row["unit_type"], "name": spec["name"] if spec else row["unit_type"], "health": row["health"], "max_health": spec["health"] if spec else row["health"], "colour": row["player_colour"], "owner_name": row["owner_name"], "mine": row["owner_id"] == viewer_id})

	tiles = []
	for layer_index, layer in enumerate(LAYERS):
		for y in range(layout["height"]):
			for x in range(layout["width"]):
				ref = layout["grid"][layer].get((x, y))
				if ref is None:
					continue
				seen = fog_state(ref, visible, explored)
				if seen == "hidden":
					tiles.append({"ref": ref, "layer": layer_index, "x": x, "y": y, "state": "hidden"})
					continue

				base = layout["territories"][ref]
				current = state.get(ref)
				improvement = get_improvement(current["improvement"]) if current and current["improvement"] else None
				tiles.append({
					"ref": ref,
					"tid": current["territory_id"] if current else None,
					"layer": layer_index,
					"x": x,
					"y": y,
					"state": seen,
					"terrain": current["terrain_type"] if current else base["terrain"],
					"resources": current["resource_value"] if current else base["resources"],
					"city": bool(current["has_city"]) if current else False,
					"capital": bool(current["is_capital"]) if current else False,
					"improvement": improvement["name"] if improvement else None,
					"improvement_key": current["improvement"] if current and current["improvement"] else None,
					"crossing": ref in crossings,
					"resource": (current["natural_resource"] if current else base["natural_resource"]),
					"colour": current["player_colour"] if current else None,
					"owner": current["owner_name"] if current else None,
					"mine": bool(current and current["owner_id"] == viewer_id),
					"units": garrisons.get(ref, []) if seen == "visible" else [],
				})

	return {"width": layout["width"], "height": layout["height"], "layers": list(LAYERS), "tiles": tiles, "visible": visible}


@click.command("load-maps")
# flask load-maps
def load_maps_command():
	names = sync_maps()
	click.echo(f"Loaded {len(names)} map(s): {', '.join(names)}")


# register the cli command
def init_app(app):
	app.cli.add_command(load_maps_command)

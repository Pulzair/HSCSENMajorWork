import json
from pathlib import Path

import click

import fog
import improvements
import units
from db import get_db

# ═══════════════════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════
# Maps are JSON tilemaps in data/maps/ - one row string per grid row, per layer,
# decoded through the map's own legend. Adding a map = drop in a file and run
# `flask load-maps`, no code changes (NF09). Adjacency gets worked out from the
# grid instead of being stored, which keeps the configs short enough to hand edit.
MAPS_DIR = Path(__file__).resolve().parent / "data" / "maps"

LAYERS = ("land", "underground", "sky")  # order matters, vertical links use it


# ═══════════════════════════════════════════════════════════════════════════
# PARSING
# ═══════════════════════════════════════════════════════════════════════════
def read_config_files():
    configs = []
    for path in sorted(MAPS_DIR.glob("*.json")):
        with open(path, "r", encoding="utf-8") as f:
            configs.append((path.name, json.load(f)))
    return configs


def parse_layout(config):
    """Blow a tilemap config out into territories with stable refs."""
    legend = config["legend"]
    territories = {}
    grid = {layer: {} for layer in LAYERS}
    ref = 0

    # Refs go layer, then row, then column, always in that order, so the same
    # config always gives the same map_territory_ref numbers
    for layer in LAYERS:
        for y, row in enumerate(config["layers"].get(layer, [])):
            for x, symbol in enumerate(row):
                spec = legend.get(symbol)
                if spec is None:
                    continue  # "." = hole, no territory here
                ref += 1
                territories[ref] = {
                    "ref":              ref,
                    "layer":            layer,
                    "x":                x,
                    "y":                y,
                    "terrain":          spec["terrain"],
                    "resources":        spec["resources"],
                    "natural_resource": spec.get("natural_resource"),
                }
                grid[layer][(x, y)] = ref

    return {
        "config": config,
        "width": config["width"],
        "height": config["height"],
        "territories": territories,
        "grid": grid,
    }


# Every ref mapped to its neighbours.
def build_adjacency(layout):
    grid = layout["grid"]
    adjacency = {ref: set() for ref in layout["territories"]}

    # Four orthogonal neighbours on the same layer
    for layer in LAYERS:
        for (x, y), ref in grid[layer].items():
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                neighbour = grid[layer].get((x + dx, y + dy))
                if neighbour is not None:
                    adjacency[ref].add(neighbour)

    # Vertical links, but only where the map says there's a transition. This is
    # what stitches the three layers into one world instead of three islands
    for x, y in layout["config"].get("transitions", []):
        land = grid["land"].get((x, y))
        underground = grid["underground"].get((x, y))
        sky = grid["sky"].get((x, y))
        for a, b in ((land, underground), (land, sky)):
            if a is not None and b is not None:
                adjacency[a].add(b)
                adjacency[b].add(a)

    return {ref: sorted(neighbours) for ref, neighbours in adjacency.items()}


def get_layout(map_row):
    return parse_layout(json.loads(map_row["layout_json"]))


# ═══════════════════════════════════════════════════════════════════════════
# LOADING INTO THE DB
# ═══════════════════════════════════════════════════════════════════════════
# Push every config file into the Map table, matching on name.
def sync_maps():
    db = get_db()
    names = []
    for _filename, config in read_config_files():
        parse_layout(config)  # blow up now if the config is broken, not mid game
        layout_json = json.dumps(config)
        existing = db.execute(
            "SELECT map_id FROM Map WHERE name = ?", (config["name"],)
        ).fetchone()
        if existing:
            db.execute(
                "UPDATE Map SET description = ?, min_players = ?, max_players = ?,"
                " layout_json = ? WHERE map_id = ?",
                (
                    config.get("description"),
                    config["min_players"],
                    config["max_players"],
                    layout_json,
                    existing["map_id"],
                ),
            )
        else:
            db.execute(
                "INSERT INTO Map (name, description, min_players, max_players, layout_json)"
                " VALUES (?, ?, ?, ?, ?)",
                (
                    config["name"],
                    config.get("description"),
                    config["min_players"],
                    config["max_players"],
                    layout_json,
                ),
            )
        names.append(config["name"])
    db.commit()
    return names


# Build the whole board for a game that's just started, and hand out spawns.
def seed_territories(db, game_id, map_row):
    layout = get_layout(map_row)

    for territory in layout["territories"].values():
        db.execute(
            "INSERT INTO Territory (game_id, map_territory_ref, layer, terrain_type,"
            " resource_value, natural_resource) VALUES (?, ?, ?, ?, ?, ?)",
            (
                game_id,
                territory["ref"],
                territory["layer"],
                territory["terrain"],
                territory["resources"],
                territory["natural_resource"],
            ),
        )

    players = db.execute(
        "SELECT user_id FROM GamePlayer WHERE game_id = ? ORDER BY gameplayer_id",
        (game_id,),
    ).fetchall()
    config = layout["config"]

    # Everyone gets one spawn tile with a city on it, that's the central district
    for player, (x, y) in zip(players, config.get("spawns", [])):
        ref = layout["grid"]["land"].get((x, y))
        if ref is None:
            continue
        db.execute(
            "UPDATE Territory SET owner_id = ?, has_city = 1"
            " WHERE game_id = ? AND map_territory_ref = ?",
            (player["user_id"], game_id, ref),
        )
        spawn = db.execute(
            "SELECT territory_id, layer FROM Territory"
            " WHERE game_id = ? AND map_territory_ref = ?",
            (game_id, ref),
        ).fetchone()

        # Starting army comes out of the map config too, not hardcoded
        for unit_type in config.get("starting_units", []):
            spec = units.get_unit(unit_type)
            if spec is None:
                continue
            db.execute(
                "INSERT INTO Unit (game_id, owner_id, territory_id, unit_type,"
                " attack, defence, health, layer) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    game_id,
                    player["user_id"],
                    spawn["territory_id"],
                    unit_type,
                    spec["attack"],
                    spec["defence"],
                    spec["health"],
                    spawn["layer"],
                ),
            )

        db.execute(
            "UPDATE GamePlayer SET resources = ? WHERE game_id = ? AND user_id = ?",
            (config.get("starting_resources", 0), game_id, player["user_id"]),
        )

    # The finite pool starts as everything the map is worth (FR19)
    total = sum(t["resources"] for t in layout["territories"].values())
    db.execute(
        "UPDATE Game SET global_resources = ? WHERE game_id = ?", (total, game_id)
    )


# ═══════════════════════════════════════════════════════════════════════════
# RENDERING
# ═══════════════════════════════════════════════════════════════════════════
def build_board(db, game, map_row, viewer_id):
    """Cells per layer, row by row, fogged for whoever's looking (FR10, FR11)."""
    layout = get_layout(map_row)
    rows = db.execute(
        """SELECT t.territory_id, t.map_territory_ref, t.terrain_type,
                  t.resource_value, t.has_city, t.fog_modifier,
                  t.improvement, t.natural_resource,
                  gp.player_colour, u.username AS owner_name
             FROM Territory t
        LEFT JOIN GamePlayer gp
               ON gp.game_id = t.game_id AND gp.user_id = t.owner_id
        LEFT JOIN User u ON u.user_id = t.owner_id
            WHERE t.game_id = ?""",
        (game["game_id"],),
    ).fetchall()
    state = {row["map_territory_ref"]: row for row in rows}

    # Work out what they can see, then write down that they've seen it (FR11)
    adjacency = build_adjacency(layout)
    fog_modifiers = {r["map_territory_ref"]: r["fog_modifier"] for r in rows}
    visible = fog.compute_visible(db, game["game_id"], viewer_id, adjacency, fog_modifiers)
    fog.record_seen(
        db,
        game,
        viewer_id,
        visible,
        {r["map_territory_ref"]: r["territory_id"] for r in rows},
    )
    explored = fog.explored_refs(db, game["game_id"], viewer_id) | visible

    # Units bucketed onto whatever tile they're standing on
    unit_rows = db.execute(
        """SELECT t.map_territory_ref, u.unit_type, u.health, gp.player_colour,
                  usr.username AS owner_name
             FROM Unit u
             JOIN Territory t ON t.territory_id = u.territory_id
        LEFT JOIN GamePlayer gp
               ON gp.game_id = u.game_id AND gp.user_id = u.owner_id
        LEFT JOIN User usr ON usr.user_id = u.owner_id
            WHERE u.game_id = ?""",
        (game["game_id"],),
    ).fetchall()
    by_territory = {}
    for row in unit_rows:
        spec = units.get_unit(row["unit_type"])
        by_territory.setdefault(row["map_territory_ref"], []).append(
            {
                "type":       row["unit_type"],
                "name":       spec["name"] if spec else row["unit_type"],
                "health":     row["health"],
                "colour":     row["player_colour"],
                "owner_name": row["owner_name"],
            }
        )

    grids = {}
    for layer in LAYERS:
        cells = []
        for y in range(layout["height"]):
            for x in range(layout["width"]):
                ref = layout["grid"][layer].get((x, y))
                if ref is None:
                    cells.append(None)
                    continue

                seen_state = fog.state_for(ref, visible, explored)
                if seen_state == "hidden":
                    cells.append({"ref": ref, "state": "hidden"})  # tell them nothing
                    continue

                territory = layout["territories"][ref]
                current = state.get(ref)
                cells.append({
                    "ref": ref,
                    "state": seen_state,
                    "terrain": current["terrain_type"] if current else territory["terrain"],
                    "resources": current["resource_value"] if current else territory["resources"],
                    "has_city": bool(current["has_city"]) if current else False,
                    "improvement": improvements.get(current["improvement"])
                    if current and current["improvement"]
                    else None,
                    "natural_resource": (
                        current["natural_resource"] if current
                        else territory["natural_resource"]
                    ),
                    "owner_colour": current["player_colour"] if current else None,
                    "owner_name": current["owner_name"] if current else None,
                    # Only report units where they're actually looking. Remembered
                    # ground must never leak where the enemy is standing right now
                    "units": by_territory.get(ref, []) if seen_state == "visible" else [],
                })
        grids[layer] = cells

    return {
        "width": layout["width"],
        "height": layout["height"],
        "grids": grids,
        "visible": visible,
    }


# ═══════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════
@click.command("load-maps")
def load_maps_command():
    # Remember the Map table holds a COPY of the config, so editing a json file
    # does nothing at all until this is run again. Got me once already
    names = sync_maps()
    click.echo(f"Loaded {len(names)} map(s): {', '.join(names)}")


def init_app(app):
    app.cli.add_command(load_maps_command)

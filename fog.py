import units

# ═══════════════════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════
# Fog of war (FR11). Every tile is one of three things to a player:
#   visible  - something of theirs is in range of it right now
#   explored - they saw it before, so they remember the ground but not who's on it
#   hidden   - never seen, they get told nothing at all
# Visibility gets recalculated every render because units move. Exploration is
# history so it has to be saved -> TerritorySeen.

CITY_VISION = 1  # how far you see out from land you own


# ═══════════════════════════════════════════════════════════════════════════
# VISION
# ═══════════════════════════════════════════════════════════════════════════
# Every ref the player sees out from, mapped to how far it reaches.
def vision_sources(db, game_id, user_id):
    sources = {}

    # Your own territory always shows you a bit of the area around it
    owned = db.execute(
        "SELECT map_territory_ref FROM Territory WHERE game_id = ? AND owner_id = ?",
        (game_id, user_id),
    ).fetchall()
    for row in owned:
        ref = row["map_territory_ref"]
        sources[ref] = max(sources.get(ref, 0), CITY_VISION)

    # Units see further, and how far comes from their config (NF09). This is the
    # whole reason a Sky Skimmer or a Dire Bat is worth buying
    garrisons = db.execute(
        """SELECT u.unit_type, t.map_territory_ref
             FROM Unit u
             JOIN Territory t ON t.territory_id = u.territory_id
            WHERE u.game_id = ? AND u.owner_id = ?""",
        (game_id, user_id),
    ).fetchall()
    for row in garrisons:
        spec = units.get_unit(row["unit_type"])
        reach = spec.get("vision", 1) if spec else 1
        ref = row["map_territory_ref"]
        sources[ref] = max(sources.get(ref, 0), reach)

    return sources


def compute_visible(db, game_id, user_id, adjacency, fog_modifiers):
    """Set of refs the player can see right now."""
    visible = set()

    for origin, reach in vision_sources(db, game_id, user_id).items():
        visible.add(origin)  # you always see where you're standing, fog or not

        # Walk outwards `reach` steps through the adjacency graph
        frontier = {origin}
        walked = {origin}
        for _step in range(reach):
            nxt = set()
            for ref in frontier:
                for neighbour in adjacency.get(ref, ()):
                    if neighbour in walked:
                        continue
                    walked.add(neighbour)
                    nxt.add(neighbour)
                    # A disaster-fogged tile can only be seen by standing on it
                    if fog_modifiers.get(neighbour, 1.0) >= 1.0:
                        visible.add(neighbour)
            frontier = nxt

    return visible


# ═══════════════════════════════════════════════════════════════════════════
# EXPLORATION HISTORY
# ═══════════════════════════════════════════════════════════════════════════
def explored_refs(db, game_id, user_id):
    rows = db.execute(
        """SELECT t.map_territory_ref
             FROM TerritorySeen s
             JOIN Territory t ON t.territory_id = s.territory_id
            WHERE s.game_id = ? AND s.user_id = ?""",
        (game_id, user_id),
    ).fetchall()
    return {row["map_territory_ref"] for row in rows}


# Remember new tiles so they stay explored once the units wander off.
def record_seen(db, game, user_id, visible, ref_to_territory_id):
    rows = [
        (game["game_id"], user_id, ref_to_territory_id[ref], game["current_turn"])
        for ref in visible
        if ref in ref_to_territory_id
    ]
    if not rows:
        return
    db.executemany(
        "INSERT OR IGNORE INTO TerritorySeen (game_id, user_id, territory_id,"
        " first_seen_turn) VALUES (?, ?, ?, ?)",
        rows,
    )
    db.commit()


def state_for(ref, visible, explored):
    if ref in visible:
        return "visible"
    if ref in explored:
        return "explored"
    return "hidden"

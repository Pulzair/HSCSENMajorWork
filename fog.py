import units

CITY_VISION = 1


def vision_sources(db, game_id, user_id):
    sources = {}

    owned = db.execute(
        "SELECT map_territory_ref FROM Territory WHERE game_id = ? AND owner_id = ?",
        (game_id, user_id),
    ).fetchall()
    for row in owned:
        ref = row["map_territory_ref"]
        sources[ref] = max(sources.get(ref, 0), CITY_VISION)

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
        visible.add(origin)

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
                    if fog_modifiers.get(neighbour, 1.0) >= 1.0:
                        visible.add(neighbour)
            frontier = nxt

    return visible


def explored_refs(db, game_id, user_id):
    rows = db.execute(
        """SELECT t.map_territory_ref
             FROM TerritorySeen s
             JOIN Territory t ON t.territory_id = s.territory_id
            WHERE s.game_id = ? AND s.user_id = ?""",
        (game_id, user_id),
    ).fetchall()
    return {row["map_territory_ref"] for row in rows}


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

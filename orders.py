import improvements
import units

HOLD = "hold"


def _territories_by_ref(db, game_id):
    rows = db.execute(
        """SELECT territory_id, map_territory_ref, layer, terrain_type, owner_id,
                  has_city, natural_resource
             FROM Territory WHERE game_id = ?""",
        (game_id,),
    ).fetchall()
    return {row["map_territory_ref"]: row for row in rows}


def _units_by_ref(db, game_id):
    rows = db.execute(
        """SELECT u.unit_id, u.owner_id, u.unit_type, u.health, t.map_territory_ref
             FROM Unit u JOIN Territory t ON t.territory_id = u.territory_id
            WHERE u.game_id = ?""",
        (game_id,),
    ).fetchall()
    grouped = {}
    for row in rows:
        grouped.setdefault(row["map_territory_ref"], []).append(row)
    return grouped


def transition_refs(layout):
    refs = set()
    for x, y in layout["config"].get("transitions", []):
        for layer in ("land", "underground", "sky"):
            ref = layout["grid"][layer].get((x, y))
            if ref is not None:
                refs.add(ref)
    return refs


def legal_orders(db, game, user_id, layout, adjacency, visible):
    """Every order this player may legally give, keyed by unit_id."""
    by_ref = _territories_by_ref(db, game["game_id"])
    occupants = _units_by_ref(db, game["game_id"])
    crossings = transition_refs(layout)

    my_units = db.execute(
        """SELECT u.unit_id, u.unit_type, u.layer, t.map_territory_ref
             FROM Unit u JOIN Territory t ON t.territory_id = u.territory_id
            WHERE u.game_id = ? AND u.owner_id = ?
         ORDER BY u.unit_id""",
        (game["game_id"], user_id),
    ).fetchall()

    options = {}
    for unit in my_units:
        spec = units.get_unit(unit["unit_type"])
        if spec is None:
            continue
        here = unit["map_territory_ref"]
        choices = [(HOLD, "Hold position")]

        for ref in adjacency.get(here, ()):
            target = by_ref.get(ref)
            if target is None:
                continue
            if not units.can_occupy(
                unit["unit_type"], target["layer"], target["terrain_type"]
            ):
                continue

            spot = layout["territories"][ref]
            where = f"({spot['x']},{spot['y']})"

            if target["layer"] != unit["layer"]:
                if not units.can_transition(unit["unit_type"]):
                    continue
                if here not in crossings or ref not in crossings:
                    continue
                choices.append(
                    (f"layer_transition:{ref}", f"Cross to {target['layer']} {where}")
                )
                continue

            extra = ""
            if target["natural_resource"] and ref in visible:
                extra = f", {target['natural_resource']}"

            enemies = [u for u in occupants.get(ref, []) if u["owner_id"] != user_id]
            if enemies and ref in visible:
                choices.append(
                    (f"attack:{ref}", f"Attack {where} ({len(enemies)} defending)")
                )
            else:
                choices.append(
                    (f"move:{ref}", f"Move to {where} {target['terrain_type']}{extra}")
                )

        options[unit["unit_id"]] = choices

    return options


def held_resources(db, game_id, user_id):
    rows = db.execute(
        """SELECT DISTINCT natural_resource FROM Territory
            WHERE game_id = ? AND owner_id = ? AND natural_resource IS NOT NULL""",
        (game_id, user_id),
    ).fetchall()
    return {row["natural_resource"] for row in rows}


def production_sites(db, game_id, user_id):
    rows = db.execute(
        """SELECT territory_id, layer, terrain_type, has_city, improvement
             FROM Territory WHERE game_id = ? AND owner_id = ?""",
        (game_id, user_id),
    ).fetchall()
    return [
        row
        for row in rows
        if row["has_city"] or improvements.allows_production(row["improvement"])
    ]


def build_options(db, game, user_id):
    purse = db.execute(
        "SELECT resources FROM GamePlayer WHERE game_id = ? AND user_id = ?",
        (game["game_id"], user_id),
    ).fetchone()
    budget = purse["resources"] if purse else 0
    stock = held_resources(db, game["game_id"], user_id)

    per_site = {}
    for site in production_sites(db, game["game_id"], user_id):
        choices = [(HOLD, "Build nothing")]
        for key in units.buildable_in(site["layer"]):
            spec = units.get_unit(key)
            if not units.can_occupy(key, site["layer"], site["terrain_type"]):
                continue

            needs = spec.get("requires")
            label = f"{spec['name']} ({spec['cost']})"
            if needs and needs not in stock:
                choices.append(("", f"{label} - needs {needs}"))
                continue
            if spec["cost"] > budget:
                choices.append(("", f"{label} - too expensive"))
                continue
            choices.append((f"unit:{key}", label))
        per_site[site["territory_id"]] = choices
    return per_site, budget


def improvement_options(db, game, user_id):
    purse = db.execute(
        "SELECT resources FROM GamePlayer WHERE game_id = ? AND user_id = ?",
        (game["game_id"], user_id),
    ).fetchone()
    budget = purse["resources"] if purse else 0

    tiles = db.execute(
        """SELECT territory_id, layer, terrain_type, improvement, has_city,
                  resource_value
             FROM Territory
            WHERE game_id = ? AND owner_id = ? AND improvement IS NULL
              AND has_city = 0
         ORDER BY territory_id""",
        (game["game_id"], user_id),
    ).fetchall()

    per_tile = {}
    for tile in tiles:
        keys = improvements.options_for(tile["layer"], tile["terrain_type"])
        if not keys:
            continue
        choices = [(HOLD, "Leave undeveloped")]
        for key in keys:
            spec = improvements.get(key)
            label = f"{spec['name']} ({spec['cost']})"
            if spec["resource_bonus"]:
                label += f" +{spec['resource_bonus']}/turn"
            if spec["cost"] > budget:
                choices.append(("", f"{label} - too expensive"))
                continue
            choices.append((f"improvement:{key}", label))
        per_tile[tile["territory_id"]] = choices
    return per_tile


def clear_orders(db, game_id, user_id, turn):
    db.execute(
        "DELETE FROM Orders WHERE game_id = ? AND player_id = ? AND turn_number = ?",
        (game_id, user_id, turn),
    )


def save_orders(db, game, user_id, unit_choices, city_choices, improve_choices,
                layout, adjacency, visible):
    """Check and store one player's orders (FR15). Returns a list of problems."""
    problems = []
    legal = legal_orders(db, game, user_id, layout, adjacency, visible)
    buildable, budget = build_options(db, game, user_id)
    improvable = improvement_options(db, game, user_id)

    accepted = []
    for unit_id, token in unit_choices.items():
        if unit_id not in legal:
            problems.append("You tried to order a unit that is not yours.")
            continue
        allowed = {t for t, _label in legal[unit_id]}
        if token not in allowed:
            problems.append("That order is not legal for one of your units.")
            continue
        if token == HOLD:
            continue
        kind, _, ref = token.partition(":")
        accepted.append((kind, unit_id, int(ref)))

    spend = 0
    builds = []
    for territory_id, token in city_choices.items():
        if territory_id not in buildable:
            problems.append("You tried to build where you have no city or barracks.")
            continue
        allowed = {t for t, _label in buildable[territory_id] if t}
        if token not in allowed:
            problems.append("That unit cannot be built there.")
            continue
        if token == HOLD:
            continue
        _kind, _, unit_type = token.partition(":")
        spend += units.get_unit(unit_type)["cost"]
        builds.append((territory_id, token))

    for territory_id, token in improve_choices.items():
        if territory_id not in improvable:
            problems.append("You tried to develop a tile you do not hold.")
            continue
        allowed = {t for t, _label in improvable[territory_id] if t}
        if token not in allowed:
            problems.append("That improvement cannot be built there.")
            continue
        if token == HOLD:
            continue
        _kind, _, key = token.partition(":")
        spend += improvements.get(key)["cost"]
        builds.append((territory_id, token))

    if spend > budget:
        problems.append(f"That costs {spend} but you only have {budget} resources.")

    if problems:
        return problems

    turn = game["current_turn"]
    clear_orders(db, game["game_id"], user_id, turn)

    ref_to_id = {
        r["map_territory_ref"]: r["territory_id"]
        for r in db.execute(
            "SELECT territory_id, map_territory_ref FROM Territory WHERE game_id = ?",
            (game["game_id"],),
        )
    }
    for kind, unit_id, ref in accepted:
        source = db.execute(
            "SELECT territory_id FROM Unit WHERE unit_id = ?", (unit_id,)
        ).fetchone()
        db.execute(
            "INSERT INTO Orders (game_id, player_id, turn_number, order_type,"
            " unit_id, source_territory, target_territory)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                game["game_id"],
                user_id,
                turn,
                kind,
                unit_id,
                source["territory_id"],
                ref_to_id[ref],
            ),
        )

    for territory_id, token in builds:
        db.execute(
            "INSERT INTO Orders (game_id, player_id, turn_number, order_type,"
            " target_territory, detail) VALUES (?, ?, ?, 'build', ?, ?)",
            (game["game_id"], user_id, turn, territory_id, token),
        )

    db.execute(
        "UPDATE GamePlayer SET submitted_turn = ? WHERE game_id = ? AND user_id = ?",
        (turn, game["game_id"], user_id),
    )
    db.commit()
    return []


def my_orders(db, game, user_id):
    return db.execute(
        """SELECT o.*, u.unit_type
             FROM Orders o
        LEFT JOIN Unit u ON u.unit_id = o.unit_id
            WHERE o.game_id = ? AND o.player_id = ? AND o.turn_number = ?""",
        (game["game_id"], user_id, game["current_turn"]),
    ).fetchall()


def submission_status(db, game):
    rows = db.execute(
        """SELECT gp.user_id, u.username, gp.is_eliminated,
                  (gp.submitted_turn = ?) AS ready
             FROM GamePlayer gp JOIN User u ON u.user_id = gp.user_id
            WHERE gp.game_id = ? ORDER BY gp.gameplayer_id""",
        (game["current_turn"], game["game_id"]),
    ).fetchall()
    active = [r for r in rows if not r["is_eliminated"]]
    return {
        "players": rows,
        "ready": sum(1 for r in active if r["ready"]),
        "total": len(active),
        "all_in": all(r["ready"] for r in active) and bool(active),
    }

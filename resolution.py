import json
from datetime import datetime, timezone

import diplomacy
import improvements
import units

DEFAULT_VICTORY_SHARE = 0.5

TURN_TIMER_DEFAULTS = {
    "turn_seconds_base": 45,
    "turn_seconds_per_unit": 4,
    "turn_seconds_per_territory": 2,
    "turn_seconds_min": 30,
    "turn_seconds_max": 300,
}


def timer_settings(config):
    settings = dict(TURN_TIMER_DEFAULTS)
    for key in settings:
        if isinstance(config.get(key), (int, float)) and config[key] >= 0:
            settings[key] = config[key]
    return settings


def turn_seconds(db, game_id, config):
    settings = timer_settings(config)

    standing = db.execute(
        "SELECT COUNT(*) c FROM GamePlayer WHERE game_id = ? AND is_eliminated = 0",
        (game_id,),
    ).fetchone()["c"]
    if not standing:
        return settings["turn_seconds_min"]

    held = db.execute(
        """SELECT COUNT(*) c FROM Territory
            WHERE game_id = ? AND owner_id IS NOT NULL""",
        (game_id,),
    ).fetchone()["c"]
    alive = db.execute(
        "SELECT COUNT(*) c FROM Unit WHERE game_id = ?", (game_id,)
    ).fetchone()["c"]

    seconds = (
        settings["turn_seconds_base"]
        + (alive / standing) * settings["turn_seconds_per_unit"]
        + (held / standing) * settings["turn_seconds_per_territory"]
    )
    seconds = max(settings["turn_seconds_min"], min(settings["turn_seconds_max"], seconds))
    return int(round(seconds))


def set_deadline(db, game_id, config):
    seconds = turn_seconds(db, game_id, config)
    db.execute(
        "UPDATE Game SET turn_deadline = datetime('now', ?) WHERE game_id = ?",
        (f"+{seconds} seconds", game_id),
    )
    return seconds


def seconds_left(game):
    if game["turn_deadline"] is None:
        return None
    deadline = datetime.strptime(game["turn_deadline"], "%Y-%m-%d %H:%M:%S")
    deadline = deadline.replace(tzinfo=timezone.utc)
    remaining = (deadline - datetime.now(timezone.utc)).total_seconds()
    return max(0, int(remaining))


def _apply_disasters(db, game, log):
    return None


def _validate(db, game, log):
    pending = db.execute(
        """SELECT o.*, u.owner_id, u.unit_type, u.territory_id AS unit_at
             FROM Orders o
        LEFT JOIN Unit u ON u.unit_id = o.unit_id
            WHERE o.game_id = ? AND o.turn_number = ? AND o.status = 'pending'""",
        (game["game_id"], game["current_turn"]),
    ).fetchall()

    valid = []
    for order in pending:
        if order["order_type"] == "build":
            valid.append(order)
            continue

        if order["unit_id"] is None or order["owner_id"] != order["player_id"]:
            log.append("An order was invalidated: the unit no longer exists.")
            db.execute(
                "UPDATE Orders SET status = 'cancelled' WHERE order_id = ?",
                (order["order_id"],),
            )
            continue
        if order["unit_at"] != order["source_territory"]:
            log.append("An order was invalidated: the unit had already moved.")
            db.execute(
                "UPDATE Orders SET status = 'cancelled' WHERE order_id = ?",
                (order["order_id"],),
            )
            continue
        valid.append(order)
    return valid


def _charge(db, game, player_id, cost):
    purse = db.execute(
        "SELECT resources FROM GamePlayer WHERE game_id = ? AND user_id = ?",
        (game["game_id"], player_id),
    ).fetchone()
    if purse is None or purse["resources"] < cost:
        return False
    db.execute(
        "UPDATE GamePlayer SET resources = resources - ?"
        " WHERE game_id = ? AND user_id = ?",
        (cost, game["game_id"], player_id),
    )
    return True


def _apply_builds(db, game, orders, log):
    for order in orders:
        if order["order_type"] != "build":
            continue

        kind, _, key = (order["detail"] or "").partition(":")
        territory = db.execute(
            "SELECT territory_id, layer, owner_id, terrain_type, improvement,"
            " resource_value FROM Territory WHERE territory_id = ?",
            (order["target_territory"],),
        ).fetchone()

        if territory is None or territory["owner_id"] != order["player_id"]:
            log.append("A build order was invalidated: the tile was lost.")
            continue

        if kind == "unit":
            spec = units.get_unit(key)
            if spec is None:
                continue
            if not _charge(db, game, order["player_id"], spec["cost"]):
                log.append(f"A {spec['name']} was not built: not enough resources.")
                continue
            db.execute(
                "INSERT INTO Unit (game_id, owner_id, territory_id, unit_type, attack,"
                " defence, health, layer) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    game["game_id"],
                    order["player_id"],
                    territory["territory_id"],
                    key,
                    spec["attack"],
                    spec["defence"],
                    spec["health"],
                    territory["layer"],
                ),
            )
            log.append(f"A {spec['name']} was built.")

        elif kind == "improvement":
            spec = improvements.get(key)
            if spec is None or territory["improvement"] is not None:
                continue
            if not _charge(db, game, order["player_id"], spec["cost"]):
                log.append(f"A {spec['name']} was not built: not enough resources.")
                continue
            db.execute(
                "UPDATE Territory SET improvement = ?, resource_value = resource_value + ?"
                " WHERE territory_id = ?",
                (key, spec["resource_bonus"], territory["territory_id"]),
            )
            log.append(f"A {spec['name']} was completed.")


def _apply_movement(db, game, orders):
    destinations = {}
    for order in orders:
        if order["order_type"] not in ("move", "attack", "layer_transition"):
            continue
        target = db.execute(
            "SELECT territory_id, layer FROM Territory WHERE territory_id = ?",
            (order["target_territory"],),
        ).fetchone()
        if target is None:
            continue
        db.execute(
            "UPDATE Unit SET territory_id = ?, layer = ? WHERE unit_id = ?",
            (target["territory_id"], target["layer"], order["unit_id"]),
        )
        destinations[order["unit_id"]] = target["territory_id"]
    return destinations


def _resolve_combat(db, game, log):
    """Fight anywhere two or more players ended up on the same tile (FR17)."""
    contested = db.execute(
        """SELECT territory_id, COUNT(DISTINCT owner_id) AS sides
             FROM Unit WHERE game_id = ?
         GROUP BY territory_id HAVING sides > 1""",
        (game["game_id"],),
    ).fetchall()

    for spot in contested:
        territory = db.execute(
            "SELECT territory_id, owner_id, map_territory_ref FROM Territory"
            " WHERE territory_id = ?",
            (spot["territory_id"],),
        ).fetchone()
        garrison = db.execute(
            "SELECT unit_id, owner_id, unit_type, attack, defence, health FROM Unit"
            " WHERE game_id = ? AND territory_id = ?",
            (game["game_id"], spot["territory_id"]),
        ).fetchall()

        sides = {}
        for unit in garrison:
            sides.setdefault(unit["owner_id"], []).append(unit)

        holder = territory["owner_id"]

        if len(sides) > 1:
            friendly = [
                owner
                for owner in sides
                if all(
                    owner == other
                    or diplomacy.are_allied(db, game["game_id"], owner, other)
                    for other in sides
                )
            ]
            if len(friendly) == len(sides):
                continue
        strength = {}
        for owner, group in sides.items():
            defending = owner == holder
            strength[owner] = sum(
                u["defence"] if defending else u["attack"] for u in group
            )

        winner = max(sides, key=lambda o: (strength[o], o == holder, -o))
        incoming = sum(strength[o] for o in sides if o != winner)

        for owner, group in sides.items():
            if owner == winner:
                continue
            for unit in group:
                db.execute("DELETE FROM Unit WHERE unit_id = ?", (unit["unit_id"],))

        survivors = sides[winner]
        share = incoming // max(len(survivors), 1)
        for unit in survivors:
            left = unit["health"] - share
            if left <= 0:
                db.execute("DELETE FROM Unit WHERE unit_id = ?", (unit["unit_id"],))
            else:
                db.execute(
                    "UPDATE Unit SET health = ? WHERE unit_id = ?",
                    (left, unit["unit_id"]),
                )

        still_there = db.execute(
            "SELECT COUNT(*) c FROM Unit WHERE game_id = ? AND territory_id = ?",
            (game["game_id"], spot["territory_id"]),
        ).fetchone()["c"]
        if still_there and winner != holder:
            db.execute(
                "UPDATE Territory SET owner_id = ? WHERE territory_id = ?",
                (winner, spot["territory_id"]),
            )
            log.append("A territory changed hands after a battle.")
        elif not still_there:
            log.append("A battle wiped out both sides.")


def _claim_empty(db, game):
    rows = db.execute(
        """SELECT t.territory_id, MIN(u.owner_id) AS claimant,
                  COUNT(DISTINCT u.owner_id) AS sides
             FROM Territory t JOIN Unit u ON u.territory_id = t.territory_id
            WHERE t.game_id = ? AND t.owner_id IS NULL
         GROUP BY t.territory_id HAVING sides = 1""",
        (game["game_id"],),
    ).fetchall()
    for row in rows:
        db.execute(
            "UPDATE Territory SET owner_id = ? WHERE territory_id = ?",
            (row["claimant"], row["territory_id"]),
        )


def _pay_income(db, game, log):
    pool = db.execute(
        "SELECT global_resources FROM Game WHERE game_id = ?", (game["game_id"],)
    ).fetchone()["global_resources"]

    earners = db.execute(
        """SELECT gp.user_id, COALESCE(SUM(t.resource_value), 0) AS income
             FROM GamePlayer gp
        LEFT JOIN Territory t
               ON t.game_id = gp.game_id AND t.owner_id = gp.user_id
            WHERE gp.game_id = ? AND gp.is_eliminated = 0
         GROUP BY gp.user_id ORDER BY gp.user_id""",
        (game["game_id"],),
    ).fetchall()

    for row in earners:
        if pool <= 0:
            break
        paid = min(row["income"], pool)
        if paid <= 0:
            continue
        db.execute(
            "UPDATE GamePlayer SET resources = resources + ?"
            " WHERE game_id = ? AND user_id = ?",
            (paid, game["game_id"], row["user_id"]),
        )
        pool -= paid

    db.execute(
        "UPDATE Game SET global_resources = ? WHERE game_id = ?",
        (pool, game["game_id"]),
    )
    if pool <= 0:
        log.append("The world's resources are exhausted. Income has stopped.")


def _check_elimination(db, game, log):
    players = db.execute(
        "SELECT user_id FROM GamePlayer WHERE game_id = ? AND is_eliminated = 0",
        (game["game_id"],),
    ).fetchall()
    for player in players:
        held = db.execute(
            "SELECT COUNT(*) c FROM Territory WHERE game_id = ? AND owner_id = ?",
            (game["game_id"], player["user_id"]),
        ).fetchone()["c"]
        alive = db.execute(
            "SELECT COUNT(*) c FROM Unit WHERE game_id = ? AND owner_id = ?",
            (game["game_id"], player["user_id"]),
        ).fetchone()["c"]
        if held == 0 and alive == 0:
            db.execute(
                "UPDATE GamePlayer SET is_eliminated = 1"
                " WHERE game_id = ? AND user_id = ?",
                (game["game_id"], player["user_id"]),
            )
            log.append("A player has been eliminated.")


def _check_victory(db, game, victory_share, log):
    """Win by conquest or by owning enough of the map (FR25)."""
    standing = db.execute(
        """SELECT gp.user_id, u.username FROM GamePlayer gp
             JOIN User u ON u.user_id = gp.user_id
            WHERE gp.game_id = ? AND gp.is_eliminated = 0""",
        (game["game_id"],),
    ).fetchall()

    winner = None
    if len(standing) == 1:
        winner = standing[0]
        log.append(f"{winner['username']} is the last player standing.")
    else:
        total = db.execute(
            "SELECT COUNT(*) c FROM Territory WHERE game_id = ?", (game["game_id"],)
        ).fetchone()["c"]
        for player in standing:
            held = db.execute(
                "SELECT COUNT(*) c FROM Territory WHERE game_id = ? AND owner_id = ?",
                (game["game_id"], player["user_id"]),
            ).fetchone()["c"]
            if total and held / total >= victory_share:
                winner = player
                log.append(f"{player['username']} controls {held} of {total} territories.")
                break

    if winner is None:
        return None

    db.execute(
        "UPDATE Game SET status = 'complete', winner_id = ?,"
        " completed_at = datetime('now') WHERE game_id = ?",
        (winner["user_id"], game["game_id"]),
    )
    return winner["user_id"]


def resolve_turn(db, game, map_row):
    """Reveal and apply everyone's orders at once (FR16). Hands back a log."""
    log = []
    config = json.loads(map_row["layout_json"]) if map_row else {}
    victory_share = config.get("victory_territory_share", DEFAULT_VICTORY_SHARE)

    _apply_disasters(db, game, log)
    valid = _validate(db, game, log)
    diplomacy.detect_breaches(db, game, valid, log)
    _apply_builds(db, game, valid, log)
    _apply_movement(db, game, valid)
    _resolve_combat(db, game, log)
    _claim_empty(db, game)
    _pay_income(db, game, log)
    _check_elimination(db, game, log)
    winner_id = _check_victory(db, game, victory_share, log)

    db.execute(
        "UPDATE Orders SET status = 'resolved'"
        " WHERE game_id = ? AND turn_number = ? AND status = 'pending'",
        (game["game_id"], game["current_turn"]),
    )
    if winner_id is None:
        db.execute(
            "UPDATE Game SET current_turn = current_turn + 1 WHERE game_id = ?",
            (game["game_id"],),
        )
        db.execute(
            "UPDATE GamePlayer SET submitted_turn = NULL WHERE game_id = ?",
            (game["game_id"],),
        )
        diplomacy.advance(db, game, log)
        set_deadline(db, game["game_id"], config)
    else:
        db.execute(
            "UPDATE Game SET turn_deadline = NULL WHERE game_id = ?",
            (game["game_id"],),
        )
    db.commit()

    log.append(f"Turn {game['current_turn']} resolved.")
    return {"log": log, "winner_id": winner_id}

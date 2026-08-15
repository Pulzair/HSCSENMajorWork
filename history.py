DETAIL_LIMIT = 3


def summary(db, user_id):
    row = db.execute(
        """SELECT COUNT(*) AS played,
                  SUM(CASE WHEN g.winner_id = ? THEN 1 ELSE 0 END) AS won,
                  SUM(g.current_turn) AS turns
             FROM GamePlayer gp JOIN Game g ON g.game_id = gp.game_id
            WHERE gp.user_id = ? AND g.status = 'complete'""",
        (user_id, user_id),
    ).fetchone()

    played = row["played"] or 0
    won = row["won"] or 0
    turns = row["turns"] or 0

    live = db.execute(
        """SELECT COUNT(*) AS c
             FROM GamePlayer gp JOIN Game g ON g.game_id = gp.game_id
            WHERE gp.user_id = ? AND g.status = 'active'""",
        (user_id,),
    ).fetchone()["c"]

    reputation = db.execute(
        "SELECT reputation FROM User WHERE user_id = ?", (user_id,)
    ).fetchone()["reputation"]

    return {
        "played": played,
        "won": won,
        "lost": played - won,
        "win_rate": round((won / played) * 100) if played else 0,
        "avg_turns": round(turns / played) if played else 0,
        "in_progress": live,
        "reputation": reputation,
    }


def recent(db, user_id, limit=DETAIL_LIMIT):
    games = db.execute(
        """SELECT g.game_id, g.join_code, g.current_turn, g.completed_at,
                  g.winner_id, m.name AS map_name, w.username AS winner_name
             FROM GamePlayer gp
             JOIN Game g ON g.game_id = gp.game_id
        LEFT JOIN Map m ON m.map_id = g.map_id
        LEFT JOIN User w ON w.user_id = g.winner_id
            WHERE gp.user_id = ? AND g.status = 'complete'
         ORDER BY g.completed_at DESC, g.game_id DESC
            LIMIT ?""",
        (user_id, limit),
    ).fetchall()

    out = []
    for game in games:
        standings = db.execute(
            """SELECT u.user_id, u.username, gp.player_colour, gp.is_eliminated,
                      gp.resources,
                      (SELECT COUNT(*) FROM Territory t
                        WHERE t.game_id = gp.game_id AND t.owner_id = gp.user_id) AS territories,
                      (SELECT COUNT(*) FROM Unit un
                        WHERE un.game_id = gp.game_id AND un.owner_id = gp.user_id) AS units
                 FROM GamePlayer gp JOIN User u ON u.user_id = gp.user_id
                WHERE gp.game_id = ?
             ORDER BY territories DESC, units DESC, gp.resources DESC""",
            (game["game_id"],),
        ).fetchall()

        deals = db.execute(
            """SELECT COUNT(*) AS signed,
                      SUM(CASE WHEN status = 'breached' THEN 1 ELSE 0 END) AS broken
                 FROM DiplomacyAgreement
                WHERE game_id = ? AND (proposer_id = ? OR recipient_id = ?)
                  AND status IN ('active', 'expired', 'breached')""",
            (game["game_id"], user_id, user_id),
        ).fetchone()

        item = dict(game)
        item["won"] = game["winner_id"] == user_id
        item["standings"] = [dict(s) for s in standings]
        item["deals_signed"] = deals["signed"] or 0
        item["deals_broken"] = deals["broken"] or 0
        for place, row in enumerate(item["standings"], 1):
            if row["user_id"] == user_id:
                item["placing"] = place
                break
        else:
            item["placing"] = None
        out.append(item)

    return out

import json

KINDS = ("non_aggression", "alliance", "trade")

KIND_NAMES = {
    "non_aggression": "Non-aggression pact",
    "alliance": "Alliance",
    "trade": "Resource trade",
}

BASE_COST = {
    "non_aggression": 20,
    "alliance": 40,
    "trade": 0,
}

BREACH_PENALTY = {
    "non_aggression": 15,
    "alliance": 25,
    "trade": 10,
}

MIN_TURNS = 2
MAX_TURNS = 20


def cost_modifier(reputation):
    return round(2.0 - (max(0, min(100, reputation)) / 100.0), 2)


def agreement_cost(kind, reputation):
    return int(round(BASE_COST.get(kind, 0) * cost_modifier(reputation)))


def _purse(db, game_id, user_id):
    row = db.execute(
        "SELECT resources FROM GamePlayer WHERE game_id = ? AND user_id = ?",
        (game_id, user_id),
    ).fetchone()
    return row["resources"] if row else 0


def _reputation(db, user_id):
    row = db.execute("SELECT reputation FROM User WHERE user_id = ?", (user_id,)).fetchone()
    return row["reputation"] if row else 50


def standing_between(db, game_id, a, b):
    return db.execute(
        """SELECT * FROM DiplomacyAgreement
            WHERE game_id = ? AND status = 'active'
              AND agreement_type IN ('non_aggression', 'alliance')
              AND ((proposer_id = ? AND recipient_id = ?)
                OR (proposer_id = ? AND recipient_id = ?))
         ORDER BY CASE agreement_type WHEN 'alliance' THEN 0 ELSE 1 END
            LIMIT 1""",
        (game_id, a, b, b, a),
    ).fetchone()


def are_allied(db, game_id, a, b):
    pact = standing_between(db, game_id, a, b)
    return pact is not None and pact["agreement_type"] == "alliance"


def propose(db, game, proposer_id, recipient_id, kind, turns, offer=0, request=0):
    problems = []
    game_id = game["game_id"]

    if kind not in KINDS:
        return ["That is not a kind of agreement."]
    if proposer_id == recipient_id:
        return ["You cannot make an agreement with yourself."]

    other = db.execute(
        "SELECT * FROM GamePlayer WHERE game_id = ? AND user_id = ?",
        (game_id, recipient_id),
    ).fetchone()
    if other is None:
        return ["That player is not in this game."]
    if other["is_eliminated"]:
        return ["That player is out of the game."]

    if kind == "trade":
        if offer <= 0 and request <= 0:
            problems.append("A trade needs resources on at least one side.")
        if offer < 0 or request < 0:
            problems.append("Trade amounts cannot be negative.")
        if offer > _purse(db, game_id, proposer_id):
            problems.append("You cannot offer more resources than you hold.")
        turns = 0
    else:
        if turns < MIN_TURNS or turns > MAX_TURNS:
            problems.append(f"Duration must be between {MIN_TURNS} and {MAX_TURNS} turns.")
        if standing_between(db, game_id, proposer_id, recipient_id):
            problems.append("You already have a pact with that player.")

    pending = db.execute(
        """SELECT 1 FROM DiplomacyAgreement
            WHERE game_id = ? AND status = 'proposed' AND agreement_type = ?
              AND proposer_id = ? AND recipient_id = ?""",
        (game_id, kind, proposer_id, recipient_id),
    ).fetchone()
    if pending:
        problems.append("You have already offered that player this deal.")

    if problems:
        return problems

    terms = json.dumps({"offer": int(offer), "request": int(request)})
    db.execute(
        """INSERT INTO DiplomacyAgreement
               (game_id, proposer_id, recipient_id, agreement_type, status,
                turns_remaining, terms_json, created_turn)
           VALUES (?, ?, ?, ?, 'proposed', ?, ?, ?)""",
        (game_id, proposer_id, recipient_id, kind, turns, terms, game["current_turn"]),
    )
    db.commit()
    return []


def respond(db, game, agreement_id, user_id, accept):
    game_id = game["game_id"]
    deal = db.execute(
        """SELECT * FROM DiplomacyAgreement
            WHERE agreement_id = ? AND game_id = ? AND status = 'proposed'""",
        (agreement_id, game_id),
    ).fetchone()
    if deal is None:
        return ["That offer is no longer on the table."]
    if deal["recipient_id"] != user_id:
        return ["That offer was not made to you."]

    if not accept:
        db.execute(
            "UPDATE DiplomacyAgreement SET status = 'declined' WHERE agreement_id = ?",
            (agreement_id,),
        )
        db.commit()
        return []

    terms = json.loads(deal["terms_json"] or "{}")
    offer = int(terms.get("offer", 0))
    request = int(terms.get("request", 0))

    if deal["agreement_type"] == "trade":
        if _purse(db, game_id, deal["proposer_id"]) < offer:
            return ["They can no longer afford their side of the trade."]
        if _purse(db, game_id, user_id) < request:
            return ["You cannot afford your side of the trade."]

        db.execute(
            "UPDATE GamePlayer SET resources = resources - ? + ?"
            " WHERE game_id = ? AND user_id = ?",
            (offer, request, game_id, deal["proposer_id"]),
        )
        db.execute(
            "UPDATE GamePlayer SET resources = resources - ? + ?"
            " WHERE game_id = ? AND user_id = ?",
            (request, offer, game_id, user_id),
        )
    else:
        price = agreement_cost(deal["agreement_type"], _reputation(db, deal["proposer_id"]))
        if _purse(db, game_id, deal["proposer_id"]) < price:
            return ["They can no longer afford to sign that agreement."]
        db.execute(
            "UPDATE GamePlayer SET resources = resources - ?"
            " WHERE game_id = ? AND user_id = ?",
            (price, game_id, deal["proposer_id"]),
        )

    db.execute(
        "UPDATE DiplomacyAgreement SET status = 'active' WHERE agreement_id = ?",
        (agreement_id,),
    )
    db.commit()
    return []


def cancel(db, game, agreement_id, user_id):
    deal = db.execute(
        """SELECT * FROM DiplomacyAgreement
            WHERE agreement_id = ? AND game_id = ? AND status = 'proposed'""",
        (agreement_id, game["game_id"]),
    ).fetchone()
    if deal is None or deal["proposer_id"] != user_id:
        return ["That offer cannot be withdrawn."]
    db.execute(
        "UPDATE DiplomacyAgreement SET status = 'declined' WHERE agreement_id = ?",
        (agreement_id,),
    )
    db.commit()
    return []


def breach(db, game, deal, breacher_id, log):
    kind = deal["agreement_type"]
    penalty = BREACH_PENALTY.get(kind, 10)

    db.execute(
        """UPDATE DiplomacyAgreement
              SET status = 'breached', breached_by = ?, breach_type = ?, breached_turn = ?
            WHERE agreement_id = ?""",
        (breacher_id, kind, game["current_turn"], deal["agreement_id"]),
    )
    db.execute(
        "UPDATE User SET reputation = MAX(0, reputation - ?) WHERE user_id = ?",
        (penalty, breacher_id),
    )

    names = _names(db, [breacher_id, _partner(deal, breacher_id)])
    log.append(
        f"{names[breacher_id]} broke their {KIND_NAMES[kind].lower()} with "
        f"{names[_partner(deal, breacher_id)]} and lost {penalty} reputation."
    )


def _partner(deal, user_id):
    return deal["recipient_id"] if deal["proposer_id"] == user_id else deal["proposer_id"]


def _names(db, user_ids):
    out = {}
    for uid in set(user_ids):
        row = db.execute("SELECT username FROM User WHERE user_id = ?", (uid,)).fetchone()
        out[uid] = row["username"] if row else "A player"
    return out


def detect_breaches(db, game, valid_orders, log):
    for order in valid_orders:
        if order["order_type"] != "attack" or not order["target_territory"]:
            continue
        target = db.execute(
            "SELECT owner_id FROM Territory WHERE territory_id = ?",
            (order["target_territory"],),
        ).fetchone()
        if target is None or target["owner_id"] is None:
            continue
        if target["owner_id"] == order["player_id"]:
            continue

        pact = standing_between(db, game["game_id"], order["player_id"], target["owner_id"])
        if pact is not None:
            breach(db, game, pact, order["player_id"], log)


def advance(db, game, log):
    live = db.execute(
        "SELECT * FROM DiplomacyAgreement WHERE game_id = ? AND status = 'active'",
        (game["game_id"],),
    ).fetchall()

    for deal in live:
        if deal["turns_remaining"] <= 0:
            db.execute(
                "UPDATE DiplomacyAgreement SET status = 'expired' WHERE agreement_id = ?",
                (deal["agreement_id"],),
            )
            if deal["agreement_type"] != "trade":
                names = _names(db, [deal["proposer_id"], deal["recipient_id"]])
                log.append(
                    f"The {KIND_NAMES[deal['agreement_type']].lower()} between "
                    f"{names[deal['proposer_id']]} and {names[deal['recipient_id']]} has expired."
                )
            continue

        db.execute(
            "UPDATE DiplomacyAgreement SET turns_remaining = turns_remaining - 1"
            " WHERE agreement_id = ?",
            (deal["agreement_id"],),
        )

    db.execute(
        """UPDATE DiplomacyAgreement SET status = 'declined'
            WHERE game_id = ? AND status = 'proposed' AND created_turn < ?""",
        (game["game_id"], game["current_turn"]),
    )


def board(db, game, user_id):
    game_id = game["game_id"]
    rows = db.execute(
        """SELECT d.*, p.username AS proposer_name, r.username AS recipient_name
             FROM DiplomacyAgreement d
             JOIN User p ON p.user_id = d.proposer_id
             JOIN User r ON r.user_id = d.recipient_id
            WHERE d.game_id = ? AND (d.proposer_id = ? OR d.recipient_id = ?)
         ORDER BY d.agreement_id DESC""",
        (game_id, user_id, user_id),
    ).fetchall()

    incoming, outgoing, active, history = [], [], [], []
    for row in rows:
        item = dict(row)
        item["terms"] = json.loads(row["terms_json"] or "{}")
        item["kind_name"] = KIND_NAMES.get(row["agreement_type"], row["agreement_type"])
        item["other_id"] = _partner(row, user_id)
        item["other_name"] = (
            row["recipient_name"] if row["proposer_id"] == user_id else row["proposer_name"]
        )
        if row["status"] == "proposed":
            (incoming if row["recipient_id"] == user_id else outgoing).append(item)
        elif row["status"] == "active":
            active.append(item)
        else:
            history.append(item)

    partners = db.execute(
        """SELECT gp.user_id, u.username, u.reputation
             FROM GamePlayer gp JOIN User u ON u.user_id = gp.user_id
            WHERE gp.game_id = ? AND gp.user_id <> ? AND gp.is_eliminated = 0
         ORDER BY u.username""",
        (game_id, user_id),
    ).fetchall()

    reputation = _reputation(db, user_id)
    return {
        "incoming": incoming,
        "outgoing": outgoing,
        "active": active,
        "history": history[:8],
        "partners": [dict(p) for p in partners],
        "reputation": reputation,
        "cost_modifier": cost_modifier(reputation),
        "costs": {k: agreement_cost(k, reputation) for k in KINDS},
        "min_turns": MIN_TURNS,
        "max_turns": MAX_TURNS,
    }

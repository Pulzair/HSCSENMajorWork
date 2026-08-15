
DROP TABLE IF EXISTS DisasterTerritory;
DROP TABLE IF EXISTS DisasterEvent;
DROP TABLE IF EXISTS DiplomacyAgreement;
DROP TABLE IF EXISTS Orders;
DROP TABLE IF EXISTS TerritorySeen;
DROP TABLE IF EXISTS Unit;
DROP TABLE IF EXISTS Territory;
DROP TABLE IF EXISTS GamePlayer;
DROP TABLE IF EXISTS Game;
DROP TABLE IF EXISTS Map;
DROP TABLE IF EXISTS User;

CREATE TABLE User (
    user_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    username       TEXT    NOT NULL UNIQUE
                          CHECK (length(username) BETWEEN 3 AND 32),
    email          TEXT    NOT NULL UNIQUE
                          CHECK (length(email) <= 254),
    password_hash  TEXT    NOT NULL,
    created_at     TEXT    NOT NULL DEFAULT (datetime('now')),
    reputation     INTEGER NOT NULL DEFAULT 50
                          CHECK (reputation BETWEEN 0 AND 100),
    is_admin       INTEGER NOT NULL DEFAULT 0
                          CHECK (is_admin IN (0, 1))
);

CREATE TABLE Map (
    map_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT    NOT NULL UNIQUE,
    description  TEXT,
    min_players  INTEGER NOT NULL DEFAULT 2
                         CHECK (min_players >= 2),
    max_players  INTEGER NOT NULL DEFAULT 6
                         CHECK (max_players BETWEEN min_players AND 6),
    layout_json  TEXT    NOT NULL,
    created_at   TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE Game (
    game_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    join_code        TEXT    NOT NULL UNIQUE
                             CHECK (length(join_code) = 6),
    map_id           INTEGER REFERENCES Map(map_id),
    status           TEXT    NOT NULL DEFAULT 'lobby'
                             CHECK (status IN ('lobby', 'active', 'complete')),
    current_turn     INTEGER NOT NULL DEFAULT 1
                             CHECK (current_turn >= 1),
    winner_id        INTEGER REFERENCES User(user_id) ON DELETE SET NULL,
    created_at       TEXT    NOT NULL DEFAULT (datetime('now')),
    completed_at     TEXT,
    global_resources INTEGER NOT NULL DEFAULT 0
                             CHECK (global_resources >= 0)
);

CREATE TABLE GamePlayer (
    gameplayer_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id        INTEGER NOT NULL REFERENCES Game(game_id) ON DELETE CASCADE,
    user_id        INTEGER NOT NULL REFERENCES User(user_id) ON DELETE CASCADE,
    player_colour  TEXT    NOT NULL
                          CHECK (length(player_colour) = 7
                                 AND substr(player_colour, 1, 1) = '#'),
    resources      INTEGER NOT NULL DEFAULT 0
                          CHECK (resources >= 0),
    is_host        INTEGER NOT NULL DEFAULT 0
                          CHECK (is_host IN (0, 1)),
    is_eliminated  INTEGER NOT NULL DEFAULT 0
                          CHECK (is_eliminated IN (0, 1)),
    submitted_turn INTEGER,
    UNIQUE (game_id, user_id),
    UNIQUE (game_id, player_colour)
);

CREATE UNIQUE INDEX idx_gameplayer_one_host
    ON GamePlayer (game_id) WHERE is_host = 1;
CREATE INDEX idx_gameplayer_game ON GamePlayer (game_id);
CREATE INDEX idx_gameplayer_user ON GamePlayer (user_id);

CREATE TABLE Territory (
    territory_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id           INTEGER NOT NULL REFERENCES Game(game_id) ON DELETE CASCADE,
    map_territory_ref INTEGER NOT NULL,
    layer             TEXT    NOT NULL
                              CHECK (layer IN ('land', 'underground', 'sky')),
    owner_id          INTEGER REFERENCES User(user_id) ON DELETE SET NULL,
    resource_value    INTEGER NOT NULL DEFAULT 0
                              CHECK (resource_value >= 0),
    terrain_type      TEXT    NOT NULL DEFAULT 'plains'
                              CHECK (terrain_type IN ('plains', 'mountain', 'water', 'destroyed')),
    has_city          INTEGER NOT NULL DEFAULT 0
                              CHECK (has_city IN (0, 1)),
    improvement       TEXT,
    natural_resource  TEXT,
    fog_modifier      REAL    NOT NULL DEFAULT 1.0
                              CHECK (fog_modifier BETWEEN 0.0 AND 1.0)
);

CREATE INDEX idx_territory_game ON Territory (game_id);
CREATE INDEX idx_territory_owner ON Territory (owner_id);

CREATE TABLE TerritorySeen (
    game_id      INTEGER NOT NULL REFERENCES Game(game_id) ON DELETE CASCADE,
    user_id      INTEGER NOT NULL REFERENCES User(user_id) ON DELETE CASCADE,
    territory_id INTEGER NOT NULL REFERENCES Territory(territory_id) ON DELETE CASCADE,
    first_seen_turn INTEGER NOT NULL CHECK (first_seen_turn >= 1),
    PRIMARY KEY (game_id, user_id, territory_id)
);

CREATE INDEX idx_seen_player ON TerritorySeen (game_id, user_id);

CREATE TABLE Unit (
    unit_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id       INTEGER NOT NULL REFERENCES Game(game_id) ON DELETE CASCADE,
    owner_id      INTEGER NOT NULL REFERENCES User(user_id) ON DELETE CASCADE,
    territory_id  INTEGER NOT NULL REFERENCES Territory(territory_id) ON DELETE CASCADE,
    unit_type     TEXT    NOT NULL,
    attack        INTEGER NOT NULL CHECK (attack BETWEEN 1 AND 20),
    defence       INTEGER NOT NULL CHECK (defence BETWEEN 1 AND 20),
    health        INTEGER NOT NULL CHECK (health BETWEEN 1 AND 100),
    layer         TEXT    NOT NULL
                          CHECK (layer IN ('land', 'underground', 'sky'))
);

CREATE INDEX idx_unit_game ON Unit (game_id);
CREATE INDEX idx_unit_owner ON Unit (owner_id);
CREATE INDEX idx_unit_territory ON Unit (territory_id);

CREATE TABLE Orders (
    order_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id          INTEGER NOT NULL REFERENCES Game(game_id) ON DELETE CASCADE,
    player_id        INTEGER NOT NULL REFERENCES User(user_id) ON DELETE CASCADE,
    turn_number      INTEGER NOT NULL CHECK (turn_number >= 1),
    order_type       TEXT    NOT NULL
                             CHECK (order_type IN ('move', 'attack', 'build', 'layer_transition')),
    unit_id          INTEGER REFERENCES Unit(unit_id) ON DELETE CASCADE,
    source_territory INTEGER REFERENCES Territory(territory_id) ON DELETE CASCADE,
    target_territory INTEGER REFERENCES Territory(territory_id) ON DELETE CASCADE,
    detail           TEXT,
    status           TEXT    NOT NULL DEFAULT 'pending'
                             CHECK (status IN ('pending', 'resolved', 'cancelled')),
    submitted_at     TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_orders_game_turn ON Orders (game_id, turn_number);
CREATE INDEX idx_orders_player ON Orders (player_id);

CREATE TABLE DiplomacyAgreement (
    agreement_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id         INTEGER NOT NULL REFERENCES Game(game_id) ON DELETE CASCADE,
    proposer_id     INTEGER NOT NULL REFERENCES User(user_id) ON DELETE CASCADE,
    recipient_id    INTEGER NOT NULL REFERENCES User(user_id) ON DELETE CASCADE,
    agreement_type  TEXT    NOT NULL
                            CHECK (agreement_type IN ('non_aggression', 'alliance', 'trade')),
    status          TEXT    NOT NULL DEFAULT 'proposed'
                            CHECK (status IN ('proposed', 'active', 'declined', 'expired', 'breached')),
    turns_remaining INTEGER NOT NULL DEFAULT 0
                            CHECK (turns_remaining >= 0),
    terms_json      TEXT,
    breached_by     INTEGER REFERENCES User(user_id) ON DELETE SET NULL,
    breach_type     TEXT,
    breached_turn   INTEGER,
    created_turn    INTEGER NOT NULL DEFAULT 1
                            CHECK (created_turn >= 1),
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    CHECK (proposer_id <> recipient_id)
);

CREATE INDEX idx_diplomacy_game ON DiplomacyAgreement (game_id);
CREATE INDEX idx_diplomacy_proposer ON DiplomacyAgreement (proposer_id);
CREATE INDEX idx_diplomacy_recipient ON DiplomacyAgreement (recipient_id);

CREATE TABLE DisasterEvent (
    disaster_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id        INTEGER NOT NULL REFERENCES Game(game_id) ON DELETE CASCADE,
    turn_number    INTEGER NOT NULL CHECK (turn_number >= 1),
    disaster_type  TEXT    NOT NULL,
    triggered_at   TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_disaster_game_turn ON DisasterEvent (game_id, turn_number);

CREATE TABLE DisasterTerritory (
    disaster_id   INTEGER NOT NULL REFERENCES DisasterEvent(disaster_id) ON DELETE CASCADE,
    territory_id  INTEGER NOT NULL REFERENCES Territory(territory_id) ON DELETE CASCADE,
    PRIMARY KEY (disaster_id, territory_id)
);

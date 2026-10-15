-- name: create
CREATE TABLE IF NOT EXISTS sessions (
    scope TEXT PRIMARY KEY, umo TEXT NOT NULL, platform TEXT NOT NULL,
    self_id TEXT NOT NULL, group_id TEXT NOT NULL, private INTEGER NOT NULL,
    last_human REAL NOT NULL DEFAULT 0, last_reply REAL NOT NULL DEFAULT 0,
    cursor INTEGER NOT NULL DEFAULT 0, last_seq INTEGER NOT NULL DEFAULT 0,
    human_count INTEGER NOT NULL DEFAULT 0, summarized_count INTEGER NOT NULL DEFAULT 0,
    next_idle REAL NOT NULL DEFAULT 0, idle_waiting INTEGER NOT NULL DEFAULT 0,
    idle_day TEXT NOT NULL DEFAULT '', idle_count INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT, scope TEXT NOT NULL,
    seq INTEGER NOT NULL, human_count INTEGER NOT NULL,
    umo TEXT NOT NULL, platform TEXT NOT NULL, self_id TEXT NOT NULL,
    group_id TEXT NOT NULL, sender_id TEXT NOT NULL, sender_name TEXT NOT NULL,
    message_id TEXT NOT NULL, sent_at REAL NOT NULL, received_at REAL NOT NULL,
    text TEXT NOT NULL, segments TEXT NOT NULL, private INTEGER NOT NULL,
    day TEXT NOT NULL, direction TEXT NOT NULL,
    FOREIGN KEY(scope) REFERENCES sessions(scope)
);
CREATE UNIQUE INDEX IF NOT EXISTS messages_source ON messages(scope, direction, message_id)
    WHERE message_id != '';
CREATE INDEX IF NOT EXISTS messages_recent ON messages(scope, seq);
CREATE TABLE IF NOT EXISTS diary_days (
    scope TEXT NOT NULL, day TEXT NOT NULL,
    through_seq INTEGER NOT NULL, created_at REAL NOT NULL,
    updated_at REAL NOT NULL, sealed INTEGER NOT NULL DEFAULT 0,
    coverage_gap INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY(scope, day)
);
CREATE TABLE IF NOT EXISTS diary_topics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scope TEXT NOT NULL, day TEXT NOT NULL,
    topic_at REAL NOT NULL, topic_time TEXT NOT NULL,
    topic TEXT NOT NULL, interact TEXT NOT NULL,
    reply TEXT NOT NULL, reaction TEXT NOT NULL,
    first_seq INTEGER NOT NULL, last_seq INTEGER NOT NULL,
    created_at REAL NOT NULL, updated_at REAL NOT NULL,
    FOREIGN KEY(scope, day) REFERENCES diary_days(scope, day) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS diary_topics_recent
    ON diary_topics(scope, day, updated_at DESC, id DESC);
CREATE TABLE IF NOT EXISTS reply_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT, scope TEXT NOT NULL,
    started_at REAL NOT NULL, trigger TEXT NOT NULL,
    status TEXT NOT NULL, sent_parts INTEGER NOT NULL DEFAULT 0,
    detail TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS controller_decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT, scope TEXT NOT NULL,
    created_at REAL NOT NULL, observed_through_seq INTEGER NOT NULL,
    last_human_at REAL NOT NULL, trigger TEXT NOT NULL,
    reply_required INTEGER NOT NULL, decision_json TEXT NOT NULL,
    outcome TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS controller_decisions_recent
    ON controller_decisions(scope,id DESC);
CREATE INDEX IF NOT EXISTS diary_topics_updated
    ON diary_topics(scope,updated_at DESC,id DESC);
PRAGMA user_version=3;

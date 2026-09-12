CREATE TABLE preferences (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    source TEXT NOT NULL,
    reference TEXT NOT NULL,
    recorded_at TEXT NOT NULL
);

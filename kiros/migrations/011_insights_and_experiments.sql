CREATE TABLE diversity_observations (
    id TEXT PRIMARY KEY,
    campaign_id TEXT REFERENCES campaigns(id),
    title TEXT NOT NULL,
    dimensions_json TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    source TEXT NOT NULL,
    intentional_reason TEXT NOT NULL DEFAULT '',
    recorded_at TEXT NOT NULL
);
CREATE TABLE competitive_observations (
    id TEXT PRIMARY KEY,
    profile TEXT NOT NULL,
    category TEXT NOT NULL,
    location TEXT NOT NULL,
    source TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    is_mock INTEGER NOT NULL CHECK(is_mock IN (0,1)),
    observation TEXT NOT NULL,
    trend_json TEXT NOT NULL
);
CREATE TABLE experiments (
    id TEXT PRIMARY KEY,
    hypothesis TEXT NOT NULL,
    control TEXT NOT NULL,
    variant TEXT NOT NULL,
    variable TEXT NOT NULL,
    metric TEXT NOT NULL,
    risk TEXT NOT NULL CHECK(risk IN ('low','medium','high')),
    risk_reason TEXT NOT NULL,
    state TEXT NOT NULL CHECK(state IN ('awaiting_approval','approved','running','completed')),
    authorization TEXT NOT NULL DEFAULT '',
    approved_by TEXT,
    approved_at TEXT,
    created_at TEXT NOT NULL,
    result_json TEXT
);
CREATE TABLE experiment_events (
    id TEXT PRIMARY KEY,
    experiment_id TEXT NOT NULL REFERENCES experiments(id),
    action TEXT NOT NULL,
    operator TEXT NOT NULL,
    detail TEXT NOT NULL,
    recorded_at TEXT NOT NULL
);
CREATE INDEX idx_diversity_date ON diversity_observations(occurred_at);
CREATE INDEX idx_competitive_discovery ON competitive_observations(category,location);

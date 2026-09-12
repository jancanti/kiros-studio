CREATE TABLE providers (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    name TEXT NOT NULL,
    model TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    secret TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    config_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE provider_test_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider_id TEXT NOT NULL REFERENCES providers(id),
    test_type TEXT NOT NULL,
    status TEXT NOT NULL,
    latency_ms INTEGER NOT NULL,
    message TEXT NOT NULL,
    executed_at TEXT NOT NULL
);

CREATE TABLE campaign_budgets (
    campaign_id TEXT PRIMARY KEY,
    budget_limit REAL NOT NULL,
    alert_threshold REAL NOT NULL DEFAULT 0.8,
    allow_over_budget INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    provenance TEXT NOT NULL
);

CREATE TABLE cost_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id TEXT NOT NULL,
    asset_id TEXT,
    stage TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    estimated_cost REAL NOT NULL,
    actual_cost REAL NOT NULL,
    generation_count INTEGER NOT NULL DEFAULT 1,
    timestamp TEXT NOT NULL,
    provenance TEXT NOT NULL
);

CREATE TABLE budget_reservations (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    reserved_amount REAL NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE campaign_engine_routing (
    campaign_id TEXT PRIMARY KEY,
    default_engine TEXT NOT NULL,
    default_model TEXT NOT NULL,
    slide_overrides_json TEXT NOT NULL DEFAULT '{}',
    provenance TEXT NOT NULL,
    updated_at TEXT NOT NULL
);


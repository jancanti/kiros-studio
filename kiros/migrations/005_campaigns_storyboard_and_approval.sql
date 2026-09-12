CREATE TABLE campaigns (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    briefing_json TEXT NOT NULL,
    strategy_json TEXT NOT NULL,
    products_json TEXT NOT NULL,
    approval_mode TEXT NOT NULL DEFAULT 'minimal',
    status TEXT NOT NULL DEFAULT 'draft',
    plan_version INTEGER NOT NULL DEFAULT 1,
    approved_version INTEGER,
    approved_at TEXT,
    approved_by TEXT,
    budget_limit REAL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    provenance TEXT NOT NULL
);

CREATE TABLE storyboard_slides (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    slide_order INTEGER NOT NULL,
    title TEXT NOT NULL,
    visual_prompt TEXT NOT NULL,
    framing TEXT NOT NULL DEFAULT 'medium',
    caption_draft TEXT NOT NULL DEFAULT '',
    engine_override TEXT,
    status TEXT NOT NULL DEFAULT 'draft',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE pipeline_steps (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    slide_id TEXT REFERENCES storyboard_slides(id) ON DELETE CASCADE,
    step_order INTEGER NOT NULL,
    step_type TEXT NOT NULL,
    name TEXT NOT NULL,
    provider_id TEXT NOT NULL,
    model_id TEXT NOT NULL,
    params_json TEXT NOT NULL,
    estimated_cost REAL NOT NULL DEFAULT 0.0,
    status TEXT NOT NULL DEFAULT 'draft',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE campaign_approvals (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    step_id TEXT REFERENCES pipeline_steps(id) ON DELETE CASCADE,
    plan_version INTEGER NOT NULL,
    approved_by TEXT NOT NULL,
    approved_at TEXT NOT NULL,
    estimated_cost REAL NOT NULL,
    budget_reservation_id TEXT,
    is_valid INTEGER NOT NULL DEFAULT 1,
    invalidation_reason TEXT
);

CREATE INDEX idx_storyboard_campaign ON storyboard_slides(campaign_id);
CREATE INDEX idx_pipeline_campaign ON pipeline_steps(campaign_id);
CREATE INDEX idx_approvals_campaign ON campaign_approvals(campaign_id);


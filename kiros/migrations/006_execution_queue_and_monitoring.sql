CREATE TABLE execution_jobs (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    slide_id TEXT REFERENCES storyboard_slides(id) ON DELETE CASCADE,
    step_id TEXT NOT NULL REFERENCES pipeline_steps(id) ON DELETE CASCADE,
    idempotency_key TEXT UNIQUE NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    priority INTEGER NOT NULL DEFAULT 10,
    attempt INTEGER NOT NULL DEFAULT 0,
    max_retries INTEGER NOT NULL DEFAULT 3,
    timeout_seconds REAL NOT NULL DEFAULT 30.0,
    provider_id TEXT NOT NULL,
    model_id TEXT NOT NULL,
    prompt TEXT NOT NULL,
    params_json TEXT NOT NULL DEFAULT '{}',
    estimated_cost REAL NOT NULL DEFAULT 0.0,
    actual_cost REAL NOT NULL DEFAULT 0.0,
    budget_reservation_id TEXT,
    output_asset_id TEXT,
    output_data_json TEXT,
    error_provider TEXT,
    error_step TEXT,
    error_probable_cause TEXT,
    error_suggested_fix TEXT,
    error_potential_cost REAL DEFAULT 0.0,
    uncertain_resolution TEXT,
    locked_by TEXT,
    locked_at TEXT,
    started_at TEXT,
    completed_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE execution_versions (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    slide_id TEXT NOT NULL REFERENCES storyboard_slides(id) ON DELETE CASCADE,
    step_id TEXT NOT NULL REFERENCES pipeline_steps(id) ON DELETE CASCADE,
    job_id TEXT REFERENCES execution_jobs(id) ON DELETE SET NULL,
    version_number INTEGER NOT NULL,
    provider_id TEXT NOT NULL,
    model_id TEXT NOT NULL,
    prompt TEXT NOT NULL,
    asset_id TEXT,
    actual_cost REAL NOT NULL DEFAULT 0.0,
    status TEXT NOT NULL DEFAULT 'completed',
    created_at TEXT NOT NULL
);

ALTER TABLE campaigns ADD COLUMN monitoring_mode TEXT NOT NULL DEFAULT 'supervised';

CREATE INDEX idx_jobs_campaign ON execution_jobs(campaign_id);
CREATE INDEX idx_jobs_status_priority ON execution_jobs(status, priority, created_at);
CREATE INDEX idx_jobs_idempotency ON execution_jobs(idempotency_key);
CREATE INDEX idx_versions_slide ON execution_versions(slide_id);


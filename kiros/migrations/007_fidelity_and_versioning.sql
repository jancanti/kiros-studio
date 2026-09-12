ALTER TABLE execution_versions ADD COLUMN reason TEXT NOT NULL DEFAULT 'Geração inicial';
ALTER TABLE execution_versions ADD COLUMN requester TEXT NOT NULL DEFAULT 'system';
ALTER TABLE execution_versions ADD COLUMN prompt_ref TEXT;
ALTER TABLE execution_versions ADD COLUMN references_json TEXT NOT NULL DEFAULT '[]';
ALTER TABLE execution_versions ADD COLUMN fidelity_score REAL;
ALTER TABLE execution_versions ADD COLUMN fidelity_details_json TEXT NOT NULL DEFAULT '{}';
ALTER TABLE execution_versions ADD COLUMN fidelity_status TEXT NOT NULL DEFAULT 'pending';
ALTER TABLE execution_versions ADD COLUMN parent_version_id TEXT REFERENCES execution_versions(id) ON DELETE SET NULL;
ALTER TABLE execution_versions ADD COLUMN is_current INTEGER NOT NULL DEFAULT 1;

ALTER TABLE campaigns ADD COLUMN fidelity_mode TEXT NOT NULL DEFAULT 'recommend_before_spend';
ALTER TABLE campaigns ADD COLUMN fidelity_threshold REAL NOT NULL DEFAULT 85.0;

CREATE TABLE product_fidelity_checks (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    slide_id TEXT REFERENCES storyboard_slides(id) ON DELETE CASCADE,
    version_id TEXT REFERENCES execution_versions(id) ON DELETE SET NULL,
    product_id TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    asset_id TEXT NOT NULL,
    score REAL NOT NULL,
    threshold REAL NOT NULL DEFAULT 85.0,
    mode TEXT NOT NULL DEFAULT 'recommend_before_spend',
    status TEXT NOT NULL DEFAULT 'passed',
    checked_attributes_json TEXT NOT NULL DEFAULT '{}',
    discrepancies_json TEXT NOT NULL DEFAULT '[]',
    suggested_fix TEXT,
    estimated_correction_cost REAL NOT NULL DEFAULT 0.0,
    approval_status TEXT NOT NULL DEFAULT 'none',
    created_at TEXT NOT NULL
);

CREATE TABLE version_learnings (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    slide_id TEXT NOT NULL REFERENCES storyboard_slides(id) ON DELETE CASCADE,
    version_id TEXT NOT NULL REFERENCES execution_versions(id) ON DELETE CASCADE,
    learning_note TEXT NOT NULL,
    action_taken TEXT NOT NULL DEFAULT 'record_learning',
    recorder TEXT NOT NULL DEFAULT 'user',
    created_at TEXT NOT NULL
);

CREATE INDEX idx_fidelity_campaign ON product_fidelity_checks(campaign_id);
CREATE INDEX idx_fidelity_slide ON product_fidelity_checks(slide_id);
CREATE INDEX idx_fidelity_version ON product_fidelity_checks(version_id);
CREATE INDEX idx_learnings_slide ON version_learnings(slide_id);


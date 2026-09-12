CREATE TABLE IF NOT EXISTS prompt_library (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    objective TEXT NOT NULL,
    engine TEXT NOT NULL,
    context TEXT NOT NULL,
    prompt_text TEXT NOT NULL,
    result_summary TEXT NOT NULL,
    performance_score REAL NOT NULL DEFAULT 0.0,
    status TEXT NOT NULL DEFAULT 'suggested',
    approved_by TEXT,
    approved_at TEXT,
    provenance TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS learning_proposals (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    summary TEXT NOT NULL,
    details_json TEXT NOT NULL DEFAULT '{}',
    evidence_count INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'suggested',
    approved_by TEXT,
    approved_at TEXT,
    provenance TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS campaign_learnings (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    slide_id TEXT,
    correction_note TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'correction',
    created_at TEXT NOT NULL,
    provenance TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_prompt_library_status ON prompt_library(status);
CREATE INDEX IF NOT EXISTS idx_learning_proposals_status ON learning_proposals(status);
CREATE INDEX IF NOT EXISTS idx_campaign_learnings_cid ON campaign_learnings(campaign_id);

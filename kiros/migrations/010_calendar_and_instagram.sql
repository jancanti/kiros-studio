CREATE TABLE calendar_preferences (
    id TEXT PRIMARY KEY,
    max_posts_per_week INTEGER NOT NULL DEFAULT 4,
    min_hours_between_posts INTEGER NOT NULL DEFAULT 24,
    preferred_days_json TEXT NOT NULL DEFAULT '["seg", "qua", "sex", "dom"]',
    preferred_time_ranges_json TEXT NOT NULL DEFAULT '[{"start": "18:00", "end": "20:00"}]',
    saturation_threshold_per_pillar_per_week INTEGER NOT NULL DEFAULT 2,
    updated_at TEXT NOT NULL
);

CREATE TABLE calendar_entries (
    id TEXT PRIMARY KEY,
    campaign_id TEXT REFERENCES campaigns(id) ON DELETE SET NULL,
    slide_id TEXT REFERENCES storyboard_slides(id) ON DELETE SET NULL,
    sequence_id TEXT REFERENCES story_sequences(id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    content_type TEXT NOT NULL DEFAULT 'feed',
    pillar TEXT NOT NULL DEFAULT 'institucional',
    priority TEXT NOT NULL DEFAULT 'medium',
    seasonal_tag TEXT,
    phase TEXT NOT NULL DEFAULT 'none',
    status TEXT NOT NULL DEFAULT 'draft',
    scheduled_for TEXT,
    recommended_time TEXT,
    selected_time TEXT,
    time_accepted INTEGER NOT NULL DEFAULT 1,
    data_basis_json TEXT NOT NULL DEFAULT '{}',
    later_performance_json TEXT NOT NULL DEFAULT '{}',
    format_specs_json TEXT NOT NULL DEFAULT '{}',
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE social_publications (
    id TEXT PRIMARY KEY,
    calendar_entry_id TEXT REFERENCES calendar_entries(id) ON DELETE SET NULL,
    campaign_id TEXT REFERENCES campaigns(id) ON DELETE SET NULL,
    asset_id TEXT NOT NULL,
    caption TEXT NOT NULL,
    media_type TEXT NOT NULL DEFAULT 'IMAGE',
    idempotency_key TEXT UNIQUE NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    provider TEXT NOT NULL DEFAULT 'mock',
    external_container_id TEXT,
    external_post_id TEXT,
    explicit_confirmed_by TEXT,
    explicit_confirmed_at TEXT,
    audit_id TEXT REFERENCES pre_publish_audits(id),
    scheduled_publish_time TEXT,
    error_message TEXT,
    published_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE instagram_accounts (
    id TEXT PRIMARY KEY,
    account_id TEXT,
    username TEXT,
    account_type TEXT NOT NULL DEFAULT 'business',
    connection_status TEXT NOT NULL DEFAULT 'unvalidated',
    permissions_json TEXT NOT NULL DEFAULT '[]',
    rate_limit_total INTEGER NOT NULL DEFAULT 25,
    rate_limit_remaining INTEGER NOT NULL DEFAULT 25,
    last_checked_at TEXT,
    updated_at TEXT NOT NULL
);

CREATE INDEX idx_calendar_entries_scheduled ON calendar_entries(scheduled_for);
CREATE INDEX idx_calendar_entries_campaign ON calendar_entries(campaign_id);
CREATE INDEX idx_calendar_entries_pillar ON calendar_entries(pillar);
CREATE INDEX idx_social_publications_idempotency ON social_publications(idempotency_key);
CREATE INDEX idx_social_publications_calendar ON social_publications(calendar_entry_id);

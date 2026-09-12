CREATE TABLE slide_copies (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    slide_id TEXT NOT NULL REFERENCES storyboard_slides(id) ON DELETE CASCADE,
    mode TEXT NOT NULL DEFAULT 'automatic',
    text TEXT NOT NULL DEFAULT '',
    user_draft TEXT NOT NULL DEFAULT '',
    suggestions_json TEXT NOT NULL DEFAULT '[]',
    tone TEXT NOT NULL DEFAULT 'leve, relaxado, brasileiro',
    seo_terms_json TEXT NOT NULL DEFAULT '[]',
    cta_mode TEXT NOT NULL DEFAULT 'none',
    cta_text TEXT NOT NULL DEFAULT '',
    cta_intent TEXT,
    destination_url TEXT NOT NULL DEFAULT '',
    show_price INTEGER NOT NULL DEFAULT 0,
    price_value TEXT,
    price_justification TEXT,
    price_approved_by TEXT,
    price_approved_at TEXT,
    status TEXT NOT NULL DEFAULT 'draft',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE story_sequences (
    id TEXT PRIMARY KEY,
    campaign_id TEXT REFERENCES campaigns(id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    story_type TEXT NOT NULL DEFAULT 'independent',
    objective TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'draft',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE story_frames (
    id TEXT PRIMARY KEY,
    sequence_id TEXT NOT NULL REFERENCES story_sequences(id) ON DELETE CASCADE,
    frame_order INTEGER NOT NULL,
    narrative_role TEXT NOT NULL DEFAULT 'context',
    title TEXT NOT NULL DEFAULT '',
    overlay_text TEXT NOT NULL DEFAULT '',
    visual_prompt TEXT NOT NULL DEFAULT '',
    interaction_type TEXT NOT NULL DEFAULT 'none',
    interaction_data_json TEXT NOT NULL DEFAULT '{}',
    interaction_justification TEXT NOT NULL DEFAULT '',
    caption_draft TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE pre_publish_audits (
    id TEXT PRIMARY KEY,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    is_ready INTEGER NOT NULL DEFAULT 0,
    checks_json TEXT NOT NULL,
    blocked_reasons_json TEXT NOT NULL,
    operator TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX idx_slide_copies_slide ON slide_copies(slide_id);
CREATE INDEX idx_slide_copies_campaign ON slide_copies(campaign_id);
CREATE INDEX idx_story_sequences_campaign ON story_sequences(campaign_id);
CREATE INDEX idx_story_frames_sequence ON story_frames(sequence_id);
CREATE INDEX idx_pre_publish_audits_target ON pre_publish_audits(target_type, target_id);


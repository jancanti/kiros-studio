CREATE TABLE layout_templates (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    family TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    supported_formats_json TEXT NOT NULL DEFAULT '["4:5", "9:16"]',
    composition_rules_json TEXT NOT NULL,
    default_elements_json TEXT NOT NULL,
    usage_count INTEGER NOT NULL DEFAULT 0,
    last_used_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    provenance TEXT NOT NULL
);

CREATE TABLE slide_layouts (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    slide_id TEXT NOT NULL REFERENCES storyboard_slides(id) ON DELETE CASCADE,
    template_id TEXT REFERENCES layout_templates(id) ON DELETE SET NULL,
    format TEXT NOT NULL DEFAULT '4:5',
    elements_json TEXT NOT NULL,
    protection_overrides_json TEXT NOT NULL DEFAULT '{}',
    is_approved INTEGER NOT NULL DEFAULT 0,
    approved_at TEXT,
    approved_by TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE layout_audit_log (
    id TEXT PRIMARY KEY,
    layout_id TEXT NOT NULL REFERENCES slide_layouts(id) ON DELETE CASCADE,
    slide_id TEXT NOT NULL REFERENCES storyboard_slides(id) ON DELETE CASCADE,
    attribute_name TEXT NOT NULL,
    protection_level TEXT NOT NULL,
    previous_value TEXT,
    new_value TEXT,
    reason TEXT NOT NULL,
    operator TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX idx_slide_layouts_slide ON slide_layouts(slide_id);
CREATE INDEX idx_slide_layouts_campaign ON slide_layouts(campaign_id);
CREATE INDEX idx_layout_templates_status ON layout_templates(status);
CREATE INDEX idx_layout_templates_family ON layout_templates(family);
CREATE INDEX idx_layout_audit_layout ON layout_audit_log(layout_id);


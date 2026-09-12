CREATE TABLE content_pillars (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    weight REAL NOT NULL,
    frequency TEXT NOT NULL,
    saturation REAL NOT NULL DEFAULT 0.0,
    performance_score REAL NOT NULL DEFAULT 0.0,
    is_official INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    provenance TEXT NOT NULL
);

CREATE TABLE ideas (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    concept TEXT NOT NULL,
    pillar TEXT NOT NULL,
    state TEXT NOT NULL,
    is_pinned INTEGER NOT NULL DEFAULT 0,
    rejection_reason TEXT,
    fingerprint TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    provenance TEXT NOT NULL
);

CREATE TABLE typed_memories (
    id TEXT PRIMARY KEY,
    memory_type TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    scope TEXT NOT NULL DEFAULT 'global',
    confidence REAL NOT NULL DEFAULT 1.0,
    created_at TEXT NOT NULL,
    provenance TEXT NOT NULL
);

CREATE TABLE strategic_decisions (
    id TEXT PRIMARY KEY,
    decision_type TEXT NOT NULL,
    summary TEXT NOT NULL,
    details_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    provenance TEXT NOT NULL
);

INSERT INTO content_pillars (id, name, weight, frequency, saturation, performance_score, is_official, created_at, provenance) VALUES
('produtos', 'Produtos', 0.25, '3x/semana', 0.0, 0.0, 1, '2026-09-12T12:00:00+00:00', 'system'),
('lifestyle', 'Lifestyle', 0.20, '2x/semana', 0.0, 0.0, 1, '2026-09-12T12:00:00+00:00', 'system'),
('marca', 'Marca', 0.15, '1x/semana', 0.0, 0.0, 1, '2026-09-12T12:00:00+00:00', 'system'),
('educativo', 'Educativo', 0.15, '1x/semana', 0.0, 0.0, 1, '2026-09-12T12:00:00+00:00', 'system'),
('relacionamento', 'Relacionamento', 0.15, '2x/semana', 0.0, 0.0, 1, '2026-09-12T12:00:00+00:00', 'system'),
('comercial', 'Comercial', 0.10, '1x/semana', 0.0, 0.0, 1, '2026-09-12T12:00:00+00:00', 'system');


CREATE TABLE products (id TEXT PRIMARY KEY, name TEXT NOT NULL, stock INTEGER, provenance TEXT NOT NULL);
CREATE TABLE stock_history (id INTEGER PRIMARY KEY, product_id TEXT NOT NULL REFERENCES products(id), quantity INTEGER NOT NULL, provenance TEXT NOT NULL);
CREATE TABLE sales_imports (digest TEXT PRIMARY KEY, provenance TEXT NOT NULL);
CREATE TABLE sales (id INTEGER PRIMARY KEY, import_digest TEXT NOT NULL REFERENCES sales_imports(digest), product_id TEXT NOT NULL REFERENCES products(id), sold_on TEXT NOT NULL, quantity INTEGER NOT NULL, revenue TEXT);
CREATE TABLE bible_versions (id INTEGER PRIMARY KEY, kind TEXT NOT NULL, owner TEXT NOT NULL, version INTEGER NOT NULL, base_id INTEGER, content TEXT NOT NULL, provenance TEXT NOT NULL, approved_by TEXT, approved_at TEXT, UNIQUE(kind, owner, version));
CREATE TABLE campaign_overrides (campaign TEXT PRIMARY KEY, brand_version INTEGER NOT NULL REFERENCES bible_versions(id), content TEXT NOT NULL, provenance TEXT NOT NULL);
CREATE TABLE visual_references (id TEXT PRIMARY KEY, asset_key TEXT NOT NULL, mime TEXT NOT NULL, product_id TEXT REFERENCES products(id), scope TEXT NOT NULL, campaign TEXT, origin TEXT NOT NULL, source_reference TEXT NOT NULL, rights TEXT NOT NULL, usage TEXT NOT NULL, angle TEXT NOT NULL, quality INTEGER NOT NULL, analysis TEXT NOT NULL, provenance TEXT NOT NULL);

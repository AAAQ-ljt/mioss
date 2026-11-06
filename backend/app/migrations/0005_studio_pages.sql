ALTER TABLE entry ADD COLUMN category_path_text TEXT;

CREATE INDEX idx_entry_category_text ON entry(category_path_text);

CREATE TABLE relay_item (
  id TEXT PRIMARY KEY,
  content TEXT NOT NULL,
  format TEXT NOT NULL DEFAULT 'plain',
  source_entry_id TEXT,
  source_title TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE prompt_preset (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  kind TEXT NOT NULL DEFAULT 'style',
  positive TEXT NOT NULL,
  negative TEXT,
  notes TEXT,
  seed INTEGER,
  profile_json TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE story_doc (
  project_id TEXT PRIMARY KEY REFERENCES project(id),
  title TEXT,
  markdown TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

ALTER TABLE prompt_preset ADD COLUMN preview_image TEXT;
ALTER TABLE prompt_preset ADD COLUMN usage_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE prompt_preset ADD COLUMN version INTEGER NOT NULL DEFAULT 1;

CREATE TABLE preset_binding (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES project(id),
  preset_id TEXT NOT NULL REFERENCES prompt_preset(id),
  order_no INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  UNIQUE (project_id, preset_id)
);

CREATE INDEX idx_preset_binding_project ON preset_binding(project_id);

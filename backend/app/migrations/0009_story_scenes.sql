ALTER TABLE project ADD COLUMN mode TEXT NOT NULL DEFAULT 'comic';
ALTER TABLE page ADD COLUMN kind TEXT NOT NULL DEFAULT 'comic';
ALTER TABLE page ADD COLUMN scene_id TEXT;

CREATE TABLE story_scene (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES project(id),
  chapter_title TEXT,
  chapter_index INTEGER NOT NULL DEFAULT 0,
  order_no INTEGER NOT NULL,
  title TEXT,
  excerpt TEXT,
  summary TEXT,
  characters TEXT,
  setting TEXT,
  mood TEXT,
  status TEXT NOT NULL DEFAULT 'draft',
  page_id TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE INDEX idx_story_scene_project ON story_scene(project_id, order_no);

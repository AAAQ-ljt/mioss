CREATE TABLE storyboard_task (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES project(id),
  scene_id TEXT REFERENCES story_scene(id),
  chapter_title TEXT,
  title TEXT NOT NULL,
  kind TEXT NOT NULL DEFAULT 'comic',
  style_preset_id TEXT,
  style_snapshot_json TEXT,
  character_snapshot_json TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE UNIQUE INDEX idx_storyboard_task_scene ON storyboard_task(scene_id) WHERE scene_id IS NOT NULL;
CREATE INDEX idx_storyboard_task_project ON storyboard_task(project_id, created_at);

ALTER TABLE page ADD COLUMN task_id TEXT;
ALTER TABLE page ADD COLUMN shot_no INTEGER;

CREATE INDEX idx_page_task ON page(task_id, shot_no);

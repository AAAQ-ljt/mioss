ALTER TABLE chapter ADD COLUMN file_name TEXT;
ALTER TABLE chapter ADD COLUMN updated_at TEXT;

CREATE INDEX idx_chapter_project ON chapter(project_id, order_no);

CREATE TABLE codex (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  author TEXT,
  version TEXT,
  type TEXT,
  nsfw INTEGER NOT NULL DEFAULT 0,
  entry_count INTEGER NOT NULL DEFAULT 0,
  source_release TEXT,
  content_hash TEXT,
  tree_json TEXT,
  synced_at TEXT
);

CREATE TABLE entry (
  id TEXT PRIMARY KEY,
  codex_id TEXT NOT NULL REFERENCES codex(id),
  title TEXT,
  category_path_json TEXT,
  tags_raw TEXT,
  tags_positive TEXT,
  tags_negative TEXT,
  negative_raw TEXT,
  note TEXT,
  image TEXT,
  image_url TEXT,
  image_width INTEGER,
  image_height INTEGER,
  original TEXT,
  asset_rev TEXT,
  rating TEXT,
  is_new INTEGER,
  moss_usable INTEGER NOT NULL DEFAULT 0,
  artist_ratio REAL NOT NULL DEFAULT 0,
  raw_json TEXT,
  updated_at TEXT
);

CREATE INDEX idx_entry_codex ON entry(codex_id);
CREATE INDEX idx_entry_usable ON entry(moss_usable);

CREATE TABLE entry_tag (
  entry_id TEXT NOT NULL REFERENCES entry(id),
  tag TEXT NOT NULL,
  kind TEXT NOT NULL,
  PRIMARY KEY (entry_id, tag, kind)
);

CREATE INDEX idx_entry_tag_tag ON entry_tag(tag);

CREATE TABLE tag_zh (
  tag TEXT NOT NULL,
  zh TEXT NOT NULL,
  codex_id TEXT NOT NULL,
  PRIMARY KEY (tag, zh, codex_id)
);

CREATE INDEX idx_tag_zh_zh ON tag_zh(zh);

CREATE TABLE artist_tag (
  tag TEXT PRIMARY KEY
);

CREATE TABLE style_preset (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  tags TEXT NOT NULL
);

CREATE TABLE project (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  story TEXT,
  style_preset_id TEXT REFERENCES style_preset(id),
  gallery_sort TEXT NOT NULL DEFAULT 'order',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE chapter (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES project(id),
  title TEXT,
  order_no INTEGER NOT NULL,
  summary TEXT
);

CREATE TABLE characters (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES project(id),
  name TEXT NOT NULL,
  anchor_tags TEXT,
  ref_image TEXT,
  notes TEXT
);

CREATE TABLE page (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES project(id),
  chapter_id TEXT REFERENCES chapter(id),
  order_no INTEGER NOT NULL,
  summary TEXT,
  layout_note TEXT,
  prompt TEXT,
  negative TEXT,
  seed INTEGER,
  status TEXT NOT NULL DEFAULT 'draft',
  image_path TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE INDEX idx_page_project ON page(project_id, order_no);

CREATE TABLE generation_job (
  id TEXT PRIMARY KEY,
  page_id TEXT NOT NULL REFERENCES page(id),
  prompt TEXT,
  negative TEXT,
  seed INTEGER,
  workflow_profile TEXT,
  comfy_prompt_id TEXT,
  status TEXT NOT NULL,
  output_path TEXT,
  error TEXT,
  started_at TEXT,
  finished_at TEXT
);

CREATE TABLE setting (
  key TEXT PRIMARY KEY,
  value TEXT
);

INSERT INTO style_preset(id, name, tags) VALUES
  ('cinematic-anime', '电影感动画', 'cinematic anime illustration, strong dramatic lighting, high saturation colors, sharp dynamic composition, film grain texture, lens blur, energetic character pose, detailed digital painting, movie key visual style'),
  ('manga-ink', '黑白网点漫画', 'black and white manga, pen line art, screentone, cel shading, dramatic composition, clean panel borders'),
  ('soft-color-manga', '日式全彩漫画', 'japanese full color manga, cel shading, clean line art, vivid color, dramatic lighting');

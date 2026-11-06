CREATE TABLE favorite_entry (
  id TEXT PRIMARY KEY,
  entry_id TEXT NOT NULL UNIQUE,
  domain TEXT NOT NULL,
  title TEXT,
  image_url TEXT,
  source_title TEXT,
  prompt_nai TEXT,
  prompt_moss TEXT,
  prompt_sd_positive TEXT,
  negative_nai TEXT,
  negative_sd TEXT,
  created_at TEXT NOT NULL
);

CREATE INDEX idx_favorite_domain ON favorite_entry(domain);

DELETE FROM relay_item;

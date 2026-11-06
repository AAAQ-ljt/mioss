ALTER TABLE entry ADD COLUMN domain TEXT;
ALTER TABLE entry ADD COLUMN cat_primary TEXT;
ALTER TABLE entry ADD COLUMN cat_labels_json TEXT;

CREATE INDEX idx_entry_domain ON entry(domain);
CREATE INDEX idx_entry_cat_primary ON entry(cat_primary);

CREATE TABLE category_l1 (
  id TEXT PRIMARY KEY,
  domain TEXT NOT NULL,
  name TEXT NOT NULL,
  order_no INTEGER NOT NULL
);

INSERT INTO category_l1(id, domain, name, order_no) VALUES
  ('character', 'regular', '角色与人物', 1),
  ('outfit', 'regular', '服装与造型', 2),
  ('scene', 'regular', '场景与背景', 3),
  ('composition', 'regular', '构图与镜头', 4),
  ('style', 'regular', '风格与画风', 5),
  ('action', 'regular', '动作与表情', 6),
  ('prop', 'regular', '道具与生物', 7),
  ('misc', 'regular', '漫画与杂项', 8),
  ('nsfw_single', 'nsfw', '单人', 1),
  ('nsfw_multi', 'nsfw', '双人/多人', 2),
  ('nsfw_relation', 'nsfw', '关系与取向', 3),
  ('nsfw_nonhuman', 'nsfw', '非人与异种', 4),
  ('nsfw_outfit', 'nsfw', '情趣服饰', 5),
  ('nsfw_scene', 'nsfw', '场景与道具', 6),
  ('nsfw_extreme', 'nsfw', 'R18G/重口', 7),
  ('nsfw_misc', 'nsfw', '连续/差分/杂项', 8),
  ('artist_ref', 'reference', '画师参考', 1);

CREATE TABLE entry_category (
  entry_id TEXT NOT NULL REFERENCES entry(id),
  category_id TEXT NOT NULL REFERENCES category_l1(id),
  is_primary INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (entry_id, category_id)
);

CREATE INDEX idx_entry_category_category ON entry_category(category_id);

export type Codex = {
  id: string;
  title: string;
  author: string | null;
  version: string | null;
  type: string | null;
  nsfw: number;
  entry_count: number;
};

export type RefDetail = {
  id: string;
  title: string;
  tags_positive: string;
  image_url: string | null;
};

export type Page = {
  id: string;
  order_no: number;
  summary: string;
  layout_note: string;
  prompt: string;
  negative: string;
  refs: string[];
  ref_details: RefDetail[];
  continuity: Record<string, string>;
  character_ids: string[];
  seed: number | null;
  status: string;
  image_path: string | null;
  image_url: string | null;
  kind?: "comic" | "illustration";
  scene_id?: string | null;
  updated_at: string;
};

export type StoryScene = {
  id: string;
  project_id: string;
  chapter_title: string;
  chapter_index: number;
  order_no: number;
  title: string;
  excerpt: string;
  summary: string;
  characters: string;
  setting: string;
  mood: string;
  status: string;
  page_id: string | null;
};

export type Project = {
  id: string;
  title: string;
  story: string;
  style_preset_id: string;
  mode?: "illustration" | "comic";
  thumbnail_url?: string | null;
  pages?: Page[];
  page_count?: number;
};

export type StylePreset = {
  id: string;
  name: string;
  tags: string;
};

export type Job = {
  id: string;
  page_id: string;
  order_no: number;
  project_id: string;
  status: string;
  seed: number | null;
  output_path: string | null;
  error: string | null;
  started_at: string;
  finished_at: string | null;
};

export type CodexEntry = {
  id: string;
  codex_id: string;
  title: string;
  tags_raw: string;
  tags_positive: string;
  tags_negative: string;
  prompt_sd_positive?: string;
  prompt_sd_negative?: string;
  note: string | null;
  image_url: string | null;
  category_path_json: string;
  moss_usable: number;
};

export type RelayItem = {
  id: string;
  content: string;
  format: string;
  source_entry_id: string | null;
  source_title: string | null;
  created_at: string;
};

export type FavoriteItem = {
  id: string;
  entry_id: string;
  domain: "regular" | "nsfw";
  title: string;
  image_url: string | null;
  source_title: string | null;
  prompt_nai: string;
  prompt_moss: string;
  prompt_sd_positive: string;
  negative_nai: string;
  negative_sd: string;
  created_at: string;
};

export type PromptPreset = {
  id: string;
  name: string;
  kind: string;
  positive: string;
  negative: string;
  notes: string;
  seed: number | null;
  profile_json: string;
  preview_image: string | null;
  usage_count: number;
  version: number;
  binding_order?: number;
  created_at: string;
  updated_at: string;
};

export type StoryDoc = {
  project_id: string;
  title: string;
  markdown: string;
  updated_at: string | null;
  chapters: { level: number; title: string; line: number }[];
};

export type Chapter = {
  id: string;
  project_id: string;
  title: string;
  order_no: number;
  summary: string;
  file_name: string | null;
  updated_at: string | null;
};

export type ChapterDetail = Chapter & { content: string };

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    ...init,
  });
  if (!response.ok) {
    throw new Error(`${response.status} ${await response.text()}`);
  }
  return response.json() as Promise<T>;
}

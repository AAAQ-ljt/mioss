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
  seed: number | null;
  status: string;
  image_path: string | null;
  image_url: string | null;
  updated_at: string;
};

export type Project = {
  id: string;
  title: string;
  story: string;
  style_preset_id: string;
  pages?: Page[];
  page_count?: number;
};

export type StylePreset = {
  id: string;
  name: string;
  tags: string;
};

export type CodexEntry = {
  id: string;
  codex_id: string;
  title: string;
  tags_positive: string;
  tags_negative: string;
  note: string | null;
  image_url: string | null;
  category_path_json: string;
  moss_usable: number;
};

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

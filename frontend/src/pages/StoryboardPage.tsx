import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { api, type Codex, type CodexEntry, type Job, type Page, type Project, type PromptPreset, type StylePreset } from "../api";

type Health = {
  ok: boolean;
  release: string | null;
  entries: { total: number; usable: number };
  comfy: { ok: boolean; error?: string };
};

type ComposeResult = {
  positive: string;
  negative: string;
  positive_count?: number;
  negative_count?: number;
  dropped: { id: string; reason: string }[];
};

type CategoryNode = {
  name: string;
  count: number;
  children?: CategoryNode[];
};

type FlatCategory = { name: string; label: string; count: number };

function flattenCategories(nodes: CategoryNode[] | undefined, depth = 0): FlatCategory[] {
  return (nodes || []).flatMap((node) => [
    { name: node.name, label: `${" ".repeat(depth * 2)}${node.name}`, count: node.count },
    ...flattenCategories(node.children, depth + 1),
  ]);
}

export default function StoryboardPage() {
  const queryClient = useQueryClient();
  const [projectTitle, setProjectTitle] = useState("测试漫画");
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);
  const [selectedPageId, setSelectedPageId] = useState<string | null>(null);
  const [storyDraft, setStoryDraft] = useState("");
  const [stylePresetId, setStylePresetId] = useState("manga-ink");
  const [selectedPresetId, setSelectedPresetId] = useState("");
  const [characterName, setCharacterName] = useState("露娜");
  const [characterAnchor, setCharacterAnchor] = useState("1girl, silver hair, amber eyes, apprentice mage, cloak");
  const [draft, setDraft] = useState<Page | null>(null);
  const [query, setQuery] = useState("森林");
  const [codexFilter, setCodexFilter] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [includeNsfw, setIncludeNsfw] = useState(false);
  const [gallerySort, setGallerySort] = useState<"order" | "time">("order");
  const [galleryOpen, setGalleryOpen] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [errorNotice, setErrorNotice] = useState<string | null>(null);
  const [lastCompose, setLastCompose] = useState<ComposeResult | null>(null);

  const healthQuery = useQuery({
    queryKey: ["health"],
    queryFn: () => api<Health>("/api/health"),
    refetchInterval: 5000,
  });

  const projectsQuery = useQuery({
    queryKey: ["projects"],
    queryFn: () => api<Project[]>("/api/projects"),
  });

  const projectQuery = useQuery({
    queryKey: ["project", selectedProjectId],
    queryFn: () => api<Project>(`/api/projects/${selectedProjectId}`),
    enabled: !!selectedProjectId,
    refetchInterval: (state) => {
      const statuses = state.state.data?.pages?.map((page) => page.status) || [];
      return statuses.some((status) => status === "queued" || status === "running") ? 3000 : false;
    },
  });

  const charactersQuery = useQuery({
    queryKey: ["characters", selectedProjectId],
    queryFn: () => api<{ id: string; name: string; anchor_tags: string; notes: string }[]>(`/api/projects/${selectedProjectId}/characters`),
    enabled: !!selectedProjectId,
  });

  const codexesQuery = useQuery({
    queryKey: ["codexes"],
    queryFn: () => api<Codex[]>("/api/codexes?include_nsfw=true"),
  });

  const categoriesQuery = useQuery({
    queryKey: ["codex-categories", codexFilter],
    queryFn: () => api<CategoryNode[]>(`/api/codex/categories?codex_id=${encodeURIComponent(codexFilter)}`),
    enabled: !!codexFilter,
  });

  const stylePresetsQuery = useQuery({
    queryKey: ["style-presets"],
    queryFn: () => api<StylePreset[]>("/api/style-presets"),
  });

  const promptPresetsQuery = useQuery({
    queryKey: ["prompt-presets"],
    queryFn: () => api<PromptPreset[]>("/api/presets"),
  });

  const suggestionsQuery = useQuery({
    queryKey: ["codex-suggest", query],
    queryFn: () => api<{ tag: string; count: number }[]>(`/api/codex/suggest?q=${encodeURIComponent(query)}&limit=20`),
    enabled: query.trim().length > 0,
  });

  const codexQuery = useQuery({
    queryKey: ["codex", query, codexFilter, categoryFilter, includeNsfw],
    queryFn: () =>
      api<CodexEntry[]>(
        `/api/codex/search?q=${encodeURIComponent(query)}&include_nsfw=${includeNsfw}&limit=20${codexFilter ? `&codex_id=${encodeURIComponent(codexFilter)}` : ""}${categoryFilter ? `&category_path=${encodeURIComponent(categoryFilter)}` : ""}`,
      ),
    enabled: query.trim().length > 0,
  });

  const variantsQuery = useQuery({
    queryKey: ["page-variants", selectedPageId],
    queryFn: () => api<{ id: string; seed: number | null; output_path: string | null; image_url: string | null }[]>(`/api/pages/${selectedPageId}/variants`),
    enabled: !!selectedPageId,
  });

  const jobsQuery = useQuery({
    queryKey: ["jobs"],
    queryFn: () => api<Job[]>("/api/jobs?limit=20"),
    refetchInterval: 3000,
  });

  const jobQuery = useQuery({
    queryKey: ["job", jobId],
    queryFn: () => api<Job>(`/api/jobs/${jobId}`),
    enabled: !!jobId,
    refetchInterval: (state) => {
      const status = state.state.data?.status;
      return status === "succeeded" || status === "failed" ? false : 2000;
    },
  });

  useEffect(() => {
    setCategoryFilter("");
  }, [codexFilter]);

  const project = projectQuery.data;
  const pages = project?.pages || [];
  const selectedPage = pages.find((page) => page.id === selectedPageId) || pages[0] || null;
  const galleryPages = [...pages]
    .filter((page) => page.image_url)
    .sort((a, b) =>
      gallerySort === "time"
        ? (b.updated_at || "").localeCompare(a.updated_at || "")
        : a.order_no - b.order_no,
    );

  useEffect(() => {
    if (selectedPage) setSelectedPageId(selectedPage.id);
  }, [selectedPage?.id]);

  useEffect(() => {
    if (selectedPage) setDraft(selectedPage);
  }, [selectedPage?.id]);

  useEffect(() => {
    if (project) {
      setStoryDraft(project.story || "");
      setStylePresetId(project.style_preset_id || "manga-ink");
    }
  }, [project?.id, project?.story, project?.style_preset_id]);

  const createProject = useMutation({
    mutationFn: (title: string) => api<Project>("/api/projects", { method: "POST", body: JSON.stringify({ title, style_preset_id: "manga-ink" }) }),
    onSuccess: (created) => {
      setSelectedProjectId(created.id);
      queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
  });

  const updateProject = useMutation({
    mutationFn: (patch: Partial<Project>) => api<Project>(`/api/projects/${selectedProjectId}`, { method: "PATCH", body: JSON.stringify(patch) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["project", selectedProjectId] }),
  });

  const saveStory = useMutation({
    mutationFn: () => api<Project>(`/api/projects/${selectedProjectId}/story`, { method: "POST", body: JSON.stringify({ story: storyDraft }) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["project", selectedProjectId] }),
  });

  const upsertCharacter = useMutation({
    mutationFn: () =>
      api<{ id: string; name: string }>(`/api/projects/${selectedProjectId}/characters`, {
        method: "POST",
        body: JSON.stringify({ name: characterName, anchor_tags: characterAnchor }),
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["characters", selectedProjectId] }),
  });

  const addPage = useMutation({
    mutationFn: async () => {
      return api<Page>(`/api/projects/${selectedProjectId}/pages`, {
        method: "POST",
        body: JSON.stringify({ summary: "新页面", layout_note: "", refs: [] }),
      });
    },
    onSuccess: (page) => {
      setSelectedPageId(page.id);
      queryClient.invalidateQueries({ queryKey: ["project", selectedProjectId] });
    },
  });

  const savePage = useMutation({
    mutationFn: async () => {
      if (!draft) return;
      return api<Page>(`/api/pages/${draft.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          summary: draft.summary,
          layout_note: draft.layout_note,
          prompt: draft.prompt,
          negative: draft.negative,
          refs: draft.refs,
          continuity: draft.continuity || {},
          character_ids: draft.character_ids || [],
          seed: draft.seed,
        }),
      });
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["project", selectedProjectId] }),
  });

  const compose = useMutation({
    mutationFn: async () => {
      if (!draft) return;
      await savePage.mutateAsync();
      const result = await api<ComposeResult>(`/api/pages/${draft.id}/compose`, {
        method: "POST",
        body: JSON.stringify({
          entry_ids: draft.refs,
          character_ids: draft.character_ids || [],
          page_text: `${draft.summary} ${draft.layout_note}`.trim(),
          save: true,
        }),
      });
      setDraft({ ...draft, prompt: result.positive, negative: result.negative });
      setLastCompose(result);
      return result;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["project", selectedProjectId] }),
  });

  const reorderPages = useMutation({
    mutationFn: async (pageIds: string[]) => {
      return api<{ pages: Page[] }>(`/api/projects/${selectedProjectId}/reorder`, {
        method: "POST",
        body: JSON.stringify({ page_ids: pageIds }),
      });
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["project", selectedProjectId] }),
  });

  const deletePage = useMutation({
    mutationFn: async (pageId: string) => api<{ deleted: string }>(`/api/pages/${pageId}`, { method: "DELETE" }),
    onSuccess: (_result, pageId) => {
      if (selectedPageId === pageId) setSelectedPageId(null);
      queryClient.invalidateQueries({ queryKey: ["project", selectedProjectId] });
    },
  });

  const generate = useMutation({
    mutationFn: async (initImagePath?: string | null) => {
      if (!draft) return;
      await savePage.mutateAsync();
      const result = await api<{ job_id: string }>(`/api/pages/${draft.id}/generate`, {
        method: "POST",
        body: JSON.stringify({ seed: draft.seed, init_image_path: initImagePath }),
      });
      setJobId(result.job_id);
      return result;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["project", selectedProjectId] });
      queryClient.invalidateQueries({ queryKey: ["page-variants", selectedPageId] });
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
    },
  });

  const importProject = useMutation({
    mutationFn: async (file: File) => {
      const payload = JSON.parse(await file.text());
      return api<Project>("/api/projects/import", { method: "POST", body: JSON.stringify(payload) });
    },
    onSuccess: (project) => {
      setSelectedProjectId(project.id);
      queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
  });

  const deleteProject = useMutation({
    mutationFn: async () => {
      if (!window.confirm("确定删除当前项目及其页、角色和任务记录？")) return;
      return api<{ deleted: string }>(`/api/projects/${selectedProjectId}`, { method: "DELETE" });
    },
    onSuccess: () => {
      setSelectedProjectId(null);
      setSelectedPageId(null);
      setDraft(null);
      queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
  });

  const duplicatePage = useMutation({
    mutationFn: async () => {
      if (!draft) throw new Error("no page selected");
      return api<Page>(`/api/pages/${draft.id}/duplicate`, { method: "POST" });
    },
    onSuccess: (page) => {
      setSelectedPageId(page.id);
      queryClient.invalidateQueries({ queryKey: ["project", selectedProjectId] });
    },
  });

  const generateVariants = useMutation({
    mutationFn: async () => {
      if (!draft) return;
      await savePage.mutateAsync();
      const results = await Promise.all([
        api<{ job_id: string }>(`/api/pages/${draft.id}/generate`, { method: "POST", body: JSON.stringify({ seed: null }) }),
        api<{ job_id: string }>(`/api/pages/${draft.id}/generate`, { method: "POST", body: JSON.stringify({ seed: null }) }),
      ]);
      return results;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      queryClient.invalidateQueries({ queryKey: ["page-variants", selectedPageId] });
      queryClient.invalidateQueries({ queryKey: ["project", selectedProjectId] });
    },
  });

  const selectVariant = useMutation({
    mutationFn: async (imagePath: string) => {
      if (!draft) return;
      return api<Page>(`/api/pages/${draft.id}`, { method: "PATCH", body: JSON.stringify({ image_path: imagePath, status: "done" }) });
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["project", selectedProjectId] }),
  });

  const generateAll = useMutation({
    mutationFn: async () => {
      return api<{ project_id: string; status: string }>(`/api/projects/${selectedProjectId}/generate_all`, {
        method: "POST",
        body: JSON.stringify({}),
      });
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["project", selectedProjectId] }),
  });

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") {
        event.preventDefault();
        if (draft) savePage.mutate();
      }
      if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
        event.preventDefault();
        if (draft?.prompt) generate.mutate();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [draft, generate, savePage]);

  useEffect(() => {
    function onError(event: Event) {
      const detail = (event as CustomEvent<string>).detail;
      setErrorNotice(detail);
      window.setTimeout(() => setErrorNotice(null), 5000);
    }
    window.addEventListener("moss-error", onError);
    return () => window.removeEventListener("moss-error", onError);
  }, []);

  useEffect(() => {
    if (!galleryOpen) return;
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") setGalleryOpen(false);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [galleryOpen]);

  async function exportCurrentProject() {
    if (!selectedProjectId) return;
    const payload = await api<unknown>(`/api/projects/${selectedProjectId}/export`);
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${selectedProjectId}.json`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  function applyPromptPreset() {
    const preset = promptPresetsQuery.data?.find((item) => item.id === selectedPresetId);
    if (!preset || !draft) return;
    setDraft({
      ...draft,
      prompt: [draft.prompt, preset.positive].filter(Boolean).join(", "),
      negative: [draft.negative, preset.negative].filter(Boolean).join(", "),
      seed: preset.seed ?? draft.seed,
    });
  }

  return (
    <div className="flex h-screen flex-col">
      <header className="panel halftone mx-3 mt-3 flex items-center justify-between px-4 py-3">
        <div>
          <h1 className="text-xl font-semibold">分镜台</h1>
          <p className="text-sm opacity-70">项目 → 角色 → 页 → 提示词 → 出图 → 画廊</p>
        </div>
        <div className="mono text-sm">
          <button className="mr-3 border border-white/20 px-3 py-1 text-sm disabled:opacity-40" onClick={() => setGalleryOpen(true)} disabled={!selectedProjectId}>
            打开画廊
          </button>
          <span className={healthQuery.data?.comfy.ok ? "text-emerald-300" : "accent"}>
            ComfyUI {healthQuery.data?.comfy.ok ? "在线" : "离线"}
          </span>
          <span className="mx-2 opacity-40">|</span>
          <span>{healthQuery.data ? `${healthQuery.data.entries.usable}/${healthQuery.data.entries.total} 可用` : "加载中"}</span>
          <span className="mx-2 opacity-40">|</span>
          <span>{healthQuery.data?.release || "-"}</span>
        </div>
      </header>

      <main className="grid min-h-0 flex-1 grid-cols-[320px_minmax(0,1fr)_380px] gap-3 overflow-hidden p-3">
        <section className="panel overflow-hidden p-3">
          <div className="mb-3 flex gap-2">
            <input
              className="min-w-0 flex-1 bg-transparent px-2 py-1 outline-none placeholder:opacity-40"
              value={projectTitle}
              onChange={(event) => setProjectTitle(event.target.value)}
              placeholder="漫画标题"
            />
            <button className="border border-[#e4572e] px-3 py-1 text-[#e4572e]" onClick={() => createProject.mutate(projectTitle)}>
              新建
            </button>
          </div>

          <div className="mb-3 flex gap-2">
            <button className="border border-white/20 px-3 py-1 text-sm disabled:opacity-40" onClick={exportCurrentProject} disabled={!selectedProjectId}>
              导出
            </button>
            <label className="cursor-pointer border border-white/20 px-3 py-1 text-sm">
              导入
              <input
                type="file"
                accept="application/json,.json"
                className="hidden"
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  if (file) importProject.mutate(file);
                  event.currentTarget.value = "";
                }}
              />
            </label>
          </div>

          <div className="mb-3 max-h-40 overflow-auto">
            {projectsQuery.data?.map((item) => (
              <button
                key={item.id}
                className={`mb-1 flex w-full items-center gap-2 px-2 py-1 text-left ${selectedProjectId === item.id ? "bg-white/10" : "hover:bg-white/5"}`}
                onClick={() => setSelectedProjectId(item.id)}
              >
                {item.thumbnail_url ? (
                  <img src={item.thumbnail_url} alt={item.title} className="h-10 w-7 object-cover" />
                ) : (
                  <div className="h-10 w-7 border border-white/15" />
                )}
                <span className="min-w-0 flex-1 truncate">{item.title}</span>
                <span className="opacity-50">({item.page_count || 0})</span>
              </button>
            ))}
          </div>

          <label className="mb-2 block text-sm opacity-70">
            风格预设
            <select
              className="mt-1 w-full bg-black/20 px-2 py-1 outline-none disabled:opacity-40"
              value={stylePresetId}
              disabled={!selectedProjectId}
              onChange={(event) => setStylePresetId(event.target.value)}
            >
              {stylePresetsQuery.data?.map((preset) => (
                <option key={preset.id} value={preset.id}>
                  {preset.name}
                </option>
              ))}
            </select>
          </label>
          <button
            className="mb-3 border border-white/20 px-3 py-1 text-sm disabled:opacity-40"
            disabled={!selectedProjectId}
            onClick={() => updateProject.mutate({ style_preset_id: stylePresetId })}
          >
            应用风格
          </button>

          <div className="mb-3 border-t border-white/10 pt-3">
            <div className="mb-2 text-sm opacity-70">角色圣经</div>
            <div className="mb-2 max-h-24 overflow-auto text-xs">
              {charactersQuery.data?.map((character) => (
                <div key={character.id} className="mb-1 truncate border-b border-white/10 py-1">
                  <span className="font-medium">{character.name}</span>
                  <span className="mono ml-2 opacity-60">{character.anchor_tags}</span>
                </div>
              ))}
              {!charactersQuery.data?.length && <div className="opacity-40">暂无角色</div>}
            </div>
            <input
              className="mb-1 w-full bg-black/20 px-2 py-1 text-sm outline-none"
              value={characterName}
              onChange={(event) => setCharacterName(event.target.value)}
              placeholder="角色名"
              disabled={!selectedProjectId}
            />
            <textarea
              className="mono mb-2 h-16 w-full resize-none bg-black/20 p-2 text-xs outline-none"
              value={characterAnchor}
              onChange={(event) => setCharacterAnchor(event.target.value)}
              placeholder="角色锚点 tag"
              disabled={!selectedProjectId}
            />
            <button className="border border-white/20 px-3 py-1 text-sm disabled:opacity-40" onClick={() => upsertCharacter.mutate()} disabled={!selectedProjectId}>
              保存角色
            </button>
          </div>

          <textarea
            className="serif mb-3 h-40 w-full resize-none bg-black/20 p-2 outline-none"
            value={storyDraft}
            onChange={(event) => setStoryDraft(event.target.value)}
            placeholder="故事梗概"
            disabled={!selectedProjectId}
          />
          <div className="mb-4 flex flex-wrap gap-2">
            <button className="border border-white/20 px-3 py-1 disabled:opacity-40" onClick={() => saveStory.mutate()} disabled={!selectedProjectId}>
              保存故事
            </button>
            <button className="border border-white/20 px-3 py-1 disabled:opacity-40" onClick={() => addPage.mutate()} disabled={!selectedProjectId}>
              加一页
            </button>
            <button className="border border-[#e4572e] px-3 py-1 text-[#e4572e] disabled:opacity-40" onClick={() => generateAll.mutate()} disabled={!selectedProjectId}>
              批量生成
            </button>
            <button className="border border-white/20 px-3 py-1 text-red-300 disabled:opacity-40" onClick={() => deleteProject.mutate()} disabled={!selectedProjectId}>
              删除项目
            </button>
          </div>

          <div className="max-h-56 overflow-auto">
            {pages.map((page, index) => (
              <div key={page.id} className={`mb-1 flex items-center justify-between px-2 py-1 ${selectedPageId === page.id ? "bg-white/10" : "hover:bg-white/5"}`}>
                <button className="min-w-0 flex-1 truncate text-left" onClick={() => setSelectedPageId(page.id)}>
                  第 {page.order_no} 页
                </button>
                <div className="flex items-center gap-1">
                  <span className="mono text-xs opacity-60">{page.status}</span>
                  <button
                    className="border border-white/20 px-1 text-xs disabled:opacity-30"
                    disabled={index === 0 || reorderPages.isPending}
                    onClick={() => {
                      const ids = pages.map((item) => item.id);
                      [ids[index - 1], ids[index]] = [ids[index], ids[index - 1]];
                      reorderPages.mutate(ids);
                    }}
                  >
                    ↑
                  </button>
                  <button
                    className="border border-white/20 px-1 text-xs disabled:opacity-30"
                    disabled={index === pages.length - 1 || reorderPages.isPending}
                    onClick={() => {
                      const ids = pages.map((item) => item.id);
                      [ids[index + 1], ids[index]] = [ids[index], ids[index + 1]];
                      reorderPages.mutate(ids);
                    }}
                  >
                    ↓
                  </button>
                  <button
                    className="border border-white/20 px-1 text-xs disabled:opacity-30"
                    disabled={pages.length <= 1 || deletePage.isPending}
                    onClick={() => deletePage.mutate(page.id)}
                  >
                    ×
                  </button>
                </div>
              </div>
            ))}
          </div>

          <div className="mb-2 flex items-center justify-between">
            <span className="text-sm opacity-70">画廊</span>
            <div className="flex gap-1 text-xs">
              <button
                className={`border px-2 py-1 ${gallerySort === "order" ? "border-[#e4572e] text-[#e4572e]" : "border-white/20"}`}
                onClick={() => setGallerySort("order")}
              >
                内容
              </button>
              <button
                className={`border px-2 py-1 ${gallerySort === "time" ? "border-[#e4572e] text-[#e4572e]" : "border-white/20"}`}
                onClick={() => setGallerySort("time")}
              >
                时间
              </button>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-2">
            {galleryPages.map((page) => (
              <a key={page.id} href={page.image_url || "#"} target="_blank" className="block border border-white/15">
                <img src={page.image_url || undefined} alt={`第 ${page.order_no} 页`} className="aspect-[9/16] w-full object-cover" />
              </a>
            ))}
          </div>
        </section>

        <section className="panel overflow-auto p-4">
          {!draft ? (
            <div className="mt-20 text-center opacity-50">选择或新建一页</div>
          ) : (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-semibold">第 {draft.order_no} 页</h2>
                <span className="mono text-sm opacity-60">{draft.status}</span>
              </div>

              <label className="block">
                <span className="mb-1 block text-sm opacity-70">页面摘要</span>
                <textarea
                  className="serif h-24 w-full resize-none bg-black/20 p-2 outline-none"
                  value={draft.summary}
                  onChange={(event) => setDraft({ ...draft, summary: event.target.value })}
                />
              </label>

              <label className="block">
                <span className="mb-1 block text-sm opacity-70">版式/镜头</span>
                <textarea
                  className="h-20 w-full resize-none bg-black/20 p-2 outline-none"
                  value={draft.layout_note}
                  onChange={(event) => setDraft({ ...draft, layout_note: event.target.value })}
                />
              </label>

              <div className="mb-3">
                <span className="mb-1 block text-sm opacity-70">本页角色</span>
                <div className="flex flex-wrap gap-3 text-sm">
                  {charactersQuery.data?.map((character) => (
                    <label key={character.id} className="flex items-center gap-1">
                      <input
                        type="checkbox"
                        checked={(draft.character_ids || []).includes(character.id)}
                        onChange={(event) => {
                          const current = draft.character_ids || [];
                          setDraft({
                            ...draft,
                            character_ids: event.target.checked
                              ? [...current, character.id]
                              : current.filter((id) => id !== character.id),
                          });
                        }}
                      />
                      {character.name}
                    </label>
                  ))}
                  {!charactersQuery.data?.length && <span className="opacity-40">暂无角色</span>}
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2">
                {[
                  ["location", "地点"],
                  ["time", "时间"],
                  ["outfit", "服装"],
                  ["injuries", "伤势"],
                  ["props", "道具"],
                  ["mood", "情绪"],
                ].map(([key, label]) => (
                  <label key={key} className="block">
                    <span className="mb-1 block text-sm opacity-70">{label}</span>
                    <input
                      className="w-full bg-black/20 px-2 py-1 outline-none"
                      value={draft.continuity?.[key] || ""}
                      onChange={(event) =>
                        setDraft({
                          ...draft,
                          continuity: { ...(draft.continuity || {}), [key]: event.target.value },
                        })
                      }
                    />
                  </label>
                ))}
              </div>

              <div>
                <span className="mb-1 block text-sm opacity-70">法典 refs</span>
                <div className="flex flex-wrap gap-2">
                  {draft.refs.map((ref) => {
                    const detail = draft.ref_details.find((item) => item.id === ref);
                    return (
                      <button
                        key={ref}
                        className="mono border border-white/20 px-2 py-1 text-xs hover:border-[#e4572e]"
                        onClick={() =>
                          setDraft({
                            ...draft,
                            refs: draft.refs.filter((item) => item !== ref),
                            ref_details: draft.ref_details.filter((item) => item.id !== ref),
                          })
                        }
                      >
                        {detail?.title || ref} ×
                      </button>
                    );
                  })}
                  {draft.refs.length === 0 && <span className="opacity-40">从右侧法典抽屉加入</span>}
                </div>
              </div>

              <label className="block">
                <span className="mb-1 block text-sm opacity-70">正向提示词</span>
                <textarea
                  className="mono h-36 w-full resize-none bg-black/20 p-2 text-sm outline-none"
                  value={draft.prompt}
                  onChange={(event) => setDraft({ ...draft, prompt: event.target.value })}
                />
              </label>

              <label className="block">
                <span className="mb-1 block text-sm opacity-70">负向提示词</span>
                <textarea
                  className="mono h-24 w-full resize-none bg-black/20 p-2 text-sm outline-none"
                  value={draft.negative}
                  onChange={(event) => setDraft({ ...draft, negative: event.target.value })}
                />
              </label>

              <label className="block">
                <span className="mb-1 block text-sm opacity-70">Seed</span>
                <div className="flex gap-2">
                  <input
                    className="mono w-40 bg-black/20 px-2 py-1 outline-none"
                    type="number"
                    value={draft.seed ?? ""}
                    onChange={(event) => setDraft({ ...draft, seed: event.target.value ? Number(event.target.value) : null })}
                  />
                  <button
                    className="border border-white/20 px-3 py-1 text-sm"
                    onClick={() => setDraft({ ...draft, seed: Math.floor(Math.random() * 1_000_000_000_000_000) })}
                  >
                    随机
                  </button>
                </div>
              </label>

              <div className="flex flex-wrap items-center gap-2">
                <select
                  className="min-w-[180px] bg-black/20 px-2 py-1 text-sm outline-none"
                  value={selectedPresetId}
                  onChange={(event) => setSelectedPresetId(event.target.value)}
                >
                  <option value="">选择提示词预设</option>
                  {promptPresetsQuery.data?.map((preset) => (
                    <option key={preset.id} value={preset.id}>
                      {preset.name} / {preset.kind}
                    </option>
                  ))}
                </select>
                <button className="border border-white/20 px-3 py-1 text-sm disabled:opacity-40" onClick={applyPromptPreset} disabled={!selectedPresetId}>
                  应用预设
                </button>
              </div>

              <div className="flex flex-wrap gap-2">
                <button className="border border-white/20 px-3 py-1" onClick={() => savePage.mutate()}>
                  保存
                </button>
                <button className="border border-white/20 px-3 py-1" onClick={() => compose.mutate()}>
                  编译提示词
                </button>
                <button className="border border-white/20 px-3 py-1" onClick={() => duplicatePage.mutate()}>
                  复制本页
                </button>
                <button className="border border-[#e4572e] px-3 py-1 text-[#e4572e]" onClick={() => generate.mutate()}>
                  生成本页
                </button>
                <button
                  className="border border-white/20 px-3 py-1 disabled:opacity-40"
                  onClick={() => draft.image_path && generate.mutate(draft.image_path)}
                  disabled={!draft.image_path}
                >
                  图生图重绘
                </button>
              </div>

              {lastCompose && (
                <div className="mono text-xs opacity-70">
                  正向 {lastCompose.positive_count ?? 0} 个 tag，负向 {lastCompose.negative_count ?? 0} 个 tag；过滤/跳过 {lastCompose.dropped.length} 项：{lastCompose.dropped.map((item) => `${item.id}:${item.reason}`).join(", ")}
                </div>
              )}

              {jobQuery.data && (
                <div className="panel p-3">
                  <div className="mono text-sm">任务 {jobQuery.data.id}: {jobQuery.data.status}</div>
                  {jobQuery.data.error && <div className="accent mt-2 text-sm">{jobQuery.data.error}</div>}
                  {jobQuery.data.output_path && <div className="mt-2 break-all text-xs opacity-70">{jobQuery.data.output_path}</div>}
                </div>
              )}

              {draft.image_url && (
                <a href={draft.image_url} target="_blank" className="block max-w-[420px] border border-white/15">
                  <img src={draft.image_url} alt="页面预览" className="w-full" />
                </a>
              )}

              <div className="border-t border-white/10 pt-3">
                <div className="mb-2 flex items-center justify-between">
                  <span className="text-sm opacity-70">变体</span>
                  <button className="border border-white/20 px-3 py-1 text-sm disabled:opacity-40" onClick={() => generateVariants.mutate()} disabled={!draft.prompt || generateVariants.isPending}>
                    生成两个变体
                  </button>
                </div>
                <div className="grid grid-cols-3 gap-2">
                  {variantsQuery.data?.map((variant) => (
                    <button
                      key={variant.id}
                      className="border border-white/15 disabled:opacity-40"
                      disabled={!variant.output_path}
                      onClick={() => variant.output_path && selectVariant.mutate(variant.output_path)}
                    >
                      {variant.image_url && <img src={variant.image_url} alt={`seed ${variant.seed}`} className="aspect-[9/16] w-full object-cover" />}
                      <div className="mono p-1 text-xs opacity-70">seed {variant.seed ?? "-"}</div>
                    </button>
                  ))}
                  {!variantsQuery.data?.length && <div className="opacity-40">暂无变体</div>}
                </div>
              </div>
            </div>
          )}
        </section>

        <section className="panel overflow-hidden p-3">
          <select
            className="mb-2 w-full bg-black/20 px-2 py-1 text-sm outline-none"
            value={codexFilter}
            onChange={(event) => setCodexFilter(event.target.value)}
          >
            <option value="">全部法典</option>
            {codexesQuery.data?.map((codex) => (
              <option key={codex.id} value={codex.id}>
                {codex.title} ({codex.entry_count})
              </option>
            ))}
          </select>

          <select
            className="mb-2 w-full bg-black/20 px-2 py-1 text-sm outline-none disabled:opacity-40"
            value={categoryFilter}
            disabled={!codexFilter}
            onChange={(event) => setCategoryFilter(event.target.value)}
          >
            <option value="">全部分类</option>
            {flattenCategories(categoriesQuery.data).map((category) => (
              <option key={category.name} value={category.name}>
                {category.label} ({category.count})
              </option>
            ))}
          </select>

          <div className="mb-3 flex gap-2">
            <input
              className="min-w-0 flex-1 bg-transparent px-2 py-1 outline-none placeholder:opacity-40"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="搜索法典 tag / 中文"
              list="tag-suggestions"
            />
          </div>
          <datalist id="tag-suggestions">
            {suggestionsQuery.data?.map((item) => (
              <option key={item.tag} value={item.tag} />
            ))}
          </datalist>
          <label className="mb-3 flex items-center gap-2 text-xs opacity-70">
            <input type="checkbox" checked={includeNsfw} onChange={(event) => setIncludeNsfw(event.target.checked)} />
            显示 R18（本地个人使用）
          </label>

          <div className="max-h-[calc(100vh-170px)] overflow-auto">
            {codexQuery.data?.map((entry) => (
              <div key={entry.id} className="panel mb-2 p-2">
                <div className="flex gap-2">
                  {entry.image_url && <img src={`/api/codex/entries/${entry.id}/thumbnail`} alt={entry.title} className="h-24 w-16 object-cover" />}
                  <div className="min-w-0 flex-1">
                    <div className="truncate font-medium">{entry.title}</div>
                    <div className="mono text-xs opacity-60">{entry.id}</div>
                    <div className="mono mt-1 line-clamp-3 text-xs opacity-80">{entry.tags_positive}</div>
                    <button
                      className="mt-2 border border-white/20 px-2 py-1 text-xs hover:border-[#e4572e] disabled:opacity-40"
                      disabled={!draft || draft.refs.includes(entry.id)}
                      onClick={() =>
                        draft &&
                        setDraft({
                          ...draft,
                          refs: [...draft.refs, entry.id],
                          ref_details: [...draft.ref_details, { id: entry.id, title: entry.title, tags_positive: entry.tags_positive, image_url: entry.image_url }],
                        })
                      }
                    >
                      {draft?.refs.includes(entry.id) ? "已加入" : "加入本页"}
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </section>
      </main>

      <footer className="panel mx-3 mb-3 p-3">
        <div className="mb-2 flex items-center justify-between">
          <span className="text-sm opacity-70">任务队列</span>
          <span className="mono text-xs opacity-50">{jobsQuery.data?.length || 0} 条</span>
        </div>
        <div className="mono max-h-36 overflow-auto text-xs">
          {jobsQuery.data?.map((job) => (
            <div key={job.id} className="mb-1 flex items-center justify-between border-b border-white/10 py-1">
              <span>
                {job.project_id.slice(0, 6)} / 第 {job.order_no} 页 / seed {job.seed ?? "-"}
              </span>
              <span className={job.status === "succeeded" ? "text-emerald-300" : job.status === "failed" ? "accent" : "opacity-70"}>
                {job.status}
              </span>
            </div>
          ))}
          {!jobsQuery.data?.length && <div className="opacity-40">暂无任务</div>}
        </div>
      </footer>

      {galleryOpen && (
        <div className="fixed inset-0 z-50 bg-black/85 p-6">
          <div className="mx-auto flex h-full max-w-7xl flex-col">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold">画廊</h2>
              <div className="flex gap-2">
                <button
                  className={`border px-3 py-1 text-sm ${gallerySort === "order" ? "border-[#e4572e] text-[#e4572e]" : "border-white/20"}`}
                  onClick={() => setGallerySort("order")}
                >
                  内容
                </button>
                <button
                  className={`border px-3 py-1 text-sm ${gallerySort === "time" ? "border-[#e4572e] text-[#e4572e]" : "border-white/20"}`}
                  onClick={() => setGallerySort("time")}
                >
                  时间
                </button>
                <button className="border border-white/20 px-3 py-1 text-sm" onClick={() => setGalleryOpen(false)}>
                  关闭
                </button>
              </div>
            </div>
            <div className="min-h-0 flex-1 overflow-auto">
              <div className="grid grid-cols-2 gap-4 md:grid-cols-4 xl:grid-cols-6">
                {galleryPages.map((page) => (
                  <a key={page.id} href={page.image_url || "#"} target="_blank" className="block border border-white/15">
                    <img src={page.image_url || undefined} alt={`第 ${page.order_no} 页`} className="aspect-[9/16] w-full object-cover" />
                    <div className="mono p-2 text-xs opacity-70">第 {page.order_no} 页</div>
                  </a>
                ))}
                {!galleryPages.length && <div className="opacity-40">暂无已生成页面</div>}
              </div>
            </div>
          </div>
        </div>
      )}

      {errorNotice && (
        <div className="fixed bottom-4 right-4 max-w-sm border border-[#e4572e] bg-black/85 p-3 text-sm text-[#ffb4a0]">
          {errorNotice}
        </div>
      )}
    </div>
  );
}

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  api,
  type CodexEntry,
  type Job,
  type Page,
  type Project,
  type PromptPreset,
  type StoryboardTask,
  type StoryboardTaskDetail,
} from "../api";

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

type LibraryCategory = { id: string; name: string; count: number };

function pageSignature(page: Page) {
  return JSON.stringify({
    summary: page.summary,
    layout_note: page.layout_note,
    prompt: page.prompt,
    negative: page.negative,
    seed: page.seed,
    refs: page.refs,
    continuity: page.continuity,
    character_ids: page.character_ids,
  });
}

export default function StoryboardPage() {
  const queryClient = useQueryClient();
  const [searchParams] = useSearchParams();
  const [projectId, setProjectId] = useState(searchParams.get("project") || "");
  const [taskId, setTaskId] = useState(searchParams.get("task") || "");
  const [pageId, setPageId] = useState(searchParams.get("page") || "");
  const [draft, setDraft] = useState<Page | null>(null);
  const [loadedPageId, setLoadedPageId] = useState("");
  const [savedSignature, setSavedSignature] = useState("");
  const [saveState, setSaveState] = useState<"saved" | "dirty" | "saving">("saved");
  const savingRef = useRef<Promise<boolean> | null>(null);
  const saveSeqRef = useRef(0);
  const latestRef = useRef<{ draft: Page | null; savedSignature: string }>({ draft: null, savedSignature: "" });
  const [selectedPages, setSelectedPages] = useState<string[]>([]);
  const [tab, setTab] = useState<"content" | "prompt" | "render">("content");
  const [codexOpen, setCodexOpen] = useState(false);
  const [libraryDomain, setLibraryDomain] = useState<"regular" | "nsfw" | "reference">("regular");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [query, setQuery] = useState("");
  const [selectedPresetId, setSelectedPresetId] = useState("");
  const [lastCompose, setLastCompose] = useState<ComposeResult | null>(null);
  const [notice, setNotice] = useState("");
  const [errorNotice, setErrorNotice] = useState<string | null>(null);

  latestRef.current = { draft, savedSignature };

  const healthQuery = useQuery({
    queryKey: ["health"],
    queryFn: () => api<Health>("/api/health"),
    refetchInterval: 5000,
  });
  const projectsQuery = useQuery({
    queryKey: ["projects"],
    queryFn: () => api<Project[]>("/api/projects"),
  });
  const tasksQuery = useQuery({
    queryKey: ["tasks", projectId],
    queryFn: () => api<StoryboardTask[]>(`/api/projects/${projectId}/tasks`),
    enabled: !!projectId,
    refetchInterval: 5000,
  });
  const taskQuery = useQuery({
    queryKey: ["task", taskId],
    queryFn: () => api<StoryboardTaskDetail>(`/api/tasks/${taskId}`),
    enabled: !!taskId,
    refetchInterval: (state) => {
      const pages = state.state.data?.pages || [];
      return pages.some((page) => page.status === "queued" || page.status === "running") ? 3000 : false;
    },
  });
  const categoriesQuery = useQuery({
    queryKey: ["library-categories", libraryDomain],
    queryFn: () => api<LibraryCategory[]>(`/api/library/categories?domain=${libraryDomain}`),
    enabled: codexOpen,
  });
  const suggestionsQuery = useQuery({
    queryKey: ["codex-suggest", query],
    queryFn: () => api<{ tag: string; count: number }[]>(`/api/codex/suggest?q=${encodeURIComponent(query)}&limit=20`),
    enabled: codexOpen && query.trim().length > 0,
  });
  const codexQuery = useQuery({
    queryKey: ["codex", query, libraryDomain, categoryFilter],
    queryFn: () =>
      api<CodexEntry[]>(
        `/api/codex/search?q=${encodeURIComponent(query)}&domain=${libraryDomain}&include_nsfw=${
          libraryDomain !== "regular"
        }&include_artist_only=${libraryDomain === "reference"}&limit=20${
          categoryFilter ? `&category_id=${encodeURIComponent(categoryFilter)}` : ""
        }`,
      ),
    enabled: codexOpen && (query.trim().length > 0 || !!categoryFilter),
  });
  const promptPresetsQuery = useQuery({
    queryKey: ["prompt-presets"],
    queryFn: () => api<PromptPreset[]>("/api/presets"),
  });
  const projectPresetsQuery = useQuery({
    queryKey: ["project-presets", projectId],
    queryFn: () => api<PromptPreset[]>(`/api/projects/${projectId}/presets`),
    enabled: !!projectId,
  });
  const variantsQuery = useQuery({
    queryKey: ["page-variants", pageId],
    queryFn: () => api<{ id: string; seed: number | null; output_path: string | null; image_url: string | null }[]>(`/api/pages/${pageId}/variants`),
    enabled: !!pageId,
  });
  const jobsQuery = useQuery({
    queryKey: ["jobs"],
    queryFn: () => api<Job[]>("/api/jobs?limit=20"),
    refetchInterval: 3000,
  });

  const projects = projectsQuery.data || [];
  const tasks = tasksQuery.data || [];
  const task = taskQuery.data;
  const pages = task?.pages || [];
  const selectedPage = pages.find((page) => page.id === pageId) || pages[0] || null;
  const selectedPageLive = selectedPage;

  useEffect(() => {
    if (!projects.length) {
      setProjectId("");
      return;
    }
    if (!projects.some((item) => item.id === projectId)) setProjectId(projects[0].id);
  }, [projects, projectId]);

  useEffect(() => {
    if (!tasks.length) {
      setTaskId("");
      return;
    }
    if (!tasks.some((item) => item.id === taskId)) setTaskId(tasks[0].id);
  }, [tasks, taskId]);

  useEffect(() => {
    if (task && !pages.length && pageId) setPageId("");
  }, [task?.id, pages.length, pageId]);

  useEffect(() => {
    if (selectedPage && selectedPage.id !== pageId) setPageId(selectedPage.id);
  }, [selectedPage?.id, pageId]);

  useEffect(() => {
    setSelectedPages((current) => current.filter((id) => pages.some((page) => page.id === id)));
  }, [pages]);

  useEffect(() => {
    if (!selectedPage) {
      setDraft(null);
      setLoadedPageId("");
      setSavedSignature("");
      setSaveState("saved");
      return;
    }
    if (selectedPage.id === loadedPageId) return;
    setDraft(selectedPage);
    setLoadedPageId(selectedPage.id);
    setSavedSignature(pageSignature(selectedPage));
    setSaveState("saved");
  }, [selectedPage?.id, loadedPageId]);

  useEffect(() => {
    if (!selectedPage || !draft || selectedPage.id !== draft.id) return;
    if (pageSignature(draft) !== savedSignature) return;
    const incoming = pageSignature(selectedPage);
    if (incoming !== savedSignature) {
      setDraft(selectedPage);
      setSavedSignature(incoming);
      setSaveState("saved");
    }
  }, [selectedPage, draft, savedSignature]);

  useEffect(() => {
    setCategoryFilter("");
  }, [libraryDomain]);

  function showNotice(text: string) {
    setNotice(text);
    window.setTimeout(() => setNotice(""), 3200);
  }

  async function persistPage(page: Page): Promise<boolean> {
    const signature = pageSignature(page);
    const seq = ++saveSeqRef.current;
    setSaveState("saving");
    const request = api<Page>(`/api/pages/${page.id}`, {
      method: "PATCH",
      body: JSON.stringify({
        summary: page.summary,
        layout_note: page.layout_note,
        prompt: page.prompt,
        negative: page.negative,
        refs: page.refs,
        continuity: page.continuity,
        character_ids: page.character_ids,
        seed: page.seed,
      }),
    })
      .then(() => {
        setSavedSignature(signature);
        latestRef.current = { ...latestRef.current, savedSignature: signature };
        const latest = latestRef.current.draft;
        setSaveState(latest && pageSignature(latest) === signature ? "saved" : "dirty");
        queryClient.invalidateQueries({ queryKey: ["task", taskId] });
        queryClient.invalidateQueries({ queryKey: ["tasks", projectId] });
        return true;
      })
      .catch(() => {
        setSaveState("dirty");
        return false;
      })
      .finally(() => {
        if (saveSeqRef.current === seq) savingRef.current = null;
      });
    savingRef.current = request;
    return request;
  }

  useEffect(() => {
    if (!draft || loadedPageId !== draft.id) return;
    if (pageSignature(draft) === savedSignature) return;
    setSaveState("dirty");
    if (savingRef.current) return;
    const timer = window.setTimeout(() => {
      if (!savingRef.current) void persistPage(draft);
    }, 800);
    return () => window.clearTimeout(timer);
  }, [draft, savedSignature, loadedPageId, pageId, taskId, projectId]);

  async function flushDraft(): Promise<boolean> {
    if (savingRef.current) await savingRef.current;
    const latest = latestRef.current.draft;
    if (!latest || pageSignature(latest) === latestRef.current.savedSignature) return true;
    if (savingRef.current) await savingRef.current;
    return persistPage(latest);
  }

  useEffect(() => {
    function flushOnExit() {
      const latest = latestRef.current.draft;
      if (!latest || pageSignature(latest) === latestRef.current.savedSignature) return;
      fetch(`/api/pages/${latest.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          summary: latest.summary,
          layout_note: latest.layout_note,
          prompt: latest.prompt,
          negative: latest.negative,
          refs: latest.refs,
          continuity: latest.continuity,
          character_ids: latest.character_ids,
          seed: latest.seed,
        }),
        keepalive: true,
      }).catch(() => undefined);
    }
    window.addEventListener("beforeunload", flushOnExit);
    return () => {
      window.removeEventListener("beforeunload", flushOnExit);
      flushOnExit();
    };
  }, []);

  useEffect(() => {
    function onError(event: Event) {
      const detail = (event as CustomEvent<string>).detail;
      setErrorNotice(detail);
      window.setTimeout(() => setErrorNotice(null), 5000);
    }
    window.addEventListener("moss-error", onError);
    return () => window.removeEventListener("moss-error", onError);
  }, []);

  async function selectProject(id: string) {
    if (id === projectId) return;
    if (!(await flushDraft())) {
      showNotice("保存失败，已取消切换");
      return;
    }
    setProjectId(id);
    setTaskId("");
    setPageId("");
    setSelectedPages([]);
  }

  async function selectTask(id: string) {
    if (id === taskId) return;
    if (!(await flushDraft())) {
      showNotice("保存失败，已取消切换");
      return;
    }
    setTaskId(id);
    setPageId("");
    setSelectedPages([]);
  }

  async function selectPage(id: string) {
    if (id === pageId) return;
    if (!(await flushDraft())) {
      showNotice("保存失败，已取消切换");
      return;
    }
    setPageId(id);
  }

  const addPage = useMutation({
    mutationFn: () => api<Page>(`/api/tasks/${taskId}/pages`, { method: "POST" }),
    onSuccess: async (page) => {
      await queryClient.invalidateQueries({ queryKey: ["task", taskId] });
      await queryClient.invalidateQueries({ queryKey: ["tasks", projectId] });
      setPageId(page.id);
    },
  });

  const deletePages = useMutation({
    mutationFn: async (ids: string[]) => {
      for (const id of ids) await api(`/api/pages/${id}`, { method: "DELETE" });
      return ids;
    },
    onSuccess: async (ids) => {
      setSelectedPages([]);
      if (ids.includes(pageId)) setPageId("");
      await queryClient.invalidateQueries({ queryKey: ["task", taskId] });
      await queryClient.invalidateQueries({ queryKey: ["tasks", projectId] });
      queryClient.invalidateQueries({ queryKey: ["gallery-files"] });
      showNotice(`已删除 ${ids.length} 页`);
    },
  });

  const generatePage = useMutation({
    mutationFn: async (id: string) => {
      await flushDraft();
      return api<{ job_id: string }>(`/api/pages/${id}/generate`, { method: "POST", body: JSON.stringify({}) });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["task", taskId] });
      queryClient.invalidateQueries({ queryKey: ["tasks", projectId] });
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      queryClient.invalidateQueries({ queryKey: ["page-variants", pageId] });
    },
  });

  const regeneratePage = useMutation({
    mutationFn: async () => {
      if (!selectedPageLive?.image_path) throw new Error("no image");
      await flushDraft();
      return api<{ job_id: string }>(`/api/pages/${selectedPageLive.id}/generate`, {
        method: "POST",
        body: JSON.stringify({ init_image_path: selectedPageLive.image_path }),
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["task", taskId] });
      queryClient.invalidateQueries({ queryKey: ["tasks", projectId] });
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
    },
  });

  const generateSelected = useMutation({
    mutationFn: async (ids: string[]) => {
      await flushDraft();
      for (const id of ids) {
        await api(`/api/pages/${id}/generate`, { method: "POST", body: JSON.stringify({}) });
      }
      return ids;
    },
    onSuccess: (ids) => {
      queryClient.invalidateQueries({ queryKey: ["task", taskId] });
      queryClient.invalidateQueries({ queryKey: ["tasks", projectId] });
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      showNotice(`已入队 ${ids.length} 页`);
    },
  });

  const generateTask = useMutation({
    mutationFn: async () => {
      await flushDraft();
      return api<{ page_ids: string[]; status: string }>(`/api/tasks/${taskId}/generate`, { method: "POST", body: JSON.stringify({}) });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["task", taskId] });
      queryClient.invalidateQueries({ queryKey: ["tasks", projectId] });
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      showNotice("任务已加入生成队列");
    },
  });

  const compose = useMutation({
    mutationFn: async () => {
      const page = latestRef.current.draft || selectedPage;
      if (!page) return null;
      await flushDraft();
      return api<ComposeResult>(`/api/pages/${page.id}/compose`, {
        method: "POST",
        body: JSON.stringify({
          entry_ids: page.refs,
          character_ids: page.character_ids || [],
          page_text: `${page.summary} ${page.layout_note}`.trim(),
          save: true,
        }),
      });
    },
    onSuccess: (result) => {
      const current = latestRef.current.draft;
      if (result && current) {
        const next = { ...current, prompt: result.positive, negative: result.negative };
        setDraft(next);
        setSavedSignature(pageSignature(next));
        setSaveState("saved");
      }
      if (result) setLastCompose(result);
      queryClient.invalidateQueries({ queryKey: ["task", taskId] });
      queryClient.invalidateQueries({ queryKey: ["tasks", projectId] });
    },
  });

  const selectVariant = useMutation({
    mutationFn: (imagePath: string) => api<Page>(`/api/pages/${pageId}`, { method: "PATCH", body: JSON.stringify({ image_path: imagePath, status: "done" }) }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["task", taskId] });
      queryClient.invalidateQueries({ queryKey: ["tasks", projectId] });
    },
  });

  const saveAsPreset = useMutation({
    mutationFn: () => {
      if (!draft) throw new Error("no page");
      return api<PromptPreset>("/api/presets", {
        method: "POST",
        body: JSON.stringify({
          name: `${task?.title || "分镜"} 第${draft.shot_no || draft.order_no}页`,
          kind: "combination",
          positive: draft.prompt,
          negative: draft.negative,
          seed: draft.seed,
          preview_image: draft.image_url,
          notes: draft.summary,
        }),
      });
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["prompt-presets"] }),
  });

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

  function addCodexEntry(entry: CodexEntry) {
    if (!draft || draft.refs.includes(entry.id)) return;
    setDraft({
      ...draft,
      refs: [...draft.refs, entry.id],
      ref_details: [...draft.ref_details, { id: entry.id, title: entry.title, tags_positive: entry.tags_positive, image_url: entry.image_url }],
    });
  }

  function toggleSelectedPage(id: string) {
    setSelectedPages((current) => (current.includes(id) ? current.filter((item) => item !== id) : [...current, id]));
  }

  function toggleAllPages() {
    setSelectedPages(selectedPages.length === pages.length ? [] : pages.map((page) => page.id));
  }

  function requestDelete(ids: string[]) {
    if (!ids.length) return;
    if (window.confirm(`删除选中的 ${ids.length} 页？对应图片会移入回收目录。`)) deletePages.mutate(ids);
  }

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") {
        event.preventDefault();
        void flushDraft();
      }
      if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
        event.preventDefault();
        if (selectedPage) generatePage.mutate(selectedPage.id);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [selectedPage?.id, selectedPage?.prompt]);

  return (
    <div className="flex h-screen flex-col">
      <header className="panel halftone m-3 flex flex-wrap items-center justify-between gap-3 px-4 py-3">
        <div>
          <h1 className="text-xl font-semibold">分镜台</h1>
          <p className="text-sm opacity-70">分镜任务 → 页 → 提示词 / 画风 / 角色一致性 → 出图</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <select className="bg-black/20 px-3 py-2 text-sm outline-none" value={projectId} onChange={(event) => void selectProject(event.target.value)}>
            {projects.map((item) => (
              <option key={item.id} value={item.id}>
                [{item.mode === "illustration" ? "插图" : "漫画"}] {item.title}
              </option>
            ))}
          </select>
          <a className="border border-white/20 px-3 py-2 text-sm" href={`/scenes?project=${projectId}`}>
            场景拆分
          </a>
          <button className="border border-white/20 px-3 py-2 text-sm" onClick={() => setCodexOpen(true)} disabled={!selectedPage}>
            法典
          </button>
          <span className="mono text-xs">
            <span className={healthQuery.data?.comfy.ok ? "text-emerald-300" : "accent"}>
              ComfyUI {healthQuery.data?.comfy.ok ? "在线" : "离线"}
            </span>
            <span className="mx-2 opacity-40">|</span>
            {healthQuery.data ? `${healthQuery.data.entries.usable}/${healthQuery.data.entries.total}` : "加载中"}
          </span>
          {notice && <span className="mono text-xs text-[#ffb4a0]">{notice}</span>}
        </div>
      </header>

      <main className="grid min-h-0 flex-1 grid-cols-[250px_minmax(0,1fr)_430px] gap-3 overflow-hidden px-3 pb-3">
        <aside className="panel flex min-h-0 flex-col p-3">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-sm font-medium">分镜任务</span>
            <span className="mono text-xs opacity-40">{tasks.length}</span>
          </div>
          <div className="min-h-0 flex-1 overflow-auto">
            {tasks.map((item) => (
              <button
                key={item.id}
                className={`mb-1 block w-full border px-2 py-2 text-left ${
                  taskId === item.id ? "border-[#e4572e] bg-[#e4572e]/5" : "border-transparent hover:border-white/15"
                }`}
                onClick={() => void selectTask(item.id)}
              >
                <div className="truncate text-sm">{item.title}</div>
                <div className="mono mt-1 truncate text-[10px] opacity-45">
                  {item.chapter_title || "未分章"} · {item.page_count} 页 · {item.status}
                </div>
              </button>
            ))}
            {!tasks.length && (
              <div className="mt-10 text-center text-xs opacity-40">
                还没有分镜任务
                <div className="mt-2">
                  <a className="border border-white/20 px-2 py-1" href={`/scenes?project=${projectId}`}>
                    去场景拆分
                  </a>
                </div>
              </div>
            )}
          </div>
        </aside>

        <section className="panel flex min-h-0 flex-col overflow-hidden p-3">
          {!task ? (
            <div className="mt-24 text-center text-sm opacity-45">选择或创建一个分镜任务</div>
          ) : (
            <>
              <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
                <div className="min-w-0">
                  <div className="truncate text-lg font-semibold">{task.title}</div>
                  <div className="mono mt-1 truncate text-xs opacity-45">
                    {task.chapter_title || "未分章"} · {task.page_count} 页 · {task.status} · 画风 {task.style_snapshot.name || task.style_snapshot.id || "-"}
                  </div>
                  <div className="mono mt-1 truncate text-[10px] opacity-35">
                    projects/{projectId}/images/mioss_{projectId}_{task.id}_p*.png
                  </div>
                </div>
                <div className="flex flex-wrap gap-2">
                  <button className="border border-white/20 px-3 py-1 text-sm disabled:opacity-40" disabled={addPage.isPending} onClick={() => void (async () => { if (await flushDraft()) addPage.mutate(); })()}>
                    加一页
                  </button>
                  <button className="border border-[#e4572e] px-3 py-1 text-sm text-[#e4572e] disabled:opacity-40" disabled={!pages.length || generateTask.isPending} onClick={() => generateTask.mutate()}>
                    生成全部
                  </button>
                </div>
              </div>

              <div className="mb-2 flex flex-wrap items-center gap-2 text-sm">
                <button className="border border-white/20 px-2 py-1 text-xs" onClick={toggleAllPages} disabled={!pages.length}>
                  {selectedPages.length === pages.length && pages.length ? "取消全选" : "全选"}
                </button>
                <button className="border border-white/20 px-2 py-1 text-xs disabled:opacity-40" disabled={!selectedPages.length || generateSelected.isPending} onClick={() => generateSelected.mutate(selectedPages)}>
                  生成选中 ({selectedPages.length})
                </button>
                <button className="border border-white/20 px-2 py-1 text-xs text-red-300 disabled:opacity-40" disabled={!selectedPages.length} onClick={() => requestDelete(selectedPages)}>
                  删除选中
                </button>
              </div>

              <div className="min-h-0 flex-1 overflow-auto">
                <div className="grid grid-cols-2 gap-3 xl:grid-cols-3">
                  {pages.map((page) => (
                    <div
                      key={page.id}
                      role="button"
                      tabIndex={0}
                      className={`relative cursor-pointer border p-2 text-left ${
                        page.id === pageId ? "border-[#e4572e]" : selectedPages.includes(page.id) ? "border-[#e4572e]/50" : "border-white/10 hover:border-white/25"
                      }`}
                      onClick={() => void selectPage(page.id)}
                    >
                      <label className="absolute right-2 top-2 z-10 flex h-5 w-5 items-center justify-center bg-black/60" onClick={(event) => event.stopPropagation()}>
                        <input
                          type="checkbox"
                          className="accent-[#e4572e]"
                          checked={selectedPages.includes(page.id)}
                          onChange={() => toggleSelectedPage(page.id)}
                        />
                      </label>
                      {page.image_url ? (
                        <img src={page.image_url} alt={`第 ${page.shot_no || page.order_no} 页`} className="aspect-[9/16] w-full object-cover" loading="lazy" />
                      ) : (
                        <div className="flex aspect-[9/16] w-full items-center justify-center border border-dashed border-white/10 bg-black/20 p-3 text-center text-xs opacity-40">
                          {page.summary || "未生成"}
                        </div>
                      )}
                      <div className="mt-2 flex items-center justify-between gap-2 text-xs">
                        <span>第 {page.shot_no || page.order_no} 页</span>
                        <span className="mono opacity-50">{page.status}</span>
                      </div>
                      <div className="mt-1 line-clamp-2 text-xs opacity-45">{page.summary}</div>
                    </div>
                  ))}
                </div>
                {!pages.length && (
                  <div className="mt-20 text-center text-sm opacity-40">
                    任务还没有页，点“加一页”
                  </div>
                )}
              </div>
            </>
          )}
        </section>

        <aside className="panel flex min-h-0 flex-col overflow-hidden">
          {!draft || !selectedPageLive ? (
            <div className="mt-24 text-center text-sm opacity-45">选择一页进行编辑</div>
          ) : (
            <>
              <div className="flex items-center justify-between border-b border-white/10 p-3">
                <div>
                  <div className="text-sm font-medium">第 {draft.shot_no || draft.order_no} 页</div>
                  <div className="mono text-xs opacity-45">{selectedPageLive.status}</div>
                </div>
                <div className="flex items-center gap-2">
                  <span className="mono text-xs opacity-50">
                    {saveState === "saving" ? "保存中…" : saveState === "dirty" ? "未保存" : "已保存"}
                  </span>
                  <button className="border border-white/20 px-2 py-1 text-xs" onClick={() => void flushDraft()}>
                    保存
                  </button>
                </div>
              </div>

              <div className="flex border-b border-white/10 text-xs">
                {([
                  ["content", "内容"],
                  ["prompt", "提示词"],
                  ["render", "出图"],
                ] as const).map(([value, text]) => (
                  <button
                    key={value}
                    className={`flex-1 px-2 py-2 ${tab === value ? "bg-[#e4572e] text-white" : "hover:bg-white/5"}`}
                    onClick={() => setTab(value)}
                  >
                    {text}
                  </button>
                ))}
              </div>

              <div className="min-h-0 flex-1 space-y-3 overflow-auto p-3">
                {tab === "content" && (
                  <>
                    <label className="block">
                      <span className="mb-1 block text-xs opacity-60">页面摘要</span>
                      <textarea
                        className="serif h-24 w-full resize-none bg-black/20 p-2 text-sm outline-none"
                        value={draft.summary}
                        onChange={(event) => setDraft({ ...draft, summary: event.target.value })}
                      />
                    </label>
                    <label className="block">
                      <span className="mb-1 block text-xs opacity-60">版式 / 镜头</span>
                      <textarea
                        className="h-20 w-full resize-none bg-black/20 p-2 text-sm outline-none"
                        value={draft.layout_note}
                        onChange={(event) => setDraft({ ...draft, layout_note: event.target.value })}
                      />
                    </label>

                    <div>
                      <span className="mb-1 block text-xs opacity-60">锚定角色</span>
                      <div className="space-y-1 text-sm">
                        {task?.character_snapshot.map((character) => (
                          <label key={character.id} className="flex items-center gap-2">
                            <input
                              type="checkbox"
                              className="accent-[#e4572e]"
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
                            <span>{character.name}</span>
                            <span className="mono truncate text-[10px] opacity-40">{character.anchor_tags}</span>
                          </label>
                        ))}
                        {!task?.character_snapshot.length && <div className="text-xs opacity-40">任务未锚定角色</div>}
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
                          <span className="mb-1 block text-xs opacity-60">{label}</span>
                          <input
                            className="w-full bg-black/20 px-2 py-1 text-sm outline-none"
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
                      <span className="mb-1 block text-xs opacity-60">法典 refs</span>
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
                        {!draft.refs.length && <span className="text-xs opacity-40">点右上“法典”加入</span>}
                      </div>
                    </div>
                  </>
                )}

                {tab === "prompt" && (
                  <>
                    <label className="block">
                      <span className="mb-1 block text-xs opacity-60">正向提示词</span>
                      <textarea
                        className="mono h-40 w-full resize-none bg-black/20 p-2 text-sm outline-none"
                        value={draft.prompt}
                        onChange={(event) => setDraft({ ...draft, prompt: event.target.value })}
                      />
                    </label>
                    <label className="block">
                      <span className="mb-1 block text-xs opacity-60">负向提示词</span>
                      <textarea
                        className="mono h-28 w-full resize-none bg-black/20 p-2 text-sm outline-none"
                        value={draft.negative}
                        onChange={(event) => setDraft({ ...draft, negative: event.target.value })}
                      />
                    </label>
                    <label className="block">
                      <span className="mb-1 block text-xs opacity-60">Seed</span>
                      <div className="flex gap-2">
                        <input
                          className="mono w-40 bg-black/20 px-2 py-1 outline-none"
                          type="number"
                          value={draft.seed ?? ""}
                          onChange={(event) => setDraft({ ...draft, seed: event.target.value ? Number(event.target.value) : null })}
                        />
                        <button className="border border-white/20 px-3 py-1 text-sm" onClick={() => setDraft({ ...draft, seed: Math.floor(Math.random() * 1_000_000_000_000_000) })}>
                          随机
                        </button>
                      </div>
                    </label>

                    <div className="flex flex-wrap items-center gap-2">
                      <select className="min-w-[180px] bg-black/20 px-2 py-1 text-sm outline-none" value={selectedPresetId} onChange={(event) => setSelectedPresetId(event.target.value)}>
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
                      <button className="border border-white/20 px-3 py-1 text-sm disabled:opacity-40" onClick={() => saveAsPreset.mutate()} disabled={!draft.prompt}>
                        保存为配方
                      </button>
                    </div>
                    {!!projectPresetsQuery.data?.length && (
                      <div className="mono text-xs opacity-50">项目配方：{projectPresetsQuery.data.map((preset) => preset.name).join(" / ")}</div>
                    )}

                    <button className="w-full border border-white/20 px-3 py-2 text-sm" onClick={() => compose.mutate()}>
                      编译提示词（含画风/角色锚点）
                    </button>
                    {lastCompose && (
                      <div className="mono text-xs opacity-60">
                        正向 {lastCompose.positive_count ?? 0} tag，负向 {lastCompose.negative_count ?? 0} tag；过滤 {lastCompose.dropped.length} 项
                      </div>
                    )}
                  </>
                )}

                {tab === "render" && (
                  <>
                    <div className="flex flex-wrap gap-2">
                      <button className="border border-[#e4572e] px-3 py-1 text-sm text-[#e4572e] disabled:opacity-40" disabled={generatePage.isPending} onClick={() => generatePage.mutate(selectedPageLive.id)}>
                        生成本页
                      </button>
                      <button
                        className="border border-white/20 px-3 py-1 text-sm disabled:opacity-40"
                        disabled={!selectedPageLive.image_path || regeneratePage.isPending}
                        onClick={() => regeneratePage.mutate()}
                      >
                        图生图重绘
                      </button>
                      <button
                        className="border border-white/20 px-3 py-1 text-sm disabled:opacity-40"
                        disabled={!draft.prompt}
                        onClick={() => {
                          generatePage.mutate(selectedPageLive.id);
                          generatePage.mutate(selectedPageLive.id);
                        }}
                      >
                        生成两个变体
                      </button>
                    </div>

                    {selectedPageLive.image_url && (
                      <a href={selectedPageLive.image_url} target="_blank" rel="noreferrer" className="block border border-white/15">
                        <img src={selectedPageLive.image_url} alt="页面预览" className="w-full" />
                      </a>
                    )}

                    <div>
                      <div className="mb-2 text-xs opacity-60">变体</div>
                      <div className="grid grid-cols-3 gap-2">
                        {variantsQuery.data?.map((variant) => (
                          <button
                            key={variant.id}
                            className="border border-white/15 disabled:opacity-40"
                            disabled={!variant.output_path}
                            onClick={() => variant.output_path && selectVariant.mutate(variant.output_path)}
                          >
                            {variant.image_url && <img src={variant.image_url} alt={`seed ${variant.seed}`} className="aspect-[9/16] w-full object-cover" />}
                            <div className="mono p-1 text-[10px] opacity-60">seed {variant.seed ?? "-"}</div>
                          </button>
                        ))}
                        {!variantsQuery.data?.length && <div className="text-xs opacity-40">暂无变体</div>}
                      </div>
                    </div>
                  </>
                )}
              </div>
            </>
          )}
        </aside>
      </main>

      <footer className="panel mx-3 mb-3 p-3">
        <div className="mb-2 flex items-center justify-between">
          <span className="text-sm opacity-70">任务队列</span>
          <span className="mono text-xs opacity-50">{jobsQuery.data?.length || 0} 条</span>
        </div>
        <div className="mono max-h-28 overflow-auto text-xs">
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

      {codexOpen && (
        <div className="fixed inset-0 z-40 bg-black/60" onClick={() => setCodexOpen(false)}>
          <aside className="absolute right-0 top-0 h-full w-[440px] overflow-auto border-l border-white/15 bg-[#14161b] p-4" onClick={(event) => event.stopPropagation()}>
            <div className="mb-3 flex items-center justify-between">
              <div className="text-lg font-semibold">法典</div>
              <button className="border border-white/20 px-2 py-1 text-xs" onClick={() => setCodexOpen(false)}>
                关闭
              </button>
            </div>
            <div className="mb-2 flex border border-white/15 text-xs">
              {([
                ["regular", "常规"],
                ["nsfw", "NSFW"],
                ["reference", "参考"],
              ] as const).map(([value, label]) => (
                <button
                  key={value}
                  className={`flex-1 px-2 py-2 ${libraryDomain === value ? "bg-[#e4572e] text-white" : "hover:bg-white/5"}`}
                  onClick={() => setLibraryDomain(value)}
                >
                  {label}
                </button>
              ))}
            </div>
            <select className="mb-2 w-full bg-black/20 px-2 py-1 text-sm outline-none" value={categoryFilter} onChange={(event) => setCategoryFilter(event.target.value)}>
              <option value="">全部分类</option>
              {categoriesQuery.data?.map((category) => (
                <option key={category.id} value={category.id}>
                  {category.name} ({category.count})
                </option>
              ))}
            </select>
            <input
              className="mb-3 w-full bg-black/20 px-2 py-2 text-sm outline-none placeholder:opacity-40"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="搜索法典 tag / 中文"
              list="board-tag-suggestions"
            />
            <datalist id="board-tag-suggestions">
              {suggestionsQuery.data?.map((item) => (
                <option key={item.tag} value={item.tag} />
              ))}
            </datalist>
            <div className="space-y-2">
              {codexQuery.data?.map((entry) => (
                <div key={entry.id} className="panel p-2">
                  <div className="flex gap-2">
                    {entry.image_url && <img src={`/api/codex/entries/${entry.id}/thumbnail`} alt={entry.title} className="h-24 w-16 object-cover" />}
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-sm font-medium">{entry.title}</div>
                      <div className="mono text-[10px] opacity-50">{entry.id}</div>
                      <div className="mono mt-1 line-clamp-3 text-xs opacity-70">{entry.tags_positive}</div>
                      <button
                        className="mt-2 border border-white/20 px-2 py-1 text-xs hover:border-[#e4572e] disabled:opacity-40"
                        disabled={!draft || draft.refs.includes(entry.id)}
                        onClick={() => addCodexEntry(entry)}
                      >
                        {draft?.refs.includes(entry.id) ? "已加入" : "加入本页"}
                      </button>
                    </div>
                  </div>
                </div>
              ))}
              {!codexQuery.data?.length && <div className="text-xs opacity-40">输入关键词或选择分类</div>}
            </div>
          </aside>
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

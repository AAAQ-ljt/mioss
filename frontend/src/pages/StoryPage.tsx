import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api, type Chapter, type ChapterDetail, type Project, type StylePreset } from "../api";
import { copyText } from "../utils/clipboard";

type ContextMenu = { x: number; y: number; text: string; start: number; end: number; target: "editor" | "preview" } | null;

export default function StoryPage() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const editorRef = useRef<HTMLTextAreaElement>(null);
  const [projectId, setProjectId] = useState(searchParams.get("project") || "");
  const [chapterId, setChapterId] = useState("");
  const [content, setContent] = useState("");
  const [savedContent, setSavedContent] = useState("");
  const [loadedChapterId, setLoadedChapterId] = useState("");
  const [saveState, setSaveState] = useState<"saved" | "dirty" | "saving">("saved");
  const savingRef = useRef<Promise<boolean> | null>(null);
  const saveSeqRef = useRef(0);
  const latestRef = useRef({ chapterId: "", content: "", savedContent: "" });
  const [viewMode, setViewMode] = useState<"edit" | "preview">("edit");
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [newTitle, setNewTitle] = useState("新作品");
  const [newMode, setNewMode] = useState<"illustration" | "comic">("illustration");
  const [newStyle, setNewStyle] = useState("manga-ink");
  const [selectedProjects, setSelectedProjects] = useState<string[]>([]);
  const [chapterModal, setChapterModal] = useState(false);
  const [chapterName, setChapterName] = useState("");
  const [dragIndex, setDragIndex] = useState<number | null>(null);
  const [menu, setMenu] = useState<ContextMenu>(null);
  const [notice, setNotice] = useState("");
  latestRef.current = { chapterId, content, savedContent };

  const projectsQuery = useQuery({
    queryKey: ["projects"],
    queryFn: () => api<Project[]>("/api/projects"),
  });

  const stylesQuery = useQuery({
    queryKey: ["style-presets"],
    queryFn: () => api<StylePreset[]>("/api/style-presets"),
  });

  useEffect(() => {
    if (!projectsQuery.data?.length) {
      setProjectId("");
      return;
    }
    if (!projectsQuery.data.some((project) => project.id === projectId)) {
      setProjectId(projectsQuery.data[0].id);
    }
  }, [projectsQuery.data, projectId]);

  const project = projectsQuery.data?.find((item) => item.id === projectId);
  const mode = project?.mode || "comic";

  useEffect(() => {
    setContent("");
    setSavedContent("");
    setLoadedChapterId("");
    setChapterId("");
  }, [projectId]);

  const chaptersQuery = useQuery({
    queryKey: ["chapters", projectId],
    queryFn: () => api<Chapter[]>(`/api/projects/${projectId}/chapters`),
    enabled: !!projectId,
  });

  useEffect(() => {
    if (!chaptersQuery.data?.length) {
      setChapterId("");
      return;
    }
    if (!chaptersQuery.data.some((chapter) => chapter.id === chapterId)) {
      setChapterId(chaptersQuery.data[0].id);
    }
  }, [chaptersQuery.data, chapterId]);

  const chapterQuery = useQuery({
    queryKey: ["chapter", chapterId],
    queryFn: () => api<ChapterDetail>(`/api/chapters/${chapterId}`),
    enabled: !!chapterId,
  });

  useEffect(() => {
    const data = chapterQuery.data;
    if (!data || !chapterId || data.id !== chapterId) return;
    const text = data.content || "";
    if (data.id !== loadedChapterId) {
      setContent(text);
      setSavedContent(text);
      setLoadedChapterId(data.id);
      setSaveState("saved");
      return;
    }
    if (content === savedContent && text !== savedContent) {
      setContent(text);
      setSavedContent(text);
      setSaveState("saved");
    }
  }, [chapterQuery.data, chapterId, loadedChapterId, content, savedContent]);

  useEffect(() => {
    function close() {
      setMenu(null);
    }
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setMenu(null);
        setDrawerOpen(false);
        setChapterModal(false);
      }
    }
    window.addEventListener("click", close);
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("click", close);
      window.removeEventListener("keydown", onKey);
    };
  }, []);

  async function persistChapter(id: string, text: string): Promise<boolean> {
    setSaveState("saving");
    const seq = ++saveSeqRef.current;
    const request = api(`/api/chapters/${id}`, { method: "PUT", body: JSON.stringify({ content: text }) })
      .then(() => {
        setSavedContent(text);
        setSaveState(latestRef.current.content === text ? "saved" : "dirty");
        queryClient.setQueryData<ChapterDetail>(["chapter", id], (current) =>
          current && current.id === id ? { ...current, content: text } : current,
        );
        queryClient.invalidateQueries({ queryKey: ["chapters", projectId] });
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
    if (!chapterId || loadedChapterId !== chapterId || content === savedContent) return;
    setSaveState("dirty");
    if (savingRef.current) return;
    const timer = window.setTimeout(() => {
      if (!savingRef.current) void persistChapter(chapterId, content);
    }, 800);
    return () => window.clearTimeout(timer);
  }, [content, savedContent, chapterId, loadedChapterId, projectId, queryClient]);

  async function flushChapter(): Promise<boolean> {
    if (savingRef.current) await savingRef.current;
    const latest = latestRef.current;
    if (!latest.chapterId || latest.content === latest.savedContent) return true;
    if (savingRef.current) await savingRef.current;
    return persistChapter(latest.chapterId, latest.content);
  }

  useEffect(() => {
    function flushOnExit() {
      const latest = latestRef.current;
      if (!latest.chapterId || latest.content === latest.savedContent) return;
      fetch(`/api/chapters/${latest.chapterId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: latest.content }),
        keepalive: true,
      }).catch(() => undefined);
    }
    window.addEventListener("beforeunload", flushOnExit);
    return () => {
      window.removeEventListener("beforeunload", flushOnExit);
      flushOnExit();
    };
  }, []);

  async function selectChapter(id: string) {
    if (id === chapterId) return;
    if (!(await flushChapter())) {
      setNotice("保存失败，已取消切换");
      return;
    }
    setContent("");
    setSavedContent("");
    setLoadedChapterId("");
    setChapterId(id);
  }

  async function selectProject(id: string) {
    if (id === projectId) return;
    if (!(await flushChapter())) {
      setNotice("保存失败，已取消切换");
      return;
    }
    setProjectId(id);
  }

  const createProject = useMutation({
    mutationFn: async () => {
      if (!(await flushChapter())) throw new Error("chapter save failed");
      const created = await api<Project>("/api/projects", {
        method: "POST",
        body: JSON.stringify({ title: newTitle, mode: newMode, style_preset_id: newStyle }),
      });
      await api(`/api/projects/${created.id}/chapters`, { method: "POST", body: JSON.stringify({ title: "第一章" }) });
      return created;
    },
    onSuccess: async (created) => {
      setDrawerOpen(false);
      await queryClient.invalidateQueries({ queryKey: ["projects"] });
      setProjectId(created.id);
    },
    onError: () => setNotice("保存失败，未新建作品"),
  });

  const deleteProject = useMutation({
    mutationFn: (id: string) => api(`/api/projects/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      setSelectedProjects([]);
      queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
  });

  const batchDeleteProjects = useMutation({
    mutationFn: () => api("/api/projects/batch_delete", { method: "POST", body: JSON.stringify({ project_ids: selectedProjects }) }),
    onSuccess: () => {
      setSelectedProjects([]);
      queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
  });

  const createChapter = useMutation({
    mutationFn: async (title: string) => {
      if (!(await flushChapter())) throw new Error("chapter save failed");
      return api<Chapter>(`/api/projects/${projectId}/chapters`, { method: "POST", body: JSON.stringify({ title }) });
    },
    onSuccess: async (chapter) => {
      setChapterModal(false);
      setChapterName("");
      await queryClient.invalidateQueries({ queryKey: ["chapters", projectId] });
      setContent("");
      setSavedContent("");
      setLoadedChapterId("");
      setChapterId(chapter.id);
    },
    onError: () => setNotice("保存失败，未新增章节"),
  });

  const reorderChapters = useMutation({
    mutationFn: (chapterIds: string[]) =>
      api<Chapter[]>(`/api/projects/${projectId}/chapters/reorder`, { method: "POST", body: JSON.stringify({ chapter_ids: chapterIds }) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["chapters", projectId] }),
  });

  const importChapters = useMutation({
    mutationFn: async (markdown: string) => {
      if (!(await flushChapter())) throw new Error("chapter save failed");
      return api<{ chapters: Chapter[] }>(`/api/projects/${projectId}/chapters/import`, {
        method: "POST",
        body: JSON.stringify({ markdown }),
      });
    },
    onSuccess: async (result) => {
      await queryClient.invalidateQueries({ queryKey: ["chapters", projectId] });
      if (result.chapters[0]) {
        setContent("");
        setSavedContent("");
        setLoadedChapterId("");
        setChapterId(result.chapters[0].id);
      }
      setNotice(`导入 ${result.chapters.length} 个章节`);
    },
    onError: () => setNotice("保存失败，未导入章节"),
  });

  const sendScene = useMutation({
    mutationFn: async (text: string) => {
      const excerpt = text.trim();
      if (!excerpt) throw new Error("empty selection");
      if (!(await flushChapter())) throw new Error("chapter save failed");
      const chapter = chaptersQuery.data?.find((item) => item.id === chapterId);
      const firstLine = excerpt.split("\n").find((line) => line.trim())?.trim() || "";
      const title = firstLine.replace(/^#+\s*/, "").slice(0, 40) || "新场景";
      return api<{ id: string }>(`/api/projects/${projectId}/scenes`, {
        method: "POST",
        body: JSON.stringify({
          title,
          summary: excerpt.slice(0, 500),
          excerpt,
          chapter_title: chapter?.title || "",
          chapter_index: chapter?.order_no || 0,
        }),
      });
    },
    onSuccess: (scene) => {
      navigate(`/scenes?project=${projectId}&scene=${scene.id}`);
    },
    onError: (error) => {
      setNotice(String(error).includes("empty selection") ? "先选中一段文字" : "创建场景失败");
    },
  });

  function getSelectedText() {
    const editor = editorRef.current;
    if (viewMode === "edit" && editor && editor.selectionStart !== editor.selectionEnd) {
      return editor.value.slice(editor.selectionStart, editor.selectionEnd);
    }
    return window.getSelection()?.toString() || "";
  }

  function sendSelectionToScenes() {
    const text = getSelectedText();
    if (!text.trim()) {
      setNotice("先选中一段文字");
      return;
    }
    sendScene.mutate(text);
  }

  function dropChapter(targetIndex: number) {
    const chapters = chaptersQuery.data || [];
    if (dragIndex === null || dragIndex === targetIndex) return;
    const ids = chapters.map((chapter) => chapter.id);
    const [moved] = ids.splice(dragIndex, 1);
    ids.splice(targetIndex, 0, moved);
    reorderChapters.mutate(ids);
    setDragIndex(null);
  }

  function openContextMenu(event: React.MouseEvent, target: "editor" | "preview") {
    event.preventDefault();
    let text = "";
    let start = 0;
    let end = 0;
    if (target === "editor" && editorRef.current) {
      const element = editorRef.current;
      start = element.selectionStart;
      end = element.selectionEnd;
      text = element.value.slice(start, end);
    } else {
      text = window.getSelection()?.toString() || "";
    }
    setMenu({ x: event.clientX, y: event.clientY, text, start, end, target });
  }

  async function pasteAtSelection() {
    if (!menu || menu.target !== "editor" || !editorRef.current) return;
    try {
      const clipboard = await navigator.clipboard.readText();
      setContent(content.slice(0, menu.start) + clipboard + content.slice(menu.end));
    } catch {
      setNotice("浏览器不允许读取剪贴板");
    }
  }

  function transferToScene() {
    if (!menu?.text.trim()) return;
    sendScene.mutate(menu.text);
  }

  return (
    <div className="flex h-screen flex-col">
      <header className="panel m-3 flex flex-wrap items-center gap-3 p-4">
        <div className="min-w-[150px]">
          <div className="text-lg font-semibold">故事整理</div>
          <div className="text-xs opacity-50">{mode === "illustration" ? "小说配图模式" : "改编漫画模式"}</div>
        </div>
        <select className="bg-black/20 px-3 py-2 text-sm outline-none" value={projectId} onChange={(event) => void selectProject(event.target.value)}>
          {projectsQuery.data?.map((item) => (
            <option key={item.id} value={item.id}>
              [{item.mode === "illustration" ? "插图" : "漫画"}] {item.title}
            </option>
          ))}
        </select>
        <button className="border border-[#e4572e] px-3 py-2 text-sm text-[#e4572e]" onClick={() => setDrawerOpen(true)}>
          新建作品
        </button>
        <a className="border border-white/20 px-3 py-2 text-sm" href={`/scenes?project=${projectId}`}>
          场景拆分
        </a>
        <a className="border border-white/20 px-3 py-2 text-sm" href="/gallery">
          去画廊
        </a>
        {notice && <span className="mono text-xs text-[#ffb4a0]">{notice}</span>}
      </header>

      <div className="grid min-h-0 flex-1 grid-cols-[200px_minmax(0,1fr)] gap-3 px-3 pb-3">
        <aside className="panel min-h-0 overflow-auto p-3">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-sm font-medium">章节目录</span>
            <button className="border border-white/20 px-2 py-1 text-xs" onClick={() => setChapterModal(true)}>
              新增章节
            </button>
          </div>
          {chaptersQuery.data?.map((chapter, index) => (
            <div
              key={chapter.id}
              draggable
              onDragStart={() => setDragIndex(index)}
              onDragOver={(event) => event.preventDefault()}
              onDrop={() => dropChapter(index)}
              className={`mb-1 cursor-move truncate border px-2 py-1 text-sm ${
                chapterId === chapter.id ? "border-[#e4572e] text-[#ffb4a0]" : "border-transparent hover:border-white/15"
              }`}
              onClick={() => selectChapter(chapter.id)}
            >
              {chapter.title}
            </div>
          ))}
          {!chaptersQuery.data?.length && <div className="text-xs opacity-40">新增章节后会生成独立 md 文件</div>}
        </aside>

        <section className="panel flex min-h-0 flex-col p-3">
          <div className="mb-2 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <label className="cursor-pointer border border-white/20 px-3 py-1 text-sm">
                导入
                <input
                  type="file"
                  accept=".md,text/markdown"
                  className="hidden"
                  onChange={async (event) => {
                    const file = event.target.files?.[0];
                    if (file) importChapters.mutate(await file.text());
                    event.currentTarget.value = "";
                  }}
                />
              </label>
              <button
                className="border border-[#e4572e] px-3 py-1 text-sm text-[#e4572e] disabled:opacity-40"
                disabled={!projectId || sendScene.isPending}
                onClick={sendSelectionToScenes}
                title="把编辑器或预览中选中的文字创建为场景，并打开场景拆分页"
              >
                送入选区到场景拆分
              </button>
              <span className="mono text-xs opacity-50">
                {saveState === "saving" ? "保存中…" : saveState === "dirty" ? "未保存" : "已保存"}
              </span>
            </div>
            <div className="flex border border-white/15 text-xs">
              <button className={`px-3 py-1 ${viewMode === "edit" ? "bg-[#e4572e] text-white" : ""}`} onClick={() => setViewMode("edit")}>
                编辑
              </button>
              <button className={`px-3 py-1 ${viewMode === "preview" ? "bg-[#e4572e] text-white" : ""}`} onClick={() => setViewMode("preview")}>
                预览
              </button>
            </div>
          </div>
          {viewMode === "edit" ? (
            <textarea
              ref={editorRef}
              className="serif min-h-0 flex-1 resize-none bg-black/25 p-3 text-sm leading-7 outline-none"
              value={content}
              onChange={(event) => setContent(event.target.value)}
              onContextMenu={(event) => openContextMenu(event, "editor")}
              placeholder="当前章节还没有内容"
            />
          ) : (
            <div className="prose-manga min-h-0 flex-1 overflow-auto p-5" onContextMenu={(event) => { event.stopPropagation(); openContextMenu(event, "preview"); }}>
              <ReactMarkdown>{content}</ReactMarkdown>
            </div>
          )}
        </section>

      </div>

      {drawerOpen && (
        <div className="fixed inset-0 z-40 bg-black/60" onClick={() => setDrawerOpen(false)}>
          <aside className="absolute right-0 top-0 h-full w-[420px] overflow-auto border-l border-white/15 bg-[#14161b] p-4" onClick={(event) => event.stopPropagation()}>
            <div className="mb-4 flex items-center justify-between">
              <div className="text-lg font-semibold">作品</div>
              <button className="border border-white/20 px-2 py-1 text-xs" onClick={() => setDrawerOpen(false)}>关闭</button>
            </div>

            <div className="panel mb-4 p-3">
              <div className="mb-2 text-sm font-medium">新建作品</div>
              <input className="mb-2 w-full bg-black/25 px-2 py-1 text-sm outline-none" value={newTitle} onChange={(event) => setNewTitle(event.target.value)} placeholder="作品名" />
              <div className="mb-2 flex border border-white/15 text-xs">
                <button className={`flex-1 px-2 py-1 ${newMode === "illustration" ? "bg-[#e4572e] text-white" : ""}`} onClick={() => setNewMode("illustration")}>小说配图</button>
                <button className={`flex-1 px-2 py-1 ${newMode === "comic" ? "bg-[#e4572e] text-white" : ""}`} onClick={() => setNewMode("comic")}>改编漫画</button>
              </div>
              <select className="mb-2 w-full bg-black/25 px-2 py-1 text-sm outline-none" value={newStyle} onChange={(event) => setNewStyle(event.target.value)}>
                {stylesQuery.data?.map((style) => (
                  <option key={style.id} value={style.id}>{style.name}</option>
                ))}
              </select>
              <button className="w-full border border-[#e4572e] px-3 py-2 text-sm text-[#e4572e]" onClick={() => createProject.mutate()}>创建</button>
            </div>

            <div className="panel p-3">
              <div className="mb-2 flex items-center justify-between">
                <span className="text-sm font-medium">作品管理</span>
                <button
                  className="border border-white/20 px-2 py-1 text-xs text-red-300 disabled:opacity-40"
                  disabled={!selectedProjects.length}
                  onClick={() => window.confirm(`删除选中的 ${selectedProjects.length} 个作品？`) && batchDeleteProjects.mutate()}
                >
                  批量删除
                </button>
              </div>
              {projectsQuery.data?.map((item) => (
                <div key={item.id} className="mb-1 flex items-center gap-2 border-b border-white/10 py-2">
                  <input
                    type="checkbox"
                    checked={selectedProjects.includes(item.id)}
                    onChange={() =>
                      setSelectedProjects((current) =>
                        current.includes(item.id) ? current.filter((id) => id !== item.id) : [...current, item.id],
                      )
                    }
                  />
                  <span className="min-w-0 flex-1 truncate text-sm">[{item.mode === "illustration" ? "插图" : "漫画"}] {item.title}</span>
                  <button className="text-xs text-red-300" onClick={() => window.confirm(`删除作品「${item.title}」？`) && deleteProject.mutate(item.id)}>删除</button>
                </div>
              ))}
              {!projectsQuery.data?.length && <div className="text-xs opacity-40">暂无作品</div>}
            </div>
          </aside>
        </div>
      )}

      {chapterModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={() => setChapterModal(false)}>
          <div className="panel w-80 p-4" onClick={(event) => event.stopPropagation()}>
            <div className="mb-3 text-sm font-medium">新增章节</div>
            <input className="mb-3 w-full bg-black/25 px-2 py-2 text-sm outline-none" value={chapterName} onChange={(event) => setChapterName(event.target.value)} placeholder="章节名" autoFocus />
            <div className="flex justify-end gap-2">
              <button className="border border-white/20 px-3 py-1 text-sm" onClick={() => setChapterModal(false)}>取消</button>
              <button className="border border-[#e4572e] px-3 py-1 text-sm text-[#e4572e]" onClick={() => createChapter.mutate(chapterName.trim())} disabled={!chapterName.trim()}>添加</button>
            </div>
          </div>
        </div>
      )}

      {menu && (
        <div className="fixed z-50 border border-white/20 bg-[#1a1c22] py-1 text-sm shadow-xl" style={{ left: menu.x, top: menu.y }} onClick={(event) => event.stopPropagation()}>
          <button className="block w-full px-4 py-1 text-left hover:bg-white/10 disabled:opacity-40" disabled={!menu.text} onClick={() => { copyText(menu.text); setMenu(null); }}>复制</button>
          <button className="block w-full px-4 py-1 text-left hover:bg-white/10 disabled:opacity-40" disabled={menu.target !== "editor"} onClick={() => { pasteAtSelection(); setMenu(null); }}>粘贴</button>
          <button className="block w-full px-4 py-1 text-left hover:bg-white/10 disabled:opacity-40" disabled={!menu.text} onClick={() => { transferToScene(); setMenu(null); }}>转移到场景</button>
          <button className="block w-full px-4 py-1 text-left hover:bg-white/10" onClick={() => { window.scrollTo({ top: 0, behavior: "smooth" }); setMenu(null); }}>顶部跳转</button>
        </div>
      )}
    </div>
  );
}

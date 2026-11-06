import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import { api, type Project, type StoryDoc, type StoryScene } from "../api";

export default function StoryPage() {
  const queryClient = useQueryClient();
  const [projectId, setProjectId] = useState("");
  const [newTitle, setNewTitle] = useState("新作品");
  const [newMode, setNewMode] = useState<"illustration" | "comic">("illustration");
  const [title, setTitle] = useState("");
  const [markdown, setMarkdown] = useState("");
  const [viewMode, setViewMode] = useState<"edit" | "preview">("edit");
  const [selectedScenes, setSelectedScenes] = useState<string[]>([]);
  const [notice, setNotice] = useState("");

  const projectsQuery = useQuery({
    queryKey: ["projects"],
    queryFn: () => api<Project[]>("/api/projects"),
  });

  useEffect(() => {
    if (!projectsQuery.data?.length) return;
    if (!projectsQuery.data.some((project) => project.id === projectId)) {
      setProjectId(projectsQuery.data[0].id);
    }
  }, [projectsQuery.data, projectId]);

  const project = projectsQuery.data?.find((item) => item.id === projectId);
  const mode = project?.mode || "comic";

  const storyQuery = useQuery({
    queryKey: ["story", projectId],
    queryFn: () => api<StoryDoc>(`/api/projects/${projectId}/story`),
    enabled: !!projectId,
  });

  const scenesQuery = useQuery({
    queryKey: ["scenes", projectId],
    queryFn: () => api<StoryScene[]>(`/api/projects/${projectId}/scenes`),
    enabled: !!projectId,
  });

  useEffect(() => {
    if (!storyQuery.data) return;
    setTitle(storyQuery.data.title || "");
    setMarkdown(storyQuery.data.markdown || "");
  }, [storyQuery.data?.project_id, storyQuery.data?.updated_at]);

  const createProject = useMutation({
    mutationFn: () => api<Project>("/api/projects", { method: "POST", body: JSON.stringify({ title: newTitle, mode: newMode }) }),
    onSuccess: (created) => {
      setProjectId(created.id);
      queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
  });

  const saveStory = useMutation({
    mutationFn: () => api<StoryDoc>(`/api/projects/${projectId}/story`, { method: "PUT", body: JSON.stringify({ title, markdown }) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["story", projectId] }),
  });

  const parseScenes = useMutation({
    mutationFn: () => api<{ scenes: StoryScene[] }>(`/api/projects/${projectId}/story/parse`, { method: "POST", body: JSON.stringify({ markdown }) }),
    onSuccess: (result) => {
      setSelectedScenes(result.scenes.map((scene) => scene.id));
      queryClient.invalidateQueries({ queryKey: ["scenes", projectId] });
      setNotice(`已切出 ${result.scenes.length} 个场景`);
    },
  });

  const updateScene = useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: Partial<StoryScene> }) =>
      api<StoryScene>(`/api/scenes/${id}`, { method: "PATCH", body: JSON.stringify(patch) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["scenes", projectId] }),
  });

  const generateScenes = useMutation({
    mutationFn: (sceneIds?: string[]) =>
      api<{ pages: unknown[]; status: string }>(`/api/projects/${projectId}/scenes/generate`, {
        method: "POST",
        body: JSON.stringify({ scene_ids: sceneIds }),
      }),
    onSuccess: (result) => {
      setNotice(`已加入队列：${result.pages.length} 个${mode === "illustration" ? "插图" : "分镜页"}`);
      queryClient.invalidateQueries({ queryKey: ["scenes", projectId] });
      queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
  });

  function toggleScene(id: string) {
    setSelectedScenes((current) => (current.includes(id) ? current.filter((item) => item !== id) : [...current, id]));
  }

  return (
    <div className="flex h-screen flex-col">
      <header className="panel m-3 flex flex-wrap items-center gap-3 p-4">
        <div className="min-w-[160px]">
          <div className="text-lg font-semibold">故事整理</div>
          <div className="text-xs opacity-50">一个项目绑定一本 Markdown 小说</div>
        </div>
        <select className="bg-black/20 px-3 py-2 text-sm outline-none" value={projectId} onChange={(event) => setProjectId(event.target.value)}>
          {projectsQuery.data?.map((item) => (
            <option key={item.id} value={item.id}>
              [{item.mode === "illustration" ? "插图" : "漫画"}] {item.title}
            </option>
          ))}
        </select>
        <input className="w-32 bg-black/20 px-2 py-2 text-sm outline-none" value={newTitle} onChange={(event) => setNewTitle(event.target.value)} placeholder="新作品名" />
        <select className="bg-black/20 px-2 py-2 text-sm outline-none" value={newMode} onChange={(event) => setNewMode(event.target.value as "illustration" | "comic")}>
          <option value="illustration">插图模式</option>
          <option value="comic">漫画模式</option>
        </select>
        <button className="border border-white/20 px-3 py-2 text-sm" onClick={() => createProject.mutate()}>
          新建作品
        </button>
        <label className="cursor-pointer border border-white/20 px-3 py-2 text-sm">
          导入 Markdown
          <input
            type="file"
            accept=".md,text/markdown"
            className="hidden"
            onChange={async (event) => {
              const file = event.target.files?.[0];
              if (file) {
                setMarkdown(await file.text());
                if (!title) setTitle(file.name.replace(/\.md$/i, ""));
              }
              event.currentTarget.value = "";
            }}
          />
        </label>
        <button className="border border-white/20 px-3 py-2 text-sm" onClick={() => saveStory.mutate()} disabled={!projectId}>
          保存原文
        </button>
        <button className="border border-[#e4572e] px-3 py-2 text-sm text-[#e4572e]" onClick={() => parseScenes.mutate()} disabled={!projectId}>
          切分场景
        </button>
        <a className="border border-white/20 px-3 py-2 text-sm" href="/gallery">
          去画廊
        </a>
        {notice && <span className="mono text-xs text-[#ffb4a0]">{notice}</span>}
      </header>

      <div className="grid min-h-0 flex-1 grid-cols-[200px_minmax(0,1fr)_380px] gap-3 px-3 pb-3">
        <aside className="panel min-h-0 overflow-auto p-3">
          <div className="mb-2 text-sm font-medium">章节目录</div>
          {storyQuery.data?.chapters.map((chapter) => (
            <div key={`${chapter.line}-${chapter.title}`} className="truncate py-1 text-sm" style={{ paddingLeft: (chapter.level - 1) * 10 }}>
              {chapter.title}
            </div>
          ))}
          {!storyQuery.data?.chapters.length && <div className="text-xs opacity-40">Markdown 标题会自动成为章节</div>}
        </aside>

        <section className="panel flex min-h-0 flex-col p-3">
          <div className="mb-2 flex items-center justify-between">
            <input className="min-w-0 flex-1 bg-black/25 px-2 py-1 text-sm outline-none" value={title} onChange={(event) => setTitle(event.target.value)} placeholder="作品标题" />
            <div className="ml-2 flex border border-white/15 text-xs">
              <button className={`px-3 py-1 ${viewMode === "edit" ? "bg-[#e4572e] text-white" : ""}`} onClick={() => setViewMode("edit")}>编辑</button>
              <button className={`px-3 py-1 ${viewMode === "preview" ? "bg-[#e4572e] text-white" : ""}`} onClick={() => setViewMode("preview")}>预览</button>
            </div>
          </div>
          {viewMode === "edit" ? (
            <textarea
              className="serif min-h-0 flex-1 resize-none bg-black/25 p-3 text-sm leading-7 outline-none"
              value={markdown}
              onChange={(event) => setMarkdown(event.target.value)}
              placeholder="# 第一章&#10;&#10;正文&#10;&#10;---&#10;&#10;场景二"
            />
          ) : (
            <div className="prose-manga min-h-0 flex-1 overflow-auto p-5">
              <ReactMarkdown>{markdown}</ReactMarkdown>
            </div>
          )}
        </section>

        <aside className="panel flex min-h-0 flex-col p-3">
          <div className="mb-2 flex items-center justify-between">
            <div>
              <div className="text-sm font-medium">场景</div>
              <div className="mono text-xs opacity-50">{mode === "illustration" ? "一场景一张插图" : "一场景一页分镜"}</div>
            </div>
            <div className="flex gap-1">
              <button
                className="border border-white/20 px-2 py-1 text-xs disabled:opacity-40"
                onClick={() => generateScenes.mutate(selectedScenes)}
                disabled={!selectedScenes.length || generateScenes.isPending}
              >
                生成选中
              </button>
              <button
                className="border border-[#e4572e] px-2 py-1 text-xs text-[#e4572e] disabled:opacity-40"
                onClick={() => generateScenes.mutate(undefined)}
                disabled={!scenesQuery.data?.length || generateScenes.isPending}
              >
                自动全部
              </button>
            </div>
          </div>

          <div className="min-h-0 flex-1 overflow-auto">
            {scenesQuery.data?.map((scene) => (
              <div key={scene.id} className={`mb-2 border p-2 ${selectedScenes.includes(scene.id) ? "border-[#e4572e]/60" : "border-white/10"}`}>
                <div className="flex items-start gap-2">
                  <input type="checkbox" className="mt-1" checked={selectedScenes.includes(scene.id)} onChange={() => toggleScene(scene.id)} />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center justify-between gap-2">
                      <span className="mono text-xs opacity-50">#{scene.order_no} {scene.chapter_title}</span>
                      <span className="mono text-xs opacity-40">{scene.status}</span>
                    </div>
                    <div className="truncate text-sm font-medium">{scene.title}</div>
                    <textarea
                      className="mt-1 h-20 w-full resize-none bg-black/25 p-2 text-xs outline-none"
                      defaultValue={scene.summary}
                      onBlur={(event) => updateScene.mutate({ id: scene.id, patch: { summary: event.target.value } })}
                    />
                    <div className="mt-1 grid grid-cols-2 gap-1">
                      <input
                        className="bg-black/25 px-2 py-1 text-xs outline-none"
                        defaultValue={scene.setting || ""}
                        placeholder="地点/环境"
                        onBlur={(event) => updateScene.mutate({ id: scene.id, patch: { setting: event.target.value } })}
                      />
                      <input
                        className="bg-black/25 px-2 py-1 text-xs outline-none"
                        defaultValue={scene.mood || ""}
                        placeholder="情绪"
                        onBlur={(event) => updateScene.mutate({ id: scene.id, patch: { mood: event.target.value } })}
                      />
                    </div>
                  </div>
                </div>
              </div>
            ))}
            {!scenesQuery.data?.length && <div className="mt-10 text-center text-xs opacity-40">保存原文后点“切分场景”</div>}
          </div>
        </aside>
      </div>
    </div>
  );
}

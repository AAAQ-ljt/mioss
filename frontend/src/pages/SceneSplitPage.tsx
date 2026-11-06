import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api, type Chapter, type Project, type StoryboardTask, type StoryScene, type StylePreset } from "../api";

type Character = { id: string; name: string; anchor_tags: string; notes: string };

export default function SceneSplitPage() {
  const queryClient = useQueryClient();
  const [searchParams] = useSearchParams();
  const [projectId, setProjectId] = useState(searchParams.get("project") || "");
  const [sceneId, setSceneId] = useState(searchParams.get("scene") || "");
  const [pageCount, setPageCount] = useState(1);
  const [stylePresetId, setStylePresetId] = useState("");
  const [selectedCharacters, setSelectedCharacters] = useState<string[]>([]);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [characterName, setCharacterName] = useState("");
  const [characterAnchor, setCharacterAnchor] = useState("");
  const [notice, setNotice] = useState("");

  const projectsQuery = useQuery({
    queryKey: ["projects"],
    queryFn: () => api<Project[]>("/api/projects"),
  });
  const chaptersQuery = useQuery({
    queryKey: ["chapters", projectId],
    queryFn: () => api<Chapter[]>(`/api/projects/${projectId}/chapters`),
    enabled: !!projectId,
  });
  const scenesQuery = useQuery({
    queryKey: ["scenes", projectId],
    queryFn: () => api<StoryScene[]>(`/api/projects/${projectId}/scenes`),
    enabled: !!projectId,
  });
  const tasksQuery = useQuery({
    queryKey: ["tasks", projectId],
    queryFn: () => api<StoryboardTask[]>(`/api/projects/${projectId}/tasks`),
    enabled: !!projectId,
  });
  const charactersQuery = useQuery({
    queryKey: ["characters", projectId],
    queryFn: () => api<Character[]>(`/api/projects/${projectId}/characters`),
    enabled: !!projectId,
  });
  const stylesQuery = useQuery({
    queryKey: ["style-presets"],
    queryFn: () => api<StylePreset[]>("/api/style-presets"),
  });

  const projects = projectsQuery.data || [];
  const project = projects.find((item) => item.id === projectId);
  const scenes = scenesQuery.data || [];
  const tasks = tasksQuery.data || [];
  const characters = useMemo(() => charactersQuery.data || [], [charactersQuery.data]);
  const scene = scenes.find((item) => item.id === sceneId) || null;
  const task = scene ? tasks.find((item) => item.scene_id === scene.id) || null : null;

  useEffect(() => {
    if (!projects.length) {
      setProjectId("");
      return;
    }
    if (!projects.some((item) => item.id === projectId)) setProjectId(projects[0].id);
  }, [projects, projectId]);

  useEffect(() => {
    if (!scenes.length) {
      setSceneId("");
      return;
    }
    if (!scenes.some((item) => item.id === sceneId)) setSceneId(scenes[0].id);
  }, [scenes, sceneId]);

  useEffect(() => {
    if (!scene) return;
    setPageCount(project?.mode === "illustration" ? 1 : task?.page_count || 1);
    setStylePresetId(task?.style_preset_id || project?.style_preset_id || "");
    setSelectedCharacters(
      task ? task.character_snapshot.map((item) => item.id) : characters.map((item) => item.id),
    );
  }, [scene?.id, task?.id, task?.page_count, task?.style_preset_id, project?.mode, project?.style_preset_id, characters]);

  const groups = useMemo(() => {
    const map = new Map<string, StoryScene[]>();
    for (const item of scenes) {
      const key = item.chapter_title || "未分章";
      map.set(key, [...(map.get(key) || []), item]);
    }
    return [...map.entries()];
  }, [scenes]);

  const taskByScene = useMemo(() => {
    const map = new Map<string, StoryboardTask>();
    for (const item of tasks) {
      if (item.scene_id) map.set(item.scene_id, item);
    }
    return map;
  }, [tasks]);

  function showNotice(text: string) {
    setNotice(text);
    window.setTimeout(() => setNotice(""), 3200);
  }

  const updateScene = useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: Partial<StoryScene> }) =>
      api<StoryScene>(`/api/scenes/${id}`, { method: "PATCH", body: JSON.stringify(patch) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["scenes", projectId] }),
  });

  const createScene = useMutation({
    mutationFn: () => {
      const chapter = chaptersQuery.data?.[0];
      return api<StoryScene>(`/api/projects/${projectId}/scenes`, {
        method: "POST",
        body: JSON.stringify({
          title: "新场景",
          summary: "",
          excerpt: "",
          chapter_title: chapter?.title || "",
          chapter_index: chapter?.order_no || 0,
        }),
      });
    },
    onSuccess: async (created) => {
      await queryClient.invalidateQueries({ queryKey: ["scenes", projectId] });
      setSceneId(created.id);
    },
  });

  const deleteScene = useMutation({
    mutationFn: (id: string) => api(`/api/scenes/${id}`, { method: "DELETE" }),
    onSuccess: async () => {
      setSceneId("");
      await queryClient.invalidateQueries({ queryKey: ["scenes", projectId] });
      await queryClient.invalidateQueries({ queryKey: ["tasks", projectId] });
    },
  });

  const createTask = useMutation({
    mutationFn: () =>
      api<StoryboardTask>(`/api/projects/${projectId}/tasks`, {
        method: "POST",
        body: JSON.stringify({
          scene_id: sceneId,
          page_count: pageCount,
          style_preset_id: stylePresetId || null,
          character_ids: selectedCharacters,
        }),
      }),
    onSuccess: async (created) => {
      await queryClient.invalidateQueries({ queryKey: ["tasks", projectId] });
      await queryClient.invalidateQueries({ queryKey: ["scenes", projectId] });
      showNotice(`已生成 ${created.page_count} 页分镜任务`);
    },
    onError: () => showNotice("创建分镜任务失败"),
  });

  const deleteTask = useMutation({
    mutationFn: (id: string) => api(`/api/tasks/${id}`, { method: "DELETE" }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["tasks", projectId] });
      await queryClient.invalidateQueries({ queryKey: ["scenes", projectId] });
      showNotice("已删除分镜任务");
    },
  });

  const upsertCharacter = useMutation({
    mutationFn: () =>
      api<Character>(`/api/projects/${projectId}/characters`, {
        method: "POST",
        body: JSON.stringify({ name: characterName, anchor_tags: characterAnchor }),
      }),
    onSuccess: async () => {
      setCharacterName("");
      setCharacterAnchor("");
      await queryClient.invalidateQueries({ queryKey: ["characters", projectId] });
    },
  });

  const importProject = useMutation({
    mutationFn: async (file: File) => {
      const payload = JSON.parse(await file.text());
      return api<Project>("/api/projects/import", { method: "POST", body: JSON.stringify(payload) });
    },
    onSuccess: async (created) => {
      await queryClient.invalidateQueries({ queryKey: ["projects"] });
      setProjectId(created.id);
      setSettingsOpen(false);
    },
  });

  async function exportProject() {
    if (!projectId) return;
    const payload = await api<unknown>(`/api/projects/${projectId}/export`);
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${projectId}.json`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  function submitTask() {
    if (!scene) return;
    const message = task
      ? `重新拆分会删除当前任务（${task.page_count} 页）及其图片，确定覆盖？`
      : `创建 ${project?.mode === "illustration" ? 1 : pageCount} 页分镜任务？`;
    if (!window.confirm(message)) return;
    createTask.mutate();
  }

  function toggleCharacter(id: string) {
    setSelectedCharacters((current) =>
      current.includes(id) ? current.filter((item) => item !== id) : [...current, id],
    );
  }

  return (
    <div className="flex h-screen flex-col">
      <header className="panel m-3 flex flex-wrap items-center justify-between gap-3 p-4">
        <div>
          <div className="text-lg font-semibold">场景拆分</div>
          <div className="text-xs opacity-50">场景/事件 → 分镜任务 → 分镜台出图</div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <select className="bg-black/20 px-3 py-2 text-sm outline-none" value={projectId} onChange={(event) => setProjectId(event.target.value)}>
            {projects.map((item) => (
              <option key={item.id} value={item.id}>
                [{item.mode === "illustration" ? "插图" : "漫画"}] {item.title}
              </option>
            ))}
          </select>
          <a className="border border-white/20 px-3 py-2 text-sm" href={`/story?project=${projectId}`}>
            去故事
          </a>
          <a className="border border-white/20 px-3 py-2 text-sm" href={task ? `/board?project=${projectId}&task=${task.id}` : `/board?project=${projectId}`}>
            去分镜台
          </a>
          <button className="border border-white/20 px-3 py-2 text-sm" onClick={() => setSettingsOpen(true)} disabled={!projectId}>
            项目资料
          </button>
          {notice && <span className="mono text-xs text-[#ffb4a0]">{notice}</span>}
        </div>
      </header>

      <main className="grid min-h-0 flex-1 grid-cols-[260px_minmax(0,1fr)_400px] gap-3 px-3 pb-3">
        <aside className="panel flex min-h-0 flex-col p-3">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-sm font-medium">场景 / 事件</span>
            <button className="border border-white/20 px-2 py-1 text-xs disabled:opacity-40" disabled={!projectId} onClick={() => createScene.mutate()}>
              新增
            </button>
          </div>
          <div className="min-h-0 flex-1 overflow-auto">
            {groups.map(([chapterTitle, chapterScenes]) => (
              <div key={chapterTitle} className="mb-3">
                <div className="mono mb-1 text-[11px] uppercase opacity-40">{chapterTitle}</div>
                {chapterScenes.map((item) => {
                  const linkedTask = taskByScene.get(item.id);
                  return (
                    <button
                      key={item.id}
                      className={`mb-1 block w-full border px-2 py-2 text-left text-sm ${
                        sceneId === item.id ? "border-[#e4572e] text-[#ffb4a0]" : "border-transparent hover:border-white/15"
                      }`}
                      onClick={() => setSceneId(item.id)}
                    >
                      <div className="truncate">{item.title}</div>
                      <div className="mono mt-1 text-[10px] opacity-45">
                        {linkedTask ? `${linkedTask.page_count} 页 · ${linkedTask.status}` : "未拆分"}
                      </div>
                    </button>
                  );
                })}
              </div>
            ))}
            {!scenes.length && <div className="mt-8 text-center text-xs opacity-40">在故事页选中文字后送入场景，或点新增</div>}
          </div>
        </aside>

        <section className="panel min-h-0 overflow-auto p-4">
          {!scene ? (
            <div className="mt-20 text-center opacity-50">选择或新建一个场景</div>
          ) : (
            <div key={scene.id} className="space-y-3">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <input
                    className="w-full bg-transparent text-lg font-semibold outline-none"
                    defaultValue={scene.title}
                    onBlur={(event) => updateScene.mutate({ id: scene.id, patch: { title: event.target.value } })}
                  />
                  <div className="mono mt-1 text-xs opacity-45">{scene.status} · 场景 {scene.order_no}</div>
                </div>
                <button
                  className="border border-white/20 px-3 py-1 text-sm text-red-300"
                  onClick={() => window.confirm(`删除场景「${scene.title}」及其分镜任务？`) && deleteScene.mutate(scene.id)}
                >
                  删除场景
                </button>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <label className="block">
                  <span className="mb-1 block text-xs opacity-60">章节</span>
                  <input
                    className="w-full bg-black/20 px-2 py-1 text-sm outline-none"
                    defaultValue={scene.chapter_title}
                    onBlur={(event) => updateScene.mutate({ id: scene.id, patch: { chapter_title: event.target.value } })}
                  />
                </label>
                <label className="block">
                  <span className="mb-1 block text-xs opacity-60">地点 / 环境</span>
                  <input
                    className="w-full bg-black/20 px-2 py-1 text-sm outline-none"
                    defaultValue={scene.setting}
                    onBlur={(event) => updateScene.mutate({ id: scene.id, patch: { setting: event.target.value } })}
                  />
                </label>
                <label className="block">
                  <span className="mb-1 block text-xs opacity-60">情绪</span>
                  <input
                    className="w-full bg-black/20 px-2 py-1 text-sm outline-none"
                    defaultValue={scene.mood}
                    onBlur={(event) => updateScene.mutate({ id: scene.id, patch: { mood: event.target.value } })}
                  />
                </label>
                <label className="block">
                  <span className="mb-1 block text-xs opacity-60">出场角色（文字备注）</span>
                  <input
                    className="w-full bg-black/20 px-2 py-1 text-sm outline-none"
                    defaultValue={scene.characters}
                    onBlur={(event) => updateScene.mutate({ id: scene.id, patch: { characters: event.target.value } })}
                  />
                </label>
              </div>

              <label className="block">
                <span className="mb-1 block text-xs opacity-60">场景摘要</span>
                <textarea
                  className="h-20 w-full resize-none bg-black/20 p-2 text-sm outline-none"
                  defaultValue={scene.summary}
                  onBlur={(event) => updateScene.mutate({ id: scene.id, patch: { summary: event.target.value } })}
                />
              </label>

              <label className="block">
                <span className="mb-1 block text-xs opacity-60">场景原文（拆分依据）</span>
                <textarea
                  className="serif h-[calc(100vh-470px)] min-h-40 w-full resize-none bg-black/20 p-3 text-sm leading-7 outline-none"
                  defaultValue={scene.excerpt}
                  onBlur={(event) => updateScene.mutate({ id: scene.id, patch: { excerpt: event.target.value } })}
                />
              </label>
            </div>
          )}
        </section>

        <aside className="panel flex min-h-0 flex-col overflow-auto p-3">
          {!scene ? (
            <div className="mt-20 text-center text-xs opacity-40">先选择场景</div>
          ) : (
            <div className="space-y-3">
              <div>
                <div className="text-sm font-medium">分镜任务</div>
                <div className="mt-1 text-xs opacity-50">一个场景对应一个任务；重新拆分直接覆盖旧任务。</div>
              </div>

              {task && (
                <div className="border border-white/15 p-3">
                  <div className="flex items-center justify-between">
                    <span className="mono text-xs opacity-60">{task.id}</span>
                    <span className="mono text-xs text-[#ffb4a0]">{task.status}</span>
                  </div>
                  <div className="mt-1 text-sm">{task.page_count} 页 · {task.kind === "illustration" ? "插图" : "漫画"}</div>
                  <div className="mt-1 text-xs opacity-50">画风：{task.style_snapshot.name || task.style_snapshot.id || "-"}</div>
                  <div className="text-xs opacity-50">角色：{task.character_snapshot.map((item) => item.name).join(" / ") || "无"}</div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <a className="border border-[#e4572e] px-3 py-1 text-sm text-[#e4572e]" href={`/board?project=${projectId}&task=${task.id}`}>
                      打开分镜台
                    </a>
                    <button
                      className="border border-white/20 px-3 py-1 text-sm text-red-300"
                      onClick={() => window.confirm(`删除任务及其 ${task.page_count} 页和图片？`) && deleteTask.mutate(task.id)}
                    >
                      删除任务
                    </button>
                  </div>
                </div>
              )}

              <div className="space-y-3 border-t border-white/10 pt-3">
                <label className="block">
                  <span className="mb-1 block text-xs opacity-60">拆成几页</span>
                  <input
                    className="mono w-28 bg-black/20 px-2 py-1 text-sm outline-none disabled:opacity-40"
                    type="number"
                    min={1}
                    max={20}
                    value={project?.mode === "illustration" ? 1 : pageCount}
                    disabled={project?.mode === "illustration"}
                    onChange={(event) => setPageCount(Math.max(1, Math.min(20, Number(event.target.value) || 1)))}
                  />
                  {project?.mode === "illustration" && <span className="ml-2 text-xs opacity-45">插图模式固定 1 页</span>}
                </label>

                <label className="block">
                  <span className="mb-1 block text-xs opacity-60">画风预设</span>
                  <select
                    className="w-full bg-black/20 px-2 py-1 text-sm outline-none"
                    value={stylePresetId}
                    onChange={(event) => setStylePresetId(event.target.value)}
                  >
                    <option value="">使用项目默认</option>
                    {stylesQuery.data?.map((style) => (
                      <option key={style.id} value={style.id}>
                        {style.name}
                      </option>
                    ))}
                  </select>
                </label>

                <div>
                  <div className="mb-1 text-xs opacity-60">锚定角色</div>
                  <div className="max-h-32 overflow-auto text-sm">
                    {characters.map((character) => (
                      <label key={character.id} className="mb-1 flex items-center gap-2">
                        <input
                          type="checkbox"
                          className="accent-[#e4572e]"
                          checked={selectedCharacters.includes(character.id)}
                          onChange={() => toggleCharacter(character.id)}
                        />
                        <span>{character.name}</span>
                        <span className="mono truncate text-[10px] opacity-45">{character.anchor_tags}</span>
                      </label>
                    ))}
                    {!characters.length && <div className="text-xs opacity-40">项目中还没有角色，去“项目资料”添加</div>}
                  </div>
                </div>

                <div className="border border-white/10 bg-black/20 p-2 text-xs opacity-60">
                  出图保存到：<span className="mono break-all">projects/{projectId}/images/</span>
                  <div className="mono mt-1 break-all">
                    {task ? `mioss_${projectId}_${task.id}_p001_*.png` : `mioss_${projectId}_t<任务ID>_p001_*.png`}
                  </div>
                </div>

                <button
                  className="w-full border border-[#e4572e] px-3 py-2 text-sm text-[#e4572e] disabled:opacity-40"
                  disabled={!scene || createTask.isPending}
                  onClick={submitTask}
                >
                  {task ? "重新拆分并覆盖" : "创建分镜任务"}
                </button>
                <div className="text-[11px] leading-5 opacity-40">
                  覆盖会删除旧任务的页记录和已生成图片（图片移入回收目录），再按当前原文和页数重建。
                </div>
              </div>
            </div>
          )}
        </aside>
      </main>

      {settingsOpen && (
        <div className="fixed inset-0 z-40 bg-black/60" onClick={() => setSettingsOpen(false)}>
          <aside className="absolute right-0 top-0 h-full w-[420px] overflow-auto border-l border-white/15 bg-[#14161b] p-4" onClick={(event) => event.stopPropagation()}>
            <div className="mb-4 flex items-center justify-between">
              <div className="text-lg font-semibold">项目资料</div>
              <button className="border border-white/20 px-2 py-1 text-xs" onClick={() => setSettingsOpen(false)}>
                关闭
              </button>
            </div>

            <div className="panel mb-4 p-3">
              <div className="mb-2 text-sm font-medium">角色圣经</div>
              <div className="mb-3 max-h-40 overflow-auto text-xs">
                {characters.map((character) => (
                  <div key={character.id} className="mb-1 border-b border-white/10 py-1">
                    <div className="font-medium">{character.name}</div>
                    <div className="mono opacity-50">{character.anchor_tags}</div>
                  </div>
                ))}
                {!characters.length && <div className="opacity-40">暂无角色</div>}
              </div>
              <input
                className="mb-2 w-full bg-black/20 px-2 py-1 text-sm outline-none"
                value={characterName}
                onChange={(event) => setCharacterName(event.target.value)}
                placeholder="角色名"
              />
              <textarea
                className="mono mb-2 h-16 w-full resize-none bg-black/20 p-2 text-xs outline-none"
                value={characterAnchor}
                onChange={(event) => setCharacterAnchor(event.target.value)}
                placeholder="角色锚点 tag，例如 1girl, silver hair, amber eyes"
              />
              <button
                className="border border-white/20 px-3 py-1 text-sm disabled:opacity-40"
                disabled={!characterName.trim() || !characterAnchor.trim() || upsertCharacter.isPending}
                onClick={() => upsertCharacter.mutate()}
              >
                添加角色
              </button>
            </div>

            <div className="panel p-3">
              <div className="mb-2 text-sm font-medium">项目导入 / 导出</div>
              <div className="flex gap-2">
                <button className="border border-white/20 px-3 py-1 text-sm disabled:opacity-40" disabled={!projectId} onClick={exportProject}>
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
            </div>
          </aside>
        </div>
      )}
    </div>
  );
}

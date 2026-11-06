import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { api, type Project, type PromptPreset } from "../api";
import { copyText } from "../utils/clipboard";

const EMPTY = { name: "", kind: "style", positive: "", negative: "", notes: "", seed: "", preview_image: "" };

export default function PresetsPage() {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<typeof EMPTY>(EMPTY);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [projectId, setProjectId] = useState("");

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

  const presetsQuery = useQuery({
    queryKey: ["presets"],
    queryFn: () => api<PromptPreset[]>("/api/presets"),
  });

  const projectPresetsQuery = useQuery({
    queryKey: ["project-presets", projectId],
    queryFn: () => api<PromptPreset[]>(`/api/projects/${projectId}/presets`),
    enabled: !!projectId,
  });

  const boundIds = new Set((projectPresetsQuery.data || []).map((preset) => preset.id));

  const savePreset = useMutation({
    mutationFn: () =>
      api<PromptPreset>("/api/presets", {
        method: "POST",
        body: JSON.stringify({
          id: editingId || undefined,
          name: form.name || "未命名配方",
          kind: form.kind,
          positive: form.positive,
          negative: form.negative,
          notes: form.notes,
          seed: form.seed ? Number(form.seed) : null,
          preview_image: form.preview_image || null,
        }),
      }),
    onSuccess: () => {
      setForm(EMPTY);
      setEditingId(null);
      queryClient.invalidateQueries({ queryKey: ["presets"] });
      queryClient.invalidateQueries({ queryKey: ["project-presets", projectId] });
    },
  });

  const deletePreset = useMutation({
    mutationFn: (id: string) => api(`/api/presets/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["presets"] });
      queryClient.invalidateQueries({ queryKey: ["project-presets", projectId] });
    },
  });

  const bindPreset = useMutation({
    mutationFn: (id: string) => api(`/api/projects/${projectId}/presets/${id}`, { method: "POST" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["project-presets", projectId] }),
  });

  const unbindPreset = useMutation({
    mutationFn: (id: string) => api(`/api/projects/${projectId}/presets/${id}`, { method: "DELETE" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["project-presets", projectId] }),
  });

  function edit(preset: PromptPreset) {
    setEditingId(preset.id);
    setForm({
      name: preset.name,
      kind: preset.kind,
      positive: preset.positive,
      negative: preset.negative || "",
      notes: preset.notes || "",
      seed: preset.seed == null ? "" : String(preset.seed),
      preview_image: preset.preview_image || "",
    });
  }

  return (
    <div className="flex h-screen flex-col">
      <header className="panel m-3 flex flex-wrap items-center justify-between gap-3 p-4">
        <div>
          <div className="text-lg font-semibold">配方库</div>
          <div className="text-xs opacity-50">风格 / 角色 / 负面 / 场景 · 项目级锁定</div>
        </div>
        <div className="flex items-center gap-2">
          <select className="bg-black/20 px-3 py-2 text-sm outline-none" value={projectId} onChange={(event) => setProjectId(event.target.value)}>
            {projectsQuery.data?.map((project) => (
              <option key={project.id} value={project.id}>
                {project.title}
              </option>
            ))}
          </select>
          <span className="text-xs opacity-50">当前项目绑定 {boundIds.size} 个配方</span>
          <button className="border border-white/20 px-3 py-1 text-sm" onClick={() => { setEditingId(null); setForm(EMPTY); }}>
            新建配方
          </button>
        </div>
      </header>

      <div className="grid min-h-0 flex-1 grid-cols-[420px_minmax(0,1fr)] gap-3 px-3 pb-3">
        <aside className="panel min-h-0 overflow-auto p-4">
          <div className="mb-2 text-sm font-medium">{editingId ? "编辑配方" : "新建配方"}</div>
          <label className="mb-2 block text-sm">
            名称
            <input className="mt-1 w-full bg-black/25 px-2 py-1 outline-none" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </label>
          <label className="mb-2 block text-sm">
            类型
            <select className="mt-1 w-full bg-black/25 px-2 py-1 outline-none" value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value })}>
              <option value="style">风格</option>
              <option value="character">角色</option>
              <option value="negative">负面</option>
              <option value="scene">场景构图</option>
              <option value="combination">组合</option>
            </select>
          </label>
          <label className="mb-2 block text-sm">
            正向提示词
            <textarea className="mono mt-1 h-32 w-full resize-none bg-black/25 p-2 text-sm outline-none" value={form.positive} onChange={(e) => setForm({ ...form, positive: e.target.value })} />
          </label>
          <label className="mb-2 block text-sm">
            负向提示词
            <textarea className="mono mt-1 h-24 w-full resize-none bg-black/25 p-2 text-sm outline-none" value={form.negative} onChange={(e) => setForm({ ...form, negative: e.target.value })} />
          </label>
          <label className="mb-2 block text-sm">
            Seed（可选）
            <input className="mono mt-1 w-full bg-black/25 px-2 py-1 outline-none" value={form.seed} onChange={(e) => setForm({ ...form, seed: e.target.value })} />
          </label>
          <label className="mb-2 block text-sm">
            预览图 URL（可选）
            <input className="mono mt-1 w-full bg-black/25 px-2 py-1 outline-none" value={form.preview_image} onChange={(e) => setForm({ ...form, preview_image: e.target.value })} />
          </label>
          <label className="mb-3 block text-sm">
            备注
            <input className="mt-1 w-full bg-black/25 px-2 py-1 outline-none" value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
          </label>
          <button className="border border-[#e4572e] px-4 py-2 text-sm text-[#e4572e]" onClick={() => savePreset.mutate()}>
            保存配方
          </button>
        </aside>

        <main className="panel min-h-0 overflow-auto p-3">
          <div className="grid grid-cols-2 gap-3 xl:grid-cols-3">
            {presetsQuery.data?.map((preset) => (
              <div key={preset.id} className={`border p-3 ${boundIds.has(preset.id) ? "border-[#e4572e]/60" : "border-white/10"}`}>
                {preset.preview_image && <img src={preset.preview_image} alt={preset.name} className="mb-2 h-40 w-full object-cover" />}
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <div className="font-medium">{preset.name}</div>
                    <div className="mono text-xs opacity-50">
                      {preset.kind} / v{preset.version} / 用过 {preset.usage_count} 次
                    </div>
                  </div>
                  <div className="flex flex-col items-end gap-1">
                    <button className="text-xs text-[#e4572e]" onClick={() => edit(preset)}>编辑</button>
                    <button className="text-xs text-red-300" onClick={() => deletePreset.mutate(preset.id)}>删除</button>
                  </div>
                </div>
                <pre className="mono mt-2 max-h-32 overflow-auto whitespace-pre-wrap text-xs opacity-75">{preset.positive}</pre>
                {preset.negative && <pre className="mono mt-1 max-h-20 overflow-auto whitespace-pre-wrap text-xs text-red-200/60">{preset.negative}</pre>}
                <div className="mt-2 flex flex-wrap gap-2">
                  <button className="border border-white/20 px-2 py-1 text-xs" onClick={() => copyText(preset.positive)}>复制正向</button>
                  <button className="border border-white/20 px-2 py-1 text-xs" onClick={() => copyText(preset.negative)}>复制负向</button>
                  {boundIds.has(preset.id) ? (
                    <button className="border border-[#e4572e] px-2 py-1 text-xs text-[#e4572e]" onClick={() => unbindPreset.mutate(preset.id)}>
                      解绑项目
                    </button>
                  ) : (
                    <button className="border border-white/20 px-2 py-1 text-xs" onClick={() => bindPreset.mutate(preset.id)}>
                      绑定到项目
                    </button>
                  )}
                </div>
              </div>
            ))}
            {!presetsQuery.data?.length && <div className="opacity-40">还没有配方</div>}
          </div>
        </main>
      </div>
    </div>
  );
}

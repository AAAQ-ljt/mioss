import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, type PromptPreset } from "../api";
import { copyText } from "../utils/clipboard";

const EMPTY = { name: "", kind: "style", positive: "", negative: "", notes: "", seed: "" };

export default function PresetsPage() {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<typeof EMPTY>(EMPTY);
  const [editingId, setEditingId] = useState<string | null>(null);

  const presetsQuery = useQuery({
    queryKey: ["presets"],
    queryFn: () => api<PromptPreset[]>("/api/presets"),
  });

  const savePreset = useMutation({
    mutationFn: () =>
      api<PromptPreset>("/api/presets", {
        method: "POST",
        body: JSON.stringify({
          id: editingId || undefined,
          name: form.name || "未命名预设",
          kind: form.kind,
          positive: form.positive,
          negative: form.negative,
          notes: form.notes,
          seed: form.seed ? Number(form.seed) : null,
        }),
      }),
    onSuccess: () => {
      setForm(EMPTY);
      setEditingId(null);
      queryClient.invalidateQueries({ queryKey: ["presets"] });
    },
  });

  const deletePreset = useMutation({
    mutationFn: (id: string) => api(`/api/presets/${id}`, { method: "DELETE" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["presets"] }),
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
    });
  }

  async function copy(value: string) {
    if (value) await copyText(value);
  }

  return (
    <div className="flex h-screen flex-col">
      <header className="panel m-3 flex items-center justify-between p-4">
        <div>
          <div className="text-lg font-semibold">预设库</div>
          <div className="text-xs opacity-50">像 LoRA 一样固定风格、角色、负面和 seed</div>
        </div>
        <button className="border border-white/20 px-3 py-1 text-sm" onClick={() => { setEditingId(null); setForm(EMPTY); }}>
          新建预设
        </button>
      </header>

      <div className="grid min-h-0 flex-1 grid-cols-[420px_minmax(0,1fr)] gap-3 px-3 pb-3">
        <aside className="panel min-h-0 overflow-auto p-4">
          <div className="mb-2 text-sm font-medium">{editingId ? "编辑预设" : "新建预设"}</div>
          <label className="mb-2 block text-sm">
            名称
            <input className="mt-1 w-full bg-black/25 px-2 py-1 outline-none" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </label>
          <label className="mb-2 block text-sm">
            类型
            <select className="mt-1 w-full bg-black/25 px-2 py-1 outline-none" value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value })}>
              <option value="style">风格</option>
              <option value="character">角色</option>
              <option value="scene">场景</option>
              <option value="negative">负面</option>
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
          <label className="mb-3 block text-sm">
            备注
            <input className="mt-1 w-full bg-black/25 px-2 py-1 outline-none" value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
          </label>
          <button className="border border-[#e4572e] px-4 py-2 text-sm text-[#e4572e]" onClick={() => savePreset.mutate()}>
            保存预设
          </button>
        </aside>

        <main className="panel min-h-0 overflow-auto p-3">
          <div className="grid grid-cols-2 gap-3 xl:grid-cols-3">
            {presetsQuery.data?.map((preset) => (
              <div key={preset.id} className="border border-white/10 p-3">
                <div className="flex items-start justify-between">
                  <div>
                    <div className="font-medium">{preset.name}</div>
                    <div className="mono text-xs opacity-50">{preset.kind} / {preset.id}</div>
                  </div>
                  <div className="flex gap-1">
                    <button className="text-xs text-[#e4572e]" onClick={() => edit(preset)}>编辑</button>
                    <button className="text-xs text-red-300" onClick={() => deletePreset.mutate(preset.id)}>删除</button>
                  </div>
                </div>
                <pre className="mono mt-2 max-h-32 overflow-auto whitespace-pre-wrap text-xs opacity-75">{preset.positive}</pre>
                {preset.negative && <pre className="mono mt-1 max-h-20 overflow-auto whitespace-pre-wrap text-xs text-red-200/60">{preset.negative}</pre>}
                <div className="mt-2 flex gap-2">
                  <button className="border border-white/20 px-2 py-1 text-xs" onClick={() => copy(preset.positive)}>复制正向</button>
                  <button className="border border-white/20 px-2 py-1 text-xs" onClick={() => copy(preset.negative)}>复制负向</button>
                </div>
              </div>
            ))}
            {!presetsQuery.data?.length && <div className="opacity-40">还没有预设</div>}
          </div>
        </main>
      </div>
    </div>
  );
}

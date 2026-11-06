import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, type RelayItem } from "../api";
import { copyText } from "../utils/clipboard";

export default function RelayPage() {
  const queryClient = useQueryClient();
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [composed, setComposed] = useState("");

  const relayQuery = useQuery({
    queryKey: ["relay"],
    queryFn: () => api<RelayItem[]>("/api/relay?limit=200"),
  });

  const deleteItem = useMutation({
    mutationFn: (id: string) => api(`/api/relay/${id}`, { method: "DELETE" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["relay"] }),
  });

  const clearAll = useMutation({
    mutationFn: () => api("/api/relay", { method: "DELETE" }),
    onSuccess: () => {
      setSelectedIds([]);
      queryClient.invalidateQueries({ queryKey: ["relay"] });
    },
  });

  function toggle(id: string) {
    setSelectedIds((current) => (current.includes(id) ? current.filter((item) => item !== id) : [...current, id]));
  }

  function compose() {
    const items = (relayQuery.data || []).filter((item) => selectedIds.includes(item.id));
    setComposed(items.map((item) => item.content.trim()).filter(Boolean).join(", "));
  }

  async function copyComposed() {
    if (!composed) return;
    await copyText(composed);
  }

  return (
    <div className="flex h-screen flex-col">
      <header className="panel m-3 flex items-center justify-between p-4">
        <div>
          <div className="text-lg font-semibold">TAG 中转站</div>
          <div className="text-xs opacity-50">复制进中转站的提示词，可组合、删除、再复制</div>
        </div>
        <div className="flex gap-2">
          <button className="border border-white/20 px-3 py-1 text-sm" onClick={compose}>
            组合选中
          </button>
          <button className="border border-white/20 px-3 py-1 text-sm" onClick={() => clearAll.mutate()} disabled={!relayQuery.data?.length}>
            清空
          </button>
        </div>
      </header>

      <div className="grid min-h-0 flex-1 grid-cols-[minmax(0,1fr)_420px] gap-3 px-3 pb-3">
        <main className="panel min-h-0 overflow-auto p-3">
          {relayQuery.data?.map((item) => (
            <div key={item.id} className="mb-2 border border-white/10 p-2">
              <div className="flex items-start gap-2">
                <input type="checkbox" checked={selectedIds.includes(item.id)} onChange={() => toggle(item.id)} className="mt-1" />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between gap-2">
                    <div className="text-sm font-medium">
                      {item.source_title || "手动复制"}
                      <span className="mono ml-2 text-xs opacity-50">{item.format.toUpperCase()}</span>
                    </div>
                    <button className="text-xs text-red-300" onClick={() => deleteItem.mutate(item.id)}>
                      删除
                    </button>
                  </div>
                  <pre className="mono mt-2 max-h-28 overflow-auto whitespace-pre-wrap text-xs opacity-75">{item.content}</pre>
                </div>
              </div>
            </div>
          ))}
          {!relayQuery.data?.length && <div className="mt-20 text-center text-sm opacity-40">还没有复制记录</div>}
        </main>

        <aside className="panel flex min-h-0 flex-col p-3">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-sm font-medium">组合区</span>
            <button className="border border-[#e4572e] px-3 py-1 text-sm text-[#e4572e]" onClick={copyComposed} disabled={!composed}>
              复制组合
            </button>
          </div>
          <textarea
            className="mono min-h-0 flex-1 resize-none bg-black/25 p-3 text-sm outline-none"
            value={composed}
            onChange={(event) => setComposed(event.target.value)}
            placeholder="勾选左侧条目后点“组合选中”，也可以手动编辑"
          />
          <div className="mono mt-2 text-xs opacity-50">{composed.split(",").filter(Boolean).length} 个 tag</div>
        </aside>
      </div>
    </div>
  );
}

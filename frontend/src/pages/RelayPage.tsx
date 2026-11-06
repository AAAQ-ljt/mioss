import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { api, type FavoriteItem } from "../api";
import { copyText } from "../utils/clipboard";

type Format = "nai" | "moss" | "sd";
type ComposeResult = { positive: string; negative: string; count: number; mixed: boolean; missing: string[] };

function FavoriteCard({
  item,
  selected,
  order,
  onToggle,
  onRemove,
}: {
  item: FavoriteItem;
  selected: boolean;
  order: number;
  onToggle: () => void;
  onRemove: () => void;
}) {
  return (
    <div
      role="button"
      tabIndex={0}
      className={`panel mb-2 block w-full break-inside-avoid p-2 text-left ${selected ? "border-[#e4572e]" : "hover:border-white/30"}`}
      onClick={onToggle}
      onKeyDown={(event) => event.key === "Enter" && onToggle()}
    >
      <div className="relative">
        {item.image_url && <img src={item.image_url} alt={item.title} className="mb-2 w-full object-cover" loading="lazy" />}
        <div className={`absolute left-2 top-2 flex h-6 w-6 items-center justify-center rounded-full text-xs font-bold ${selected ? "bg-[#e4572e] text-white" : "bg-black/65 text-white/70"}`}>
          {selected ? order : ""}
        </div>
        <button
          className="absolute right-2 top-2 bg-black/65 px-2 py-1 text-xs text-red-300"
          onClick={(event) => {
            event.stopPropagation();
            onRemove();
          }}
        >
          移除
        </button>
      </div>
      <div className="truncate text-sm font-medium">{item.title}</div>
      <div className="mono mt-1 line-clamp-2 text-xs opacity-50">{item.prompt_moss}</div>
      <div className="mono mt-2 truncate text-[11px] opacity-40">{item.source_title}</div>
    </div>
  );
}

export default function RelayPage() {
  const queryClient = useQueryClient();
  const [format, setFormat] = useState<Format>("moss");
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [composed, setComposed] = useState<ComposeResult | null>(null);

  const favoritesQuery = useQuery({
    queryKey: ["favorites"],
    queryFn: () => api<FavoriteItem[]>("/api/favorites"),
  });

  const groups = useMemo(
    () => ({
      regular: (favoritesQuery.data || []).filter((item) => item.domain === "regular"),
      nsfw: (favoritesQuery.data || []).filter((item) => item.domain === "nsfw"),
    }),
    [favoritesQuery.data],
  );

  const removeFavorite = useMutation({
    mutationFn: (entryId: string) => api(`/api/favorites/${entryId}`, { method: "DELETE" }),
    onSuccess: (_result, entryId) => {
      setSelectedIds((current) => current.filter((item) => item !== entryId));
      queryClient.invalidateQueries({ queryKey: ["favorites"] });
      queryClient.invalidateQueries({ queryKey: ["favorite-ids"] });
    },
  });

  const clearFavorites = useMutation({
    mutationFn: () => api("/api/favorites", { method: "DELETE" }),
    onSuccess: () => {
      setSelectedIds([]);
      setComposed(null);
      queryClient.invalidateQueries({ queryKey: ["favorites"] });
      queryClient.invalidateQueries({ queryKey: ["favorite-ids"] });
    },
  });

  const compose = useMutation({
    mutationFn: () =>
      api<ComposeResult>("/api/favorites/compose", {
        method: "POST",
        body: JSON.stringify({ entry_ids: selectedIds, format }),
      }),
    onSuccess: (result) => setComposed(result),
  });

  function toggle(entryId: string) {
    setSelectedIds((current) =>
      current.includes(entryId) ? current.filter((item) => item !== entryId) : [...current, entryId],
    );
    setComposed(null);
  }

  const selectedItems = selectedIds
    .map((entryId) => favoritesQuery.data?.find((item) => item.entry_id === entryId))
    .filter((item): item is FavoriteItem => !!item);

  return (
    <div className="flex h-screen flex-col">
      <header className="panel m-3 flex flex-wrap items-center justify-between gap-3 p-4">
        <div>
          <div className="text-lg font-semibold">TAG 中转站</div>
          <div className="text-xs opacity-50">收藏卡片 · 常规 / NSFW 双栏 · 跨栏多选组合</div>
        </div>
        <div className="flex items-center gap-2">
          <span className="mono text-xs opacity-50">{favoritesQuery.data?.length || 0} 张收藏</span>
          <button
            className="border border-white/20 px-3 py-1 text-sm"
            onClick={() => window.confirm("清空所有收藏？") && clearFavorites.mutate()}
            disabled={!favoritesQuery.data?.length}
          >
            清空收藏
          </button>
        </div>
      </header>

      <main className="grid min-h-0 flex-1 grid-cols-2 gap-3 px-3 pb-3">
        <section className="panel flex min-h-0 flex-col p-3">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-sm font-semibold">常规</span>
            <span className="mono text-xs opacity-40">{groups.regular.length}</span>
          </div>
          <div className="min-h-0 flex-1 overflow-auto">
            <div className="columns-2 gap-2">
              {groups.regular.map((item) => (
                <FavoriteCard
                  key={item.entry_id}
                  item={item}
                  selected={selectedIds.includes(item.entry_id)}
                  order={selectedIds.indexOf(item.entry_id) + 1}
                  onToggle={() => toggle(item.entry_id)}
                  onRemove={() => removeFavorite.mutate(item.entry_id)}
                />
              ))}
            </div>
            {!groups.regular.length && <div className="mt-20 text-center text-sm opacity-40">常规收藏为空</div>}
          </div>
        </section>

        <section className="panel flex min-h-0 flex-col p-3">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-sm font-semibold">NSFW</span>
            <span className="mono text-xs opacity-40">{groups.nsfw.length}</span>
          </div>
          <div className="min-h-0 flex-1 overflow-auto">
            <div className="columns-2 gap-2">
              {groups.nsfw.map((item) => (
                <FavoriteCard
                  key={item.entry_id}
                  item={item}
                  selected={selectedIds.includes(item.entry_id)}
                  order={selectedIds.indexOf(item.entry_id) + 1}
                  onToggle={() => toggle(item.entry_id)}
                  onRemove={() => removeFavorite.mutate(item.entry_id)}
                />
              ))}
            </div>
            {!groups.nsfw.length && <div className="mt-20 text-center text-sm opacity-40">NSFW 收藏为空</div>}
          </div>
        </section>
      </main>

      <footer className="panel mx-3 mb-3 p-3">
        <div className="mb-2 flex flex-wrap items-center gap-2">
          <span className="text-sm font-medium">组合区</span>
          {selectedItems.map((item, index) => (
            <button
              key={item.entry_id}
              className="mono border border-[#e4572e]/60 bg-[#e4572e]/10 px-2 py-1 text-xs text-[#ffb4a0]"
              onClick={() => toggle(item.entry_id)}
            >
              {index + 1}. {item.title} ×
            </button>
          ))}
          {!selectedItems.length && <span className="text-xs opacity-40">在左右两栏点选卡片</span>}
          {composed?.mixed && <span className="text-xs text-yellow-300">混合常规 + NSFW</span>}
          <div className="ml-auto flex items-center gap-2">
            <div className="flex border border-white/15">
              {(["nai", "moss", "sd"] as Format[]).map((value) => (
                <button
                  key={value}
                  className={`px-3 py-1 text-xs ${format === value ? "bg-[#e4572e] text-white" : "hover:bg-white/5"}`}
                  onClick={() => {
                    setFormat(value);
                    setComposed(null);
                  }}
                >
                  {value.toUpperCase()}
                </button>
              ))}
            </div>
            <button
              className="border border-[#e4572e] px-4 py-1 text-sm text-[#e4572e] disabled:opacity-40"
              onClick={() => compose.mutate()}
              disabled={!selectedIds.length || compose.isPending}
            >
              组合
            </button>
            <button
              className="border border-white/20 px-4 py-1 text-sm disabled:opacity-40"
              onClick={() => composed && copyText(composed.positive)}
              disabled={!composed?.positive}
            >
              复制组合
            </button>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-2">
          <textarea
            className="mono h-28 resize-none bg-black/25 p-2 text-xs outline-none"
            value={composed?.positive || ""}
            onChange={(event) => composed && setComposed({ ...composed, positive: event.target.value })}
            placeholder="组合后的正向提示词"
          />
          <textarea
            className="mono h-28 resize-none bg-black/25 p-2 text-xs outline-none"
            value={composed?.negative || ""}
            onChange={(event) => composed && setComposed({ ...composed, negative: event.target.value })}
            placeholder="组合后的负向提示词"
          />
        </div>
      </footer>
    </div>
  );
}

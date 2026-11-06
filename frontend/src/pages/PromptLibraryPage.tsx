import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { api, type CodexEntry } from "../api";
import { copyText } from "../utils/clipboard";

type Domain = "regular" | "nsfw" | "reference";
type Format = "nai" | "moss" | "sd";
type Category = { id: string; name: string; count: number; order_no: number };

const DOMAIN_TABS: { id: Domain; label: string }[] = [
  { id: "regular", label: "常规" },
  { id: "nsfw", label: "NSFW 18+" },
  { id: "reference", label: "画师参考" },
];

function categoryPathLabel(entry: CodexEntry): string {
  try {
    return (JSON.parse(entry.category_path_json) as string[]).join(" / ");
  } catch {
    return "";
  }
}

export default function PromptLibraryPage() {
  const queryClient = useQueryClient();
  const [domain, setDomain] = useState<Domain>("regular");
  const [query, setQuery] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [format, setFormat] = useState<Format>("moss");
  const [selected, setSelected] = useState<CodexEntry | null>(null);
  const [notice, setNotice] = useState("");

  useEffect(() => {
    setCategoryId("");
  }, [domain]);

  const categoriesQuery = useQuery({
    queryKey: ["library-categories", domain],
    queryFn: () => api<Category[]>(`/api/library/categories?domain=${domain}`),
  });

  const favoriteIdsQuery = useQuery({
    queryKey: ["favorite-ids"],
    queryFn: () => api<string[]>("/api/favorites/ids"),
  });

  const favoriteSet = new Set(favoriteIdsQuery.data || []);

  const toggleFavorite = useMutation({
    mutationFn: (entryId: string) =>
      api<{ favorited: boolean }>("/api/favorites/toggle", {
        method: "POST",
        body: JSON.stringify({ entry_id: entryId }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["favorite-ids"] });
      queryClient.invalidateQueries({ queryKey: ["favorites"] });
    },
  });

  const searchQuery = useQuery({
    queryKey: ["library-search", query, domain, categoryId],
    queryFn: () =>
      api<CodexEntry[]>(
        `/api/codex/search?q=${encodeURIComponent(query)}&domain=${domain}&limit=60&include_nsfw=${
          domain !== "regular"
        }&include_artist_only=${domain === "reference"}${
          categoryId ? `&category_id=${encodeURIComponent(categoryId)}` : ""
        }`,
      ),
    enabled: true,
  });

  const relayMutation = useMutation({
    mutationFn: (payload: { content: string; entry: CodexEntry }) =>
      api("/api/relay", {
        method: "POST",
        body: JSON.stringify({
          content: payload.content,
          format,
          source_entry_id: payload.entry.id,
          source_title: payload.entry.title,
        }),
      }),
  });

  function textFor(entry: CodexEntry, target: Format = format): string {
    if (target === "nai") return entry.tags_raw || entry.tags_positive || "";
    if (target === "sd") return entry.prompt_sd_positive || entry.tags_positive || "";
    return entry.tags_positive || "";
  }

  async function copyEntry(entry: CodexEntry, target: Format = format, negative = false) {
    const text = negative
      ? target === "sd"
        ? entry.prompt_sd_negative || entry.tags_negative || ""
        : entry.tags_negative || ""
      : textFor(entry, target);
    if (!text) return;
    const ok = await copyText(text);
    if (!negative) relayMutation.mutate({ content: text, entry });
    setNotice(ok ? (negative ? "负向已复制" : "已复制并加入中转站") : "已加入中转站，但剪贴板不可用");
    window.setTimeout(() => setNotice(""), 2500);
  }

  const domainLabel = DOMAIN_TABS.find((tab) => tab.id === domain)?.label || "全部内容";

  return (
    <div className="flex h-screen flex-col">
      <header className="panel m-3 flex flex-wrap items-center gap-3 p-3">
        <div className="min-w-[180px]">
          <div className="text-lg font-semibold">提示词检索</div>
          <div className="text-xs opacity-50">{domainLabel} · 全库</div>
        </div>
        <div className="flex border border-white/15">
          {DOMAIN_TABS.map((tab) => (
            <button
              key={tab.id}
              className={`px-4 py-2 text-sm ${domain === tab.id ? "bg-[#e4572e] text-white" : "hover:bg-white/5"}`}
              onClick={() => setDomain(tab.id)}
            >
              {tab.label}
            </button>
          ))}
        </div>
        <input
          className="min-w-[240px] flex-1 border border-white/15 bg-black/20 px-3 py-2 outline-none"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="搜索中文 / 英文 tag（留空浏览当前分类）"
        />
        <div className="flex border border-white/15">
          {(["nai", "moss", "sd"] as Format[]).map((item) => (
            <button
              key={item}
              className={`px-3 py-2 text-sm ${format === item ? "bg-[#e4572e] text-white" : "hover:bg-white/5"}`}
              onClick={() => setFormat(item)}
            >
              {item === "nai" ? "NAI" : item === "moss" ? "MOSS" : "SD权重"}
            </button>
          ))}
        </div>
      </header>

      <div className="grid min-h-0 flex-1 grid-cols-[220px_minmax(0,1fr)_340px] gap-3 px-3 pb-3">
        <aside className="panel overflow-auto p-2">
          <button
            className={`mb-2 w-full px-2 py-2 text-left text-sm ${!categoryId ? "bg-white/10" : "hover:bg-white/5"}`}
            onClick={() => setCategoryId("")}
          >
            全部分类
          </button>
          {categoriesQuery.data?.map((category) => (
            <button
              key={category.id}
              className={`mb-0.5 flex w-full items-center justify-between px-2 py-2 text-left text-sm ${
                categoryId === category.id ? "bg-[#e4572e]/15 text-[#ffb4a0]" : "hover:bg-white/5"
              }`}
              onClick={() => setCategoryId(categoryId === category.id ? "" : category.id)}
            >
              <span>{category.name}</span>
              <span className="mono text-xs opacity-40">{category.count}</span>
            </button>
          ))}
        </aside>

        <main className="min-h-0 overflow-auto">
          <div className="mb-2 flex items-center justify-between text-xs opacity-60">
            <span>{searchQuery.data?.length || 0} 条结果</span>
            <span>{categoriesQuery.data?.find((category) => category.id === categoryId)?.name || "全部分类"}</span>
          </div>
          <div className="columns-2 gap-3 md:columns-3 xl:columns-4">
            {searchQuery.data?.map((entry) => (
              <div
                key={entry.id}
                role="button"
                tabIndex={0}
                className="panel mb-3 block w-full break-inside-avoid p-2 text-left hover:border-[#e4572e]"
                onClick={() => setSelected(entry)}
                onKeyDown={(event) => event.key === "Enter" && setSelected(entry)}
              >
                {entry.image_url && (
                  <div className="relative mb-2">
                    <img
                      src={`/api/codex/entries/${entry.id}/thumbnail`}
                      alt={entry.title}
                      className="w-full object-cover"
                      loading="lazy"
                    />
                    {domain !== "reference" && (
                      <button
                        className={`absolute right-2 top-2 border px-2 py-1 text-lg leading-none ${
                          favoriteSet.has(entry.id)
                            ? "border-[#e4572e] bg-[#e4572e] text-white"
                            : "border-white/40 bg-black/60 text-white/80"
                        }`}
                        title={favoriteSet.has(entry.id) ? "取消收藏" : "收藏"}
                        onClick={(event) => {
                          event.stopPropagation();
                          toggleFavorite.mutate(entry.id);
                        }}
                      >
                        {favoriteSet.has(entry.id) ? "♥" : "♡"}
                      </button>
                    )}
                  </div>
                )}
                <div className="truncate text-sm font-medium">{entry.title}</div>
                <div className="mono mt-1 line-clamp-2 text-xs opacity-50">{textFor(entry)}</div>
                <div className="mt-2 flex items-center justify-between gap-2">
                  <span className="mono truncate text-[11px] opacity-40">{categoryPathLabel(entry)}</span>
                  <button
                    className="shrink-0 border border-[#e4572e] px-2 py-1 text-[11px] text-[#e4572e]"
                    onClick={(event) => {
                      event.stopPropagation();
                      copyEntry(entry);
                    }}
                  >
                    复制
                  </button>
                </div>
              </div>
            ))}
          </div>
          {searchQuery.isFetching && <div className="p-6 text-center text-sm opacity-50">检索中…</div>}
        </main>

        <aside className="panel min-h-0 overflow-auto p-3">
          {selected ? (
            <div className="space-y-3">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <div className="text-lg font-semibold">{selected.title}</div>
                  <div className="mono text-xs opacity-50">{selected.id}</div>
                  <div className="mt-1 text-xs opacity-60">{categoryPathLabel(selected)}</div>
                </div>
                <div className="flex gap-1">
                  {domain !== "reference" && (
                    <button
                      className={`border px-2 py-1 text-xs ${
                        favoriteSet.has(selected.id) ? "border-[#e4572e] text-[#e4572e]" : "border-white/20"
                      }`}
                      onClick={() => toggleFavorite.mutate(selected.id)}
                    >
                      {favoriteSet.has(selected.id) ? "♥ 已收藏" : "♡ 收藏"}
                    </button>
                  )}
                  <button className="border border-white/20 px-2 py-1 text-xs" onClick={() => setSelected(null)}>
                    关闭
                  </button>
                </div>
              </div>
              {selected.image_url && (
                <a href={selected.image_url} target="_blank" rel="noreferrer" className="block border border-white/15">
                  <img src={`/api/codex/entries/${selected.id}/thumbnail`} alt={selected.title} className="w-full" />
                </a>
              )}
              <div>
                <div className="mb-1 flex items-center justify-between text-sm">
                  <span>正向提示词</span>
                  <button className="border border-[#e4572e] px-2 py-1 text-xs text-[#e4572e]" onClick={() => copyEntry(selected)}>
                    复制并加入中转站
                  </button>
                </div>
                <pre className="mono max-h-52 overflow-auto whitespace-pre-wrap bg-black/25 p-2 text-xs">{textFor(selected)}</pre>
              </div>
              <div>
                <div className="mb-1 flex items-center justify-between text-sm">
                  <span>负向提示词</span>
                  <button className="border border-white/20 px-2 py-1 text-xs" onClick={() => copyEntry(selected, format, true)}>
                    复制负向
                  </button>
                </div>
                <pre className="mono max-h-32 overflow-auto whitespace-pre-wrap bg-black/25 p-2 text-xs">
                  {format === "sd" ? selected.prompt_sd_negative || selected.tags_negative : selected.tags_negative}
                </pre>
              </div>
              {selected.note && <div className="text-sm opacity-70">{selected.note}</div>}
              {notice && <div className="border border-[#e4572e]/50 bg-[#e4572e]/10 px-2 py-1 text-xs text-[#ffb4a0]">{notice}</div>}
              <div className="flex flex-wrap gap-2">
                {(["nai", "moss", "sd"] as Format[]).map((item) => (
                  <button
                    key={item}
                    className={`border px-2 py-1 text-xs ${format === item ? "border-[#e4572e] text-[#e4572e]" : "border-white/20"}`}
                    onClick={() => setFormat(item)}
                  >
                    {item.toUpperCase()}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="mt-20 text-center text-sm opacity-40">点一张图查看提示词</div>
          )}
        </aside>
      </div>
    </div>
  );
}

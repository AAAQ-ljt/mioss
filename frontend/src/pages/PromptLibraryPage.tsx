import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { api, type Codex, type CodexEntry } from "../api";
import { copyText } from "../utils/clipboard";

type CategoryNode = { name: string; count: number; children?: CategoryNode[] };
type Format = "nai" | "moss" | "sd";

function categoryPathLabel(entry: CodexEntry): string {
  try {
    return (JSON.parse(entry.category_path_json) as string[]).join(" / ");
  } catch {
    return "";
  }
}

function CategoryTree({
  nodes,
  parent,
  onSelect,
  active,
}: {
  nodes: CategoryNode[];
  parent: string;
  onSelect: (path: string) => void;
  active: string;
}) {
  return (
    <div className="text-sm">
      {nodes.map((node) => {
        const path = parent ? `${parent} / ${node.name}` : node.name;
        const hasChildren = (node.children || []).length > 0;
        return (
          <div key={path} className="mb-0.5">
            <button
              className={`flex w-full items-center justify-between px-2 py-1 text-left ${
                active === path ? "bg-[#e4572e]/15 text-[#ffb4a0]" : "hover:bg-white/5"
              }`}
              onClick={() => onSelect(active === path ? "" : path)}
            >
              <span className="truncate">{node.name}</span>
              <span className="mono ml-2 text-xs opacity-40">{node.count}</span>
            </button>
            {hasChildren && (
              <div className="ml-3 border-l border-white/10 pl-1">
                <CategoryTree nodes={node.children || []} parent={path} onSelect={onSelect} active={active} />
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

export default function PromptLibraryPage() {
  const [query, setQuery] = useState("森林");
  const [codexFilter, setCodexFilter] = useState("suozhang");
  const [categoryPath, setCategoryPath] = useState("");
  const [format, setFormat] = useState<Format>("moss");
  const [selected, setSelected] = useState<CodexEntry | null>(null);
  const [notice, setNotice] = useState("");

  const codexesQuery = useQuery({
    queryKey: ["codexes-all"],
    queryFn: () => api<Codex[]>("/api/codexes?include_nsfw=true"),
  });

  useEffect(() => {
    if (!codexesQuery.data?.length) return;
    if (!codexesQuery.data.some((codex) => codex.id === codexFilter)) {
      setCodexFilter(codexesQuery.data.find((codex) => !codex.id.startsWith("artist_"))?.id || "");
    }
  }, [codexesQuery.data, codexFilter]);

  const categoriesQuery = useQuery({
    queryKey: ["categories", codexFilter],
    queryFn: () => api<CategoryNode[]>(`/api/codex/categories?codex_id=${encodeURIComponent(codexFilter)}`),
    enabled: !!codexFilter,
  });

  useEffect(() => {
    setCategoryPath("");
  }, [codexFilter]);

  const searchQuery = useQuery({
    queryKey: ["library-search", query, codexFilter, categoryPath],
    queryFn: () =>
      api<CodexEntry[]>(
        `/api/codex/search?q=${encodeURIComponent(query)}&limit=60&include_nsfw=false${
          codexFilter ? `&codex_id=${encodeURIComponent(codexFilter)}` : ""
        }${categoryPath ? `&category_path=${encodeURIComponent(categoryPath)}` : ""}`,
      ),
    enabled: query.trim().length > 0,
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

  const codexTitle = useMemo(
    () => codexesQuery.data?.find((codex) => codex.id === codexFilter)?.title || codexFilter,
    [codexesQuery.data, codexFilter],
  );

  return (
    <div className="flex h-screen flex-col">
      <header className="panel m-3 flex flex-wrap items-center gap-3 p-3">
        <div className="min-w-[180px]">
          <div className="text-lg font-semibold">提示词检索</div>
          <div className="text-xs opacity-50">{codexTitle}</div>
        </div>
        <input
          className="min-w-[240px] flex-1 border border-white/15 bg-black/20 px-3 py-2 outline-none"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="搜索中文 / 英文 tag"
        />
        <select
          className="bg-black/20 px-3 py-2 text-sm outline-none"
          value={codexFilter}
          onChange={(event) => setCodexFilter(event.target.value)}
        >
          {codexesQuery.data?.map((codex) => (
            <option key={codex.id} value={codex.id}>
              {codex.title} ({codex.entry_count})
            </option>
          ))}
        </select>
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

      <div className="grid min-h-0 flex-1 grid-cols-[240px_minmax(0,1fr)_340px] gap-3 px-3 pb-3">
        <aside className="panel overflow-auto p-2">
          <button
            className={`mb-2 w-full px-2 py-1 text-left text-sm ${!categoryPath ? "bg-white/10" : "hover:bg-white/5"}`}
            onClick={() => setCategoryPath("")}
          >
            全部分类
          </button>
          {categoriesQuery.data && (
            <CategoryTree nodes={categoriesQuery.data} parent="" onSelect={setCategoryPath} active={categoryPath} />
          )}
          {!codexFilter && <div className="p-2 text-xs opacity-50">选择法典后显示分类</div>}
        </aside>

        <main className="min-h-0 overflow-auto">
          <div className="mb-2 flex items-center justify-between text-xs opacity-60">
            <span>{searchQuery.data?.length || 0} 条结果</span>
            <span>{categoryPath || "全部分类"}</span>
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
                  <img
                    src={`/api/codex/entries/${entry.id}/thumbnail`}
                    alt={entry.title}
                    className="mb-2 w-full object-cover"
                    loading="lazy"
                  />
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
                <button className="border border-white/20 px-2 py-1 text-xs" onClick={() => setSelected(null)}>
                  关闭
                </button>
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

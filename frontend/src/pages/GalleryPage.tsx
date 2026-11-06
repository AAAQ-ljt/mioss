import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState, type MouseEvent } from "react";
import { api, type GalleryItem, type Project } from "../api";

type ViewSize = "large" | "medium" | "small";
type MenuState = { x: number; y: number; item: GalleryItem } | null;

const VIEW_KEY = "moss.gallery.view";

const GRID: Record<ViewSize, string> = {
  large: "grid-cols-1 gap-5 sm:grid-cols-2 xl:grid-cols-3",
  medium: "grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-4",
  small: "grid-cols-3 gap-2 md:grid-cols-5 xl:grid-cols-8",
};

function label(item: GalleryItem) {
  return item.order_no !== null ? `第 ${item.order_no} 页` : item.name;
}

export default function GalleryPage() {
  const queryClient = useQueryClient();
  const [mode, setMode] = useState<"illustration" | "comic">("illustration");
  const [projectId, setProjectId] = useState("");
  const [sort, setSort] = useState<"order" | "time">("order");
  const [view, setView] = useState<ViewSize>("medium");
  const [selected, setSelected] = useState<string[]>([]);
  const [menu, setMenu] = useState<MenuState>(null);
  const [lightbox, setLightbox] = useState<number | null>(null);
  const [notice, setNotice] = useState("");

  useEffect(() => {
    const saved = window.localStorage.getItem(VIEW_KEY);
    if (saved === "large" || saved === "medium" || saved === "small") setView(saved);
  }, []);

  useEffect(() => {
    window.localStorage.setItem(VIEW_KEY, view);
  }, [view]);

  const projectsQuery = useQuery({
    queryKey: ["projects"],
    queryFn: () => api<Project[]>("/api/projects"),
  });

  const projects = useMemo(() => projectsQuery.data || [], [projectsQuery.data]);
  const filtered = useMemo(() => projects.filter((project) => (project.mode || "comic") === mode), [projects, mode]);

  useEffect(() => {
    if (!filtered.length) {
      setProjectId("");
      return;
    }
    if (!filtered.some((project) => project.id === projectId)) {
      setProjectId(filtered[0].id);
    }
  }, [filtered, projectId]);

  const galleryQuery = useQuery({
    queryKey: ["gallery-files", projectId, sort],
    queryFn: () => api<GalleryItem[]>(`/api/projects/${projectId}/gallery?sort=${sort}`),
    enabled: !!projectId,
  });

  const items = useMemo(() => galleryQuery.data || [], [galleryQuery.data]);
  const project = projectsQuery.data?.find((item) => item.id === projectId);
  const lightboxItem = lightbox !== null ? items[lightbox] : null;

  useEffect(() => {
    setSelected([]);
    setMenu(null);
    setLightbox(null);
  }, [projectId, mode]);

  useEffect(() => {
    if (!galleryQuery.data) return;
    const paths = new Set(galleryQuery.data.map((item) => item.path));
    setSelected((current) => {
      const next = current.filter((path) => paths.has(path));
      return next.length === current.length ? current : next;
    });
  }, [galleryQuery.data]);

  useEffect(() => {
    function closeMenu() {
      setMenu(null);
    }
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setMenu(null);
        setLightbox(null);
      }
    }
    window.addEventListener("click", closeMenu);
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("click", closeMenu);
      window.removeEventListener("keydown", onKey);
    };
  }, []);

  useEffect(() => {
    if (lightbox === null) return;
    function onKey(event: KeyboardEvent) {
      if (event.key === "ArrowLeft") {
        event.preventDefault();
        setLightbox((current) => (current === null ? null : (current - 1 + items.length) % items.length));
      }
      if (event.key === "ArrowRight") {
        event.preventDefault();
        setLightbox((current) => (current === null ? null : (current + 1) % items.length));
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [lightbox, items.length]);

  function showNotice(text: string) {
    setNotice(text);
    window.setTimeout(() => setNotice(""), 3200);
  }

  const deleteImages = useMutation({
    mutationFn: (paths: string[]) =>
      api<{ count: number }>(`/api/projects/${projectId}/gallery/batch_delete`, {
        method: "POST",
        body: JSON.stringify({ paths }),
      }),
    onSuccess: (result) => {
      setSelected([]);
      setMenu(null);
      setLightbox(null);
      queryClient.invalidateQueries({ queryKey: ["gallery-files", projectId] });
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      showNotice(`已删除 ${result.count} 张图片，页面记录已保留`);
    },
    onError: () => showNotice("删除失败"),
  });

  function removeImages(paths: string[]) {
    if (!paths.length) return;
    const message =
      paths.length === 1
        ? "删除这张图片？图片会移到回收目录，页面记录保留。"
        : `删除选中的 ${paths.length} 张图片？图片会移到回收目录，页面记录保留。`;
    if (window.confirm(message)) deleteImages.mutate(paths);
  }

  function downloadImage(item: GalleryItem) {
    const anchor = document.createElement("a");
    anchor.href = `/api/projects/${projectId}/gallery/download?path=${encodeURIComponent(item.path)}`;
    anchor.download = item.name;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    setMenu(null);
  }

  function toggle(path: string) {
    setSelected((current) => (current.includes(path) ? current.filter((item) => item !== path) : [...current, path]));
  }

  function toggleAll() {
    setSelected(selected.length === items.length && items.length ? [] : items.map((item) => item.path));
  }

  function openMenu(event: MouseEvent<HTMLDivElement>, item: GalleryItem) {
    event.preventDefault();
    setMenu({
      x: Math.max(8, Math.min(event.clientX, window.innerWidth - 180)),
      y: Math.max(8, Math.min(event.clientY, window.innerHeight - 120)),
      item,
    });
  }

  function openLightbox(item: GalleryItem) {
    const index = items.findIndex((entry) => entry.path === item.path);
    if (index >= 0) setLightbox(index);
  }

  function moveLightbox(step: number) {
    setLightbox((current) => (current === null ? null : (current + step + items.length) % items.length));
  }

  return (
    <div className="flex h-screen flex-col">
      <header className="panel m-3 flex flex-wrap items-center justify-between gap-3 p-4">
        <div>
          <div className="text-lg font-semibold">画廊</div>
          <div className="text-xs opacity-50">页序＝按第 1、2、3 页；时间＝按图片文件修改时间（最新在前）</div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex border border-white/15">
            {([
              ["illustration", "插图"],
              ["comic", "漫画"],
            ] as const).map(([value, text]) => (
              <button
                key={value}
                className={`px-3 py-2 text-sm ${mode === value ? "bg-[#e4572e] text-white" : "hover:bg-white/5"}`}
                onClick={() => setMode(value)}
              >
                {text}
              </button>
            ))}
          </div>
          <select className="bg-black/20 px-3 py-2 text-sm outline-none" value={projectId} onChange={(event) => setProjectId(event.target.value)}>
            {filtered.map((item) => (
              <option key={item.id} value={item.id}>
                {item.title}
              </option>
            ))}
          </select>
          <div className="flex border border-white/15">
            <button
              className={`px-3 py-2 text-sm ${sort === "order" ? "bg-[#e4572e] text-white" : ""}`}
              title="按故事页序排列，第 1 页在最前"
              onClick={() => setSort("order")}
            >
              页序
            </button>
            <button
              className={`px-3 py-2 text-sm ${sort === "time" ? "bg-[#e4572e] text-white" : ""}`}
              title="按图片文件修改时间排列，最新在前"
              onClick={() => setSort("time")}
            >
              时间
            </button>
          </div>
          <div className="flex items-center border border-white/15">
            <span className="px-2 text-xs opacity-45">查看</span>
            {([
              ["large", "大图标"],
              ["medium", "中图标"],
              ["small", "小图标"],
            ] as const).map(([value, text]) => (
              <button
                key={value}
                className={`px-2 py-2 text-xs ${view === value ? "bg-[#e4572e] text-white" : "hover:bg-white/5"}`}
                onClick={() => setView(value)}
              >
                {text}
              </button>
            ))}
          </div>
        </div>
      </header>

      <div className="mx-3 mb-2 flex flex-wrap items-center gap-2">
        <button className="border border-white/20 px-3 py-1 text-sm disabled:opacity-40" disabled={!items.length} onClick={toggleAll}>
          {selected.length === items.length && items.length ? "取消全选" : "全选"}
        </button>
        <button
          className="border border-white/20 px-3 py-1 text-sm text-red-300 disabled:opacity-40"
          disabled={!selected.length}
          onClick={() => removeImages(selected)}
        >
          删除选中 {selected.length ? `(${selected.length})` : ""}
        </button>
        <span className="mono text-xs opacity-45">
          {items.length} 张 · 已选 {selected.length}
        </span>
        {notice && <span className="mono text-xs text-[#ffb4a0]">{notice}</span>}
      </div>

      <main className="panel mx-3 mb-3 min-h-0 flex-1 overflow-auto p-4">
        {project && (
          <div className="mb-3 flex flex-wrap items-baseline gap-3">
            <span className="text-base font-medium">{project.title}</span>
            <span className="mono text-xs opacity-50">
              {mode === "illustration" ? "插图模式" : "漫画模式"} · {items.length} 张 · projects/{projectId}/images
            </span>
          </div>
        )}
        <div className={`grid ${GRID[view]}`}>
          {items.map((item, index) => (
            <div
              key={item.path}
              role="button"
              tabIndex={0}
              className={`group relative cursor-zoom-in overflow-hidden border bg-black/20 ${
                selected.includes(item.path) ? "border-[#e4572e]" : "border-white/10 hover:border-white/30"
              }`}
              onClick={() => setLightbox(index)}
              onKeyDown={(event) => {
                if (event.key === "Enter") setLightbox(index);
              }}
              onContextMenu={(event) => openMenu(event, item)}
            >
              <img src={item.url} alt={label(item)} className="aspect-[9/16] w-full object-cover" loading="lazy" />
              <label
                className="absolute left-2 top-2 flex h-5 w-5 items-center justify-center bg-black/60"
                onClick={(event) => event.stopPropagation()}
              >
                <input
                  type="checkbox"
                  className="accent-[#e4572e]"
                  checked={selected.includes(item.path)}
                  onChange={() => toggle(item.path)}
                />
              </label>
              <div className={`flex items-center justify-between gap-2 bg-black/55 ${view === "small" ? "p-1 text-[10px]" : "p-2 text-xs"}`}>
                <span className="truncate">{label(item)}</span>
                <span className="mono shrink-0 opacity-50">{item.status || "变体"}</span>
              </div>
              {view !== "small" && <div className="truncate px-2 pb-2 text-xs opacity-45">{item.summary || item.name}</div>}
            </div>
          ))}
        </div>
        {!items.length && (
          <div className="mt-24 text-center text-sm opacity-40">
            {filtered.length ? "这个项目的 images 文件夹还没有图片" : `还没有${mode === "illustration" ? "插图" : "漫画"}项目`}
          </div>
        )}
      </main>

      {menu && (
        <div
          className="fixed z-[60] w-36 border border-white/20 bg-[#1a1c22] py-1 text-sm shadow-xl"
          style={{ left: menu.x, top: menu.y }}
          onClick={(event) => event.stopPropagation()}
        >
          <button
            className="block w-full px-4 py-1.5 text-left hover:bg-white/10"
            onClick={() => {
              openLightbox(menu.item);
              setMenu(null);
            }}
          >
            放大查看
          </button>
          <button className="block w-full px-4 py-1.5 text-left hover:bg-white/10" onClick={() => downloadImage(menu.item)}>
            下载
          </button>
          <button
            className="block w-full px-4 py-1.5 text-left text-red-300 hover:bg-white/10"
            onClick={() => {
              const path = menu.item.path;
              setMenu(null);
              removeImages([path]);
            }}
          >
            删除图片
          </button>
        </div>
      )}

      {lightboxItem && (
        <div className="fixed inset-0 z-50 flex flex-col bg-black/95 p-4" onClick={() => setLightbox(null)}>
          <div className="flex flex-wrap items-center justify-between gap-3 py-2" onClick={(event) => event.stopPropagation()}>
            <div className="min-w-0">
              <div className="truncate text-sm font-medium">{label(lightboxItem)}</div>
              <div className="mono truncate text-xs opacity-50">{lightboxItem.summary || lightboxItem.name}</div>
            </div>
            <div className="flex gap-2">
              <button className="border border-white/20 px-3 py-1 text-sm" onClick={() => downloadImage(lightboxItem)}>
                下载
              </button>
              <button className="border border-white/20 px-3 py-1 text-sm text-red-300" onClick={() => removeImages([lightboxItem.path])}>
                删除
              </button>
              <button className="border border-white/20 px-3 py-1 text-sm" onClick={() => setLightbox(null)}>
                关闭
              </button>
            </div>
          </div>
          <div className="relative flex min-h-0 flex-1 items-center justify-center" onClick={() => setLightbox(null)}>
            <button
              aria-label="上一张"
              className="absolute left-2 z-10 flex h-12 w-12 items-center justify-center border border-white/20 bg-black/50 text-3xl hover:bg-white/10"
              onClick={(event) => {
                event.stopPropagation();
                moveLightbox(-1);
              }}
            >
              ‹
            </button>
            <img
              src={lightboxItem.url}
              alt={label(lightboxItem)}
              className="max-h-full max-w-full object-contain"
              onClick={(event) => event.stopPropagation()}
            />
            <button
              aria-label="下一张"
              className="absolute right-2 z-10 flex h-12 w-12 items-center justify-center border border-white/20 bg-black/50 text-3xl hover:bg-white/10"
              onClick={(event) => {
                event.stopPropagation();
                moveLightbox(1);
              }}
            >
              ›
            </button>
          </div>
          <div className="mono py-2 text-center text-xs opacity-60">
            {lightbox !== null ? lightbox + 1 : 0} / {items.length}
          </div>
        </div>
      )}
    </div>
  );
}

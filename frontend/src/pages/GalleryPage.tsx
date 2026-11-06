import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { api, type Page, type Project } from "../api";

export default function GalleryPage() {
  const [mode, setMode] = useState<"illustration" | "comic">("illustration");
  const [projectId, setProjectId] = useState("");
  const [sort, setSort] = useState<"order" | "time">("order");

  const projectsQuery = useQuery({
    queryKey: ["projects"],
    queryFn: () => api<Project[]>("/api/projects"),
  });

  const filtered = (projectsQuery.data || []).filter((project) => (project.mode || "comic") === mode);

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
    queryKey: ["gallery", projectId, mode, sort],
    queryFn: () => api<Page[]>(`/api/projects/${projectId}/gallery?kind=${mode}&sort=${sort}`),
    enabled: !!projectId,
  });

  const project = projectsQuery.data?.find((item) => item.id === projectId);

  return (
    <div className="flex h-screen flex-col">
      <header className="panel m-3 flex flex-wrap items-center justify-between gap-3 p-4">
        <div>
          <div className="text-lg font-semibold">画廊</div>
          <div className="text-xs opacity-50">按模式和项目查看生成结果</div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex border border-white/15">
            {([
              ["illustration", "插图"],
              ["comic", "漫画"],
            ] as const).map(([value, label]) => (
              <button
                key={value}
                className={`px-3 py-2 text-sm ${mode === value ? "bg-[#e4572e] text-white" : "hover:bg-white/5"}`}
                onClick={() => setMode(value)}
              >
                {label}
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
            <button className={`px-3 py-2 text-sm ${sort === "order" ? "bg-[#e4572e] text-white" : ""}`} onClick={() => setSort("order")}>
              内容
            </button>
            <button className={`px-3 py-2 text-sm ${sort === "time" ? "bg-[#e4572e] text-white" : ""}`} onClick={() => setSort("time")}>
              时间
            </button>
          </div>
        </div>
      </header>

      <main className="panel mx-3 mb-3 min-h-0 flex-1 overflow-auto p-4">
        {project && (
          <div className="mb-3 flex items-baseline gap-3">
            <span className="text-base font-medium">{project.title}</span>
            <span className="mono text-xs opacity-50">{mode === "illustration" ? "插图模式" : "漫画模式"} · {galleryQuery.data?.length || 0} 张</span>
          </div>
        )}
        <div className="columns-2 gap-4 md:columns-3 xl:columns-4">
          {galleryQuery.data?.filter((page) => page.image_url).map((page) => (
            <a key={page.id} href={page.image_url || "#"} target="_blank" rel="noreferrer" className="panel mb-4 block break-inside-avoid p-2">
              <img src={page.image_url || ""} alt={`第 ${page.order_no} 页`} className="mb-2 w-full object-cover" loading="lazy" />
              <div className="flex items-center justify-between gap-2">
                <span className="text-sm">第 {page.order_no} 页</span>
                <span className="mono text-xs opacity-50">{page.status}</span>
              </div>
              <div className="mono mt-1 line-clamp-2 text-xs opacity-45">{page.summary}</div>
            </a>
          ))}
        </div>
        {!galleryQuery.data?.length && (
          <div className="mt-24 text-center text-sm opacity-40">
            {filtered.length ? "这个项目还没有生成图片" : `还没有${mode === "illustration" ? "插图" : "漫画"}项目`}
          </div>
        )}
      </main>
    </div>
  );
}

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import { api, type Project, type StoryDoc } from "../api";

export default function StoryPage() {
  const queryClient = useQueryClient();
  const [projectId, setProjectId] = useState("");
  const [title, setTitle] = useState("");
  const [markdown, setMarkdown] = useState("");

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

  const storyQuery = useQuery({
    queryKey: ["story", projectId],
    queryFn: () => api<StoryDoc>(`/api/projects/${projectId}/story`),
    enabled: !!projectId,
  });

  useEffect(() => {
    if (!storyQuery.data) return;
    setTitle(storyQuery.data.title || "");
    setMarkdown(storyQuery.data.markdown || "");
  }, [storyQuery.data?.project_id, storyQuery.data?.updated_at]);

  const saveStory = useMutation({
    mutationFn: () =>
      api<StoryDoc>(`/api/projects/${projectId}/story`, {
        method: "PUT",
        body: JSON.stringify({ title, markdown }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["story", projectId] });
    },
  });

  async function importMarkdown(file: File) {
    const text = await file.text();
    setMarkdown(text);
    if (!title) setTitle(file.name.replace(/\.md$/i, ""));
  }

  return (
    <div className="flex h-screen flex-col">
      <header className="panel m-3 flex flex-wrap items-center gap-3 p-4">
        <div className="min-w-[180px]">
          <div className="text-lg font-semibold">故事整理</div>
          <div className="text-xs opacity-50">一个项目绑定一本小说</div>
        </div>
        <select className="bg-black/20 px-3 py-2 text-sm outline-none" value={projectId} onChange={(e) => setProjectId(e.target.value)}>
          {projectsQuery.data?.map((project) => (
            <option key={project.id} value={project.id}>
              {project.title}
            </option>
          ))}
        </select>
        <label className="cursor-pointer border border-white/20 px-3 py-2 text-sm">
          导入 Markdown
          <input
            type="file"
            accept=".md,text/markdown"
            className="hidden"
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) importMarkdown(file);
              event.currentTarget.value = "";
            }}
          />
        </label>
        <button className="border border-[#e4572e] px-4 py-2 text-sm text-[#e4572e]" onClick={() => saveStory.mutate()} disabled={!projectId}>
          保存故事
        </button>
      </header>

      <div className="grid min-h-0 flex-1 grid-cols-[220px_minmax(0,1fr)_minmax(0,1fr)] gap-3 px-3 pb-3">
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
          <input className="mb-2 bg-black/25 px-2 py-1 text-sm outline-none" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="作品标题" />
          <textarea
            className="serif min-h-0 flex-1 resize-none bg-black/25 p-3 text-sm leading-7 outline-none"
            value={markdown}
            onChange={(e) => setMarkdown(e.target.value)}
            placeholder="# 第一章&#10;&#10;把小说 Markdown 粘贴到这里，或点上方导入。"
          />
        </section>

        <section className="panel min-h-0 overflow-auto p-5">
          <div className="prose-manga">
            <ReactMarkdown>{markdown}</ReactMarkdown>
          </div>
        </section>
      </div>
    </div>
  );
}

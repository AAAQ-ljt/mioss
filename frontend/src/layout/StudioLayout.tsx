import { NavLink, Outlet } from "react-router-dom";

const items = [
  { to: "/", label: "提示词检索", hint: "法典分类与复制" },
  { to: "/relay", label: "TAG 中转站", hint: "组合与整理" },
  { to: "/presets", label: "预设库", hint: "固定风格与角色" },
  { to: "/story", label: "故事整理", hint: "小说 Markdown" },
  { to: "/board", label: "分镜台", hint: "页、角色、出图" },
];

export default function StudioLayout() {
  return (
    <div className="flex min-h-screen">
      <aside className="halftone w-64 shrink-0 border-r border-white/10 bg-[#121419]">
        <div className="border-b border-white/10 px-5 py-5">
          <div className="serif text-xl font-semibold">MOSS 漫画工坊</div>
          <div className="mt-1 text-xs opacity-50">法典 → 中转 → 预设 → 故事 → 分镜</div>
        </div>
        <nav className="p-3">
          {items.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/"}
              className={({ isActive }) =>
                `mb-1 block border px-3 py-3 transition ${
                  isActive
                    ? "border-[#e4572e] bg-[#e4572e]/10 text-[#ffb4a0]"
                    : "border-transparent hover:border-white/15 hover:bg-white/5"
                }`
              }
            >
              <div className="text-sm font-medium">{item.label}</div>
              <div className="mt-0.5 text-xs opacity-50">{item.hint}</div>
            </NavLink>
          ))}
        </nav>
      </aside>
      <div className="min-w-0 flex-1">
        <Outlet />
      </div>
    </div>
  );
}

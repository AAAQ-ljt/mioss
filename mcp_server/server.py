from __future__ import annotations

import os
from typing import Any

import httpx
from mcp.server.mcpserver import MCPServer

API_BASE = os.getenv("MOSS_API_BASE", "http://127.0.0.1:8780")
server = MCPServer(
    name="moss-manga-studio",
    instructions="调用本地 MOSS 漫画分镜台：检索法典 tag、保存页级分镜、编译提示词、生成页面图。",
)


def _request(method: str, path: str, **kwargs: Any) -> Any:
    with httpx.Client(timeout=httpx.Timeout(30.0, read=120.0), trust_env=False) as client:
        response = client.request(method, f"{API_BASE}{path}", **kwargs)
        if response.status_code >= 400:
            raise RuntimeError(f"{method} {path} failed: {response.status_code} {response.text[:1000]}")
        return response.json()


@server.tool(description="搜索本地法典普通 tag。默认只返回 MOSS 可用且非 R18 条目。")
def codex_search(
    query: str,
    codex_id: str | None = None,
    category_path: str | None = None,
    include_artist_only: bool = False,
    include_nsfw: bool = False,
    limit: int = 20,
) -> Any:
    params = {"q": query, "include_artist_only": include_artist_only, "include_nsfw": include_nsfw, "limit": limit}
    if codex_id:
        params["codex_id"] = codex_id
    if category_path:
        params["category_path"] = category_path
    return _request("GET", "/api/codex/search", params=params)


@server.tool(description="根据中英文片段提示常用 tag。")
def codex_suggest(query: str, limit: int = 20) -> Any:
    return _request("GET", "/api/codex/suggest", params={"q": query, "limit": limit})


@server.tool(description="按 entry_id 获取法典条目。")
def codex_get(entry_id: str) -> Any:
    return _request("GET", f"/api/codex/entries/{entry_id}")


@server.tool(description="创建漫画项目。默认风格为 manga-ink，适合黑白网点漫画页。")
def project_create(title: str, story: str = "", style_preset_id: str = "manga-ink") -> Any:
    return _request("POST", "/api/projects", json={"title": title, "story": story, "style_preset_id": style_preset_id})


@server.tool(description="列出项目。")
def project_list() -> Any:
    return _request("GET", "/api/projects")


@server.tool(description="获取项目详情和页列表。")
def project_get(project_id: str) -> Any:
    return _request("GET", f"/api/projects/{project_id}")


@server.tool(description="更新项目标题、故事、风格预设或画廊排序。")
def project_update(project_id: str, patch: dict[str, Any]) -> Any:
    return _request("PATCH", f"/api/projects/{project_id}", json=patch)


@server.tool(description="列出可用风格预设。")
def style_presets_list() -> Any:
    return _request("GET", "/api/style-presets")


@server.tool(description="删除项目及其页、角色和任务记录。")
def project_delete(project_id: str) -> Any:
    return _request("DELETE", f"/api/projects/{project_id}")


@server.tool(description="导出项目 JSON（角色、页、refs、连续性、角色选择）。")
def project_export(project_id: str) -> Any:
    return _request("GET", f"/api/projects/{project_id}/export")


@server.tool(description="导入项目 JSON，创建为新项目。")
def project_import(payload: dict[str, Any]) -> Any:
    return _request("POST", "/api/projects/import", json=payload)


@server.tool(description="列出 TAG 中转站内容。")
def relay_list(limit: int = 200) -> Any:
    return _request("GET", "/api/relay", params={"limit": limit})


@server.tool(description="加入 TAG 中转站。")
def relay_add(content: str, format: str = "plain", source_entry_id: str | None = None, source_title: str | None = None) -> Any:
    return _request("POST", "/api/relay", json={"content": content, "format": format, "source_entry_id": source_entry_id, "source_title": source_title})


@server.tool(description="删除中转站条目。")
def relay_delete(item_id: str) -> Any:
    return _request("DELETE", f"/api/relay/{item_id}")


@server.tool(description="清空中转站。")
def relay_clear() -> Any:
    return _request("DELETE", "/api/relay")


@server.tool(description="列出提示词预设。")
def preset_list() -> Any:
    return _request("GET", "/api/presets")


@server.tool(description="新增或更新提示词预设。")
def preset_upsert(preset: dict[str, Any]) -> Any:
    return _request("POST", "/api/presets", json=preset)


@server.tool(description="删除提示词预设。")
def preset_delete(preset_id: str) -> Any:
    return _request("DELETE", f"/api/presets/{preset_id}")


@server.tool(description="读取项目绑定的 Markdown 小说。")
def story_get(project_id: str) -> Any:
    return _request("GET", f"/api/projects/{project_id}/story")


@server.tool(description="保存项目绑定的 Markdown 小说。")
def story_save(project_id: str, title: str, markdown: str) -> Any:
    return _request("PUT", f"/api/projects/{project_id}/story", json={"title": title, "markdown": markdown})


@server.tool(description="保存项目故事文本。")
def story_set(project_id: str, story: str) -> Any:
    return _request("POST", f"/api/projects/{project_id}/story", json={"story": story})


@server.tool(description="保存页级分镜。pages 是列表，每项可含 order_no、summary、layout_note、refs、seed。")
def storyboard_save(project_id: str, pages: list[dict[str, Any]]) -> Any:
    return _request("POST", f"/api/projects/{project_id}/storyboard", json={"pages": pages})


@server.tool(description="列出项目的页。")
def page_list(project_id: str) -> Any:
    return _request("GET", f"/api/projects/{project_id}").get("pages", [])


@server.tool(description="更新页字段。")
def page_update(page_id: str, patch: dict[str, Any]) -> Any:
    return _request("PATCH", f"/api/pages/{page_id}", json=patch)


@server.tool(description="复制一页到末尾，状态重置为 draft。")
def page_duplicate(page_id: str) -> Any:
    return _request("POST", f"/api/pages/{page_id}/duplicate")


@server.tool(description="删除一页及其任务记录。")
def page_delete(page_id: str) -> Any:
    return _request("DELETE", f"/api/pages/{page_id}")


@server.tool(description="按给定 page_id 顺序重排项目页。")
def project_reorder(project_id: str, page_ids: list[str]) -> Any:
    return _request("POST", f"/api/projects/{project_id}/reorder", json={"page_ids": page_ids})


@server.tool(description="获取项目画廊。sort=order 或 time。")
def gallery_list(project_id: str, sort: str = "order") -> Any:
    return _request("GET", f"/api/projects/{project_id}/gallery", params={"sort": sort})


@server.tool(description="列出项目角色圣经。")
def character_list(project_id: str) -> Any:
    return _request("GET", f"/api/projects/{project_id}/characters")


@server.tool(description="新增或更新角色锚点。body 可含 id、name、anchor_tags、ref_image、notes。")
def character_upsert(project_id: str, body: dict[str, Any]) -> Any:
    return _request("POST", f"/api/projects/{project_id}/characters", json=body)


@server.tool(description="编译页提示词：风格块 + 角色锚点 + 页面文本 + 法典 refs。默认跳过 R18 条目。")
def prompt_compose(
    page_id: str,
    entry_ids: list[str] | None = None,
    character_ids: list[str] | None = None,
    style_preset_id: str | None = None,
    page_text: str = "",
    character_text: str = "",
    negative_text: str = "",
    include_nsfw: bool = False,
    save: bool = True,
) -> Any:
    return _request(
        "POST",
        f"/api/pages/{page_id}/compose",
        json={
            "entry_ids": entry_ids,
            "character_ids": character_ids,
            "style_preset_id": style_preset_id,
            "page_text": page_text,
            "character_text": character_text,
            "negative_text": negative_text,
            "include_nsfw": include_nsfw,
            "save": save,
        },
    )


@server.tool(description="列出某页成功生成的变体图片。")
def page_variants(page_id: str) -> Any:
    return _request("GET", f"/api/pages/{page_id}/variants")


@server.tool(description="生成一页图，返回 job_id。可传 init_image_path 做图生图重绘。")
def generate_page(page_id: str, seed: int | None = None, profile: dict[str, Any] | None = None, init_image_path: str | None = None) -> Any:
    return _request("POST", f"/api/pages/{page_id}/generate", json={"seed": seed, "profile": profile, "init_image_path": init_image_path})


@server.tool(description="按页序串行生成项目全部页面；已有提示词的页面才会生成。")
def generate_project(project_id: str, seed: int | None = None, profile: dict[str, Any] | None = None) -> Any:
    return _request("POST", f"/api/projects/{project_id}/generate_all", json={"seed": seed, "profile": profile})


@server.tool(description="列出最近生成任务。")
def job_list(limit: int = 50) -> Any:
    return _request("GET", "/api/jobs", params={"limit": limit})


@server.tool(description="查询生成任务状态。")
def job_status(job_id: str) -> Any:
    return _request("GET", f"/api/jobs/{job_id}")


@server.tool(description="取消排队中的任务；运行中的任务会中断当前 ComfyUI 作业。")
def job_cancel(job_id: str) -> Any:
    return _request("POST", f"/api/jobs/{job_id}/cancel")


@server.tool(description="返回外部 AI 应遵守的项目 schema 和调用顺序。")
def schema_get() -> dict[str, Any]:
    return {
        "workflow": [
            "project_create(title, story)",
            "character_upsert(project_id, body)",
            "storyboard_save(project_id, pages)",
            "prompt_compose(page_id, entry_ids, character_ids)",
            "generate_page(page_id, seed)",
            "job_status(job_id)",
            "gallery_list(project_id)",
        ],
        "page_schema": {
            "order_no": "int",
            "summary": "页面剧情摘要，中文",
            "layout_note": "版式/镜头/格位说明，中文",
            "refs": "法典 entry_id 列表，必须来自 codex_search",
            "character_ids": "角色 id 列表，必须来自 character_upsert",
            "seed": "可选 int",
        },
        "rules": [
            "只能引用 codex_search/codex_get 返回的真实 entry_id。",
            "不要引用 artist_* 法典作为 MOSS 正向 tag。",
            "提示词由项目端清洗和拼接，AI 不直接拼 NAI 权重语法。",
        ],
    }


def main() -> None:
    server.run("stdio")


if __name__ == "__main__":
    main()

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
import sqlite3

from .config import ensure_dirs, FRONTEND_DIST, PROJECTS_DIR
from .db import connect, migrate
from .services import codex, comfy, favorites, gallery, jobs, projects, prompt, studio, tasks, thumbs


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_dirs()
    conn = connect()
    migrate(conn)
    conn.close()
    jobs.recover_stale_jobs()
    yield


app = FastAPI(title="MOSS Manga Studio", lifespan=lifespan)
PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/projects", StaticFiles(directory=PROJECTS_DIR), name="projects")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_conn():
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


@app.get("/api/health")
def health(conn: sqlite3.Connection = Depends(get_conn)):
    release = conn.execute("SELECT value FROM setting WHERE key = 'release'").fetchone()
    synced_at = conn.execute("SELECT value FROM setting WHERE key = 'synced_at'").fetchone()
    counts = conn.execute("SELECT COUNT(*) AS total, COALESCE(SUM(moss_usable), 0) AS usable FROM entry").fetchone()
    client = comfy.ComfyClient()
    comfy_health = client.health()
    client.close()
    return {
        "ok": True,
        "release": release["value"] if release else None,
        "synced_at": synced_at["value"] if synced_at else None,
        "entries": dict(counts),
        "comfy": comfy_health,
    }


@app.get("/api/codexes")
def list_codexes(include_nsfw: bool = False, conn: sqlite3.Connection = Depends(get_conn)):
    return codex.list_codexes(conn, include_nsfw=include_nsfw)


@app.get("/api/codex/categories")
def categories(codex_id: str = Query(alias="codex_id"), conn: sqlite3.Connection = Depends(get_conn)):
    return codex.categories(conn, codex_id)


@app.get("/api/codex/suggest")
def suggest_tags(q: str, limit: int = 20, conn: sqlite3.Connection = Depends(get_conn)):
    return codex.suggest_tags(conn, q, limit=limit)


@app.get("/api/library/categories")
def library_categories(domain: str = "regular", conn: sqlite3.Connection = Depends(get_conn)):
    return codex.library_categories(conn, domain)


@app.get("/api/codex/search")
def search(
    q: str,
    codex_id: str | None = None,
    category_path: str | None = None,
    domain: str | None = None,
    category_id: str | None = None,
    include_artist_only: bool = False,
    include_nsfw: bool = False,
    limit: int = 20,
    conn: sqlite3.Connection = Depends(get_conn),
):
    return codex.search_entries(
        conn,
        q,
        codex_id=codex_id,
        category_path=category_path,
        domain=domain,
        category_id=category_id,
        include_artist_only=include_artist_only,
        include_nsfw=include_nsfw,
        limit=limit,
    )


@app.get("/api/codex/entries/{entry_id}")
def get_entry(entry_id: str, conn: sqlite3.Connection = Depends(get_conn)):
    entry = codex.get_entry(conn, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="entry not found")
    return entry


@app.get("/api/style-presets")
def list_style_presets(conn: sqlite3.Connection = Depends(get_conn)):
    return projects.list_style_presets(conn)


@app.get("/api/codex/entries/{entry_id}/thumbnail")
def entry_thumbnail(entry_id: str, conn: sqlite3.Connection = Depends(get_conn)):
    entry, path = thumbs.ensure_thumbnail(conn, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="entry not found")
    if path:
        return FileResponse(path)
    if entry.get("image_url"):
        return RedirectResponse(entry["image_url"])
    raise HTTPException(status_code=404, detail="entry image not found")


@app.get("/api/projects")
def list_projects(conn: sqlite3.Connection = Depends(get_conn)):
    return projects.list_projects(conn)


@app.post("/api/projects")
def create_project(body: dict[str, Any], conn: sqlite3.Connection = Depends(get_conn)):
    return projects.create_project(
        conn,
        title=body.get("title", "未命名漫画"),
        story=body.get("story", ""),
        style_preset_id=body.get("style_preset_id", "manga-ink"),
        mode=body.get("mode", "comic"),
    )


@app.get("/api/projects/{project_id}")
def get_project(project_id: str, conn: sqlite3.Connection = Depends(get_conn)):
    project = projects.get_project(conn, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="project not found")
    return project


@app.patch("/api/projects/{project_id}")
def update_project(project_id: str, body: dict[str, Any], conn: sqlite3.Connection = Depends(get_conn)):
    project = projects.update_project(conn, project_id, body)
    if not project:
        raise HTTPException(status_code=404, detail="project not found")
    return project


@app.post("/api/projects/batch_delete")
def batch_delete_projects(body: dict[str, Any], conn: sqlite3.Connection = Depends(get_conn)):
    project_ids = body.get("project_ids")
    if not isinstance(project_ids, list):
        raise HTTPException(status_code=400, detail="project_ids must be a list")
    return {"deleted": projects.batch_delete_projects(conn, project_ids)}


@app.delete("/api/projects/{project_id}")
def delete_project(project_id: str, conn: sqlite3.Connection = Depends(get_conn)):
    if not projects.delete_project(conn, project_id):
        raise HTTPException(status_code=404, detail="project not found")
    return {"deleted": project_id}


@app.get("/api/projects/{project_id}/export")
def export_project(project_id: str, conn: sqlite3.Connection = Depends(get_conn)):
    payload = projects.export_project(conn, project_id)
    if not payload:
        raise HTTPException(status_code=404, detail="project not found")
    return payload


@app.post("/api/projects/import")
def import_project(body: dict[str, Any], conn: sqlite3.Connection = Depends(get_conn)):
    project = projects.import_project(conn, body)
    if not project:
        raise HTTPException(status_code=400, detail="invalid project payload")
    return project


@app.post("/api/projects/{project_id}/story")
def set_story(project_id: str, body: dict[str, Any], conn: sqlite3.Connection = Depends(get_conn)):
    project = projects.set_story(conn, project_id, body.get("story", ""))
    if not project:
        raise HTTPException(status_code=404, detail="project not found")
    return project


@app.post("/api/projects/{project_id}/storyboard")
def save_storyboard(project_id: str, body: dict[str, Any], conn: sqlite3.Connection = Depends(get_conn)):
    pages = body.get("pages")
    if not isinstance(pages, list):
        raise HTTPException(status_code=400, detail="pages must be a list")
    for page in pages:
        for ref in page.get("refs") or page.get("entry_ids") or []:
            if not codex.get_entry(conn, ref):
                raise HTTPException(status_code=400, detail=f"unknown entry ref: {ref}")
    return {"pages": projects.replace_pages(conn, project_id, pages)}


@app.get("/api/projects/{project_id}/characters")
def list_characters(project_id: str, conn: sqlite3.Connection = Depends(get_conn)):
    return projects.list_characters(conn, project_id)


@app.post("/api/projects/{project_id}/characters")
def upsert_character(project_id: str, body: dict[str, Any], conn: sqlite3.Connection = Depends(get_conn)):
    character = projects.upsert_character(conn, project_id, body)
    if not character:
        raise HTTPException(status_code=500, detail="character save failed")
    return character


@app.post("/api/projects/{project_id}/pages")
def add_page(project_id: str, body: dict[str, Any], conn: sqlite3.Connection = Depends(get_conn)):
    for ref in body.get("refs") or body.get("entry_ids") or []:
        if not codex.get_entry(conn, ref):
            raise HTTPException(status_code=400, detail=f"unknown entry ref: {ref}")
    page = projects.add_page(conn, project_id, body)
    if not page:
        raise HTTPException(status_code=404, detail="project not found")
    return page


@app.post("/api/pages/{page_id}/compose")
def compose_page(page_id: str, body: dict[str, Any], conn: sqlite3.Connection = Depends(get_conn)):
    compiled = prompt.compose_for_page(
        conn,
        page_id,
        entry_ids=body.get("entry_ids"),
        character_ids=body.get("character_ids"),
        style_preset_id=body.get("style_preset_id"),
        page_text=body.get("page_text"),
        character_text=body.get("character_text", ""),
        negative_text=body.get("negative_text", ""),
        include_nsfw=body.get("include_nsfw", False),
        save=body.get("save", True),
    )
    if compiled is None:
        raise HTTPException(status_code=404, detail="page not found")
    return compiled


@app.post("/api/pages/{page_id}/duplicate")
def duplicate_page(page_id: str, conn: sqlite3.Connection = Depends(get_conn)):
    page = projects.duplicate_page(conn, page_id)
    if not page:
        raise HTTPException(status_code=404, detail="page not found")
    return page


@app.patch("/api/pages/{page_id}")
def update_page(page_id: str, body: dict[str, Any], conn: sqlite3.Connection = Depends(get_conn)):
    page = projects.update_page(conn, page_id, body)
    if not page:
        raise HTTPException(status_code=404, detail="page not found")
    return page


@app.post("/api/projects/{project_id}/reorder")
def reorder_pages(project_id: str, body: dict[str, Any], conn: sqlite3.Connection = Depends(get_conn)):
    page_ids = body.get("page_ids")
    if not isinstance(page_ids, list):
        raise HTTPException(status_code=400, detail="page_ids must be a list")
    try:
        return {"pages": projects.reorder_pages(conn, project_id, page_ids)}
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.delete("/api/pages/{page_id}")
def delete_page(page_id: str, conn: sqlite3.Connection = Depends(get_conn)):
    if not projects.delete_page(conn, page_id):
        raise HTTPException(status_code=404, detail="page not found")
    return {"deleted": page_id}


@app.get("/api/projects/{project_id}/gallery")
def list_gallery(project_id: str, sort: str = "order", conn: sqlite3.Connection = Depends(get_conn)):
    items = gallery.list_gallery(conn, project_id, sort=sort)
    if items is None:
        raise HTTPException(status_code=404, detail="project not found")
    return items


@app.post("/api/projects/{project_id}/gallery/batch_delete")
def delete_gallery_images(project_id: str, body: dict[str, Any], conn: sqlite3.Connection = Depends(get_conn)):
    paths = body.get("paths")
    if not isinstance(paths, list):
        raise HTTPException(status_code=400, detail="paths must be a list")
    deleted = gallery.delete_images(conn, project_id, paths)
    return {"deleted": deleted, "count": len(deleted)}


@app.get("/api/projects/{project_id}/gallery/download")
def download_gallery_image(
    project_id: str,
    path: str = Query(...),
    conn: sqlite3.Connection = Depends(get_conn),
):
    info = gallery.download_info(conn, project_id, path)
    if info is None:
        raise HTTPException(status_code=404, detail="image not found")
    target, filename = info
    return FileResponse(target, filename=filename)


@app.post("/api/pages/{page_id}/generate")
def generate_page(page_id: str, body: dict[str, Any] | None = None):
    body = body or {}
    job_id = jobs.submit_page(page_id, seed=body.get("seed"), profile=body.get("profile"), init_image_path=body.get("init_image_path"))
    return {"job_id": job_id}


@app.post("/api/projects/{project_id}/generate_all")
def generate_project(project_id: str, body: dict[str, Any] | None = None, conn: sqlite3.Connection = Depends(get_conn)):
    if not projects.get_project(conn, project_id):
        raise HTTPException(status_code=404, detail="project not found")
    body = body or {}
    return jobs.generate_project(project_id, seed=body.get("seed"), profile=body.get("profile"))


@app.get("/api/pages/{page_id}/variants")
def page_variants(page_id: str, conn: sqlite3.Connection = Depends(get_conn)):
    if not projects.get_page(conn, page_id):
        raise HTTPException(status_code=404, detail="page not found")
    return jobs.list_page_variants(conn, page_id)


@app.get("/api/jobs")
def list_jobs(limit: int = 50, conn: sqlite3.Connection = Depends(get_conn)):
    return jobs.list_jobs(conn, limit=limit)


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str, conn: sqlite3.Connection = Depends(get_conn)):
    job = jobs.get_job(conn, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    return job


@app.post("/api/jobs/{job_id}/cancel")
def cancel_job(job_id: str):
    job = jobs.cancel_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    return job


@app.get("/api/favorites")
def list_favorites(domain: str | None = None, conn: sqlite3.Connection = Depends(get_conn)):
    return favorites.list_favorites(conn, domain)


@app.get("/api/favorites/ids")
def favorite_ids(conn: sqlite3.Connection = Depends(get_conn)):
    return favorites.favorite_ids(conn)


@app.post("/api/favorites/toggle")
def toggle_favorite(body: dict[str, Any], conn: sqlite3.Connection = Depends(get_conn)):
    entry_id = body.get("entry_id", "")
    if not entry_id:
        raise HTTPException(status_code=400, detail="entry_id is required")
    try:
        return favorites.toggle_favorite(conn, entry_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.delete("/api/favorites/{entry_id}")
def delete_favorite(entry_id: str, conn: sqlite3.Connection = Depends(get_conn)):
    if not favorites.delete_favorite(conn, entry_id):
        raise HTTPException(status_code=404, detail="favorite not found")
    return {"deleted": entry_id}


@app.delete("/api/favorites")
def clear_favorites(conn: sqlite3.Connection = Depends(get_conn)):
    return {"deleted": favorites.clear_favorites(conn)}


@app.post("/api/favorites/compose")
def compose_favorites(body: dict[str, Any], conn: sqlite3.Connection = Depends(get_conn)):
    entry_ids = body.get("entry_ids")
    if not isinstance(entry_ids, list):
        raise HTTPException(status_code=400, detail="entry_ids must be a list")
    try:
        return favorites.compose_favorites(conn, entry_ids, body.get("format", "moss"))
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.get("/api/relay")
def list_relay(limit: int = 200, conn: sqlite3.Connection = Depends(get_conn)):
    return studio.list_relay_items(conn, limit=limit)


@app.post("/api/relay")
def add_relay(body: dict[str, Any], conn: sqlite3.Connection = Depends(get_conn)):
    content = body.get("content", "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="content is empty")
    return studio.add_relay_item(
        conn,
        content=content,
        format_name=body.get("format", "plain"),
        source_entry_id=body.get("source_entry_id"),
        source_title=body.get("source_title"),
    )


@app.delete("/api/relay/{item_id}")
def delete_relay(item_id: str, conn: sqlite3.Connection = Depends(get_conn)):
    if not studio.delete_relay_item(conn, item_id):
        raise HTTPException(status_code=404, detail="relay item not found")
    return {"deleted": item_id}


@app.delete("/api/relay")
def clear_relay(conn: sqlite3.Connection = Depends(get_conn)):
    return {"deleted": studio.clear_relay_items(conn)}


@app.get("/api/presets")
def list_presets(conn: sqlite3.Connection = Depends(get_conn)):
    return studio.list_presets(conn)


@app.post("/api/presets")
def upsert_preset(body: dict[str, Any], conn: sqlite3.Connection = Depends(get_conn)):
    return studio.upsert_preset(conn, body)


@app.delete("/api/presets/{preset_id}")
def delete_preset(preset_id: str, conn: sqlite3.Connection = Depends(get_conn)):
    if not studio.delete_preset(conn, preset_id):
        raise HTTPException(status_code=404, detail="preset not found")
    return {"deleted": preset_id}


@app.get("/api/projects/{project_id}/presets")
def list_project_presets(project_id: str, conn: sqlite3.Connection = Depends(get_conn)):
    return studio.list_project_presets(conn, project_id)


@app.post("/api/projects/{project_id}/presets/{preset_id}")
def bind_preset(project_id: str, preset_id: str, conn: sqlite3.Connection = Depends(get_conn)):
    return studio.bind_preset(conn, project_id, preset_id)


@app.delete("/api/projects/{project_id}/presets/{preset_id}")
def unbind_preset(project_id: str, preset_id: str, conn: sqlite3.Connection = Depends(get_conn)):
    if not studio.unbind_preset(conn, project_id, preset_id):
        raise HTTPException(status_code=404, detail="binding not found")
    return {"deleted": preset_id}


@app.get("/api/projects/{project_id}/chapters")
def list_chapters(project_id: str, conn: sqlite3.Connection = Depends(get_conn)):
    return studio.list_chapters(conn, project_id)


@app.post("/api/projects/{project_id}/chapters")
def create_chapter(project_id: str, body: dict[str, Any], conn: sqlite3.Connection = Depends(get_conn)):
    return studio.create_chapter(conn, project_id, body.get("title", "新章节"), body.get("content"))


@app.post("/api/projects/{project_id}/chapters/reorder")
def reorder_chapters(project_id: str, body: dict[str, Any], conn: sqlite3.Connection = Depends(get_conn)):
    chapter_ids = body.get("chapter_ids")
    if not isinstance(chapter_ids, list):
        raise HTTPException(status_code=400, detail="chapter_ids must be a list")
    try:
        return studio.reorder_chapters(conn, project_id, chapter_ids)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.post("/api/projects/{project_id}/chapters/import")
def import_chapters(project_id: str, body: dict[str, Any], conn: sqlite3.Connection = Depends(get_conn)):
    return {"chapters": studio.import_markdown_chapters(conn, project_id, body.get("markdown", ""))}


@app.get("/api/chapters/{chapter_id}")
def get_chapter(chapter_id: str, conn: sqlite3.Connection = Depends(get_conn)):
    chapter = studio.get_chapter(conn, chapter_id)
    if not chapter:
        raise HTTPException(status_code=404, detail="chapter not found")
    return chapter


@app.put("/api/chapters/{chapter_id}")
def save_chapter(chapter_id: str, body: dict[str, Any], conn: sqlite3.Connection = Depends(get_conn)):
    chapter = studio.save_chapter(conn, chapter_id, body.get("content", ""), body.get("title"))
    if not chapter:
        raise HTTPException(status_code=404, detail="chapter not found")
    return chapter


@app.delete("/api/chapters/{chapter_id}")
def delete_chapter(chapter_id: str, conn: sqlite3.Connection = Depends(get_conn)):
    if not studio.delete_chapter(conn, chapter_id):
        raise HTTPException(status_code=404, detail="chapter not found")
    return {"deleted": chapter_id}


@app.get("/api/projects/{project_id}/tasks")
def list_storyboard_tasks(project_id: str, conn: sqlite3.Connection = Depends(get_conn)):
    if not projects.get_project(conn, project_id):
        raise HTTPException(status_code=404, detail="project not found")
    return tasks.list_tasks(conn, project_id)


@app.post("/api/projects/{project_id}/tasks")
def create_storyboard_task(project_id: str, body: dict[str, Any], conn: sqlite3.Connection = Depends(get_conn)):
    scene_id = body.get("scene_id")
    if not scene_id:
        raise HTTPException(status_code=400, detail="scene_id required")
    character_ids = body.get("character_ids")
    if character_ids is not None and not isinstance(character_ids, list):
        raise HTTPException(status_code=400, detail="character_ids must be a list")
    task = tasks.create_task(
        conn,
        project_id,
        scene_id,
        page_count=int(body.get("page_count", 1)),
        style_preset_id=body.get("style_preset_id"),
        character_ids=character_ids,
    )
    if not task:
        raise HTTPException(status_code=404, detail="project or scene not found")
    return task


@app.get("/api/tasks/{task_id}")
def get_storyboard_task(task_id: str, conn: sqlite3.Connection = Depends(get_conn)):
    task = tasks.get_task(conn, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="task not found")
    return task


@app.delete("/api/tasks/{task_id}")
def delete_storyboard_task(task_id: str, conn: sqlite3.Connection = Depends(get_conn)):
    if not tasks.delete_task(conn, task_id):
        raise HTTPException(status_code=404, detail="task not found")
    return {"deleted": task_id}


@app.post("/api/tasks/{task_id}/pages")
def add_storyboard_task_page(task_id: str, conn: sqlite3.Connection = Depends(get_conn)):
    page = tasks.add_task_page(conn, task_id)
    if not page:
        raise HTTPException(status_code=404, detail="task not found")
    return page


@app.post("/api/tasks/{task_id}/generate")
def generate_storyboard_task(task_id: str, body: dict[str, Any] | None = None, conn: sqlite3.Connection = Depends(get_conn)):
    task = tasks.get_task(conn, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="task not found")
    body = body or {}
    page_ids = [page["id"] for page in task["pages"]]
    if page_ids:
        jobs.generate_pages(page_ids, seed=body.get("seed"), profile=body.get("profile"))
    return {"task_id": task_id, "page_ids": page_ids, "status": "started" if page_ids else "empty"}


@app.get("/api/projects/{project_id}/story")
def get_story(project_id: str, conn: sqlite3.Connection = Depends(get_conn)):
    if not projects.get_project(conn, project_id):
        raise HTTPException(status_code=404, detail="project not found")
    return studio.get_story(conn, project_id)


@app.put("/api/projects/{project_id}/story")
def save_story(project_id: str, body: dict[str, Any], conn: sqlite3.Connection = Depends(get_conn)):
    if not projects.get_project(conn, project_id):
        raise HTTPException(status_code=404, detail="project not found")
    return studio.save_story(
        conn,
        project_id,
        title=body.get("title", ""),
        markdown=body.get("markdown", ""),
    )


@app.post("/api/projects/{project_id}/story/parse")
def parse_story(project_id: str, body: dict[str, Any] | None = None, conn: sqlite3.Connection = Depends(get_conn)):
    if not projects.get_project(conn, project_id):
        raise HTTPException(status_code=404, detail="project not found")
    body = body or {}
    markdown = body.get("markdown")
    if markdown is None:
        markdown = studio.get_story(conn, project_id)["markdown"]
    return {"scenes": studio.replace_scenes(conn, project_id, studio.parse_scenes(markdown))}


@app.post("/api/projects/{project_id}/scenes")
def create_scene(project_id: str, body: dict[str, Any], conn: sqlite3.Connection = Depends(get_conn)):
    if not projects.get_project(conn, project_id):
        raise HTTPException(status_code=404, detail="project not found")
    return studio.create_scene(conn, project_id, body)


@app.delete("/api/scenes/{scene_id}")
def delete_scene(scene_id: str, conn: sqlite3.Connection = Depends(get_conn)):
    if not studio.delete_scene(conn, scene_id):
        raise HTTPException(status_code=404, detail="scene not found")
    return {"deleted": scene_id}


@app.get("/api/projects/{project_id}/scenes")
def list_scenes(project_id: str, conn: sqlite3.Connection = Depends(get_conn)):
    return studio.list_scenes(conn, project_id)


@app.patch("/api/scenes/{scene_id}")
def update_scene(scene_id: str, body: dict[str, Any], conn: sqlite3.Connection = Depends(get_conn)):
    scene = studio.update_scene(conn, scene_id, body)
    if not scene:
        raise HTTPException(status_code=404, detail="scene not found")
    return scene


@app.post("/api/projects/{project_id}/scenes/batch_delete")
def batch_delete_scenes(project_id: str, body: dict[str, Any], conn: sqlite3.Connection = Depends(get_conn)):
    scene_ids = body.get("scene_ids")
    if not isinstance(scene_ids, list):
        raise HTTPException(status_code=400, detail="scene_ids must be a list")
    return {"deleted": studio.delete_scenes(conn, project_id, scene_ids)}


@app.post("/api/projects/{project_id}/scenes/pages")
def ensure_scene_pages(project_id: str, body: dict[str, Any] | None = None, conn: sqlite3.Connection = Depends(get_conn)):
    if not projects.get_project(conn, project_id):
        raise HTTPException(status_code=404, detail="project not found")
    body = body or {}
    return {"pages": studio.scenes_to_pages(conn, project_id, body.get("scene_ids"))}


@app.post("/api/projects/{project_id}/scenes/generate")
def generate_scenes(project_id: str, body: dict[str, Any] | None = None, conn: sqlite3.Connection = Depends(get_conn)):
    if not projects.get_project(conn, project_id):
        raise HTTPException(status_code=404, detail="project not found")
    body = body or {}
    pages = studio.scenes_to_pages(conn, project_id, body.get("scene_ids"))
    if pages:
        jobs.generate_pages([page["id"] for page in pages], seed=body.get("seed"), profile=body.get("profile"))
    return {"pages": pages, "status": "started" if pages else "empty"}


if FRONTEND_DIST.exists():
    assets_dir = FRONTEND_DIST / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{full_path:path}")
    def spa_fallback(full_path: str):
        if full_path == "api" or full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="not found")
        return FileResponse(FRONTEND_DIST / "index.html")

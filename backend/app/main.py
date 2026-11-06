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
from .services import codex, comfy, jobs, projects, prompt, studio, thumbs


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


@app.get("/api/codex/search")
def search(
    q: str,
    codex_id: str | None = None,
    category_path: str | None = None,
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
def gallery(project_id: str, sort: str = "order", conn: sqlite3.Connection = Depends(get_conn)):
    return projects.gallery_list(conn, project_id, sort=sort)


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


if FRONTEND_DIST.exists():
    assets_dir = FRONTEND_DIST / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{full_path:path}")
    def spa_fallback(full_path: str):
        if full_path == "api" or full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="not found")
        return FileResponse(FRONTEND_DIST / "index.html")

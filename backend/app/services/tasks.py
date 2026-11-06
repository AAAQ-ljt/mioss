from __future__ import annotations

import json
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any

from . import gallery, projects


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id() -> str:
    return uuid.uuid4().hex[:12]


def _load_json(value: str | None, fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def _task_status(pages: list[dict[str, Any]]) -> str:
    if not pages:
        return "draft"
    statuses = {page.get("status") or "draft" for page in pages}
    if statuses <= {"done"}:
        return "done"
    if statuses & {"queued", "running"}:
        return "running"
    if "failed" in statuses:
        return "failed"
    return "draft"


def split_scene_text(text: str, page_count: int) -> list[str]:
    page_count = max(1, min(int(page_count), 20))
    source = (text or "").strip()
    if not source:
        return [""] * page_count
    cleaned = re.sub(r"(?m)^\s*#{1,6}\s+.*$", "", source).strip()
    if cleaned:
        source = cleaned
    if page_count == 1:
        return [source]

    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", source) if part.strip()]
    if len(paragraphs) < page_count:
        sentences = [part.strip() for part in re.split(r"(?<=[。！？!?；;])", source) if part.strip()]
        units = sentences if len(sentences) >= page_count else paragraphs
    else:
        units = paragraphs
    if len(units) < page_count:
        units = [unit for unit in source.splitlines() if unit.strip()] or [source]

    buckets: list[list[str]] = [[] for _ in range(page_count)]
    for index, unit in enumerate(units):
        bucket = min(index * page_count // max(len(units), 1), page_count - 1)
        buckets[bucket].append(unit)
    chunks = ["\n\n".join(bucket).strip() for bucket in buckets]
    for index, chunk in enumerate(chunks):
        if not chunk:
            chunks[index] = source if index == 0 else ""
    return chunks


def _task_row(conn: sqlite3.Connection, task_id: str) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM storyboard_task WHERE id = ?", (task_id,)).fetchone()
    return dict(row) if row else None


def _task_pages(conn: sqlite3.Connection, task_id: str) -> list[dict[str, Any]]:
    task = _task_row(conn, task_id)
    if not task:
        return []
    pages = [page for page in projects.list_pages(conn, task["project_id"]) if page.get("task_id") == task_id]
    pages.sort(key=lambda page: (page.get("shot_no") or page.get("order_no") or 0, page.get("order_no") or 0))
    return pages


def _serialize_task(conn: sqlite3.Connection, task: dict[str, Any], pages: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    pages = pages if pages is not None else _task_pages(conn, task["id"])
    task["page_count"] = len(pages)
    task["status"] = _task_status(pages)
    task["style_snapshot"] = _load_json(task.pop("style_snapshot_json", None), {})
    task["character_snapshot"] = _load_json(task.pop("character_snapshot_json", None), [])
    return task


def list_tasks(conn: sqlite3.Connection, project_id: str) -> list[dict[str, Any]]:
    if not conn.execute("SELECT id FROM project WHERE id = ?", (project_id,)).fetchone():
        return []
    rows = conn.execute(
        """
        SELECT t.*, s.excerpt AS scene_excerpt, s.order_no AS scene_order
        FROM storyboard_task t
        LEFT JOIN story_scene s ON s.id = t.scene_id
        WHERE t.project_id = ?
        ORDER BY s.order_no, t.created_at
        """,
        (project_id,),
    ).fetchall()
    all_pages = projects.list_pages(conn, project_id)
    by_task: dict[str, list[dict[str, Any]]] = {}
    for page in all_pages:
        if page.get("task_id"):
            by_task.setdefault(page["task_id"], []).append(page)
    tasks = []
    for row in rows:
        task = _serialize_task(conn, dict(row), by_task.get(row["id"], []))
        tasks.append(task)
    return tasks


def get_task(conn: sqlite3.Connection, task_id: str) -> dict[str, Any] | None:
    row = _task_row(conn, task_id)
    if not row:
        return None
    pages = _task_pages(conn, task_id)
    task = _serialize_task(conn, row, pages)
    task["pages"] = pages
    scene = None
    if task.get("scene_id"):
        scene_row = conn.execute("SELECT * FROM story_scene WHERE id = ?", (task["scene_id"],)).fetchone()
        scene = dict(scene_row) if scene_row else None
    task["scene"] = scene
    return task


def _delete_task_records(conn: sqlite3.Connection, task: dict[str, Any]) -> None:
    pages = _task_pages(conn, task["id"])
    relative_images = []
    images_dir = projects.PROJECTS_DIR / task["project_id"]
    from pathlib import Path

    for page in pages:
        if page.get("image_path"):
            try:
                relative_images.append(Path(page["image_path"]).relative_to(images_dir).as_posix())
            except ValueError:
                continue
    if relative_images:
        gallery.delete_images(conn, task["project_id"], relative_images)
    conn.execute(
        "DELETE FROM generation_job WHERE page_id IN (SELECT id FROM page WHERE task_id = ?)",
        (task["id"],),
    )
    conn.execute("DELETE FROM page WHERE task_id = ?", (task["id"],))
    conn.execute("DELETE FROM storyboard_task WHERE id = ?", (task["id"],))
    if task.get("scene_id"):
        conn.execute(
            "UPDATE story_scene SET page_id = NULL, status = 'draft', updated_at = datetime('now') WHERE id = ?",
            (task["scene_id"],),
        )
    conn.execute("UPDATE project SET updated_at = datetime('now') WHERE id = ?", (task["project_id"],))
    conn.commit()


def delete_task(conn: sqlite3.Connection, task_id: str) -> bool:
    task = _task_row(conn, task_id)
    if not task:
        return False
    _delete_task_records(conn, task)
    return True


def delete_tasks_for_scene(conn: sqlite3.Connection, scene_id: str) -> int:
    rows = conn.execute("SELECT * FROM storyboard_task WHERE scene_id = ?", (scene_id,)).fetchall()
    for row in rows:
        _delete_task_records(conn, dict(row))
    return len(rows)


def create_task(
    conn: sqlite3.Connection,
    project_id: str,
    scene_id: str,
    page_count: int = 1,
    style_preset_id: str | None = None,
    character_ids: list[str] | None = None,
) -> dict[str, Any] | None:
    project = conn.execute("SELECT * FROM project WHERE id = ?", (project_id,)).fetchone()
    if not project:
        return None
    scene = conn.execute("SELECT * FROM story_scene WHERE id = ? AND project_id = ?", (scene_id, project_id)).fetchone()
    if not scene:
        return None

    existing = conn.execute("SELECT id FROM storyboard_task WHERE scene_id = ?", (scene_id,)).fetchone()
    if existing:
        delete_task(conn, existing["id"])

    kind = "illustration" if project["mode"] == "illustration" else "comic"
    page_count = 1 if kind == "illustration" else max(1, min(int(page_count), 20))
    style_id = style_preset_id or project["style_preset_id"]
    style_row = conn.execute("SELECT id, name, tags FROM style_preset WHERE id = ?", (style_id,)).fetchone()
    style_snapshot = dict(style_row) if style_row else {}

    if character_ids is None:
        character_rows = conn.execute(
            "SELECT id, name, anchor_tags FROM characters WHERE project_id = ? ORDER BY name",
            (project_id,),
        ).fetchall()
    else:
        selected = set(character_ids)
        character_rows = [
            row
            for row in conn.execute(
                "SELECT id, name, anchor_tags FROM characters WHERE project_id = ? ORDER BY name",
                (project_id,),
            ).fetchall()
            if row["id"] in selected
        ]
    character_snapshot = [dict(row) for row in character_rows]
    selected_ids = [row["id"] for row in character_snapshot]

    task_id = _id()
    timestamp = _now()
    title = scene["title"] or "未命名场景"
    conn.execute(
        """
        INSERT INTO storyboard_task(
          id, project_id, scene_id, chapter_title, title, kind, style_preset_id,
          style_snapshot_json, character_snapshot_json, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            task_id,
            project_id,
            scene_id,
            scene["chapter_title"] or "",
            title,
            kind,
            style_id,
            json.dumps(style_snapshot, ensure_ascii=False),
            json.dumps(character_snapshot, ensure_ascii=False),
            timestamp,
            timestamp,
        ),
    )
    conn.commit()

    chunks = split_scene_text(scene["excerpt"] or scene["summary"] or title, page_count)
    base_order = conn.execute(
        "SELECT COALESCE(MAX(order_no), 0) AS max_order FROM page WHERE project_id = ?",
        (project_id,),
    ).fetchone()["max_order"]
    first_page_id = None
    for index, chunk in enumerate(chunks, start=1):
        page = projects.add_page(
            conn,
            project_id,
            {
                "task_id": task_id,
                "shot_no": index,
                "order_no": base_order + index,
                "summary": chunk[:500],
                "layout_note": f"场景「{title}」· 第 {index}/{len(chunks)} 页",
                "kind": kind,
                "scene_id": scene_id,
                "character_ids": selected_ids,
                "continuity": {"location": scene["setting"] or "", "mood": scene["mood"] or ""},
                "status": "draft",
            },
        )
        if page and first_page_id is None:
            first_page_id = page["id"]
    conn.execute(
        "UPDATE story_scene SET page_id = ?, status = 'page_created', updated_at = datetime('now') WHERE id = ?",
        (first_page_id, scene_id),
    )
    conn.commit()
    return get_task(conn, task_id)


def add_task_page(conn: sqlite3.Connection, task_id: str) -> dict[str, Any] | None:
    task = _task_row(conn, task_id)
    if not task:
        return None
    scene = None
    if task.get("scene_id"):
        row = conn.execute("SELECT * FROM story_scene WHERE id = ?", (task["scene_id"],)).fetchone()
        scene = dict(row) if row else None
    base_order = conn.execute(
        "SELECT COALESCE(MAX(order_no), 0) + 1 AS next_order FROM page WHERE project_id = ?",
        (task["project_id"],),
    ).fetchone()["next_order"]
    snapshot = _load_json(task.get("character_snapshot_json"), [])
    page = projects.add_page(
        conn,
        task["project_id"],
        {
            "task_id": task_id,
            "order_no": base_order,
            "summary": "新页面",
            "layout_note": f"场景「{task['title']}」· 追加页",
            "kind": task["kind"],
            "scene_id": task.get("scene_id"),
            "character_ids": [item.get("id") for item in snapshot if item.get("id")],
            "continuity": {
                "location": (scene or {}).get("setting") or "",
                "mood": (scene or {}).get("mood") or "",
            },
            "status": "draft",
        },
    )
    return page

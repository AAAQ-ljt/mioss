from __future__ import annotations

import json
import shutil
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..config import PROJECTS_DIR


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def _default_character_ids(conn: sqlite3.Connection, project_id: str) -> list[str]:
    rows = conn.execute("SELECT id FROM characters WHERE project_id = ? ORDER BY name", (project_id,)).fetchall()
    return [row["id"] for row in rows]


def _page_character_ids(conn: sqlite3.Connection, page: dict[str, Any]) -> list[str]:
    if page.get("character_ids_json") is None:
        return _default_character_ids(conn, page["project_id"])
    return json.loads(page.get("character_ids_json") or "[]")


def _ref_details(conn: sqlite3.Connection, refs: list[str]) -> list[dict[str, Any]]:
    if not refs:
        return []
    placeholders = ",".join("?" for _ in refs)
    rows = conn.execute(
        f"SELECT id, title, tags_positive, image_url FROM entry WHERE id IN ({placeholders})",
        refs,
    ).fetchall()
    order = {ref: index for index, ref in enumerate(refs)}
    details = [dict(row) for row in rows]
    details.sort(key=lambda item: order.get(item["id"], len(order)))
    return details


def project_dir(project_id: str):
    path = PROJECTS_DIR / project_id
    (path / "images").mkdir(parents=True, exist_ok=True)
    return path


def create_project(
    conn: sqlite3.Connection,
    title: str,
    story: str = "",
    style_preset_id: str = "manga-ink",
    mode: str = "comic",
) -> dict[str, Any]:
    project_id = new_id()
    timestamp = now()
    conn.execute(
        """
        INSERT INTO project(id, title, story, style_preset_id, gallery_sort, mode, created_at, updated_at)
        VALUES (?, ?, ?, ?, 'order', ?, ?, ?)
        """,
        (project_id, title, story, style_preset_id, mode, timestamp, timestamp),
    )
    conn.commit()
    project_dir(project_id)
    return get_project(conn, project_id)  # type: ignore[return-value]


def list_projects(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT p.*, COUNT(g.id) page_count,
          (
            SELECT image_path FROM page
            WHERE project_id = p.id AND image_path IS NOT NULL
            ORDER BY order_no LIMIT 1
          ) thumbnail_path
        FROM project p LEFT JOIN page g ON g.project_id = p.id
        GROUP BY p.id
        ORDER BY p.updated_at DESC
        """
    ).fetchall()
    projects = []
    for row in rows:
        item = dict(row)
        item["thumbnail_url"] = _image_url(item.pop("thumbnail_path", None))
        projects.append(item)
    return projects


def get_project(conn: sqlite3.Connection, project_id: str) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM project WHERE id = ?", (project_id,)).fetchone()
    if not row:
        return None
    project = dict(row)
    project["pages"] = list_pages(conn, project_id)
    return project


def set_story(conn: sqlite3.Connection, project_id: str, story: str) -> dict[str, Any] | None:
    conn.execute(
        "UPDATE project SET story = ?, updated_at = datetime('now') WHERE id = ?",
        (story, project_id),
    )
    conn.commit()
    return get_project(conn, project_id)


def replace_pages(conn: sqlite3.Connection, project_id: str, pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    conn.execute("DELETE FROM page WHERE project_id = ?", (project_id,))
    for index, page in enumerate(pages, start=1):
        page_id = page.get("id") or new_id()
        order_no = int(page.get("order_no", index))
        refs = page.get("refs") or page.get("entry_ids") or []
        conn.execute(
            """
            INSERT INTO page(
              id, project_id, chapter_id, task_id, shot_no, order_no, summary, layout_note, prompt, negative,
              seed, status, image_path, kind, scene_id, refs_json, continuity_json, character_ids_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                page_id,
                project_id,
                page.get("chapter_id"),
                page.get("task_id"),
                page.get("shot_no"),
                order_no,
                page.get("summary", ""),
                page.get("layout_note", ""),
                page.get("prompt", ""),
                page.get("negative", ""),
                page.get("seed"),
                page.get("status", "draft"),
                page.get("image_path"),
                page.get("kind", "comic"),
                page.get("scene_id"),
                json.dumps(refs, ensure_ascii=False),
                json.dumps(page.get("continuity") or {}, ensure_ascii=False),
                json.dumps(page["character_ids"] if "character_ids" in page else _default_character_ids(conn, project_id), ensure_ascii=False),
                page.get("created_at") or now(),
                now(),
            ),
        )
    conn.execute("UPDATE project SET updated_at = datetime('now') WHERE id = ?", (project_id,))
    conn.commit()
    return list_pages(conn, project_id)


def add_page(conn: sqlite3.Connection, project_id: str, page: dict[str, Any] | None = None) -> dict[str, Any] | None:
    page = page or {}
    refs = page.get("refs") or page.get("entry_ids") or []
    task_id = page.get("task_id")
    if task_id:
        next_order = conn.execute(
            "SELECT COALESCE(MAX(order_no), 0) + 1 AS next_order FROM page WHERE task_id = ?",
            (task_id,),
        ).fetchone()["next_order"]
        next_shot = conn.execute(
            "SELECT COALESCE(MAX(shot_no), 0) + 1 AS next_shot FROM page WHERE task_id = ?",
            (task_id,),
        ).fetchone()["next_shot"]
    else:
        next_order = conn.execute(
            "SELECT COALESCE(MAX(order_no), 0) + 1 AS next_order FROM page WHERE project_id = ?",
            (project_id,),
        ).fetchone()["next_order"]
        next_shot = None
    page_id = page.get("id") or new_id()
    timestamp = now()
    conn.execute(
        """
        INSERT INTO page(
          id, project_id, chapter_id, task_id, shot_no, order_no, summary, layout_note, prompt, negative,
          seed, status, image_path, kind, scene_id, refs_json, continuity_json, character_ids_json, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            page_id,
            project_id,
            page.get("chapter_id"),
            task_id,
            int(page.get("shot_no", next_shot)) if page.get("shot_no", next_shot) is not None else None,
            int(page.get("order_no", next_order)),
            page.get("summary", "新页面"),
            page.get("layout_note", ""),
            page.get("prompt", ""),
            page.get("negative", ""),
            page.get("seed"),
            page.get("status", "draft"),
            page.get("image_path"),
            page.get("kind", "comic"),
            page.get("scene_id"),
            json.dumps(refs, ensure_ascii=False),
            json.dumps(page.get("continuity") or {}, ensure_ascii=False),
            json.dumps(page["character_ids"] if "character_ids" in page else _default_character_ids(conn, project_id), ensure_ascii=False),
            page.get("created_at") or timestamp,
            timestamp,
        ),
    )
    conn.execute("UPDATE project SET updated_at = datetime('now') WHERE id = ?", (project_id,))
    conn.commit()
    return get_page(conn, page_id)


def list_pages(conn: sqlite3.Connection, project_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM page WHERE project_id = ? ORDER BY order_no",
        (project_id,),
    ).fetchall()
    pages = []
    for row in rows:
        page = dict(row)
        page["refs"] = json.loads(page.get("refs_json") or "[]")
        page["ref_details"] = _ref_details(conn, page["refs"])
        page["continuity"] = json.loads(page.get("continuity_json") or "{}")
        page["character_ids"] = _page_character_ids(conn, page)
        page["image_url"] = _image_url(page.get("image_path"))
        pages.append(page)
    return pages


def get_page(conn: sqlite3.Connection, page_id: str) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM page WHERE id = ?", (page_id,)).fetchone()
    if not row:
        return None
    page = dict(row)
    page["refs"] = json.loads(page.get("refs_json") or "[]")
    page["ref_details"] = _ref_details(conn, page["refs"])
    page["continuity"] = json.loads(page.get("continuity_json") or "{}")
    page["character_ids"] = _page_character_ids(conn, page)
    page["image_url"] = _image_url(page.get("image_path"))
    return page


def update_page(conn: sqlite3.Connection, page_id: str, patch: dict[str, Any]) -> dict[str, Any] | None:
    allowed = {"summary", "layout_note", "prompt", "negative", "seed", "status", "image_path", "refs", "continuity", "character_ids", "kind", "scene_id", "shot_no"}
    fields = []
    params = []
    for key, value in patch.items():
        if key not in allowed:
            continue
        if key == "refs":
            fields.append("refs_json = ?")
            params.append(json.dumps(value, ensure_ascii=False))
        elif key == "continuity":
            fields.append("continuity_json = ?")
            params.append(json.dumps(value, ensure_ascii=False))
        elif key == "character_ids":
            fields.append("character_ids_json = ?")
            params.append(json.dumps(value, ensure_ascii=False))
        else:
            fields.append(f"{key} = ?")
            params.append(value)
    if not fields:
        return get_page(conn, page_id)
    fields.append("updated_at = datetime('now')")
    params.append(page_id)
    conn.execute(f"UPDATE page SET {', '.join(fields)} WHERE id = ?", params)
    conn.commit()
    return get_page(conn, page_id)


def _image_url(image_path: str | None) -> str | None:
    if not image_path:
        return None
    try:
        return "/projects/" + Path(image_path).relative_to(PROJECTS_DIR).as_posix()
    except ValueError:
        return None


def list_style_presets(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute("SELECT * FROM style_preset ORDER BY name").fetchall()
    return [dict(row) for row in rows]


def update_project(conn: sqlite3.Connection, project_id: str, patch: dict[str, Any]) -> dict[str, Any] | None:
    allowed = {"title", "story", "style_preset_id", "gallery_sort", "mode"}
    fields = []
    params = []
    for key, value in patch.items():
        if key not in allowed:
            continue
        fields.append(f"{key} = ?")
        params.append(value)
    if not fields:
        return get_project(conn, project_id)
    fields.append("updated_at = datetime('now')")
    params.append(project_id)
    conn.execute(f"UPDATE project SET {', '.join(fields)} WHERE id = ?", params)
    conn.commit()
    return get_project(conn, project_id)


def list_characters(conn: sqlite3.Connection, project_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM characters WHERE project_id = ? ORDER BY name",
        (project_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def upsert_character(conn: sqlite3.Connection, project_id: str, character: dict[str, Any]) -> dict[str, Any] | None:
    character_id = character.get("id") or new_id()
    conn.execute(
        """
        INSERT OR REPLACE INTO characters(id, project_id, name, anchor_tags, ref_image, notes)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            character_id,
            project_id,
            character.get("name", "未命名角色"),
            character.get("anchor_tags", ""),
            character.get("ref_image"),
            character.get("notes", ""),
        ),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM characters WHERE id = ?", (character_id,)).fetchone()
    return dict(row) if row else None


def reorder_pages(conn: sqlite3.Connection, project_id: str, page_ids: list[str]) -> list[dict[str, Any]]:
    rows = conn.execute("SELECT id FROM page WHERE project_id = ?", (project_id,)).fetchall()
    current = {row["id"] for row in rows}
    if set(page_ids) != current:
        raise ValueError("page_ids must contain exactly the project pages")
    for index, page_id in enumerate(page_ids, start=1):
        conn.execute("UPDATE page SET order_no = ?, updated_at = datetime('now') WHERE id = ?", (index, page_id))
    conn.execute("UPDATE project SET updated_at = datetime('now') WHERE id = ?", (project_id,))
    conn.commit()
    return list_pages(conn, project_id)


def delete_page(conn: sqlite3.Connection, page_id: str) -> bool:
    row = conn.execute("SELECT project_id, image_path FROM page WHERE id = ?", (page_id,)).fetchone()
    if not row:
        return False
    if row["image_path"]:
        try:
            relative = Path(row["image_path"]).relative_to(PROJECTS_DIR / row["project_id"]).as_posix()
        except ValueError:
            relative = None
        if relative:
            from .gallery import delete_images

            delete_images(conn, row["project_id"], [relative])
    conn.execute("DELETE FROM generation_job WHERE page_id = ?", (page_id,))
    conn.execute("DELETE FROM page WHERE id = ?", (page_id,))
    conn.execute("UPDATE story_scene SET page_id = NULL, status = 'draft' WHERE page_id = ?", (page_id,))
    conn.execute("UPDATE project SET updated_at = datetime('now') WHERE id = ?", (row["project_id"],))
    conn.commit()
    return True


def delete_project(conn: sqlite3.Connection, project_id: str) -> bool:
    row = conn.execute("SELECT id FROM project WHERE id = ?", (project_id,)).fetchone()
    if not row:
        return False
    conn.execute("DELETE FROM generation_job WHERE page_id IN (SELECT id FROM page WHERE project_id = ?)", (project_id,))
    conn.execute("DELETE FROM page WHERE project_id = ?", (project_id,))
    conn.execute("DELETE FROM storyboard_task WHERE project_id = ?", (project_id,))
    conn.execute("DELETE FROM story_scene WHERE project_id = ?", (project_id,))
    conn.execute("DELETE FROM story_doc WHERE project_id = ?", (project_id,))
    conn.execute("DELETE FROM preset_binding WHERE project_id = ?", (project_id,))
    conn.execute("DELETE FROM characters WHERE project_id = ?", (project_id,))
    conn.execute("DELETE FROM chapter WHERE project_id = ?", (project_id,))
    conn.execute("DELETE FROM project WHERE id = ?", (project_id,))
    conn.commit()
    folder = PROJECTS_DIR / project_id
    if folder.is_dir():
        trash = PROJECTS_DIR / "_trash"
        trash.mkdir(parents=True, exist_ok=True)
        target = trash / f"{project_id}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        shutil.move(str(folder), str(target))
    return True


def batch_delete_projects(conn: sqlite3.Connection, project_ids: list[str]) -> int:
    deleted = 0
    for project_id in project_ids:
        if delete_project(conn, project_id):
            deleted += 1
    return deleted


def duplicate_page(conn: sqlite3.Connection, page_id: str) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM page WHERE id = ?", (page_id,)).fetchone()
    if not row:
        return None
    source = dict(row)
    new_id_value = new_id()
    next_order = conn.execute(
        "SELECT COALESCE(MAX(order_no), 0) + 1 AS next_order FROM page WHERE project_id = ?",
        (source["project_id"],),
    ).fetchone()["next_order"]
    next_shot = None
    if source.get("task_id"):
        next_shot = conn.execute(
            "SELECT COALESCE(MAX(shot_no), 0) + 1 AS next_shot FROM page WHERE task_id = ?",
            (source["task_id"],),
        ).fetchone()["next_shot"]
    conn.execute(
        """
        INSERT INTO page(
          id, project_id, chapter_id, task_id, shot_no, order_no, summary, layout_note, prompt, negative,
          seed, status, image_path, kind, scene_id, refs_json, continuity_json, character_ids_json, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            new_id_value,
            source["project_id"],
            source["chapter_id"],
            source.get("task_id"),
            next_shot,
            next_order,
            source["summary"],
            source["layout_note"],
            source["prompt"],
            source["negative"],
            source["seed"],
            "draft",
            None,
            source.get("kind", "comic"),
            None,
            source["refs_json"],
            source["continuity_json"],
            source["character_ids_json"],
            now(),
            now(),
        ),
    )
    conn.execute("UPDATE project SET updated_at = datetime('now') WHERE id = ?", (source["project_id"],))
    conn.commit()
    return get_page(conn, new_id_value)


def export_project(conn: sqlite3.Connection, project_id: str) -> dict[str, Any] | None:
    project = get_project(conn, project_id)
    if not project:
        return None
    return {
        "project": {
            "title": project["title"],
            "story": project.get("story", ""),
            "style_preset_id": project.get("style_preset_id", "manga-ink"),
            "gallery_sort": project.get("gallery_sort", "order"),
        },
        "characters": list_characters(conn, project_id),
        "pages": project.get("pages", []),
    }


def import_project(conn: sqlite3.Connection, payload: dict[str, Any]) -> dict[str, Any] | None:
    project_meta = payload.get("project") or {}
    project = create_project(
        conn,
        title=project_meta.get("title", "导入漫画"),
        story=project_meta.get("story", ""),
        style_preset_id=project_meta.get("style_preset_id", "manga-ink"),
    )
    character_map: dict[str, str] = {}
    for character in payload.get("characters") or []:
        old_id = character.get("id")
        saved = upsert_character(
            conn,
            project["id"],
            {
                "name": character.get("name", "未命名角色"),
                "anchor_tags": character.get("anchor_tags", ""),
                "ref_image": character.get("ref_image"),
                "notes": character.get("notes", ""),
            },
        )
        if old_id and saved:
            character_map[old_id] = saved["id"]

    pages = []
    for index, page in enumerate(payload.get("pages") or [], start=1):
        pages.append(
            {
                "order_no": int(page.get("order_no", index)),
                "summary": page.get("summary", ""),
                "layout_note": page.get("layout_note", ""),
                "prompt": page.get("prompt", ""),
                "negative": page.get("negative", ""),
                "refs": page.get("refs") or [],
                "continuity": page.get("continuity") or {},
                "character_ids": [character_map.get(cid, cid) for cid in (page.get("character_ids") or [])],
                "seed": page.get("seed"),
                "status": "draft",
                "image_path": None,
            }
        )
    if pages:
        replace_pages(conn, project["id"], pages)
    return get_project(conn, project["id"])



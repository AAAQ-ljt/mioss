from __future__ import annotations

import json
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id() -> str:
    return uuid.uuid4().hex[:12]


def add_relay_item(
    conn: sqlite3.Connection,
    content: str,
    format_name: str = "plain",
    source_entry_id: str | None = None,
    source_title: str | None = None,
) -> dict[str, Any]:
    item_id = _id()
    conn.execute(
        """
        INSERT INTO relay_item(id, content, format, source_entry_id, source_title, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (item_id, content, format_name, source_entry_id, source_title, _now()),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM relay_item WHERE id = ?", (item_id,)).fetchone()
    return dict(row)


def list_relay_items(conn: sqlite3.Connection, limit: int = 200) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM relay_item ORDER BY created_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [dict(row) for row in rows]


def delete_relay_item(conn: sqlite3.Connection, item_id: str) -> bool:
    cursor = conn.execute("DELETE FROM relay_item WHERE id = ?", (item_id,))
    conn.commit()
    return cursor.rowcount > 0


def clear_relay_items(conn: sqlite3.Connection) -> int:
    cursor = conn.execute("DELETE FROM relay_item")
    conn.commit()
    return cursor.rowcount


def list_presets(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute("SELECT * FROM prompt_preset ORDER BY updated_at DESC").fetchall()
    return [dict(row) for row in rows]


def upsert_preset(conn: sqlite3.Connection, preset: dict[str, Any]) -> dict[str, Any]:
    preset_id = preset.get("id") or _id()
    timestamp = _now()
    conn.execute(
        """
        INSERT INTO prompt_preset(
          id, name, kind, positive, negative, notes, seed, profile_json,
          preview_image, usage_count, version, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 1, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
          name = excluded.name,
          kind = excluded.kind,
          positive = excluded.positive,
          negative = excluded.negative,
          notes = excluded.notes,
          seed = excluded.seed,
          profile_json = excluded.profile_json,
          preview_image = excluded.preview_image,
          version = prompt_preset.version + 1,
          updated_at = excluded.updated_at
        """,
        (
            preset_id,
            preset.get("name", "未命名预设"),
            preset.get("kind", "style"),
            preset.get("positive", ""),
            preset.get("negative", ""),
            preset.get("notes", ""),
            preset.get("seed"),
            json.dumps(preset.get("profile") or {}, ensure_ascii=False),
            preset.get("preview_image"),
            timestamp,
            timestamp,
        ),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM prompt_preset WHERE id = ?", (preset_id,)).fetchone()
    return dict(row)


def bind_preset(conn: sqlite3.Connection, project_id: str, preset_id: str) -> dict[str, Any]:
    order_row = conn.execute(
        "SELECT COALESCE(MAX(order_no), 0) + 1 AS next_order FROM preset_binding WHERE project_id = ?",
        (project_id,),
    ).fetchone()
    binding_id = _id()
    conn.execute(
        """
        INSERT OR IGNORE INTO preset_binding(id, project_id, preset_id, order_no, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (binding_id, project_id, preset_id, order_row["next_order"], _now()),
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM preset_binding WHERE project_id = ? AND preset_id = ?",
        (project_id, preset_id),
    ).fetchone()
    return dict(row)


def unbind_preset(conn: sqlite3.Connection, project_id: str, preset_id: str) -> bool:
    cursor = conn.execute(
        "DELETE FROM preset_binding WHERE project_id = ? AND preset_id = ?",
        (project_id, preset_id),
    )
    conn.commit()
    return cursor.rowcount > 0


def list_project_presets(conn: sqlite3.Connection, project_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT p.*, b.order_no binding_order
        FROM preset_binding b JOIN prompt_preset p ON p.id = b.preset_id
        WHERE b.project_id = ?
        ORDER BY b.order_no, p.updated_at
        """,
        (project_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def mark_presets_used(conn: sqlite3.Connection, preset_ids: list[str]) -> None:
    if not preset_ids:
        return
    conn.executemany(
        "UPDATE prompt_preset SET usage_count = usage_count + 1 WHERE id = ?",
        [(preset_id,) for preset_id in preset_ids],
    )
    conn.commit()


def delete_preset(conn: sqlite3.Connection, preset_id: str) -> bool:
    cursor = conn.execute("DELETE FROM prompt_preset WHERE id = ?", (preset_id,))
    conn.commit()
    return cursor.rowcount > 0


def get_story(conn: sqlite3.Connection, project_id: str) -> dict[str, Any]:
    row = conn.execute("SELECT * FROM story_doc WHERE project_id = ?", (project_id,)).fetchone()
    if not row:
        return {"project_id": project_id, "title": "", "markdown": "", "updated_at": None, "chapters": []}
    story = dict(row)
    story["chapters"] = parse_chapters(story.get("markdown") or "")
    return story


def parse_chapters(markdown: str) -> list[dict[str, Any]]:
    chapters = []
    for index, line in enumerate(markdown.splitlines(), start=1):
        match = re.match(r"^(#{1,6})\s+(.+)$", line)
        if match:
            chapters.append({"level": len(match.group(1)), "title": match.group(2).strip(), "line": index})
    return chapters


def parse_scenes(markdown: str) -> list[dict[str, Any]]:
    chapter_title = ""
    chapter_index = 0
    scenes = []
    buffer: list[str] = []

    def flush() -> None:
        text = "\n".join(buffer).strip()
        if not text:
            return
        first_line = next((line.strip() for line in text.splitlines() if line.strip()), "")
        title = re.sub(r"^#+\s*", "", first_line)[:40] or f"场景 {len(scenes) + 1}"
        scenes.append(
            {
                "chapter_title": chapter_title,
                "chapter_index": chapter_index,
                "order_no": len(scenes) + 1,
                "title": title,
                "excerpt": text[:4000],
                "summary": text[:300],
            }
        )
        buffer.clear()

    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        heading = re.match(r"^(#{1,6})\s+(.+)$", line)
        if heading:
            flush()
            chapter_title = heading.group(2).strip()
            chapter_index += 1
            continue
        if line == "---":
            flush()
            continue
        buffer.append(raw_line)
    flush()
    return scenes


def replace_scenes(conn: sqlite3.Connection, project_id: str, scenes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    conn.execute("DELETE FROM story_scene WHERE project_id = ?", (project_id,))
    timestamp = _now()
    for index, scene in enumerate(scenes, start=1):
        scene_id = scene.get("id") or _id()
        conn.execute(
            """
            INSERT INTO story_scene(
              id, project_id, chapter_title, chapter_index, order_no, title, excerpt, summary,
              characters, setting, mood, status, page_id, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                scene_id,
                project_id,
                scene.get("chapter_title", ""),
                int(scene.get("chapter_index", 0)),
                int(scene.get("order_no", index)),
                scene.get("title", ""),
                scene.get("excerpt", ""),
                scene.get("summary", ""),
                scene.get("characters", ""),
                scene.get("setting", ""),
                scene.get("mood", ""),
                scene.get("status", "draft"),
                scene.get("page_id"),
                scene.get("created_at") or timestamp,
                timestamp,
            ),
        )
    conn.execute("UPDATE project SET updated_at = datetime('now') WHERE id = ?", (project_id,))
    conn.commit()
    return list_scenes(conn, project_id)


def create_scene(conn: sqlite3.Connection, project_id: str, scene: dict[str, Any]) -> dict[str, Any]:
    next_order = conn.execute(
        "SELECT COALESCE(MAX(order_no), 0) + 1 AS next_order FROM story_scene WHERE project_id = ?",
        (project_id,),
    ).fetchone()["next_order"]
    scene_id = _id()
    timestamp = _now()
    conn.execute(
        """
        INSERT INTO story_scene(
          id, project_id, chapter_title, chapter_index, order_no, title, excerpt, summary,
          characters, setting, mood, status, page_id, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'draft', NULL, ?, ?)
        """,
        (
            scene_id,
            project_id,
            scene.get("chapter_title", ""),
            int(scene.get("chapter_index", 0)),
            int(scene.get("order_no", next_order)),
            scene.get("title", "新场景"),
            scene.get("excerpt", ""),
            scene.get("summary", ""),
            scene.get("characters", ""),
            scene.get("setting", ""),
            scene.get("mood", ""),
            timestamp,
            timestamp,
        ),
    )
    conn.execute("UPDATE project SET updated_at = datetime('now') WHERE id = ?", (project_id,))
    conn.commit()
    row = conn.execute("SELECT * FROM story_scene WHERE id = ?", (scene_id,)).fetchone()
    return dict(row)


def delete_scene(conn: sqlite3.Connection, scene_id: str) -> bool:
    row = conn.execute("SELECT project_id FROM story_scene WHERE id = ?", (scene_id,)).fetchone()
    if not row:
        return False
    conn.execute("UPDATE page SET scene_id = NULL WHERE scene_id = ?", (scene_id,))
    conn.execute("DELETE FROM story_scene WHERE id = ?", (scene_id,))
    conn.execute("UPDATE project SET updated_at = datetime('now') WHERE id = ?", (row["project_id"],))
    conn.commit()
    return True


def list_scenes(conn: sqlite3.Connection, project_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM story_scene WHERE project_id = ? ORDER BY order_no",
        (project_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def update_scene(conn: sqlite3.Connection, scene_id: str, patch: dict[str, Any]) -> dict[str, Any] | None:
    allowed = {"title", "summary", "characters", "setting", "mood", "status", "page_id", "order_no"}
    fields = []
    params = []
    for key, value in patch.items():
        if key in allowed:
            fields.append(f"{key} = ?")
            params.append(value)
    if not fields:
        return None
    fields.append("updated_at = datetime('now')")
    params.append(scene_id)
    conn.execute(f"UPDATE story_scene SET {', '.join(fields)} WHERE id = ?", params)
    conn.commit()
    row = conn.execute("SELECT * FROM story_scene WHERE id = ?", (scene_id,)).fetchone()
    return dict(row) if row else None


def scenes_to_pages(
    conn: sqlite3.Connection,
    project_id: str,
    scene_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    project = conn.execute("SELECT mode FROM project WHERE id = ?", (project_id,)).fetchone()
    if not project:
        return []
    kind = "illustration" if project["mode"] == "illustration" else "comic"
    scenes = list_scenes(conn, project_id)
    if scene_ids:
        scenes = [scene for scene in scenes if scene["id"] in set(scene_ids)]

    from .projects import add_page

    pages = []
    for scene in scenes:
        page = None
        if scene.get("page_id"):
            page = conn.execute("SELECT * FROM page WHERE id = ?", (scene["page_id"],)).fetchone()
        if not page:
            page = add_page(
                conn,
                project_id,
                {
                    "summary": scene.get("summary") or scene.get("excerpt") or scene.get("title"),
                    "layout_note": scene.get("setting") or "",
                    "kind": kind,
                    "scene_id": scene["id"],
                    "status": "draft",
                },
            )
            conn.execute(
                "UPDATE story_scene SET page_id = ?, status = 'page_created', updated_at = datetime('now') WHERE id = ?",
                (page["id"], scene["id"]),
            )
            conn.commit()
        pages.append(dict(page))
    return pages


def save_story(conn: sqlite3.Connection, project_id: str, title: str, markdown: str) -> dict[str, Any]:
    timestamp = _now()
    conn.execute(
        """
        INSERT INTO story_doc(project_id, title, markdown, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(project_id) DO UPDATE SET
          title = excluded.title,
          markdown = excluded.markdown,
          updated_at = excluded.updated_at
        """,
        (project_id, title, markdown, timestamp),
    )
    conn.commit()
    return get_story(conn, project_id)

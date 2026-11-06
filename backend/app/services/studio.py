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

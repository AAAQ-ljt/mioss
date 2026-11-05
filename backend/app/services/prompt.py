from __future__ import annotations

import json
import sqlite3
from typing import Any

from .sanitize import normalize_tag_list

DEFAULT_NEGATIVE = (
    "worst quality, bad quality, lowres, blurry, watermark, signature, text, "
    "error, deformed, bad anatomy, bad hands, extra digits"
)


CONTINUITY_FIELDS = (
    ("location", "地点"),
    ("time", "时间"),
    ("outfit", "服装"),
    ("injuries", "伤势"),
    ("props", "道具"),
    ("mood", "情绪"),
)


def continuity_text(continuity: dict[str, str] | None) -> str:
    if not continuity:
        return ""
    parts = []
    for key, label in CONTINUITY_FIELDS:
        value = (continuity.get(key) or "").strip()
        if value:
            parts.append(f"{label}: {value}")
    return "; ".join(parts)


def compose_prompt(
    conn: sqlite3.Connection,
    style_preset_id: str = "cinematic-anime",
    entry_ids: list[str] | None = None,
    page_text: str = "",
    character_text: str = "",
    negative_text: str = "",
    include_nsfw: bool = False,
    project_id: str | None = None,
    character_ids: list[str] | None = None,
    continuity_text_value: str = "",
) -> dict[str, Any]:
    style = conn.execute("SELECT tags FROM style_preset WHERE id = ?", (style_preset_id,)).fetchone()
    positive_parts: list[str] = []
    negative_parts: list[str] = [DEFAULT_NEGATIVE, negative_text]
    dropped: list[dict[str, str]] = []

    if style:
        positive_parts.append(style["tags"])
    else:
        dropped.append({"id": style_preset_id, "reason": "style_not_found"})

    if character_text:
        positive_parts.append(character_text)
    for character_id in character_ids or []:
        if not project_id:
            dropped.append({"id": character_id, "reason": "character_requires_project"})
            continue
        character = conn.execute(
            "SELECT name, anchor_tags FROM characters WHERE id = ? AND project_id = ?",
            (character_id, project_id),
        ).fetchone()
        if not character:
            dropped.append({"id": character_id, "reason": "character_not_found"})
            continue
        if character["anchor_tags"]:
            positive_parts.append(character["anchor_tags"])
    if continuity_text_value:
        positive_parts.append(continuity_text_value)
    if page_text:
        positive_parts.append(page_text)

    for entry_id in entry_ids or []:
        entry = conn.execute(
            """
            SELECT id, title, tags_positive, tags_negative, negative_raw, moss_usable, rating
            FROM entry WHERE id = ?
            """,
            (entry_id,),
        ).fetchone()
        if not entry:
            dropped.append({"id": entry_id, "reason": "entry_not_found"})
            continue
        if not include_nsfw and entry["rating"] not in (None, "safe"):
            dropped.append({"id": entry_id, "reason": "entry_nsfw"})
            continue
        if not entry["moss_usable"]:
            dropped.append({"id": entry_id, "reason": "entry_not_moss_usable"})
            continue
        positive_parts.append(entry["tags_positive"] or "")
        negative_parts.append(entry["tags_negative"] or "")
        negative_parts.append(entry["negative_raw"] or "")

    positive = normalize_tag_list(", ".join(positive_parts))
    negative = normalize_tag_list(", ".join(negative_parts))
    return {
        "positive": positive,
        "negative": negative,
        "positive_count": len(positive.split(", ")) if positive else 0,
        "negative_count": len(negative.split(", ")) if negative else 0,
        "dropped": dropped,
    }


def compose_for_page(
    conn: sqlite3.Connection,
    page_id: str,
    entry_ids: list[str] | None = None,
    character_ids: list[str] | None = None,
    style_preset_id: str | None = None,
    page_text: str | None = None,
    character_text: str = "",
    negative_text: str = "",
    include_nsfw: bool = False,
    save: bool = True,
) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM page WHERE id = ?", (page_id,)).fetchone()
    if not row:
        return None
    page = dict(row)

    resolved_entry_ids = entry_ids if entry_ids is not None else json.loads(page.get("refs_json") or "[]")
    if character_ids is None:
        if page.get("character_ids_json") is None:
            character_ids = [
                char["id"]
                for char in conn.execute(
                    "SELECT id FROM characters WHERE project_id = ? ORDER BY name",
                    (page["project_id"],),
                ).fetchall()
            ]
        else:
            character_ids = json.loads(page.get("character_ids_json") or "[]")

    if style_preset_id is None:
        project = conn.execute("SELECT style_preset_id FROM project WHERE id = ?", (page["project_id"],)).fetchone()
        style_preset_id = project["style_preset_id"] if project else "manga-ink"

    resolved_page_text = page_text
    if resolved_page_text is None:
        resolved_page_text = f"{page.get('summary') or ''} {page.get('layout_note') or ''}".strip()

    continuity_value = continuity_text(json.loads(page.get("continuity_json") or "{}"))
    result = compose_prompt(
        conn,
        style_preset_id=style_preset_id,
        entry_ids=resolved_entry_ids,
        page_text=resolved_page_text,
        character_text=character_text,
        negative_text=negative_text,
        include_nsfw=include_nsfw,
        project_id=page["project_id"],
        character_ids=character_ids,
        continuity_text_value=continuity_value,
    )

    if save:
        conn.execute(
            """
            UPDATE page
            SET prompt = ?, negative = ?, refs_json = ?, character_ids_json = ?, updated_at = datetime('now')
            WHERE id = ?
            """,
            (
                result["positive"],
                result["negative"],
                json.dumps(resolved_entry_ids, ensure_ascii=False),
                json.dumps(character_ids, ensure_ascii=False),
                page_id,
            ),
        )
        conn.commit()
    return result

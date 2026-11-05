from __future__ import annotations

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

    return {
        "positive": normalize_tag_list(", ".join(positive_parts)),
        "negative": normalize_tag_list(", ".join(negative_parts)),
        "dropped": dropped,
    }

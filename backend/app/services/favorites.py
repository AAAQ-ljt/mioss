from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any

from .codex import get_entry
from .prompt import DEFAULT_NEGATIVE
from .sanitize import normalize_tag_list


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id() -> str:
    return uuid.uuid4().hex[:12]


def list_favorites(conn: sqlite3.Connection, domain: str | None = None) -> list[dict[str, Any]]:
    if domain:
        rows = conn.execute(
            "SELECT * FROM favorite_entry WHERE domain = ? ORDER BY created_at DESC",
            (domain,),
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM favorite_entry ORDER BY created_at DESC").fetchall()
    return [dict(row) for row in rows]


def favorite_ids(conn: sqlite3.Connection) -> list[str]:
    return [row["entry_id"] for row in conn.execute("SELECT entry_id FROM favorite_entry").fetchall()]


def toggle_favorite(conn: sqlite3.Connection, entry_id: str) -> dict[str, Any]:
    existing = conn.execute("SELECT id FROM favorite_entry WHERE entry_id = ?", (entry_id,)).fetchone()
    if existing:
        conn.execute("DELETE FROM favorite_entry WHERE entry_id = ?", (entry_id,))
        conn.commit()
        return {"favorited": False, "entry_id": entry_id}

    entry = get_entry(conn, entry_id)
    if not entry:
        raise KeyError(f"entry not found: {entry_id}")
    if entry.get("domain") not in {"regular", "nsfw"}:
        raise ValueError("画师参考不参与收藏；它不用于 MOSS 生成")

    codex_row = conn.execute("SELECT title FROM codex WHERE id = ?", (entry["codex_id"],)).fetchone()
    negative = normalize_tag_list(
        ", ".join(filter(None, [entry.get("tags_negative") or "", entry.get("negative_raw") or ""]))
    )
    favorite_id = _id()
    conn.execute(
        """
        INSERT INTO favorite_entry(
          id, entry_id, domain, title, image_url, source_title,
          prompt_nai, prompt_moss, prompt_sd_positive, negative_nai, negative_sd, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            favorite_id,
            entry_id,
            entry["domain"],
            entry.get("title") or "",
            entry.get("image_url"),
            codex_row["title"] if codex_row else entry["codex_id"],
            entry.get("tags_raw") or "",
            entry.get("tags_positive") or "",
            entry.get("prompt_sd_positive") or "",
            negative,
            entry.get("prompt_sd_negative") or "",
            _now(),
        ),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM favorite_entry WHERE id = ?", (favorite_id,)).fetchone()
    return {"favorited": True, "item": dict(row)}


def delete_favorite(conn: sqlite3.Connection, entry_id: str) -> bool:
    cursor = conn.execute("DELETE FROM favorite_entry WHERE entry_id = ?", (entry_id,))
    conn.commit()
    return cursor.rowcount > 0


def clear_favorites(conn: sqlite3.Connection) -> int:
    cursor = conn.execute("DELETE FROM favorite_entry")
    conn.commit()
    return cursor.rowcount


def _dedupe_prompts(chunks: list[str], normalize: bool) -> str:
    if normalize:
        return normalize_tag_list(", ".join(chunks))
    seen: set[str] = set()
    output = []
    for chunk in chunks:
        text = chunk.strip()
        if text and text not in seen:
            seen.add(text)
            output.append(text)
    return ", ".join(output)


def compose_favorites(conn: sqlite3.Connection, entry_ids: list[str], format_name: str = "moss") -> dict[str, Any]:
    if format_name not in {"nai", "moss", "sd"}:
        raise ValueError("format must be nai, moss or sd")
    rows = conn.execute("SELECT * FROM favorite_entry").fetchall()
    by_entry = {row["entry_id"]: dict(row) for row in rows}

    selected = []
    missing = []
    for entry_id in entry_ids:
        row = by_entry.get(entry_id)
        if row:
            selected.append(row)
        else:
            missing.append(entry_id)

    positive_key = {"nai": "prompt_nai", "moss": "prompt_moss", "sd": "prompt_sd_positive"}[format_name]
    negative_key = "negative_sd" if format_name == "sd" else "negative_nai"
    positives = [row[positive_key] or "" for row in selected]
    negatives = [DEFAULT_NEGATIVE, *[row[negative_key] or "" for row in selected]]
    normalize = format_name != "nai"
    domains = {row["domain"] for row in selected}
    return {
        "positive": _dedupe_prompts(positives, normalize),
        "negative": _dedupe_prompts(negatives, normalize),
        "count": len(selected),
        "mixed": len(domains) > 1,
        "missing": missing,
    }

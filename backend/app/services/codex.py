from __future__ import annotations

import json
import re
import sqlite3
from typing import Any

from .weights import decorate_entry

CJK_RE = re.compile(r"[\u3400-\u9fff\u3040-\u30ff]")


def list_codexes(conn: sqlite3.Connection, include_nsfw: bool = False) -> list[dict[str, Any]]:
    sql = "SELECT id, title, author, version, type, nsfw, entry_count FROM codex"
    if not include_nsfw:
        sql += " WHERE nsfw=0"
    sql += " ORDER BY nsfw, title"
    return [dict(row) for row in conn.execute(sql).fetchall()]


def categories(conn: sqlite3.Connection, codex_id: str) -> list[dict[str, Any]]:
    row = conn.execute("SELECT tree_json FROM codex WHERE id = ?", (codex_id,)).fetchone()
    if not row or not row["tree_json"]:
        return []
    return json.loads(row["tree_json"])


def get_entry(conn: sqlite3.Connection, entry_id: str) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM entry WHERE id = ?", (entry_id,)).fetchone()
    if not row:
        return None
    entry = dict(row)
    entry["category_path"] = json.loads(entry.get("category_path_json") or "[]")
    return decorate_entry(entry)


def suggest_tags(conn: sqlite3.Connection, query: str, limit: int = 20) -> list[dict[str, Any]]:
    q = query.strip().lower()
    if not q:
        return []
    rows = conn.execute(
        """
        SELECT tag, COUNT(*) count FROM entry_tag
        WHERE kind = 'positive' AND tag LIKE ?
        GROUP BY tag
        ORDER BY count DESC, tag ASC
        LIMIT ?
        """,
        (f"%{q}%", limit),
    ).fetchall()
    zh_rows = conn.execute(
        """
        SELECT zh AS tag, COUNT(*) count FROM tag_zh
        WHERE zh LIKE ?
        GROUP BY zh
        ORDER BY count DESC, zh ASC
        LIMIT ?
        """,
        (f"%{query.strip()}%", limit),
    ).fetchall()
    seen: set[str] = set()
    suggestions = []
    for row in [*rows, *zh_rows]:
        tag = row["tag"]
        if tag not in seen:
            seen.add(tag)
            suggestions.append({"tag": tag, "count": row["count"]})
    return suggestions[:limit]


def search_entries(
    conn: sqlite3.Connection,
    query: str,
    codex_id: str | None = None,
    category_path: str | None = None,
    include_artist_only: bool = False,
    include_nsfw: bool = False,
    limit: int = 20,
) -> list[dict[str, Any]]:
    q = query.strip().lower()

    clauses: list[str] = []
    params: list[str] = []
    if not include_nsfw:
        clauses.append("c.nsfw = 0")
        clauses.append("(e.rating IS NULL OR e.rating = 'safe')")
    if not include_artist_only:
        clauses.append("e.moss_usable = 1")
    if codex_id:
        clauses.append("e.codex_id = ?")
        params.append(codex_id)
    if category_path:
        clauses.append("(e.category_path_text = ? OR e.category_path_text LIKE ?)")
        params.extend([category_path, f"{category_path} / %"])

    zh_tags: list[str] = []
    if q:
        broad: list[str] = [
            "LOWER(e.title) LIKE ?",
            "LOWER(e.tags_positive) LIKE ?",
            "LOWER(COALESCE(e.note, '')) LIKE ?",
        ]
        params.extend([f"%{q}%", f"%{q}%", f"%{q}%"])

        if CJK_RE.search(query):
            zh_rows = conn.execute(
                "SELECT DISTINCT tag FROM tag_zh WHERE zh LIKE ? LIMIT 50",
                (f"%{query}%",),
            ).fetchall()
            zh_tags = [row["tag"].lower() for row in zh_rows]
            for tag in zh_tags:
                broad.append("LOWER(e.tags_positive) LIKE ?")
                params.append(f"%{tag}%")

        clauses.append("(" + " OR ".join(broad) + ")")

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    order = "ORDER BY RANDOM()" if not q and not codex_id and not category_path else "ORDER BY e.id"
    sql = f"SELECT e.* FROM entry e JOIN codex c ON c.id = e.codex_id {where} {order} LIMIT 300"
    rows = [dict(row) for row in conn.execute(sql, params).fetchall()]
    if not q:
        return [decorate_entry(row) for row in rows[:limit]]

    exact_tags = {q, *zh_tags}
    scored: list[tuple[int, dict[str, Any]]] = []
    for row in rows:
        tags = [tag.strip() for tag in (row.get("tags_positive") or "").split(",")]
        score = 0
        title = (row.get("title") or "").lower()
        note = (row.get("note") or "").lower()
        positive = (row.get("tags_positive") or "").lower()
        if title == q:
            score += 100
        if q in tags:
            score += 80
        if any(tag in exact_tags for tag in tags):
            score += 70
        if q in title:
            score += 30
        if q in note:
            score += 20
        if q in positive:
            score += 10
        scored.append((score, row))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [decorate_entry(item[1]) for item in scored[:limit]]

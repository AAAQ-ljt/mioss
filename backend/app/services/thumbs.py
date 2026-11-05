from __future__ import annotations

import sqlite3
from pathlib import Path

import httpx

from ..config import THUMB_DIR
from .codex import get_entry


def _cache_path(entry: dict) -> Path | None:
    image = entry.get("image")
    if not image:
        return None
    codex_id = entry["codex_id"]
    path = Path(image)
    asset_rev = entry.get("asset_rev")
    name = f"{path.stem}_{asset_rev}{path.suffix}" if asset_rev else path.name
    return THUMB_DIR / codex_id / name


def ensure_thumbnail(conn: sqlite3.Connection, entry_id: str) -> tuple[dict | None, Path | None]:
    entry = get_entry(conn, entry_id)
    if not entry or not entry.get("image_url"):
        return entry, None

    path = _cache_path(entry)
    if not path:
        return entry, None
    if path.exists():
        return entry, path

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        with httpx.Client(timeout=httpx.Timeout(30.0, read=120.0), follow_redirects=True) as client:
            response = client.get(entry["image_url"])
            response.raise_for_status()
            tmp.write_bytes(response.content)
        tmp.replace(path)
        return entry, path
    except Exception:
        tmp.unlink(missing_ok=True)
        return entry, None

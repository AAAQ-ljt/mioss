from __future__ import annotations

import mimetypes
import shutil
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

from ..config import PROJECTS_DIR

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


def images_dir(project_id: str) -> Path:
    path = PROJECTS_DIR / project_id / "images"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _url(project_id: str, relative: str) -> str:
    return "/projects/" + quote(f"{project_id}/{relative}", safe="/")


def _resolve_image(project_id: str, relative: str) -> Path | None:
    if not relative:
        return None
    try:
        base = images_dir(project_id).resolve()
        target = (PROJECTS_DIR / project_id / relative).resolve()
    except (OSError, ValueError):
        return None
    if target.parent != base or not target.is_file() or target.suffix.lower() not in IMAGE_SUFFIXES:
        return None
    return target


def _page_map(conn: sqlite3.Connection, project_id: str) -> dict[str, dict[str, Any]]:
    rows = conn.execute(
        "SELECT id, order_no, summary, status, image_path, kind, scene_id FROM page WHERE project_id = ?",
        (project_id,),
    ).fetchall()
    pages: dict[str, dict[str, Any]] = {}
    for row in rows:
        if row["image_path"]:
            pages.setdefault(Path(row["image_path"]).name.lower(), dict(row))
    return pages


def list_gallery(
    conn: sqlite3.Connection,
    project_id: str,
    sort: str = "order",
) -> list[dict[str, Any]] | None:
    project = conn.execute("SELECT id FROM project WHERE id = ?", (project_id,)).fetchone()
    if not project:
        return None
    pages = _page_map(conn, project_id)
    items: list[dict[str, Any]] = []
    for path in images_dir(project_id).iterdir():
        if not path.is_file() or path.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        try:
            stat = path.stat()
        except OSError:
            continue
        page = pages.get(path.name.lower())
        relative = path.relative_to(PROJECTS_DIR / project_id).as_posix()
        items.append(
            {
                "path": relative,
                "name": path.name,
                "url": _url(project_id, relative),
                "size": stat.st_size,
                "mtime": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
                "page_id": page["id"] if page else None,
                "order_no": page["order_no"] if page else None,
                "summary": page["summary"] if page else "",
                "status": page["status"] if page else None,
                "kind": page["kind"] if page else None,
                "scene_id": page["scene_id"] if page else None,
            }
        )
    if sort == "time":
        items.sort(key=lambda item: (item["mtime"], item["name"]), reverse=True)
    else:
        items.sort(
            key=lambda item: (
                0 if item["order_no"] is not None else 1,
                item["order_no"] if item["order_no"] is not None else 0,
                item["name"].lower(),
            )
        )
    return items


def delete_images(conn: sqlite3.Connection, project_id: str, relative_paths: list[str]) -> list[str]:
    targets: list[tuple[str, Path]] = []
    seen: set[str] = set()
    for relative in relative_paths:
        if not isinstance(relative, str) or relative in seen:
            continue
        path = _resolve_image(project_id, relative)
        if path is None:
            continue
        seen.add(relative)
        targets.append((relative, path))

    if not targets:
        return []

    trash = PROJECTS_DIR / "_trash_images" / f"{project_id}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    trash.mkdir(parents=True, exist_ok=True)
    pages_by_name: dict[str, list[str]] = {}
    for page in _page_map(conn, project_id).values():
        pages_by_name.setdefault(Path(page["image_path"]).name.lower(), []).append(page["id"])

    deleted: list[str] = []
    for relative, path in targets:
        target = trash / path.name
        if target.exists():
            target = trash / f"{path.stem}-{uuid.uuid4().hex[:6]}{path.suffix}"
        shutil.move(str(path), str(target))
        for page_id in pages_by_name.get(path.name.lower(), []):
            conn.execute(
                "UPDATE page SET image_path = NULL, status = 'draft', updated_at = datetime('now') WHERE id = ?",
                (page_id,),
            )
        deleted.append(relative)

    conn.execute("UPDATE project SET updated_at = datetime('now') WHERE id = ?", (project_id,))
    conn.commit()
    return deleted


def download_info(
    conn: sqlite3.Connection,
    project_id: str,
    relative: str,
) -> tuple[Path, str] | None:
    path = _resolve_image(project_id, relative)
    if path is None:
        return None
    order_no = None
    for page in _page_map(conn, project_id).values():
        if Path(page["image_path"]).name.lower() == path.name.lower():
            order_no = page["order_no"]
            break
    filename = f"page-{int(order_no):03d}{path.suffix.lower()}" if order_no is not None else path.name
    media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return path, filename

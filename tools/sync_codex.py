from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app import config  # noqa: E402
from backend.app.db import connect, migrate  # noqa: E402
from backend.app.services.sanitize import (  # noqa: E402
    artist_keys,
    normalize_tag_list,
    sanitize_tags,
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class Downloader:
    def __init__(self, client: httpx.Client):
        self.client = client

    def json(self, url: str, target: Path, expected_sha: str | None = None, force: bool = False) -> Any:
        if target.exists() and not force:
            if expected_sha is None or sha256_file(target) == expected_sha:
                return json.loads(target.read_text(encoding="utf-8"))
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(target.suffix + ".tmp")
        last_error: Exception | None = None
        for attempt in range(6):
            try:
                with self.client.stream("GET", url) as response:
                    if response.status_code == 404:
                        return None
                    response.raise_for_status()
                    with tmp.open("wb") as handle:
                        for chunk in response.iter_bytes(1024 * 1024):
                            handle.write(chunk)
                if expected_sha and sha256_file(tmp) != expected_sha:
                    raise ValueError(f"sha256 mismatch: {url}")
                tmp.replace(target)
                return json.loads(target.read_text(encoding="utf-8"))
            except Exception as error:
                last_error = error
                tmp.unlink(missing_ok=True)
                wait = min(30, 2**attempt)
                print(f"download failed {url}: {type(error).__name__} {error}; retry in {wait}s", file=sys.stderr)
                time.sleep(wait)
        raise RuntimeError(f"download failed after retries: {url}") from last_error


def load_artist_set(conn: sqlite3.Connection, downloader: Downloader, base: str, release: str, force: bool) -> set[str]:
    artists: set[str] = set()
    strings = downloader.json(
        f"{base}artist_strings.json",
        config.RAW_DIR / release / "artist_strings.json",
        force=force,
    )
    if strings:
        for version in strings.get("versions", {}).values():
            for artist in version.get("artists", []):
                artists.update(artist_keys(artist))

    index = downloader.json(
        f"{base}artist_index.json",
        config.RAW_DIR / release / "artist_index.json",
        force=force,
    )
    if index:
        for version in index.get("versions", {}).values():
            for artist in version.get("samples", {}).keys():
                artists.update(artist_keys(artist))

    conn.execute("DELETE FROM artist_tag")
    conn.executemany("INSERT OR REPLACE INTO artist_tag(tag) VALUES (?)", [(artist,) for artist in sorted(artists)])
    conn.commit()
    return artists


def image_url(codex_id: str, image: str | None, asset_rev: str | None) -> str | None:
    if not image:
        return None
    if asset_rev:
        return f"{config.IMAGE_CDN_URL}{codex_id}/{image}?v={asset_rev}"
    return f"{config.IMAGE_CDN_URL}{codex_id}/{image}"


def import_entries(conn: sqlite3.Connection, codex_meta: dict[str, Any], data: dict[str, Any], artists: set[str], release: str) -> tuple[int, int]:
    codex_id = codex_meta["id"]
    entries = data.get("entries") or []
    is_artist_codex = codex_id.startswith("artist_") or codex_meta.get("type") == "string"
    conn.execute(
        """
        INSERT OR REPLACE INTO codex(
          id, title, author, version, type, nsfw, entry_count, source_release,
          content_hash, tree_json, synced_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        """,
        (
            codex_id,
            codex_meta.get("title") or data.get("title") or codex_id,
            codex_meta.get("author") or data.get("author"),
            codex_meta.get("version") or data.get("version"),
            codex_meta.get("type") or data.get("type"),
            1 if codex_meta.get("nsfw") else 0,
            int(codex_meta.get("entryCount") or len(entries)),
            release,
            data.get("contentHash"),
            json.dumps(data.get("tree") or [], ensure_ascii=False),
        ),
    )

    entry_rows = []
    tag_rows = []
    for entry in entries:
        tags_raw = entry.get("tags") or ""
        sanitized = sanitize_tags(tags_raw, artists)
        negative_raw = normalize_tag_list(entry.get("negative") or "")
        path = entry.get("path") or []
        entry_rows.append(
            (
                entry.get("id"),
                codex_id,
                entry.get("title"),
                json.dumps(path, ensure_ascii=False),
                tags_raw,
                sanitized.positive_text,
                sanitized.negative_text,
                negative_raw,
                entry.get("note"),
                entry.get("image"),
                image_url(codex_id, entry.get("image"), entry.get("asset_rev")),
                entry.get("imageWidth"),
                entry.get("imageHeight"),
                entry.get("original"),
                entry.get("assetRev"),
                entry.get("rating"),
                1 if entry.get("isNew") else 0,
                1 if sanitized.moss_usable and not is_artist_codex else 0,
                sanitized.artist_ratio,
                json.dumps(entry, ensure_ascii=False),
            )
        )
        for tag in sanitized.positive:
            tag_rows.append((entry.get("id"), tag, "positive"))
        for tag in sanitized.negative:
            tag_rows.append((entry.get("id"), tag, "negative"))
        for item in sanitized.dropped:
            if item["reason"] == "artist":
                tag_rows.append((entry.get("id"), item["tag"], "artist"))

    conn.executemany(
        """
        INSERT OR REPLACE INTO entry(
          id, codex_id, title, category_path_json, tags_raw, tags_positive, tags_negative,
          negative_raw, note, image, image_url, image_width, image_height, original,
          asset_rev, rating, is_new, moss_usable, artist_ratio, raw_json, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        """,
        entry_rows,
    )
    conn.execute("DELETE FROM entry_tag WHERE entry_id IN (SELECT id FROM entry WHERE codex_id = ?)", (codex_id,))
    conn.executemany("INSERT OR REPLACE INTO entry_tag(entry_id, tag, kind) VALUES (?, ?, ?)", tag_rows)
    conn.commit()
    return len(entry_rows), len(tag_rows)


def import_tag_zh(conn: sqlite3.Connection, downloader: Downloader, base: str, release: str, codex_id: str, manifest_files: dict[str, dict[str, Any]], force: bool) -> int:
    rel = f"tag_zh/{codex_id}.json"
    if rel not in manifest_files:
        return 0
    data = downloader.json(
        f"{base}{rel}",
        config.RAW_DIR / release / rel,
        manifest_files[rel].get("sha256"),
        force=force,
    )
    if not data:
        return 0
    rows = []
    for tag, zh in (data.get("d") or {}).items():
        if isinstance(zh, str) and zh:
            rows.append((tag, zh, codex_id))
    conn.executemany("INSERT OR REPLACE INTO tag_zh(tag, zh, codex_id) VALUES (?, ?, ?)", rows)
    conn.commit()
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync quicktagcloud codex data into local SQLite.")
    parser.add_argument("--codex", action="append", help="Only sync selected codex id. Repeatable.")
    parser.add_argument("--force", action="store_true", help="Re-download even if cached.")
    parser.add_argument("--skip-tag-zh", action="store_true")
    args = parser.parse_args()

    config.ensure_dirs()
    conn = connect()
    migrate(conn)

    with httpx.Client(
        headers={"User-Agent": "moss-tag-studio/0.1", "Referer": "https://novelai.quicktagcloud.com/"},
        timeout=httpx.Timeout(30.0, read=300.0),
        follow_redirects=True,
    ) as client:
        downloader = Downloader(client)
        current = downloader.json(f"{config.DATA_SOURCE_URL}current.json", config.DATA_DIR / "current.json")
        release = current["release"]
        base = f"{config.DATA_SOURCE_URL}releases/{release}/"
        manifest = downloader.json(
            f"{base}manifest.json",
            config.RAW_DIR / release / "manifest.json",
            force=args.force,
        )
        codexes = downloader.json(
            f"{base}codexes.json",
            config.RAW_DIR / release / "codexes.json",
            force=args.force,
        )
        manifest_files = manifest.get("files", {})

        artists = load_artist_set(conn, downloader, base, release, args.force)
        selected = set(args.codex or [])
        total_entries = 0
        total_tags = 0
        total_zh = 0

        for meta in codexes:
            codex_id = meta["id"]
            if selected and codex_id not in selected:
                continue
            rel = f"{codex_id}.json"
            if rel not in manifest_files:
                print(f"skip {codex_id}: not in manifest", file=sys.stderr)
                continue
            data = downloader.json(
                f"{base}{rel}",
                config.RAW_DIR / release / rel,
                manifest_files[rel].get("sha256"),
                force=args.force,
            )
            entries, tags = import_entries(conn, meta, data, artists, release)
            zh = 0 if args.skip_tag_zh else import_tag_zh(conn, downloader, base, release, codex_id, manifest_files, args.force)
            total_entries += entries
            total_tags += tags
            total_zh += zh
            print(f"synced {codex_id}: entries={entries} entry_tags={tags} tag_zh={zh}")

        conn.execute("INSERT OR REPLACE INTO setting(key, value) VALUES ('release', ?)", (release,))
        conn.execute("INSERT OR REPLACE INTO setting(key, value) VALUES ('content_hash', ?)", (current.get("contentHash"),))
        conn.execute("INSERT OR REPLACE INTO setting(key, value) VALUES ('published_at', ?)", (current.get("publishedAt"),))
        conn.execute("INSERT OR REPLACE INTO setting(key, value) VALUES ('synced_at', datetime('now'))")
        conn.commit()

    print(f"release={release} artists={len(artists)} entries={total_entries} entry_tags={total_tags} tag_zh={total_zh}")


if __name__ == "__main__":
    main()

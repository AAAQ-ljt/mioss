from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.config import DATA_DIR  # noqa: E402
from backend.app.db import connect  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Export MOSS-usable codex prompts to JSONL and CSV.")
    parser.add_argument("--include-nsfw", action="store_true")
    parser.add_argument("--include-artist-codex", action="store_true")
    parser.add_argument("--out-dir", default=str(DATA_DIR / "exports"))
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = out_dir / "moss_prompts.jsonl"
    csv_path = out_dir / "moss_prompts.csv"

    clauses = ["e.moss_usable = 1"]
    if not args.include_nsfw:
        clauses.append("c.nsfw = 0")
        clauses.append("(e.rating IS NULL OR e.rating = 'safe')")
    if not args.include_artist_codex:
        clauses.append("e.codex_id NOT LIKE 'artist_%'")

    conn = connect()
    rows = conn.execute(
        f"""
        SELECT e.id, e.codex_id, e.title, e.category_path_json, e.tags_positive, e.tags_negative,
               e.negative_raw, e.note, e.image_url
        FROM entry e JOIN codex c ON c.id = e.codex_id
        WHERE {' AND '.join(clauses)}
        ORDER BY e.codex_id, e.id
        """
    ).fetchall()

    fields = ["id", "codex_id", "title", "category", "positive", "negative", "note", "image_url"]
    with jsonl_path.open("w", encoding="utf-8") as jsonl, csv_path.open("w", encoding="utf-8", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            item = dict(row)
            record = {
                "id": item["id"],
                "codex_id": item["codex_id"],
                "title": item.get("title") or "",
                "category": " / ".join(json.loads(item.get("category_path_json") or "[]")),
                "positive": item.get("tags_positive") or "",
                "negative": ", ".join(filter(None, [item.get("tags_negative") or "", item.get("negative_raw") or ""])),
                "note": item.get("note") or "",
                "image_url": item.get("image_url") or "",
            }
            jsonl.write(json.dumps(record, ensure_ascii=False) + "\n")
            writer.writerow(record)

    print(jsonl_path)
    print(csv_path)
    print("rows:", len(rows))


if __name__ == "__main__":
    main()

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.db import connect, migrate  # noqa: E402


def main() -> None:
    conn = connect()
    migrate(conn)
    deleted_ids = {
        row["id"]
        for row in conn.execute("SELECT id FROM entry WHERE cat_primary = 'nsfw_extreme'").fetchall()
    }
    if not deleted_ids:
        print("nothing to delete")
        return

    conn.executemany("DELETE FROM entry_tag WHERE entry_id = ?", [(entry_id,) for entry_id in deleted_ids])
    conn.executemany("DELETE FROM entry_category WHERE entry_id = ?", [(entry_id,) for entry_id in deleted_ids])
    conn.execute("DELETE FROM entry_category WHERE category_id = 'nsfw_extreme'")
    conn.executemany("DELETE FROM entry WHERE id = ?", [(entry_id,) for entry_id in deleted_ids])
    conn.execute("DELETE FROM category_l1 WHERE id = 'nsfw_extreme'")

    pages = conn.execute("SELECT id, refs_json FROM page WHERE refs_json IS NOT NULL").fetchall()
    for page in pages:
        refs = json.loads(page["refs_json"] or "[]")
        kept = [ref for ref in refs if ref not in deleted_ids]
        if len(kept) != len(refs):
            conn.execute("UPDATE page SET refs_json = ?, updated_at = datetime('now') WHERE id = ?", (json.dumps(kept, ensure_ascii=False), page["id"]))

    conn.commit()
    print("deleted entries:", len(deleted_ids))
    print("deleted category: nsfw_extreme")
    print("removed refs from pages:", sum(1 for page in pages if any(ref in deleted_ids for ref in json.loads(page["refs_json"] or "[]"))))


if __name__ == "__main__":
    main()

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
    rows = conn.execute("SELECT id, category_path_json FROM entry WHERE category_path_text IS NULL").fetchall()
    updates = []
    for row in rows:
        try:
            path = json.loads(row["category_path_json"] or "[]")
        except json.JSONDecodeError:
            path = []
        updates.append((" / ".join(str(part) for part in path), row["id"]))
    conn.executemany("UPDATE entry SET category_path_text = ? WHERE id = ?", updates)
    conn.commit()
    print("backfilled", len(updates))


if __name__ == "__main__":
    main()

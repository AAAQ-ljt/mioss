from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.db import connect, migrate  # noqa: E402
from backend.app.services.classify import classify_entry  # noqa: E402


def main() -> None:
    conn = connect()
    migrate(conn)
    rows = conn.execute(
        """
        SELECT e.id, e.codex_id, e.rating, e.category_path_json, e.tags_positive, e.tags_raw, c.nsfw
        FROM entry e JOIN codex c ON c.id = e.codex_id
        """
    ).fetchall()

    counts = Counter()
    valid_categories = {row["id"] for row in conn.execute("SELECT id FROM category_l1").fetchall()}
    updates = []
    category_rows = []
    for row in rows:
        entry = dict(row)
        domain, primary, labels = classify_entry(entry, row["nsfw"])
        counts[(domain, primary)] += 1
        updates.append((domain, primary, json.dumps(labels, ensure_ascii=False), row["id"]))
        category_rows.extend(
            (row["id"], label, 1 if label == primary else 0)
            for label in labels
            if label in valid_categories
        )

    conn.executemany(
        "UPDATE entry SET domain = ?, cat_primary = ?, cat_labels_json = ? WHERE id = ?",
        updates,
    )
    conn.execute("DELETE FROM entry_category")
    conn.executemany("INSERT OR REPLACE INTO entry_category(entry_id, category_id, is_primary) VALUES (?, ?, ?)", category_rows)
    conn.commit()

    print("domain totals:")
    domains = Counter()
    for (domain, _), count in counts.items():
        domains[domain] += count
    for domain, count in domains.items():
        print(f"  {domain}: {count}")

    print("\ncategory totals:")
    for (domain, primary), count in sorted(counts.items(), key=lambda item: (item[0][0], -item[1])):
        print(f"  {domain:9s} {primary:16s} {count}")

    print("\nmisc samples:")
    for row in conn.execute(
        """
        SELECT e.id, e.title, e.category_path_text, e.tags_positive
        FROM entry e
        WHERE e.cat_primary = 'misc' AND e.domain = 'regular'
        LIMIT 15
        """
    ):
        print(f"  {row['id']} | {row['title']} | {row['category_path_text']} | {(row['tags_positive'] or '')[:90]}")


if __name__ == "__main__":
    main()

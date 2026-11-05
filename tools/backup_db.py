from __future__ import annotations

import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.config import DB_PATH  # noqa: E402

KEEP = 10


def main() -> None:
    if not DB_PATH.exists():
        raise SystemExit(f"database not found: {DB_PATH}")

    backup_dir = DB_PATH.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = backup_dir / f"moss-{stamp}.db"

    source = sqlite3.connect(DB_PATH)
    destination = sqlite3.connect(target)
    try:
        with destination:
            source.backup(destination)
    finally:
        destination.close()
        source.close()

    backups = sorted(backup_dir.glob("moss-*.db"), key=lambda path: path.name, reverse=True)
    for old in backups[KEEP:]:
        old.unlink()
    print(target)


if __name__ == "__main__":
    main()

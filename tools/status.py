from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.db import connect  # noqa: E402
from backend.app.services.comfy import ComfyClient  # noqa: E402


def scalar(conn, sql: str, params: tuple = ()) -> object:
    row = conn.execute(sql, params).fetchone()
    return row[0] if row else None


def main() -> None:
    conn = connect()
    print("release:", scalar(conn, "SELECT value FROM setting WHERE key = 'release'"))
    print("synced_at:", scalar(conn, "SELECT value FROM setting WHERE key = 'synced_at'"))
    print("entries:", scalar(conn, "SELECT COUNT(*) FROM entry"), "usable:", scalar(conn, "SELECT COALESCE(SUM(moss_usable),0) FROM entry"))
    print("projects:", scalar(conn, "SELECT COUNT(*) FROM project"), "pages:", scalar(conn, "SELECT COUNT(*) FROM page"))
    print("jobs:")
    for row in conn.execute("SELECT status, COUNT(*) FROM generation_job GROUP BY status ORDER BY status"):
        print(f"  {row[0]}: {row[1]}")

    client = ComfyClient()
    health = client.health()
    client.close()
    if health["ok"]:
        system = health["data"].get("system", {})
        print("comfyui: online", system.get("comfyui_version"))
    else:
        print("comfyui: offline", health.get("error"))


if __name__ == "__main__":
    main()

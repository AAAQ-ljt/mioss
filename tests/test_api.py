import sqlite3

from fastapi.testclient import TestClient

from backend.app.db import MIGRATIONS_DIR
from backend.app.main import app, get_conn


def make_conn(tmp_path):
    conn = sqlite3.connect(tmp_path / "api-test.db", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        conn.executescript(path.read_text(encoding="utf-8"))
    conn.execute(
        """
        INSERT INTO codex(id, title, nsfw, entry_count, tree_json, synced_at)
        VALUES ('suozhang', '所长', 0, 1, '[]', datetime('now'))
        """
    )
    conn.execute(
        """
        INSERT INTO entry(id, codex_id, title, category_path_json, tags_positive, tags_negative, negative_raw, moss_usable)
        VALUES ('suozhang-1', 'suozhang', '森林', '["各式场景"]', 'forest, fog', '', '', 1)
        """
    )
    conn.execute("INSERT INTO tag_zh(tag, zh, codex_id) VALUES ('forest', '森林', 'suozhang')")
    conn.execute("INSERT OR REPLACE INTO style_preset(id, name, tags) VALUES ('manga-ink', '黑白网点漫画', 'black and white manga')")
    conn.commit()
    return conn


def test_api_project_flow(tmp_path):
    conn = make_conn(tmp_path)
    app.dependency_overrides[get_conn] = lambda: conn
    try:
        with TestClient(app) as client:
            project = client.post("/api/projects", json={"title": "API 测试漫画"}).json()
            page = client.post(
                f"/api/projects/{project['id']}/pages",
                json={"summary": "第一页", "refs": ["suozhang-1"]},
            ).json()

            replaced = client.post(
                f"/api/projects/{project['id']}/storyboard",
                json={"pages": [{"order_no": 1, "summary": "替换页", "refs": ["suozhang-1"]}]},
            ).json()["pages"]
            assert len(replaced) == 1

            composed = client.post(f"/api/pages/{replaced[0]['id']}/compose", json={"save": True}).json()
            assert "forest" in composed["positive"]
            assert "black and white manga" in composed["positive"]

            bad = client.post(
                f"/api/projects/{project['id']}/storyboard",
                json={"pages": [{"refs": ["missing-entry"]}]},
            )
            assert bad.status_code == 400

            search = client.get("/api/codex/search", params={"q": "森林"}).json()
            assert search[0]["id"] == "suozhang-1"

            reordered = client.post(
                f"/api/projects/{project['id']}/reorder",
                json={"page_ids": [replaced[0]["id"]]},
            ).json()["pages"]
            assert reordered[0]["order_no"] == 1

            deleted = client.delete(f"/api/pages/{replaced[0]['id']}")
            assert deleted.status_code == 200
            assert client.get(f"/api/projects/{project['id']}").json()["pages"] == []
            assert client.get("/api/jobs").json() == []
    finally:
        app.dependency_overrides.clear()

import sqlite3

from backend.app.db import MIGRATIONS_DIR
from backend.app.services import projects, studio


def make_conn(tmp_path):
    conn = sqlite3.connect(tmp_path / "studio.db")
    conn.row_factory = sqlite3.Row
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        conn.executescript(path.read_text(encoding="utf-8"))
    conn.execute("INSERT OR REPLACE INTO style_preset(id, name, tags) VALUES ('manga-ink', '黑白', 'black and white manga')")
    return conn


def test_relay_crud(tmp_path):
    conn = make_conn(tmp_path)
    item = studio.add_relay_item(conn, "forest, fog", "sd", "suozhang-1", "森林")
    assert studio.list_relay_items(conn)[0]["id"] == item["id"]
    assert studio.delete_relay_item(conn, item["id"]) is True
    assert studio.list_relay_items(conn) == []


def test_preset_crud(tmp_path):
    conn = make_conn(tmp_path)
    preset = studio.upsert_preset(conn, {"name": "露娜", "kind": "character", "positive": "silver hair"})
    assert studio.list_presets(conn)[0]["name"] == "露娜"
    updated = studio.upsert_preset(conn, {"id": preset["id"], "name": "露娜2", "kind": "character", "positive": "silver hair, amber eyes"})
    assert updated["name"] == "露娜2"
    assert studio.delete_preset(conn, preset["id"]) is True


def test_story_save_and_chapters(tmp_path):
    conn = make_conn(tmp_path)
    project = projects.create_project(conn, "故事测试", style_preset_id="manga-ink")
    story = studio.save_story(conn, project["id"], "雾林", "# 第一章\n内容\n## 场景一\n内容")
    assert story["title"] == "雾林"
    assert [chapter["title"] for chapter in story["chapters"]] == ["第一章", "场景一"]
    assert studio.get_story(conn, project["id"])["chapters"][1]["level"] == 2

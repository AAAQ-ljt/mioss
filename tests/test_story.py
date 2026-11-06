import sqlite3

from backend.app.db import MIGRATIONS_DIR
from backend.app.services import projects, studio


def make_conn(tmp_path):
    conn = sqlite3.connect(tmp_path / "story.db")
    conn.row_factory = sqlite3.Row
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        conn.executescript(path.read_text(encoding="utf-8"))
    conn.execute("INSERT OR REPLACE INTO style_preset(id, name, tags) VALUES ('manga-ink', '黑白', 'black and white manga')")
    return conn


def test_parse_scenes_by_heading_and_separator():
    markdown = "# 第一章\n森林里。\n---\n她回头。\n## 第二章\n城镇。"
    scenes = studio.parse_scenes(markdown)
    assert [scene["chapter_title"] for scene in scenes] == ["第一章", "第一章", "第二章"]
    assert scenes[0]["title"] == "森林里。"
    assert scenes[1]["title"] == "她回头。"


def test_illustration_project_creates_illustration_pages(tmp_path):
    conn = make_conn(tmp_path)
    project = projects.create_project(conn, "配图项目", mode="illustration")
    saved = studio.replace_scenes(conn, project["id"], studio.parse_scenes("# 第一章\n森林。\n---\n城镇。"))
    pages = studio.scenes_to_pages(conn, project["id"], [saved[0]["id"]])
    assert len(pages) == 1
    assert pages[0]["kind"] == "illustration"
    assert pages[0]["scene_id"] == saved[0]["id"]
    assert studio.list_scenes(conn, project["id"])[0]["page_id"] == pages[0]["id"]


def test_scene_create_and_delete(tmp_path):
    conn = make_conn(tmp_path)
    project = projects.create_project(conn, "场景增删", mode="illustration")
    scene = studio.create_scene(conn, project["id"], {"title": "新场景", "summary": "森林"})
    assert studio.list_scenes(conn, project["id"])[0]["title"] == "新场景"
    assert studio.delete_scene(conn, scene["id"]) is True
    assert studio.list_scenes(conn, project["id"]) == []


def test_batch_delete_projects(tmp_path):
    conn = make_conn(tmp_path)
    first = projects.create_project(conn, "项目一", mode="comic")
    second = projects.create_project(conn, "项目二", mode="illustration")
    assert projects.batch_delete_projects(conn, [first["id"], second["id"]]) == 2
    assert projects.list_projects(conn) == []


def test_comic_project_creates_comic_pages(tmp_path):
    conn = make_conn(tmp_path)
    project = projects.create_project(conn, "漫画项目", mode="comic")
    saved = studio.replace_scenes(conn, project["id"], studio.parse_scenes("# 第一章\n森林。"))
    pages = studio.scenes_to_pages(conn, project["id"])
    assert pages[0]["kind"] == "comic"
    assert len(pages) == 1

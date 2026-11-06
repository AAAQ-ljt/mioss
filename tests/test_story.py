import sqlite3

import pytest

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


def test_chapter_files_crud(tmp_path):
    conn = make_conn(tmp_path)
    project = projects.create_project(conn, "章节项目", mode="comic")
    first = studio.create_chapter(conn, project["id"], "第一章")
    second = studio.create_chapter(conn, project["id"], "第二章", "# 第二章\n\n内容")

    path = studio.chapter_dir(project["id"]) / first["file_name"]
    assert path.exists()
    assert "# 第一章" in path.read_text(encoding="utf-8")
    assert [chapter["title"] for chapter in studio.list_chapters(conn, project["id"])] == ["第一章", "第二章"]

    studio.save_chapter(conn, first["id"], "# 第一章\n\n改写后的内容")
    assert path.read_text(encoding="utf-8") == "# 第一章\n\n改写后的内容"
    assert studio.get_chapter(conn, first["id"])["content"] == "# 第一章\n\n改写后的内容"

    second_path = studio.chapter_dir(project["id"]) / second["file_name"]
    assert studio.delete_chapter(conn, second["id"]) is True
    assert not second_path.exists()
    assert [chapter["title"] for chapter in studio.list_chapters(conn, project["id"])] == ["第一章"]


def test_chapter_import_and_reorder(tmp_path):
    conn = make_conn(tmp_path)
    project = projects.create_project(conn, "导入章节", mode="comic")
    created = studio.import_markdown_chapters(conn, project["id"], "前言段落\n# 一\n甲\n## 二\n乙")
    assert [chapter["title"] for chapter in created] == ["前言", "一", "二"]

    reordered = studio.reorder_chapters(
        conn,
        project["id"],
        [created[2]["id"], created[0]["id"], created[1]["id"]],
    )
    assert [chapter["title"] for chapter in reordered] == ["二", "前言", "一"]
    assert [chapter["order_no"] for chapter in reordered] == [1, 2, 3]

    with pytest.raises(ValueError):
        studio.reorder_chapters(conn, project["id"], [created[0]["id"]])


def test_batch_delete_scenes_scoped_to_project(tmp_path):
    conn = make_conn(tmp_path)
    first = projects.create_project(conn, "项目一", mode="comic")
    second = projects.create_project(conn, "项目二", mode="comic")
    first_scene = studio.create_scene(conn, first["id"], {"title": "一"})
    second_scene = studio.create_scene(conn, second["id"], {"title": "二"})

    assert studio.delete_scenes(conn, first["id"], [first_scene["id"], second_scene["id"]]) == 1
    assert studio.list_scenes(conn, first["id"]) == []
    assert [scene["id"] for scene in studio.list_scenes(conn, second["id"])] == [second_scene["id"]]


def test_delete_project_moves_folder_to_trash(tmp_path):
    conn = make_conn(tmp_path)
    project = projects.create_project(conn, "待删作品", mode="comic")
    folder = projects.PROJECTS_DIR / project["id"]
    chapter_file = folder / "chapters" / "chapter.md"
    chapter_file.parent.mkdir(parents=True, exist_ok=True)
    chapter_file.write_text("# 保留稿\n", encoding="utf-8")

    assert projects.delete_project(conn, project["id"]) is True
    assert not folder.exists()
    trashed = list((projects.PROJECTS_DIR / "_trash").glob(f"{project['id']}-*"))
    assert len(trashed) == 1
    assert (trashed[0] / "chapters" / "chapter.md").read_text(encoding="utf-8") == "# 保留稿\n"

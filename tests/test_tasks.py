import sqlite3

from backend.app.db import MIGRATIONS_DIR
from backend.app.services import gallery, projects, prompt, studio, tasks


def make_conn(tmp_path):
    conn = sqlite3.connect(tmp_path / "tasks.db")
    conn.row_factory = sqlite3.Row
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        conn.executescript(path.read_text(encoding="utf-8"))
    conn.execute("INSERT OR REPLACE INTO style_preset(id, name, tags) VALUES ('manga-ink', '黑白', 'black and white manga')")
    conn.execute("INSERT OR REPLACE INTO style_preset(id, name, tags) VALUES ('color', '彩色', 'color anime')")
    return conn


def make_scene(conn, project_id, title="场景一", excerpt=None):
    excerpt = excerpt or "第一段。\n\n第二段。\n\n第三段。\n\n第四段。"
    return studio.create_scene(
        conn,
        project_id,
        {
            "title": title,
            "summary": excerpt[:120],
            "excerpt": excerpt,
            "chapter_title": "第一章",
            "setting": "森林",
            "mood": "紧张",
        },
    )


def test_split_strips_markdown_headings():
    chunks = tasks.split_scene_text("# 第一章\n\n第一段。\n\n第二段。", 2)
    assert all("# 第一章" not in chunk for chunk in chunks)
    assert all(chunk for chunk in chunks)


def test_create_task_splits_scene_and_snapshots_style_and_characters(tmp_path):
    conn = make_conn(tmp_path)
    project = projects.create_project(conn, "任务项目", mode="comic")
    character = projects.upsert_character(conn, project["id"], {"name": "露娜", "anchor_tags": "1girl, silver hair"})
    scene = make_scene(conn, project["id"])

    task = tasks.create_task(
        conn,
        project["id"],
        scene["id"],
        page_count=3,
        style_preset_id="manga-ink",
        character_ids=[character["id"]],
    )
    assert task is not None
    assert task["page_count"] == 3
    assert task["kind"] == "comic"
    assert [page["shot_no"] for page in task["pages"]] == [1, 2, 3]
    assert all(page["task_id"] == task["id"] for page in task["pages"])
    assert all(page["scene_id"] == scene["id"] for page in task["pages"])
    assert task["style_snapshot"]["tags"] == "black and white manga"
    assert task["character_snapshot"][0]["anchor_tags"] == "1girl, silver hair"

    listed = tasks.list_tasks(conn, project["id"])
    assert len(listed) == 1
    assert listed[0]["page_count"] == 3
    assert listed[0]["status"] == "draft"

    page = task["pages"][0]
    result = prompt.compose_for_page(conn, page["id"], save=True)
    assert "black and white manga" in result["positive"]
    assert "silver hair" in result["positive"]

    conn.execute("UPDATE style_preset SET tags = 'color anime' WHERE id = 'manga-ink'")
    conn.execute("UPDATE characters SET anchor_tags = 'red hair' WHERE id = ?", (character["id"],))
    conn.commit()
    extra = tasks.add_task_page(conn, task["id"])
    assert extra is not None
    assert extra["shot_no"] == 4
    result = prompt.compose_for_page(conn, extra["id"], save=True)
    assert "black and white manga" in result["positive"]
    assert "silver hair" in result["positive"]
    assert "color anime" not in result["positive"]
    assert "red hair" not in result["positive"]


def test_illustration_task_is_single_page(tmp_path):
    conn = make_conn(tmp_path)
    project = projects.create_project(conn, "插图任务", mode="illustration")
    scene = make_scene(conn, project["id"])
    task = tasks.create_task(conn, project["id"], scene["id"], page_count=5)
    assert task["page_count"] == 1
    assert task["kind"] == "illustration"
    assert task["pages"][0]["kind"] == "illustration"


def test_resplit_overwrites_old_task_and_moves_images(tmp_path):
    conn = make_conn(tmp_path)
    project = projects.create_project(conn, "覆盖任务", mode="comic")
    scene = make_scene(conn, project["id"])
    first = tasks.create_task(conn, project["id"], scene["id"], page_count=2)
    image_dir = gallery.images_dir(project["id"])
    image = image_dir / "old-page.png"
    image.write_bytes(b"old")
    projects.update_page(conn, first["pages"][0]["id"], {"image_path": str(image), "status": "done"})

    second = tasks.create_task(conn, project["id"], scene["id"], page_count=3)
    assert second["id"] != first["id"]
    assert second["page_count"] == 3
    assert tasks.get_task(conn, first["id"]) is None
    assert not image.exists()
    assert list((projects.PROJECTS_DIR / "_trash_images").glob(f"{project['id']}-*/*"))

    assert tasks.delete_task(conn, second["id"]) is True
    assert tasks.list_tasks(conn, project["id"]) == []
    scene_row = conn.execute("SELECT page_id, status FROM story_scene WHERE id = ?", (scene["id"],)).fetchone()
    assert scene_row["page_id"] is None
    assert scene_row["status"] == "draft"


def test_delete_scene_cascades_task(tmp_path):
    conn = make_conn(tmp_path)
    project = projects.create_project(conn, "级联删除", mode="comic")
    scene = make_scene(conn, project["id"])
    task = tasks.create_task(conn, project["id"], scene["id"], page_count=2)

    assert studio.delete_scene(conn, scene["id"]) is True
    assert tasks.get_task(conn, task["id"]) is None
    assert conn.execute("SELECT COUNT(*) FROM page WHERE project_id = ?", (project["id"],)).fetchone()[0] == 0

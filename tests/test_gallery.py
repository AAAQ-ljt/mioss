import os
import sqlite3

from backend.app.db import MIGRATIONS_DIR
from backend.app.services import gallery, jobs, projects


def make_conn(tmp_path):
    conn = sqlite3.connect(tmp_path / "gallery.db")
    conn.row_factory = sqlite3.Row
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        conn.executescript(path.read_text(encoding="utf-8"))
    conn.execute("INSERT OR REPLACE INTO style_preset(id, name, tags) VALUES ('manga-ink', '黑白', 'black and white manga')")
    return conn


def test_gallery_scans_files_and_maps_pages(tmp_path):
    conn = make_conn(tmp_path)
    project = projects.create_project(conn, "画廊项目", mode="comic")
    images = gallery.images_dir(project["id"])
    first = images / "comfy_0001.png"
    second = images / "comfy_0002.png"
    orphan = images / "variant.png"
    for path, payload in ((first, b"a"), (second, b"bb"), (orphan, b"ccc")):
        path.write_bytes(payload)

    first_page = projects.add_page(conn, project["id"], {"summary": "第一页"})
    second_page = projects.add_page(conn, project["id"], {"summary": "第二页"})
    projects.update_page(conn, first_page["id"], {"image_path": str(first), "status": "done"})
    projects.update_page(conn, second_page["id"], {"image_path": str(second), "status": "done"})

    items = gallery.list_gallery(conn, project["id"], "order")
    assert [item["name"] for item in items] == ["comfy_0001.png", "comfy_0002.png", "variant.png"]
    assert items[0]["page_id"] == first_page["id"]
    assert items[0]["order_no"] == 1
    assert items[0]["url"] == f"/projects/{project['id']}/images/comfy_0001.png"
    assert items[2]["page_id"] is None
    os.utime(orphan, (1000, 1000))
    os.utime(first, (2000, 2000))
    os.utime(second, (3000, 3000))
    by_time = gallery.list_gallery(conn, project["id"], "time")
    assert [item["name"] for item in by_time] == ["comfy_0002.png", "comfy_0001.png", "variant.png"]
    assert gallery.list_gallery(conn, "missing") is None

    info = gallery.download_info(conn, project["id"], "images/comfy_0002.png")
    assert info is not None
    assert info[0] == second
    assert info[1] == "page-002.png"


def test_gallery_delete_moves_files_and_clears_page_image(tmp_path):
    conn = make_conn(tmp_path)
    project = projects.create_project(conn, "删除图片", mode="comic")
    images = gallery.images_dir(project["id"])
    first = images / "comfy_0001.png"
    second = images / "comfy_0002.png"
    orphan = images / "variant.png"
    for path in (first, second, orphan):
        path.write_bytes(b"x")
    page = projects.add_page(conn, project["id"], {"summary": "第一页"})
    projects.update_page(conn, page["id"], {"image_path": str(first), "status": "done"})
    conn.execute(
        """
        INSERT INTO generation_job(id, page_id, prompt, negative, seed, workflow_profile, status, output_path, started_at)
        VALUES ('job-1', ?, 'p', 'n', 1, '{}', 'succeeded', ?, datetime('now'))
        """,
        (page["id"], str(first)),
    )
    conn.commit()

    outside = projects.PROJECTS_DIR / project["id"] / "outside.png"
    outside.write_bytes(b"x")

    deleted = gallery.delete_images(
        conn,
        project["id"],
        ["images/comfy_0001.png", "images/variant.png", "../outside.png", "outside.png"],
    )
    assert sorted(deleted) == ["images/comfy_0001.png", "images/variant.png"]
    assert not first.exists()
    assert not orphan.exists()
    assert second.exists()
    assert outside.exists()

    row = conn.execute("SELECT image_path, status FROM page WHERE id = ?", (page["id"],)).fetchone()
    assert row["image_path"] is None
    assert row["status"] == "draft"
    assert jobs.list_page_variants(conn, page["id"]) == []
    trashed = list((projects.PROJECTS_DIR / "_trash_images").glob(f"{project['id']}-*/*"))
    assert {path.name for path in trashed} == {"comfy_0001.png", "variant.png"}

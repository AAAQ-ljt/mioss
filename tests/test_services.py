import sqlite3

from backend.app.db import MIGRATIONS_DIR
from backend.app.services import codex, projects, prompt


def make_conn(tmp_path):
    conn = sqlite3.connect(tmp_path / "test.db")
    conn.row_factory = sqlite3.Row
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        conn.executescript(path.read_text(encoding="utf-8"))
    conn.execute(
        """
        INSERT INTO codex(id, title, nsfw, entry_count, tree_json, synced_at)
        VALUES ('suozhang', '所长', 0, 2, '[{"name":"各式场景","count":2,"children":[]}]', datetime('now'))
        """
    )
    conn.execute(
        """
        INSERT INTO entry(id, codex_id, title, category_path_json, tags_positive, tags_negative, negative_raw, moss_usable)
        VALUES ('suozhang-1', 'suozhang', '森林', '["各式场景"]', 'forest, fog, dawn', 'curvy', '', 1)
        """
    )
    conn.execute(
        """
        INSERT INTO entry(id, codex_id, title, category_path_json, tags_positive, tags_negative, negative_raw, moss_usable)
        VALUES ('suozhang-2', 'suozhang', '画师组', '["编纂者杂项"]', 'masterpiece, best quality', '', '', 0)
        """
    )
    conn.execute("INSERT INTO tag_zh(tag, zh, codex_id) VALUES ('forest', '森林', 'suozhang')")
    conn.execute(
        """
        INSERT INTO codex(id, title, nsfw, entry_count, tree_json, synced_at)
        VALUES ('suozhang_r18', '所长R18', 1, 1, '[]', datetime('now'))
        """
    )
    conn.execute(
        """
        INSERT INTO entry(id, codex_id, title, category_path_json, tags_positive, tags_negative, negative_raw, moss_usable, rating)
        VALUES ('suozhang_r18-1', 'suozhang_r18', 'R18森林', '["各式场景"]', 'forest, nsfw', '', '', 1, 'r18')
        """
    )
    conn.execute("INSERT OR REPLACE INTO style_preset(id, name, tags) VALUES ('test-style', '测试', 'cinematic anime illustration')")
    conn.commit()
    return conn


def test_search_english_and_chinese(tmp_path):
    conn = make_conn(tmp_path)
    assert codex.search_entries(conn, "forest")[0]["id"] == "suozhang-1"
    assert codex.search_entries(conn, "森林")[0]["id"] == "suozhang-1"
    assert codex.search_entries(conn, "masterpiece") == []
    assert all(item["codex_id"] != "suozhang_r18" for item in codex.search_entries(conn, "forest"))
    assert any(item["codex_id"] == "suozhang_r18" for item in codex.search_entries(conn, "forest", include_nsfw=True))


def test_project_storyboard_gallery(tmp_path):
    conn = make_conn(tmp_path)
    project = projects.create_project(conn, "测试漫画", style_preset_id="test-style")
    pages = projects.replace_pages(conn, project["id"], [
        {"order_no": 1, "summary": "第一页", "refs": ["suozhang-1"]},
        {"order_no": 2, "summary": "第二页", "refs": ["suozhang-2"]},
    ])
    assert len(pages) == 2
    assert pages[0]["refs"] == ["suozhang-1"]
    assert projects.gallery_list(conn, project["id"], "order")[0]["order_no"] == 1

    added = projects.add_page(conn, project["id"], {"summary": "追加页", "refs": ["suozhang-1"]})
    assert added["order_no"] == 3
    assert added["refs"] == ["suozhang-1"]


def test_compose_prompt_skips_unusable_entry(tmp_path):
    conn = make_conn(tmp_path)
    result = prompt.compose_prompt(
        conn,
        style_preset_id="test-style",
        entry_ids=["suozhang-1", "suozhang-2", "missing"],
        page_text="1girl, silver hair",
        negative_text="watermark",
    )
    assert "cinematic anime illustration" in result["positive"]
    assert "forest, fog, dawn" in result["positive"]
    assert "1girl, silver hair" in result["positive"]
    assert "curvy" in result["negative"]
    assert "watermark" in result["negative"]
    assert {"id": "suozhang-2", "reason": "entry_not_moss_usable"} in result["dropped"]
    assert {"id": "missing", "reason": "entry_not_found"} in result["dropped"]


def test_compose_prompt_uses_character_anchor(tmp_path):
    conn = make_conn(tmp_path)
    project = projects.create_project(conn, "角色测试", style_preset_id="test-style")
    character = projects.upsert_character(conn, project["id"], {"name": "露娜", "anchor_tags": "silver hair, amber eyes"})
    result = prompt.compose_prompt(conn, style_preset_id="test-style", character_ids=[character["id"]], project_id=project["id"])
    assert "silver hair, amber eyes" in result["positive"]


def test_compose_prompt_includes_continuity(tmp_path):
    conn = make_conn(tmp_path)
    result = prompt.compose_prompt(
        conn,
        style_preset_id="test-style",
        continuity_text_value=prompt.continuity_text({"location": "魔兽森林", "time": "黎明", "outfit": "破损披风"}),
    )
    assert "地点: 魔兽森林" in result["positive"]
    assert "时间: 黎明" in result["positive"]
    assert "服装: 破损披风" in result["positive"]


def test_compose_prompt_skips_nsfw_by_default(tmp_path):
    conn = make_conn(tmp_path)
    result = prompt.compose_prompt(conn, style_preset_id="test-style", entry_ids=["suozhang_r18-1"])
    assert {"id": "suozhang_r18-1", "reason": "entry_nsfw"} in result["dropped"]
    assert "nsfw" not in result["positive"]
    included = prompt.compose_prompt(conn, style_preset_id="test-style", entry_ids=["suozhang_r18-1"], include_nsfw=True)
    assert "nsfw" in included["positive"]

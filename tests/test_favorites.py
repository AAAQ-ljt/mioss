import sqlite3
import pytest

from backend.app.db import MIGRATIONS_DIR
from backend.app.services import favorites


def make_conn(tmp_path):
    conn = sqlite3.connect(tmp_path / "favorites.db")
    conn.row_factory = sqlite3.Row
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        conn.executescript(path.read_text(encoding="utf-8"))
    conn.execute("INSERT INTO codex(id,title,nsfw,entry_count) VALUES ('suozhang','所长',0,2)")
    conn.execute("INSERT INTO codex(id,title,nsfw,entry_count) VALUES ('artist_nai5','画师',0,1)")
    conn.executemany(
        """
        INSERT INTO entry(id, codex_id, title, tags_raw, tags_positive, tags_negative, negative_raw, domain, cat_primary)
        VALUES (?, ?, ?, ?, ?, '', '', ?, ?)
        """,
        [
            ("suozhang-1", "suozhang", "森林", "forest, fog", "forest, fog", "regular", "scene"),
            ("suozhang-2", "suozhang", "单人", "1girl, nsfw", "1girl, nsfw", "nsfw", "nsfw_single"),
            ("artist-1", "artist_nai5", "画师", "artist:foo", "artist:foo", "reference", "artist_ref"),
        ],
    )
    conn.commit()
    return conn


def test_toggle_and_list_favorites(tmp_path):
    conn = make_conn(tmp_path)
    result = favorites.toggle_favorite(conn, "suozhang-1")
    assert result["favorited"] is True
    assert favorites.favorite_ids(conn) == ["suozhang-1"]
    assert favorites.list_favorites(conn, "regular")[0]["entry_id"] == "suozhang-1"
    assert favorites.list_favorites(conn, "nsfw") == []
    assert favorites.toggle_favorite(conn, "suozhang-1")["favorited"] is False
    assert favorites.favorite_ids(conn) == []


def test_reference_cannot_be_favorited(tmp_path):
    conn = make_conn(tmp_path)
    with pytest.raises(ValueError):
        favorites.toggle_favorite(conn, "artist-1")


def test_compose_favorites_dedupes_and_marks_mixed(tmp_path):
    conn = make_conn(tmp_path)
    favorites.toggle_favorite(conn, "suozhang-1")
    favorites.toggle_favorite(conn, "suozhang-2")
    result = favorites.compose_favorites(conn, ["suozhang-1", "suozhang-2"], "moss")
    assert result["count"] == 2
    assert result["mixed"] is True
    assert "forest" in result["positive"]
    assert "1girl" in result["positive"]
    assert result["missing"] == []
    missing = favorites.compose_favorites(conn, ["missing"], "moss")
    assert missing["missing"] == ["missing"]

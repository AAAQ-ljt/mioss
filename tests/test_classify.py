from backend.app.services.classify import classify_entry


def base_entry(**overrides):
    entry = {
        "codex_id": "suozhang",
        "rating": "safe",
        "category_path_json": '["各式场景","场景","战斗华丽"]',
        "tags_positive": "forest, fog, dynamic pose",
        "tags_raw": "forest, fog, dynamic pose",
    }
    entry.update(overrides)
    return entry


def test_regular_scene_classification():
    domain, primary, labels = classify_entry(base_entry())
    assert domain == "regular"
    assert primary == "scene"
    assert "scene" in labels


def test_reference_codex():
    domain, primary, labels = classify_entry(base_entry(codex_id="artist_nai5_personal"))
    assert domain == "reference"
    assert primary == "artist_ref"


def test_nsfw_rating_and_multi_tags():
    domain, primary, labels = classify_entry(
        base_entry(rating="r18", category_path_json='["各种涩涩"]', tags_positive="2girls, group, yuri")
    )
    assert domain == "nsfw"
    assert primary in {"nsfw_multi", "nsfw_relation"}
    assert primary in labels


def test_nsfw_extreme_path():
    domain, primary, labels = classify_entry(
        base_entry(codex_id="suozhang_r18", rating=None, category_path_json='["r18g/重口"]'),
        codex_nsfw=1,
    )
    assert domain == "nsfw"
    assert primary == "nsfw_extreme"
    assert labels[0] == "nsfw_extreme"


def test_artist_dictionary_never_moss_content():
    domain, primary, _ = classify_entry(base_entry(codex_id="artist_nai45_personal", tags_positive="artist:foo"))
    assert domain == "reference"
    assert primary == "artist_ref"

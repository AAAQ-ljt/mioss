from backend.app.services.sanitize import artist_keys, normalize_tag_list, sanitize_tags

ARTISTS = set()
for name in [
    "hyulla",
    "ie (raarami)",
    "eonsang",
    "momokumo",
    "blue gk",
    "ahemaru",
    "sos adult",
    "mx2j",
    "freng",
    "null (nyanpyoun)",
    "Beeeeen",
    "myabit",
    "misaka 12003-gou",
    "ohisashiburi",
    "channel (caststation)",
    "yoneyama mai",
    "satou kuuki",
]:
    ARTISTS.update(artist_keys(name))


def test_user_example():
    result = sanitize_tags(
        "0.95::hyulla::,0.8::artist:ahemaru::,"
        "-1::curvy,artist collaboration::,-2::multiple views::,"
        "high detail,masterpiece",
        ARTISTS,
    )
    assert result.positive_text == "high detail, masterpiece"
    assert result.negative_text == "curvy, artist collaboration, multiple views"
    assert {item["tag"] for item in result.dropped} == {"hyulla", "artist:ahemaru"}
    assert result.moss_usable is False


def test_braces_underscores_and_dedupe():
    result = sanitize_tags(
        "{{{school uniform}}},[[bad anatomy]],chromatic_aberration,school uniform",
        set(),
    )
    assert result.positive_text == "school uniform, bad anatomy, chromatic aberration"


def test_negative_policy_drop():
    result = sanitize_tags("-1::curvy::,high detail", set(), negative_policy="drop")
    assert result.negative_text == ""
    assert result.positive_text == "high detail"


def test_artist_codex_entry_is_not_moss_usable():
    result = sanitize_tags(
        "0.95::hyulla::,year 2025,masterpiece,best quality",
        ARTISTS,
    )
    assert result.moss_usable is False
    assert result.artist_ratio == 0.25


def test_normalize_tag_list_keeps_parentheses():
    assert normalize_tag_list("poster (object), photo (object)") == "poster (object), photo (object)"


def test_weightless_artist_group_and_year_format():
    result = sanitize_tags("::satou kuuki::,year2024,no text,best quality", ARTISTS)
    assert result.positive_text == "year 2024, no text, best quality"
    assert result.moss_usable is False


def test_punctuation_only_tokens_are_dropped():
    result = sanitize_tags("year 2025 ::, no text, best quality", set())
    assert result.positive_text == "year 2025, no text, best quality"
    assert result.parsed_count == 3


def test_standalone_double_colon_does_not_swallow_later_weights():
    result = sanitize_tags(
        "year 2025 ::, no text, best quality, 0.1::shiny skin::, -5.1::artist collaboration::",
        set(),
    )
    assert result.positive_text == "year 2025, no text, best quality, shiny skin"
    assert result.negative_text == "artist collaboration"

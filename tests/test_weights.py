from backend.app.services.weights import to_sd_weights


def test_braces_and_brackets_convert_to_sd_weights():
    result = to_sd_weights("{{{silver hair}}}, [[bad anatomy]], normal tag")
    assert "silver hair" in result["positive"]
    assert "(silver hair:1.16)" in result["positive"]
    assert "(bad anatomy:0.9)" in result["positive"]


def test_numeric_weights_convert_and_negative_goes_to_negative():
    result = to_sd_weights("1.2::forest::, -1::curvy, low quality::, 0.9::fog::")
    assert "(forest:1.2)" in result["positive"]
    assert "(fog:0.9)" in result["positive"]
    assert "curvy" in result["negative"]
    assert "low quality" in result["negative"]


def test_plain_tags_stay_plain():
    result = to_sd_weights("1girl, solo, smile")
    assert result["positive"] == "1girl, solo, smile"
    assert result["negative"] == ""

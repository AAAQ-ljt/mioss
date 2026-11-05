from backend.app.services.comfy import build_graph


def test_build_graph_text_to_image_uses_empty_latent():
    graph = build_graph("a", "b", 1, {"width": 848, "height": 1488})
    assert graph["22"]["class_type"] == "EmptyLatentImage"
    assert graph["16"]["inputs"]["latent_image"] == ["22", 0]
    assert graph["16"]["inputs"]["denoise"] == 1.0


def test_build_graph_img2img_uses_loaded_latent():
    graph = build_graph("a", "b", 1, {"init_image": "reference.png", "init_denoise": 0.55})
    assert graph["31"]["inputs"]["image"] == "reference.png"
    assert graph["32"]["class_type"] == "VAEEncode"
    assert graph["16"]["inputs"]["latent_image"] == ["32", 0]
    assert graph["16"]["inputs"]["denoise"] == 0.55
    assert "22" not in graph

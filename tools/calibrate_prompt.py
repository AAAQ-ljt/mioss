from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.db import connect  # noqa: E402
from backend.app.services.codex import get_entry  # noqa: E402
from backend.app.services.comfy import ComfyClient, build_graph  # noqa: E402
from backend.app.services.prompt import DEFAULT_NEGATIVE  # noqa: E402

CINEMATIC = (
    "cinematic anime illustration, strong dramatic lighting, high saturation colors, "
    "sharp dynamic composition, film grain texture, lens blur, energetic character pose, "
    "detailed digital painting, movie key visual style"
)
MANGA = "black and white manga, pen line art, screentone, cel shading, clean panel borders, dramatic composition"
SCENE = "1girl, silver hair, amber eyes, standing, forest, fog, dawn"
NATURAL = (
    "生成一张 9:16 竖版日式漫画单页，双色网点黑白漫画风格，赛璐璐硬边阴影，钢笔线稿。"
    "主角是 14 岁少女见习魔法师，银灰色及肩短发、琥珀色眼睛，站在黎明薄雾中的森林边缘，"
    "巨大树木如高墙，斜射光柱穿过雾层，画面大量留白，安静而紧张。"
)


def main() -> None:
    if not ComfyClient().health()["ok"]:
        raise SystemExit("ComfyUI unavailable")

    conn = connect()
    entry = get_entry(conn, "suozhang-5510") or get_entry(conn, "raven_composition-2332")
    if not entry:
        raise SystemExit("calibration needs a synced forest entry")

    variants = {
        "cinematic_anime": f"{CINEMATIC}, {SCENE}",
        "black_white_manga": f"{MANGA}, {SCENE}",
        "codex_entry": f"{CINEMATIC}, {entry['tags_positive']}",
        "natural_language": NATURAL,
    }

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = ROOT / "projects" / "_calibration" / stamp
    out_dir.mkdir(parents=True, exist_ok=True)
    client = ComfyClient()
    for name, prompt in variants.items():
        graph = build_graph(prompt, DEFAULT_NEGATIVE, 12345, {"filename_prefix": f"calibration/{name}"})
        prompt_id = client.queue(graph)["prompt_id"]
        history = client.wait(prompt_id, timeout=900)
        image = client.output_image(history)
        if not image:
            raise RuntimeError(f"no output for {name}")
        path = out_dir / f"{name}.png"
        path.write_bytes(client.download(image))
        print(path)


if __name__ == "__main__":
    main()

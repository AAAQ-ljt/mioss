from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.services.comfy import ComfyClient, build_graph  # noqa: E402
from backend.app.services.prompt import DEFAULT_NEGATIVE  # noqa: E402

PROMPT = (
    "cinematic anime illustration, strong dramatic lighting, high saturation colors, "
    "sharp dynamic composition, film grain texture, lens blur, energetic character pose, "
    "detailed digital painting, movie key visual style, 1girl, silver hair, amber eyes, "
    "standing, forest, fog, dawn, black and white manga, pen line art, screentone"
)


def main() -> None:
    output_dir = ROOT / "projects" / "_smoke"
    output_dir.mkdir(parents=True, exist_ok=True)
    client = ComfyClient()
    health = client.health()
    if not health["ok"]:
        raise SystemExit(f"ComfyUI unavailable: {health.get('error')}")

    graph = build_graph(PROMPT, DEFAULT_NEGATIVE, 12345, {"filename_prefix": "mioss_smoke"})
    prompt_id = client.queue(graph)["prompt_id"]
    history = client.wait(prompt_id, timeout=900)
    image = client.output_image(history)
    if not image:
        raise SystemExit("ComfyUI finished without output image")

    path = output_dir / image["filename"]
    path.write_bytes(client.download(image))
    print(path)


if __name__ == "__main__":
    main()

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.getenv("MOSS_DATA_DIR", ROOT / "data"))
RAW_DIR = DATA_DIR / "raw"
THUMB_DIR = DATA_DIR / "thumbs"
DB_PATH = Path(os.getenv("MOSS_DB_PATH", DATA_DIR / "moss.db"))
PROJECTS_DIR = Path(os.getenv("MOSS_PROJECTS_DIR", ROOT / "projects"))
FRONTEND_DIST = Path(os.getenv("MOSS_FRONTEND_DIST", ROOT / "frontend" / "dist"))
COMFY_URL = os.getenv("MOSS_COMFY_URL", "http://127.0.0.1:8188")
API_BASE = os.getenv("MOSS_API_BASE", "http://127.0.0.1:8780")
DATA_SOURCE_URL = os.getenv("MOSS_DATA_SOURCE_URL", "https://novelai.quicktagcloud.com/data/")
IMAGE_CDN_URL = os.getenv("MOSS_IMAGE_CDN_URL", "https://assets.quicktagcloud.com/images/")


def ensure_dirs() -> None:
    for path in (DATA_DIR, RAW_DIR, THUMB_DIR, PROJECTS_DIR):
        path.mkdir(parents=True, exist_ok=True)

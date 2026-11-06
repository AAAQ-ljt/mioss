import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from backend.app import config
from backend.app.services import projects, studio


@pytest.fixture(autouse=True, scope="session")
def isolate_project_dirs(tmp_path_factory):
    root = tmp_path_factory.mktemp("projects")
    config.PROJECTS_DIR = root
    projects.PROJECTS_DIR = root
    studio.PROJECTS_DIR = root
    yield root

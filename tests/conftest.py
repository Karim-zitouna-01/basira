"""Isole les tests : données dans un dossier temporaire, API en mode mock, pas de LLM (C) ; jeu jouet de B."""

import os
import tempfile

os.environ["BASIRA_DATA_DIR"] = tempfile.mkdtemp(prefix="basira_test_")
os.environ["BASIRA_MODE"] = "mock"
os.environ["LLM_BASE_URL"] = ""

import pytest  # noqa: E402

from signaux.demo import create_demo  # noqa: E402
from signaux.io import load_tables  # noqa: E402


@pytest.fixture(scope="session")
def sample_dir(tmp_path_factory):
    path = tmp_path_factory.mktemp("sample") / "data"
    create_demo(path, 80)
    return path


@pytest.fixture
def tables(sample_dir):
    return load_tables(sample_dir)[0]

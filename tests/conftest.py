"""Isole les tests : données dans un dossier temporaire, API en mode mock, pas de LLM."""

import os
import tempfile

os.environ["BASIRA_DATA_DIR"] = tempfile.mkdtemp(prefix="basira_test_")
os.environ["BASIRA_MODE"] = "mock"
os.environ["LLM_BASE_URL"] = ""

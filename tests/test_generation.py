"""Tests for the synthetic data generator (run with `uv run pytest`)."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd
import pytest

from generation import config as cfg
from generation.checks import run_checks
from generation.population import KEY_LETTERS, mf, mf_display
from generation.run import generate


def _digest(root: Path) -> dict[str, str]:
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.rglob("*.csv"))}


@pytest.fixture(scope="module")
def sample(tmp_path_factory) -> Path:
    out = tmp_path_factory.mktemp("sample")
    generate(200, cfg.SEED, out)
    return out


def test_mf_format():
    assert mf(1000001, "B") == "1000001BAM000"
    assert mf_display("1000001BAM000") == "1000001/B/A/M/000"
    assert len(KEY_LETTERS) == 23 and not {"I", "O", "U"} & set(KEY_LETTERS)


def test_sample_passes_all_checks(sample):
    assert run_checks(sample)


def test_heroes_present_with_contract_identity(sample):
    c = pd.read_csv(sample / "raw" / "contribuables.csv", dtype={"code_nat": str})
    c = c.set_index("mf")
    for h in cfg.HEROES:
        assert c.loc[h.mf, "raison_sociale"] == h.raison_sociale
        assert c.loc[h.mf, "code_nat"] == h.code_nat
        assert int(c.loc[h.mf, "gouvernorat_code"]) == h.gouvernorat
    assert c.loc[cfg.KAPPA[0], "raison_sociale"] == cfg.KAPPA[1]


def test_ground_truth_not_leaked_into_register(sample):
    c = pd.read_csv(sample / "raw" / "contribuables.csv")
    assert not {"scenario", "role", "intensite", "groupe"} & set(c.columns)


def test_same_seed_same_bytes(sample, tmp_path):
    generate(200, cfg.SEED, tmp_path)
    assert _digest(sample) == _digest(tmp_path)


def test_other_seed_other_world(sample, tmp_path):
    generate(200, cfg.SEED + 1, tmp_path)
    a = pd.read_csv(sample / "raw" / "contribuables.csv")
    b = pd.read_csv(tmp_path / "raw" / "contribuables.csv")
    assert set(a["raison_sociale"]) != set(b["raison_sociale"])
    # the heroes are fixed whatever the seed
    assert set(h.mf for h in cfg.HEROES) <= set(b["mf"])


def test_explorer_builds_offline(sample, tmp_path):
    from generation.visualisation import build_payload, render

    payload = build_payload(sample)
    assert cfg.ALPHA_MF in payload["nodes"] and cfg.ALPHA_SUPPLIER in payload["nodes"]
    assert len(payload["edges"]) > 0 and len(payload["months"]) == 24
    html = render(payload)
    assert "vis.Network" in html and "cdn." not in html  # library embedded, no network needed

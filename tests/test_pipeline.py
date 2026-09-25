import json

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from pandas.testing import assert_frame_equal

from signaux.catalogue import CODES
from signaux.checks import hero_report
from signaux.demo import HEROES
from signaux.engine import Engine
from signaux.io import InputError, load_tables
from signaux.peers import build_groups
from signaux.run import run
from signaux.statistics import available_exercise, ewma_z, normalize_z, robust_distances


def calculate(tables, month="2026-08"):
    return Engine(tables).calculate(pd.Period(month, "M"))


def test_full_contract_outputs_and_heroes(sample_dir, tmp_path):
    out = tmp_path / "signaux"
    report = run(sample_dir, out)
    signals = pd.read_parquet(out / "signaux.parquet")
    assert len(signals) == 80 * 24 * 16
    assert set(signals.code_signal) == set(CODES)
    assert not signals.duplicated(["mf", "mois", "code_signal"]).any()
    assert np.isfinite(signals[["valeur_brute", "valeur_norm"]]).all().all()
    assert signals.valeur_norm.between(0, 1).all()
    assert signals.preuves.map(len).max() <= 50
    assert signals.loc[signals.valeur_norm < 0.5, "fait_fr"].eq("").all()
    schema = pq.read_schema(out / "signaux.parquet")
    assert schema.field("preuves").type == pa.list_(pa.string())
    assert schema.field("sources").type == pa.list_(pa.string())
    assert len(pd.read_parquet(out / "enjeux.parquet")) == 80 * 24
    assert report["problemes_preuves"] == []
    _, failures = hero_report(tmp_path)
    assert failures == []


def test_future_filing_and_customs_cannot_change_past(tables):
    before = calculate(tables, "2026-02")
    monthly = tables["declarations_mensuelles"]
    columns = [
        "ca_total_declare",
        "tva_collectee",
        "tva_deductible_import",
        "tva_deductible_biens_services_local",
    ]
    monthly.loc[monthly.date_depot > "2026-02-28", columns] *= 1000
    headers = tables["douane_declarations"]
    future_numbers = headers.loc[headers.date_enregistrement > "2026-02-28", "num_declaration"]
    articles = tables["douane_articles"]
    articles.loc[articles.num_declaration.isin(future_numbers), "valeur_caf_tnd"] *= 1000
    after = calculate(tables, "2026-02")
    for left, right in zip(before[:3], after[:3]):
        assert_frame_equal(left, right)


def test_annex_five_release_in_march(tables):
    before = calculate(tables, "2026-02")[0]
    a5 = tables["employeur_annexe5"]
    a5.loc[a5.exercice.eq(2025), "montant_ttc"] *= 2
    after = calculate(tables, "2026-02")[0]
    assert_frame_equal(before, after)
    march = calculate(tables, "2026-03")[0]
    omega = march.loc[march.mf.eq(HEROES[7]) & march.code_signal.eq("COH_CLIENTS_VS_CA")].iloc[0]
    assert omega.valeur_brute == pytest.approx(5_000_000 / (12000 * 1.19))
    assert available_exercise(pd.Period("2026-02", "M")) == 2024
    assert available_exercise(pd.Period("2026-03", "M")) == 2025


def test_missing_current_and_future_filings_not_zero_turnover(tables):
    frame = tables["declarations_mensuelles"]
    mask = frame.mf.eq(HEROES[6]) & frame.mois.eq("2026-07")
    frame.loc[mask, "date_depot"] = pd.Timestamp("2026-12-01")
    signals = calculate(tables)[0]
    row = signals.loc[signals.mf.eq(HEROES[6]) & signals.code_signal.eq("CHG_CA")].iloc[0]
    assert row.valeur_norm == 0
    frame.loc[mask, "ca_total_declare"] = 10**12
    changed = calculate(tables)[0]
    assert_frame_equal(signals, changed)


def test_legitimate_growth_and_vat_payment_lag(tables):
    signals = calculate(tables)[0]
    zeta = signals.loc[signals.mf.eq(HEROES[5])].set_index("code_signal")
    assert (zeta.loc[zeta.index.str.startswith("COH_"), "valeur_norm"] < 0.5).all()
    assert zeta.loc["CHG_IMPORTS", "valeur_norm"] >= 0.5
    assert zeta.loc["COH_TVA_IMPORT", "valeur_brute"] == pytest.approx(1, abs=1e-6)


def test_evidence_resolves_is_bounded_and_sorted(tables):
    signals = calculate(tables)[0]
    amount = {}
    for name, key, field in (
        ("douane_articles", "id_article", "valeur_caf_tnd"),
        ("employeur_annexe5", "id_ligne", "montant_ttc"),
        ("adeb_paiements", "num_ordonnance", "montant_ht"),
        ("employeur_annexe2", "id_ligne", "montant_brut"),
    ):
        amount.update({f"{name}:{row[key]}": row[field] for row in tables[name].to_dict("records")})
    for row in tables["declarations_mensuelles"].itertuples():
        amount[f"declarations_mensuelles:{row.mf}:{row.mois}"] = row.ca_total_declare
    for row in tables["douane_liquidation"].itertuples():
        amount[f"douane_liquidation:{row.id_article}:105"] = row.montant_tnd
    for row in signals.loc[signals.valeur_norm >= 0.5].itertuples():
        assert row.preuves
        assert all(ref in amount for ref in row.preuves)
        if row.code_signal != "CHG_DEPOTS":
            values = [amount[ref] for ref in row.preuves]
            assert values == sorted(values, reverse=True)


def test_statistics_and_singular_groups():
    assert np.array_equal(normalize_z([1, 2.5, 4]), [0, 0.5, 1])
    constant = np.ones((10, 4))
    distance, _, _ = robust_distances(constant)
    assert np.isfinite(distance).all()
    assert (distance == 0).all()
    series = np.full((2, 15), 100.0)
    series[0, -1] = 500
    series[1, -1] = np.nan
    result = ewma_z(series)
    assert result[0] > 4
    assert result[1] == 0


def test_peer_fallback():
    frame = pd.DataFrame(
        {
            "code_nat": ["46.69"] * 35 + ["47.11"] * 5,
            "section_nat": ["G"] * 40,
            "effectif_declare": [1] * 20 + [25] * 20,
        },
        index=[str(i) for i in range(40)],
    )
    groups = build_groups(frame)
    assert set(groups.iloc[:35].groupe) == {"46"}
    assert set(groups.iloc[35:].groupe) == {"SECTION|G"}


def test_exposure_contract_identities(tables):
    _, exposure, _, _, _ = calculate(tables)
    assert np.allclose(
        exposure.base_omise_12m,
        np.maximum(exposure.ca_observe_12m - exposure.ca_declare_12m, 0),
        atol=0.002,
    )
    assert exposure.confiance.between(0, 1).all()
    assert (exposure.enjeu_bas <= exposure.enjeu_estime).all()
    assert (exposure.enjeu_estime <= exposure.enjeu_haut).all()
    assert np.isfinite(exposure.select_dtypes("number")).all().all()


def test_ground_truth_is_never_opened(sample_dir, tmp_path, monkeypatch):
    from pathlib import Path

    original = Path.open

    def guarded(path, *args, **kwargs):
        assert path.name != "verite_terrain.csv"
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded)
    run(sample_dir, tmp_path, start="2026-08", end="2026-08")
    report = json.loads((tmp_path / "rapport_execution.json").read_text())
    assert all("verite_terrain" not in name for name in report["entrees_sha256"])


def test_duplicates_rejected(sample_dir, tmp_path):
    import shutil

    shutil.copytree(sample_dir, tmp_path / "data")
    path = tmp_path / "data/raw/contribuables.csv"
    frame = pd.read_csv(path)
    pd.concat([frame, frame.iloc[:1]]).to_csv(path, index=False)
    with pytest.raises(InputError, match="dupliquée"):
        load_tables(tmp_path / "data")


def test_missing_reference_source_preserves_other_customs_signals(sample_dir, tmp_path):
    import shutil

    shutil.copytree(sample_dir, tmp_path / "data")
    (tmp_path / "data/raw/ref_ndp.csv").unlink()
    tables, warnings = load_tables(tmp_path / "data", allow_missing=True)
    assert warnings
    signals = calculate(tables)[0]
    alpha = signals.loc[signals.mf.eq(HEROES[0])].set_index("code_signal")
    assert alpha.loc["CHG_IMPORTS", "valeur_norm"] >= 0.5
    assert (signals.loc[signals.code_signal.eq("COH_VALEUR_REF"), "valeur_norm"] == 0).all()


def test_fallback_members_include_fine_group_companies():
    from signaux.peers import peer_members

    companies = pd.DataFrame(
        {
            "code_nat": ["46.69"] * 40,
            "section_nat": ["G"] * 40,
            "effectif_declare": [1] * 35 + [25] * 5,
        },
        index=range(40),
    )
    groups = build_groups(companies)
    assert groups.iloc[0].groupe == "46|0-2"
    assert groups.iloc[-1].groupe == "46"
    assert groups.iloc[-1].nb_pairs == 40
    assert peer_members(companies, "46").sum() == 40


def test_proximity_evidence_respects_notification_date(tables):
    tables["historique_controles"] = pd.DataFrame(
        [
            {
                "id_controle": "CTL-TEST",
                "mf": HEROES[7],
                "date_notification_resultats": pd.Timestamp("2026-07-15"),
                "categorie_resultat": "FRAUDE_SIGNIFICATIVE",
            }
        ]
    )
    graph = tables["metriques_noeuds"]
    client = tables["contribuables"].iloc[8].mf
    graph.loc[graph.mf.eq(client) & graph.mois.eq("2026-08"), "distance_entite_redressee"] = 1
    signals, _, _, _, issues = calculate(tables)
    row = signals.loc[
        signals.mf.eq(client) & signals.code_signal.eq("RES_PROXIMITE_REDRESSE")
    ].iloc[0]
    assert "historique_controles:CTL-TEST" in row.preuves
    assert row.valeur_norm == 1
    assert not issues
    tables["historique_controles"]["date_notification_resultats"] = pd.Timestamp("2026-09-15")
    _, _, _, _, issues = calculate(tables)
    assert any(item["code_signal"] == "RES_PROXIMITE_REDRESSE" for item in issues)


def test_capped_evidence_uses_all_rows_for_calculation(tables):
    original = (
        tables["douane_articles"]
        .loc[tables["douane_articles"].num_declaration.eq("2026/301/0000108")]
        .iloc[0]
    )
    copies = []
    for i in range(70):
        row = original.copy()
        row["id_article"] = f"2026/301/0000108-{i + 2:03d}"
        row["valeur_caf_tnd"] = 100_000 + i
        copies.append(row)
    tables["douane_articles"] = pd.concat(
        [tables["douane_articles"], pd.DataFrame(copies)], ignore_index=True
    )
    signals, _, _, audit, _ = calculate(tables)
    beta = signals.loc[signals.mf.eq(HEROES[1]) & signals.code_signal.eq("COH_VALEUR_REF")].iloc[0]
    assert beta.valeur_brute == pytest.approx(0.5)
    assert len(beta.preuves) == 50
    assert "100 069,000 DT" in beta.fait_fr
    entry = next(
        row for row in audit if row["mf"] == HEROES[1] and row["code_signal"] == "COH_VALEUR_REF"
    )
    assert entry["nb_preuves_disponibles"] > 50


def test_final_note_does_not_invent_missing_evaluation(tmp_path):
    from signaux.report import PROJECT, generate_report

    with pytest.raises(ValueError, match="Version finale impossible"):
        generate_report(
            tmp_path, tmp_path / "note.pdf", PROJECT / "docs/team_stack.json", final=True
        )


def test_financial_formula_and_confidence_numerically():
    from signaux.exposure import estimate_exposure

    def a(value):
        return np.array([value], dtype=float)

    frame = estimate_exposure(
        ["X"],
        "2026-08",
        declared=a(100_000),
        imports=a(100_000),
        clients_ttc=a(142_800),
        annual_ttc=a(119_000),
        annual_ht=a(100_000),
        annual_complete=np.array([True]),
        public_ht=a(10_000),
        import_vat=a(20_000),
        customs_vat=a(15_000),
        local_vat=a(1000),
        shell_share=a(0.3),
        peer_margin=a(0.2),
        history_count=a(24),
        source_count=a(4),
    ).iloc[0]
    assert frame.ca_observe_12m == 130_000
    assert frame.base_omise_12m == 30_000
    assert frame.tva_surdeduite_12m == 5300
    assert frame.enjeu_estime == 30_000 * (0.19 + 0.2 * 0.2) + 5300
    assert frame.confiance == pytest.approx((1 + 1 + (1 - 10000 / 130000)) / 3)

"""Propriétés du score (contrat §5.1) sur un petit jeu synthétique."""

import numpy as np
import pandas as pd

from scoring import config, score, train


def _X(lignes: dict[tuple, dict]) -> pd.DataFrame:
    idx = pd.MultiIndex.from_tuples(list(lignes), names=["mf", "mois"])
    X = pd.DataFrame(0.0, index=idx, columns=config.FEATURES)
    for k, v in lignes.items():
        for c, x in v.items():
            X.loc[k, c] = x
    for code, (a, b, _) in config.COMBINAISONS.items():
        X[code] = X[a] * X[b]
    return X


MODELE = {"intercept": float(np.log(0.05 / 0.95)), "poids": {f: 1.0 for f in config.FEATURES}}
MODELE["poids"].update({"COH_IMPORT_VS_CA": 3.0, "CHG_IMPORTS": 2.0})


def test_points_somment_a_score_moins_base():
    X = _X({("A", "2026-08"): {"COH_IMPORT_VS_CA": 1.0, "CHG_IMPORTS": 0.5}, ("B", "2026-08"): {}})
    r = score.calculer(X, MODELE)
    pts = r[[c for c in r if c.startswith("pts_")]].sum(axis=1)
    assert np.allclose(pts, r["score_sans_bonus"] - r["score_base"])
    assert r.loc[("B", "2026-08"), "score"] == r.loc[("B", "2026-08"), "score_base"]
    assert abs(r["score_base"].iloc[0] - 5.0) < 1e-9


def test_bonus_nouveau_schema():
    m = {"intercept": MODELE["intercept"], "poids": {f: 1.0 for f in config.FEATURES}}
    m["poids"].update({"COH_VALEUR_REF": 0.0, "CHG_NOUVELLES_CATEGORIES": 0.1})
    X = _X({("A", "2026-08"): {"COH_VALEUR_REF": 0.9, "CHG_NOUVELLES_CATEGORIES": 1.0}, ("B", "2026-08"): {"COH_VALEUR_REF": 0.9}})
    r = score.calculer(X, m)
    assert r.loc[("A", "2026-08"), "bonus_nouveau_schema"] == min(15, 5 * 2 * 0.95)
    assert r.loc[("B", "2026-08"), "bonus_nouveau_schema"] == 0


def test_actions():
    assert score._action("PRIORITAIRE", 150_000, 0.1) == "VERIFICATION"
    assert score._action("PRIORITAIRE", 50_000, 0.1) == "DEMANDE_INFO"
    assert score._action("SURVEILLANCE", 50_000, 0.6) == "SIGNALEMENT_DOUANE"
    assert score._action("SURVEILLANCE", 50_000, 0.2) == "RELANCE"
    assert score._action("CONFIANCE", 0, 0) == "AUCUNE"


def test_poids_positifs_et_calibrage():
    rng = np.random.default_rng(0)
    n = 300
    mois = [config.MOIS[1 + i % 20] for i in range(n)]
    X = pd.DataFrame(rng.random((n, len(config.FEATURES))) * (rng.random((n, len(config.FEATURES))) < 0.2),
                     index=pd.MultiIndex.from_arrays([[f"M{i}" for i in range(n)], mois], names=["mf", "mois"]), columns=config.FEATURES)
    risque = 3 * X["COH_IMPORT_VS_CA"] - 2 * X["CHG_CA"]  # CHG_CA anti-corrélé → doit être retiré
    y = rng.random(n) < 1 / (1 + np.exp(-(risque - 0.5)))
    cat = np.where(y, np.where(rng.random(n) < 0.3, "FRAUDE_SIGNIFICATIVE", "REDRESSEMENT_MINEUR"), "CONFORME")
    ctl = pd.DataFrame({"mf": [f"M{i}" for i in range(n)], "date_avis": [f"{config.MOIS[2 + i % 20]}-15" for i in range(n)],
                        "categorie_resultat": cat})
    m = train.entrainer(X, ctl)
    assert all(w >= 0 for w in m["poids"].values())
    assert m["poids"]["CHG_CA"] == 0 and "CHG_CA" in [e["code_signal"] for e in m["signaux_exclus"]]
    assert m["poids"]["COH_IMPORT_VS_CA"] == max(m["poids"].values())
    assert abs(100 / (1 + np.exp(-m["intercept"])) - train.ANCRE_BASE) < 1e-6

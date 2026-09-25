"""Matrice des caractéristiques : valeur_norm des 16 signaux de B + les 2 combinaisons (contrat §3)."""

import numpy as np
import pandas as pd

from . import config


def matrice(sig: pd.DataFrame) -> pd.DataFrame:
    """Format long de B → large : index (mf, mois), colonnes config.FEATURES, valeurs ∈ [0, 1] (manquant = 0)."""
    X = sig.pivot_table(index=["mf", "mois"], columns="code_signal", values="valeur_norm", aggfunc="max")
    X = X.reindex(columns=list(config.SIGNAUX_B)).fillna(0.0).clip(0.0, 1.0)
    for code, (a, b, _) in config.COMBINAISONS.items():
        X[code] = X[a] * X[b]
    return X[config.FEATURES].astype(np.float64)


def lignes_combinaisons(X: pd.DataFrame) -> pd.DataFrame:
    """Lignes au format long de B pour les CMB_* (pour l'affichage : fait_fr si actif, preuves = celles des 2 signaux)."""
    out = []
    for code, (a, b, fait) in config.COMBINAISONS.items():
        v = X[code]
        d = v.reset_index()
        d.columns = ["mf", "mois", "valeur_norm"]
        d["code_signal"] = code
        d["lentille"] = "COMBINAISON"
        d["valeur_brute"] = d["valeur_norm"]
        d["unite"] = "x"
        d["fait_fr"] = np.where(d["valeur_norm"] >= config.SEUIL_ACTIF, fait, "")
        d["composantes"] = [[a, b]] * len(d)
        out.append(d)
    return pd.concat(out, ignore_index=True)

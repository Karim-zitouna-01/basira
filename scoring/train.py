"""Apprentissage du poids de chaque signal à partir des contrôles passés (historique_controles).

Cible : 1 si REDRESSEMENT_MINEUR ou FRAUDE_SIGNIFICATIVE (poids d'échantillon 2), 0 si CONFORME.
Caractéristiques : valeur_norm des signaux au mois précédant date_avis (pas de fuite du futur).
Contrainte : poids ≥ 0 (un signal d'alerte ne fait jamais baisser le risque) → on retire les signaux
à coefficient négatif et on réentraîne, jusqu'à ce que tous les poids restants soient ≥ 0.
Signal sans poids appris (jamais observé, ou coefficient négatif) : poids a priori = médiane des poids positifs appris.
Les contrôles passés, choisis par une règle type SAR, n'ont jamais regardé certains schémas et ont sur-sélectionné
d'autres signaux (souvent sans redressement) : un coefficient négatif y traduit ce biais de sélection, pas une baisse
du risque. Absence de preuve ≠ absence de risque.
Calibrage : échelle fixée par capacité (voir `calibrer`), poids relatifs inchangés.
`verite_terrain` n'est jamais lu ici.
"""

import json
from datetime import date

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

from . import config

POSITIFS = {"REDRESSEMENT_MINEUR", "FRAUDE_SIGNIFICATIVE"}
ANCRE_BASE = 5.0      # score d'une entreprise sans aucun signal
ANCRE_CAPACITE = 70.0  # score atteint par le quantile CAPACITE des couples entreprise × mois (= seuil PRIORITAIRE)
CAPACITE = 0.01        # ~1 % du portefeuille : ordre de grandeur de la capacité de contrôle mensuelle
CATEGORIES = POSITIFS | {"CONFORME"}


def jeu_entrainement(X: pd.DataFrame, controles: pd.DataFrame, extra: pd.DataFrame | None = None) -> pd.DataFrame:
    """Une ligne par contrôle : caractéristiques au mois précédant l'avis, cible et poids.
    `extra` (optionnel) : exemples supplémentaires (mf, mois_caracteristiques, y, poids), ex. décisions des inspecteurs."""
    c = controles[controles["categorie_resultat"].isin(CATEGORIES)].copy()
    c["mois_caracteristiques"] = c["date_avis"].str[:7].map(config.mois_precedent)
    c["y"] = c["categorie_resultat"].isin(POSITIFS).astype(int)
    c["poids"] = np.where(c["categorie_resultat"] == "FRAUDE_SIGNIFICATIVE", 2.0, 1.0)
    c = c[["mf", "mois_caracteristiques", "y", "poids"]]
    if extra is not None and len(extra):
        c = pd.concat([c, extra[["mf", "mois_caracteristiques", "y", "poids"]]], ignore_index=True)
    idx = pd.MultiIndex.from_frame(c[["mf", "mois_caracteristiques"]])
    feats = X.reindex(idx)
    garde = feats.notna().all(axis=1).to_numpy()
    out = pd.concat([c.reset_index(drop=True), feats.reset_index(drop=True)], axis=1)[garde]
    return out.reset_index(drop=True)


def ajuster(jeu: pd.DataFrame, X: pd.DataFrame, C: float = 1.0) -> dict:
    actifs = list(config.FEATURES)
    exclus: list[dict] = []
    y, w = jeu["y"].to_numpy(), jeu["poids"].to_numpy()
    if len(np.unique(y)) < 2:
        raise ValueError("le jeu d'entraînement ne contient qu'une seule classe")
    while True:
        # un signal jamais présent dans les exemples ne peut pas être appris : poids 0
        vides = [f for f in actifs if jeu[f].max() <= 0]
        for f in vides:
            exclus.append({"code_signal": f, "raison": "jamais observé dans les contrôles passés"})
        actifs = [f for f in actifs if f not in vides]
        m = LogisticRegression(C=C, class_weight="balanced", max_iter=5000, random_state=config.SEED)
        m.fit(jeu[actifs].to_numpy(), y, sample_weight=w)
        coefs = dict(zip(actifs, m.coef_[0]))
        negatifs = [f for f, v in coefs.items() if v < 0]
        if not negatifs:
            break
        for f in negatifs:
            exclus.append({"code_signal": f, "raison": f"coefficient négatif ({coefs[f]:.3f}) : retiré puis réentraînement"})
        actifs = [f for f in actifs if f not in negatifs]
    appris = np.array([coefs.get(f, 0.0) for f in config.FEATURES])
    positifs = appris[appris > 0]
    a_priori = float(np.median(positifs)) if len(positifs) else 1.0
    sans_poids = {e["code_signal"] for e in exclus}
    for e in exclus:
        e["raison"] += f" ; poids a priori {a_priori:.3f} (médiane des poids appris)"
    appris = np.array([a_priori if f in sans_poids else v for f, v in zip(config.FEATURES, appris)])
    calib = calibrer(X, appris)
    poids = {f: round(float(v * calib["facteur_echelle"]), 6) for f, v in zip(config.FEATURES, appris)}
    return {
        "intercept": round(calib["intercept"], 6),
        "poids": poids,
        "date_entrainement": date.today().isoformat(),
        "nb_exemples": int(len(jeu)),
        "nb_positifs": int(jeu["y"].sum()),
        "definition_cible": "REDRESSEMENT_MINEUR ou FRAUDE_SIGNIFICATIVE (poids 2)",
        "methode": "Régression logistique L2 (scikit-learn), class_weight équilibré, poids contraints ≥ 0 (retrait itératif), "
                   "poids a priori (médiane des poids appris) pour les signaux jamais observés ou à coefficient négatif "
                   "(biais de sélection des contrôles passés), puis calibrage de l'échelle par la capacité "
                   "(1 % des couples entreprise × mois ≥ 70) ; plancher 70 si une preuve de cohérence est forte (score.py)",
        "signaux_exclus": exclus,
        "calibrage": {**calib, "intercept_appris": round(float(m.intercept_[0]), 6),
                      "poids_appris": {f: round(float(v), 6) for f, v in zip(config.FEATURES, appris)}},
    }


def _logit(p: float) -> float:
    return float(np.log(p / (1 - p)))


def calibrer(X: pd.DataFrame, w: np.ndarray, base: float = ANCRE_BASE, capacite: float = CAPACITE,
             ancre: float = ANCRE_CAPACITE) -> dict:
    """Le taux de petits redressements (~1/3 des entreprises normales) place l'intercept appris vers 35/100 : aucune
    entreprise ne pourrait être CONFIANCE. Une ancre sur les fraudes confirmées ne tient pas non plus : les 15 fraudes
    significatives avaient des signaux faibles au moment de l'avis, l'échelle explose (×10) et 30 % du portefeuille
    passe PRIORITAIRE. On garde les poids relatifs appris (donc le classement et les explications) et on fixe
    l'échelle par la capacité de contrôle, sans aucune étiquette :
      - entreprise sans aucun signal → score `base` (5) ;
      - quantile 1 − `capacite` des gains sur tous les couples entreprise × mois → score `ancre` (70, seuil PRIORITAIRE).
    """
    gain = X[config.FEATURES].to_numpy() @ w
    ref = float(np.quantile(gain, 1 - capacite))
    if ref <= 1e-6:
        ref = float(gain.max()) if gain.max() > 0 else 1.0
    b0 = _logit(base / 100)
    k = (_logit(ancre / 100) - b0) / ref
    return {"intercept": b0, "facteur_echelle": round(k, 6), "ancre_base": base, "ancre_capacite": ancre,
            "capacite": capacite, "gain_quantile_capacite": round(ref, 6)}


def entrainer(X: pd.DataFrame, controles: pd.DataFrame, extra: pd.DataFrame | None = None) -> dict:
    return ajuster(jeu_entrainement(X, controles, extra), X)


def ecrire(modele: dict) -> None:
    config.SCORES.mkdir(parents=True, exist_ok=True)
    (config.SCORES / "modele.json").write_text(json.dumps(modele, ensure_ascii=False, indent=2), encoding="utf-8")


def lire() -> dict:
    return json.loads((config.SCORES / "modele.json").read_text(encoding="utf-8"))

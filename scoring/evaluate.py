"""Évaluation : Basira vs règle statique type SAR vs sélection aléatoire (GET /api/evaluation).

C'est le SEUL module qui lit verite_terrain.csv, et seulement pour mesurer : jamais pour entraîner ni régler un seuil.
Période de test : 12 derniers mois ; chaque mois, chaque méthode choisit N = 50 entreprises à contrôler.
Une entreprise compte comme fraude au mois m si son scénario ∉ {AUCUN, CROISSANCE_LEGITIME, CITOYEN_MODELE}
et m ≥ mois_debut_scenario.
"""

import json

import numpy as np
import pandas as pd

from . import config


def classe_taille(effectif) -> int:
    e = 0 if pd.isna(effectif) else int(effectif)
    return 0 if e <= 2 else 1 if e <= 9 else 2 if e <= 49 else 3


def score_sar(X: pd.DataFrame, contribuables: pd.DataFrame) -> pd.Series:
    """Règle statique : poids égaux sur 5 signaux « classiques » + bonus de taille (reproduit le biais actuel)."""
    base = X[list(config.SIGNAUX_SAR)].mean(axis=1)
    taille = contribuables.set_index("mf")["effectif_declare"].map(classe_taille)
    bonus = config.BONUS_TAILLE_SAR * X.index.get_level_values("mf").map(taille).fillna(0).to_numpy()
    return base + bonus


def _selections(scores: pd.DataFrame, sar: pd.Series, mois: str, n: int) -> dict[str, list[str]]:
    s = scores[scores["mois"] == mois]
    basira = s.sort_values("rang_priorite")["mf"].head(n).tolist()
    sm = sar.xs(mois, level="mois").sort_values(ascending=False, kind="stable")
    return {"Basira": basira, "Règle statique (type SAR)": sm.head(n).index.tolist()}


def evaluer(scores: pd.DataFrame, X: pd.DataFrame, contribuables: pd.DataFrame, vt: pd.DataFrame,
            n: int = config.TOP_N) -> dict:
    rng = np.random.default_rng(config.SEED)
    vt = vt.set_index("mf")
    fraude = ~vt["scenario"].isin(config.SCENARIOS_NON_FRAUDE)
    debut = vt["mois_debut_scenario"].fillna("9999-99")
    montant = vt["montant_fraude_reel"].fillna(0.0)
    legit = vt["scenario"] == "CROISSANCE_LEGITIME"
    sar = score_sar(X, contribuables)

    def est_fraude(mfs, mois):
        mfs = [m for m in mfs if m in vt.index]
        return np.array([bool(fraude[m] and debut[m] <= mois) for m in mfs]), mfs

    noms = ["Basira", "Règle statique (type SAR)", "Sélection aléatoire"]
    acc = {k: {"det": [], "mnt": [], "legit": []} for k in noms}
    premier_top: dict[str, dict[str, str]] = {k: {} for k in noms[:2]}

    # premiers mois de détection sur toute la fenêtre (les scénarios démarrent à partir de 2025-03)
    for mois in config.MOIS:
        sel = _selections(scores, sar, mois, n)
        for k, mfs in sel.items():
            for m in mfs:
                if m in vt.index and fraude[m] and debut[m] <= mois:
                    premier_top[k].setdefault(m, mois)
        if mois not in config.MOIS_TEST:
            continue
        for k, mfs in sel.items():
            f, mfs_ok = est_fraude(mfs, mois)
            acc[k]["det"].append(f.sum() / n)
            acc[k]["mnt"].append(sum(montant[m] for m, x in zip(mfs_ok, f) if x) / n)
            acc[k]["legit"].append(int(sum(legit.get(m, False) for m in mfs)))
        univers = scores.loc[scores["mois"] == mois, "mf"].to_numpy()
        det, mnt, lg = [], [], []
        for _ in range(config.NB_TIRAGES_ALEATOIRES):
            mfs = rng.choice(univers, size=min(n, len(univers)), replace=False).tolist()
            f, mfs_ok = est_fraude(mfs, mois)
            det.append(f.sum() / n)
            mnt.append(sum(montant[m] for m, x in zip(mfs_ok, f) if x) / n)
            lg.append(sum(legit.get(m, False) for m in mfs))
        acc["Sélection aléatoire"]["det"].append(np.mean(det))
        acc["Sélection aléatoire"]["mnt"].append(np.mean(mnt))
        acc["Sélection aléatoire"]["legit"].append(np.mean(lg))

    delai = {k: {m: config.ecart_mois(debut[m], mo) for m, mo in premier_top[k].items()} for k in premier_top}
    communs = sorted(set(delai["Basira"]) & set(delai["Règle statique (type SAR)"]))
    avance = float(np.mean([delai["Règle statique (type SAR)"][m] - delai["Basira"][m] for m in communs])) if communs else None
    nb_fraudes = int(sum(1 for m in vt.index if fraude[m] and debut[m] <= config.MOIS[-1]))

    methodes, details = [], {}
    for k in noms:
        a = acc[k]
        methodes.append({
            "nom": k,
            "taux_detection_top_n": round(float(np.mean(a["det"])), 3),
            "montant_moyen_par_controle": round(float(np.mean(a["mnt"])), 3),
            "fausses_alertes_croissance_legitime": round(float(np.mean(a["legit"])), 1),
            "avance_detection_mois": (round(avance, 1) if avance is not None else None) if k == "Basira"
            else (0.0 if k.startswith("Règle") else None),
        })
        if k in delai:
            d = delai[k]
            details[k] = {"entreprises_frauduleuses_detectees": len(d), "sur": nb_fraudes,
                          "delai_moyen_detection_mois": round(float(np.mean(list(d.values()))), 1) if d else None}
    return {
        "top_n": n,
        "periode_test": f"{config.MOIS_TEST[0]} → {config.MOIS_TEST[-1]}",
        "methodes": methodes,
        "note": "Chiffres calculés sur données synthétiques ; vérité terrain cachée au modèle.",
        "details": {
            **details,
            "avance_calculee_sur": len(communs),
            "definition": "Moyennes mensuelles sur la période de test ; fausses alertes = entreprises à croissance légitime "
                          "dans le top N (moyenne par mois) ; avance = délai de la règle statique − délai de Basira, "
                          "sur les fraudes détectées par les deux méthodes.",
        },
    }


def _detection_top_n(priorite: pd.Series, vt: pd.DataFrame, n: int) -> float:
    """Part moyenne de fraudes actives dans le top n de `priorite` (index mf × mois), sur la période de test."""
    fraude = ~vt["scenario"].isin(config.SCENARIOS_NON_FRAUDE)
    debut = vt["mois_debut_scenario"].fillna("9999-99")
    taux = []
    for mois in config.MOIS_TEST:
        top = priorite.xs(mois, level="mois").sort_values(ascending=False, kind="stable").head(n).index
        taux.append(np.mean([bool(fraude.get(m, False) and debut.get(m, "9999-99") <= mois) for m in top]))
    return round(float(np.mean(taux)), 3)


def valider(X: pd.DataFrame, controles: pd.DataFrame, scores: pd.DataFrame, vt: pd.DataFrame,
            n: int = config.TOP_N) -> dict:
    """Robustesse de l'apprentissage : les poids appris apportent-ils plus que des poids égaux, et le résultat tient-il
    avec un modèle entraîné sans aucun contrôle de la période de test ?"""
    from sklearn.metrics import roc_auc_score
    from sklearn.model_selection import StratifiedKFold

    from . import score, train

    F = config.FEATURES
    jeu = train.jeu_entrainement(X, controles)
    auc_appris, auc_egaux = [], []
    for a, b in StratifiedKFold(5, shuffle=True, random_state=config.SEED).split(jeu, jeu["y"]):
        m = train.ajuster(jeu.iloc[a].reset_index(drop=True), X)
        t = jeu.iloc[b]
        auc_appris.append(roc_auc_score(t["y"], t[F].to_numpy() @ np.array([m["poids"][f] for f in F]), sample_weight=t["poids"]))
        auc_egaux.append(roc_auc_score(t["y"], t[F].sum(axis=1), sample_weight=t["poids"]))

    vt = vt.set_index("mf")
    enjeu = scores.set_index(["mf", "mois"])["enjeu_estime"].reindex(X.index).fillna(0.0)
    avant = jeu[jeu["mois_caracteristiques"] < config.MOIS_TEST[0]].reset_index(drop=True)
    hors_periode = score.calculer(X, train.ajuster(avant, X))["score"] / 100 * enjeu
    c = train.calibrer(X, np.ones(len(F)))
    egaux = score.calculer(X, {"intercept": c["intercept"], "poids": {f: c["facteur_echelle"] for f in F}})["score"] / 100 * enjeu

    dernier = scores[scores["mois"] == config.MOIS_COURANT].set_index("mf")
    fraude = ~vt["scenario"].isin(config.SCENARIOS_NON_FRAUDE)
    debut = vt["mois_debut_scenario"].fillna("9999-99")
    active = pd.Series([bool(fraude.get(m, False) and debut.get(m, "9999-99") <= config.MOIS_COURANT) for m in dernier.index],
                       index=dernier.index)
    prio = dernier["segment"] == "PRIORITAIRE"
    par_scenario = (pd.DataFrame({"scenario": vt["scenario"].reindex(dernier.index), "prio": prio})
                    .groupby("scenario")["prio"].agg(["size", "mean"]))
    return {
        "auc_validation_croisee_poids_appris": round(float(np.mean(auc_appris)), 3),
        "auc_validation_croisee_poids_egaux": round(float(np.mean(auc_egaux)), 3),
        "nb_controles": int(len(jeu)),
        "detection_top_n_modele_sans_controles_periode_test": _detection_top_n(hors_periode, vt, n),
        "nb_controles_avant_periode_test": int(len(avant)),
        "detection_top_n_poids_egaux": _detection_top_n(egaux, vt, n),
        "prioritaires_mois_courant": int(prio.sum()),
        "precision_prioritaires_mois_courant": round(float(active[prio].mean()), 3) if prio.any() else None,
        "part_prioritaire_par_scenario": {k: {"nb": int(r["size"]), "part": round(float(r["mean"]), 3)}
                                          for k, r in par_scenario.iterrows()},
        "definition": "AUC : contrôles passés, validation croisée à 5 plis (0,5 = hasard). Détection : même définition que "
                      "le top N principal (priorité = score × enjeu). Précision : part de fraudes actives parmi les PRIORITAIRE.",
    }


def ecrire(ev: dict) -> None:
    config.SCORES.mkdir(parents=True, exist_ok=True)
    (config.SCORES / "evaluation.json").write_text(json.dumps(ev, ensure_ascii=False, indent=2), encoding="utf-8")

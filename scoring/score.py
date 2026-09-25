"""Score explicable par entreprise × mois (contrat §5.1).

score_sans_bonus = 100·σ(b0 + Σ w_i x_i) ; score_base = 100·σ(b0)
points_i = (w_i x_i / Σ w_j x_j) × (score_sans_bonus − score_base)   → la somme des points = score − score_base
bonus « nouveau schéma » (0–15) : ≥ 2 signaux très forts (valeur_norm ≥ 0.8) dont le poids appris est sous la médiane
des poids positifs → bonus = min(15, 5 × n × moyenne de leurs valeur_norm), affiché comme contribution NOUVEAU_SCHEMA.
plancher « preuve forte » : si un signal COH_* atteint valeur_norm ≥ 0.8, score_sans_bonus ≥ 70 (seuil PRIORITAIRE) ;
les points ajoutés sont attribués à ce signal.
"""

import numpy as np
import pandas as pd

from . import config

SEUIL_FORT = 0.8


def _sigmoide(z):
    return 1.0 / (1.0 + np.exp(-z))


def calculer(X: pd.DataFrame, modele: dict) -> pd.DataFrame:
    """Scores bruts et points par signal (tableau large, une ligne par mf × mois)."""
    W = np.array([modele["poids"].get(f, 0.0) for f in config.FEATURES])
    b0 = modele["intercept"]
    Xv = X.to_numpy()
    lin = Xv * W
    S = lin.sum(axis=1)
    s_sans = 100 * _sigmoide(b0 + S)
    s_base = 100 * _sigmoide(b0)
    with np.errstate(invalid="ignore", divide="ignore"):
        pts = np.where(S[:, None] > 0, lin / S[:, None], 0.0) * (s_sans - s_base)[:, None]

    # plancher « preuve forte » : un écart entre sources (COH_*) très marqué suffit à rendre l'entreprise prioritaire ;
    # les points ajoutés vont au signal de cohérence le plus fort (la somme des points reste = score − score_base)
    idx_coh = np.array([config.FEATURES.index(c) for c in config.SIGNAUX_PREUVE])
    j_coh = idx_coh[Xv[:, idx_coh].argmax(axis=1)]
    lignes = np.arange(len(Xv))
    forte = Xv[lignes, j_coh] >= config.SEUIL_PREUVE
    plancher = np.where(forte, np.maximum(s_sans, config.SEUILS["PRIORITAIRE"]) - s_sans, 0.0)
    pts[lignes, j_coh] += plancher
    s_sans = s_sans + plancher

    positifs = W[W > 0]
    mediane = np.median(positifs) if len(positifs) else 0.0
    qual = (Xv >= SEUIL_FORT) & (W < mediane)[None, :]
    n = qual.sum(axis=1)
    moy = np.where(n > 0, np.where(qual, Xv, 0).sum(axis=1) / np.maximum(n, 1), 0.0)
    bonus = np.where(n >= 2, np.minimum(config.BONUS_MAX, 5.0 * n * moy), 0.0)

    out = pd.DataFrame(index=X.index)
    out["score_sans_bonus"] = s_sans
    out["score_base"] = s_base
    out["bonus_nouveau_schema"] = bonus
    out["score"] = np.minimum(100.0, s_sans + bonus)
    for j, f in enumerate(config.FEATURES):
        out[f"pts_{f}"] = pts[:, j]
    # signal actif (hors combinaisons) pour la règle CONFIANCE
    out["signal_actif"] = (X[list(config.SIGNAUX_B)].to_numpy() >= config.SEUIL_ACTIF).any(axis=1)
    return out


def _segments(df: pd.DataFrame, contribuables: pd.DataFrame, controles: pd.DataFrame) -> pd.Series:
    s = config.SEUILS
    seg = np.where(df["score"] >= s["PRIORITAIRE"], "PRIORITAIRE", np.where(df["score"] >= s["SURVEILLANCE"], "SURVEILLANCE", "NORMAL"))

    # aucun signal actif sur 12 mois (mois courant inclus)
    d = df[["mf", "mois", "signal_actif"]].sort_values(["mf", "mois"])
    actif_12m = d.groupby("mf")["signal_actif"].transform(lambda x: x.astype(int).rolling(12, min_periods=1).max()).astype(bool)
    actif_12m = actif_12m.reindex(df.index)

    # ≥ 24 mois d'historique
    debut = df["mf"].map(contribuables.set_index("mf")["date_debut_activite"].str[:7]) if len(contribuables) else pd.Series("", index=df.index)
    historique = np.array([config.ecart_mois(a, m) >= 24 if isinstance(a, str) and a else False for a, m in zip(debut, df["mois"])])

    # aucun redressement passé (résultat notifié avant la fin du mois)
    red = controles[controles["categorie_resultat"].isin(["REDRESSEMENT_MINEUR", "FRAUDE_SIGNIFICATIVE"])] if len(controles) else controles
    premier = red.assign(m=red["date_notification_resultats"].fillna(red["date_avis"]).str[:7]).groupby("mf")["m"].min() if len(red) else pd.Series(dtype=str)
    m_red = df["mf"].map(premier)
    deja_redresse = m_red.notna() & (m_red.fillna("9999-99") <= df["mois"])

    confiance = (df["score"] < s["CONFIANCE"]) & ~actif_12m & historique & ~deja_redresse
    return pd.Series(np.where((seg == "NORMAL") & confiance, "CONFIANCE", seg), index=df.index)


def _action(segment: str, enjeu: float, part_douane: float) -> str:
    if segment in ("PRIORITAIRE", "SURVEILLANCE") and part_douane > 0.5:
        return "SIGNALEMENT_DOUANE"
    if segment == "PRIORITAIRE":
        return "VERIFICATION" if enjeu >= config.ENJEU_VERIFICATION else "DEMANDE_INFO"
    if segment == "SURVEILLANCE":
        return "RELANCE"
    return "AUCUNE"


def scorer(X: pd.DataFrame, modele: dict, sig: pd.DataFrame, enjeux: pd.DataFrame,
           contribuables: pd.DataFrame, controles: pd.DataFrame) -> pd.DataFrame:
    brut = calculer(X, modele).reset_index()
    e = enjeux.set_index(["mf", "mois"])["enjeu_estime"] if len(enjeux) else pd.Series(dtype=float)
    brut["enjeu_estime"] = pd.MultiIndex.from_frame(brut[["mf", "mois"]]).map(lambda k: e.get(k, 0.0)) if len(e) else 0.0
    brut["enjeu_estime"] = brut["enjeu_estime"].fillna(0.0).astype(float)
    brut["segment"] = _segments(brut, contribuables, controles)
    brut["priorite"] = brut["score"] / 100 * brut["enjeu_estime"]
    brut = brut.sort_values(["mois", "priorite", "score"], ascending=[True, False, False])
    brut["rang_priorite"] = brut.groupby("mois").cumcount() + 1

    faits = {(m, mo, c): f for m, mo, c, f in sig.loc[sig["fait_fr"].fillna("") != "", ["mf", "mois", "code_signal", "fait_fr"]].itertuples(index=False)}
    cols_pts = [f"pts_{f}" for f in config.FEATURES]
    P = brut[cols_pts].to_numpy()
    X_al = X.reindex(pd.MultiIndex.from_frame(brut[["mf", "mois"]])).to_numpy()
    idx_douane = [config.FEATURES.index(c) for c in config.SIGNAUX_DOUANE]

    contributions, actions, resumes = [], [], []
    for i, (mf, mois, seg, enjeu, bonus) in enumerate(brut[["mf", "mois", "segment", "enjeu_estime", "bonus_nouveau_schema"]].itertuples(index=False)):
        p = P[i]
        ordre = np.argsort(-p)
        lst = [{"code_signal": config.FEATURES[j], "points": round(float(p[j]), 1)} for j in ordre if p[j] >= 0.05]
        if bonus > 0:
            lst.append({"code_signal": config.NOUVEAU_SCHEMA, "points": round(float(bonus), 1)})
            lst.sort(key=lambda c: -c["points"])
        contributions.append(lst)
        total = p[p > 0].sum()
        part = p[idx_douane].clip(min=0).sum() / total if total > 0 else 0.0
        actions.append(_action(seg, enjeu, part))
        textes = []
        for j in ordre[:4]:
            code = config.FEATURES[j]
            if p[j] <= 0:
                break
            f = faits.get((mf, mois, code))
            if f is None and code in config.COMBINAISONS and X_al[i, j] >= config.SEUIL_ACTIF:
                f = config.COMBINAISONS[code][2]
            if f:
                textes.append(f.strip())
            if len(textes) == 2:
                break
        if seg == "CONFIANCE":
            r = "Aucun signal actif depuis 12 mois, aucun redressement passé : candidat à la facilitation."
        elif textes:
            r = " ".join(t if t.endswith(".") else t + "." for t in textes)
            if enjeu > 0:
                r += f" Enjeu estimé : {config.fmt_dt(enjeu)}."
        else:
            r = "Aucun signal actif ce mois-ci."
        resumes.append(r)

    brut["contributions"] = contributions
    brut["action_suggeree"] = actions
    brut["resume_fr"] = resumes
    cols = ["mf", "mois", "score", "score_base", "contributions", "bonus_nouveau_schema", "segment", "priorite",
            "rang_priorite", "action_suggeree", "resume_fr", "enjeu_estime", "score_sans_bonus"]
    out = brut[cols].sort_values(["mf", "mois"]).reset_index(drop=True)
    for c in ("score", "score_base", "bonus_nouveau_schema", "score_sans_bonus"):
        out[c] = out[c].round(1)
    out["priorite"] = out["priorite"].round(3)
    return out


def ecrire(scores: pd.DataFrame) -> None:
    config.SCORES.mkdir(parents=True, exist_ok=True)
    scores.to_parquet(config.SCORES / "scores.parquet", index=False)

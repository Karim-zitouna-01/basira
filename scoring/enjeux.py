"""Enjeu complété par C : deux mécanismes de fraude que l'estimation de B (§4.2) ne chiffre pas.

B chiffre le CA omis quand les sources tierces (clients, acheteurs publics, imports × marge) dépassent le CA
déclaré, et la TVA sur-déduite. Deux cas y échappent :

1. Sous-évaluation en douane (scénario C) : les droits éludés ne sont pas dans le CA.
   Articles des 12 derniers mois dont le prix unitaire est < 80 % du prix de référence (hors bruit ±15 %) :
   écart de valeur = (prix de référence − prix déclaré) × quantité ;
   droits éludés = écart × (DD + FODEC) + écart × (1 + DD + FODEC) × TVA  (taux de ref_ndp).
2. Ventes cachées révélées par la croissance des imports (scénario A) : les imports augmentent plus vite que le CA,
   mais leur niveau reste sous le CA déclaré, donc B ne voit rien. Seulement si l'écart de croissance ≥ 50 points.
   Imports excédentaires (6 derniers mois déclarés) = imports récents − imports précédents × (CA récent / CA précédent) ;
   ventes cachées = excédent / (1 − marge brute du secteur) ; enjeu = ventes × (19 % TVA + marge × 20 % IS), comme B.

enjeu = max(enjeu B, douane + imports) ; fourchette ±40 % pour la part de C. Hypothèses de prototype, pas un redressement.
"""

import numpy as np
import pandas as pd

from . import config
from .io import lire_csv

SEUIL_SOUS_EVALUATION = 0.8
ECART_MIN_POINTS = 50.0  # écart de croissance imports − CA (6 mois) en dessous duquel on ne chiffre rien (bruit)
LARGEUR_C = 0.4


def _periode(mois: str) -> pd.Period:
    return pd.Period(mois, freq="M")


def calculer(enjeux_b: pd.DataFrame) -> pd.DataFrame:
    contrib = lire_csv("contribuables.csv")
    ids = contrib["mf"].tolist()
    nat = lire_csv("ref_nat.csv")
    marge = contrib["code_nat"].map(dict(zip(nat["code_nat"], nat["marge_brute_reference"]))).fillna(0.25).to_numpy(float)

    art = lire_csv("douane_articles.csv")
    dec = lire_csv("douane_declarations.csv")[["num_declaration", "mf_importateur", "date_enregistrement"]]
    art = art.merge(dec, on="num_declaration")
    art["mois"] = art["date_enregistrement"].str[:7]
    ndp = lire_csv("ref_ndp.csv").set_index("code_ndp")
    art = art.join(ndp[["prix_reference_tnd", "taux_dd", "taux_tva", "taux_fodec"]], on="code_ndp")

    # droits éludés par article sous-évalué
    ratio = art["prix_unitaire_tnd"] / art["prix_reference_tnd"]
    sous = art[(art["prix_reference_tnd"] > 0) & (ratio < SEUIL_SOUS_EVALUATION)].copy()
    ecart = (sous["prix_reference_tnd"] - sous["prix_unitaire_tnd"]) * sous["quantite"]
    ddf = (sous["taux_dd"].fillna(0) + sous["taux_fodec"].fillna(0)) / 100
    sous["elude"] = ecart * ddf + ecart * (1 + ddf) * sous["taux_tva"].fillna(0) / 100

    mois_tous = [str(p) for p in pd.period_range("2023-09", config.MOIS[-1], freq="M")]  # historique complet de A

    def pivot(frame, cle, col):
        p = frame.pivot_table(index=cle, columns="mois", values=col, aggfunc="sum")
        return p.reindex(index=ids, columns=mois_tous).fillna(0.0).to_numpy(float)

    imports = pivot(art, "mf_importateur", "valeur_caf_tnd")
    elude = pivot(sous, "mf_importateur", "elude")
    decl = lire_csv("declarations_mensuelles.csv")
    decl = decl[decl["statut_depot"] == "DEPOSEE"]
    col = {m: i for i, m in enumerate(mois_tous)}

    def fenetre(mat, fin: pd.Period, largeur: int):
        idx = [col[str(fin - k)] for k in range(largeur) if str(fin - k) in col]
        return mat[:, idx].sum(axis=1)

    lignes = []
    for mois in config.MOIS:
        p = _periode(mois)
        fiscal = p - 1  # dernier mois dont la déclaration est connue (comme B)
        vus = decl[(decl["date_depot"] <= f"{mois}-31") & (decl["mois"] <= str(fiscal))]
        ca = pivot(vus, "mf", "ca_total_declare")
        imp_r, imp_p = fenetre(imports, fiscal, 6), fenetre(imports, fiscal - 6, 6)
        ca_r, ca_p = fenetre(ca, fiscal, 6), fenetre(ca, fiscal - 6, 6)
        ok = (imp_p > 0) & (ca_p > 0)
        croissance_ca = np.divide(ca_r, ca_p, out=np.zeros_like(ca_r), where=ca_p > 0)
        croissance_imp = np.divide(imp_r, imp_p, out=np.zeros_like(imp_r), where=imp_p > 0)
        ok &= (croissance_imp - croissance_ca) * 100 >= ECART_MIN_POINTS  # hors bruit : écart de croissance marqué
        excedent = np.where(ok, imp_r - imp_p * croissance_ca, 0.0)
        ventes = np.maximum(excedent, 0.0) / (1 - marge)
        enjeu_imports = ventes * (0.19 + marge * 0.20)
        enjeu_douane = fenetre(elude, p, 12)
        lignes.append(pd.DataFrame({"mf": ids, "mois": mois, "enjeu_douane_c": enjeu_douane, "enjeu_imports_c": enjeu_imports}))
    c = pd.concat(lignes, ignore_index=True)

    b = enjeux_b[["mf", "mois", "enjeu_estime", "enjeu_bas", "enjeu_haut", "confiance"]].rename(
        columns={"enjeu_estime": "enjeu_b", "enjeu_bas": "bas_b", "enjeu_haut": "haut_b"})
    out = b.merge(c, on=["mf", "mois"], how="left").fillna({"enjeu_douane_c": 0.0, "enjeu_imports_c": 0.0})
    part_c = out["enjeu_douane_c"] + out["enjeu_imports_c"]
    prend_c = part_c > out["enjeu_b"]
    out["enjeu_estime"] = np.where(prend_c, part_c, out["enjeu_b"])
    out["enjeu_bas"] = np.where(prend_c, part_c * (1 - LARGEUR_C), out["bas_b"])
    out["enjeu_haut"] = np.where(prend_c, part_c * (1 + LARGEUR_C), out["haut_b"])
    out["source_enjeu"] = np.where(prend_c, "C", "B")
    cols = ["mf", "mois", "enjeu_estime", "enjeu_bas", "enjeu_haut", "confiance", "source_enjeu", "enjeu_b",
            "enjeu_douane_c", "enjeu_imports_c"]
    out = out[cols]
    argent = ["enjeu_estime", "enjeu_bas", "enjeu_haut", "enjeu_b", "enjeu_douane_c", "enjeu_imports_c"]
    out[argent] = out[argent].round(3)
    return out


def ecrire(enjeux: pd.DataFrame) -> None:
    config.SCORES.mkdir(parents=True, exist_ok=True)
    enjeux.to_parquet(config.SCORES / "enjeux.parquet", index=False)

"""Données de développement de C, au format exact des livrables de A (data/raw, data/graphe) et de B (data/signaux).

Elles servent uniquement à construire et tester le scoring, l'évaluation et l'API réelle avant les livraisons
de A et B. Elles sont écrites dans data/dev/ et ne se mélangent jamais aux données de l'équipe.

Usage : uv run python -m scoring.dev_fixtures [nb_entreprises]
        BASIRA_DATA_DIR=data/dev uv run python -m scoring.run
"""

import sys

import numpy as np
import pandas as pd

from . import config

DEV = config.ROOT / "data" / "dev"
rng = np.random.default_rng(config.SEED)
MOIS = config.MOIS
T = len(MOIS)
CODES = list(config.SIGNAUX_B)
K = {c: i for i, c in enumerate(CODES)}

NAT = {  # code_nat → (libelle, section, marge de référence, part importatrice)
    "46.69": ("Commerce de gros d'autres machines et équipements", "G", 0.31, 0.8),
    "46.43": ("Commerce de gros d'appareils électroménagers", "G", 0.31, 0.8),
    "46.46": ("Commerce de gros de produits pharmaceutiques", "G", 0.31, 0.7),
    "46.90": ("Commerce de gros non spécialisé", "G", 0.31, 0.6),
    "47.11": ("Commerce de détail en magasin non spécialisé", "G", 0.33, 0.2),
    "42.11": ("Construction de routes et autoroutes", "F", 0.15, 0.1),
    "41.20": ("Construction de bâtiments", "F", 0.15, 0.1),
    "14.13": ("Fabrication d'autres vêtements de dessus", "C", 0.57, 0.6),
    "10.71": ("Fabrication de pain et de pâtisserie fraîche", "C", 0.23, 0.1),
    "25.11": ("Fabrication de structures métalliques", "C", 0.12, 0.5),
    "22.22": ("Fabrication d'emballages en matières plastiques", "C", 0.2, 0.6),
    "49.41": ("Transports routiers de fret", "H", 0.2, 0.1),
    "62.01": ("Programmation informatique", "J", 0.33, 0.1),
    "56.10": ("Restauration traditionnelle", "I", 0.32, 0.0),
}
NAT_POIDS = np.array([6, 3, 2, 5, 8, 3, 7, 4, 4, 3, 3, 5, 3, 3], dtype=float)
GOUV_POIDS = {11: 18, 12: 7.3, 13: 7, 14: 3, 15: 7.4, 17: 4.4, 31: 7.7, 32: 5.2, 33: 2.5, 34: 10, 41: 2.5, 51: 2, 52: 4.2, 61: 1.5}

SIGNATURES = {  # scénario → {signal: force}
    "A": {"COH_IMPORT_VS_CA": 1.0, "CHG_IMPORTS": 0.9, "CHG_NOUVEAUX_FOURNISSEURS": 0.7, "COH_CLIENTS_VS_CA": 0.3},
    "B": {"CHG_TVA_DEDUCTIBLE": 0.9, "RES_COQUILLE": 0.95, "RES_FOURNISSEUR_PARTAGE": 0.6},
    "COQUILLE": {"COH_CLIENTS_VS_CA": 1.0, "PAI_MAHALANOBIS": 0.8, "RES_FOURNISSEUR_PARTAGE": 0.6},
    "C": {"COH_VALEUR_REF": 1.0, "PAI_MAHALANOBIS": 0.6, "CHG_NOUVELLES_CATEGORIES": 0.4},
    "D": {"COH_ADEB_VS_CA": 1.0, "PAI_MARGE": 0.45},
    "E": {"CHG_DEPOTS": 1.0, "CHG_IMPORTS": 1.0, "COH_IMPORT_VS_CA": 0.75, "CHG_NOUVELLES_CATEGORIES": 0.7},
    "F": {"PAI_MARGE": 0.9, "PAI_MAHALANOBIS": 0.75},
    "CROISSANCE_LEGITIME": {"CHG_IMPORTS": 0.9, "CHG_CA": 0.8, "CHG_NOUVEAUX_FOURNISSEURS": 0.5, "CHG_TVA_DEDUCTIBLE": 0.5},
}
PART_SCENARIO = {"A": 0.016, "C": 0.01, "D": 0.006, "E": 0.005, "F": 0.01, "CROISSANCE_LEGITIME": 0.02, "CITOYEN_MODELE": 0.08}

SOURCES = {
    "COH_IMPORT_VS_CA": ["douane", "dgi_declarations"], "COH_CLIENTS_VS_CA": ["dgi_annexe5", "dgi_declarations"],
    "COH_ADEB_VS_CA": ["adeb", "dgi_declarations"], "COH_TVA_IMPORT": ["douane", "dgi_declarations"], "COH_VALEUR_REF": ["douane"],
    "CHG_CA": ["dgi_declarations"], "CHG_IMPORTS": ["douane"], "CHG_TVA_DEDUCTIBLE": ["dgi_declarations"],
    "CHG_NOUVEAUX_FOURNISSEURS": ["douane", "dgi_annexe5"], "CHG_NOUVELLES_CATEGORIES": ["douane"], "CHG_DEPOTS": ["dgi_declarations"],
    "PAI_MARGE": ["dgi_declarations", "douane"], "PAI_MAHALANOBIS": ["dgi_declarations", "douane"],
    "RES_FOURNISSEUR_PARTAGE": ["graphe", "douane"], "RES_COQUILLE": ["graphe", "dgi_annexe5"], "RES_PROXIMITE_REDRESSE": ["graphe"],
}
UNITES = {"COH_IMPORT_VS_CA": "pts", "COH_CLIENTS_VS_CA": "x", "COH_ADEB_VS_CA": "x", "COH_TVA_IMPORT": "x", "COH_VALEUR_REF": "x",
          "CHG_CA": "z", "CHG_IMPORTS": "z", "CHG_TVA_DEDUCTIBLE": "z", "CHG_NOUVEAUX_FOURNISSEURS": "n", "CHG_NOUVELLES_CATEGORIES": "n",
          "CHG_DEPOTS": "n", "PAI_MARGE": "z", "PAI_MAHALANOBIS": "d", "RES_FOURNISSEUR_PARTAGE": "n", "RES_COQUILLE": "%",
          "RES_PROXIMITE_REDRESSE": "d"}


def brute(code: str, v: float) -> float:
    """Inverse approximatif des normalisations du contrat §3."""
    return {"COH_IMPORT_VS_CA": v * 200, "COH_CLIENTS_VS_CA": 1 + 2 * v, "COH_ADEB_VS_CA": 0.9 + 0.6 * v, "COH_TVA_IMPORT": 1.1 + 0.9 * v,
            "COH_VALEUR_REF": 0.9 - 0.4 * v, "CHG_NOUVEAUX_FOURNISSEURS": round(5 * v), "CHG_NOUVELLES_CATEGORIES": round(3 * v),
            "CHG_DEPOTS": round(4 * v), "PAI_MAHALANOBIS": 2 + 4 * v, "RES_FOURNISSEUR_PARTAGE": round(5 * v), "RES_COQUILLE": 0.3 * v,
            "RES_PROXIMITE_REDRESSE": 1 if v >= 1 else 2 if v >= 0.5 else 3 if v >= 0.2 else 99}.get(code, 1 + 3 * v)


def fait(code: str, v: float, mf: str) -> str:
    b = brute(code, v)
    f = lambda x: f"{x:.1f}".replace(".", ",")  # noqa: E731
    if mf == "1000001BAM000":
        speciaux = {"COH_IMPORT_VS_CA": "Importations sur 6 mois : +240 % ; CA déclaré : +3 %.",
                    "RES_FOURNISSEUR_PARTAGE": "Partage un nouveau fournisseur étranger (FE00231) avec 4 autres entreprises apparues le même mois.",
                    "CHG_IMPORTS": "Importations ×3,4 par rapport à la moyenne des 12 derniers mois.",
                    "CHG_NOUVEAUX_FOURNISSEURS": "3 nouveaux fournisseurs en 3 mois (2 étrangers, 1 local)."}
        if code in speciaux:
            return speciaux[code]
    return {
        "COH_IMPORT_VS_CA": f"Importations sur 6 mois : +{b + 3:.0f} % ; CA déclaré : +3 %.",
        "COH_CLIENTS_VS_CA": f"Les clients déclarent {f(b)} fois le CA déclaré par l'entreprise sur le dernier exercice.",
        "COH_ADEB_VS_CA": f"Paiements publics reçus sur 12 mois égaux à {f(b)} fois le CA déclaré.",
        "COH_TVA_IMPORT": f"TVA déduite sur importations égale à {f(b)} fois la TVA payée en douane.",
        "COH_VALEUR_REF": f"Valeurs unitaires déclarées à {b * 100:.0f} % du prix de référence.",
        "CHG_CA": f"CA déclaré du mois {f(b)} écarts-types hors de son niveau habituel.",
        "CHG_IMPORTS": f"Importations {f(b)} écarts-types au-dessus de la moyenne des 12 derniers mois.",
        "CHG_TVA_DEDUCTIBLE": f"TVA déductible sur achats locaux {f(b)} écarts-types au-dessus de son niveau habituel.",
        "CHG_NOUVEAUX_FOURNISSEURS": f"{max(1, b):.0f} nouveaux fournisseurs en 3 mois.",
        "CHG_NOUVELLES_CATEGORIES": f"{max(1, b):.0f} nouvelle(s) catégorie(s) de produits importée(s) en 3 mois.",
        "CHG_DEPOTS": f"{max(1, b):.0f} déclarations mensuelles sur 6 non déposées ou en retard.",
        "PAI_MARGE": f"Marge apparente {f(b)} écarts-types sous la médiane des pairs.",
        "PAI_MAHALANOBIS": f"Profil atypique pour son secteur (distance {f(b)} au centre du groupe de pairs).",
        "RES_FOURNISSEUR_PARTAGE": f"Partage {max(1, b):.0f} nouveau(x) fournisseur(s) avec d'autres entreprises apparues au même moment.",
        "RES_COQUILLE": f"{b * 100:.0f} % des achats déclarés proviennent de fournisseurs sans salarié ni activité déclarée.",
        "RES_PROXIMITE_REDRESSE": "Partenaire commercial proche d'une entreprise redressée pour fraude significative.",
    }[code]


def lettre(i: int) -> str:
    return "ABCDEFGHJKLMNPQRSTVWXYZ"[i % 23]


def entreprises(n: int) -> pd.DataFrame:
    rows = []
    heros = [("1000001BAM000", "Alpha SARL", "SARL", "46.69", 34, 23, "2014-03-01", "A", "2026-07", 1.0, False, "CRCI"),
             ("1000002CAM000", "Beta Import SUARL", "SUARL", "46.43", 13, 7, "2017-09-15", "C", "2026-02", 1.0, False, "CRCI"),
             ("1000003DAM000", "Gamma Travaux SA", "SA", "42.11", 11, 64, "2009-05-20", "D", "2025-10", 1.0, False, "DME"),
             ("1000004EAM000", "Delta Trade SARL", "SARL", "46.90", 52, 2, "2019-01-10", "E", "2026-03", 1.0, False, "CRCI"),
             ("1000005FAM000", "Epsilon Textile SARL", "SARL", "14.13", 32, 38, "2011-06-01", "F", "2025-09", 0.55, False, "CRCI"),
             ("1000006GAM000", "Zeta Industries SA", "SA", "25.11", 31, 120, "2008-02-12", "CROISSANCE_LEGITIME", "2026-03", 1.0, False, "DGE"),
             ("1000007HAM000", "Eta Pharma SA", "SA", "46.46", 12, 85, "2005-10-03", "CITOYEN_MODELE", None, 0.0, True, "DGE"),
             ("1000008JAM000", "Omega Négoce SUARL", "SUARL", "46.90", 11, 0, "2024-11-18", "COQUILLE", "2025-03", 1.0, False, "CRCI")]
    for h in heros:
        rows.append(dict(zip(["mf", "raison_sociale", "forme_juridique", "code_nat", "gouvernorat_code", "effectif_declare",
                              "date_debut_activite", "scenario", "mois_debut_scenario", "intensite", "statut_oea", "centre_gestion"], h)))
    for i, nom in enumerate(["Kappa Equipements SARL", "Lambda Import SARL", "Mu Outillage SUARL", "Nu Machines SARL"]):
        rows.append(dict(mf=f"100031{i + 1}KAM000", raison_sociale=nom, forme_juridique=nom.split()[-1], code_nat="46.69",
                         gouvernorat_code=[11, 13, 34, 31][i], effectif_declare=[12, 5, 3, 9][i], date_debut_activite="2016-04-01",
                         scenario="A", mois_debut_scenario="2026-07", intensite=0.8, statut_oea=False, centre_gestion="CRCI", id_reseau="FE00231"))
    for i, nom in enumerate(["Sigma Distribution SARL", "Tau Matériaux SARL", "Upsilon Services SUARL", "Phi Équipements SARL", "Chi Commerce SARL"]):
        rows.append(dict(mf=f"100041{i + 1}KAM000", raison_sociale=nom, forme_juridique=nom.split()[-1], code_nat=["46.90", "41.20", "62.01", "46.69", "47.11"][i],
                         gouvernorat_code=11, effectif_declare=[14, 22, 6, 11, 8][i], date_debut_activite="2012-01-01",
                         scenario="B", mois_debut_scenario="2025-03", intensite=0.9, statut_oea=False, centre_gestion="CRCI", id_reseau="R01"))
    codes = list(NAT)
    gouv = list(GOUV_POIDS)
    gp = np.array(list(GOUV_POIDS.values()))
    prefixes = ["Société", "Ets", "Groupe", "Comptoir", "Atelier", "Tunisie", "Méditerranée", "Carthage", "Sahel", "Atlas"]
    noms = ["Nour", "Yasmine", "Salam", "Horizon", "Elyssa", "Hannibal", "Jasmin", "Zitouna", "Oasis", "Kairouan", "Dido", "Amal",
            "Baraka", "Rayen", "Sabra", "Tanit", "Lotus", "Ennasr", "Medina", "Ribat"]
    reste = n - len(rows)
    tailles = rng.choice([1, 5, 25, 70, 150], size=reste, p=[0.45, 0.30, 0.18, 0.04, 0.03])
    for j in range(reste):
        i = 9 + j if 9 + j < 311 else 500 + j
        forme = rng.choice(["SARL", "SUARL", "SA"], p=[0.73, 0.23, 0.04])
        eff = int(max(0, rng.normal(tailles[j], tailles[j] * 0.3)))
        rows.append(dict(mf=f"{1000000 + i:07d}{lettre(i)}AM000", raison_sociale=f"{rng.choice(prefixes)} {rng.choice(noms)} {forme}",
                         forme_juridique=forme, code_nat=codes[rng.choice(len(codes), p=NAT_POIDS / NAT_POIDS.sum())],
                         gouvernorat_code=int(rng.choice(gouv, p=gp / gp.sum())), effectif_declare=eff,
                         date_debut_activite=f"{rng.integers(1995, 2024)}-{rng.integers(1, 13):02d}-01",
                         scenario="AUCUN", mois_debut_scenario=None, intensite=0.0, statut_oea=False,
                         centre_gestion="DGE" if eff >= 100 else "DME" if eff >= 50 else "CRCI"))
    df = pd.DataFrame(rows)
    # scénarios aléatoires sur les entreprises ordinaires
    libres = df.index[df["scenario"] == "AUCUN"].to_numpy().copy()
    rng.shuffle(libres)
    pos = 0
    for sc, part in PART_SCENARIO.items():
        k = int(round(part * n))
        sel = libres[pos:pos + k]
        pos += k
        df.loc[sel, "scenario"] = sc
        if sc != "CITOYEN_MODELE":
            df.loc[sel, "mois_debut_scenario"] = rng.choice(config._mois("2025-03", "2026-06"), size=len(sel))
            df.loc[sel, "intensite"] = rng.uniform(0.3, 1.0, size=len(sel)).round(2)
        else:
            df.loc[sel, "statut_oea"] = rng.random(len(sel)) < 0.2
            df.loc[sel, "date_debut_activite"] = "2010-01-01"
    # 3 réseaux B supplémentaires : 1 coquille + 4 clients
    for r in range(3):
        bloc = libres[pos:pos + 5]
        pos += 5
        debut = str(rng.choice(config._mois("2025-03", "2026-03")))
        df.loc[bloc[0], ["scenario", "effectif_declare", "date_debut_activite"]] = ["COQUILLE", 0, "2024-06-01"]
        df.loc[bloc, "mois_debut_scenario"] = debut
        df.loc[bloc, "intensite"] = round(float(rng.uniform(0.6, 1.0)), 2)
        df.loc[bloc[1:], "scenario"] = "B"
        df.loc[bloc, "id_reseau"] = f"R{r + 2:02d}"
    df["id_reseau"] = df.get("id_reseau")
    df.loc[df["mf"].isin([f"100041{i}KAM000" for i in range(1, 6)] + ["1000008JAM000"]), "id_reseau"] = "R01"
    df.loc[df["mf"] == "1000001BAM000", "id_reseau"] = "FE00231"
    return df


def rampe(t: np.ndarray, mf: str) -> np.ndarray:
    if mf == "1000001BAM000" or (mf.startswith("100031") and mf.endswith("KAM000")):
        return np.where(t < 0, 0.0, np.where(t == 0, 0.55, 1.0))
    return np.where(t < 0, 0.0, np.minimum(1.0, (t + 1) / 3))


def signaux_matrice(df: pd.DataFrame) -> np.ndarray:
    n = len(df)
    # bruit réaliste : même normalisation que B, clip((z − 1) / 3) avec z ~ N(0, 1) → 0 dans ~84 % des cas
    V = np.clip((rng.normal(0, 1, size=(n, T, len(CODES))) - 1) / 3, 0, 1)
    bruit_chg = np.array([0.01 if c.startswith("CHG_") else 0.003 for c in CODES])
    pics = rng.random((n, T, len(CODES))) < bruit_chg
    V = np.where(pics, rng.uniform(0.45, 0.85, size=V.shape), V)
    idx_mois = {m: i for i, m in enumerate(MOIS)}
    for i, r in enumerate(df.itertuples(index=False)):
        if r.scenario == "CITOYEN_MODELE":
            V[i] = 0.0
            continue
        if r.mf == "1000006GAM000":
            V[i] = np.minimum(V[i], 0.1)
        if r.scenario not in SIGNATURES or not isinstance(r.mois_debut_scenario, str):
            continue
        t = np.arange(T) - idx_mois.get(r.mois_debut_scenario, T)
        a = rampe(t, r.mf) * (0.45 + 0.55 * r.intensite)
        for code, force in SIGNATURES[r.scenario].items():
            V[i, :, K[code]] = np.clip(np.maximum(V[i, :, K[code]], a * force * rng.uniform(0.85, 1.1)), 0, 1)
        if r.scenario == "A" and isinstance(r.id_reseau, str):
            V[i, :, K["RES_FOURNISSEUR_PARTAGE"]] = np.maximum(V[i, :, K["RES_FOURNISSEUR_PARTAGE"]], a * 0.85)
        if r.scenario == "E":
            V[i, :, K["CHG_DEPOTS"]] = np.where(t >= -6, 1.0, 0.6)
    # héros : forcer la lisibilité
    h = {m: i for i, m in enumerate(df["mf"])}
    V[h["1000002CAM000"], :, K["CHG_NOUVELLES_CATEGORIES"]] = np.minimum(V[h["1000002CAM000"], :, K["CHG_NOUVELLES_CATEGORIES"]], 0.4)
    V[h["1000005FAM000"], :, [K["COH_IMPORT_VS_CA"], K["COH_CLIENTS_VS_CA"], K["COH_ADEB_VS_CA"]]] = 0.0
    V[h["1000001BAM000"], :-2, :] = np.minimum(V[h["1000001BAM000"], :-2, :], 0.25)
    return V.round(3)


def main(n: int = 1500) -> None:
    for d in ("raw", "graphe", "signaux", "scores"):
        (DEV / d).mkdir(parents=True, exist_ok=True)
    df = entreprises(n)
    V = signaux_matrice(df)
    mfs = df["mf"].tolist()
    info = df.set_index("mf")
    idx_mois = {m: i for i, m in enumerate(MOIS)}

    # ------------------------------------------------ contribuables + référentiels
    c = df[["mf", "raison_sociale", "forme_juridique", "code_nat", "gouvernorat_code", "effectif_declare", "date_debut_activite",
            "statut_oea", "centre_gestion"]].copy()
    c.insert(1, "matricule_fiscal", c["mf"].map(lambda m: f"{m[:7]}/{m[7]}/{m[8]}/{m[9]}/{m[10:]}"))
    c["code_tva"] = c["mf"].str[7]
    c["code_categorie"] = "M"
    c["section_nat"] = c["code_nat"].map(lambda x: NAT[x][1])
    c["regime_fiscal"] = "REEL"
    c["taux_is"] = 20.0
    c["statut_export"] = "ONSHORE"
    c["capital_social"] = 50000.0
    c["date_cloture_exercice"] = "12-31"
    c["code_en_douane"] = "CD" + c["mf"].str[:7]
    c["date_oea"] = np.where(c["statut_oea"], "2021-06-01", "")
    c["date_cessation"] = ""
    c.to_csv(DEV / "raw" / "contribuables.csv", index=False)
    pd.DataFrame([{"code_nat": k, "libelle": v[0], "section_nat": v[1], "division": k[:2], "marge_brute_reference": v[2],
                   "part_importatrice": v[3]} for k, v in NAT.items()]).to_csv(DEV / "raw" / "ref_nat.csv", index=False)
    pd.DataFrame([{"gouvernorat_code": k, "libelle": v, "poids_entreprises": GOUV_POIDS.get(k, 1)} for k, v in config.GOUVERNORATS.items()]
                 ).to_csv(DEV / "raw" / "ref_gouvernorats.csv", index=False)
    pd.DataFrame([{"id_acheteur_public": "AP0007", "libelle": "Ministère de l'Équipement", "type": "MINISTERE", "gouvernorat_code": 11},
                  {"id_acheteur_public": "AP0023", "libelle": "Commune de Tunis", "type": "COMMUNE", "gouvernorat_code": 11},
                  {"id_acheteur_public": "AP0031", "libelle": "Office national de l'assainissement", "type": "ENTREPRISE_PUBLIQUE", "gouvernorat_code": 11}]
                 ).to_csv(DEV / "raw" / "ref_acheteurs_publics.csv", index=False)

    # ------------------------------------------------ déclarations mensuelles
    taille_ca = {1: 25_000, 5: 60_000, 25: 125_000, 70: 400_000, 150: 1_200_000}
    ca_base = np.array([max(3000.0, rng.lognormal(np.log(10_000 + 9_000 * max(e, 0) ** 0.9), 0.4)) for e in df["effectif_declare"]])
    ca_base[mfs.index("1000001BAM000")] = 96_000
    importateur = (rng.random(n) < df["code_nat"].map(lambda x: NAT[x][3]).to_numpy()) | df["scenario"].isin(["A", "C", "E", "CROISSANCE_LEGITIME"]).to_numpy()
    importateur[mfs.index("1000003DAM000")] = False
    decl, series_imp = [], np.zeros((n, T))
    for i, mf in enumerate(mfs):
        sc = info.at[mf, "scenario"]
        t0 = idx_mois.get(info.at[mf, "mois_debut_scenario"] or "", T)
        for t, m in enumerate(MOIS):
            ca = ca_base[i] * rng.uniform(0.93, 1.07)
            imp = ca_base[i] * 0.45 * rng.uniform(0.8, 1.2) if importateur[i] else 0.0
            if sc == "CROISSANCE_LEGITIME" and t >= t0:
                ca *= 2.0
                imp *= 2.4
            if sc in ("A", "E") and t >= t0:
                imp *= 3.4 if t > t0 else 2.3
            if mf == "1000001BAM000":
                ca, imp = {"2026-06": (95000.0, 60000.0), "2026-07": (97000.0, 150000.0), "2026-08": (96500.0, 170000.0)}.get(m, (ca, imp))
            if sc == "E" and t < t0:
                ca, imp = 0.0, 0.0
            series_imp[i, t] = imp
            tva_ded = (ca * 0.6 - imp) * 0.19 if ca * 0.6 > imp else ca * 0.05
            if sc == "B" and t >= t0:
                tva_ded *= 1.8
            depose = not (sc == "E" and t0 - 6 <= t < t0 + 1 and t % 2 == 0) and rng.random() > 0.02
            retard = int(rng.integers(35, 90)) if sc == "E" and depose and t >= t0 - 6 else (int(rng.integers(1, 20)) if rng.random() < 0.06 else 0)
            a, mo = map(int, m.split("-"))
            lim = f"{a + (mo == 12):04d}-{mo % 12 + 1:02d}-28"
            decl.append({"mf": mf, "mois": m, "statut_depot": "DEPOSEE" if depose else "NON_DEPOSEE", "code_declaration": 0 if depose else None,
                         "date_limite": lim, "date_depot": lim if depose else None, "jours_retard": retard if depose else None,
                         "ca_total_declare": round(ca, 3) if depose else 0.0, "tva_collectee": round(ca * 0.19, 3) if depose else 0.0,
                         "tva_deductible_biens_services_local": round(max(tva_ded, 0), 3) if depose else 0.0,
                         "tva_deductible_import": round(imp * 0.19, 3) if depose else 0.0})
    pd.DataFrame(decl).to_csv(DEV / "raw" / "declarations_mensuelles.csv", index=False)

    # ------------------------------------------------ douane
    fe = [{"id_fournisseur": f"FE{k:05d}", "nom": f"{rng.choice(['Shanghai', 'Istanbul', 'Milano', 'Lyon', 'Valencia', 'Hamburg'])} "
                                                   f"{rng.choice(['Trading', 'Industries', 'Export', 'Tools', 'Supply'])} {k}",
           "pays": str(rng.choice(["CN", "TR", "IT", "FR", "ES", "DE"])), "date_premiere_apparition": "2020-01-01", "chapitres_sh_principaux": "84;85"}
          for k in range(1, 400)]
    fe[230] = {"id_fournisseur": "FE00231", "nom": "Shenzhen Tools Co.", "pays": "CN", "date_premiere_apparition": "2026-06-04", "chapitres_sh_principaux": "84"}
    pd.DataFrame(fe).to_csv(DEV / "raw" / "fournisseurs_etrangers.csv", index=False)
    decls, arts, seq = [], [], 10000
    four_habituel = {mf: f"FE{rng.integers(1, 230):05d}" for mf in mfs}
    for i, mf in enumerate(mfs):
        if not importateur[i]:
            continue
        sc = info.at[mf, "scenario"]
        t0 = idx_mois.get(info.at[mf, "mois_debut_scenario"] or "", T)
        for t, m in enumerate(MOIS):
            if series_imp[i, t] <= 0:
                continue
            seq += 1
            num = f"{m[:4]}/{rng.choice([301, 302, 401, 402])}/{seq:07d}"
            nouveau = sc in ("A", "E") and t >= t0
            four = ("FE00231" if isinstance(info.at[mf, "id_reseau"], str) and info.at[mf, "id_reseau"] == "FE00231" else f"FE{240 + i % 150:05d}") if nouveau else four_habituel[mf]
            decls.append({"num_declaration": num, "type_declaration": "IC100", "bureau_code": num.split("/")[1],
                          "date_enregistrement": f"{m}-{rng.integers(2, 27):02d}", "mf_importateur": mf, "code_en_douane": "CD" + mf[:7],
                          "pays_provenance": "CN" if four == "FE00231" else "IT", "circuit": str(rng.choice(["V", "O", "R"], p=[0.7, 0.22, 0.08])),
                          "valeur_caf_tnd": round(series_imp[i, t], 3)})
            nb_art = 2
            for k in range(nb_art):
                v = series_imp[i, t] / nb_art
                pref = rng.uniform(900, 25000)
                ratio = rng.uniform(0.45, 0.65) if sc == "C" and t >= t0 else rng.uniform(0.9, 1.1)
                pu = pref * ratio
                q = max(1, int(v / pu))
                chap = "85" if sc == "E" and t >= t0 and k == 1 else "84"
                arts.append({"id_article": f"{num}-{k + 1:03d}", "num_declaration": num, "num_article": k + 1,
                             "code_ndp": f"{chap}79899700{k}", "code_sh6": f"{chap}7989", "chapitre_sh": chap,
                             "designation": "Machines diverses" if chap == "84" else "Machines électriques",
                             "id_fournisseur_etranger": four, "pays_origine": "CN" if four == "FE00231" else "IT",
                             "poids_net_kg": round(q * 12.5, 1), "quantite": q, "unite": "U", "valeur_caf_tnd": round(v, 3),
                             "prix_unitaire_tnd": round(v / q, 3), "prix_reference_tnd": round(pref, 3)})
    art = pd.DataFrame(arts)
    ddm = pd.DataFrame(decls)
    art.drop(columns="prix_reference_tnd").to_csv(DEV / "raw" / "douane_articles.csv", index=False)
    ddm.to_csv(DEV / "raw" / "douane_declarations.csv", index=False)
    art.merge(ddm[["num_declaration", "date_enregistrement", "mf_importateur"]], on="num_declaration")[["code_ndp", "prix_reference_tnd"]] \
        .drop_duplicates("code_ndp").assign(designation="Machines", unite="U", taux_dd=0.0, taux_tva=19.0, taux_fodec=1.0) \
        .to_csv(DEV / "raw" / "ref_ndp.csv", index=False)
    art_m = art.merge(ddm[["num_declaration", "date_enregistrement", "mf_importateur", "circuit"]], on="num_declaration")
    art_m["mois"] = art_m["date_enregistrement"].str[:7]

    # ------------------------------------------------ annexe V (réseaux B) et ADEB (scénario D)
    a5 = []
    for res, g in df[df["id_reseau"].fillna("").str.startswith("R")].groupby("id_reseau"):
        coq = g[g["scenario"] == "COQUILLE"]["mf"].tolist()
        for cli in g[g["scenario"] == "B"]["mf"]:
            for k, fr in enumerate(coq):
                a5.append({"id_ligne": f"A5-2025-{cli}-{len(a5) + 1:06d}", "mf_payeur": cli, "exercice": 2025, "code_acte": 0,
                           "mf_fournisseur": fr, "montant_ttc": round(float(rng.uniform(450_000, 800_000)), 3), "taux_retenue": 1.5,
                           "retenue_is": 0.0, "retenue_tva": 0.0, "montant_net": 0.0, "premiere_annee_relation": 2025})
    for i, mf in enumerate(mfs[:600]):
        fr = mfs[(i * 7 + 13) % n]
        if fr != mf and info.at[fr, "scenario"] != "COQUILLE":
            a5.append({"id_ligne": f"A5-2025-{mf}-{len(a5) + 1:06d}", "mf_payeur": mf, "exercice": 2025, "code_acte": 0, "mf_fournisseur": fr,
                       "montant_ttc": round(float(rng.uniform(2_000, 60_000)), 3), "taux_retenue": 1.5, "retenue_is": 0.0, "retenue_tva": 0.0,
                       "montant_net": 0.0, "premiere_annee_relation": int(rng.integers(2019, 2026))})
    a5 = pd.DataFrame(a5)
    a5["retenue_is"] = (a5["montant_ttc"] * 0.015).round(3)
    a5["montant_net"] = (a5["montant_ttc"] - a5["retenue_is"]).round(3)
    a5.to_csv(DEV / "raw" / "employeur_annexe5.csv", index=False)
    adeb = []
    for mf in df[df["scenario"] == "D"]["mf"]:
        for k in range(12):
            m = MOIS[-1 - k]
            ht = round(float(rng.uniform(40_000, 110_000)), 3)
            adeb.append({"num_ordonnance": f"ORD-{m[:4]}-{len(adeb) + 1:07d}", "exercice": int(m[:4]), "id_acheteur_public": ["AP0007", "AP0023", "AP0031"][k % 3],
                         "mf_beneficiaire": mf, "nature_achat": "MARCHE_TUNEPS", "date_paiement": f"{m}-15", "montant_ht": ht,
                         "montant_tva": round(ht * 0.19, 3), "montant_ttc": round(ht * 1.19, 3), "retenue_tva_25": round(ht * 0.19 * 0.25, 3),
                         "retenue_is": round(ht * 0.015, 3), "net_a_payer": round(ht * 1.19 * 0.94, 3)})
    adeb = pd.DataFrame(adeb)
    adeb.to_csv(DEV / "raw" / "adeb_paiements.csv", index=False)

    # ------------------------------------------------ graphe
    ar = []
    g = art_m.groupby(["mf_importateur", "id_fournisseur_etranger"]).agg(montant_total=("valeur_caf_tnd", "sum"),
                                                                           premiere_date=("date_enregistrement", "min"),
                                                                           derniere_date=("date_enregistrement", "max")).reset_index()
    ar.append(g.rename(columns={"mf_importateur": "source", "id_fournisseur_etranger": "cible"}).assign(type_relation="IMPORT_FOURNISSEUR"))
    ar.append(a5.groupby(["mf_payeur", "mf_fournisseur"]).agg(montant_total=("montant_ttc", "sum"), premiere_annee=("premiere_annee_relation", "min"))
              .reset_index().rename(columns={"mf_payeur": "source", "mf_fournisseur": "cible"})
              .assign(type_relation="ACHAT_LOCAL_A5", premiere_date=lambda d: d["premiere_annee"].astype(str) + "-01-01",
                      derniere_date="2025-12-31").drop(columns="premiere_annee"))
    if len(adeb):
        ar.append(adeb.groupby(["id_acheteur_public", "mf_beneficiaire"]).agg(montant_total=("montant_ttc", "sum"), premiere_date=("date_paiement", "min"),
                                                                                derniere_date=("date_paiement", "max")).reset_index()
                  .rename(columns={"id_acheteur_public": "source", "mf_beneficiaire": "cible"}).assign(type_relation="PAIEMENT_PUBLIC"))
    aretes = pd.concat(ar, ignore_index=True)[["source", "cible", "type_relation", "montant_total", "premiere_date", "derniere_date"]]
    aretes["montant_total"] = aretes["montant_total"].round(3)
    aretes.to_csv(DEV / "graphe" / "aretes.csv", index=False)

    # ------------------------------------------------ signaux (format long de B)
    art_par_mf = {mf: g.sort_values("valeur_caf_tnd", ascending=False) for mf, g in art_m.groupby("mf_importateur")}
    a5_par = {}
    for r in a5.itertuples(index=False):
        a5_par.setdefault(r.mf_payeur, []).append(r.id_ligne)
        a5_par.setdefault(r.mf_fournisseur, []).append(r.id_ligne)
    adeb_par = adeb.groupby("mf_beneficiaire")["num_ordonnance"].apply(list).to_dict() if len(adeb) else {}

    def preuves(code, mf, t):
        m = MOIS[t]
        fen = set(MOIS[max(0, t - 5):t + 1])
        if code in ("COH_CLIENTS_VS_CA", "RES_COQUILLE", "CMB_COQUILLE_X_TVA") or (code == "RES_FOURNISSEUR_PARTAGE" and mf in a5_par and mf not in art_par_mf):
            return [f"employeur_annexe5:{x}" for x in a5_par.get(mf, [])[:50]]
        if code == "COH_ADEB_VS_CA":
            return [f"adeb_paiements:{x}" for x in adeb_par.get(mf, [])[:50]]
        if code.startswith(("COH_IMPORT", "CHG_IMPORTS", "CHG_NOUVE", "COH_VALEUR", "COH_TVA", "RES_FOURNISSEUR")):
            a = art_par_mf.get(mf)
            if a is None:
                return []
            return [f"douane_articles:{x}" for x in a[a["mois"].isin(fen)]["id_article"].head(50)]
        return [f"declarations_mensuelles:{mf}:{x}" for x in sorted(fen)]

    lignes = {k: [] for k in ("mf", "mois", "code_signal", "lentille", "valeur_brute", "unite", "valeur_norm", "fait_fr", "sources", "preuves")}
    for i, mf in enumerate(mfs):
        for t, m in enumerate(MOIS):
            for code in CODES:
                v = float(V[i, t, K[code]])
                actif = v >= config.SEUIL_ACTIF
                lignes["mf"].append(mf)
                lignes["mois"].append(m)
                lignes["code_signal"].append(code)
                lignes["lentille"].append(config.SIGNAUX_B[code])
                lignes["valeur_brute"].append(round(float(brute(code, v)), 3))
                lignes["unite"].append(UNITES[code])
                lignes["valeur_norm"].append(v)
                lignes["fait_fr"].append(fait(code, v, mf) if actif else "")
                lignes["sources"].append(SOURCES[code])
                lignes["preuves"].append(preuves(code, mf, t) if actif else [])
    sig = pd.DataFrame(lignes)
    sig.to_parquet(DEV / "signaux" / "signaux.parquet", index=False)

    # ------------------------------------------------ enjeux
    fraude = ~df["scenario"].isin(config.SCENARIOS_NON_FRAUDE)
    montant = np.where(fraude, np.maximum(20_000, rng.lognormal(np.log(160_000), 0.6, size=n)) * (0.5 + df["intensite"].to_numpy()), 0.0)
    montant[mfs.index("1000001BAM000")] = 460_000
    montant[mfs.index("1000008JAM000")] = 700_000
    montant[mfs.index("1000003DAM000")] = 650_000
    montant[mfs.index("1000004EAM000")] = 90_000
    en = []
    for i, mf in enumerate(mfs):
        t0 = idx_mois.get(info.at[mf, "mois_debut_scenario"] or "", T)
        for t, m in enumerate(MOIS):
            if fraude.iloc[i] and t >= t0:
                e = montant[i] * float(rampe(np.array([t - t0]), mf)[0]) * rng.uniform(0.8, 1.1)
            else:
                e = 0.0 if rng.random() < 0.7 else rng.uniform(0, 25_000)
            if mf == "1000001BAM000" and m == "2026-08":
                e = 420_000.0
            conf = round(float(rng.uniform(0.5, 0.95)), 2)
            en.append({"mf": mf, "mois": m, "ca_observe_12m": round(ca_base[i] * 12 + e * 3, 3), "ca_declare_12m": round(ca_base[i] * 12, 3),
                       "base_omise_12m": round(e * 3, 3), "tva_surdeduite_12m": 0.0, "enjeu_estime": round(e, 3),
                       "enjeu_bas": round(e * 0.74, 3), "enjeu_haut": round(e * 1.29, 3), "confiance": conf})
    pd.DataFrame(en).to_parquet(DEV / "signaux" / "enjeux.parquet", index=False)

    # ------------------------------------------------ pairs
    classe = df["effectif_declare"].map(lambda e: "0-2" if e <= 2 else "3-9" if e <= 9 else "10-49" if e <= 49 else "50+")
    groupe = df["code_nat"].str[:2] + "|" + classe
    nb = groupe.map(groupe.value_counts())
    gp = pd.DataFrame({"mf": df["mf"], "groupe": groupe, "libelle_groupe": df["code_nat"].str[:2] + " × " + classe.str.replace("-", "–") + " salariés",
                       "nb_pairs": nb})
    gp.to_parquet(DEV / "signaux" / "groupes_pairs.parquet", index=False)
    ps = []
    for gname, g in gp.groupby("groupe"):
        marge = NAT[df.loc[g.index[0], "code_nat"]][2]
        for m in MOIS:
            for ind, med, sp in (("MARGE", marge * 0.6, 0.08), ("TVA_DED_SUR_COLL", 0.62, 0.15), ("CA_PAR_SALARIE", 60_000, 35_000), ("IMPORTS_SUR_CA", 0.4, 0.3)):
                ps.append({"groupe": gname, "mois": m, "indicateur": ind, "mediane": round(med, 3), "p10": round(max(0, med - sp), 3),
                           "p90": round(med + sp, 3), "nb": int(len(g))})
    pd.DataFrame(ps).to_parquet(DEV / "signaux" / "pairs_stats.parquet", index=False)

    # ------------------------------------------------ historique des contrôles (biais de sélection volontaire)
    sar = V[:, :, [K[c] for c in config.SIGNAUX_SAR]].mean(axis=2) + 0.2 * np.array([[0 if e <= 2 else 1 if e <= 9 else 2 if e <= 49 else 3]
                                                                                     for e in df["effectif_declare"]])
    coh = V[:, :, [K[c] for c in CODES if c.startswith("COH_")]].max(axis=2)
    ctl, deja = [], set()
    heros = set(config.HEROS) | {f"100031{i}KAM000" for i in range(1, 5)}
    mois_ctl = config._mois("2024-10", "2026-06")
    for m in mois_ctl:
        t = idx_mois[config.mois_precedent(m)]
        for origine, k in (("PROGRAMME_RISQUE", 7), ("RECOUPEMENT", 3), ("DENONCIATION", 1), ("ALEATOIRE", 2)):
            if origine == "PROGRAMME_RISQUE":
                p = sar[:, t] ** 3
            elif origine == "RECOUPEMENT":
                p = coh[:, t] ** 2 + 0.01
            elif origine == "DENONCIATION":
                p = np.array([2.0 if fraude.iloc[i] and idx_mois.get(info.at[mf, "mois_debut_scenario"] or "", T) <= t else 0.05 for i, mf in enumerate(mfs)])
            else:
                p = np.ones(n)
            p = np.array([0 if (mf in heros or mf in deja) else x for mf, x in zip(mfs, p)], dtype=float)
            for i in rng.choice(n, size=k, replace=False, p=p / p.sum()):
                mf = mfs[i]
                deja.add(mf)
                actif = bool(fraude.iloc[i]) and idx_mois.get(info.at[mf, "mois_debut_scenario"] or "", T) <= idx_mois[m]
                cat = rng.choice(["FRAUDE_SIGNIFICATIVE", "REDRESSEMENT_MINEUR", "CONFORME"], p=[0.7, 0.25, 0.05] if actif else [0.02, 0.33, 0.65])
                if info.at[mf, "scenario"] == "CITOYEN_MODELE":
                    cat = "CONFORME"
                mt = {"FRAUDE_SIGNIFICATIVE": montant[i] or 80_000, "REDRESSEMENT_MINEUR": rng.uniform(2_000, 20_000), "CONFORME": 0.0}[cat]
                j = f"{m}-{rng.integers(2, 27):02d}"
                ctl.append({"id_controle": f"CTL-{m[:4]}-{len(ctl) + 1:06d}", "mf": mf, "type_controle": "VERIF_APPROFONDIE_PARTIELLE",
                            "origine_selection": origine, "date_avis": j, "date_debut": j, "date_fin": j, "periode_debut": "2023-01",
                            "periode_fin": "2024-12", "impots_verifies": "TVA;IS;RS", "date_notification_resultats": j,
                            "issue": "SANS_REDRESSEMENT" if cat == "CONFORME" else "ACCORD", "categorie_resultat": cat,
                            "montant_redresse_tva": round(mt * 0.6, 3), "montant_redresse_is": round(mt * 0.4, 3), "montant_redresse_rs": 0.0,
                            "penalites": round(mt * 0.1, 3), "montant_recouvre": round(mt * 0.8, 3)})
    ctl.append({"id_controle": "CTL-2025-000041", "mf": "1000007HAM000", "type_controle": "VERIF_PRELIMINAIRE", "origine_selection": "ALEATOIRE",
                "date_avis": "2025-03-04", "date_debut": "2025-03-10", "date_fin": "2025-04-15", "periode_debut": "2023-01", "periode_fin": "2024-12",
                "impots_verifies": "TVA;IS", "date_notification_resultats": "2025-05-02", "issue": "SANS_REDRESSEMENT", "categorie_resultat": "CONFORME",
                "montant_redresse_tva": 0.0, "montant_redresse_is": 0.0, "montant_redresse_rs": 0.0, "penalites": 0.0, "montant_recouvre": 0.0})
    pd.DataFrame(ctl).to_csv(DEV / "raw" / "historique_controles.csv", index=False)

    # ------------------------------------------------ vérité terrain (🔒 évaluation seulement)
    vt = df[["mf", "scenario", "mois_debut_scenario", "intensite", "id_reseau"]].copy()
    vt["montant_fraude_reel"] = montant.round(3)
    vt.loc[vt["scenario"].isin(["CITOYEN_MODELE", "AUCUN"]), ["mois_debut_scenario"]] = None
    vt[["mf", "scenario", "mois_debut_scenario", "intensite", "montant_fraude_reel", "id_reseau"]].to_csv(DEV / "raw" / "verite_terrain.csv", index=False)

    print(f"Données de dev écrites dans {DEV} : {n} entreprises, {len(sig):,} lignes de signaux, {len(ctl)} contrôles, "
          f"{len(art):,} articles douane, {len(aretes):,} arêtes")
    print(df["scenario"].value_counts().to_string())


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 1500)

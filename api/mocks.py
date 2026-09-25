"""Écrit data/mock/*.json à partir des exemples du contrat (§6.2) et des 8 cas héros (§7).

Alpha reprend exactement les exemples du contrat (trajectoire et séries étendues aux 24 mois,
en gardant les points donnés). Les 7 autres héros sont des mocks plausibles cohérents avec §7.

Usage : uv run python -m api.mocks
"""

import json
import random

from scoring.config import DECISIONS, LENTILLES, MOCK, MOIS, SEED, SEUILS, fmt_dt

MOIS_AFFICHE = "2026-08"


def segment_de(score: float, confiance: bool = False) -> str:
    if confiance:
        return "CONFIANCE"
    if score >= SEUILS["PRIORITAIRE"]:
        return "PRIORITAIRE"
    if score >= SEUILS["SURVEILLANCE"]:
        return "SURVEILLANCE"
    return "NORMAL"


def trajectoire(points: dict[str, float], base: float, rng: random.Random, confiance_depuis: str | None = None):
    """24 mois : valeurs imposées dans `points`, bruit autour de `base` ailleurs (interpolation après le 1er point imposé)."""
    out, cles = [], sorted(points)
    for m in MOIS:
        if m in points:
            s = points[m]
        elif cles and m > cles[0]:
            prev = max(k for k in cles if k < m)
            nxt = [k for k in cles if k > m]
            s = points[prev] if not nxt else points[prev] + (points[nxt[0]] - points[prev]) * 0.5
            s += rng.uniform(-1.5, 1.5)
        else:
            s = base + rng.uniform(-2.5, 2.5)
        s = round(max(0.0, min(100.0, s)), 1)
        out.append({"mois": m, "score": s, "segment": segment_de(s, confiance_depuis is not None and m >= confiance_depuis)})
    return out


def series(ca: float, imp: float, tva: float, rng: random.Random, evenements: dict | None = None):
    """Séries mensuelles ; `evenements` = {mois: (ca, imports, tva)} valeurs imposées (≥ ce mois si clé '>=AAAA-MM')."""
    evenements = evenements or {}
    out = []
    for m in MOIS:
        c, i, t = ca * rng.uniform(0.93, 1.07), imp * rng.uniform(0.85, 1.15), tva * rng.uniform(0.9, 1.1)
        for k, v in evenements.items():
            if (k.startswith(">=") and m >= k[2:]) or k == m:
                c, i, t = (x if x is not None else y for x, y in zip(v, (c, i, t)))
        out.append({"mois": m, "ca_declare": round(c, 3), "imports_caf": round(i, 3), "tva_deductible": round(t, 3)})
    return out


def contrib(code, points, norm, fait, sources, nb):
    return {"code_signal": code, "lentille": LENTILLES.get(code, "COMBINAISON"), "points": points,
            "valeur_norm": norm, "fait_fr": fait, "sources": sources, "nb_preuves": nb}


# ---------------------------------------------------------------- Alpha (exemples exacts du contrat)
ALPHA_CONTRIB_CONTRAT = [
    contrib("COH_IMPORT_VS_CA", 18.5, 0.95, "Importations sur 6 mois : +240 % ; CA déclaré : +3 %.", ["douane", "dgi_declarations"], 14),
    contrib("RES_FOURNISSEUR_PARTAGE", 11.2, 0.8,
            "Partage un nouveau fournisseur étranger (FE00231) avec 4 autres entreprises apparues le même mois.", ["graphe", "douane"], 5),
]
ALPHA_PREUVE_CONTRAT = {
    "source": "douane_articles", "ref": "2026/401/0034567-001", "date": "2026-07-12",
    "libelle": "NDP 84798997000 — Machines diverses — Chine — FE00231", "montant": 88000.0,
    "champs": {"pays_origine": "CN", "quantite": 4, "unite": "U", "prix_unitaire_tnd": 22000.0, "circuit": "V"},
}
SYNTHESE_CONTRAT = {
    "mois": "2026-08", "nb_entreprises": 5250,
    "par_segment": {"PRIORITAIRE": 17, "SURVEILLANCE": 43, "NORMAL": 4760, "CONFIANCE": 430},
    "nouveaux_prioritaires_du_mois": 9, "enjeu_total_prioritaires": 6840000.0,
    "seuils": {"PRIORITAIRE": 70, "SURVEILLANCE": 40, "CONFIANCE": 15},
}
EVALUATION_CONTRAT = {
    "top_n": 50, "periode_test": "2025-09 → 2026-08",
    "methodes": [
        {"nom": "Basira", "taux_detection_top_n": 0.78, "montant_moyen_par_controle": 185000.0,
         "fausses_alertes_croissance_legitime": 1, "avance_detection_mois": 2.4},
        {"nom": "Règle statique (type SAR)", "taux_detection_top_n": 0.34, "montant_moyen_par_controle": 72000.0,
         "fausses_alertes_croissance_legitime": 11, "avance_detection_mois": 0.0},
        {"nom": "Sélection aléatoire", "taux_detection_top_n": 0.08, "montant_moyen_par_controle": 15000.0,
         "fausses_alertes_croissance_legitime": 1, "avance_detection_mois": None},
    ],
    "note": "Chiffres calculés sur données synthétiques ; vérité terrain cachée au modèle.",
}
ASSISTANT_CONTRAT = {
    "reponse": "Le score est passé de 28 à 76 en deux mois pour trois raisons principales : …",
    "citations": [{"type": "signal", "ref": "COH_IMPORT_VS_CA"}, {"type": "preuve", "ref": "douane_articles:2026/401/0034567-001"}],
    "mode": "llm",
}
DECISION_CONTRAT = {"id_decision": "DEC-000001", "enregistre": True, "date_heure": "2026-09-26T03:12:00"}


def heros(rng: random.Random) -> list[dict]:
    """Spécification des 8 héros au mois 2026-08."""
    H = []

    H.append(dict(
        identite={"mf": "1000001BAM000", "matricule_fiscal": "1000001/B/A/M/000", "raison_sociale": "Alpha SARL",
                  "forme_juridique": "SARL", "code_nat": "46.69", "libelle_nat": "Commerce de gros d'autres machines et équipements",
                  "gouvernorat": "Sfax", "date_debut_activite": "2014-03-01", "effectif": 23, "statut_oea": False, "centre_gestion": "CRCI"},
        gouvernorat_code=34, confiance=0.72, enjeu=(420000.0, 310000.0, 540000.0), action="VERIFICATION",
        resume="Imports ×3,4, CA déclaré stable, 3 nouveaux fournisseurs dont 1 partagé avec 4 entreprises signalées. Enjeu estimé : 420 000 DT.",
        trajectoire=trajectoire({"2025-09": 27.0, "2026-06": 28.0, "2026-07": 52.0, "2026-08": 76.0}, 27.0, rng),
        contributions=ALPHA_CONTRIB_CONTRAT + [
            contrib("CHG_IMPORTS", 14.3, 0.9, "Importations ×3,4 par rapport à la moyenne des 12 derniers mois.", ["douane"], 9),
            contrib("CMB_IMPORT_X_NOUV_FOURN", 12.6, 0.54, "Hausse des importations concentrée sur des fournisseurs nouveaux.", ["douane"], 9),
            contrib("CHG_NOUVEAUX_FOURNISSEURS", 8.4, 0.6, "3 nouveaux fournisseurs en 3 mois (2 étrangers, 1 local).", ["douane", "dgi_annexe5"], 3),
        ],
        pairs={"groupe": "46 × 10–49 salariés", "nb_pairs": 212, "indicateurs": [
            {"nom": "Marge apparente", "entreprise": 0.03, "mediane_pairs": 0.18, "p10": 0.09, "p90": 0.27},
            {"nom": "TVA déductible / collectée", "entreprise": 0.97, "mediane_pairs": 0.62, "p10": 0.45, "p90": 0.78},
            {"nom": "CA par salarié", "entreprise": 50600.0, "mediane_pairs": 61000.0, "p10": 32000.0, "p90": 118000.0},
            {"nom": "Imports / CA", "entreprise": 1.62, "mediane_pairs": 0.41, "p10": 0.08, "p90": 0.83}]},
        series=series(96000, 48000, 13500, rng, {"2026-06": (95000.0, 60000.0, 14000.0), "2026-07": (97000.0, 150000.0, 31000.0),
                                                 "2026-08": (96500.0, 170000.0, 36000.0)}),
        controles_passes=[],
    ))

    H.append(dict(
        identite={"mf": "1000002CAM000", "matricule_fiscal": "1000002/C/A/M/000", "raison_sociale": "Beta Import SUARL",
                  "forme_juridique": "SUARL", "code_nat": "46.43", "libelle_nat": "Commerce de gros d'appareils électroménagers",
                  "gouvernorat": "Ben Arous", "date_debut_activite": "2017-09-15", "effectif": 7, "statut_oea": False, "centre_gestion": "CRCI"},
        gouvernorat_code=13, confiance=0.64, enjeu=(185000.0, 120000.0, 260000.0), action="SIGNALEMENT_DOUANE",
        resume="Valeurs unitaires déclarées à 52 % du prix de référence sur 18 articles, profil atypique pour ses pairs. Enjeu estimé : 185 000 DT.",
        trajectoire=trajectoire({"2026-03": 24.0, "2026-05": 45.0, "2026-08": 66.0}, 23.0, rng),
        contributions=[
            contrib("COH_VALEUR_REF", 31.5, 0.95, "Valeurs unitaires déclarées à 52 % du prix de référence (18 articles, 3 codes NDP).", ["douane"], 18),
            contrib("PAI_MAHALANOBIS", 12.1, 0.7, "Profil atypique pour son secteur, surtout le ratio imports / CA (1,4 contre 0,5).", ["dgi_declarations", "douane"], 6),
            contrib("CHG_NOUVELLES_CATEGORIES", 8.2, 0.67, "Nouvelles catégories importées : chapitres 85 et 94.", ["douane"], 4),
        ],
        pairs={"groupe": "46 × 3–9 salariés", "nb_pairs": 388, "indicateurs": [
            {"nom": "Marge apparente", "entreprise": 0.24, "mediane_pairs": 0.19, "p10": 0.08, "p90": 0.29},
            {"nom": "Imports / CA", "entreprise": 1.4, "mediane_pairs": 0.5, "p10": 0.1, "p90": 0.9}]},
        series=series(210000, 150000, 9000, rng),
        controles_passes=[],
    ))

    H.append(dict(
        identite={"mf": "1000003DAM000", "matricule_fiscal": "1000003/D/A/M/000", "raison_sociale": "Gamma Travaux SA",
                  "forme_juridique": "SA", "code_nat": "42.11", "libelle_nat": "Construction de routes et autoroutes",
                  "gouvernorat": "Tunis", "date_debut_activite": "2009-05-20", "effectif": 64, "statut_oea": False, "centre_gestion": "DME"},
        gouvernorat_code=11, confiance=0.81, enjeu=(610000.0, 470000.0, 760000.0), action="VERIFICATION",
        resume="840 000 DT reçus d'acheteurs publics sur 12 mois pour un CA déclaré de 610 000 DT. Enjeu estimé : 610 000 DT.",
        trajectoire=trajectoire({"2025-11": 31.0, "2026-02": 58.0, "2026-05": 74.0, "2026-08": 82.0}, 30.0, rng),
        contributions=[
            contrib("COH_ADEB_VS_CA", 41.7, 1.0, "840 000 DT reçus d'acheteurs publics sur 12 mois, pour un CA déclaré de 610 000 DT.", ["adeb", "dgi_declarations"], 12),
            contrib("PAI_MARGE", 9.8, 0.55, "Marge apparente de 4 % contre 15 % en médiane pour les pairs (42, 50+ salariés).", ["dgi_declarations"], 12),
        ],
        pairs={"groupe": "42 × 50+ salariés", "nb_pairs": 64, "indicateurs": [
            {"nom": "Marge apparente", "entreprise": 0.04, "mediane_pairs": 0.15, "p10": 0.07, "p90": 0.22}]},
        series=series(51000, 0, 6500, rng),
        controles_passes=[],
    ))

    H.append(dict(
        identite={"mf": "1000004EAM000", "matricule_fiscal": "1000004/E/A/M/000", "raison_sociale": "Delta Trade SARL",
                  "forme_juridique": "SARL", "code_nat": "46.90", "libelle_nat": "Commerce de gros non spécialisé",
                  "gouvernorat": "Médenine", "date_debut_activite": "2019-01-10", "effectif": 2, "statut_oea": False, "centre_gestion": "CRCI"},
        gouvernorat_code=52, confiance=0.55, enjeu=(95000.0, 55000.0, 150000.0), action="DEMANDE_INFO",
        resume="4 déclarations mensuelles sur 6 non déposées ou en retard, puis importations ×6 soudaines. Enjeu estimé : 95 000 DT.",
        trajectoire=trajectoire({"2026-04": 35.0, "2026-06": 61.0, "2026-08": 73.0}, 34.0, rng),
        contributions=[
            contrib("CHG_DEPOTS", 17.5, 1.0, "4 déclarations mensuelles sur 6 non déposées ou en retard.", ["dgi_declarations"], 6),
            contrib("CHG_IMPORTS", 16.0, 1.0, "Importations ×6,1 par rapport à la moyenne des 12 derniers mois.", ["douane"], 7),
            contrib("COH_IMPORT_VS_CA", 12.4, 0.7, "Importations sur 6 mois : +480 % ; CA déclaré : −10 %.", ["douane", "dgi_declarations"], 7),
            contrib("CHG_NOUVELLES_CATEGORIES", 6.1, 0.67, "Nouvelles catégories importées : chapitres 61 et 64.", ["douane"], 3),
        ],
        pairs={"groupe": "46 × 0–2 salariés", "nb_pairs": 912, "indicateurs": [
            {"nom": "Imports / CA", "entreprise": 3.1, "mediane_pairs": 0.3, "p10": 0.0, "p90": 0.8}]},
        series=series(4000, 1000, 500, rng, {">=2026-03": (None, 45000.0, None), ">=2026-06": (3500.0, 95000.0, None)}),
        controles_passes=[],
    ))

    H.append(dict(
        identite={"mf": "1000005FAM000", "matricule_fiscal": "1000005/F/A/M/000", "raison_sociale": "Epsilon Textile SARL",
                  "forme_juridique": "SARL", "code_nat": "14.13", "libelle_nat": "Fabrication d'autres vêtements de dessus",
                  "gouvernorat": "Monastir", "date_debut_activite": "2011-06-01", "effectif": 38, "statut_oea": False, "centre_gestion": "CRCI"},
        gouvernorat_code=32, confiance=0.68, enjeu=(120000.0, 80000.0, 170000.0), action="RELANCE",
        resume="Marge apparente de 3 % contre 22 % en médiane pour les pairs, profil atypique. Enjeu estimé : 120 000 DT.",
        trajectoire=trajectoire({"2025-10": 22.0, "2026-02": 38.0, "2026-08": 56.0}, 21.0, rng),
        contributions=[
            contrib("PAI_MARGE", 21.3, 0.85, "Marge apparente de 3 % contre 22 % en médiane pour les pairs (14, 10–49 salariés).", ["dgi_declarations", "douane"], 12),
            contrib("PAI_MAHALANOBIS", 14.4, 0.75, "Profil atypique pour son secteur, surtout le ratio TVA déductible / collectée (0,94 contre 0,58).", ["dgi_declarations"], 12),
        ],
        pairs={"groupe": "14 × 10–49 salariés", "nb_pairs": 143, "indicateurs": [
            {"nom": "Marge apparente", "entreprise": 0.03, "mediane_pairs": 0.22, "p10": 0.12, "p90": 0.31},
            {"nom": "TVA déductible / collectée", "entreprise": 0.94, "mediane_pairs": 0.58, "p10": 0.41, "p90": 0.74}]},
        series=series(180000, 95000, 21000, rng),
        controles_passes=[],
    ))

    H.append(dict(
        identite={"mf": "1000006GAM000", "matricule_fiscal": "1000006/G/A/M/000", "raison_sociale": "Zeta Industries SA",
                  "forme_juridique": "SA", "code_nat": "25.11", "libelle_nat": "Fabrication de structures métalliques",
                  "gouvernorat": "Sousse", "date_debut_activite": "2008-02-12", "effectif": 120, "statut_oea": False, "centre_gestion": "DGE"},
        gouvernorat_code=31, confiance=0.9, enjeu=(0.0, 0.0, 15000.0), action="AUCUNE",
        resume="Importations en forte hausse, entièrement reflétées dans le CA et la TVA déclarés. Enjeu estimé : 0 DT.",
        trajectoire=trajectoire({"2026-08": 21.0}, 18.0, rng),
        contributions=[
            contrib("CHG_IMPORTS", 6.2, 0.85, "Importations ×2,6 par rapport à la moyenne des 12 derniers mois.", ["douane"], 8),
        ],
        pairs={"groupe": "25 × 50+ salariés", "nb_pairs": 58, "indicateurs": [
            {"nom": "Marge apparente", "entreprise": 0.21, "mediane_pairs": 0.2, "p10": 0.11, "p90": 0.28}]},
        series=series(900000, 300000, 110000, rng, {">=2026-04": (1900000.0, 780000.0, 240000.0)}),
        controles_passes=[],
    ))

    H.append(dict(
        identite={"mf": "1000007HAM000", "matricule_fiscal": "1000007/H/A/M/000", "raison_sociale": "Eta Pharma SA",
                  "forme_juridique": "SA", "code_nat": "46.46", "libelle_nat": "Commerce de gros de produits pharmaceutiques",
                  "gouvernorat": "Ariana", "date_debut_activite": "2005-10-03", "effectif": 85, "statut_oea": True, "centre_gestion": "DGE"},
        gouvernorat_code=12, confiance=0.95, enjeu=(0.0, 0.0, 5000.0), action="AUCUNE",
        resume="Dépôts à l'heure depuis 36 mois, déclarations cohérentes avec la douane, contrôle 2025 conforme, opérateur OEA. Candidat à la facilitation.",
        trajectoire=trajectoire({}, 6.0, rng, confiance_depuis="2024-09"),
        contributions=[],
        pairs={"groupe": "46 × 50+ salariés", "nb_pairs": 71, "indicateurs": [
            {"nom": "Marge apparente", "entreprise": 0.29, "mediane_pairs": 0.27, "p10": 0.15, "p90": 0.36}]},
        series=series(1400000, 700000, 160000, rng),
        controles_passes=[{"id_controle": "CTL-2025-000041", "date_avis": "2025-03-04", "type_controle": "VERIF_PRELIMINAIRE",
                           "origine_selection": "ALEATOIRE", "categorie_resultat": "CONFORME", "montant_redresse_total": 0.0}],
    ))

    H.append(dict(
        identite={"mf": "1000008JAM000", "matricule_fiscal": "1000008/J/A/M/000", "raison_sociale": "Omega Négoce SUARL",
                  "forme_juridique": "SUARL", "code_nat": "46.90", "libelle_nat": "Commerce de gros non spécialisé",
                  "gouvernorat": "Tunis", "date_debut_activite": "2024-11-18", "effectif": 0, "statut_oea": False, "centre_gestion": "CRCI"},
        gouvernorat_code=11, confiance=0.77, enjeu=(640000.0, 450000.0, 830000.0), action="VERIFICATION",
        resume="5 clients déclarent 3,2 MD d'achats auprès de l'entreprise en 2025 ; CA déclaré 2025 : 0,2 MD, aucun salarié. Enjeu estimé : 640 000 DT.",
        trajectoire=trajectoire({"2025-03": 30.0, "2025-06": 62.0, "2026-03": 84.0, "2026-08": 89.0}, 29.0, rng),
        contributions=[
            contrib("COH_CLIENTS_VS_CA", 45.5, 1.0, "5 clients déclarent 3,2 MD d'achats auprès de l'entreprise en 2025 ; CA déclaré 2025 : 0,2 MD.", ["dgi_annexe5", "dgi_declarations"], 5),
            contrib("PAI_MAHALANOBIS", 12.0, 0.8, "Profil atypique pour son secteur, surtout le CA par salarié (aucun salarié déclaré).", ["dgi_declarations"], 12),
            contrib("RES_FOURNISSEUR_PARTAGE", 10.4, 1.0, "Ses 5 clients ont commencé à lui acheter la même année, avec d'autres fournisseurs sans salarié.", ["graphe", "dgi_annexe5"], 5),
        ],
        pairs={"groupe": "46 × 0–2 salariés", "nb_pairs": 912, "indicateurs": [
            {"nom": "CA par salarié", "entreprise": None, "mediane_pairs": 95000.0, "p10": 30000.0, "p90": 240000.0}]},
        series=series(17000, 0, 2500, rng),
        controles_passes=[],
    ))
    return H


# ---------------------------------------------------------------- preuves et réseau
NOMS_CLIENTS_OMEGA = [("1000411KAM000", "Sigma Distribution SARL"), ("1000412KAM000", "Tau Matériaux SARL"),
                      ("1000413KAM000", "Upsilon Services SUARL"), ("1000414KAM000", "Phi Équipements SARL"),
                      ("1000415KAM000", "Chi Commerce SARL")]
IMPORTATEURS_FE00231 = [("1000311KAM000", "Kappa Equipements SARL", 275000.0, "2026-06-11"),
                        ("1000312KAM000", "Lambda Import SARL", 240000.0, "2026-06-09"),
                        ("1000313KAM000", "Mu Outillage SUARL", 198000.0, "2026-06-17"),
                        ("1000314KAM000", "Nu Machines SARL", 226000.0, "2026-06-22")]


def lignes_preuves(h: dict, c: dict, rng: random.Random) -> list[dict]:
    mf, code, n = h["identite"]["mf"], c["code_signal"], c["nb_preuves"]
    out = []
    for k in range(n):
        mois = MOIS[-1 - (k % 6)]
        jour = f"{mois}-{rng.randint(2, 27):02d}"
        if code in ("COH_ADEB_VS_CA",):
            m = round(rng.uniform(40000, 110000), 3)
            out.append({"source": "adeb_paiements", "ref": f"ORD-2026-{rng.randint(1000, 9999):07d}", "date": jour,
                        "libelle": "Ordonnance de paiement — Ministère de l'Équipement — Marché TUNEPS", "montant": m,
                        "champs": {"montant_ht": m, "retenue_tva_25": round(m * 0.19 * 0.25, 3), "nature_achat": "MARCHE_TUNEPS"}})
        elif code in ("COH_CLIENTS_VS_CA", "RES_COQUILLE"):
            cli, nom = NOMS_CLIENTS_OMEGA[k % len(NOMS_CLIENTS_OMEGA)]
            m = round(rng.uniform(450000, 800000), 3)
            out.append({"source": "employeur_annexe5", "ref": f"A5-2025-{cli}-{k + 1:06d}", "date": "2026-03-31",
                        "libelle": f"Annexe V 2025 — {nom} déclare des achats auprès de {h['identite']['raison_sociale']}", "montant": m,
                        "champs": {"mf_payeur": cli, "exercice": 2025, "retenue_is": round(m * 0.015, 3), "premiere_annee_relation": 2025}})
        elif code.startswith(("PAI_", "CHG_DEPOTS", "CHG_CA", "CHG_TVA")):
            s = next(x for x in h["series"] if x["mois"] == mois)
            champs = {"ca_total_declare": s["ca_declare"], "tva_deductible_biens_services_local": s["tva_deductible"]}
            if code == "CHG_DEPOTS":
                champs = {"statut_depot": "NON_DEPOSEE" if k % 2 else "DEPOSEE", "jours_retard": 0 if k % 2 else rng.randint(35, 80)}
            out.append({"source": "declarations_mensuelles", "ref": f"{mf}:{mois}", "date": f"{mois}-28",
                        "libelle": f"Déclaration mensuelle {mois}", "montant": s["ca_declare"], "champs": champs})
        else:  # douane
            if code == "COH_IMPORT_VS_CA" and mf == "1000001BAM000" and k == 0:
                out.append(dict(ALPHA_PREUVE_CONTRAT))
                continue
            fe = "FE00231" if mf == "1000001BAM000" else f"FE00{rng.randint(100, 899)}"
            q = rng.randint(2, 40)
            pu = round(rng.uniform(900, 25000), 3)
            champs = {"pays_origine": "CN" if fe == "FE00231" else rng.choice(["IT", "TR", "FR", "CN"]), "quantite": q, "unite": "U",
                      "prix_unitaire_tnd": pu, "circuit": rng.choice(["V", "V", "O"])}
            if code == "COH_VALEUR_REF":
                champs["prix_reference_tnd"] = round(pu / rng.uniform(0.45, 0.62), 3)
            out.append({"source": "douane_articles", "ref": f"2026/{rng.choice([301, 401, 402])}/00{rng.randint(10000, 99999)}-00{k % 9 + 1}",
                        "date": jour, "libelle": f"NDP 8479899700{k % 10} — Machines diverses — {champs['pays_origine']} — {fe}",
                        "montant": round(q * pu, 3), "champs": champs})
    return out


def reseau(h: dict, par_mf: dict) -> dict:
    mf, nom = h["identite"]["mf"], h["identite"]["raison_sociale"]
    centre = {"id": mf, "label": nom, "type": "ENTREPRISE", "segment": h["segment"], "est_coquille": mf == "1000008JAM000", "centre": True}
    if mf == "1000001BAM000":
        noeuds = [centre, {"id": "FE00231", "label": "Shenzhen Tools Co.", "type": "FOURNISSEUR_ETRANGER", "segment": None, "est_coquille": False, "centre": False}]
        aretes = [{"source": mf, "cible": "FE00231", "type_relation": "IMPORT_FOURNISSEUR", "montant": 310000.0, "premiere_date": "2026-06-04", "nouvelle": True}]
        for i, (omf, onom, m, d) in enumerate(IMPORTATEURS_FE00231):
            noeuds.append({"id": omf, "label": onom, "type": "ENTREPRISE", "segment": "PRIORITAIRE" if i < 2 else "SURVEILLANCE", "est_coquille": False, "centre": False})
            aretes.append({"source": omf, "cible": "FE00231", "type_relation": "IMPORT_FOURNISSEUR", "montant": m, "premiere_date": d, "nouvelle": True})
        noeuds.append({"id": "FE00088", "label": "Milano Meccanica SpA", "type": "FOURNISSEUR_ETRANGER", "segment": None, "est_coquille": False, "centre": False})
        aretes.append({"source": mf, "cible": "FE00088", "type_relation": "IMPORT_FOURNISSEUR", "montant": 145000.0, "premiere_date": "2019-04-02", "nouvelle": False})
        return {"noeuds": noeuds, "aretes": aretes}
    if mf == "1000008JAM000":
        noeuds, aretes = [centre], []
        for omf, onom in NOMS_CLIENTS_OMEGA:
            noeuds.append({"id": omf, "label": onom, "type": "ENTREPRISE", "segment": "SURVEILLANCE", "est_coquille": False, "centre": False})
            aretes.append({"source": omf, "cible": mf, "type_relation": "ACHAT_LOCAL_A5", "montant": 640000.0, "premiere_date": "2025-03-01", "nouvelle": True})
        return {"noeuds": noeuds, "aretes": aretes}
    if mf == "1000003DAM000":
        return {"noeuds": [centre, {"id": "AP0007", "label": "Ministère de l'Équipement", "type": "ACHETEUR_PUBLIC", "segment": None, "est_coquille": False, "centre": False},
                           {"id": "AP0023", "label": "Commune de Tunis", "type": "ACHETEUR_PUBLIC", "segment": None, "est_coquille": False, "centre": False}],
                "aretes": [{"source": "AP0007", "cible": mf, "type_relation": "PAIEMENT_PUBLIC", "montant": 610000.0, "premiere_date": "2023-02-14", "nouvelle": False},
                           {"source": "AP0023", "cible": mf, "type_relation": "PAIEMENT_PUBLIC", "montant": 230000.0, "premiere_date": "2025-11-03", "nouvelle": True}]}
    return {"noeuds": [centre, {"id": "FE00412", "label": "Anatolia Trade Ltd.", "type": "FOURNISSEUR_ETRANGER", "segment": None, "est_coquille": False, "centre": False}],
            "aretes": [{"source": mf, "cible": "FE00412", "type_relation": "IMPORT_FOURNISSEUR", "montant": 120000.0, "premiere_date": "2021-05-10", "nouvelle": False}]}


def construire() -> dict[str, object]:
    rng = random.Random(SEED)
    fichiers: dict[str, object] = {"api_stats_synthese.json": SYNTHESE_CONTRAT, "api_evaluation.json": EVALUATION_CONTRAT,
                                    "api_assistant.json": ASSISTANT_CONTRAT}
    items = []
    H = heros(rng)
    for h in H:
        t = h["trajectoire"]
        h["segment"] = t[-1]["segment"]
        score, prec = t[-1]["score"], t[-2]["score"]
        mf = h["identite"]["mf"]
        items.append({
            "mf": mf, "raison_sociale": h["identite"]["raison_sociale"], "code_nat": h["identite"]["code_nat"],
            "libelle_nat": h["identite"]["libelle_nat"], "gouvernorat": h["identite"]["gouvernorat"],
            "score": score, "score_mois_precedent": prec, "delta_score": round(score - prec, 1), "segment": h["segment"],
            "enjeu_estime": h["enjeu"][0], "enjeu_bas": h["enjeu"][1], "enjeu_haut": h["enjeu"][2],
            "rang_priorite": 0, "resume_fr": h["resume"], "action_suggeree": h["action"], "derniere_decision": None,
        })
        detail = {
            "identite": h["identite"], "score": score, "segment": h["segment"], "confiance": h["confiance"],
            "enjeu": {"estime": h["enjeu"][0], "bas": h["enjeu"][1], "haut": h["enjeu"][2]},
            "action_suggeree": h["action"], "resume_fr": h["resume"], "trajectoire": t,
            "contributions": h["contributions"], "pairs": h["pairs"], "series": h["series"],
            "decisions": [], "controles_passes": h["controles_passes"],
        }
        fichiers[f"api_entreprises_{mf}.json"] = detail
        fichiers[f"api_entreprises_{mf}_reseau.json"] = reseau(h, {})
        fichiers[f"api_entreprises_{mf}_decision.json"] = DECISION_CONTRAT
        for i, c in enumerate(h["contributions"]):
            p = {"code_signal": c["code_signal"], "fait_fr": c["fait_fr"], "lignes": lignes_preuves(h, c, rng)}
            fichiers[f"api_entreprises_{mf}_preuves_{c['code_signal']}.json"] = p
            if i == 0:
                fichiers[f"api_entreprises_{mf}_preuves.json"] = p

    # rang par priorité = score/100 × enjeu (comme le vrai calcul), sauf Alpha rang 1 comme dans le contrat
    items.sort(key=lambda it: (it["mf"] != "1000001BAM000", -(it["score"] / 100 * it["enjeu_estime"])))
    for r, it in enumerate(items, 1):
        it["rang_priorite"] = r
    alpha = next(it for it in items if it["mf"] == "1000001BAM000")
    alpha.update({"score": 76.0, "score_mois_precedent": 52.0, "delta_score": 24.0})
    fichiers["api_entreprises.json"] = {"total": len(items), "page": 1, "taille": 50, "items": items}
    return fichiers


def main() -> None:
    MOCK.mkdir(parents=True, exist_ok=True)
    fichiers = construire()
    for nom, contenu in fichiers.items():
        (MOCK / nom).write_text(json.dumps(contenu, ensure_ascii=False, indent=2), encoding="utf-8")
    (MOCK / "README.md").write_text(LISEZMOI, encoding="utf-8")
    print(f"{len(fichiers)} fichiers mock écrits dans {MOCK}")


LISEZMOI = """# Mocks de l'API Basira (écrits par C, régénérés par `uv run python -m api.mocks`)

Nom de fichier = chemin de la route avec `_` (sans les paramètres de requête).

| Route | Fichier |
|---|---|
| `GET /api/stats/synthese` | `api_stats_synthese.json` |
| `GET /api/entreprises` | `api_entreprises.json` (les 8 héros ; les filtres/tri sont appliqués par l'API en mode mock) |
| `GET /api/entreprises/{mf}` | `api_entreprises_{mf}.json` (8 héros) |
| `GET /api/entreprises/{mf}/preuves?signal=X` | `api_entreprises_{mf}_preuves_{X}.json` (un par contribution) ; `api_entreprises_{mf}_preuves.json` = 1re contribution |
| `GET /api/entreprises/{mf}/reseau` | `api_entreprises_{mf}_reseau.json` |
| `POST /api/entreprises/{mf}/decision` | `api_entreprises_{mf}_decision.json` |
| `POST /api/assistant` | `api_assistant.json` |
| `GET /api/evaluation` | `api_evaluation.json` (⚠️ exemples de format, pas des résultats) |

Alpha (`1000001BAM000`) reprend exactement les exemples du contrat §6.2 ; `trajectoire` et `series` sont étendues aux 24 mois.
"""

if __name__ == "__main__":
    main()

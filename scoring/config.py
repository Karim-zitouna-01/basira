"""Constantes partagées par le scoring et l'API (contrat d'intégration §1, §3, §5, §6)."""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# BASIRA_DATA_DIR permet de basculer entre les données de dev de C (data/dev) et celles de A/B (data).
DATA = Path(os.environ.get("BASIRA_DATA_DIR", ROOT / "data"))
if not DATA.is_absolute():
    DATA = ROOT / DATA
RAW = DATA / "raw"
GRAPHE = DATA / "graphe"
SIGNAUX = DATA / "signaux"
SCORES = DATA / "scores"
MOCK = ROOT / "data" / "mock"

SEED = 2026


def _mois(debut: str, fin: str) -> list[str]:
    a, m = map(int, debut.split("-"))
    out = []
    while f"{a:04d}-{m:02d}" <= fin:
        out.append(f"{a:04d}-{m:02d}")
        a, m = (a + 1, 1) if m == 12 else (a, m + 1)
    return out


MOIS = _mois("2024-09", "2026-08")
MOIS_COURANT = "2026-08"
MOIS_TEST = MOIS[-12:]  # 2025-09 → 2026-08


def mois_precedent(mois: str) -> str:
    a, m = map(int, mois.split("-"))
    return f"{a - 1:04d}-12" if m == 1 else f"{a:04d}-{m - 1:02d}"


def ecart_mois(debut: str, fin: str) -> int:
    a1, m1 = map(int, debut.split("-"))
    a2, m2 = map(int, fin.split("-"))
    return (a2 - a1) * 12 + (m2 - m1)


# Catalogue des signaux (contrat §3) : code → lentille
SIGNAUX_B = {
    "COH_IMPORT_VS_CA": "COHERENCE",
    "COH_CLIENTS_VS_CA": "COHERENCE",
    "COH_ADEB_VS_CA": "COHERENCE",
    "COH_TVA_IMPORT": "COHERENCE",
    "COH_VALEUR_REF": "COHERENCE",
    "CHG_CA": "CHANGEMENT",
    "CHG_IMPORTS": "CHANGEMENT",
    "CHG_TVA_DEDUCTIBLE": "CHANGEMENT",
    "CHG_NOUVEAUX_FOURNISSEURS": "CHANGEMENT",
    "CHG_NOUVELLES_CATEGORIES": "CHANGEMENT",
    "CHG_DEPOTS": "CHANGEMENT",
    "PAI_MARGE": "PAIRS",
    "PAI_MAHALANOBIS": "PAIRS",
    "RES_FOURNISSEUR_PARTAGE": "RESEAU",
    "RES_COQUILLE": "RESEAU",
    "RES_PROXIMITE_REDRESSE": "RESEAU",
}

# Combinaisons calculées par C : code → (signal a, signal b, fait_fr)
COMBINAISONS = {
    "CMB_IMPORT_X_NOUV_FOURN": (
        "CHG_IMPORTS",
        "CHG_NOUVEAUX_FOURNISSEURS",
        "Hausse des importations concentrée sur des fournisseurs nouveaux.",
    ),
    "CMB_COQUILLE_X_TVA": (
        "RES_COQUILLE",
        "CHG_TVA_DEDUCTIBLE",
        "Hausse de la TVA déductible liée à des achats auprès de fournisseurs coquilles.",
    ),
}

LENTILLES = {**SIGNAUX_B, **{c: "COMBINAISON" for c in COMBINAISONS}}
FEATURES = list(LENTILLES)  # 16 signaux + 2 combinaisons, ordre figé
NOUVEAU_SCHEMA = "NOUVEAU_SCHEMA"
SEUIL_ACTIF = 0.5

SEUILS = {"PRIORITAIRE": 70, "SURVEILLANCE": 40, "CONFIANCE": 15}
BONUS_MAX = 15.0
ENJEU_VERIFICATION = 100_000.0
SIGNAUX_DOUANE = ("COH_VALEUR_REF", "CHG_NOUVELLES_CATEGORIES")

# Règle statique type SAR (évaluation) : 5 signaux « classiques » à poids égaux + bonus de taille
SIGNAUX_SAR = ("COH_IMPORT_VS_CA", "COH_CLIENTS_VS_CA", "CHG_CA", "CHG_DEPOTS", "PAI_MARGE")
BONUS_TAILLE_SAR = 0.2  # × classe de taille (0 : 0–2, 1 : 3–9, 2 : 10–49, 3 : 50+)
TOP_N = 50
NB_TIRAGES_ALEATOIRES = 100
SCENARIOS_NON_FRAUDE = ("AUCUN", "CROISSANCE_LEGITIME", "CITOYEN_MODELE")

SEGMENTS = ("PRIORITAIRE", "SURVEILLANCE", "NORMAL", "CONFIANCE")
DECISIONS = {
    "AUCUNE": "Aucune action",
    "RELANCE": "Relance de conformité volontaire",
    "DEMANDE_INFO": "Demande d'information / contrôle sur pièces",
    "VERIFICATION": "Vérification approfondie",
    "SIGNALEMENT_DOUANE": "Signalement à la douane",
}

GOUVERNORATS = {
    11: "Tunis", 12: "Ariana", 13: "Ben Arous", 14: "Manouba", 15: "Nabeul", 16: "Zaghouan",
    17: "Bizerte", 21: "Béja", 22: "Jendouba", 23: "Le Kef", 24: "Siliana", 31: "Sousse",
    32: "Monastir", 33: "Mahdia", 34: "Sfax", 41: "Kairouan", 42: "Kasserine", 43: "Sidi Bouzid",
    51: "Gabès", 52: "Médenine", 53: "Tataouine", 61: "Gafsa", 62: "Tozeur", 63: "Kébili",
}

HEROS = {
    "1000001BAM000": "Alpha SARL",
    "1000002CAM000": "Beta Import SUARL",
    "1000003DAM000": "Gamma Travaux SA",
    "1000004EAM000": "Delta Trade SARL",
    "1000005FAM000": "Epsilon Textile SARL",
    "1000006GAM000": "Zeta Industries SA",
    "1000007HAM000": "Eta Pharma SA",
    "1000008JAM000": "Omega Négoce SUARL",
}

# Assistant (LLM distant, compatible OpenAI). URL vide → mode modele_texte.
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "")
LLM_MODEL = os.environ.get("LLM_MODEL", "qwen3.5:9b")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "ollama")
LLM_TOOLS = os.environ.get("LLM_TOOLS", "1") == "1"
LLM_TIMEOUT = float(os.environ.get("LLM_TIMEOUT", "30"))
LLM_THINKING = os.environ.get("LLM_THINKING", "0") == "1"  # 0 → enable_thinking=false (Qwen 3.5, latence)
LLM_MAX_TOKENS = int(os.environ.get("LLM_MAX_TOKENS", "700"))


def fmt_dt(montant: float) -> str:
    """420000 → « 420 000 DT » ; ≥ 1 MD → « 3,2 MD »."""
    if montant is None:
        return "—"
    if abs(montant) >= 1_000_000:
        return f"{montant / 1_000_000:.1f}".replace(".", ",") + " MD"
    return f"{round(montant):,}".replace(",", " ") + " DT"

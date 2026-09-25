"""Lecture des fichiers produits par A (data/raw, data/graphe) et B (data/signaux)."""

import pandas as pd

from . import config

# colonnes à lire en texte (identifiants et codes)
_TEXTE = {"mf", "mf_payeur", "mf_fournisseur", "mf_importateur", "mf_beneficiaire", "code_nat", "mois", "source", "cible",
          "id_article", "num_declaration", "code_ndp", "chapitre_sh", "id_fournisseur_etranger", "id_ligne", "num_ordonnance",
          "id_acheteur_public", "id_fournisseur", "periode_debut", "periode_fin", "mois_debut_scenario", "code_sh6"}


def lire_csv(nom: str, dossier=None, obligatoire: bool = True) -> pd.DataFrame:
    chemin = (dossier or config.RAW) / nom
    if not chemin.exists():
        if obligatoire:
            raise FileNotFoundError(chemin)
        return pd.DataFrame()
    entete = pd.read_csv(chemin, nrows=0).columns
    return pd.read_csv(chemin, dtype={c: str for c in entete if c in _TEXTE}, keep_default_na=True)


def signaux() -> pd.DataFrame:
    return pd.read_parquet(config.SIGNAUX / "signaux.parquet")


def enjeux() -> pd.DataFrame:
    return pd.read_parquet(config.SIGNAUX / "enjeux.parquet")


def parquet_optionnel(chemin) -> pd.DataFrame:
    return pd.read_parquet(chemin) if chemin.exists() else pd.DataFrame()


def contribuables() -> pd.DataFrame:
    return lire_csv("contribuables.csv")


def controles() -> pd.DataFrame:
    return lire_csv("historique_controles.csv")


def verite_terrain() -> pd.DataFrame:
    """⚠️ Réservé à scoring.evaluate : jamais pour l'entraînement ni le choix des seuils."""
    return lire_csv("verite_terrain.csv")

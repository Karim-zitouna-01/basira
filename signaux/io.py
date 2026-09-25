"""Explicit allowlist loading: ground truth is never opened or enumerated."""

from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa


class InputError(ValueError):
    """An upstream table violates the agreed contract."""


# Only fields consumed by B are required. Other official columns are preserved.
COLUMNS = {
    "contribuables": "mf code_nat section_nat effectif_declare date_debut_activite",
    "declarations_mensuelles": "mf mois statut_depot date_limite date_depot ca_total_declare tva_collectee tva_deductible_immobilisations tva_deductible_biens_services_local tva_deductible_import tva_retenue_source_subie",
    "douane_declarations": "num_declaration mf_importateur date_enregistrement",
    "douane_articles": "id_article num_declaration code_ndp chapitre_sh id_fournisseur_etranger valeur_caf_tnd prix_unitaire_tnd",
    "douane_liquidation": "id_article code_taxe montant_tnd",
    "employeur_annexe5": "id_ligne mf_payeur mf_fournisseur exercice montant_ttc premiere_annee_relation",
    "employeur_annexe2": "id_ligne mf_payeur type_id_beneficiaire id_beneficiaire exercice montant_brut",
    "employeur_annexe1_synthese": "mf exercice nb_salaries",
    "adeb_paiements": "num_ordonnance mf_beneficiaire date_paiement montant_ht montant_tva retenue_tva_25",
    "ref_ndp": "code_ndp prix_reference_tnd",
    "metriques_noeuds": "mf mois nb_clients_partageant_fournisseur_nouveau part_achats_coquilles est_profil_coquille distance_entite_redressee",
    "historique_controles": "id_controle mf date_notification_resultats categorie_resultat",
}
NUMBERS = set(
    "effectif_declare ca_total_declare tva_collectee tva_deductible_immobilisations tva_deductible_biens_services_local tva_deductible_import tva_retenue_source_subie valeur_caf_tnd prix_unitaire_tnd montant_tnd exercice montant_ttc premiere_annee_relation montant_brut nb_salaries montant_ht montant_tva retenue_tva_25 prix_reference_tnd nb_clients_partageant_fournisseur_nouveau part_achats_coquilles distance_entite_redressee".split()
)
KEYS = {
    "contribuables": ["mf"],
    "declarations_mensuelles": ["mf", "mois"],
    "douane_declarations": ["num_declaration"],
    "douane_articles": ["id_article"],
    "douane_liquidation": ["id_article", "code_taxe"],
    "employeur_annexe5": ["id_ligne"],
    "employeur_annexe2": ["id_ligne"],
    "employeur_annexe1_synthese": ["mf", "exercice"],
    "adeb_paiements": ["num_ordonnance"],
    "ref_ndp": ["code_ndp"],
    "metriques_noeuds": ["mf", "mois"],
    "historique_controles": ["id_controle"],
}


def load_tables(data_dir: Path, allow_missing=False):
    tables, warnings = {}, []
    for name, fields in COLUMNS.items():
        path = data_dir / ("graphe" if name == "metriques_noeuds" else "raw") / f"{name}.csv"
        required = fields.split()
        if not path.exists():
            if not allow_missing or name == "contribuables":
                raise InputError(f"Fichier manquant : {path}. Voir README, ou --allow-missing.")
            frame = pd.DataFrame(columns=required)
            warnings.append(f"Source absente : {name}; signaux associés neutralisés.")
        else:
            frame = pd.read_csv(path, dtype=str, keep_default_na=False)
            missing = set(required) - set(frame.columns)
            if missing:
                raise InputError(f"{path.name}: colonnes manquantes : {sorted(missing)}")
        if frame.duplicated(KEYS[name]).any():
            raise InputError(f"{path.name}: clé dupliquée {KEYS[name]}")
        for key in KEYS[name]:
            if frame[key].eq("").any():
                raise InputError(f"{path.name}: clé vide : {key}")
        for column in set(frame.columns) & NUMBERS:
            try:
                frame[column] = pd.to_numeric(frame[column].replace("", np.nan))
            except ValueError as exc:
                raise InputError(f"{path.name}: nombre invalide dans {column}") from exc
            # Numeric blanks are permitted only for unfiled declaration placeholders.
            allowed_blank = (
                frame["statut_depot"].eq("NON_DEPOSEE")
                if name == "declarations_mensuelles"
                else False
            )
            bad = ~np.isfinite(frame[column])
            if (bad & ~np.asarray(allowed_blank)).any():
                raise InputError(f"{path.name}: nombre manquant/non fini dans {column}")
            if (frame[column].dropna() < 0).any():
                raise InputError(f"{path.name}: nombre négatif dans {column}")
            frame[column] = frame[column].fillna(0.0)
        for column in frame.columns:
            if column.startswith("date_") and column in required:
                values = frame[column].replace("", pd.NaT)
                try:
                    frame[column] = pd.to_datetime(values, format="%Y-%m-%d", errors="raise")
                except (ValueError, TypeError) as exc:
                    raise InputError(f"{path.name}: date invalide dans {column}") from exc
                if column != "date_depot" and frame[column].isna().any():
                    raise InputError(f"{path.name}: date obligatoire vide : {column}")
        if "mois" in required and not frame["mois"].str.fullmatch(r"\d{4}-(0[1-9]|1[0-2])").all():
            raise InputError(f"{path.name}: mois invalide (AAAA-MM requis)")
        frame.attrs["source_missing"] = not path.exists()
        tables[name] = frame
    validate_relationships(tables)
    return tables, warnings


def validate_relationships(tables):
    ids = set(tables["contribuables"]["mf"])
    for name, frame in tables.items():
        for field in ("mf", "mf_importateur", "mf_payeur", "mf_fournisseur", "mf_beneficiaire"):
            if field in frame and not set(frame[field]).issubset(ids):
                raise InputError(f"{name}: {field} référence un contribuable inconnu")
    for child, foreign, parent, key in (
        ("douane_articles", "num_declaration", "douane_declarations", "num_declaration"),
        ("douane_liquidation", "id_article", "douane_articles", "id_article"),
        ("douane_articles", "code_ndp", "ref_ndp", "code_ndp"),
    ):
        if tables[parent].attrs.get("source_missing", False):
            continue
        if not set(tables[child][foreign]).issubset(set(tables[parent][key])):
            raise InputError(f"{child}: référence {foreign} absente de {parent}")
    monthly = tables["declarations_mensuelles"]
    if not monthly.statut_depot.isin(["DEPOSEE", "NON_DEPOSEE"]).all():
        raise InputError("declarations_mensuelles: statut_depot inconnu")
    if (monthly.statut_depot.eq("DEPOSEE") & monthly.date_depot.isna()).any():
        raise InputError("declarations_mensuelles: DEPOSEE sans date_depot")
    graph = tables["metriques_noeuds"]
    if not graph.part_achats_coquilles.between(0, 1).all():
        raise InputError("metriques_noeuds: part_achats_coquilles doit être dans [0,1]")


SIGNAL_SCHEMA = pa.schema(
    [
        ("mf", pa.string()),
        ("mois", pa.string()),
        ("code_signal", pa.string()),
        ("lentille", pa.string()),
        ("valeur_brute", pa.float64()),
        ("unite", pa.string()),
        ("valeur_norm", pa.float64()),
        ("fait_fr", pa.string()),
        ("sources", pa.list_(pa.string())),
        ("preuves", pa.list_(pa.string())),
    ]
)

"""Small deterministic integration fixtures; this is not Member A's generator.

No ground truth is written. No real file is overwritten. Hero scenarios are
illustrations for testing B, not promised scores or calibrated fraud populations.
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from .io import COLUMNS

HEROES = [
    "1000001BAM000",
    "1000002CAM000",
    "1000003DAM000",
    "1000004EAM000",
    "1000005FAM000",
    "1000006GAM000",
    "1000007HAM000",
    "1000008JAM000",
]
NAMES = [
    "Alpha SARL",
    "Beta Import SUARL",
    "Gamma Travaux SA",
    "Delta Trade SARL",
    "Epsilon Textile SARL",
    "Zeta Industries SA",
    "Eta Pharma SA",
    "Omega Négoce SUARL",
]


def create_demo(data_dir: Path, n=80):
    if n < 40:
        raise ValueError("Au moins 40 entreprises pour tester les pairs.")
    if any((data_dir / folder).exists() for folder in ("raw", "graphe")):
        raise FileExistsError(f"{data_dir}: raw/graphe existe déjà; choisir un répertoire vide.")
    (data_dir / "raw").mkdir(parents=True)
    (data_dir / "graphe").mkdir()
    ids = HEROES + [f"{1_000_001 + i:07d}KAM000" for i in range(8, n)]
    tables = {name: [] for name in COLUMNS}
    for i, mf in enumerate(ids):
        tables["contribuables"].append(
            {
                "mf": mf,
                "raison_sociale": NAMES[i] if i < 8 else f"Témoin {i}",
                "code_nat": "46.69",
                "section_nat": "G",
                "effectif_declare": 0 if i == 7 else 20 + i % 20,
                "date_debut_activite": "2024-01-01" if i == 7 else "2014-01-01",
            }
        )
    tables["ref_ndp"] = [{"code_ndp": "85171200005", "prix_reference_tnd": 100}]
    months = pd.period_range("2023-01", "2026-08", freq="M")
    for i, mf in enumerate(ids):
        previous_vat = 0.0
        for k, month in enumerate(months):
            seasonal = 1.0 + 0.025 * np.sin(2 * np.pi * k / 12)
            ca = (80_000 + 600 * (i % 20)) * seasonal
            imports = ca * (0.45 + 0.002 * (i % 7))
            local_vat = ca * 0.25 * 0.19
            if i == 0 and month >= pd.Period("2026-06", "M"):
                imports *= 7  # Strong enough after fiscal publication lag; deliberately not x3.4.
            if i == 3:
                ca = 0.0 if month < pd.Period("2026-06", "M") else 1000.0
                imports = 0.0 if month < pd.Period("2026-06", "M") else 400_000.0
                local_vat = 0.0
            if i == 4 and month >= pd.Period("2025-03", "M"):
                imports = ca * 0.73
            if i == 5 and month >= pd.Period("2026-06", "M"):
                ca *= 7
                imports *= 7
                local_vat *= 7
            if i == 7:
                ca, imports, local_vat = 1000.0, 0.0, 0.0
            if 8 <= i < 13 and month >= pd.Period("2025-03", "M"):
                local_vat *= 2
            public = 200_000.0 if i == 2 else 0.0
            missing = i == 3 and month < pd.Period("2026-06", "M")
            due = pd.Timestamp(year=(month + 1).year, month=(month + 1).month, day=28)
            supplier = f"FE{i:05d}"
            if (i == 0 or 8 <= i < 12) and month >= pd.Period("2026-06", "M"):
                supplier = f"FE0023{k % 3 + 1}"
            tables["declarations_mensuelles"].append(
                {
                    "mf": mf,
                    "mois": str(month),
                    "statut_depot": "NON_DEPOSEE" if missing else "DEPOSEE",
                    "date_limite": due.strftime("%Y-%m-%d"),
                    "date_depot": "" if missing else due.strftime("%Y-%m-%d"),
                    "ca_total_declare": ca,
                    "tva_collectee": ca * 0.19,
                    "tva_deductible_immobilisations": 0.0,
                    "tva_deductible_biens_services_local": local_vat,
                    "tva_deductible_import": previous_vat,
                    "tva_retenue_source_subie": 0.0,
                }
            )
            if imports:
                number = f"{month.year}/301/{i:05d}{month.month:02d}"
                article = number + "-001"
                tables["douane_declarations"].append(
                    {
                        "num_declaration": number,
                        "mf_importateur": mf,
                        "date_enregistrement": month.start_time.strftime("%Y-%m-%d"),
                    }
                )
                tables["douane_articles"].append(
                    {
                        "id_article": article,
                        "num_declaration": number,
                        "code_ndp": "85171200005",
                        "chapitre_sh": "85",
                        "id_fournisseur_etranger": supplier,
                        "valeur_caf_tnd": imports,
                        "prix_unitaire_tnd": 50.0 if i == 1 else 100.0,
                    }
                )
                tables["douane_liquidation"].append(
                    {"id_article": article, "code_taxe": "105", "montant_tnd": imports * 0.19}
                )
            previous_vat = imports * 0.19
            if public:
                tables["adeb_paiements"].append(
                    {
                        "num_ordonnance": f"ORD-{mf}-{month}",
                        "mf_beneficiaire": mf,
                        "date_paiement": month.start_time.strftime("%Y-%m-%d"),
                        "montant_ht": public,
                        "montant_tva": public * 0.19,
                        "retenue_tva_25": public * 0.19 * 0.25,
                    }
                )
            if month >= pd.Period("2024-09", "M"):
                shared = (i == 0 or 8 <= i < 12) and month >= pd.Period("2026-06", "M")
                shell = 8 <= i < 13 and month >= pd.Period("2026-03", "M")
                tables["metriques_noeuds"].append(
                    {
                        "mf": mf,
                        "mois": str(month),
                        "nb_clients_partageant_fournisseur_nouveau": 4 if shared else 0,
                        "part_achats_coquilles": 1.0 if shell else 0.0,
                        "est_profil_coquille": str(
                            i == 7 and month >= pd.Period("2026-03", "M")
                        ).lower(),
                        "distance_entite_redressee": 99,
                    }
                )
        for year in (2023, 2024, 2025):
            tables["employeur_annexe1_synthese"].append(
                {"mf": mf, "exercice": year, "nb_salaries": 0 if i == 7 else 20 + i % 20}
            )
            if 8 <= i < 13:
                tables["employeur_annexe5"].append(
                    {
                        "id_ligne": f"A5-{year}-{mf}-000001",
                        "mf_payeur": mf,
                        "mf_fournisseur": ids[7] if year == 2025 else ids[6],
                        "exercice": year,
                        "montant_ttc": 500_000.0 if year == 2025 else 5000.0,
                        "premiere_annee_relation": 2025 if year == 2025 else 2023,
                    }
                )
    for name, rows in tables.items():
        frame = pd.DataFrame(rows) if rows else pd.DataFrame(columns=COLUMNS[name].split())
        folder = "graphe" if name == "metriques_noeuds" else "raw"
        frame.to_csv(data_dir / folder / f"{name}.csv", index=False, float_format="%.3f")
    (data_dir / "raw" / "README.md").write_text(
        "Jeu jouet déterministe du lot B. Ne remplace pas le générateur de A.\n", encoding="utf-8"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--n", type=int, default=80)
    args = parser.parse_args()
    create_demo(args.data_dir, args.n)
    print(f"Jeu jouet créé : {args.data_dir} ({args.n} entreprises)")


if __name__ == "__main__":
    main()

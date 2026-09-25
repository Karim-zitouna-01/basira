"""One monthly snapshot at a time; arithmetic is vectorized over companies."""

import numpy as np
import pandas as pd

from .catalogue import CATALOGUE
from .data import Dataset
from .evidence import Evidence
from .exposure import estimate_exposure
from .peers import build_groups, compute_peers
from .statistics import ewma_z, french_amount, growth, normalize_z, ratio


class Engine:
    def __init__(self, tables, end="2026-08"):
        earliest = tables["declarations_mensuelles"].mois.min()
        start = earliest if isinstance(earliest, str) else "2023-09"
        self.data = Dataset(tables, start, end)
        self.groups = build_groups(self.data.companies)
        # Months for which a return was due (a row exists whatever its status), used to gate the
        # coherence signals: an unfiled return declares nothing, it must not switch the check off.
        declarations = tables["declarations_mensuelles"]
        self.due = np.isfinite(self.data.matrix(declarations.assign(_due=1.0), "_due", fill=np.nan))

    def calculate(self, month):
        d = self.data
        s = d.snapshot(month)
        matrix = {
            name: d.matrix(s.declarations, name, fill=np.nan)
            for name in (
                "ca_total_declare",
                "tva_collectee",
                "tva_deductible_import",
                "tva_deductible_biens_services_local",
                "tva_deductible_immobilisations",
                "tva_retenue_source_subie",
            )
        }
        sums = {name: d.sum_window(values, s.fiscal, 12) for name, values in matrix.items()}
        ca = sums["ca_total_declare"]
        present = np.isfinite(matrix["ca_total_declare"])
        complete = d.sum_window(present, s.fiscal, 12) == 12
        due_complete = d.sum_window(self.due, s.fiscal, 12) == 12
        in_exercise = np.array([str(m).startswith(str(s.exercise)) for m in d.months])
        annual_due = self.due[:, in_exercise].sum(axis=1) == 12
        history_count = present[:, d.months <= str(s.fiscal)].sum(axis=1)
        imports = d.sum_window(d.import_matrix, s.fiscal, 12)
        import_recent = d.sum_window(d.import_matrix, s.fiscal, 6)
        import_previous = d.sum_window(d.import_matrix, s.fiscal - 6, 6)
        ca_recent = d.sum_window(matrix["ca_total_declare"], s.fiscal, 6)
        ca_previous = d.sum_window(matrix["ca_total_declare"], s.fiscal - 6, 6)
        growth_gap = growth(import_recent, import_previous) - growth(ca_recent, ca_previous)
        clients, annual_ttc, annual_ht, annual_complete = d.annual_totals(s)
        public = d.sum_window(d.public_matrix, s.fiscal, 12)
        public_retention = d.sum_window(d.retention_matrix, s.fiscal, 12)
        # Data dictionary: fiscal period t deducts customs VAT paid in t-1.
        customs_vat = d.sum_window(d.vat_matrix, s.fiscal - 1, 12)
        imports_vat = sums["tva_deductible_import"]
        local_vat = sums["tva_deductible_biens_services_local"]
        paid_ratio = ratio(clients, annual_ttc)
        public_ratio = ratio(public, ca)
        vat_ratio = ratio(imports_vat, customs_vat)
        reference_rows = d.articles.loc[
            d.articles.mois.between(str(month - 5), str(month))
            & (d.articles.prix_reference_tnd > 0)
        ].copy()
        reference_rows["weighted"] = (
            reference_rows.valeur_caf_tnd
            * reference_rows.prix_unitaire_tnd
            / reference_rows.prix_reference_tnd
        )
        weights = d.aggregate(reference_rows, "valeur_caf_tnd")
        reference_ratio = ratio(d.aggregate(reference_rows, "weighted"), weights)
        signals = {
            "COH_IMPORT_VS_CA": (growth_gap, np.clip(growth_gap / 200, 0, 1) * due_complete),
            "COH_CLIENTS_VS_CA": (
                paid_ratio,
                np.clip((paid_ratio - 1) / 2, 0, 1) * annual_due,
            ),
            "COH_ADEB_VS_CA": (public_ratio, np.clip((public_ratio - 0.9) / 0.6, 0, 1) * due_complete),
            "COH_TVA_IMPORT": (vat_ratio, np.clip((vat_ratio - 1.1) / 0.9, 0, 1) * due_complete),
            "COH_VALEUR_REF": (
                reference_ratio,
                np.clip((0.9 - reference_ratio) / 0.4, 0, 1) * (weights > 0),
            ),
        }
        for code, source, two_sided in (
            ("CHG_CA", matrix["ca_total_declare"], True),
            ("CHG_IMPORTS", d.import_matrix, False),
            ("CHG_TVA_DEDUCTIBLE", matrix["tva_deductible_biens_services_local"], False),
        ):
            endpoint = month if code == "CHG_IMPORTS" else s.fiscal
            z = ewma_z(d.history(source, endpoint), two_sided=two_sided)
            if code == "CHG_IMPORTS":
                # Calendar zeros before the dataset begins are not observed history.
                coverage = d.tables["declarations_mensuelles"]
                coverage = coverage.loc[coverage.mois <= str(s.fiscal)].groupby("mf").size()
                eligible = coverage.reindex(d.ids, fill_value=0).to_numpy() >= 6
                z = np.where(eligible, z, 0)
            signals[code] = (z, normalize_z(z))
        suppliers, chapters, foreign, local, categories = d.novelty(s)
        failures, failure_rows = d.filing_failures(s)
        signals.update(
            {
                "CHG_NOUVEAUX_FOURNISSEURS": (suppliers, np.clip(suppliers / 5, 0, 1)),
                "CHG_NOUVELLES_CATEGORIES": (chapters, np.clip(chapters / 3, 0, 1)),
                "CHG_DEPOTS": (failures, np.clip(failures / 4, 0, 1)),
            }
        )
        total_vat = imports_vat + local_vat + sums["tva_deductible_immobilisations"]
        peer_signals, peer_stats, peer_margin, dominant, indicators = compute_peers(
            self.groups,
            month,
            ca,
            imports,
            local_vat,
            total_vat,
            sums["tva_collectee"],
            d.headcount(s),
            complete,
            d.companies,
        )
        signals.update(peer_signals)
        shared = s.graph.nb_clients_partageant_fournisseur_nouveau.fillna(0).to_numpy(float)
        shell = s.graph.part_achats_coquilles.fillna(0).to_numpy(float)
        distance = s.graph.distance_entite_redressee.fillna(99).to_numpy(float)
        proximity = np.select([distance == 1, distance == 2, distance == 3], [1.0, 0.5, 0.2], 0.0)
        signals.update(
            {
                "RES_FOURNISSEUR_PARTAGE": (shared, np.clip(shared / 5, 0, 1)),
                "RES_COQUILLE": (shell * 100, np.clip(shell / 0.3, 0, 1)),
                "RES_PROXIMITE_REDRESSE": (distance, proximity),
            }
        )
        evidence = Evidence(d, s, foreign, local, categories, failure_rows)
        frames, audit, issues = [], [], []
        exists = (d.companies.date_debut_activite <= month.end_time).to_numpy()
        for spec in CATALOGUE:
            raw, normalized = signals[spec.code]
            raw = np.nan_to_num(raw, nan=0.0, posinf=0.0, neginf=0.0)
            normalized = np.clip(np.nan_to_num(normalized), 0, 1) * exists
            # Missing operands must yield both zero raw and zero normalized.
            valid = np.ones(len(d.ids), bool)
            if spec.code in ("COH_IMPORT_VS_CA", "COH_ADEB_VS_CA", "COH_TVA_IMPORT"):
                valid &= due_complete
            if spec.code == "COH_CLIENTS_VS_CA":
                valid &= annual_due
            dependencies = {
                "COH_IMPORT_VS_CA": (
                    "douane_articles",
                    "douane_declarations",
                    "declarations_mensuelles",
                ),
                "COH_CLIENTS_VS_CA": ("employeur_annexe5", "declarations_mensuelles"),
                "COH_ADEB_VS_CA": ("adeb_paiements", "declarations_mensuelles"),
                "COH_TVA_IMPORT": ("douane_liquidation", "declarations_mensuelles"),
                "COH_VALEUR_REF": ("douane_articles", "ref_ndp"),
                "CHG_CA": ("declarations_mensuelles",),
                "CHG_IMPORTS": ("douane_articles",),
                "CHG_TVA_DEDUCTIBLE": ("declarations_mensuelles",),
                "CHG_DEPOTS": ("declarations_mensuelles",),
                "PAI_MARGE": ("declarations_mensuelles", "douane_articles"),
                "PAI_MAHALANOBIS": ("declarations_mensuelles", "douane_articles"),
            }.get(spec.code, ("metriques_noeuds",) if spec.lens == "RESEAU" else ())
            if any(d.tables[name].attrs.get("source_missing", False) for name in dependencies):
                valid[:] = False
            raw = np.where(valid & exists, raw, 0.0)
            normalized = np.where(valid, normalized, 0.0)
            facts = np.full(len(d.ids), "", dtype=object)
            proofs = [[] for _ in d.ids]
            for i in np.flatnonzero(normalized >= 0.5):
                fact, refs, count = evidence.fact(d.ids[i], spec.code, dominant[i])
                # Aggregate amounts are displayed only when ALL their raw rows
                # fit inside the proof cap. Otherwise Evidence.fact cites one row.
                if count <= 50 and refs:
                    if spec.code == "COH_IMPORT_VS_CA":
                        fact = (
                            f"Importations sur six mois : {french_amount(import_recent[i])}, "
                            f"contre {french_amount(import_previous[i])} sur les six mois précédents. "
                            f"CA déclaré : {french_amount(ca_recent[i])}, "
                            f"contre {french_amount(ca_previous[i])}."
                        )
                    elif spec.code == "COH_CLIENTS_VS_CA":
                        fact = (
                            f"Les clients déclarent {french_amount(clients[i])} de paiements "
                            f"pour l'exercice {s.exercise}; "
                            f"CA TTC déclaré : {french_amount(annual_ttc[i])}."
                        )
                    elif spec.code == "COH_ADEB_VS_CA":
                        fact = (
                            f"Paiements publics HT sur douze mois : {french_amount(public[i])}; "
                            f"CA déclaré : {french_amount(ca[i])}."
                        )
                    elif spec.code == "COH_TVA_IMPORT":
                        fact = (
                            f"TVA déduite sur importations : {french_amount(imports_vat[i])}; "
                            f"TVA douanière de la période alignée : {french_amount(customs_vat[i])}."
                        )
                facts[i], proofs[i] = fact, refs
                if not refs:
                    issues.append(
                        {
                            "mf": d.ids[i],
                            "mois": str(month),
                            "code_signal": spec.code,
                            "probleme": "Métrique active sans ligne source justificative; vérifier le lot A.",
                        }
                    )
                audit.append(
                    {
                        "mf": d.ids[i],
                        "mois": str(month),
                        "code_signal": spec.code,
                        "valeur_brute": float(raw[i]),
                        "valeur_norm": float(normalized[i]),
                        "nb_preuves_disponibles": count,
                        "nb_preuves_affichees": len(refs),
                        "periode_fiscale_fin": str(s.fiscal),
                        "exercice_disponible": s.exercise,
                        "groupe": self.groups.iloc[i].groupe,
                        "variable_dominante": dominant[i] if spec.code == "PAI_MAHALANOBIS" else "",
                        "ca_12m": float(ca[i]),
                        "imports_12m": float(imports[i]),
                        "clients_ttc_exercice": float(clients[i]),
                        "ca_ttc_exercice": float(annual_ttc[i]),
                        "retenue_tva_adeb": float(public_retention[i]),
                        "retenue_tva_declaree": float(sums["tva_retenue_source_subie"][i]),
                    }
                )
            frames.append(
                pd.DataFrame(
                    {
                        "mf": d.ids,
                        "mois": str(month),
                        "code_signal": spec.code,
                        "lentille": spec.lens,
                        "valeur_brute": raw,
                        "unite": spec.unit,
                        "valeur_norm": normalized,
                        "fait_fr": facts,
                        "sources": [list(spec.sources) for _ in d.ids],
                        "preuves": proofs,
                    }
                )
            )
        source_count = (
            (history_count > 0).astype(float) + (imports > 0) + (clients > 0) + (public > 0)
        )
        exposure = estimate_exposure(
            d.ids,
            month,
            ca,
            imports,
            clients,
            annual_ttc,
            annual_ht,
            annual_complete,
            public,
            imports_vat,
            customs_vat,
            local_vat,
            shell,
            peer_margin,
            history_count,
            source_count,
        )
        return pd.concat(frames, ignore_index=True), exposure, peer_stats, audit, issues

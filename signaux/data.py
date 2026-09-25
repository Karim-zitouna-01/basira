"""Calendar-aligned matrices and data snapshots available at each month end."""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .statistics import available_exercise


@dataclass
class Snapshot:
    month: pd.Period
    fiscal: pd.Period
    declarations: pd.DataFrame
    annual5: pd.DataFrame
    annual2: pd.DataFrame
    employees: pd.DataFrame
    graph: pd.DataFrame
    exercise: int


class Dataset:
    def __init__(self, tables, start="2023-01", end="2026-08"):
        self.tables = tables
        self.companies = tables["contribuables"].sort_values("mf").set_index("mf")
        self.ids = self.companies.index
        self.months = pd.period_range(start, end, freq="M").astype(str)
        self.articles = (
            tables["douane_articles"]
            .merge(
                tables["douane_declarations"][
                    ["num_declaration", "mf_importateur", "date_enregistrement"]
                ],
                on="num_declaration",
                validate="many_to_one",
            )
            .rename(columns={"mf_importateur": "mf"})
        )
        self.articles["mois"] = self.articles.date_enregistrement.dt.strftime("%Y-%m")
        self.articles = self.articles.merge(
            tables["ref_ndp"],
            on="code_ndp",
            how="left",
            validate="many_to_one",
            suffixes=("", "_ref"),
        )
        self.customs_vat = (
            tables["douane_liquidation"]
            .loc[tables["douane_liquidation"].code_taxe.str.zfill(3).eq("105")]
            .merge(
                self.articles[["id_article", "mf", "mois"]], on="id_article", validate="many_to_one"
            )
        )
        self.public = tables["adeb_paiements"].rename(columns={"mf_beneficiaire": "mf"}).copy()
        self.public["mois"] = self.public.date_paiement.dt.strftime("%Y-%m")
        self.import_matrix = self.matrix(self.articles, "valeur_caf_tnd")
        self.vat_matrix = self.matrix(self.customs_vat, "montant_tnd")
        self.public_matrix = self.matrix(self.public, "montant_ht")
        self.retention_matrix = self.matrix(self.public, "retenue_tva_25")

    def matrix(self, frame, value, fill=0.0):
        if frame.empty:
            return np.full((len(self.ids), len(self.months)), fill, float)
        pivot = frame.pivot_table(index="mf", columns="mois", values=value, aggfunc="sum")
        return pivot.reindex(index=self.ids, columns=self.months).fillna(fill).to_numpy(float)

    def sum_window(self, matrix, end, width):
        mask = (self.months >= str(end - width + 1)) & (self.months <= str(end))
        return np.nansum(matrix[:, mask], axis=1)

    def history(self, matrix, end):
        return matrix[:, self.months <= str(end)]

    def aggregate(self, frame, column, key="mf"):
        return frame.groupby(key)[column].sum().reindex(self.ids, fill_value=0).to_numpy(float)

    def snapshot(self, month):
        end = month.end_time
        frame = self.tables["declarations_mensuelles"]
        declarations = frame.loc[
            (frame.date_depot <= end)
            & frame.statut_depot.eq("DEPOSEE")
            & (frame.mois <= str(month))
        ].copy()
        exercise = available_exercise(month)
        a5 = self.tables["employeur_annexe5"]
        a2 = self.tables["employeur_annexe2"]
        a1 = self.tables["employeur_annexe1_synthese"]
        graph = self.tables["metriques_noeuds"]
        return Snapshot(
            month,
            month - 1,
            declarations,
            a5.loc[a5.exercice <= exercise].copy(),
            a2.loc[(a2.exercice <= exercise) & a2.type_id_beneficiaire.eq("1")].copy(),
            a1.loc[a1.exercice <= exercise].copy(),
            graph.loc[graph.mois.eq(str(month))].set_index("mf").reindex(self.ids),
            exercise,
        )

    def filing_failures(self, snapshot):
        """Unfiled as of now, or >30 days late; not the future final status."""
        rows = self.tables["declarations_mensuelles"].copy()
        in_window = rows.mois.between(str(snapshot.fiscal - 5), str(snapshot.fiscal))
        due = rows.date_limite <= snapshot.month.end_time
        filed = rows.date_depot.notna() & (rows.date_depot <= snapshot.month.end_time)
        delayed = (rows.date_depot - rows.date_limite).dt.days > 30
        rows["failure"] = (due & (~filed | delayed)).astype(float)
        return self.aggregate(rows.loc[in_window], "failure"), rows.loc[
            in_window & rows.failure.eq(1)
        ]

    def annual_totals(self, snapshot):
        a5 = snapshot.annual5.loc[snapshot.annual5.exercice.eq(snapshot.exercise)]
        a2 = snapshot.annual2.loc[snapshot.annual2.exercice.eq(snapshot.exercise)]
        paid = self.aggregate(a5, "montant_ttc", "mf_fournisseur") + self.aggregate(
            a2, "montant_brut", "id_beneficiaire"
        )
        declarations = snapshot.declarations.loc[
            snapshot.declarations.mois.str.startswith(str(snapshot.exercise))
        ].copy()
        declarations["ttc"] = declarations.ca_total_declare + declarations.tva_collectee
        declared = self.aggregate(declarations, "ttc")
        ht = self.aggregate(declarations, "ca_total_declare")
        count = declarations.groupby("mf").size().reindex(self.ids, fill_value=0).to_numpy()
        # Do not compare full-year receipts with the partial Sep-Dec 2023 history.
        complete = count == 12
        return paid, declared, ht, complete

    def headcount(self, snapshot):
        latest = (
            snapshot.employees.sort_values("exercice")
            .drop_duplicates("mf", keep="last")
            .set_index("mf")
        )
        return (
            latest.nb_salaries.reindex(self.ids)
            .fillna(self.companies.effectif_declare)
            .to_numpy(float)
        )

    def novelty(self, snapshot):
        articles = self.articles.loc[self.articles.mois <= str(snapshot.month)]
        foreign = articles.groupby(["mf", "id_fournisseur_etranger"], as_index=False).mois.min()
        foreign = foreign.loc[foreign.mois >= str(snapshot.month - 2)]
        categories = articles.groupby(["mf", "chapitre_sh"], as_index=False).mois.min()
        categories = categories.loc[categories.mois >= str(snapshot.month - 2)]
        a5 = snapshot.annual5
        # Annual local novelty persists for the last released exercise; no invented month.
        local = a5.loc[
            a5.exercice.eq(snapshot.exercise) & a5.premiere_annee_relation.eq(snapshot.exercise)
        ]
        local = local.drop_duplicates(["mf_payeur", "mf_fournisseur"])

        def counts(frame, key):
            return frame.groupby(key).size().reindex(self.ids, fill_value=0).to_numpy(float)

        return (
            counts(foreign, "mf") + counts(local, "mf_payeur"),
            counts(categories, "mf"),
            foreign,
            local,
            categories,
        )

"""Bounded evidence, ordered by amount, with facts limited to displayed records.

Numerical calculations use every eligible row. A separate audit file records
inputs to those calculations; displayed text never presents a sampled total as
though it were the portfolio total.
"""

from collections import defaultdict

from .statistics import french_amount

TITLES = {
    "COH_IMPORT_VS_CA": "Les importations progressent plus vite que le CA déclaré.",
    "COH_CLIENTS_VS_CA": "Les paiements déclarés par les clients dépassent le CA TTC déclaré du même exercice.",
    "COH_ADEB_VS_CA": "Les recettes publiques sont élevées par rapport au CA déclaré.",
    "COH_TVA_IMPORT": "La TVA déduite à l'importation dépasse la TVA douanière de la période correspondante.",
    "COH_VALEUR_REF": "Les prix unitaires importés sont inférieurs aux prix de référence.",
    "CHG_CA": "Le CA déclaré s'écarte de son historique.",
    "CHG_IMPORTS": "Les importations augmentent par rapport à leur historique.",
    "CHG_TVA_DEDUCTIBLE": "La TVA déductible sur achats locaux augmente par rapport à son historique.",
    "CHG_NOUVEAUX_FOURNISSEURS": "De nouveaux fournisseurs apparaissent dans les sources disponibles.",
    "CHG_NOUVELLES_CATEGORIES": "De nouveaux chapitres SH apparaissent dans les importations.",
    "CHG_DEPOTS": "Des déclarations échues ne sont pas déposées ou ont été déposées avec plus de trente jours de retard.",
    "PAI_MARGE": "La marge apparente est inférieure à celle des pairs.",
    "PAI_MAHALANOBIS": "Le profil est atypique pour son groupe de pairs",
    "RES_FOURNISSEUR_PARTAGE": "Des entreprises commencent une relation avec les mêmes nouveaux fournisseurs.",
    "RES_COQUILLE": "Une part importante des achats provient de fournisseurs au profil de coquille.",
    "RES_PROXIMITE_REDRESSE": "Le réseau relie l'entreprise à une entité dont le redressement est déjà notifié.",
}
VARIABLES = {
    "MARGE": "la marge apparente",
    "TVA_DED_SUR_COLL": "le ratio TVA déductible / collectée",
    "CA_PAR_SALARIE": "le CA par salarié",
    "IMPORTS_SUR_CA": "le ratio importations / CA",
}


class Evidence:
    def __init__(self, dataset, snapshot, foreign, local, categories, failure_rows):
        self.pools = {}
        self.dataset = dataset
        self.snapshot = snapshot
        fiscal, month = snapshot.fiscal, snapshot.month
        self.add(
            "declarations",
            snapshot.declarations.loc[
                snapshot.declarations.mois.between(str(fiscal - 13), str(fiscal))
            ],
            "mf",
            "declarations_mensuelles",
            None,
            "ca_total_declare",
        )
        self.add(
            "annual_declarations",
            snapshot.declarations.loc[
                snapshot.declarations.mois.str.startswith(str(snapshot.exercise))
            ],
            "mf",
            "declarations_mensuelles",
            None,
            "ca_total_declare",
        )
        articles = dataset.articles
        self.add(
            "imports",
            articles.loc[articles.mois.between(str(fiscal - 11), str(fiscal))],
            "mf",
            "douane_articles",
            "id_article",
            "valeur_caf_tnd",
        )
        self.add(
            "imports_history",
            articles.loc[articles.mois.between(str(month - 12), str(month))],
            "mf",
            "douane_articles",
            "id_article",
            "valeur_caf_tnd",
        )
        self.add(
            "reference",
            articles.loc[articles.mois.between(str(month - 5), str(month))],
            "mf",
            "douane_articles",
            "id_article",
            "valeur_caf_tnd",
        )
        self.add(
            "vat",
            dataset.customs_vat.loc[
                dataset.customs_vat.mois.between(str(fiscal - 12), str(fiscal - 1))
            ],
            "mf",
            "douane_liquidation",
            "id_article",
            "montant_tnd",
        )
        self.add(
            "public",
            dataset.public.loc[dataset.public.mois.between(str(fiscal - 11), str(fiscal))],
            "mf",
            "adeb_paiements",
            "num_ordonnance",
            "montant_ht",
        )
        a5 = snapshot.annual5.loc[snapshot.annual5.exercice.eq(snapshot.exercise)]
        a2 = snapshot.annual2.loc[snapshot.annual2.exercice.eq(snapshot.exercise)]
        self.add("clients5", a5, "mf_fournisseur", "employeur_annexe5", "id_ligne", "montant_ttc")
        self.add("clients2", a2, "id_beneficiaire", "employeur_annexe2", "id_ligne", "montant_brut")
        self.add("purchases", a5, "mf_payeur", "employeur_annexe5", "id_ligne", "montant_ttc")
        new_foreign = articles.merge(
            foreign[["mf", "id_fournisseur_etranger"]],
            on=["mf", "id_fournisseur_etranger"],
            how="inner",
        )
        new_foreign = new_foreign.loc[new_foreign.mois <= str(month)]
        self.add(
            "new_foreign", new_foreign, "mf", "douane_articles", "id_article", "valeur_caf_tnd"
        )
        self.add("new_local", local, "mf_payeur", "employeur_annexe5", "id_ligne", "montant_ttc")
        new_categories = articles.merge(
            categories[["mf", "chapitre_sh"]], on=["mf", "chapitre_sh"], how="inner"
        )
        self.add(
            "new_categories",
            new_categories.loc[new_categories.mois <= str(month)],
            "mf",
            "douane_articles",
            "id_article",
            "valeur_caf_tnd",
        )
        self.add(
            "failures", failure_rows, "mf", "declarations_mensuelles", None, "ca_total_declare"
        )
        self._network_pools(a5, a2, foreign, new_foreign, local)

    def add(self, name, frame, key, table, identifier, amount):
        pool = defaultdict(list)
        for row in frame.to_dict("records"):
            ref = row[identifier] if identifier else f"{row['mf']}:{row['mois']}"
            if table == "douane_liquidation":
                ref += ":105"
            # Unfiled declarations contain no amount available at the cutoff.
            unavailable = name == "failures" and not (
                row["date_depot"] <= self.snapshot.month.end_time
            )
            value = 0.0 if unavailable else float(row[amount])
            pool[row[key]].append((f"{table}:{ref}", value, table))
        self.pools[name] = pool

    def _network_pools(self, a5, a2, foreign, new_foreign, local):
        shared = defaultdict(list)
        # Match new foreign relationships within the same three-month window.
        by_supplier = defaultdict(list)
        for row in new_foreign.itertuples():
            by_supplier[row.id_fournisseur_etranger].append(
                (
                    row.mf,
                    (
                        f"douane_articles:{row.id_article}",
                        float(row.valeur_caf_tnd),
                        "douane_articles",
                    ),
                )
            )
        for row in foreign.itertuples():
            others = by_supplier[row.id_fournisseur_etranger]
            if len({mf for mf, _ in others}) > 1:
                shared[row.mf].extend(record for _, record in others)
        for _, rows in local.groupby("mf_fournisseur"):
            if rows.mf_payeur.nunique() > 1:
                records = [
                    (f"employeur_annexe5:{r.id_ligne}", float(r.montant_ttc), "employeur_annexe5")
                    for r in rows.itertuples()
                ]
                for mf in rows.mf_payeur.unique():
                    shared[mf].extend(records)
        self.pools["shared"] = shared
        shells = (
            self.snapshot.graph.est_profil_coquille.fillna("false")
            .astype(str)
            .str.lower()
            .isin(["true", "1"])
        )
        shell_ids = set(shells.index[shells])
        self.add(
            "shells",
            a5.loc[a5.mf_fournisseur.isin(shell_ids)],
            "mf_payeur",
            "employeur_annexe5",
            "id_ligne",
            "montant_ttc",
        )

        # Build dated raw-edge paths. Do not use all-time aretes.csv aggregates.
        adjacency = defaultdict(list)

        def edge(a, b, ref, amount, table):
            item = (ref, float(amount), table)
            adjacency[a].append((b, item))
            adjacency[b].append((a, item))

        for row in self.dataset.articles.loc[
            self.dataset.articles.mois <= str(self.snapshot.month)
        ].itertuples():
            edge(
                row.mf,
                row.id_fournisseur_etranger,
                f"douane_articles:{row.id_article}",
                row.valeur_caf_tnd,
                "douane_articles",
            )
        for row in a5.itertuples():
            edge(
                row.mf_payeur,
                row.mf_fournisseur,
                f"employeur_annexe5:{row.id_ligne}",
                row.montant_ttc,
                "employeur_annexe5",
            )
        for row in a2.itertuples():
            edge(
                row.mf_payeur,
                row.id_beneficiaire,
                f"employeur_annexe2:{row.id_ligne}",
                row.montant_brut,
                "employeur_annexe2",
            )
        controls = self.dataset.tables["historique_controles"]
        controls = controls.loc[
            (controls.date_notification_resultats < self.snapshot.month.end_time)
            & controls.categorie_resultat.eq("FRAUDE_SIGNIFICATIVE")
        ]
        paths, frontier = {}, {}
        for row in controls.itertuples():
            frontier[row.mf] = [
                (f"historique_controles:{row.id_controle}", 0.0, "historique_controles")
            ]
        visited = set(frontier)
        for _ in range(3):
            next_frontier = {}
            for node, path in frontier.items():
                for neighbor, record in adjacency[node]:
                    if neighbor not in visited:
                        visited.add(neighbor)
                        next_frontier[neighbor] = path + [record]
                        paths[neighbor] = path + [record]
            frontier = next_frontier
        self.pools["paths"] = paths

    def select(self, mf, code):
        names = {
            "COH_IMPORT_VS_CA": ("imports", "declarations"),
            "COH_CLIENTS_VS_CA": ("clients5", "clients2", "annual_declarations"),
            "COH_ADEB_VS_CA": ("public", "declarations"),
            "COH_TVA_IMPORT": ("vat", "declarations"),
            "COH_VALEUR_REF": ("reference",),
            "CHG_CA": ("declarations",),
            "CHG_IMPORTS": ("imports_history",),
            "CHG_TVA_DEDUCTIBLE": ("declarations",),
            "CHG_NOUVEAUX_FOURNISSEURS": ("new_foreign", "new_local"),
            "CHG_NOUVELLES_CATEGORIES": ("new_categories",),
            "CHG_DEPOTS": ("failures",),
            "PAI_MARGE": ("imports", "declarations"),
            "PAI_MAHALANOBIS": ("imports", "declarations"),
            "RES_FOURNISSEUR_PARTAGE": ("shared",),
            "RES_COQUILLE": ("shells",),
            "RES_PROXIMITE_REDRESSE": ("paths",),
        }[code]
        unique = {record[0]: record for name in names for record in self.pools[name].get(mf, [])}
        ordered = sorted(unique.values(), key=lambda r: (-r[1], r[0]))
        return ordered[:50], len(ordered)

    def fact(self, mf, code, dominant="MARGE"):
        rows, count = self.select(mf, code)
        title = TITLES[code]
        if code == "PAI_MAHALANOBIS":
            title += f", surtout {VARIABLES[dominant]}."
        if not rows:
            return (
                title + " Aucune ligne justificative disponible dans les sources fournies.",
                [],
                count,
            )
        # Cite one exact, human-checkable number rather than an unverifiable
        # aggregate when there are more raw operations than the 50-proof cap.
        ref, amount, table = rows[0]
        labels = {
            "douane_articles": "CAF",
            "declarations_mensuelles": "CA HT",
            "employeur_annexe5": "montant TTC",
            "employeur_annexe2": "montant brut",
            "adeb_paiements": "paiement HT",
            "douane_liquidation": "TVA liquidée",
        }
        if table in labels and code != "CHG_DEPOTS":
            title += f" Pièce {ref} : {labels[table]} {french_amount(amount)}."
        else:
            title += f" Pièce : {ref}."
        return title, [r[0] for r in rows], count

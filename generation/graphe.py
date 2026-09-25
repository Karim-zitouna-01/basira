"""Relationship graph (data/graphe/aretes.csv) and monthly node metrics (metriques_noeuds.csv).

Built only from the published raw tables, with the availability rules of the real sources:
customs is known monthly; annex V / annex I / IS of year N are usable from March N+1; a control
counts for `distance_entite_redressee` only once its results were notified before the month ended.
"""

from __future__ import annotations

import networkx as nx
import numpy as np
import pandas as pd

from . import config as cfg

MONTH_POS = {m: i for i, m in enumerate(cfg.SIM_MONTHS)}


def _t_of(dates: pd.Series) -> np.ndarray:
    return dates.dt.strftime("%Y-%m").map(MONTH_POS).to_numpy()


def build_edges(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    decl, arts = tables["douane_declarations"], tables["douane_articles"]
    imp = arts[["num_declaration", "id_fournisseur_etranger", "valeur_caf_tnd"]].merge(
        decl[["num_declaration", "mf_importateur", "date_enregistrement"]], on="num_declaration")
    e1 = imp.groupby(["mf_importateur", "id_fournisseur_etranger"]).agg(
        montant_total=("valeur_caf_tnd", "sum"), premiere_date=("date_enregistrement", "min"),
        derniere_date=("date_enregistrement", "max")).reset_index()
    e1.columns = ["source", "cible", "montant_total", "premiere_date", "derniere_date"]
    e1["type_relation"] = "IMPORT_FOURNISSEUR"

    def annual(df, src, dst, amount, typ):
        g = df.groupby([src, dst]).agg(montant_total=(amount, "sum"), y0=("exercice", "min"), y1=("exercice", "max")).reset_index()
        g["premiere_date"] = pd.to_datetime(g["y0"].astype(str) + "-01-01").clip(lower=cfg.WINDOW_START_DATE)
        g["derniere_date"] = pd.to_datetime(g["y1"].astype(str) + "-12-31").clip(upper=cfg.WINDOW_END_DATE)
        g = g.rename(columns={src: "source", dst: "cible"})
        g["type_relation"] = typ
        return g[["source", "cible", "montant_total", "premiere_date", "derniere_date", "type_relation"]]

    e2 = annual(tables["employeur_annexe5"], "mf_payeur", "mf_fournisseur", "montant_ttc", "ACHAT_LOCAL_A5")
    a2 = tables["employeur_annexe2"]
    e3 = annual(a2[a2["type_id_beneficiaire"] == 1], "mf_payeur", "id_beneficiaire", "montant_brut", "HONORAIRES_A2")
    adeb = tables["adeb_paiements"]
    e4 = adeb.groupby(["id_acheteur_public", "mf_beneficiaire"]).agg(
        montant_total=("montant_ttc", "sum"), premiere_date=("date_paiement", "min"), derniere_date=("date_paiement", "max")).reset_index()
    e4.columns = ["source", "cible", "montant_total", "premiere_date", "derniere_date"]
    e4["type_relation"] = "PAIEMENT_PUBLIC"
    edges = pd.concat([e1, e2, e3, e4], ignore_index=True)
    edges["montant_total"] = edges["montant_total"].round(3)
    return edges[["source", "cible", "type_relation", "montant_total", "premiere_date", "derniere_date"]]


def _shared_new(pairs: pd.DataFrame, active_counts: pd.Series) -> pd.DataFrame:
    """pairs: (mf, s) new relations in the window. A supplier qualifies when >= 2 of its clients are new
    and new clients are at least half of its active clients (simultaneous onboarding)."""
    if pairs.empty:
        return pairs.assign(other=pd.Series(dtype=str))
    n_new = pairs.groupby("s")["mf"].nunique()
    share = n_new / active_counts.reindex(n_new.index).fillna(n_new).clip(lower=1)
    ok = n_new[(n_new >= 2) & (share >= 0.5)].index
    q = pairs[pairs["s"].isin(ok)]
    j = q.merge(q.rename(columns={"mf": "other"}), on="s")
    return j[j["mf"] != j["other"]][["mf", "other"]]


HUB_DEGREE = 20


def _bfs_no_hub_transit(G: nx.Graph, source: str, cutoff: int = 3) -> dict[str, int]:
    """Shortest distances up to `cutoff`, where hubs (> HUB_DEGREE partners: large wholesalers,
    accounting firms) can be reached but do not relay the path. Without this rule almost every
    company sits two hops away from any sanctioned company through a shared accountant."""
    seen = {source: 0}
    frontier = [source]
    for depth in range(1, cutoff + 1):
        nxt = []
        for x in frontier:
            if x != source and G.degree(x) > HUB_DEGREE:
                continue
            for y in G.neighbors(x):
                if y not in seen:
                    seen[y] = depth
                    nxt.append(y)
        frontier = nxt
    return seen


def build_metrics(tables: dict[str, pd.DataFrame], comp: pd.DataFrame) -> pd.DataFrame:
    decl, arts = tables["douane_declarations"], tables["douane_articles"]
    imp = arts[["num_declaration", "id_fournisseur_etranger"]].merge(
        decl[["num_declaration", "mf_importateur", "date_enregistrement"]], on="num_declaration")
    imp = pd.DataFrame({"mf": imp["mf_importateur"], "s": imp["id_fournisseur_etranger"], "t": _t_of(imp["date_enregistrement"])})
    imp = imp.drop_duplicates()
    first = imp.groupby(["mf", "s"])["t"].min().rename("first").reset_index()

    a5 = tables["employeur_annexe5"][["mf_payeur", "mf_fournisseur", "exercice", "premiere_annee_relation", "montant_ttc"]]
    a5 = a5.rename(columns={"mf_payeur": "mf", "mf_fournisseur": "s"})
    a2 = tables["employeur_annexe2"]
    a2 = a2[a2["type_id_beneficiaire"] == 1]
    a1 = tables["employeur_annexe1_synthese"].set_index(["mf", "exercice"])["nb_salaries"]
    dis = tables["declarations_is"]
    ca_is = (dis["ca_local"] + dis["ca_export"]).groupby([dis["mf"], dis["exercice"]]).sum()
    dm = tables["declarations_mensuelles"]
    ca_m = dm.groupby([dm["mf"], dm["mois"].str[:4].astype(int)])["ca_total_declare"].sum()
    received = a5.groupby(["s", "exercice"])["montant_ttc"].sum()

    ctl = tables["historique_controles"]
    fraud_ctl = ctl[ctl["categorie_resultat"] == "FRAUDE_SIGNIFICATIVE"][["mf", "date_notification_resultats"]]

    created = comp.set_index("mf")["created_t"]
    all_mf = comp["mf"].to_numpy()
    out = []
    cache_graph: dict[int, nx.Graph] = {}
    for m in range(cfg.METRIC_T0, cfg.T):
        E = cfg.latest_exercice_available(m)
        exists = all_mf[created.reindex(all_mf).to_numpy() <= m]

        # Foreign suppliers
        win12 = imp[(imp["t"] > m - 12) & (imp["t"] <= m)]
        deg_f = win12.groupby("mf")["s"].nunique()
        new_f = first[(first["first"] > m - 12) & (first["first"] <= m) & (first["first"] >= cfg.NOVELTY_BURN_IN)]
        n_new_f = new_f.groupby("mf")["s"].nunique()
        new3 = first[(first["first"] > m - 3) & (first["first"] <= m) & (first["first"] >= cfg.NOVELTY_BURN_IN)][["mf", "s"]]
        sh_f = _shared_new(new3, win12.groupby("s")["mf"].nunique())

        # Local suppliers (annex V of the latest available year)
        a5e = a5[a5["exercice"] == E]
        deg_l = a5e.groupby("mf")["s"].nunique()
        new_l = a5e[a5e["premiere_annee_relation"] == E]
        n_new_l = new_l.groupby("mf")["s"].nunique()
        sh_l = _shared_new(new_l[["mf", "s"]], a5e.groupby("s")["mf"].nunique())
        shared = pd.concat([sh_f, sh_l]).drop_duplicates().groupby("mf")["other"].nunique()

        # Shell profile (fixed rule, modele_donnees.md 2.14)
        age_ok = (m - created) < 36
        nb_sal = pd.Series(a1.xs(E, level="exercice") if E in a1.index.get_level_values(1) else pd.Series(dtype=float))
        nb_sal = nb_sal.reindex(created.index).fillna(0)
        rec = received.xs(E, level="exercice") if E in received.index.get_level_values(1) else pd.Series(dtype=float)
        rec = rec.reindex(created.index).fillna(0)
        ca_e = ca_is.xs(E, level="exercice") if E in ca_is.index.get_level_values(1) else pd.Series(dtype=float)
        ca_fallback = ca_m.xs(E, level=1) if E in ca_m.index.get_level_values(1) else pd.Series(dtype=float)
        ca_e = ca_e.reindex(created.index).fillna(ca_fallback.reindex(created.index)).fillna(0)
        shell = (nb_sal == 0) & age_ok & (rec > 0) & (rec >= 3 * ca_e)
        shells = set(shell[shell].index)

        tot = a5e.groupby("mf")["montant_ttc"].sum()
        sh_amt = a5e[a5e["s"].isin(shells)].groupby("mf")["montant_ttc"].sum()
        part = (sh_amt.reindex(tot.index).fillna(0) / tot.replace(0, np.nan)).fillna(0)

        # Distance to an entity found in significant fraud, notified before the end of month m
        end_m = (pd.Period(cfg.SIM_MONTHS[m], freq="M") + 1).to_timestamp()
        red = set(fraud_ctl.loc[fraud_ctl["date_notification_resultats"] < end_m, "mf"])
        if E not in cache_graph:
            G = nx.Graph()
            G.add_nodes_from(all_mf)
            e5 = a5[a5["exercice"] <= E]
            G.add_edges_from(zip(e5["mf"], e5["s"]))
            e2 = a2[a2["exercice"] <= E]
            G.add_edges_from(zip(e2["mf_payeur"], e2["id_beneficiaire"]))
            cache_graph[E] = G
        G = cache_graph[E]
        dist = {}
        for r in red:
            if r not in G:
                continue
            for v, d in _bfs_no_hub_transit(G, r).items():
                if v != r and d < dist.get(v, 99):
                    dist[v] = d

        df = pd.DataFrame({"mf": exists})
        df["mois"] = cfg.SIM_MONTHS[m]
        df["degre_fournisseurs"] = (deg_f.reindex(exists).fillna(0) + deg_l.reindex(exists).fillna(0)).astype(int).to_numpy()
        df["nb_fournisseurs_nouveaux_12m"] = (n_new_f.reindex(exists).fillna(0) + n_new_l.reindex(exists).fillna(0)).astype(int).to_numpy()
        df["nb_clients_partageant_fournisseur_nouveau"] = shared.reindex(exists).fillna(0).astype(int).to_numpy()
        df["part_achats_coquilles"] = part.reindex(exists).fillna(0).round(4).to_numpy()
        df["est_profil_coquille"] = shell.reindex(exists).fillna(False).astype(bool).to_numpy()
        df["distance_entite_redressee"] = [dist.get(x, 99) for x in exists]
        out.append(df)
    return pd.concat(out, ignore_index=True)

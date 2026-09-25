"""Consistency checks on the generated CSV files (member A task, section 5).

    uv run python -m generation.checks [--data data]

Reads the files back from disk, so it validates exactly what the other teams consume.
Exit code 0 when every check passes.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from . import config as cfg
from .referentiels import DD_FREE_ORIGINS

HONEST = {"AUCUN", "CITOYEN_MODELE", "CROISSANCE_LEGITIME"}
MF_RE = re.compile(r"^\d{7}[A-HJ-NP-TV-Z][ABPFN][MCPN]\d{3}$")


@dataclass
class Result:
    name: str
    ok: bool
    detail: str


class Checker:
    def __init__(self, root: Path):
        self.raw, self.gdir = root / "raw", root / "graphe"
        self.results: list[Result] = []
        self._cache: dict[str, pd.DataFrame] = {}

    def t(self, name: str) -> pd.DataFrame:
        if name not in self._cache:
            path = self.gdir / f"{name}.csv" if name in ("aretes", "metriques_noeuds") else self.raw / f"{name}.csv"
            self._cache[name] = pd.read_csv(path, dtype={"mf": str, "code_ndp": str, "code_sh6": str, "chapitre_sh": str,
                                                         "code_nat": str, "bureau_code": str, "code_taxe": str,
                                                         "mission_code": str, "id_beneficiaire": str, "division": str,
                                                         "source": str, "cible": str, "code": str},
                                            keep_default_na=True)
        return self._cache[name]

    def add(self, name: str, ok: bool, detail: str = "") -> None:
        self.results.append(Result(name, bool(ok), detail))

    # ------------------------------------------------------------------
    def keys(self) -> None:
        for table, cols in [
            ("contribuables", ["mf"]), ("declarations_mensuelles", ["mf", "mois"]), ("declarations_is", ["mf", "exercice"]),
            ("douane_declarations", ["num_declaration"]), ("douane_articles", ["id_article"]),
            ("douane_liquidation", ["id_article", "code_taxe"]), ("employeur_annexe5", ["id_ligne"]),
            ("employeur_annexe2", ["id_ligne"]), ("employeur_annexe1_synthese", ["mf", "exercice"]),
            ("adeb_paiements", ["num_ordonnance"]), ("historique_controles", ["id_controle"]),
            ("fournisseurs_etrangers", ["id_fournisseur"]), ("verite_terrain", ["mf"]), ("ref_ndp", ["code_ndp"]),
            ("metriques_noeuds", ["mf", "mois"]),
        ]:
            df = self.t(table)
            dup = int(df.duplicated(cols).sum())
            self.add(f"unique key {table}({', '.join(cols)})", dup == 0, f"{dup} duplicates" if dup else f"{len(df):,} rows")
        c = self.t("contribuables")
        bad = int((~c["mf"].str.match(MF_RE)).sum())
        disp = (c["mf"].str[:7] + "/" + c["mf"].str[7] + "/" + c["mf"].str[8] + "/" + c["mf"].str[9] + "/" + c["mf"].str[10:])
        self.add("mf format NNNNNNN+key(no I,O,U)+TVA+cat+EEE", bad == 0 and (disp == c["matricule_fiscal"]).all(), f"{bad} malformed")

    def foreign_keys(self) -> None:
        mfs = set(self.t("contribuables")["mf"])
        a2 = self.t("employeur_annexe2")
        pairs = [
            ("employeur_annexe5.mf_fournisseur", self.t("employeur_annexe5")["mf_fournisseur"]),
            ("employeur_annexe5.mf_payeur", self.t("employeur_annexe5")["mf_payeur"]),
            ("employeur_annexe2.mf_payeur", a2["mf_payeur"]),
            ("employeur_annexe2.id_beneficiaire (type 1)", a2.loc[a2["type_id_beneficiaire"] == 1, "id_beneficiaire"]),
            ("adeb_paiements.mf_beneficiaire", self.t("adeb_paiements")["mf_beneficiaire"]),
            ("douane_declarations.mf_importateur", self.t("douane_declarations")["mf_importateur"]),
            ("declarations_mensuelles.mf", self.t("declarations_mensuelles")["mf"]),
            ("historique_controles.mf", self.t("historique_controles")["mf"]),
            ("metriques_noeuds.mf", self.t("metriques_noeuds")["mf"]),
            ("verite_terrain.mf", self.t("verite_terrain")["mf"]),
        ]
        for name, s in pairs:
            miss = int((~s.isin(mfs)).sum())
            self.add(f"FK {name} in contribuables", miss == 0, f"{miss} missing" if miss else "")
        arts = self.t("douane_articles")
        for name, s, ref in [
            ("douane_articles.num_declaration", arts["num_declaration"], set(self.t("douane_declarations")["num_declaration"])),
            ("douane_articles.id_fournisseur_etranger", arts["id_fournisseur_etranger"], set(self.t("fournisseurs_etrangers")["id_fournisseur"])),
            ("douane_articles.code_ndp", arts["code_ndp"], set(self.t("ref_ndp")["code_ndp"])),
            ("douane_liquidation.id_article", self.t("douane_liquidation")["id_article"], set(arts["id_article"])),
            ("adeb_paiements.id_acheteur_public", self.t("adeb_paiements")["id_acheteur_public"], set(self.t("ref_acheteurs_publics")["id_acheteur_public"])),
            ("contribuables.code_nat", self.t("contribuables")["code_nat"], set(self.t("ref_nat")["code_nat"])),
        ]:
            miss = int((~s.isin(ref)).sum())
            self.add(f"FK {name}", miss == 0, f"{miss} missing" if miss else "")

    def customs(self) -> None:
        d, a, l, ref = self.t("douane_declarations"), self.t("douane_articles"), self.t("douane_liquidation"), self.t("ref_ndp")
        s = a.groupby("num_declaration")["valeur_caf_tnd"].sum()
        diff = (d.set_index("num_declaration")["valeur_caf_tnd"] - s.reindex(d["num_declaration"]).to_numpy()).abs()
        self.add("customs: declaration CAF = sum of articles (+/-0.01)", (diff <= 0.011).all(), f"max diff {diff.max():.4f}")
        pu = (a["quantite"] * a["prix_unitaire_tnd"] - a["valeur_caf_tnd"]).abs()
        self.add("customs: quantity x unit price = article value (+/-0.01)", (pu <= 0.011 + 1e-6 * a["valeur_caf_tnd"]).all(), f"max diff {pu.max():.4f}")

        x = l.merge(a[["id_article", "code_ndp", "pays_origine", "valeur_caf_tnd", "num_declaration"]], on="id_article")
        x = x.merge(ref[["code_ndp", "taux_dd", "taux_tva", "taux_fodec"]], on="code_ndp")
        wide = l.pivot_table(index="id_article", columns="code_taxe", values="montant_tnd", aggfunc="sum").fillna(0)
        for c in ("001", "093", "105", "473"):
            if c not in wide:
                wide[c] = 0.0
        amt_ok = ((x["base_tnd"] * x["taux"] / 100).round(3) - x["montant_tnd"]).abs() <= 0.011
        dd = x[x["code_taxe"] == "001"]
        dd_ok = ((dd["taux"] == dd["taux_dd"]) & ~dd["pays_origine"].isin(DD_FREE_ORIGINS)).all()
        fod = x[x["code_taxe"] == "093"]
        fod_ok = (fod["taux"] == fod["taux_fodec"]).all() and ((fod["base_tnd"] - fod["valeur_caf_tnd"]).abs() <= 0.011).all()
        tva = x[x["code_taxe"] == "105"].set_index("id_article")
        tva_base = tva["valeur_caf_tnd"] + wide.reindex(tva.index)["001"] + wide.reindex(tva.index)["093"]
        tva_ok = (tva["taux"] == tva["taux_tva"]).all() and ((tva["base_tnd"] - tva_base).abs() <= 0.011).all()
        rpd = x[x["code_taxe"] == "473"].set_index("id_article")
        rpd_base = wide.reindex(rpd.index)[["001", "093", "105"]].sum(axis=1)
        rpd_ok = ((rpd["base_tnd"] - rpd_base).abs() <= 0.011).all() and (rpd["taux"] == 3.0).all()
        # Articles subject to DD (non-preferential origin, IC100) must carry a DD line.
        ic = a.merge(d[["num_declaration", "type_declaration"]], on="num_declaration").merge(ref[["code_ndp", "taux_dd"]], on="code_ndp")
        need_dd = ic[(ic["type_declaration"] == "IC100") & (ic["taux_dd"] > 0) & ~ic["pays_origine"].isin(DD_FREE_ORIGINS) & (ic["valeur_caf_tnd"] > 1)]
        has_dd = need_dd["id_article"].isin(dd["id_article"]).mean() if len(need_dd) else 1.0
        susp = ic[ic["type_declaration"] != "IC100"]["id_article"]
        self.add("liquidation: amount = base x rate (all taxes)", amt_ok.all(), f"{int((~amt_ok).sum())} bad lines")
        self.add("liquidation: DD rate = ref_ndp.taux_dd, 0 only for EU/TR origins", dd_ok and has_dd > 0.999, f"DD coverage {has_dd:.4f}")
        self.add("liquidation: FODEC 093 rate/base consistent with ref_ndp", fod_ok)
        self.add("liquidation: TVA 105 base = CAF + DD + FODEC, rate = ref_ndp", tva_ok)
        self.add("liquidation: RPD 473 = 3 % of duties and taxes", rpd_ok)
        self.add("liquidation: none for suspension regimes (SA530/SA531/SE737)", not l["id_article"].isin(susp).any())
        tot = l.merge(a[["id_article", "num_declaration"]], on="id_article").groupby("num_declaration")["montant_tnd"].sum()
        tdiff = (d.set_index("num_declaration")["total_droits_taxes_tnd"] - tot.reindex(d["num_declaration"]).fillna(0).to_numpy()).abs()
        self.add("customs: total_droits_taxes = sum of liquidation (+/-0.05)", (tdiff <= 0.05).all(), f"max diff {tdiff.max():.3f}")

    def honest_coherence(self) -> None:
        vt = self.t("verite_terrain").set_index("mf")["scenario"]
        honest = set(vt[vt.isin(HONEST)].index)
        dm = self.t("declarations_mensuelles").copy()
        dm["y"] = dm["mois"].str[:4].astype(int)
        dm["ttc"] = dm["ca_taxable_19"] * 1.19 + dm["ca_taxable_13"] * 1.13 + dm["ca_taxable_7"] * 1.07 + dm["ca_exonere"] + dm["ca_export"]
        ttc = dm.groupby(["mf", "y"])["ttc"].sum()
        a5 = self.t("employeur_annexe5")
        rec = a5.groupby(["mf_fournisseur", "exercice"])["montant_ttc"].sum()
        rec = rec[rec.index.get_level_values(0).isin(honest) & rec.index.get_level_values(1).isin([2024, 2025])]
        cmp_ = ttc.reindex(rec.index).fillna(0)
        bad = rec > cmp_ + 1.0
        self.add("honest suppliers: sum annex V received <= declared CA TTC (2024, 2025)", not bad.any(),
                 f"{int(bad.sum())} of {len(rec)} supplier-years over" if bad.any() else f"{len(rec)} supplier-years, max ratio {(rec / cmp_.replace(0, np.nan)).max():.2f}")

        d, a, l = self.t("douane_declarations"), self.t("douane_articles"), self.t("douane_liquidation")
        v = l[l["code_taxe"] == "105"].merge(a[["id_article", "num_declaration"]], on="id_article").merge(
            d[["num_declaration", "mf_importateur", "date_enregistrement"]], on="num_declaration")
        v["mois"] = v["date_enregistrement"].str[:7]
        t105 = v.groupby(["mf_importateur", "mois"])["montant_tnd"].sum()
        nxt = {m: str(pd.Period(m, freq="M") + 1) for m in dm["mois"].unique()}
        dm_h = dm[dm["mf"].isin(honest) & (dm["statut_depot"] == "DEPOSEE") & (dm["mois"] > cfg.WINDOW_START)].copy()
        dm_h["prev"] = [str(pd.Period(m, freq="M") - 1) for m in dm_h["mois"]]
        exp = t105.reindex(list(zip(dm_h["mf"], dm_h["prev"]))).fillna(0).to_numpy()
        got = dm_h["tva_deductible_import"].to_numpy()
        ok = np.abs(got - exp) <= 0.05 * np.maximum(exp, got) + 1.0
        self.add("honest importers: TVA 105 of M = deductible import VAT of M+1 (+/-5 %)", ok.all(),
                 f"{int((~ok).sum())} of {len(ok)} company-months off" if not ok.all() else f"{int((exp > 0).sum())} months with import VAT")
        del nxt

        dis = self.t("declarations_is")
        dis = dis[dis["mf"].isin(honest) & dis["exercice"].isin([2024, 2025])].set_index(["mf", "exercice"])
        s = dm[dm["statut_depot"] == "DEPOSEE"].groupby(["mf", "y"])["ca_total_declare"].sum()
        mon = s.reindex(dis.index).fillna(0)
        is_ca = dis["ca_local"] + dis["ca_export"]
        ok = (is_ca - mon).abs() <= 0.02 * mon.abs() + 1.0
        self.add("honest companies: IS turnover = sum of monthly declared (+/-2 %, 2024-2025)", ok.all(),
                 f"{int((~ok).sum())} of {len(ok)} off" if not ok.all() else f"{len(ok)} returns")

    # ------------------------------------------------------------------
    def scenarios(self) -> None:
        vt = self.t("verite_terrain")
        dm = self.t("declarations_mensuelles")
        d, a, ref = self.t("douane_declarations"), self.t("douane_articles"), self.t("ref_ndp")
        d = d.assign(mois=d["date_enregistrement"].str[:7])
        caf = d.groupby(["mf_importateur", "mois"])["valeur_caf_tnd"].sum()
        ca = dm.set_index(["mf", "mois"])["ca_total_declare"]
        loc = dm.set_index(["mf", "mois"])["tva_deductible_biens_services_local"]
        a5 = self.t("employeur_annexe5")
        dis = self.t("declarations_is").set_index(["mf", "exercice"])
        a1 = self.t("employeur_annexe1_synthese")
        adeb = self.t("adeb_paiements").assign(mois=lambda x: x["date_paiement"].str[:7])
        pub = adeb.groupby(["mf_beneficiaire", "mois"])["montant_ht"].sum()
        arts = a.merge(d[["num_declaration", "mf_importateur", "mois"]], on="num_declaration").merge(ref[["code_ndp", "prix_reference_tnd"]], on="code_ndp")
        arts["ratio"] = arts["prix_unitaire_tnd"] / arts["prix_reference_tnd"]
        months = cfg.SIM_MONTHS

        def window(series, mf, lo, hi):
            """Flows (customs, payments): missing = 0. Declarations: missing month = not filed, kept NaN."""
            idx = [(mf, m) for m in months[max(lo, cfg.OUT0):hi + 1]]
            x = series.reindex(idx)
            return x if series is ca or series is loc else x.fillna(0)

        def sig(row) -> bool:
            mf, sc = row["mf"], row["scenario"]
            t0 = months.index(row["mois_debut_scenario"]) if isinstance(row["mois_debut_scenario"], str) and row["mois_debut_scenario"] else -1
            end = min(t0 + 5, cfg.T - 1)
            if sc == "A":
                before, after = window(caf, mf, t0 - 12, t0 - 1).mean(), window(caf, mf, t0, end).mean()
                imp_ok = before > 0 and after / before >= 1.6
                ca_b, ca_a = window(ca, mf, t0 - 6, t0 - 1).mean(), window(ca, mf, t0, end).mean()
                flat = ca_b > 0 and abs(ca_a / ca_b - 1) <= 0.25
                y = int(months[t0][:4])
                rec = a5[(a5["mf_fournisseur"] == mf) & (a5["exercice"] == y)]["montant_ttc"].sum()
                clients_ok = y <= 2025 and (mf, y) in dis.index and rec > 1.05 * (dis.loc[(mf, y), "ca_local"] + dis.loc[(mf, y), "ca_export"])
                return flat and (imp_ok or clients_ok)
            if sc == "B":
                b, af = window(loc, mf, t0 - 6, t0 - 1).mean(), window(loc, mf, t0, end).mean()
                net = row["id_reseau"]
                shells = set(vt[(vt["scenario"] == "COQUILLE") & (vt["id_reseau"] == net)]["mf"])
                return b > 0 and af / b >= 1.3 and a5[(a5["mf_payeur"] == mf) & a5["mf_fournisseur"].isin(shells)].shape[0] > 0
            if sc == "COQUILLE":
                rec = a5[(a5["mf_fournisseur"] == mf) & (a5["exercice"] == 2025)]["montant_ttc"].sum()
                decl = dis.loc[(mf, 2025), ["ca_local", "ca_export"]].sum() if (mf, 2025) in dis.index else 0.0
                return rec > 0 and rec >= 3 * decl and not (a1["mf"] == mf).any()
            if sc == "C":
                return int((arts[(arts["mf_importateur"] == mf) & (arts["mois"] >= months[t0])]["ratio"] < 0.7).sum()) >= 3
            if sc == "D":
                p, c = window(pub, mf, t0, cfg.T - 1).sum(), window(ca, mf, t0, cfg.T - 1).mean() * (cfg.T - t0)
                return c > 0 and p / c >= 0.9
            if sc == "E":
                x = dm[(dm["mf"] == mf) & (dm["mois"] < months[t0])]
                dormant = ((x["statut_depot"] == "NON_DEPOSEE") | (x["ca_total_declare"] == 0)).sum() >= 12
                return dormant and window(caf, mf, t0, cfg.T - 1).sum() > 0
            if sc == "F":
                def margin(lo, hi):
                    filed = window(ca, mf, lo, hi).notna().to_numpy()
                    c = window(ca, mf, lo, hi).to_numpy()[filed].sum()
                    purch = window(caf, mf, lo, hi).to_numpy()[filed].sum() + window(loc, mf, lo, hi).to_numpy()[filed].sum() / 0.19
                    return 1 - purch / c if c > 0 else np.nan
                return margin(t0 - 12, t0 - 1) - margin(cfg.T - 6, cfg.T - 1) >= 0.08
            if sc == "CROISSANCE_LEGITIME":
                c0, c1 = window(ca, mf, t0 - 6, t0 - 1).mean(), window(ca, mf, max(t0, cfg.T - 3), cfg.T - 1).mean()
                return c0 > 0 and c1 / c0 >= 1.4
            if sc == "CITOYEN_MODELE":
                x = dm[dm["mf"] == mf]
                ctl = self.t("historique_controles")
                clean = ctl[ctl["mf"] == mf]["categorie_resultat"].eq("CONFORME").all()
                return (x["statut_depot"] == "DEPOSEE").all() and (x["jours_retard"].fillna(0) == 0).all() and clean
            return True

        for sc in ["A", "B", "C", "D", "E", "F", "COQUILLE", "CROISSANCE_LEGITIME", "CITOYEN_MODELE"]:
            rows = vt[vt["scenario"] == sc]
            if rows.empty:
                continue
            ok = rows.apply(sig, axis=1)
            rate = ok.mean()
            self.add(f"scenario {sc}: signature present", rate >= 0.9, f"{int(ok.sum())}/{len(ok)} companies ({rate:.0%})")

    def heroes(self) -> None:
        dm = self.t("declarations_mensuelles").set_index(["mf", "mois"])
        d, a = self.t("douane_declarations"), self.t("douane_articles")
        d = d.assign(mois=d["date_enregistrement"].str[:7])
        caf = d.groupby(["mf_importateur", "mois"])["valeur_caf_tnd"].sum()
        c = self.t("contribuables").set_index("mf")
        vt = self.t("verite_terrain").set_index("mf")
        for h in cfg.HEROES:
            ok = h.mf in c.index and c.loc[h.mf, "raison_sociale"] == h.raison_sociale and c.loc[h.mf, "code_nat"] == h.code_nat \
                and int(c.loc[h.mf, "gouvernorat_code"]) == h.gouvernorat and vt.loc[h.mf, "scenario"] == h.scenario
            self.add(f"hero {h.raison_sociale}: identity and scenario", ok, f"{h.mf} {h.code_nat} gouv {h.gouvernorat} {h.scenario}")

        m = lambda lo, hi: cfg.SIM_MONTHS[cfg.month_index(lo):cfg.month_index(hi) + 1]  # noqa: E731
        alpha = cfg.ALPHA_MF
        before = caf.reindex([(alpha, x) for x in m("2025-06", "2026-05")]).fillna(0).mean()
        after = caf.reindex([(alpha, x) for x in m("2026-06", "2026-08")]).fillna(0).mean()
        ca_b = dm.loc[[(alpha, x) for x in m("2025-12", "2026-05")], "ca_total_declare"].mean()
        ca_a = dm.loc[[(alpha, x) for x in m("2026-06", "2026-08")], "ca_total_declare"].mean()
        self.add("hero Alpha: imports x3.4 from 2026-06 (x2.8 to x4.0), declared CA flat (+/-5 %)",
                 2.8 <= after / before <= 4.0 and abs(ca_a / ca_b - 1) <= 0.05, f"imports x{after / before:.2f}, CA {ca_a / ca_b - 1:+.1%}")
        fe = a[a["id_fournisseur_etranger"] == cfg.ALPHA_SUPPLIER].merge(d[["num_declaration", "mf_importateur", "mois"]], on="num_declaration")
        first = fe.groupby("mf_importateur")["mois"].min()
        vtg = vt[vt["id_reseau"] == "GA01"]
        ok = fe["mois"].min() == "2026-06" and len(first) == 5 and (first == "2026-06").all() and alpha in first.index \
            and set(first.index) == set(vtg.index) and (vtg["scenario"] == "A").all()
        self.add(f"hero Alpha: new supplier {cfg.ALPHA_SUPPLIER} shared with 4 other A importers, all starting 2026-06", ok,
                 f"importers {sorted(first.index)}")
        beta = a.merge(d[["num_declaration", "mf_importateur"]], on="num_declaration").merge(self.t("ref_ndp")[["code_ndp", "prix_reference_tnd"]], on="code_ndp")
        beta = beta[beta["mf_importateur"] == "1000002CAM000"]
        n_low = int((beta["prix_unitaire_tnd"] / beta["prix_reference_tnd"] < 0.7).sum())
        self.add("hero Beta: unit price / reference < 0.7 on >= 3 articles", n_low >= 3, f"{n_low} articles")
        adeb = self.t("adeb_paiements")
        g = adeb[(adeb["mf_beneficiaire"] == "1000003DAM000") & (adeb["date_paiement"] >= "2025-09-01")]["montant_ht"].sum()
        gca = dm.loc[[("1000003DAM000", x) for x in m("2025-09", "2026-08")], "ca_total_declare"].sum()
        self.add("hero Gamma: ADEB receipts 12 m / declared CA 12 m >= 1.5", gca > 0 and g / gca >= 1.5, f"ratio {g / gca:.2f}")
        dl = dm.loc["1000004EAM000"]
        dorm = dl.loc[:"2026-02"]
        n_dorm = int(((dorm["statut_depot"] == "NON_DEPOSEE") | (dorm["ca_total_declare"] == 0)).sum())
        last6 = dl.loc["2026-03":"2026-08"]
        bad = int(((last6["statut_depot"] == "NON_DEPOSEE") | (last6["jours_retard"].fillna(0) > 30)).sum())
        dimp = caf.reindex([("1000004EAM000", x) for x in m("2026-03", "2026-08")]).fillna(0).sum()
        self.add("hero Delta: >= 12 dormant months, then imports; >= 3 of last 6 filings missing or > 30 days late",
                 n_dorm >= 12 and bad >= 3 and dimp > 500_000, f"dormant {n_dorm}, bad filings {bad}, imports {dimp:,.0f}")

        def app_margin(mf, lo, hi):
            x = dm.loc[[(mf, k) for k in m(lo, hi)]]
            imp = caf.reindex([(mf, k) for k in m(lo, hi)]).fillna(0).sum()
            return 1 - (imp + x["tva_deductible_biens_services_local"].sum() / 0.19) / x["ca_total_declare"].sum()
        m0, m1 = app_margin("1000005FAM000", "2024-09", "2025-08"), app_margin("1000005FAM000", "2025-09", "2026-08")
        m_last = app_margin("1000005FAM000", "2026-03", "2026-08")
        self.add("hero Epsilon: apparent margin drifts from >= 20 % to <= 8 %", m0 >= 0.2 and m_last <= 0.08,
                 f"{m0:.1%} (12 m to 2025-08) -> {m1:.1%} (12 m to 2026-08), {m_last:.1%} (last 6 m)")
        z = "1000006GAM000"
        zi = caf.reindex([(z, k) for k in m("2026-04", "2026-08")]).fillna(0).mean() / caf.reindex([(z, k) for k in m("2025-02", "2026-01")]).fillna(0).mean()
        zc = dm.loc[[(z, k) for k in m("2026-04", "2026-08")], "ca_total_declare"].mean() / dm.loc[[(z, k) for k in m("2025-02", "2026-01")], "ca_total_declare"].mean()
        self.add("hero Zeta: imports and declared CA both up > x2, gap < 25 %", zi > 2 and zc > 2 and abs(zi / zc - 1) < 0.25, f"imports x{zi:.2f}, CA x{zc:.2f}")
        e = dm.loc["1000007HAM000"]
        ctl = self.t("historique_controles")
        ec = ctl[ctl["mf"] == "1000007HAM000"]
        ok = bool(c.loc["1000007HAM000", "statut_oea"]) and (e["statut_depot"] == "DEPOSEE").all() and (e["jours_retard"] == 0).all() \
            and len(ec) >= 1 and (ec["categorie_resultat"] == "CONFORME").all()
        self.add("hero Eta: OEA, every filing on time, past controls all CONFORME", ok, f"{len(ec)} control(s)")
        mt = self.t("metriques_noeuds")
        om = mt[(mt["mf"] == cfg.OMEGA_MF) & (mt["mois"] == "2026-08")]
        clients = set(self.t("verite_terrain").query("scenario == 'B' and id_reseau == 'RB01'")["mf"])
        cm = mt[mt["mf"].isin(clients) & (mt["mois"] == "2026-08")]
        a5 = self.t("employeur_annexe5")
        rec = a5[(a5["mf_fournisseur"] == cfg.OMEGA_MF) & (a5["exercice"] == 2025)]
        dis = self.t("declarations_is").set_index(["mf", "exercice"])
        decl = dis.loc[(cfg.OMEGA_MF, 2025), ["ca_local", "ca_export"]].sum()
        ok = len(om) == 1 and bool(om["est_profil_coquille"].iloc[0]) and len(clients) == 5 and set(rec["mf_payeur"]) == clients \
            and (cm["part_achats_coquilles"] >= 0.3).all() and rec["montant_ttc"].sum() >= 10 * decl
        self.add("hero Omega: shell profile, 5 clients since 2025-03, received >= 10x declared, clients' shell share >= 30 %", ok,
                 f"received {rec['montant_ttc'].sum():,.0f} vs declared {decl:,.0f}; client shell share min {cm['part_achats_coquilles'].min():.2f}")

    # ------------------------------------------------------------------
    def distributions(self) -> None:
        d = self.t("douane_declarations")
        share = d["circuit"].value_counts(normalize=True)
        ok = abs(share.get("V", 0) - 0.70) <= 0.05 and abs(share.get("O", 0) - 0.22) <= 0.05 and abs(share.get("R", 0) - 0.08) <= 0.04
        self.add("distribution: customs circuits close to 70/22/8", ok, " / ".join(f"{k} {share.get(k, 0):.1%}" for k in "VOR"))
        c = self.t("contribuables")
        ctl = self.t("historique_controles")
        rate = len(ctl) / len(c) / (21 / 12)
        self.add("distribution: control rate about 3 % a year", 0.02 <= rate <= 0.04, f"{rate:.2%} per year ({len(ctl)} controls)")
        vt = self.t("verite_terrain")
        fraud = vt["scenario"].isin(["A", "B", "C", "D", "E", "F", "COQUILLE"]).mean()
        self.add("distribution: share of companies with a fraud scenario (target about 8 %, 5-10 % accepted)", 0.05 <= fraud <= 0.10, f"{fraud:.1%}")
        imp = (c["code_en_douane"].fillna("") != "").mean()
        self.add("distribution: importers about 35 % of companies", 0.28 <= imp <= 0.42, f"{imp:.1%}")
        pub = self.t("adeb_paiements")["mf_beneficiaire"].nunique() / len(c)
        self.add("distribution: companies paid by public buyers about 15 %", 0.08 <= pub <= 0.22, f"{pub:.1%}")
        dm = self.t("declarations_mensuelles")
        honest = set(vt[vt["scenario"] == "AUCUN"]["mf"])
        x = dm[dm["mf"].isin(honest)]
        late = (x["jours_retard"].fillna(0) > 0).mean()
        miss = (x["statut_depot"] == "NON_DEPOSEE").mean()
        self.add("distribution: filing incidents of normal companies (about 6 % late, 2 % missed)", 0.03 <= late <= 0.12 and miss <= 0.05,
                 f"late {late:.1%}, missing {miss:.1%}")

    def signs_and_dates(self) -> None:
        allowed_negative = {("declarations_is", "resultat_comptable"), ("declarations_is", "resultat_fiscal")}
        neg = []
        for name in ["declarations_mensuelles", "declarations_is", "employeur_annexe1_synthese", "employeur_annexe2", "employeur_annexe5",
                     "douane_declarations", "douane_articles", "douane_liquidation", "adeb_paiements", "historique_controles",
                     "verite_terrain", "aretes", "metriques_noeuds", "contribuables"]:
            df = self.t(name)
            for col in df.select_dtypes("number").columns:
                if (name, col) not in allowed_negative and (df[col] < 0).any():
                    neg.append(f"{name}.{col}")
        self.add("no negative numbers (except accounting results)", not neg, ", ".join(neg))

        lo, hi, snap = str(cfg.WINDOW_START_DATE.date()), str(cfg.WINDOW_END_DATE.date()), str(cfg.SNAPSHOT_DATE.date())
        bad = []
        event_dates = {
            "douane_declarations": ["date_enregistrement"], "adeb_paiements": ["date_engagement", "date_ordonnancement", "date_paiement"],
            "historique_controles": ["date_avis", "date_debut", "date_fin", "date_notification_resultats"],
            "fournisseurs_etrangers": ["date_premiere_apparition"], "aretes": ["premiere_date", "derniere_date"],
        }
        for name, cols in event_dates.items():
            for col in cols:
                s = self.t(name)[col].dropna()
                if ((s < lo) | (s > hi)).any():
                    bad.append(f"{name}.{col}")
        for name, col in [("declarations_mensuelles", "date_depot"), ("declarations_mensuelles", "date_limite"), ("declarations_is", "date_depot")]:
            s = self.t(name)[col].dropna()
            if ((s < lo) | (s > snap)).any():
                bad.append(f"{name}.{col}")
        for name, col in [("declarations_mensuelles", "mois"), ("historique_controles", "periode_debut"), ("historique_controles", "periode_fin")]:
            s = self.t(name)[col]
            if ((s < cfg.WINDOW_START) | (s > cfg.WINDOW_END)).any():
                bad.append(f"{name}.{col}")
        ctl = self.t("historique_controles")
        order = ((ctl["date_avis"] <= ctl["date_debut"]) & (ctl["date_debut"] <= ctl["date_fin"]) & (ctl["date_fin"] <= ctl["date_notification_resultats"])).all()
        adeb = self.t("adeb_paiements")
        order &= ((adeb["date_engagement"] <= adeb["date_ordonnancement"]) & (adeb["date_ordonnancement"] <= adeb["date_paiement"])).all()
        av = ctl["date_avis"]
        self.add("dates: events in 2023-09..2026-08, filings by the 2026-09-30 extraction", not bad, ", ".join(bad))
        self.add("dates: controls avis 2024-10..2026-06; chronological order of control and payment steps",
                 bool(order) and av.min() >= "2024-10-01" and av.max() <= "2026-06-30", f"avis {av.min()} .. {av.max()}")

    def graph(self) -> None:
        mt = self.t("metriques_noeuds")
        e = self.t("aretes")
        ok = mt["mois"].min() == cfg.METRIC_START and mt["mois"].max() == cfg.WINDOW_END and mt["mois"].nunique() == 24
        self.add("graph: metrics for every month 2024-09..2026-08", ok, f"{mt['mois'].nunique()} months, {len(mt):,} rows")
        self.add("graph: distance values in {1, 2, 3, 99}", mt["distance_entite_redressee"].isin([1, 2, 3, 99]).all())
        ctl = self.t("historique_controles")
        f = ctl[ctl["categorie_resultat"] == "FRAUDE_SIGNIFICATIVE"]["date_notification_resultats"].sort_values()
        leak = False
        if len(f):
            first_month = f.iloc[0][:7]
            leak = (mt[mt["mois"] < first_month]["distance_entite_redressee"] != 99).any()
        self.add("graph: no future control used in distance_entite_redressee", not leak,
                 f"first fraud notification {f.iloc[0] if len(f) else 'none'}")
        types = set(e["type_relation"])
        self.add("graph: edge types", types <= {"IMPORT_FOURNISSEUR", "ACHAT_LOCAL_A5", "HONORAIRES_A2", "PAIEMENT_PUBLIC"}, ", ".join(sorted(types)))
        # Shell profile only for recent, staff-less companies whose clients report >= 3x their declared turnover
        sh = mt[mt["est_profil_coquille"]]
        vt = self.t("verite_terrain").set_index("mf")["scenario"]
        prec = (vt.reindex(sh["mf"].unique()) == "COQUILLE").mean() if len(sh) else 1.0
        self.add("graph: shell profile flags only shells of fake-invoice rings", prec >= 0.9, f"{sh['mf'].nunique()} flagged, {prec:.0%} are COQUILLE")

    def run(self) -> bool:
        for step in (self.keys, self.foreign_keys, self.customs, self.honest_coherence, self.scenarios, self.heroes,
                     self.distributions, self.signs_and_dates, self.graph):
            try:
                step()
            except Exception as exc:  # a crashing check is a failed check
                self.add(f"{step.__name__} (crashed)", False, f"{type(exc).__name__}: {exc}")
        width = max(len(r.name) for r in self.results)
        print(f"\nChecks on {self.raw.parent}/")
        for r in self.results:
            print(f"  [{'PASS' if r.ok else 'FAIL'}] {r.name:<{width}}  {r.detail}")
        n_fail = sum(not r.ok for r in self.results)
        print(f"\n{len(self.results) - n_fail}/{len(self.results)} checks passed")
        return n_fail == 0


def run_checks(root: Path) -> bool:
    return Checker(Path(root)).run()


def main() -> int:
    ap = argparse.ArgumentParser(description="Consistency checks on generated data.")
    ap.add_argument("--data", type=Path, default=Path("data"))
    args = ap.parse_args()
    return 0 if run_checks(args.data) else 1


if __name__ == "__main__":
    sys.exit(main())

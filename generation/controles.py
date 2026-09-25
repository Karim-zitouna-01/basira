"""Past tax audits (historique_controles.csv) and the hidden ground truth (verite_terrain.csv).

Selection is deliberately biased (modele_donnees.md 3.2): the static rule favours large companies
and "classic" sectors; cross-checks and tip-offs favour companies whose fraud has started. The
outcome is then drawn from the ground truth, so labels are partial and noisy, as in reality.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as cfg
from .activite import World

FRAUD_ROLES = ("A", "B", "C", "D", "E", "F", "COQUILLE")


def monthly_fraud(w: World) -> np.ndarray:
    """Evaded duties per company and month (TND)."""
    comp, a = w.comp, w.arr
    N, T = w.n, cfg.T
    F = np.zeros((N, T))
    role = comp["role"].to_numpy()
    marge = comp["marge"].to_numpy()[:, None]
    hid = np.isin(role, ["A", "D", "E", "F"])
    F[hid] = (a["hidden"][hid] * (0.19 + marge[hid] * 0.20))
    b = role == "B"
    F[b] = a["fake"][b] * (0.19 + 0.20)
    s = role == "COQUILLE"
    F[s] = np.maximum(a["real"][s] - a["decl"][s], 0) * 0.19
    for i in np.where(role == "C")[0]:
        t0 = int(comp.at[i, "t_start"])
        imp = a["imports"][i].copy()
        imp[:t0] = 0
        if imp.sum() > 0:
            F[i] = comp.at[i, "customs_evaded"] * imp / imp.sum()
    return F


def _rand_days(rng, lo, hi):
    return pd.Timedelta(days=int(rng.integers(lo, hi + 1)))


def simulate_controls(w: World) -> None:
    comp, rng, a = w.comp, w.rng, w.arr
    N = w.n
    F = monthly_fraud(w)
    a["fraud_monthly"] = F
    role = comp["role"].to_numpy()
    months = cfg.SIM_MONTHS

    n_ctrl = max(5, int(round(cfg.CONTROL_RATE_PER_YEAR * N * 21 / 12)))
    excluded = comp["is_hero"].to_numpy() | (comp["groupe"].to_numpy() == "GA01") | (comp["groupe"].to_numpy() == "RB01") | np.isin(role, ["DORMANT", "COQUILLE"])
    eta = w.idx_of("1000007HAM000")

    # Static-rule (SAR-like) score: size, classic sectors, filing incidents.
    classic = np.isin(comp["family"].to_numpy(), ["GROS", "BTP"]) | (comp["code_nat"].to_numpy() == "45.11")
    late_count = (a["filing_status"] != 0).sum(axis=1)
    sar = 0.8 * np.log(np.maximum(comp["ca_annuel"].to_numpy(), 1e4)) + 1.0 * classic + 0.08 * late_count + rng.normal(0, 0.5, N)
    sar_w = np.exp(sar - sar.max())

    span = (cfg.CONTROL_AVIS_END - cfg.CONTROL_AVIS_START).days
    origins = list(cfg.CONTROL_ORIGINS)
    ow = np.array(list(cfg.CONTROL_ORIGINS.values()))
    chosen: set[int] = set()
    plans = [(eta, pd.Timestamp("2025-04-14"), "PROGRAMME_RISQUE", "VERIF_PRELIMINAIRE")]
    chosen.add(eta)
    while len(plans) < n_ctrl:
        avis = cfg.CONTROL_AVIS_START + pd.Timedelta(days=int(rng.integers(0, span + 1)))
        if avis.dayofweek >= 5:
            continue
        t_avis = cfg.SIM_MONTHS.index(avis.strftime("%Y-%m"))
        origin = origins[int(rng.choice(len(origins), p=ow / ow.sum()))]
        elig = ~excluded & (comp["created_t"].to_numpy() <= t_avis - 12)
        elig[list(chosen)] = False
        started = np.isin(role, FRAUD_ROLES) & (comp["t_start"].to_numpy() >= 0) & (comp["t_start"].to_numpy() <= t_avis - 2)
        if origin == "PROGRAMME_RISQUE":
            wts = sar_w.copy()
        elif origin == "RECOUPEMENT":
            wts = 1 + 12 * started
        elif origin == "DENONCIATION":
            wts = 1 + 6 * started
        else:
            wts = np.ones(N)
        wts = np.where(elig, wts, 0).astype(float)
        if wts.sum() == 0:
            continue
        i = int(rng.choice(N, p=wts / wts.sum()))
        chosen.add(i)
        typ = str(rng.choice(["VERIF_PRELIMINAIRE", "VERIF_APPROFONDIE_PARTIELLE", "VERIF_APPROFONDIE_TOTALE"], p=[0.55, 0.25, 0.20]))
        plans.append((i, avis, origin, typ))

    rows = []
    limit_notif = cfg.WINDOW_END_DATE - pd.Timedelta(days=5)
    for k, (i, avis, origin, typ) in enumerate(sorted(plans, key=lambda p: p[1]), start=1):
        prelim = typ == "VERIF_PRELIMINAIRE"
        start = avis + (_rand_days(rng, 0, 10) if prelim else _rand_days(rng, 15, 30))
        dur = _rand_days(rng, 20, 75) if prelim else _rand_days(rng, 60, 180)
        notif_lag = _rand_days(rng, 15, 60)
        overflow = (start + dur + notif_lag) - limit_notif
        if overflow > pd.Timedelta(0):
            room = max((limit_notif - start).days, 10)
            dur = pd.Timedelta(days=max(5, int(room * 0.7)))
            notif_lag = pd.Timedelta(days=max(3, room - dur.days))
        end = start + dur
        notif = min(end + notif_lag, limit_notif)
        t_avis = months.index(avis.strftime("%Y-%m"))
        p_end = t_avis - 1
        p_start = max(cfg.OUT0, p_end - (11 if prelim else 23))
        impots = "TVA;RS" if prelim and rng.random() < 0.5 else ("TVA" if prelim else "TVA;IS;RS")

        r = role[i]
        fraud_active = r in FRAUD_ROLES and 0 <= comp.at[i, "t_start"] <= p_end
        if r == "CITOYEN_MODELE" or i == eta:
            cat = "CONFORME"
        elif fraud_active:
            cat = str(rng.choice(["FRAUDE_SIGNIFICATIVE", "REDRESSEMENT_MINEUR", "CONFORME"], p=[0.70, 0.25, 0.05]))
        else:
            cat = str(rng.choice(["CONFORME", "REDRESSEMENT_MINEUR", "FRAUDE_SIGNIFICATIVE"], p=[0.65, 0.33, 0.02]))

        ca_m = comp.at[i, "ca_annuel"] / 1e6
        if cat == "CONFORME":
            total, issue = 0.0, "SANS_REDRESSEMENT"
        elif cat == "REDRESSEMENT_MINEUR":
            total = float(rng.lognormal(np.log(12_000 * np.sqrt(max(ca_m, 0.05)) + 4_000), 0.5))
            issue = str(rng.choice(["ACCORD", "TAXATION_OFFICE", "CONTENTIEUX"], p=[0.80, 0.15, 0.05]))
        else:
            accrued = F[i, : p_end + 1].sum()
            total = max(60_000.0, accrued * rng.uniform(0.6, 1.1)) if fraud_active else float(rng.lognormal(np.log(200_000), 0.6))
            issue = str(rng.choice(["ACCORD", "TAXATION_OFFICE", "CONTENTIEUX"], p=[0.40, 0.35, 0.25]))
        taxes = impots.split(";")
        split = {"TVA": 0.45, "IS": 0.35, "RS": 0.20}
        norm = sum(split[x] for x in taxes)
        amounts = {x: round(total * split[x] / norm, 3) if x in taxes else 0.0 for x in split}
        pen = round(total * rng.uniform(0.15, 0.5), 3) if total else 0.0
        rec_share = {"SANS_REDRESSEMENT": 0.0, "ACCORD": rng.uniform(0.7, 1.0), "TAXATION_OFFICE": rng.uniform(0.2, 0.6),
                     "CONTENTIEUX": rng.uniform(0.0, 0.2)}[issue]
        rows.append({
            "id_controle": f"CTL-{avis.year}-{k:06d}", "mf": comp.at[i, "mf"], "type_controle": typ, "origine_selection": origin,
            "date_avis": avis, "date_debut": start, "date_fin": end, "periode_debut": months[p_start], "periode_fin": months[p_end],
            "impots_verifies": impots, "date_notification_resultats": notif, "issue": issue, "categorie_resultat": cat,
            "montant_redresse_tva": amounts["TVA"], "montant_redresse_is": amounts["IS"], "montant_redresse_rs": amounts["RS"],
            "penalites": pen, "montant_recouvre": round((sum(amounts.values()) + pen) * rec_share, 3),
        })
    w.tables["historique_controles"] = pd.DataFrame(rows)


def build_ground_truth(w: World) -> None:
    comp, a = w.comp, w.arr
    scen = comp["role"].map({"A": "A", "B": "B", "C": "C", "D": "D", "E": "E", "F": "F", "COQUILLE": "COQUILLE",
                             "CROISSANCE_LEGITIME": "CROISSANCE_LEGITIME", "CITOYEN_MODELE": "CITOYEN_MODELE"}).fillna("AUCUN")
    has_start = comp["t_start"] >= 0
    vt = pd.DataFrame({
        "mf": comp["mf"],
        "scenario": scen,
        "mois_debut_scenario": np.where(has_start & (scen != "AUCUN"), [cfg.SIM_MONTHS[t] if t >= 0 else "" for t in comp["t_start"]], ""),
        "intensite": np.where(scen.isin(["AUCUN", "CITOYEN_MODELE"]), 0.0, comp["intensite"].round(3)),
        "montant_fraude_reel": a["fraud_monthly"].sum(axis=1).round(3),
        "id_reseau": comp["groupe"].fillna(""),
    })
    w.tables["verite_terrain"] = vt

"""Monthly tax declarations (form 2023) and annual corporate income tax (IS) returns.

Declared amounts are the real ones except where a scenario changed `decl`, `fake` or the declared
public withholding. Deductible import VAT of month M is the customs VAT 105 liquidated in M-1.
Missed filings older than 2026 were regularised later (code 1, late); recent ones may still be
missing at the extraction date.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as cfg
from .activite import World
from .employeur import YEAR_T, ttc_factor
from .referentiels import NAT_BY_CODE

ON_TIME, LATE, REGULARISED, MISSING, ZERO = 0, 1, 2, 3, 4


def _deadline(t: int) -> pd.Timestamp:
    p = pd.Period(cfg.SIM_MONTHS[t], freq="M") + 1
    return pd.Timestamp(year=p.year, month=p.month, day=28)


DEADLINES = [_deadline(t) for t in range(cfg.T)]


def _filing(w: World) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Returns status (N,T), filing date offsets in days vs deadline (N,T), code_declaration (N,T)."""
    comp, rng = w.comp, w.rng
    N, T = w.n, cfg.T
    status = np.full((N, T), ON_TIME)
    days = np.zeros((N, T), dtype=int)
    code = np.zeros((N, T), dtype=int)
    snap = cfg.SNAPSHOT_DATE
    for i, row in comp.iterrows():
        role, t0 = row["role"], int(row["t_start"])
        for t in range(T):
            limit = DEADLINES[t]
            u = rng.random()
            if role in ("DORMANT", "E") and (role == "DORMANT" or t < t0):
                if u < row["zero_filing_p"]:
                    d = int(rng.integers(-20, 1)) if rng.random() < 0.7 else int(rng.integers(1, 90))
                    if limit + pd.Timedelta(days=d) > snap:
                        status[i, t] = MISSING
                    else:
                        status[i, t], days[i, t] = ZERO, d
                else:
                    status[i, t] = MISSING
                continue
            if role == "E":
                p_miss, p_late, late_long = 0.35, 0.3, True
            elif role == "COQUILLE":
                p_miss, p_late, late_long = 0.3, 0.3, True
            else:
                p_miss, p_late, late_long = row["p_miss"], row["p_late"], False
            if u < p_miss:
                # Returns of a closed fiscal year are regularised before the IS return; recent ones may still be missing.
                if int(cfg.SIM_MONTHS[t][:4]) <= 2025 or rng.random() < 0.5:
                    d = int(rng.integers(35, 301))
                    d = min(d, (snap - limit).days)
                    if d >= 31 and role not in ("E", "COQUILLE"):
                        status[i, t], days[i, t], code[i, t] = REGULARISED, d, 1
                        continue
                status[i, t] = MISSING
            elif u < p_miss + p_late:
                d = int(rng.integers(31, 121)) if (late_long or rng.random() < 0.3) else int(rng.integers(1, 31))
                if limit + pd.Timedelta(days=d) > snap:
                    status[i, t] = MISSING
                else:
                    status[i, t], days[i, t] = LATE, d
                    code[i, t] = 1 if d > 30 and rng.random() < 0.5 else 0
            else:
                days[i, t] = -int(rng.integers(0, 26))
                if rng.random() < 0.01:
                    code[i, t] = 2
    # Delta Trade: reactivated in 2026-03 with erratic filings (4 of the last 6 missing or > 30 days late).
    d = w.idx_of("1000004EAM000")
    for mois, (st, dd) in zip(["2026-03", "2026-04", "2026-05", "2026-06", "2026-07", "2026-08"],
                              [(LATE, 45), (MISSING, 0), (LATE, 38), (MISSING, 0), (ON_TIME, -3), (ON_TIME, -5)]):
        t = cfg.month_index(mois)
        status[d, t], days[d, t], code[d, t] = st, dd, 1 if st == LATE else 0
    return status, days, code


def simulate_declarations(w: World) -> None:
    comp, rng, a = w.comp, w.rng, w.arr
    N, T = w.n, cfg.T
    status, days, code = _filing(w)
    a["filing_status"] = status

    decl = a["decl"]
    exp_share = comp["export_share"].to_numpy()[:, None]
    mix = np.array([NAT_BY_CODE[c].vat for c in comp["code_nat"]])  # (N, 4)
    export = decl * exp_share
    dom = decl - export
    ca19, ca13, ca7, exo = (dom * mix[:, k][:, None] for k in range(4))
    tva_coll = 0.19 * ca19 + 0.13 * ca13 + 0.07 * ca7
    ded_immo = 0.19 * a["capex"]
    ded_local = 0.19 * (a["local"] + a["fake"]) * rng.lognormal(0, 0.02, (N, T))
    ded_import = np.zeros((N, T))
    ded_import[:, 1:] = a["tva105"][:, :-1] * rng.uniform(0.99, 1.01, (N, T - 1))

    pub = np.maximum(a["pub"], 1e-9)
    extra_share = np.clip(a["pub_extra"] / pub, 0, 1)
    ret_factor = comp["ret_decl_factor"].to_numpy()[:, None]
    ret_decl = a["ret_tva_subie"] * ((1 - extra_share) + extra_share * ret_factor)
    ret_decl = np.where(comp["role"].to_numpy()[:, None] == "D", ret_decl, a["ret_tva_subie"])

    filed = np.isin(status, [ON_TIME, LATE, REGULARISED])
    zero = status == ZERO
    active = a["active"]
    for arr in (ca19, ca13, ca7, exo, export, tva_coll, ded_immo, ded_local, ded_import, ret_decl):
        arr[zero] = 0.0

    # Withholding, training tax, FOPROLOS, TCL, per year of the month
    yidx = np.array([min(int(m[:4]), 2025) - cfg.EXERCICES[0] for m in cfg.SIM_MONTHS])
    grow = np.array([1.03 if m.startswith("2026") else 1.0 for m in cfg.SIM_MONTHS])
    ret_versees = (a["irpp_year"] + a["a5_retenues_payer"] + a["a2_retenues_payer"])[:, yidx] / 12 * grow * rng.lognormal(0, 0.05, (N, T))
    masse_m = a["masse_year"][:, yidx] / 12 * grow
    tfp_rate = np.where(comp["family"].to_numpy() == "INDUSTRIE", 0.01, 0.02)[:, None]
    tfp = masse_m * tfp_rate
    foprolos = masse_m * 0.01
    tcl = 0.002 * (dom * (1 + (0.19 * mix[:, 0] + 0.13 * mix[:, 1] + 0.07 * mix[:, 2]))[:, None])
    for arr in (ret_versees, tfp, foprolos, tcl):
        arr[zero] = 0.0

    credit_prev = np.zeros((N, T))
    tva_pay = np.zeros((N, T))
    credit_end = np.zeros((N, T))
    carry = np.zeros(N)
    for t in range(T):
        credit_prev[:, t] = carry
        net = tva_coll[:, t] - ded_immo[:, t] - ded_local[:, t] - ded_import[:, t] - ret_decl[:, t] - carry
        f = (filed[:, t] | zero[:, t]) & active[:, t]
        tva_pay[:, t] = np.where(f, np.maximum(net, 0), 0)
        credit_end[:, t] = np.where(f, np.maximum(-net, 0), carry)
        carry = credit_end[:, t]

    ca_total = ca19 + ca13 + ca7 + exo + export
    a["ca_declared_filed"] = np.where(filed | zero, ca_total, 0.0) * active
    a["export_declared_filed"] = np.where(filed | zero, export, 0.0) * active

    # Long format, published window only
    ii, tt = np.nonzero(active[:, cfg.OUT0:])
    tt = tt + cfg.OUT0
    st = status[ii, tt]
    dep = np.isin(st, [ON_TIME, LATE, REGULARISED, ZERO])
    limit = np.array([DEADLINES[t] for t in tt], dtype="datetime64[ns]")
    dd = limit + days[ii, tt].astype("timedelta64[D]")

    def col(x):
        v = np.round(x[ii, tt], 3)
        return np.where(dep, v, np.nan)

    out = pd.DataFrame({
        "mf": comp["mf"].to_numpy()[ii],
        "mois": np.array(cfg.SIM_MONTHS)[tt],
        "statut_depot": np.where(dep, "DEPOSEE", "NON_DEPOSEE"),
        "code_declaration": pd.array(np.where(dep, code[ii, tt], 0), dtype="Int64"),
        "date_limite": limit,
        "date_depot": pd.to_datetime(np.where(dep, dd, np.datetime64("NaT", "ns"))),
        "jours_retard": pd.array(np.maximum(0, days[ii, tt]), dtype="Int64"),
        "ca_taxable_19": col(ca19), "ca_taxable_13": col(ca13), "ca_taxable_7": col(ca7),
        "ca_exonere": col(exo), "ca_export": col(export),
    })
    out.loc[~dep, ["code_declaration", "jours_retard"]] = pd.NA
    out["ca_total_declare"] = np.where(dep, (out["ca_taxable_19"] + out["ca_taxable_13"] + out["ca_taxable_7"] + out["ca_exonere"] + out["ca_export"]).round(3), np.nan)
    for name, arr in (("tva_collectee", tva_coll), ("tva_deductible_immobilisations", ded_immo),
                      ("tva_deductible_biens_services_local", ded_local), ("tva_deductible_import", ded_import),
                      ("tva_retenue_source_subie", ret_decl), ("credit_tva_reporte", credit_prev), ("tva_a_payer", tva_pay),
                      ("credit_tva_fin_mois", credit_end), ("retenues_source_versees", ret_versees), ("tfp", tfp),
                      ("foprolos", foprolos), ("tcl", tcl)):
        out[name] = col(arr)
    w.tables["declarations_mensuelles"] = out.sort_values(["mf", "mois"]).reset_index(drop=True)
    _declarations_is(w, filed | zero)


def _declarations_is(w: World, filed: np.ndarray) -> None:
    comp, rng, a = w.comp, w.rng, w.arr
    N = w.n
    role = comp["role"].to_numpy()
    nm = np.clip(rng.normal(0.05, 0.05, N), -0.15, 0.25)
    ttc = ttc_factor(comp)
    adeb = w.tables["adeb_paiements"]
    adeb_ret = np.zeros((N, len(cfg.EXERCICES)))
    if len(adeb):
        idx = comp.set_index("mf")["idx"]
        m = adeb["exercice"].isin(cfg.EXERCICES)
        np.add.at(adeb_ret, (adeb.loc[m, "mf_beneficiaire"].map(idx).to_numpy(), adeb.loc[m, "exercice"].to_numpy() - cfg.EXERCICES[0]),
                  adeb.loc[m, "retenue_is"].to_numpy())
    rows = []
    prev_is = None
    for k, y in enumerate(cfg.EXERCICES):
        yt = YEAR_T[y]
        exists = comp["created_t"].to_numpy() <= yt[-1]
        ca = a["ca_declared_filed"][:, yt].sum(axis=1) * np.clip(1 + rng.normal(0, 0.004, N), 0.985, 1.015)
        ca_exp = np.minimum(a["export_declared_filed"][:, yt].sum(axis=1), ca)
        real = a["real"][:, yt].sum(axis=1)
        hidden = np.maximum(real - a["decl"][:, yt].sum(axis=1), 0)
        fake = a["fake"][:, yt].sum(axis=1)
        res = nm * real - hidden - fake
        res = np.where(np.isin(role, ["COQUILLE"]), ca * rng.uniform(-0.02, 0.03, N), res)
        rf = res + np.abs(rng.normal(0, 0.01, N)) * ca
        taux = comp["taux_is"].to_numpy()
        is_theo = np.maximum(rf, 0) * taux / 100
        minimum = np.where(ca > 0, np.maximum(300.0, 0.002 * ca * ttc), 0.0)
        is_du = np.maximum(is_theo, minimum)
        young = comp["created_t"].to_numpy() > yt[0] - 12
        if prev_is is None:
            prev_is = is_du * rng.uniform(0.8, 1.2, N)
        acomptes = np.where(young, 0.0, 0.9 * prev_is)
        retenues = a["a5_retenues_received"][:, k] + a["a2_retenues_received"][:, k] + adeb_ret[:, k]
        css = np.maximum(rf, 0) * np.where(taux >= 35, 0.04, 0.03)
        a_payer = np.maximum(0, is_du - acomptes - retenues)
        credit = np.maximum(0, acomptes + retenues - is_du)
        prev_is = is_du
        limit = pd.Timestamp(year=y + 1, month=3, day=25)
        for i in np.where(exists)[0]:
            if role[i] in ("DORMANT", "E") and ca[i] == 0 and rng.random() < 0.5:
                continue
            late = rng.random() < (0.06 if comp.at[i, "p_late"] > 0 else 0.0)
            dep = limit + pd.Timedelta(days=int(rng.integers(1, 61)) if late else -int(rng.integers(0, 21)))
            rows.append({"mf": comp.at[i, "mf"], "exercice": y, "date_depot": min(dep, cfg.SNAPSHOT_DATE),
                         "ca_local": round(ca[i] - ca_exp[i], 3), "ca_export": round(ca_exp[i], 3),
                         "resultat_comptable": round(res[i], 3), "resultat_fiscal": round(rf[i], 3), "taux_is": taux[i],
                         "is_du": round(is_du[i], 3), "minimum_impot": round(minimum[i], 3), "acomptes_verses": round(acomptes[i], 3),
                         "retenues_imputees": round(retenues[i], 3), "css": round(css[i], 3), "is_a_payer": round(a_payer[i], 3),
                         "credit_is": round(credit[i], 3)})
    w.tables["declarations_is"] = pd.DataFrame(rows)

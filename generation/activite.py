"""Real economic activity (steps 1-2 of the generation order) and scenario injection (step 4).

All monthly quantities are (N, T) numpy arrays over SIM_MONTHS (2023-01 .. 2026-08), in TND HT.
`real_sales` is what the company really sells; `decl_sales` is what it declares. Both are equal
unless a scenario modifies the declared side.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import config as cfg
from .referentiels import NAT_BY_CODE, SEASON_PROFILES


@dataclass
class World:
    comp: pd.DataFrame
    rng: np.random.Generator
    ref: dict[str, pd.DataFrame]
    arr: dict[str, np.ndarray] = field(default_factory=dict)
    tables: dict[str, pd.DataFrame] = field(default_factory=dict)
    graphe: dict[str, pd.DataFrame] = field(default_factory=dict)

    @property
    def n(self) -> int:
        return len(self.comp)

    def idx_of(self, mf: str) -> int:
        return int(self.comp.index[self.comp["mf"] == mf][0])


def _beta(rng, a, b, n):
    return rng.beta(a, b, n)


def simulate_activity(w: World) -> None:
    comp, rng = w.comp, w.rng
    N, T = w.n, cfg.T
    t = np.arange(T)
    role = comp["role"].to_numpy()
    nat = [NAT_BY_CODE[c] for c in comp["code_nat"]]
    created = comp["created_t"].to_numpy()

    active = t[None, :] >= created[:, None]
    age = t[None, :] - created[:, None]
    ramp = np.clip((age + 1) / 6.0, 0, 1)  # new companies ramp up over 6 months

    citizen = role == "CITOYEN_MODELE"
    g = np.clip(rng.normal(0.04, 0.08, N), -0.2, 0.35)
    g = np.where(citizen, np.clip(rng.normal(0.04, 0.03, N), 0, 0.1), g)
    hero = comp["is_hero"].to_numpy()
    g = np.where(hero, 0.02, g)
    trend = (1 + g)[:, None] ** (t[None, :] / 12.0)

    prof = np.stack([SEASON_PROFILES[n.season] for n in nat])  # (N, 12)
    amp = rng.uniform(0.5, 1.0, N)[:, None]
    season = 1 + amp * (prof[:, t % 12] - 1)
    sigma = np.where(citizen | hero, 0.025, 0.04)[:, None]
    noise = rng.lognormal(0, 1, (N, T)) ** sigma

    base = comp["ca_annuel"].to_numpy().astype(float) / 12.0
    real = base[:, None] * trend * season * noise * ramp * active

    # One-off legitimate events (a big order) for a few normal companies, fully declared.
    ev = (role == "NORMAL") & (rng.random(N) < 0.04)
    ev_t = rng.integers(cfg.OUT0, T, N)
    ev_mult = rng.uniform(1.3, 2.0, N)
    real[ev, ev_t[ev]] *= ev_mult[ev]

    # Margins and purchases
    marge_ref = np.array([n.marge for n in nat])
    labour = np.array([n.labour for n in nat])
    marge = np.clip(marge_ref * rng.lognormal(0, 0.12, N), 0.05, 0.7)
    cogs_ratio = (1 - marge) * (1 - labour)
    overhead = rng.uniform(0.03, 0.08, N)
    fam = comp["family"].to_numpy()
    imp_share = np.select(
        [fam == "GROS", fam == "DETAIL", fam == "INDUSTRIE"],
        [_beta(rng, 6, 2, N), _beta(rng, 4, 3, N), _beta(rng, 3, 3, N)], _beta(rng, 2, 4, N))
    imp_share = np.where(comp["offshore"].to_numpy(), _beta(rng, 7, 2, N), imp_share)
    imp_share = np.where(comp["importer"].to_numpy(), np.clip(imp_share, 0.1, 0.95), 0.0)

    purch_noise = rng.lognormal(0, 1, (N, T)) ** 0.06
    goods = real * cogs_ratio[:, None] * purch_noise
    imports = goods * imp_share[:, None]
    local = goods * (1 - imp_share)[:, None] + real * overhead[:, None]

    # Public buyers (ADEB): share of real sales paid by the State.
    pub_p = np.array([n.public for n in nat])
    is_pub = (rng.random(N) < pub_p) & np.isin(role, ["NORMAL", "CITOYEN_MODELE", "CROISSANCE_LEGITIME", "D", "F", "B", "A"])
    lo = np.array([n.public_share[0] for n in nat])
    hi = np.array([n.public_share[1] for n in nat])
    pub_share = np.where(is_pub, rng.uniform(lo, hi), 0.0)
    exp_share = np.array([n.export for n in nat]) * rng.uniform(0.4, 1.4, N)
    exp_share = np.where(comp["offshore"].to_numpy(), rng.uniform(0.93, 1.0, N), np.clip(exp_share, 0, 0.8))
    exp_share = np.where(pub_share > 0, np.minimum(exp_share, 1 - pub_share - 0.05), exp_share)

    # Capital expenditure (deductible VAT on fixed assets), occasional.
    capex = (rng.random((N, T)) < 0.04) * (base * 12)[:, None] * rng.uniform(0.03, 0.25, (N, T)) * active

    comp["marge"] = marge
    comp["cogs_ratio"] = cogs_ratio
    comp["overhead"] = overhead
    comp["import_share"] = imp_share
    comp["pub_share"] = pub_share
    comp["export_share"] = exp_share
    comp["croissance"] = g
    w.arr.update(active=active, real=real, goods=goods, imports=imports, local=local, capex=capex,
                 pub=real * pub_share[:, None], fake=np.zeros((N, T)), pub_extra=np.zeros((N, T)),
                 hidden=np.zeros((N, T)), hidden_b2b=np.zeros((N, T)))


def _profile(t0: int, ramp_months: int, T: int) -> np.ndarray:
    """0 before t0, then linear ramp to 1 over `ramp_months` months (1 = immediate)."""
    t = np.arange(T)
    return np.clip((t - t0 + 1) / max(ramp_months, 1), 0, 1) * (t >= t0)


def inject_scenarios(w: World) -> None:
    comp, rng, a = w.comp, w.rng, w.arr
    T = cfg.T
    real, imports, local, goods = a["real"], a["imports"], a["local"], a["goods"]
    base_real = real.copy()
    a["imports_base"] = imports.copy()
    decl = real.copy()
    comp["c_factor"] = 1.0
    comp["ret_decl_factor"] = 1.0
    comp["zero_filing_p"] = 0.0

    for i, row in comp.iterrows():
        r, t0, q = row["role"], int(row["t_start"]), float(row["intensite"])
        if r == "A":
            is_alpha_group = row["groupe"] == "GA01"
            K = 3.4 if row["mf"] == cfg.ALPHA_MF else (2.0 + 2.0 * q)
            ramp = 1 if is_alpha_group else int(rng.integers(1, 4))
            k = 1 + (K - 1) * _profile(t0, ramp, T)
            if row["a_import"]:
                if imports[i, :t0].sum() <= 0:
                    raise ValueError(f"A importer {row['mf']} has no baseline imports")
                extra_imp = imports[i] * (k - 1)
                imports[i] += extra_imp
                a["hidden"][i] += extra_imp / row["cogs_ratio"]
            if row["a_clients"]:
                hb = base_real[i] * (k - 1) * 0.8
                a["hidden_b2b"][i] += hb
                a["hidden"][i] += hb
            real[i] += a["hidden"][i]
            decl[i] = base_real[i]
        elif r == "B":
            f = 0.4 + 0.8 * q
            a["fake"][i] = local[i] * f * _profile(t0, 1, T)
        elif r == "COQUILLE":
            real[i] = 0.0
            decl[i] = 0.0
            local[i] = 0.0
            goods[i] = 0.0
            imports[i] = 0.0
        elif r == "C":
            comp.at[i, "c_factor"] = 0.7 - 0.25 * q if row["mf"] != "1000002CAM000" else 0.52
        elif r == "D":
            decl_year = base_real[i, t0 - 12:t0].sum()
            P = float(np.clip(decl_year * (0.8 + 1.2 * q), 300_000, 2_000_000))
            if row["mf"] == "1000003DAM000":
                P = 1_400_000.0
            extra = P / 12.0 * rng.lognormal(0, 0.25, T) * (np.arange(T) >= t0)
            a["pub_extra"][i] = extra
            a["pub"][i] += extra
            real[i] += extra
            a["hidden"][i] = extra
            comp.at[i, "ret_decl_factor"] = float(rng.uniform(0.0, 0.3)) if row["mf"] != "1000003DAM000" else 0.0
            # Extra works need extra material (not a coherence signal on its own).
            goods[i] += extra * row["cogs_ratio"]
            local[i] += extra * row["cogs_ratio"] * 0.5
            decl[i] = base_real[i]
        elif r in ("E", "DORMANT"):
            before = np.arange(T) < (t0 if r == "E" else T)
            comp.at[i, "zero_filing_p"] = float(rng.uniform(0.3, 0.8))
            real[i, before] = 0.0
            goods[i, before] = 0.0
            imports[i, before] = 0.0
            local[i, before] = 0.0
            a["capex"][i, before] = 0.0
            a["pub"][i] = 0.0
            if r == "E":
                monthly = 350_000.0 if row["mf"] == "1000004EAM000" else float(rng.uniform(100_000, 800_000) * (0.4 + 0.6 * q))
                prof = _profile(t0, 1, T) * rng.lognormal(0, 0.2, T)
                imports[i] = monthly * prof
                goods[i] = imports[i]
                real[i] = imports[i] / row["cogs_ratio"]
                local[i] = real[i] * row["overhead"] * 0.5
                share = 0.06 if row["mf"] == "1000004EAM000" else float(rng.uniform(0.05, 0.2))
                decl[i] = real[i] * share
                a["hidden"][i] = real[i] - decl[i]
            else:
                decl[i] = 0.0
        elif r == "F":
            R = 9 if row["mf"] == "1000005FAM000" else int(6 + round(6 * (1 - q)))
            G = 1.3 + 0.5 * q
            gp = 1 + (G - 1) * _profile(t0, R, T)
            for key in ("real", "goods", "imports", "local"):
                a[key][i] *= gp
            # Declared turnover is set from realised purchases once customs exist (finalise_margin_compression).
            comp.at[i, "f_ramp"] = R
            comp.at[i, "f_target"] = 0.03 if row["mf"] == "1000005FAM000" else float(rng.uniform(0.02, 0.05))
        elif r == "CROISSANCE_LEGITIME":
            if row["mf"] == "1000006GAM000":
                G, R, gi = 2.6, 3, 2.8 / 2.6
            else:
                G, R, gi = 1.8 + 1.2 * q, int(rng.integers(3, 7)), float(rng.uniform(1.0, 1.1))
            gp = 1 + (G - 1) * _profile(t0, R, T)
            for key in ("real", "goods", "local", "pub", "capex"):
                a[key][i] *= gp
            imports[i] *= 1 + (G * gi - 1) * _profile(t0, R, T)
            if row["mf"] == "1000006GAM000" or rng.random() < 0.3:
                # new public contracts, fully declared
                add = real[i] * 0.25 * _profile(t0, R, T)
                a["pub"][i] += add
            decl[i] = real[i]
        elif r == "MICRO":
            local[i] *= 0.5

    # Shells: declared turnover is 0-10 % of what their clients will report paying them.
    for net, grp in comp[comp["role"] == "COQUILLE"].groupby("groupe"):
        clients = comp.index[(comp["role"] == "B") & (comp["groupe"] == net)]
        fake_total = a["fake"][clients].sum(axis=0)  # (T,)
        shells = grp.index.to_numpy()
        split = rng.dirichlet(np.ones(len(shells)))
        for s, share in zip(shells, split):
            ratio = 0.036 if comp.at[s, "mf"] == cfg.OMEGA_MF else float(rng.uniform(0.0, 0.1))
            a["real"][s] = fake_total * share  # invoiced (fictitious) sales
            decl[s] = fake_total * share * ratio * rng.lognormal(0, 0.3, T)
            comp.at[s, "fake_share"] = share
        a.setdefault("shell_of", {})[net] = shells

    a["decl"] = np.maximum(decl, 0.0) * a["active"]
    a["base_real"] = base_real


def finalise_margin_compression(w: World) -> None:
    """Scenario F: declared turnover = realised purchases / (1 - m(t)), m drifting to 2-5 %.

    Uses the customs values actually declared (lumpy shipments), smoothed over 3 months, so the
    apparent margin a peer analysis would compute follows the intended drift.
    """
    comp, a = w.comp, w.arr
    T = cfg.T
    for i in comp.index[comp["role"] == "F"]:
        t0, R, mT = int(comp.at[i, "t_start"]), int(comp.at[i, "f_ramp"]), float(comp.at[i, "f_target"])
        purch = a["caf_declared"][i] + a["local"][i]
        lo = max(0, t0 - 12)
        m0 = 1 - purch[lo:t0].sum() / max(a["real"][i, lo:t0].sum(), 1.0)
        m = m0 + (mT - m0) * _profile(t0, R, T)
        smooth = pd.Series(purch).rolling(3, min_periods=1).mean().to_numpy()
        decl = np.where(np.arange(T) >= t0, np.minimum(a["real"][i], smooth / (1 - m)), a["decl"][i])
        a["decl"][i] = np.maximum(decl, 0) * a["active"][i]
        a["hidden"][i] = np.maximum(a["real"][i] - a["decl"][i], 0)

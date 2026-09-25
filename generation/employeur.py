"""Employer declaration annexes: I (salaries, aggregated), II (fees, commissions, rents), V (purchases >= 1000 TTC).

Annex V is generated as a client -> supplier allocation of each client's real local purchases, so
the client's annex V line is the same transaction as the supplier's sale. For honest suppliers the
total received is capped below their declared turnover (TTC). Only part of each client's purchases
goes to suppliers inside the simulated regional portfolio; purchases from suppliers outside it are
not listed (their matricule is not in contribuables.csv).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as cfg
from .activite import World
from .referentiels import NAT_BY_CODE, SUPPLIER_AFFINITY

YEAR_T = {y: np.array([t for t, m in enumerate(cfg.SIM_MONTHS) if m.startswith(str(y))]) for y in cfg.EXERCICES}
NOT_SUPPLIER = ("COQUILLE", "DORMANT", "E")
NOT_PAYER = ("COQUILLE", "DORMANT")
CONSULT = ["70.22", "71.12", "73.11", "62.02"]
FRAUD_CIRCLE = ("A", "B", "C", "D", "F")


def ttc_factor(comp: pd.DataFrame) -> np.ndarray:
    """TTC / HT ratio of declared turnover (export and exempt sales carry no VAT)."""
    f = []
    for code, exp in zip(comp["code_nat"], comp["export_share"]):
        s19, s13, s7, exo = NAT_BY_CODE[code].vat
        f.append(exp + (1 - exp) * (s19 * 1.19 + s13 * 1.13 + s7 * 1.07 + exo))
    return np.array(f)


def _retenue_rate(taux_is: float) -> float:
    return 0.5 if taux_is <= 10 else (1.5 if taux_is >= 35 else 1.0)


def simulate_employer(w: World) -> None:
    comp, a = w.comp, w.arr
    role = comp["role"].to_numpy()
    created_year = comp["date_debut_activite"].dt.year.to_numpy()
    hero = comp["is_hero"].to_numpy()
    decl_ttc = {y: a["decl"][:, YEAR_T[y]].sum(axis=1) * ttc_factor(comp) for y in cfg.EXERCICES}
    real_y = {y: a["real"][:, YEAR_T[y]].sum(axis=1) for y in cfg.EXERCICES}
    exists = {y: comp["created_t"].to_numpy() <= YEAR_T[y][-1] for y in cfg.EXERCICES}
    a["decl_ttc_year"] = decl_ttc

    _annexe1(w, exists, real_y, hero, role)
    a2_received = _annexe2(w, exists, real_y, decl_ttc, role)
    _annexe5(w, exists, decl_ttc, a2_received, role, created_year)


def _annexe1(w, exists, real_y, hero, role):
    comp, rng = w.comp, w.rng
    rows = []
    for y in cfg.EXERCICES:
        for i in np.where(exists[y])[0]:
            eff0 = int(comp.at[i, "effectif"])
            if eff0 == 0 or role[i] in ("COQUILLE", "DORMANT", "MICRO"):
                continue
            if role[i] == "E" and real_y[y][i] <= 0:
                continue
            if hero[i]:
                nb = eff0
            else:
                ref = max(real_y[2024][i], 1.0)
                scale = (max(real_y[y][i], 1.0) / ref) ** 0.5 if role[i] != "A" else 1.0
                nb = max(1, int(round(eff0 * np.clip(scale, 0.7, 1.6) * rng.uniform(0.92, 1.08))))
            if comp.at[i, "created_t"] > YEAR_T[y][0]:
                nb = max(1, int(round(nb * (YEAR_T[y][-1] - comp.at[i, "created_t"] + 1) / 12)))
            salary = NAT_BY_CODE[comp.at[i, "code_nat"]].salary * 1.05 ** (y - 2023)
            masse = nb * salary * float(rng.lognormal(0, 0.12))
            rows.append({"mf": comp.at[i, "mf"], "exercice": y, "code_acte": 1 if rng.random() < 0.02 else 0,
                         "nb_salaries": nb, "masse_salariale_brute": round(masse, 3),
                         "irpp_retenu": round(masse * rng.uniform(0.12, 0.18), 3), "css_retenue": round(masse * 0.01, 3)})
    df = pd.DataFrame(rows)
    w.tables["employeur_annexe1_synthese"] = df
    masse = np.zeros((w.n, len(cfg.EXERCICES)))
    irpp = np.zeros_like(masse)
    idx = comp.set_index("mf")["idx"]
    if len(df):
        ii = df["mf"].map(idx).to_numpy()
        yy = df["exercice"].to_numpy() - cfg.EXERCICES[0]
        masse[ii, yy] = df["masse_salariale_brute"].to_numpy()
        irpp[ii, yy] = df["irpp_retenu"].to_numpy()
    w.arr["masse_year"] = masse
    w.arr["irpp_year"] = irpp


def _cin(rng) -> str:
    return f"{int(rng.choice([0, 1])):01d}{int(rng.integers(0, 10_000_000)):07d}"


def _annexe2(w, exists, real_y, decl_ttc, role):
    comp, rng = w.comp, w.rng
    N = w.n
    accountants = comp.index[(comp["code_nat"] == "69.20") & ~comp["role"].isin(NOT_SUPPLIER)].to_numpy()
    consultants = comp.index[comp["code_nat"].isin(CONSULT) & ~comp["role"].isin(NOT_SUPPLIER)].to_numpy()
    gouv = comp["gouvernorat_code"].to_numpy()
    has_acc = rng.random(N) < 0.75
    acc_of = np.full(N, -1)
    if len(accountants):
        for i in range(N):
            same = accountants[gouv[accountants] == gouv[i]]
            pool = same if len(same) and rng.random() < 0.8 else accountants
            acc_of[i] = int(rng.choice(pool))
    has_rent = rng.random(N) < 0.55
    landlord = [_cin(rng) for _ in range(N)]
    rows = []
    for y in cfg.EXERCICES:
        for i in np.where(exists[y])[0]:
            if role[i] in NOT_PAYER or real_y[y][i] <= 0:
                continue
            ca = real_y[y][i]
            if has_acc[i] and acc_of[i] >= 0 and acc_of[i] != i:
                fee = float(np.clip(2500 + 0.003 * ca, 2500, 90_000) * rng.lognormal(0, 0.25))
                rows.append((i, y, 1, int(acc_of[i]), comp.at[int(acc_of[i]), "mf"], 1, fee, 3.0))
            if len(consultants) and rng.random() < 0.2:
                j = int(rng.choice(consultants))
                if j != i:
                    amt = float(np.clip(ca * rng.uniform(0.002, 0.02), 3000, 250_000))
                    typ = 2 if comp.at[j, "code_nat"] == "73.11" else 1
                    rows.append((i, y, 1, j, comp.at[j, "mf"], typ, amt, 3.0))
            if has_rent[i]:
                amt = float(np.clip(ca * rng.uniform(0.005, 0.03), 4800, 360_000))
                rows.append((i, y, 2, -1, landlord[i], 4, amt, 10.0))
    df = pd.DataFrame(rows, columns=["_i", "exercice", "type_id_beneficiaire", "_j", "id_beneficiaire", "type_montant", "montant_brut", "taux_retenue"])
    # Cap what each firm receives at 60 % of its declared turnover TTC.
    received = np.zeros((N, len(cfg.EXERCICES)))
    firm = df["_j"] >= 0
    for y in cfg.EXERCICES:
        m = firm & (df["exercice"] == y)
        tot = df[m].groupby("_j")["montant_brut"].sum()
        cap = 0.6 * decl_ttc[y][tot.index.to_numpy()]
        scale = np.where(tot.to_numpy() > cap, cap / np.maximum(tot.to_numpy(), 1e-9), 1.0)
        df.loc[m, "montant_brut"] *= df.loc[m, "_j"].map(dict(zip(tot.index, scale))).to_numpy()
    df = df[df["montant_brut"] >= 1000].copy()
    df["montant_brut"] = df["montant_brut"].round(3)
    df["retenue"] = (df["montant_brut"] * df["taux_retenue"] / 100).round(3)
    df["montant_net"] = (df["montant_brut"] - df["retenue"]).round(3)
    df["mf_payeur"] = comp["mf"].to_numpy()[df["_i"].to_numpy()]
    df["code_acte"] = np.where(rng.random(len(df)) < 0.02, 1, 0)
    df = df.sort_values(["exercice", "mf_payeur", "id_beneficiaire"]).reset_index(drop=True)
    df["id_ligne"] = "A2-" + df["exercice"].astype(str) + "-" + df["mf_payeur"] + "-" + (df.groupby(["exercice", "mf_payeur"]).cumcount() + 1).map(lambda k: f"{k:06d}")
    for y in cfg.EXERCICES:
        m = (df["_j"] >= 0) & (df["exercice"] == y)
        np.add.at(received[:, y - cfg.EXERCICES[0]], df.loc[m, "_j"].to_numpy().astype(int), df.loc[m, "montant_brut"].to_numpy())
    pay = np.zeros((N, len(cfg.EXERCICES)))
    np.add.at(pay, (df["_i"].to_numpy(), df["exercice"].to_numpy() - cfg.EXERCICES[0]), df["retenue"].to_numpy())
    w.arr["a2_retenues_payer"] = pay
    w.arr["a2_retenues_received"] = np.zeros_like(pay)
    m = df["_j"] >= 0
    np.add.at(w.arr["a2_retenues_received"], (df.loc[m, "_j"].to_numpy().astype(int), df.loc[m, "exercice"].to_numpy() - cfg.EXERCICES[0]), df.loc[m, "retenue"].to_numpy())
    w.tables["employeur_annexe2"] = df[["id_ligne", "mf_payeur", "exercice", "code_acte", "type_id_beneficiaire", "id_beneficiaire",
                                        "type_montant", "montant_brut", "taux_retenue", "retenue", "montant_net"]]
    w.tables["_a2_internal"] = df
    return received


def _annexe5(w, exists, decl_ttc, a2_received, role, created_year):
    comp, rng, a = w.comp, w.rng, w.arr
    N = w.n
    fam = comp["family"].to_numpy()
    gouv = comp["gouvernorat_code"].to_numpy()
    b2b = np.array([NAT_BY_CODE[c].b2b for c in comp["code_nat"]])
    b2b = np.minimum(b2b, np.maximum(0.0, 1 - comp["pub_share"].to_numpy() - comp["export_share"].to_numpy()))
    eligible_sup = ~np.isin(role, NOT_SUPPLIER) & (b2b > 0.03)
    eff = comp["effectif"].to_numpy()
    local = a["local"]

    cap_w = np.maximum(decl_ttc[2024] + decl_ttc[2025], 1.0) * b2b
    by_fam: dict[str, np.ndarray] = {}
    by_fam_gouv: dict[tuple[str, int], np.ndarray] = {}
    for f in set(fam):
        ids = np.where(eligible_sup & (fam == f))[0]
        by_fam[f] = ids
        for g in set(gouv[ids]):
            by_fam_gouv[(f, int(g))] = ids[gouv[ids] == g]

    fraud_sup = np.where(eligible_sup & np.isin(role, FRAUD_CIRCLE))[0]

    def draw_supplier(i: int, exclude: set[int]) -> int | None:
        # Fraud homophily: companies with a fraud scenario trade more often with each other.
        if role[i] in FRAUD_CIRCLE and len(fraud_sup) > 1 and rng.random() < 0.3:
            j = int(rng.choice(fraud_sup))
            if j != i and j not in exclude:
                return j
        aff = SUPPLIER_AFFINITY[fam[i]]
        fams = [f for f in aff if len(by_fam.get(f, []))]
        if not fams:
            return None
        p = np.array([aff[f] for f in fams])
        for _ in range(10):
            f = fams[int(rng.choice(len(fams), p=p / p.sum()))]
            pool = by_fam_gouv.get((f, int(gouv[i])), np.array([], dtype=int))
            if len(pool) < 3 or rng.random() < 0.4:
                pool = by_fam[f]
            wts = cap_w[pool] ** 0.7
            j = int(pool[rng.choice(len(pool), p=wts / wts.sum())])
            if j != i and j not in exclude:
                return j
        return None

    # Relations: (client, supplier) -> (first year, strength); churn about 12 % a year.
    rel_rows = []
    phi = rng.uniform(0.25, 0.6, N)
    for i in range(N):
        if role[i] in NOT_PAYER or local[i].sum() <= 0:
            continue
        k = int(np.clip(2 + round(0.6 * np.sqrt(eff[i])) + rng.poisson(1), 1, 30))
        current: dict[int, tuple[int, float]] = {}
        for y in cfg.EXERCICES:
            if not exists[y][i]:
                continue
            if current:
                for j in list(current):
                    if rng.random() < 0.12 and role[i] != "CITOYEN_MODELE":
                        del current[j]
            attempts = 0
            while len(current) < k and attempts < 3 * k:
                attempts += 1
                j = draw_supplier(i, set(current))
                if j is None:
                    break
                if not exists[y][j]:
                    continue
                if y == cfg.EXERCICES[0]:
                    # Relationships seen in the first year mostly predate it; only the usual churn (~12 %)
                    # or a company created that year makes them new in 2023.
                    lo = max(created_year[i], created_year[j])
                    first = 2023 if lo >= 2023 or rng.random() < 0.12 else int(rng.integers(lo, 2023))
                else:
                    first = y
                current[j] = (first, float(rng.lognormal(0, 1)))
            yt = YEAR_T[y]
            L = local[i, yt].sum() * 1.19 * phi[i]
            if L <= 0 or not current:
                continue
            js = np.array(list(current))
            st = np.array([current[j][1] for j in js])
            amts = L * st / st.sum()
            for j, amt in zip(js, amts):
                if exists[y][j]:
                    rel_rows.append((i, int(j), y, current[int(j)][0], float(amt)))
    rel = pd.DataFrame(rel_rows, columns=["_i", "_j", "exercice", "premiere_annee_relation", "montant_ttc"])

    # Capacity: honest suppliers never receive more than 90 % x b2b share of declared TTC, minus annex II.
    for y in cfg.EXERCICES:
        m = rel["exercice"] == y
        tot = rel[m].groupby("_j")["montant_ttc"].sum()
        j = tot.index.to_numpy()
        cap = np.maximum(0.0, 0.9 * b2b[j] * decl_ttc[y][j] - a2_received[j, y - cfg.EXERCICES[0]])
        scale = np.where(tot.to_numpy() > cap, cap / np.maximum(tot.to_numpy(), 1e-9), 1.0)
        rel.loc[m, "montant_ttc"] *= rel.loc[m, "_j"].map(dict(zip(j, scale))).to_numpy()

    extra = []
    # Scenario B: fake invoices from the shells, declared by their clients.
    for net, shells in a.get("shell_of", {}).items():
        clients = comp.index[(comp["role"] == "B") & (comp["groupe"] == net)].to_numpy()
        for y in cfg.EXERCICES:
            for c in clients:
                fake_ttc = a["fake"][c, YEAR_T[y]].sum() * 1.19
                if fake_ttc <= 0:
                    continue
                for s in shells:
                    extra.append((int(c), int(s), y, y, fake_ttc * float(comp.at[s, "fake_share"])))
    # Scenario A (clients variant): clients report paying more than the supplier declares.
    for s in comp.index[(comp["role"] == "A") & comp["a_clients"]]:
        for y in cfg.EXERCICES:
            hidden = a["hidden_b2b"][s, YEAR_T[y]].sum() * 1.19
            if hidden <= 0:
                continue
            incoming = rel[(rel["_j"] == s) & (rel["exercice"] == y)]
            new_clients = []
            for _ in range(int(rng.integers(1, 4))):
                cands = np.where(exists[y] & ~np.isin(role, NOT_PAYER) & (np.arange(N) != s))[0]
                new_clients.append(int(rng.choice(cands)))
            weights = list(incoming["montant_ttc"].to_numpy()) + [incoming["montant_ttc"].mean() if len(incoming) else 1.0] * len(new_clients)
            wts = np.array(weights) / np.sum(weights)
            targets = list(zip(incoming["_i"].to_numpy(), incoming["premiere_annee_relation"].to_numpy())) + [(c, y) for c in new_clients]
            for (c, first), wt in zip(targets, wts):
                extra.append((int(c), int(s), y, int(first), hidden * float(wt)))
    if extra:
        rel = pd.concat([rel, pd.DataFrame(extra, columns=rel.columns)], ignore_index=True)
        rel = rel.groupby(["_i", "_j", "exercice"], as_index=False).agg(
            premiere_annee_relation=("premiere_annee_relation", "min"), montant_ttc=("montant_ttc", "sum"))

    rel = rel[rel["montant_ttc"] >= 1000].copy()
    rel["montant_ttc"] = rel["montant_ttc"].round(3)
    rel["mf_payeur"] = comp["mf"].to_numpy()[rel["_i"].to_numpy()]
    rel["mf_fournisseur"] = comp["mf"].to_numpy()[rel["_j"].to_numpy()]
    rel["taux_retenue"] = [_retenue_rate(t) for t in comp["taux_is"].to_numpy()[rel["_j"].to_numpy()]]
    rel["retenue_is"] = (rel["montant_ttc"] * rel["taux_retenue"] / 100).round(3)
    rel["retenue_tva"] = 0.0
    rel["montant_net"] = (rel["montant_ttc"] - rel["retenue_is"] - rel["retenue_tva"]).round(3)
    rel["code_acte"] = np.where(rng.random(len(rel)) < 0.03, 1, 0)
    rel = rel.sort_values(["exercice", "mf_payeur", "mf_fournisseur"]).reset_index(drop=True)
    rel["id_ligne"] = "A5-" + rel["exercice"].astype(str) + "-" + rel["mf_payeur"] + "-" + (rel.groupby(["exercice", "mf_payeur"]).cumcount() + 1).map(lambda k: f"{k:06d}")

    ny = len(cfg.EXERCICES)
    ret_paid = np.zeros((N, ny))
    ret_recv = np.zeros((N, ny))
    np.add.at(ret_paid, (rel["_i"].to_numpy(), rel["exercice"].to_numpy() - cfg.EXERCICES[0]), rel["retenue_is"].to_numpy())
    np.add.at(ret_recv, (rel["_j"].to_numpy(), rel["exercice"].to_numpy() - cfg.EXERCICES[0]), rel["retenue_is"].to_numpy())
    a["a5_retenues_payer"] = ret_paid
    a["a5_retenues_received"] = ret_recv
    w.tables["employeur_annexe5"] = rel[["id_ligne", "mf_payeur", "exercice", "code_acte", "mf_fournisseur", "montant_ttc", "taux_retenue",
                                         "retenue_is", "retenue_tva", "montant_net", "premiere_annee_relation"]]

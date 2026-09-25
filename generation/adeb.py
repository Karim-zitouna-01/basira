"""Public-spending payments (ADEB payment orders) to companies.

Public sales accrue monthly in the activity model; they are paid in lumps (payment orders),
each tied to an engagement of a public buyer. The 25 % VAT withholding and the 0.5/1/1.5 % IS
withholding follow modele_donnees.md 1.7 and 1.9.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as cfg
from .activite import World
from .referentiels import GOUV_LIBELLE

BUYER_AFFINITY = {
    "BTP": ["07", "05", "09", "08"],
    "SERVICES": ["16", "03", "11", "08", "07", "05", "09"],
    "GROS": ["11", "08", "16", "10", "05", "09", "03"],
    "INDUSTRIE": ["11", "10", "12", "14"],
    "TRANSPORT": ["14", "12", "05"],
    "AUTRE": ["11", "08", "09", "05"],
}
PHARMA = {"46.46", "21.20", "47.73"}


def _is_rate(taux_is: float) -> float:
    return 0.5 if taux_is <= 10 else (1.5 if taux_is >= 35 else 1.0)


def _comptable(row: pd.Series) -> str:
    g = GOUV_LIBELLE.get(int(row["gouvernorat_code"]), "Tunis")
    if row["type"] == "COMMUNE":
        return f"Receveur municipal - {row['libelle'].replace('Commune de ', '')}"
    if row["type"] == "ENTREPRISE_PUBLIQUE":
        return f"Agent comptable - {row['libelle']}"
    if row["type"] == "MINISTERE":
        return "Payeur général de Tunisie"
    return f"Trésorier régional de {g}"


def simulate_adeb(w: World) -> None:
    comp, rng, a = w.comp, w.rng, w.arr
    buyers = w.ref["ref_acheteurs_publics"]
    pub = a["pub"]
    N, T = w.n, cfg.T
    ret_tva = np.zeros((N, T))
    rows = []
    months = cfg.SIM_MONTHS

    for i in np.where(pub.sum(axis=1) > 0)[0]:
        row = comp.loc[i]
        fam = row["family"]
        missions = ["11"] if row["code_nat"] in PHARMA else BUYER_AFFINITY.get(fam, ["05", "11"])
        cand = buyers[buyers["_mission_code"].isin(missions)]
        local = cand[(cand["gouvernorat_code"] == row["gouvernorat_code"]) | (cand["type"].isin(["MINISTERE", "ENTREPRISE_PUBLIQUE"]))]
        cand = local if len(local) >= 2 else cand
        k = min(len(cand), int(rng.integers(1, 5)))
        chosen = cand.sample(n=k, random_state=int(rng.integers(1 << 31)))
        bw = rng.dirichlet(np.ones(k) * 2)
        rate_is = _is_rate(float(row["taux_is"]))
        mean_m = pub[i][pub[i] > 0].mean()
        acc = 0.0
        for t in range(T):
            acc += pub[i, t]
            if acc <= 0:
                continue
            if rng.random() < 0.45 or acc > 3 * mean_m or t == T - 1 and rng.random() < 0.5:
                npay = 1 + int(rng.poisson(0.4))
                amounts = acc * rng.dirichlet(np.ones(npay) * 3)
                acc = 0.0
                y, m = int(months[t][:4]), int(months[t][5:7])
                dim = pd.Timestamp(year=y, month=m, day=1).days_in_month
                for amt in amounts:
                    if amt < 500:
                        continue
                    b = chosen.iloc[int(rng.choice(k, p=bw))]
                    day = pd.Timestamp(year=y, month=m, day=int(rng.integers(1, dim + 1)))
                    ht = round(float(amt), 3)
                    tva = round(ht * 0.19, 3)
                    ttc = round(ht + tva, 3)
                    r_tva = round(tva * 0.25, 3) if ttc >= 1000 else 0.0
                    r_is = round(ttc * rate_is / 100, 3) if ttc >= 1000 else 0.0
                    ret_tva[i, t] += r_tva
                    rows.append((i, t, row["mf"], b["id_acheteur_public"], b["_mission_code"], b["_mission_libelle"],
                                 b["type"], _comptable(b), fam, day, ht, tva, ttc, r_tva, r_is))

    df = pd.DataFrame(rows, columns=["_i", "_t", "mf_beneficiaire", "id_acheteur_public", "mission_code", "mission_libelle",
                                     "_type", "comptable_assignataire", "_family", "date_paiement", "montant_ht", "montant_tva",
                                     "montant_ttc", "retenue_tva_25", "retenue_is"])
    a["ret_tva_subie"] = ret_tva
    a["adeb_ht"] = np.zeros((N, T))
    if df.empty:
        w.tables["adeb_paiements"] = df
        return
    np.add.at(a["adeb_ht"], (df["_i"].to_numpy(), df["_t"].to_numpy()), df["montant_ht"].to_numpy())
    df["net_a_payer"] = (df["montant_ttc"] - df["retenue_tva_25"] - df["retenue_is"]).round(3)
    df["exercice"] = df["date_paiement"].dt.year
    lag_ord = pd.to_timedelta(rng.integers(5, 46, len(df)), unit="D")
    df["date_ordonnancement"] = df["date_paiement"] - lag_ord

    # One engagement per company x buyer x year.
    df["_eng_key"] = df["mf_beneficiaire"] + "|" + df["id_acheteur_public"] + "|" + df["exercice"].astype(str)
    eng = df.groupby("_eng_key").agg(first_ord=("date_ordonnancement", "min"), total=("montant_ttc", "sum")).reset_index()
    eng["date_engagement"] = eng["first_ord"] - pd.to_timedelta(rng.integers(30, 181, len(eng)), unit="D")
    eng = eng.sort_values("date_engagement").reset_index(drop=True)
    eng["num_engagement"] = "ENG-" + eng["date_engagement"].dt.year.astype(str) + "-" + (eng.index + 1).map(lambda k: f"{k:06d}")
    eng["nature_achat"] = np.select([eng["total"] >= 200_000, eng["total"] >= 30_000], ["MARCHE_TUNEPS", "CONSULTATION"], "BON_COMMANDE")
    df = df.merge(eng[["_eng_key", "date_engagement", "num_engagement", "nature_achat"]], on="_eng_key")

    df["programme_code"] = df["mission_code"] + "." + df["id_acheteur_public"].str[-2:].map(lambda s: f"{int(s) % 4 + 1:02d}")
    invest = df["_family"].isin(["BTP"]) | ((df["_family"] == "SERVICES") & (rng.random(len(df)) < 0.4))
    df["imputation_nature"] = np.where(invest, "INVESTISSEMENT", "FONCTIONNEMENT")

    # Publish payments of the window; engagement and ordering dates never precede the window.
    df = df[df["date_paiement"] >= cfg.WINDOW_START_DATE].copy()
    df["date_ordonnancement"] = df["date_ordonnancement"].clip(lower=cfg.WINDOW_START_DATE)
    df["date_engagement"] = df[["date_engagement"]].assign(o=df["date_ordonnancement"]).apply(
        lambda r: min(max(r["date_engagement"], cfg.WINDOW_START_DATE), r["o"]), axis=1)
    df = df.sort_values(["date_paiement", "_i"]).reset_index(drop=True)
    df["num_ordonnance"] = "ORD-" + df["exercice"].astype(str) + "-" + (df.groupby("exercice").cumcount() + 1).map(lambda k: f"{k:07d}")
    w.tables["adeb_paiements"] = df[[
        "num_ordonnance", "exercice", "mission_code", "mission_libelle", "programme_code", "imputation_nature",
        "id_acheteur_public", "mf_beneficiaire", "nature_achat", "num_engagement", "date_engagement",
        "date_ordonnancement", "date_paiement", "montant_ht", "montant_tva", "montant_ttc", "retenue_tva_25",
        "retenue_is", "net_a_payer", "comptable_assignataire"]]

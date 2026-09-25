"""Taxpayer register (contribuables.csv) and the hidden role of every company.

Roles: NORMAL, A, B (fake-invoice client), COQUILLE (shell), C, D, E, DORMANT, F,
CROISSANCE_LEGITIME, CITOYEN_MODELE, MICRO (recent, no staff, honest).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as cfg
from .referentiels import GOUVERNORATS, NAT_BY_CODE, NAT_CLASSES
from .vocab import CompanyNamer

KEY_LETTERS = list("ABCDEFGHJKLMNPQRSTVWXYZ")  # 23 letters, without I, O, U


def mf(number: int, key: str, code_tva: str = "A", categorie: str = "M", etab: str = "000") -> str:
    """Compact 13-character matricule fiscal: NNNNNNN + key + TVA code + category + establishment."""
    return f"{number:07d}{key}{code_tva}{categorie}{etab}"


def mf_display(compact: str) -> str:
    return f"{compact[:7]}/{compact[7]}/{compact[8]}/{compact[9]}/{compact[10:]}"


def _month_t(date: pd.Timestamp) -> int:
    """Month index relative to SIM_START (can be negative)."""
    return (date.year - 2023) * 12 + (date.month - 1)


def _rand_date(rng: np.random.Generator, start: str, end: str) -> pd.Timestamp:
    a, b = pd.Timestamp(start).value // 86_400_000_000_000, pd.Timestamp(end).value // 86_400_000_000_000
    return pd.Timestamp(int(rng.integers(a, b + 1)), unit="D")


def _start_t(rng: np.random.Generator, lo: str, hi: str) -> int:
    return int(rng.integers(cfg.month_index(lo), cfg.month_index(hi) + 1))


class PopulationBuilder:
    def __init__(self, n: int, rng: np.random.Generator):
        self.n = n
        self.rng = rng
        self.rows: list[dict] = []
        codes = [n.code for n in NAT_CLASSES]
        w = np.array([n.weight for n in NAT_CLASSES])
        self.nat_codes, self.nat_w = codes, w / w.sum()
        g = np.array([x[2] for x in GOUVERNORATS])
        self.gouv_codes, self.gouv_w = [x[0] for x in GOUVERNORATS], g / g.sum()

    # -- sampling helpers ---------------------------------------------------
    def sector(self, allowed: list[str] | None = None) -> str:
        if not allowed:
            return self.nat_codes[self.rng.choice(len(self.nat_codes), p=self.nat_w)]
        w = np.array([NAT_BY_CODE[c].weight for c in allowed])
        return allowed[self.rng.choice(len(allowed), p=w / w.sum())]

    def gouv(self) -> int:
        return int(self.gouv_codes[self.rng.choice(len(self.gouv_codes), p=self.gouv_w)])

    def size(self, allowed: list[str] | None = None) -> str:
        classes, w = cfg.SIZE_CLASSES, np.array(cfg.SIZE_WEIGHTS)
        if allowed:
            mask = np.array([c in allowed for c in classes])
            w = np.where(mask, w, 0)
        return classes[self.rng.choice(len(classes), p=w / w.sum())]

    def effectif(self, size: str) -> int:
        r = self.rng
        if size == "0-2":
            return int(r.choice([0, 1, 2], p=[0.25, 0.35, 0.40]))
        if size == "3-9":
            return int(r.integers(3, 10))
        if size == "10-49":
            return int(np.exp(r.uniform(np.log(10), np.log(50))))
        if size == "50-99":
            return int(r.integers(50, 100))
        return int(np.exp(r.uniform(np.log(100), np.log(600))))

    def ca(self, size: str, code_nat: str) -> float:
        med = cfg.SIZE_CA_MEDIAN[size] * NAT_BY_CODE[code_nat].ca_mult
        return float(med * self.rng.lognormal(0, 0.45))

    def creation(self, lo: str | None = None, hi: str | None = None) -> pd.Timestamp:
        if lo or hi:
            return _rand_date(self.rng, lo or "1990-01-01", hi or "2023-06-30")
        if self.rng.random() < 0.04:  # companies created during the observation window
            return _rand_date(self.rng, "2023-09-01", "2025-12-31")
        age_days = int((0.5 + min(self.rng.exponential(9.0), 38.0)) * 365.25)
        return pd.Timestamp("2023-08-31") - pd.Timedelta(days=age_days)

    # -- row construction ---------------------------------------------------
    def add(self, role: str, *, code_nat: str | None = None, sectors: list[str] | None = None,
            sizes: list[str] | None = None, created: pd.Timestamp | None = None, **extra) -> dict:
        code_nat = code_nat or self.sector(sectors)
        size = extra.pop("size", None) or self.size(sizes)
        eff = extra.pop("effectif", None)
        eff = self.effectif(size) if eff is None else eff
        row = {
            "role": role, "code_nat": code_nat, "size_class": size, "effectif": eff,
            "ca_annuel": extra.pop("ca_annuel", None) or self.ca(size, code_nat),
            "gouvernorat_code": extra.pop("gouvernorat_code", None) or self.gouv(),
            "date_debut_activite": created if created is not None else self.creation(),
            "t_start": -1, "intensite": 0.0, "groupe": "", "is_hero": False, "mf": None,
            "raison_sociale": None, "forme_juridique": None,
        }
        row.update(extra)
        self.rows.append(row)
        return row


def _size_of(eff: int) -> str:
    if eff <= 2:
        return "0-2"
    if eff <= 9:
        return "3-9"
    if eff <= 49:
        return "10-49"
    if eff <= 99:
        return "50-99"
    return "100+"


def build_population(n: int, rng: np.random.Generator) -> pd.DataFrame:
    pb = PopulationBuilder(n, rng)
    counts = {k: cfg.scaled_count(k, n) for k in cfg.SCENARIO_COUNTS}

    # ---- heroes ------------------------------------------------------------
    for h in cfg.HEROES:
        role = {"CROISSANCE_LEGITIME": "CROISSANCE_LEGITIME", "CITOYEN_MODELE": "CITOYEN_MODELE"}.get(h.scenario, h.scenario)
        pb.add(role, code_nat=h.code_nat, size=_size_of(h.effectif), effectif=h.effectif,
               ca_annuel=h.ca_annuel or None, gouvernorat_code=h.gouvernorat,
               created=pd.Timestamp(h.date_debut), t_start=cfg.month_index(h.start) if h.start else -1,
               intensite=1.0, is_hero=True, mf=h.mf, raison_sociale=h.raison_sociale, forme_juridique=h.forme,
               centre_gestion=h.centre)
    rows = pb.rows
    alpha, beta, gamma, delta, epsilon, zeta, eta, omega = rows[:8]
    delta["ca_annuel"] = 0.0
    omega["ca_annuel"] = 0.0

    # ---- scenario A --------------------------------------------------------
    import_sectors_a = ["46.69", "46.43", "46.51", "46.90", "46.74", "46.49", "45.31", "47.41", "46.73"]
    n_a = counts["A"]
    t_alpha = cfg.month_index("2026-06")
    alpha.update(groupe="GA01", a_import=True, a_clients=False, group_supplier=cfg.ALPHA_SUPPLIER)
    group_members = [alpha]
    kappa = pb.add("A", code_nat="46.69", sizes=["10-49"], created=pb.creation("2008-01-01", "2019-12-31"),
                   t_start=t_alpha, intensite=float(rng.uniform(0.7, 1.0)), groupe="GA01", a_import=True,
                   a_clients=False, group_supplier=cfg.ALPHA_SUPPLIER, mf=cfg.KAPPA[0], raison_sociale=cfg.KAPPA[1],
                   forme_juridique="SARL")
    group_members.append(kappa)
    for _ in range(cfg.ALPHA_GROUP_SIZE - 2):
        group_members.append(pb.add("A", sectors=["46.69", "46.74", "46.90", "46.51"], sizes=["3-9", "10-49", "50-99"],
                                    created=pb.creation("2005-01-01", "2020-12-31"), t_start=t_alpha,
                                    intensite=float(rng.uniform(0.5, 1.0)), groupe="GA01", a_import=True,
                                    a_clients=False, group_supplier=cfg.ALPHA_SUPPLIER))
    remaining = n_a - len(group_members)
    # About a third of A cases are organised in groups of 4-6 importers.
    n_grouped = max(0, int(round(n_a / 3)) - len(group_members))
    g = 2
    while n_grouped >= 4 and remaining >= 4:
        size = int(min(rng.integers(4, 7), n_grouped, remaining))
        t0 = _start_t(rng, *cfg.SCENARIO_START_RANGE)
        for _ in range(size):
            pb.add("A", sectors=import_sectors_a, sizes=["3-9", "10-49", "50-99"], created=pb.creation("2003-01-01", "2020-12-31"),
                   t_start=t0, intensite=float(rng.uniform(0.4, 1.0)), groupe=f"GA{g:02d}", a_import=True, a_clients=False,
                   group_supplier="")
        n_grouped -= size
        remaining -= size
        g += 1
    for _ in range(remaining):
        t0 = _start_t(rng, *cfg.SCENARIO_START_RANGE)
        importer = rng.random() < 0.7
        clients = t0 <= cfg.month_index("2025-09") and (not importer or rng.random() < 0.5)
        if not importer and not clients:
            importer = True
        sectors = import_sectors_a if importer else ["46.69", "46.90", "46.76", "25.62", "22.22", "62.02", "49.41", "43.21"]
        pb.add("A", sectors=sectors, sizes=["3-9", "10-49", "50-99"], created=pb.creation("2003-01-01", "2020-12-31"),
               t_start=t0, intensite=float(rng.uniform(0.3, 1.0)), a_import=importer, a_clients=clients, group_supplier="")

    # ---- scenario B: fake-invoice rings ------------------------------------
    omega.update(groupe="RB01", intensite=1.0)
    for k in range(counts["B_NETWORKS"]):
        net = f"RB{k + 1:02d}"
        if k == 0:
            t0 = cfg.month_index("2025-03")
            shells = [omega]
            n_clients = cfg.OMEGA_CLIENTS
        else:
            t0 = _start_t(rng, "2025-03", "2025-10")
            shells = []
            for _ in range(int(rng.integers(1, 3))):
                created = _rand_date(rng, "2024-01-01", cfg.SIM_MONTHS[t0 - 2] + "-28")
                shells.append(pb.add("COQUILLE", sectors=["46.90", "46.76", "41.20", "70.22"], size="0-2", effectif=0,
                                     ca_annuel=0.0, created=created, t_start=t0, intensite=1.0, groupe=net))
            n_clients = int(rng.integers(4, 7))
        for sh in shells:
            sh["t_start"] = t0
        q = float(rng.uniform(0.5, 1.0)) if k else 1.0
        for _ in range(n_clients):
            pb.add("B", sectors=["46.69", "46.73", "46.90", "41.20", "42.11", "25.11", "22.22", "43.21", "49.41", "46.49"],
                   sizes=["3-9", "10-49", "50-99"], created=pb.creation("2003-01-01", "2021-12-31"),
                   t_start=t0, intensite=float(np.clip(q + rng.normal(0, 0.1), 0.3, 1.0)), groupe=net)

    # ---- C, D, E, dormant, F, growth, model citizens, micro --------------------
    for _ in range(counts["C"] - 1):
        pb.add("C", sectors=["46.43", "46.49", "46.51", "46.69", "45.31", "47.41", "46.90", "46.74"], sizes=["3-9", "10-49", "50-99"],
               created=pb.creation("2003-01-01", "2021-12-31"), t_start=_start_t(rng, *cfg.SCENARIO_START_RANGE),
               intensite=float(rng.uniform(0.3, 1.0)))
    for _ in range(counts["D"] - 1):
        # Undeclared public revenue is 0.3-2 MD a year, so D targets small and mid-size firms.
        row = pb.add("D", sectors=["42.11", "41.20", "43.21", "43.22", "46.51", "71.12", "81.21", "62.02"], sizes=["3-9", "10-49"],
                     created=pb.creation("2003-01-01", "2021-12-31"), t_start=_start_t(rng, "2025-03", "2026-02"),
                     intensite=float(rng.uniform(0.3, 1.0)))
        row["ca_annuel"] = min(row["ca_annuel"], 1_600_000.0)
    for _ in range(counts["E"] - 1):
        pb.add("E", sectors=["46.90", "46.49", "45.31", "46.43", "46.69"], sizes=["0-2", "3-9"],
               created=pb.creation("2010-01-01", "2020-12-31"), ca_annuel=1.0,
               t_start=_start_t(rng, "2025-03", "2026-05"), intensite=float(rng.uniform(0.3, 1.0)))
    for _ in range(counts["DORMANT"]):
        pb.add("DORMANT", sizes=["0-2"], created=pb.creation("2005-01-01", "2020-12-31"), ca_annuel=1.0)
    for _ in range(counts["F"] - 1):
        pb.add("F", sectors=["14.13", "14.14", "13.20", "22.22", "22.29", "25.11", "10.39", "46.43", "46.69", "46.90", "46.49"],
               sizes=["3-9", "10-49", "50-99"], created=pb.creation("2003-01-01", "2021-12-31"),
               t_start=_start_t(rng, "2025-03", "2026-01"), intensite=float(rng.uniform(0.3, 1.0)))
    for _ in range(counts["CROISSANCE_LEGITIME"] - 1):
        pb.add("CROISSANCE_LEGITIME", sectors=["25.11", "22.22", "27.32", "46.69", "46.43", "46.73", "41.20", "42.11", "10.39", "62.01"],
               sizes=["10-49", "50-99", "100+"], created=pb.creation("2000-01-01", "2021-12-31"),
               t_start=_start_t(rng, *cfg.SCENARIO_START_RANGE), intensite=float(rng.uniform(0.3, 1.0)))
    for _ in range(counts["CITOYEN_MODELE"] - 1):
        pb.add("CITOYEN_MODELE", sizes=["3-9", "10-49", "50-99", "100+"], created=pb.creation("1990-01-01", "2018-12-31"))
    for _ in range(counts["MICRO_SANS_SALARIE"]):
        code = pb.sector(["62.01", "70.22", "73.11", "46.90", "71.12", "62.02"])
        pb.add("MICRO", code_nat=code, size="0-2", effectif=0, created=_rand_date(rng, "2023-10-01", "2025-12-31"),
               ca_annuel=float(rng.uniform(40_000, 250_000)))

    # ---- normal population fills the rest --------------------------------------
    while len(pb.rows) < n:
        pb.add("NORMAL")
    if len(pb.rows) > n:
        raise ValueError(f"n={n} is too small for the mandatory hero cases and scenarios ({len(pb.rows)} needed)")

    comp = pd.DataFrame(pb.rows)
    comp = _finalise(comp, rng)
    return comp


def _finalise(comp: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    n = len(comp)
    nat = comp["code_nat"].map(NAT_BY_CODE)
    comp["family"] = nat.map(lambda x: x.family)
    comp["section_nat"] = nat.map(lambda x: x.section)
    comp["date_debut_activite"] = pd.to_datetime(comp["date_debut_activite"])
    comp["created_t"] = comp["date_debut_activite"].map(_month_t).astype(int)

    # Legal form
    formes = np.array(list(cfg.FORME_WEIGHTS))
    fw = np.array(list(cfg.FORME_WEIGHTS.values()))
    for i in comp.index[comp["forme_juridique"].isna()]:
        size = comp.at[i, "size_class"]
        w = fw.copy()
        if size in ("50-99", "100+"):
            w = np.array([0.55, 0.05, 0.40])
        elif size == "0-2":
            w = np.array([0.55, 0.44, 0.01])
        comp.at[i, "forme_juridique"] = formes[rng.choice(3, p=w / w.sum())]

    # Behaviour parameters
    comp["importer"] = False
    comp["offshore"] = False
    for i, row in comp.iterrows():
        nt = NAT_BY_CODE[row["code_nat"]]
        role = row["role"]
        if role in ("A",):
            imp = bool(row.get("a_import", True))
        elif role in ("C", "E"):
            imp = True
        elif role in ("COQUILLE", "DORMANT", "MICRO"):
            imp = False
        elif role == "CROISSANCE_LEGITIME":
            imp = bool(rng.random() < max(0.7, nt.part_imp))
        elif role in ("B", "F", "D"):
            imp = bool(rng.random() < nt.part_imp)
        else:
            imp = bool(rng.random() < nt.part_imp * (0.85 if row["size_class"] == "0-2" else 1.1))
        comp.at[i, "importer"] = imp
        if role in ("NORMAL", "CITOYEN_MODELE") and rng.random() < nt.offshore:
            comp.at[i, "offshore"] = True
    hero = comp["is_hero"]
    comp.loc[hero & comp["role"].isin(["A", "C", "E", "CITOYEN_MODELE", "CROISSANCE_LEGITIME"]), "importer"] = True
    comp.loc[hero & comp["role"].isin(["D", "COQUILLE"]), "importer"] = False
    comp.loc[comp["mf"] == "1000005FAM000", "importer"] = True
    comp.loc[hero, "offshore"] = False
    for c in ("a_import", "a_clients"):
        comp[c] = comp[c].fillna(False).astype(bool) if c in comp else False
    comp["group_supplier"] = comp.get("group_supplier", pd.Series([""] * n)).fillna("")

    # Matricules: heroes are fixed; others numbered by creation date with gaps.
    fixed = set(comp["mf"].dropna().str[:7].astype(int))
    order = comp.index[comp["mf"].isna()]
    order = comp.loc[order].sort_values("date_debut_activite").index
    num = 1_000_008
    for i in order:
        num += int(rng.integers(1, 4))
        while num in fixed:
            num += 1
        tva = rng.choice(["A", "B", "P"], p=[0.93, 0.04, 0.03])
        comp.at[i, "mf"] = mf(num, KEY_LETTERS[rng.integers(len(KEY_LETTERS))], tva)
        fixed.add(num)
    comp["matricule_fiscal"] = comp["mf"].map(mf_display)
    comp["code_tva"] = comp["mf"].str[8]
    comp["code_categorie"] = "M"

    # Names
    namer = CompanyNamer(rng, set(comp["raison_sociale"].dropna()))
    for i in comp.index[comp["raison_sociale"].isna()]:
        comp.at[i, "raison_sociale"] = namer.name(NAT_BY_CODE[comp.at[i, "code_nat"]].words, comp.at[i, "forme_juridique"])

    # Fiscal attributes
    comp["taux_is"] = [10.0 if off else NAT_BY_CODE[c].taux_is for c, off in zip(comp["code_nat"], comp["offshore"])]
    comp["statut_export"] = np.where(comp["offshore"], "TOTALEMENT_EXPORTATRICE", "ONSHORE")
    ca = comp["ca_annuel"].astype(float)
    centre = np.where(ca >= 25e6, "DGE", np.where(ca >= 3e6, "DME", "CRCI"))
    if "centre_gestion" in comp:
        comp["centre_gestion"] = comp["centre_gestion"].fillna(pd.Series(centre, index=comp.index))
    else:
        comp["centre_gestion"] = centre
    comp["regime_fiscal"] = np.where((ca < 150_000) & (comp["size_class"] == "0-2") & (rng.random(n) < 0.5) & ~hero
                                     & (comp["role"] == "NORMAL"), "REEL_SIMPLIFIE", "REEL")
    eff_decl = np.maximum(0, np.round(comp["effectif"] * rng.uniform(0.6, 1.15, n))).astype(int)
    comp["effectif_declare"] = np.where(hero | (comp["effectif"] == 0), comp["effectif"], eff_decl)
    cap_min = np.where(comp["forme_juridique"] == "SA", 5000, 1000)
    cap = np.maximum(cap_min, np.round(ca * rng.uniform(0.02, 0.15, n) / 1000) * 1000)
    cap = np.where(comp["forme_juridique"] == "SA", cap * 2, cap)
    cap = np.where(comp["role"] == "COQUILLE", rng.choice([1000, 2000, 5000], n), cap)
    cap = np.where(comp["mf"] == cfg.ALPHA_MF, 50_000, cap)
    comp["capital_social"] = cap.astype(float)
    comp["date_cloture_exercice"] = "12-31"
    comp["code_en_douane"] = np.where(comp["importer"], "CD" + comp["mf"].str[:7], "")

    # Authorised economic operators (OEA): model-citizen importers mostly.
    oea_p = np.where((comp["role"] == "CITOYEN_MODELE") & comp["importer"] & comp["size_class"].isin(["10-49", "50-99", "100+"]), 0.15,
                     np.where((comp["role"] == "NORMAL") & comp["importer"] & comp["size_class"].isin(["50-99", "100+"]), 0.04, 0.0))
    oea = (rng.random(n) < oea_p) | (comp["mf"] == "1000007HAM000")
    oea &= ~(hero & (comp["mf"] != "1000007HAM000"))
    oea &= comp["date_debut_activite"] <= pd.Timestamp("2022-06-30")  # OEA requires 3 years of clean history
    comp["statut_oea"] = oea
    oea_dates = [(_rand_date(rng, max("2019-01-01", str(d.date() + pd.Timedelta(days=3 * 366))), "2025-06-30")
                  if o else pd.NaT) for o, d in zip(oea, comp["date_debut_activite"])]
    comp["date_oea"] = pd.to_datetime(oea_dates)
    comp.loc[comp["mf"] == "1000007HAM000", "date_oea"] = pd.Timestamp("2021-05-17")
    comp["date_cessation"] = pd.NaT

    # Filing behaviour: most companies are punctual, a minority is often late.
    sloppy = rng.random(n) < 0.2
    comp["p_late"] = np.where(sloppy, 0.22, 0.025)
    comp["p_miss"] = np.where(sloppy, 0.07, 0.008)
    good = comp["role"].isin(["CITOYEN_MODELE"]) | hero
    comp.loc[good, ["p_late", "p_miss"]] = 0.0
    comp = comp.reset_index(drop=True)
    comp["idx"] = comp.index
    return comp


CONTRIBUABLES_COLUMNS = [
    "mf", "matricule_fiscal", "code_tva", "code_categorie", "raison_sociale", "forme_juridique", "code_nat", "section_nat",
    "date_debut_activite", "gouvernorat_code", "regime_fiscal", "taux_is", "statut_export", "centre_gestion", "effectif_declare",
    "capital_social", "date_cloture_exercice", "code_en_douane", "statut_oea", "date_oea", "date_cessation",
]

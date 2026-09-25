"""Customs declarations (DDM / SINDA): headers, articles, tax liquidation, foreign suppliers.

Monthly true import values come from the activity model. Each importer has a portfolio of NDP
codes and a set of regular foreign suppliers that churns slowly (about 12 % a year). Scenario
imports (A, E, legitimate growth) are served by suppliers that are new for the importer.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as cfg
from .activite import World
from .referentiels import DD_FREE_ORIGINS, EU_ORIGINS, NAT_BY_CODE, PORT_BY_GOUV
from .vocab import supplier_name

COUNTRY_WEIGHTS = {
    "IT": 12, "CN": 11, "FR": 10, "DE": 7, "TR": 6, "DZ": 4, "ES": 4, "US": 3, "IN": 3, "BE": 3, "NL": 2.5,
    "PT": 2, "GB": 2, "KR": 2, "JP": 1.5, "EG": 2, "MA": 1.5, "CH": 2, "PL": 2, "CZ": 1, "AT": 1, "RO": 1,
    "VN": 1.5, "TH": 1, "MY": 1, "PK": 1, "BR": 1, "GR": 1, "SE": 1, "LY": 0.5,
}
CHAPTER_WEIGHTS = {"85": 0.2, "84": 0.2, "87": 0.12, "39": 0.14, "30": 0.08, "52": 0.1, "72": 0.08, "73": 0.08}
BASE_RATES = {"EUR": 3.38, "USD": 3.10, "CNY": 0.43, "TRY": 0.095, "DZD": 0.023, "GBP": 3.95, "CHF": 3.55, "JPY": 0.021}
INCOTERMS = (["FOB", "CFR", "CIF", "EXW", "DAP"], [0.35, 0.15, 0.25, 0.15, 0.10])


def _currency(rng, country: str) -> str:
    if country in EU_ORIGINS:
        return "EUR"
    table = {"CN": (["USD", "CNY"], [0.7, 0.3]), "TR": (["USD", "EUR", "TRY"], [0.5, 0.3, 0.2]),
             "DZ": (["EUR", "DZD"], [0.5, 0.5]), "GB": (["GBP"], [1.0]), "CH": (["CHF", "EUR"], [0.6, 0.4]),
             "JP": (["JPY", "USD"], [0.5, 0.5])}
    cur, p = table.get(country, (["USD", "EUR"], [0.8, 0.2]))
    return str(rng.choice(cur, p=p))


class SupplierPool:
    def __init__(self, rng: np.random.Generator, n_pool: int):
        self.rng = rng
        self.rows: dict[str, dict] = {}
        self.taken_names: set[str] = set()
        self.next_id = 1
        countries = list(COUNTRY_WEIGHTS)
        cw = np.array(list(COUNTRY_WEIGHTS.values()))
        self.countries, self.cw = countries, cw / cw.sum()
        chaps = list(CHAPTER_WEIGHTS)
        chw = np.array(list(CHAPTER_WEIGHTS.values()))
        self.chaps, self.chw = chaps, chw / chw.sum()
        self.add(cfg.ALPHA_SUPPLIER, "CN", ["84", "85"], name=cfg.ALPHA_SUPPLIER_NAME, regular=False)
        for _ in range(n_pool):
            self.add()
        self.by_chapter: dict[str, list[str]] = {}
        self._index()

    def _new_id(self) -> str:
        while True:
            sid = f"FE{self.next_id:05d}"
            self.next_id += 1
            if sid not in self.rows:
                return sid

    def add(self, sid: str | None = None, country: str | None = None, chapters: list[str] | None = None,
            name: str | None = None, regular: bool = True) -> str:
        rng = self.rng
        sid = sid or self._new_id()
        country = country or str(self.countries[rng.choice(len(self.countries), p=self.cw)])
        if chapters is None:
            k = int(rng.choice([1, 2, 3], p=[0.5, 0.35, 0.15]))
            chapters = sorted(rng.choice(self.chaps, size=k, replace=False, p=self.chw).tolist())
        name = name or supplier_name(rng, country, chapters[0], self.taken_names)
        self.taken_names.add(name)
        self.rows[sid] = {"id_fournisseur": sid, "nom": name, "pays": country, "chapitres": chapters, "regular": regular}
        return sid

    def _index(self) -> None:
        self.by_chapter = {c: [] for c in CHAPTER_WEIGHTS}
        for sid, r in self.rows.items():
            if r["regular"]:
                for c in r["chapitres"]:
                    self.by_chapter[c].append(sid)

    def pick(self, chapters: list[str], k: int, exclude: set[str]) -> list[str]:
        cands = sorted({s for c in chapters for s in self.by_chapter.get(c, [])} - exclude)
        if len(cands) < k:
            cands = sorted({s for s, r in self.rows.items() if r["regular"]} - exclude)
        k = min(k, len(cands))
        return self.rng.choice(cands, size=k, replace=False).tolist() if k else []

    def fresh(self, chapters: list[str], country: str | None = None) -> str:
        """A supplier never seen before (first appearance at the time it is used)."""
        if country is None:
            country = str(self.rng.choice(["CN", "TR", "CN", "IN", "VN", "AE", "EG"]))
        return self.add(country=country, chapters=chapters, regular=False)


def _exchange_rates(rng: np.random.Generator) -> dict[str, np.ndarray]:
    out = {}
    for cur, r0 in BASE_RATES.items():
        steps = rng.normal(0.0005, 0.01, cfg.T)
        out[cur] = r0 * np.exp(np.cumsum(steps))
    return out


def simulate_customs(w: World) -> None:
    comp, rng, a = w.comp, w.rng, w.arr
    ref = w.ref["ref_ndp"].reset_index(drop=True)
    ndp_chap = ref["chapitre_sh"].to_numpy()
    ndp_price = ref["prix_reference_tnd"].to_numpy()
    ndp_unit = ref["unite"].to_numpy()
    ndp_kg = ref["_kg_par_unite"].to_numpy()
    ndp_dd = ref["taux_dd"].to_numpy()
    ndp_tva = ref["taux_tva"].to_numpy()
    ndp_fodec = ref["taux_fodec"].to_numpy()

    N, T = w.n, cfg.T
    # About 800 foreign suppliers in total once scenario suppliers (new, never seen before) are added.
    pool = SupplierPool(rng, max(80, int(round(620 * N / cfg.N_DEFAULT))))
    rates = _exchange_rates(rng)
    imports = a["imports"]
    new_stream = np.zeros((N, T))

    # Portion of imports served by suppliers that are new for the importer.
    for i, row in comp.iterrows():
        t0 = int(row["t_start"])
        if row["role"] == "A" and row["a_import"]:
            base = a["imports_base"][i]
            new_stream[i] = np.clip(imports[i] - base, 0, None)
        elif row["role"] == "E":
            new_stream[i] = imports[i]
        elif row["role"] == "CROISSANCE_LEGITIME" and t0 >= 0:
            base = a["imports_base"][i]
            new_stream[i] = np.clip(imports[i] - base, 0, None) * 0.5
    base_stream = np.clip(imports - new_stream, 0, None)

    decl_rows: list[tuple] = []
    art_rows: list[tuple] = []
    evaded = np.zeros(N)
    t_arr = np.arange(T)

    # Each A group other than Alpha's gets its own brand-new shared supplier.
    for grp in sorted(comp.loc[(comp["role"] == "A") & (comp["groupe"] != "") & (comp["groupe"] != "GA01"), "groupe"].unique()):
        comp.loc[comp["groupe"] == grp, "group_supplier"] = pool.fresh(["84", "85"], "CN")

    importers = comp.index[comp["importer"] & (imports.sum(axis=1) > 0)]
    for i in importers:
        row = comp.loc[i]
        nat = NAT_BY_CODE[row["code_nat"]]
        mf, role, t0 = row["mf"], row["role"], int(row["t_start"])
        mean_imp = imports[i, imports[i] > 0].mean()
        v = float(np.clip(rng.lognormal(np.log(50_000), 0.8), 6_000, max(8_000, 1.5 * mean_imp)))
        if row["is_hero"]:
            v = float(mean_imp / 3)  # regular shipments keep the hero stories readable

        # Portfolio of NDP codes
        chaps = list(nat.chapitres) or ["84"]
        if role == "E":
            chaps = sorted(set(chaps) | set(rng.choice(["85", "87", "84", "39"], size=2, replace=False)))
        k_ch = min(len(chaps), int(rng.integers(1, 4)))
        port_ch = chaps[:k_ch] if role != "E" else chaps
        cand = np.where(np.isin(ndp_chap, port_ch) & ((ndp_unit != "U") | (ndp_price <= 0.6 * v)))[0]
        if len(cand) == 0:
            cand = np.where(np.isin(ndp_chap, port_ch))[0]
            cand = cand[np.argsort(ndp_price[cand])[:3]]
        if mf == cfg.ALPHA_MF:
            cand = np.where(np.isin(ndp_chap, ["84", "85"]) & (ndp_price <= 25_000))[0]
        port = rng.choice(cand, size=min(len(cand), int(rng.integers(3, 11))), replace=False)
        if mf == cfg.ALPHA_MF:
            alpha_ndp = np.where(ref["code_ndp"].to_numpy() == "84798997000")[0][0]
            port = np.unique(np.append(port, alpha_ndp))
        port_w = rng.dirichlet(np.ones(len(port)) * 1.5)

        # Regular suppliers with churn (~1 % per month per relation)
        k_sup = int(np.clip(1 + rng.poisson(0.8 + mean_imp / 100_000), 1, 12))
        slots = []
        used: set[str] = set()
        for sid in pool.pick(port_ch, k_sup, used):
            used.add(sid)
            start = max(0, int(row["created_t"]))
            weight = float(rng.lognormal(0, 0.6))
            cur = sid
            for t in range(start, T):
                if t > start and rng.random() < 0.01 and role not in ("CITOYEN_MODELE",):
                    slots.append((cur, start, t, weight))
                    nxt = pool.pick(port_ch, 1, used)
                    if not nxt:
                        break
                    cur, start = nxt[0], t
                    used.add(cur)
            slots.append((cur, start, T, weight))
        # New suppliers for scenario streams
        new_slots = []
        if new_stream[i].sum() > 0:
            ts = int(np.argmax(new_stream[i] > 0))
            if row["role"] == "A" and row["groupe"]:
                gs = row["group_supplier"]
                new_slots.append((gs, ts, T, 3.0))
            n_new = 2 if mf == cfg.ALPHA_MF else int(rng.integers(1, 3))
            if role == "E":
                n_new = int(rng.integers(2, 5))
            for _ in range(n_new):
                country = "TR" if mf == "1000004EAM000" and rng.random() < 0.4 else None
                new_slots.append((pool.fresh(port_ch[:2], country), ts, T, float(rng.lognormal(0, 0.4))))

        oea = bool(row["statut_oea"])
        gouv = int(row["gouvernorat_code"])
        c_factor = float(row["c_factor"])

        for t in t_arr[imports[i] > 0]:
            for stream, slist in ((base_stream, slots), (new_stream, new_slots)):
                I = stream[i, t]
                if I <= 0 or not slist:
                    continue
                act = [s for s in slist if s[1] <= t < s[2]]
                if not act:
                    act = [slist[-1]]
                lam = I / v
                forced_first = stream is new_stream and row["role"] == "A" and bool(row["groupe"]) and t == t0
                k = int(rng.poisson(lam)) if lam >= 1 else int(rng.random() < lam)
                if stream is new_stream and t0 <= t <= t0 + 2:
                    k = max(k, 1)
                if k == 0:
                    continue
                vals = (np.full(k, I / k) if lam >= 1 else np.full(k, v)) * rng.lognormal(-0.02, 0.2, k)
                sw = np.array([s[3] for s in act])
                sup_idx = rng.choice(len(act), size=k, p=sw / sw.sum())
                if forced_first:
                    sup_idx[0] = 0  # the shared group supplier comes first
                for d in range(k):
                    sid = act[sup_idx[d]][0]
                    decl_rows.append(_make_declaration(
                        rng, rates, i, mf, row, t, float(vals[d]), sid, pool, oea, gouv, c_factor,
                        port, port_w, ndp_chap, ndp_price, ndp_unit, ndp_kg, ndp_dd, ndp_tva, ndp_fodec,
                        art_rows, evaded))

    decl = pd.DataFrame(decl_rows, columns=[
        "_i", "_t", "date_enregistrement", "type_declaration", "bureau_code", "mf_importateur", "code_en_douane",
        "id_declarant", "pays_provenance", "mode_transport", "incoterm", "devise", "taux_change",
        "valeur_facture_devise", "fret_tnd", "assurance_tnd", "valeur_caf_tnd", "circuit", "resultat_controle",
        "total_droits_taxes_tnd", "_key"])
    arts = pd.DataFrame(art_rows, columns=[
        "_key", "num_article", "code_ndp", "code_sh6", "chapitre_sh", "designation", "id_fournisseur_etranger",
        "pays_origine", "poids_net_kg", "quantite", "unite", "valeur_caf_tnd", "prix_unitaire_tnd",
        "_dd", "_fodec", "_tva", "_rpd", "_dd_rate", "_tva_rate", "_fodec_rate", "_true_value"])

    # Declaration numbers: year / office / sequence, in chronological order.
    decl = decl.sort_values(["date_enregistrement", "_i"]).reset_index(drop=True)
    yr = decl["date_enregistrement"].dt.year.astype(str)
    seq = decl.groupby([yr, decl["bureau_code"]]).cumcount() + 1 + rng.integers(1000, 9000)
    decl["num_declaration"] = yr + "/" + decl["bureau_code"] + "/" + seq.map(lambda s: f"{s:07d}")
    key_to_num = dict(zip(decl["_key"], decl["num_declaration"]))
    arts["num_declaration"] = arts["_key"].map(key_to_num)
    arts["id_article"] = arts["num_declaration"] + "-" + arts["num_article"].map(lambda k: f"{k:03d}")

    # Liquidation (only for release for consumption; suspension regimes pay nothing at entry).
    liq_src = arts.merge(decl[["_key", "type_declaration"]], on="_key")
    liq_src = liq_src[liq_src["type_declaration"] == "IC100"]
    parts = []
    for code, base_col, rate_col, amt_col in (
        ("001", None, "_dd_rate", "_dd"), ("093", None, "_fodec_rate", "_fodec"),
        ("105", "tva_base", "_tva_rate", "_tva"), ("473", "rpd_base", None, "_rpd"),
    ):
        df = liq_src[["id_article"]].copy()
        if code in ("001", "093"):
            df["base_tnd"] = liq_src["valeur_caf_tnd"].to_numpy()
            df["taux"] = liq_src[rate_col].to_numpy()
        elif code == "105":
            df["base_tnd"] = (liq_src["valeur_caf_tnd"] + liq_src["_dd"] + liq_src["_fodec"]).to_numpy()
            df["taux"] = liq_src[rate_col].to_numpy()
        else:
            df["base_tnd"] = (liq_src["_dd"] + liq_src["_fodec"] + liq_src["_tva"]).to_numpy()
            df["taux"] = 3.0
        df["montant_tnd"] = liq_src[amt_col].to_numpy()
        df["code_taxe"] = code
        parts.append(df[df["montant_tnd"] > 0])
    liq = pd.concat(parts, ignore_index=True)
    liq = liq[["id_article", "code_taxe", "base_tnd", "taux", "montant_tnd"]].sort_values(["id_article", "code_taxe"])

    # Monthly VAT 105 per importer (feeds the deductible import VAT of the following month).
    tva_art = liq[liq["code_taxe"] == "105"].merge(arts[["id_article", "_key"]], on="id_article").merge(decl[["_key", "_i", "_t"]], on="_key")
    tva105 = np.zeros((N, T))
    np.add.at(tva105, (tva_art["_i"].to_numpy(), tva_art["_t"].to_numpy()), tva_art["montant_tnd"].to_numpy())
    caf_decl = np.zeros((N, T))
    np.add.at(caf_decl, (decl["_i"].to_numpy(), decl["_t"].to_numpy()), decl["valeur_caf_tnd"].to_numpy())
    a["tva105"] = tva105
    a["caf_declared"] = caf_decl
    comp["customs_evaded"] = evaded

    # Published tables: from WINDOW_START only.
    pub = decl["date_enregistrement"] >= cfg.WINDOW_START_DATE
    decl_pub = decl[pub]
    arts_pub = arts[arts["_key"].isin(decl_pub["_key"])]
    liq_pub = liq[liq["id_article"].isin(arts_pub["id_article"])]

    first_seen = arts_pub.merge(decl_pub[["_key", "date_enregistrement"]], on="_key").groupby("id_fournisseur_etranger")["date_enregistrement"].min()
    fe = pd.DataFrame(list(pool.rows.values()))
    fe = fe[fe["id_fournisseur"].isin(first_seen.index)].copy()
    fe["date_premiere_apparition"] = fe["id_fournisseur"].map(first_seen)
    fe["chapitres_sh_principaux"] = fe["chapitres"].map(lambda c: ";".join(c))
    fe = fe.sort_values("id_fournisseur")[["id_fournisseur", "nom", "pays", "date_premiere_apparition", "chapitres_sh_principaux"]]

    w.tables["douane_declarations"] = decl_pub[[
        "num_declaration", "type_declaration", "bureau_code", "date_enregistrement", "mf_importateur", "code_en_douane",
        "id_declarant", "pays_provenance", "mode_transport", "incoterm", "devise", "taux_change", "valeur_facture_devise",
        "fret_tnd", "assurance_tnd", "valeur_caf_tnd", "circuit", "resultat_controle", "total_droits_taxes_tnd"]].reset_index(drop=True)
    w.tables["douane_articles"] = arts_pub[[
        "id_article", "num_declaration", "num_article", "code_ndp", "code_sh6", "chapitre_sh", "designation",
        "id_fournisseur_etranger", "pays_origine", "poids_net_kg", "quantite", "unite", "valeur_caf_tnd",
        "prix_unitaire_tnd"]].reset_index(drop=True)
    w.tables["douane_liquidation"] = liq_pub.reset_index(drop=True)
    w.tables["fournisseurs_etrangers"] = fe.reset_index(drop=True)
    w.tables["_customs_internal"] = arts.merge(decl[["_key", "_i", "_t", "date_enregistrement", "mf_importateur"]], on="_key")


_DECLARANTS = [f"COM{k:04d}" for k in range(1, 121)]


def _make_declaration(rng, rates, i, mf, row, t, value, sid, pool, oea, gouv, c_factor, port, port_w,
                      ndp_chap, ndp_price, ndp_unit, ndp_kg, ndp_dd, ndp_tva, ndp_fodec, art_rows, evaded):
    sup = pool.rows[sid]
    country = sup["pays"]
    year, month = int(cfg.SIM_MONTHS[t][:4]), int(cfg.SIM_MONTHS[t][5:7])
    days = pd.Timestamp(year=year, month=month, day=1).days_in_month
    date = pd.Timestamp(year=year, month=month, day=int(rng.integers(1, days + 1)))
    if date.dayofweek == 6:
        date += pd.Timedelta(days=1) if date.day < days else -pd.Timedelta(days=1)

    delta = mf == "1000004EAM000"
    if delta:
        provenance, mode, bureau = "LY", "ROUTIER", "601"
    elif country == "DZ":
        provenance, mode, bureau = "DZ", "ROUTIER", "602"
    elif country == "LY":
        provenance, mode, bureau = "LY", "ROUTIER", "601"
    else:
        provenance = country
        air = rng.random() < (0.3 if set(sup["chapitres"]) & {"30", "85"} else 0.08)
        mode = "AERIEN" if air else "MARITIME"
        bureau = "303" if air else PORT_BY_GOUV.get(gouv, "301" if rng.random() < 0.7 else "302")
    if row["offshore"]:
        typ = "SA530" if rng.random() < 0.7 else "SA531"
    elif row["family"] == "GROS" and rng.random() < 0.01:
        typ = "SE737"
    else:
        typ = "IC100"

    # Circuit (selectivity)
    if oea:
        circuit = rng.choice(["V", "O", "R"], p=[0.92, 0.07, 0.01])
    elif row["role"] == "E" and t >= row["t_start"]:
        circuit = rng.choice(["V", "O", "R"], p=[0.5, 0.35, 0.15])
    else:
        circuit = rng.choice(["V", "O", "R"], p=list(cfg.CIRCUIT_WEIGHTS.values()))
    under = row["role"] == "C" and t >= row["t_start"]
    if circuit == "V":
        res = "CONFORME"
    elif circuit == "O":
        res = rng.choice(["CONFORME", "COMPLEMENT_DEMANDE", "LITIGE"], p=[0.75, 0.13, 0.12] if under else [0.85, 0.12, 0.03])
    else:
        res = rng.choice(["CONFORME", "COMPLEMENT_DEMANDE", "LITIGE", "INFRACTION"], p=[0.5, 0.15, 0.2, 0.15] if under else [0.7, 0.15, 0.1, 0.05])

    # Articles
    n_art = int(min(6, 1 + rng.poisson(0.9)))
    sup_ch = set(sup["chapitres"])
    mask = np.array([ndp_chap[p] in sup_ch for p in port])
    cand, cw = (port[mask], port_w[mask]) if mask.any() else (port, port_w)
    picks = rng.choice(cand, size=n_art, p=cw / cw.sum())
    shares = rng.dirichlet(np.full(n_art, 2.0))
    key = f"{i}-{t}-{len(art_rows)}"
    caf_total, droits_total = 0.0, 0.0
    for k, (p, sh) in enumerate(zip(picks, shares), start=1):
        true_val = value * sh
        noise = float(np.clip(rng.lognormal(0, 0.06), 0.87, 1.15))
        true_pu = ndp_price[p] * noise
        if ndp_unit[p] == "U":
            qty = float(max(1, round(true_val / true_pu)))
        else:
            qty = round(max(true_val / true_pu, 1.0), 3)
        factor = float(np.clip(c_factor * rng.uniform(0.92, 1.06), 0.35, 0.69)) if under else 1.0
        pu = round(true_pu * factor, 3)
        caf = round(qty * pu, 3)
        true_caf = qty * true_pu
        weight = round(qty * ndp_kg[p] * (1.0 if ndp_unit[p] == "KG" else rng.uniform(0.9, 1.1)), 3)
        origin = country if rng.random() > 0.08 else str(rng.choice(["CN", "TR", "IN", "VN"]))
        if typ == "IC100":
            dd_rate = 0.0 if origin in DD_FREE_ORIGINS else float(ndp_dd[p])
            fodec_rate = float(ndp_fodec[p])
            tva_rate = float(ndp_tva[p])
        else:
            dd_rate = fodec_rate = tva_rate = 0.0
        dd = round(caf * dd_rate / 100, 3)
        fodec = round(caf * fodec_rate / 100, 3)
        tva = round((caf + dd + fodec) * tva_rate / 100, 3)
        rpd = round((dd + fodec + tva) * 0.03, 3)
        if under:
            eff = (dd_rate + fodec_rate) / 100
            evaded[i] += (true_caf - caf) * (eff + (1 + eff) * tva_rate / 100) * 1.03
        caf_total += caf
        droits_total += dd + fodec + tva + rpd
        art_rows.append((key, k, _NDP_CODE[p], _NDP_SH6[p], ndp_chap[p], _NDP_LIB[p], sid, origin, weight, qty,
                         ndp_unit[p], caf, pu, dd, fodec, tva, rpd, dd_rate, tva_rate, fodec_rate, true_caf))

    caf_total = round(caf_total, 3)
    incoterm = str(rng.choice(INCOTERMS[0], p=INCOTERMS[1]))
    cur = _currency(rng, country)
    fx = round(float(rates[cur][t]), 5)
    fret_r = {"MARITIME": rng.uniform(0.03, 0.08), "AERIEN": rng.uniform(0.08, 0.14), "ROUTIER": rng.uniform(0.03, 0.06)}[mode]
    fret = round(caf_total * fret_r, 3)
    assurance = round(caf_total * 0.005, 3)
    if incoterm in ("CIF", "DAP"):
        fac, fret_out, ass_out = caf_total, 0.0, 0.0
    elif incoterm == "CFR":
        fac, fret_out, ass_out = caf_total - assurance, 0.0, assurance
    else:
        fac, fret_out, ass_out = caf_total - fret - assurance, fret, assurance
    declarant = _DECLARANTS[(int(mf[:7]) * 7 + (1 if rng.random() < 0.2 else 0)) % len(_DECLARANTS)]
    return (i, t, date, typ, bureau, mf, row["code_en_douane"], declarant, provenance, mode, incoterm, cur, fx,
            round(fac / fx, 3), fret_out, ass_out, caf_total, circuit, res, round(droits_total, 3), key)


_NDP_CODE: np.ndarray = np.array([])
_NDP_SH6: np.ndarray = np.array([])
_NDP_LIB: np.ndarray = np.array([])


def bind_nomenclature(ref_ndp: pd.DataFrame) -> None:
    global _NDP_CODE, _NDP_SH6, _NDP_LIB
    r = ref_ndp.reset_index(drop=True)
    _NDP_CODE, _NDP_SH6, _NDP_LIB = r["code_ndp"].to_numpy(), r["code_sh6"].to_numpy(), r["designation"].to_numpy()

"""Independent recomputation of data/graphe/metriques_noeuds.csv.

Deliberately shares no code with generation/graphe.py: plain dictionaries and a hand-written
breadth-first search over the raw CSV files. If both implementations agree, the metrics follow the
written definitions (README section 6) rather than an artefact of one implementation.
"""

from __future__ import annotations

from collections import deque
from pathlib import Path

import pandas as pd
import pytest

from generation import config as cfg
from generation.run import generate

HUB = 20


class BruteForce:
    def __init__(self, root: Path):
        r = root / "raw"
        dd = pd.read_csv(r / "douane_declarations.csv")
        da = pd.read_csv(r / "douane_articles.csv")
        self.a5 = pd.read_csv(r / "employeur_annexe5.csv")
        self.a2 = pd.read_csv(r / "employeur_annexe2.csv", dtype={"id_beneficiaire": str})
        self.a1 = pd.read_csv(r / "employeur_annexe1_synthese.csv")
        self.dis = pd.read_csv(r / "declarations_is.csv")
        self.ctl = pd.read_csv(r / "historique_controles.csv")
        c = pd.read_csv(r / "contribuables.csv")
        self.months = [str(p) for p in pd.period_range("2023-01", "2026-08", freq="M")]
        self.ix = {m: i for i, m in enumerate(self.months)}
        imp = da.merge(dd[["num_declaration", "mf_importateur", "date_enregistrement"]], on="num_declaration")
        self.rel: dict[tuple[str, str], set[int]] = {}
        for mf, s, d in zip(imp["mf_importateur"], imp["id_fournisseur_etranger"], imp["date_enregistrement"]):
            self.rel.setdefault((mf, s), set()).add(self.ix[d[:7]])
        self.first = {k: min(v) for k, v in self.rel.items()}
        self.created = {m: (int(d[:4]) - 2023) * 12 + int(d[5:7]) - 1 for m, d in zip(c["mf"], c["date_debut_activite"])}
        self.burn = self.ix["2024-09"]

    def exercice(self, m: int) -> int:
        y, mo = int(self.months[m][:4]), int(self.months[m][5:])
        return y - 1 if mo >= 3 else y - 2

    def shell(self, x: str, m: int, E: int, a5e: pd.DataFrame) -> bool:
        sal = self.a1[(self.a1["mf"] == x) & (self.a1["exercice"] == E)]["nb_salaries"].sum()
        rec = a5e[a5e["mf_fournisseur"] == x]["montant_ttc"].sum()
        ca = self.dis[(self.dis["mf"] == x) & (self.dis["exercice"] == E)][["ca_local", "ca_export"]].to_numpy().sum()
        return sal == 0 and (m - self.created[x]) < 36 and rec > 0 and rec >= 3 * ca

    def metrics(self, mf: str, mois: str) -> dict:
        m = self.ix[mois]
        E = self.exercice(m)
        a5e = self.a5[self.a5["exercice"] == E]
        loc = a5e[a5e["mf_payeur"] == mf]
        f12 = {s for (x, s), ts in self.rel.items() if x == mf and any(m - 12 < t <= m for t in ts)}
        newf = {s for (x, s), t in self.first.items() if x == mf and m - 12 < t <= m and t >= self.burn}
        newl = set(loc[loc["premiere_annee_relation"] == E]["mf_fournisseur"])

        others: set[str] = set()
        for s in {s for (x, s), t in self.first.items() if x == mf and m - 3 < t <= m and t >= self.burn}:
            new_clients = {x for (x, s2), t in self.first.items() if s2 == s and m - 3 < t <= m and t >= self.burn}
            active = {x for (x, s2), ts in self.rel.items() if s2 == s and any(m - 12 < t <= m for t in ts)}
            if len(new_clients) >= 2 and len(new_clients) / max(len(active), 1) >= 0.5:
                others |= new_clients - {mf}
        for s in newl:
            cl = a5e[a5e["mf_fournisseur"] == s]
            nc = set(cl[cl["premiere_annee_relation"] == E]["mf_payeur"])
            if len(nc) >= 2 and len(nc) / cl["mf_payeur"].nunique() >= 0.5:
                others |= nc - {mf}

        tot = loc["montant_ttc"].sum()
        shell_mask = [self.shell(s, m, E, a5e) for s in loc["mf_fournisseur"]]
        part = loc[shell_mask]["montant_ttc"].sum() / tot if tot > 0 else 0.0

        adj: dict[str, set[str]] = {}
        e5 = self.a5[self.a5["exercice"] <= E]
        e2 = self.a2[(self.a2["exercice"] <= E) & (self.a2["type_id_beneficiaire"] == 1)]
        for u, v in list(zip(e5["mf_payeur"], e5["mf_fournisseur"])) + list(zip(e2["mf_payeur"], e2["id_beneficiaire"])):
            if u != v:
                adj.setdefault(u, set()).add(v)
                adj.setdefault(v, set()).add(u)
        end = (pd.Period(mois, freq="M") + 1).to_timestamp().strftime("%Y-%m-%d")
        sanctioned = set(self.ctl[(self.ctl["categorie_resultat"] == "FRAUDE_SIGNIFICATIVE")
                                  & (self.ctl["date_notification_resultats"] < end)]["mf"]) - {mf}
        seen, queue = {mf: 0}, deque([mf])
        while queue:
            x = queue.popleft()
            if seen[x] >= 3 or (x != mf and len(adj.get(x, ())) > HUB):
                continue
            for y in adj.get(x, ()):
                if y not in seen:
                    seen[y] = seen[x] + 1
                    queue.append(y)
        hits = [seen[r] for r in sanctioned if r in seen]
        return {
            "degre_fournisseurs": len(f12) + loc["mf_fournisseur"].nunique(),
            "nb_fournisseurs_nouveaux_12m": len(newf) + len(newl),
            "nb_clients_partageant_fournisseur_nouveau": len(others),
            "part_achats_coquilles": round(part, 4),
            "est_profil_coquille": self.shell(mf, m, E, a5e),
            "distance_entite_redressee": min(hits) if hits else 99,
        }


@pytest.fixture(scope="module")
def world(tmp_path_factory) -> Path:
    out = tmp_path_factory.mktemp("graph_audit")
    generate(200, cfg.SEED, out)
    return out


def test_metrics_match_independent_recomputation(world):
    bf = BruteForce(world)
    mt = pd.read_csv(world / "graphe" / "metriques_noeuds.csv")
    heroes = mt[mt["mf"].isin([cfg.ALPHA_MF, cfg.OMEGA_MF]) & mt["mois"].isin(["2025-02", "2026-03", "2026-06", "2026-08"])]
    interesting = mt[(mt["distance_entite_redressee"] < 99) | (mt["nb_clients_partageant_fournisseur_nouveau"] > 0)
                     | (mt["part_achats_coquilles"] > 0)]
    rows = pd.concat([mt.sample(120, random_state=1), heroes, interesting.sample(min(80, len(interesting)), random_state=1)])
    mismatches = []
    for _, r in rows.iterrows():
        for k, v in bf.metrics(r["mf"], r["mois"]).items():
            ok = abs(v - r[k]) < 1e-3 if isinstance(v, float) else v == r[k]
            if not ok:
                mismatches.append((r["mf"], r["mois"], k, r[k], v))
    assert not mismatches, mismatches[:10]
    assert len(interesting) > 0  # the audit must exercise non-trivial rows

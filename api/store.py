"""Source des données de l'API. Deux implémentations, même format de sortie (contrat §6.2) :
- MockStore : lit data/mock/*.json (disponible dès 17h00 pour D) ;
- RealStore (api/store_reel.py) : lit data/scores/, data/signaux/, data/raw/, data/graphe/ en mémoire au démarrage.
"""

import json
import os

from scoring.config import GOUVERNORATS, MOCK, MOIS_COURANT, SCORES, SEGMENTS

from .decisions import JournalDecisions

TRIS = {"priorite", "score", "delta_score", "enjeu"}


class Introuvable(Exception):
    pass


class BaseStore:
    mode = "base"

    def __init__(self):
        self.decisions = JournalDecisions(SCORES / "decisions.csv")

    # -- à fournir par les implémentations
    def synthese(self, mois: str) -> dict: ...
    def items_du_mois(self, mois: str) -> list[dict]: ...
    def entreprise(self, mf: str, mois: str) -> dict: ...
    def preuves(self, mf: str, signal: str | None, mois: str) -> dict: ...
    def reseau(self, mf: str, mois: str, profondeur: int) -> dict: ...
    def evaluation(self) -> dict: ...

    # -- commun
    def liste(self, mois: str, segment=None, code_nat=None, gouvernorat=None, tri="priorite", page=1, taille=50) -> dict:
        items = self.items_du_mois(mois)
        if segment:
            voulus = {s.strip().upper() for s in segment.split(",")}
            items = [i for i in items if i["segment"] in voulus]
        if code_nat:
            items = [i for i in items if str(i["code_nat"]).startswith(str(code_nat))]
        if gouvernorat:
            g = str(gouvernorat).strip()
            libelle = GOUVERNORATS.get(int(g)) if g.isdigit() else g
            items = [i for i in items if (i["gouvernorat"] or "").lower() == (libelle or "").lower()]
        tri = tri if tri in TRIS else "priorite"
        cle = {
            "priorite": lambda i: (i["rang_priorite"],),
            "score": lambda i: (-i["score"],),
            "delta_score": lambda i: (-(i["delta_score"] or 0),),
            "enjeu": lambda i: (-(i["enjeu_estime"] or 0),),
        }[tri]
        items = sorted(items, key=cle)
        page, taille = max(1, page), max(1, min(taille, 500))
        debut = (page - 1) * taille
        sortie = []
        for i in items[debut:debut + taille]:
            i = dict(i)
            i["derniere_decision"] = self.decisions.derniere(i["mf"])
            sortie.append(i)
        return {"total": len(items), "page": page, "taille": taille, "items": sortie}

    def entreprise_avec_decisions(self, mf: str, mois: str) -> dict:
        d = dict(self.entreprise(mf, mois))
        d["decisions"] = self.decisions.pour(mf)
        return d


class MockStore(BaseStore):
    mode = "mock"

    def __init__(self):
        super().__init__()
        self.fichiers = {p.name: json.loads(p.read_text(encoding="utf-8")) for p in MOCK.glob("*.json")}
        if not self.fichiers:
            raise RuntimeError("data/mock est vide : lancer `uv run python -m api.mocks`")

    def _f(self, nom: str):
        if nom not in self.fichiers:
            raise Introuvable(nom)
        return self.fichiers[nom]

    def synthese(self, mois):
        return {**self._f("api_stats_synthese.json"), "mois": mois}

    def items_du_mois(self, mois):
        return self._f("api_entreprises.json")["items"]

    def entreprise(self, mf, mois):
        return self._f(f"api_entreprises_{mf}.json")

    def preuves(self, mf, signal, mois):
        if signal:
            return self._f(f"api_entreprises_{mf}_preuves_{signal}.json")
        return self._f(f"api_entreprises_{mf}_preuves.json")

    def reseau(self, mf, mois, profondeur):
        return self._f(f"api_entreprises_{mf}_reseau.json")

    def evaluation(self):
        return self._f("api_evaluation.json")


def creer_store() -> BaseStore:
    mode = os.environ.get("BASIRA_MODE", "auto")
    if mode == "real" or (mode == "auto" and (SCORES / "scores.parquet").exists()):
        from .store_reel import RealStore
        return RealStore()
    return MockStore()


__all__ = ["BaseStore", "MockStore", "Introuvable", "creer_store", "SEGMENTS", "MOIS_COURANT"]

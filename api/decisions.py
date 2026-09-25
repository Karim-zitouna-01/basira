"""Journal des décisions de l'inspecteur : data/scores/decisions.csv (contrat §5.2)."""

import csv
import threading
from datetime import datetime
from pathlib import Path

COLONNES = ["id_decision", "mf", "mois", "date_heure", "decision", "justification", "inspecteur", "score_au_moment", "segment_au_moment"]


class JournalDecisions:
    def __init__(self, chemin: Path):
        self.chemin = chemin
        self._verrou = threading.Lock()
        self._lignes: list[dict] = []
        if chemin.exists():
            with chemin.open(encoding="utf-8", newline="") as f:
                self._lignes = list(csv.DictReader(f))

    def ajouter(self, mf: str, mois: str, decision: str, justification: str, inspecteur: str,
                score: float | None, segment: str | None) -> dict:
        with self._verrou:
            ligne = {
                "id_decision": f"DEC-{len(self._lignes) + 1:06d}", "mf": mf, "mois": mois,
                "date_heure": datetime.now().replace(microsecond=0).isoformat(), "decision": decision,
                "justification": justification, "inspecteur": inspecteur,
                "score_au_moment": "" if score is None else score, "segment_au_moment": segment or "",
            }
            self.chemin.parent.mkdir(parents=True, exist_ok=True)
            nouveau = not self.chemin.exists()
            with self.chemin.open("a", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, fieldnames=COLONNES)
                if nouveau:
                    w.writeheader()
                w.writerow(ligne)
            self._lignes.append(ligne)
            return ligne

    def pour(self, mf: str) -> list[dict]:
        out = []
        for l in self._lignes:
            if l["mf"] == mf:
                d = dict(l)
                d["score_au_moment"] = float(d["score_au_moment"]) if d["score_au_moment"] not in ("", None) else None
                out.append(d)
        return out

    def derniere(self, mf: str) -> dict | None:
        l = self.pour(mf)
        return l[-1] if l else None

    def toutes(self) -> list[dict]:
        return list(self._lignes)

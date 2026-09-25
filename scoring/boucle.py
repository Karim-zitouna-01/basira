"""Démonstration de la boucle d'apprentissage (« avant / après ») — jamais exécutée en direct pendant la démo.

Les décisions des inspecteurs (decisions.csv) deviennent des exemples étiquetés supplémentaires :
VERIFICATION, SIGNALEMENT_DOUANE, DEMANDE_INFO → 1 ; AUCUNE → 0 ; RELANCE → ignorée (pas un verdict).
On réentraîne et on écrit la variation des poids dans data/scores/simulation_boucle.json.

Usage : uv run python -m scoring.boucle            (décisions réelles de decisions.csv)
        uv run python -m scoring.boucle --demo     (si decisions.csv est vide : 30 décisions simulées, signalées comme telles)
"""

import json
import sys

import pandas as pd

from . import config, features, io, train

ETIQUETTES = {"VERIFICATION": 1, "SIGNALEMENT_DOUANE": 1, "DEMANDE_INFO": 1, "AUCUNE": 0}


def decisions_simulees() -> pd.DataFrame:
    """30 décisions plausibles au mois courant : 20 dossiers prioritaires confirmés, 10 dossiers CONFIANCE classés sans suite."""
    s = pd.read_parquet(config.SCORES / "scores.parquet")
    s = s[s["mois"] == config.MOIS_COURANT]
    prio = s[s["segment"] == "PRIORITAIRE"].nsmallest(20, "rang_priorite")
    conf = s[s["segment"] == "CONFIANCE"].head(10)
    return pd.concat([prio.assign(decision="VERIFICATION"), conf.assign(decision="AUCUNE")])[["mf", "mois", "decision"]]


def main(demo: bool = False) -> None:
    chemin = config.SCORES / "decisions.csv"
    dec = pd.read_csv(chemin, dtype=str) if chemin.exists() else pd.DataFrame(columns=["mf", "mois", "decision"])
    simule = False
    if dec.empty and demo:
        dec, simule = decisions_simulees(), True
    dec = dec[dec["decision"].isin(ETIQUETTES)]
    if dec.empty:
        print("Aucune décision exploitable (relancer avec --demo pour une simulation).")
        return
    extra = pd.DataFrame({"mf": dec["mf"], "mois_caracteristiques": dec["mois"], "y": dec["decision"].map(ETIQUETTES),
                          "poids": 1.0})
    X = features.matrice(io.signaux())
    controles = io.controles()
    avant = train.entrainer(X, controles)
    apres = train.entrainer(X, controles, extra)
    variation = []
    for f in config.FEATURES:
        a, b = avant["calibrage"]["poids_appris"][f], apres["calibrage"]["poids_appris"][f]
        variation.append({"code_signal": f, "poids_avant": round(a, 4), "poids_apres": round(b, 4), "variation": round(b - a, 4)})
    variation.sort(key=lambda v: -abs(v["variation"]))
    sortie = {"decisions_ajoutees": int(len(extra)), "simulation": simule,
              "nb_exemples_avant": avant["nb_exemples"], "nb_exemples_apres": apres["nb_exemples"],
              "note": "Poids appris avant calibrage. Les décisions de l'inspecteur deviennent des exemples étiquetés ; "
                      "le modèle est réentraîné hors démo, puis validé avant mise en service.",
              "variations": variation}
    (config.SCORES / "simulation_boucle.json").write_text(json.dumps(sortie, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{len(extra)} décisions{' simulées' if simule else ''} ajoutées ({avant['nb_exemples']} → {apres['nb_exemples']} exemples).")
    for v in variation[:6]:
        print(f"  {v['code_signal']:<28} {v['poids_avant']:7.3f} → {v['poids_apres']:7.3f} ({v['variation']:+.3f})")


if __name__ == "__main__":
    main(demo="--demo" in sys.argv)

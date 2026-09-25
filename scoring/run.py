"""Pipeline de C : entraînement → scores des 24 mois → vérification des héros → évaluation.

Usage : uv run python -m scoring.run            (données de A/B dans data/)
        BASIRA_DATA_DIR=data/dev uv run python -m scoring.run   (données de dev de C)
"""

import time

import pandas as pd

from . import config, evaluate, features, io, score, train
from . import enjeux as enjeux_c

ATTENDUS = {  # contrat §7 : segments acceptés au mois 2026-08, signaux attendus parmi les contributions
    "1000001BAM000": ({"PRIORITAIRE"}, ["COH_IMPORT_VS_CA", "CHG_IMPORTS", "CHG_NOUVEAUX_FOURNISSEURS", "RES_FOURNISSEUR_PARTAGE", "CMB_IMPORT_X_NOUV_FOURN"]),
    "1000002CAM000": ({"PRIORITAIRE", "SURVEILLANCE"}, ["COH_VALEUR_REF"]),
    "1000003DAM000": ({"PRIORITAIRE"}, ["COH_ADEB_VS_CA"]),
    "1000004EAM000": ({"PRIORITAIRE"}, ["CHG_DEPOTS", "CHG_IMPORTS"]),
    "1000005FAM000": ({"SURVEILLANCE"}, ["PAI_MARGE", "PAI_MAHALANOBIS"]),
    "1000006GAM000": ({"NORMAL"}, []),
    "1000007HAM000": ({"CONFIANCE"}, []),
    "1000008JAM000": ({"PRIORITAIRE"}, ["COH_CLIENTS_VS_CA"]),
}


def verifier_heros(scores: pd.DataFrame) -> bool:
    ok_global = True
    s = scores[scores["mois"] == config.MOIS_COURANT].set_index("mf")
    print(f"\nCas héros au mois {config.MOIS_COURANT} :")
    for mf, (segs, signaux) in ATTENDUS.items():
        if mf not in s.index:
            print(f"  ✗ {config.HEROS[mf]:<22} absent des scores")
            ok_global = False
            continue
        r = s.loc[mf]
        codes = [c["code_signal"] for c in r["contributions"]]
        manquants = [c for c in signaux if c not in codes]
        ok = r["segment"] in segs and not manquants
        if mf == "1000002CAM000":
            ok = ok and r["action_suggeree"] == "SIGNALEMENT_DOUANE"
        ok_global &= ok
        traj = scores[(scores["mf"] == mf) & (scores["mois"].isin(config.MOIS[-3:]))].sort_values("mois")["score"].tolist()
        print(f"  {'✓' if ok else '✗'} {config.HEROS[mf]:<22} {r['segment']:<12} score {r['score']:5.1f} "
              f"(3 mois : {' → '.join(f'{x:.0f}' for x in traj)}) action {r['action_suggeree']:<18}"
              + (f" signaux manquants : {manquants}" if manquants else ""))
    if not ok_global:
        print("  ⚠️ Écart avec le contrat §7 : investiguer les signaux avec B avant de toucher aux seuils.")
    return ok_global


def main() -> None:
    t0 = time.time()
    print(f"Données : {config.DATA}")
    sig = io.signaux()
    X = features.matrice(sig)
    print(f"Signaux : {len(sig):,} lignes, {X.index.get_level_values('mf').nunique():,} entreprises × "
          f"{X.index.get_level_values('mois').nunique()} mois")
    controles = io.controles()
    modele = train.entrainer(X, controles)
    train.ecrire(modele)
    print(f"Modèle : {modele['nb_exemples']} contrôles ({modele['nb_positifs']} positifs), intercept {modele['intercept']:.2f} "
          f"→ score_base {100 / (1 + 2.718281828 ** -modele['intercept']):.1f}")
    for f, w in sorted(modele["poids"].items(), key=lambda kv: -kv[1]):
        print(f"    {f:<28} {w:6.3f}")
    if modele["signaux_exclus"]:
        print("  Exclus : " + ", ".join(e["code_signal"] for e in modele["signaux_exclus"]))

    enjeux = io.enjeux()
    try:
        enjeux = enjeux_c.calculer(enjeux)
        enjeux_c.ecrire(enjeux)
        n_c = enjeux[enjeux["mois"] == config.MOIS_COURANT]["source_enjeu"].eq("C").sum()
        print(f"Enjeu complété par C (douane sous-évaluée, imports excédentaires) : {n_c} entreprises en {config.MOIS_COURANT}")
    except (FileNotFoundError, KeyError) as e:
        print(f"Enjeu de B seul (complément C impossible : {e})")
    contrib = io.contribuables()
    scores = score.scorer(X, modele, sig, enjeux, contrib, controles)
    score.ecrire(scores)
    dernier = scores[scores["mois"] == config.MOIS_COURANT]
    print(f"Scores : {len(scores):,} lignes ; {config.MOIS_COURANT} : " +
          ", ".join(f"{k} {v}" for k, v in dernier["segment"].value_counts().items()))
    verifier_heros(scores)

    if (config.RAW / "verite_terrain.csv").exists():
        ev = evaluate.evaluer(scores, X, contrib, io.verite_terrain())
        evaluate.ecrire(ev)
        print("\nÉvaluation (top %d, %s) :" % (ev["top_n"], ev["periode_test"]))
        for m in ev["methodes"]:
            print(f"  {m['nom']:<28} détection {m['taux_detection_top_n']:.0%}  montant/contrôle {config.fmt_dt(m['montant_moyen_par_controle']):>12}"
                  f"  croissance légitime {m['fausses_alertes_croissance_legitime']}  avance {m['avance_detection_mois']}")
    else:
        print("\n(verite_terrain.csv absent : évaluation non calculée)")
    print(f"\nTerminé en {time.time() - t0:.1f} s → {config.SCORES}")


if __name__ == "__main__":
    main()

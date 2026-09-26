"""RealStore : sert l'API à partir des fichiers de A (data/raw, data/graphe), B (data/signaux) et C (data/scores).

Tout est chargé en mémoire au démarrage ; aucune formule de risque n'est recalculée ici (les scores, points, segments,
actions et résumés viennent de scores.parquet). Seules des mises en forme sont faites à la volée (séries, preuves,
sous-graphe, positions dans les pairs).
"""

import json
import logging
import time
from collections import defaultdict, deque

import numpy as np
import pandas as pd

from scoring import config
from scoring.io import lire_csv

from .explications import expliquer
from .store import BaseStore, Introuvable

log = logging.getLogger("basira.store")

FAIT_NOUVEAU_SCHEMA = "Combinaison inhabituelle de signaux forts, rare dans les contrôles passés : nouveau schéma possible."
INDICATEURS = {"MARGE": "Marge apparente", "TVA_DED_SUR_COLL": "TVA déductible / collectée",
               "CA_PAR_SALARIE": "CA par salarié", "IMPORTS_SUR_CA": "Imports / CA"}
MOIS_NOUVELLE_RELATION = 18

# Phrase de repli quand B ne fournit pas de fait_fr (signal sous le seuil d'activation mais porteur de points).
_FAITS_FAIBLES = {
    "COH_IMPORT_VS_CA": "croissance des importations supérieure de {pts} points à celle du CA déclaré (6 mois)",
    "COH_CLIENTS_VS_CA": "paiements déclarés par les clients égaux à {x} fois le CA TTC déclaré",
    "COH_ADEB_VS_CA": "paiements publics égaux à {x} fois le CA déclaré sur 12 mois",
    "COH_TVA_IMPORT": "TVA déduite sur importations égale à {x} fois la TVA payée en douane",
    "COH_VALEUR_REF": "valeurs unitaires déclarées à {pct} du prix de référence",
    "CHG_CA": "CA déclaré à {z} écarts-types de son niveau habituel",
    "CHG_IMPORTS": "importations à {z} écarts-types au-dessus de leur niveau habituel",
    "CHG_TVA_DEDUCTIBLE": "TVA déductible locale à {z} écarts-types au-dessus de son niveau habituel",
    "CHG_NOUVEAUX_FOURNISSEURS": "{n} fournisseur(s) nouveau(x) sur la période récente",
    "CHG_NOUVELLES_CATEGORIES": "{n} chapitre(s) SH importé(s) pour la première fois sur 3 mois",
    "CHG_DEPOTS": "{n} déclaration(s) sur 6 non déposée(s) ou en retard de plus de 30 jours",
    "PAI_MARGE": "marge apparente à {z} écarts-types sous celle des pairs",
    "PAI_MAHALANOBIS": "profil à une distance {z} du centre de son groupe de pairs",
    "RES_FOURNISSEUR_PARTAGE": "{n} entreprise(s) démarrent avec le même nouveau fournisseur",
    "RES_COQUILLE": "{n} % des achats déclarés auprès de fournisseurs à profil coquille",
    "RES_PROXIMITE_REDRESSE": "à {n} relation(s) d'une entreprise redressée pour fraude significative",
}


def _nombre(v: float, nd: int = 1) -> str:
    return f"{v:.{nd}f}".replace(".", ",").rstrip("0").rstrip(",") if nd else f"{v:.0f}"


def fait_faible(code: str, brute: float, v: float) -> str:
    modele = _FAITS_FAIBLES.get(code)
    if not modele or brute is None or not np.isfinite(brute):
        return ""
    texte = modele.format(pts=f"{brute:+.0f}".replace("-", "−"), x=_nombre(brute, 2), pct=f"{brute * 100:.0f} %",
                          z=_nombre(brute, 1), n=_nombre(brute, 0))
    return f"Signal faible ({_nombre(v, 2)} sur 1, sous le seuil d'activation) : {texte}."


def _f(x, nd=3):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return None
    return round(float(x), nd)


def _liste(x) -> list:
    if x is None:
        return []
    if isinstance(x, float) and np.isnan(x):
        return []
    return [str(v) for v in list(x)]


def _fin_de_mois(mois: str) -> str:
    return f"{mois}-31"


def _mois_moins(mois: str, n: int) -> str:
    a, m = map(int, mois.split("-"))
    k = a * 12 + (m - 1) - n
    return f"{k // 12:04d}-{k % 12 + 1:02d}"


class RealStore(BaseStore):
    mode = "real"

    def __init__(self):
        super().__init__()
        t0 = time.time()
        self._charger_scores()
        self._charger_referentiels()
        self._charger_signaux()
        self._charger_series()
        self._charger_preuves()
        self._charger_graphe()
        self._items_cache: dict[str, list[dict]] = {}
        log.info("RealStore chargé en %.1f s depuis %s (%d entreprises, %d mois)", time.time() - t0, config.DATA,
                 len(self.identites), len(self.mois_dispo))

    # ------------------------------------------------------------------ chargement
    def _charger_scores(self):
        s = pd.read_parquet(config.SCORES / "scores.parquet")
        self.mois_dispo = sorted(s["mois"].unique())
        self.scores = {(r["mf"], r["mois"]): r for r in s.to_dict("records")}
        self.traj = {mf: g.sort_values("mois")[["mois", "score", "segment"]].to_dict("records") for mf, g in s.groupby("mf")}
        self.par_mois = {m: g for m, g in s.groupby("mois")}
        p = config.SCORES / "evaluation.json"
        self._evaluation = json.loads(p.read_text(encoding="utf-8")) if p.exists() else None

    def _charger_referentiels(self):
        c = lire_csv("contribuables.csv")
        nat = lire_csv("ref_nat.csv", obligatoire=False)
        lib_nat = dict(zip(nat["code_nat"], nat["libelle"])) if len(nat) else {}
        gv = lire_csv("ref_gouvernorats.csv", obligatoire=False)
        lib_gouv = {int(k): v for k, v in zip(gv["gouvernorat_code"], gv["libelle"])} if len(gv) else dict(config.GOUVERNORATS)
        self.identites = {}
        for r in c.to_dict("records"):
            eff = r.get("effectif_declare")
            self.identites[r["mf"]] = {
                "mf": r["mf"], "matricule_fiscal": r.get("matricule_fiscal") or r["mf"], "raison_sociale": r["raison_sociale"],
                "forme_juridique": r.get("forme_juridique"), "code_nat": r["code_nat"], "libelle_nat": lib_nat.get(r["code_nat"], ""),
                "gouvernorat": lib_gouv.get(int(r["gouvernorat_code"]), str(r["gouvernorat_code"])) if pd.notna(r.get("gouvernorat_code")) else None,
                "date_debut_activite": r.get("date_debut_activite"), "effectif": int(eff) if pd.notna(eff) else None,
                "statut_oea": str(r.get("statut_oea")).lower() in ("true", "1"), "centre_gestion": r.get("centre_gestion"),
            }
        self.noms = {mf: i["raison_sociale"] for mf, i in self.identites.items()}
        fe = lire_csv("fournisseurs_etrangers.csv", obligatoire=False)
        self.noms_fe = dict(zip(fe["id_fournisseur"], fe["nom"])) if len(fe) else {}
        ap = lire_csv("ref_acheteurs_publics.csv", obligatoire=False)
        self.noms_ap = dict(zip(ap["id_acheteur_public"], ap["libelle"])) if len(ap) else {}
        # enjeu complété par C (scoring/enjeux.py) s'il existe, sinon celui de B
        complet = config.SCORES / "enjeux.parquet"
        e = pd.read_parquet(complet if complet.exists() else config.SIGNAUX / "enjeux.parquet")
        self.enjeux = {(r["mf"], r["mois"]): r for r in e[["mf", "mois", "enjeu_estime", "enjeu_bas", "enjeu_haut", "confiance"]].to_dict("records")}
        ctl = lire_csv("historique_controles.csv", obligatoire=False)
        self.controles = defaultdict(list)
        for r in ctl.to_dict("records"):
            total = sum(float(r.get(k) or 0) for k in ("montant_redresse_tva", "montant_redresse_is", "montant_redresse_rs"))
            self.controles[r["mf"]].append({"id_controle": r["id_controle"], "date_avis": r["date_avis"], "type_controle": r["type_controle"],
                                            "origine_selection": r["origine_selection"], "categorie_resultat": r["categorie_resultat"],
                                            "montant_redresse_total": round(total, 3)})
        gp = config.SIGNAUX / "groupes_pairs.parquet"
        ps = config.SIGNAUX / "pairs_stats.parquet"
        self.groupes = pd.read_parquet(gp).set_index("mf").to_dict("index") if gp.exists() else {}
        self.pairs_stats = {(r["groupe"], r["mois"], r["indicateur"]): r for r in pd.read_parquet(ps).to_dict("records")} if ps.exists() else {}

    def _charger_signaux(self):
        cols = ["mf", "mois", "code_signal", "lentille", "valeur_norm", "valeur_brute", "fait_fr", "sources", "preuves"]
        sig = pd.read_parquet(config.SIGNAUX / "signaux.parquet", columns=cols, filters=[("valeur_norm", ">", 0)])
        self.signaux: dict[tuple, dict] = defaultdict(dict)
        self.brutes: dict[tuple, dict] = defaultdict(dict)  # valeur_brute, pour les explications chiffrées
        for mf, mois, code, lent, v, brute, fait, src, pr in sig.itertuples(index=False):
            self.signaux[(mf, mois)][code] = (float(v), fait or fait_faible(code, brute, v), _liste(src), _liste(pr))
            self.brutes[(mf, mois)][code] = float(brute)

    def _charger_series(self):
        d = lire_csv("declarations_mensuelles.csv")
        d = d[d["mois"].isin(config.MOIS)]
        self.declarations = {(r["mf"], r["mois"]): r for r in d.to_dict("records")}
        art = lire_csv("douane_articles.csv", obligatoire=False)
        ddm = lire_csv("douane_declarations.csv", obligatoire=False)
        imports = {}
        if len(art) and len(ddm):
            ddm = ddm[["num_declaration", "date_enregistrement", "mf_importateur", "circuit", "bureau_code"]]
            art = art.merge(ddm, on="num_declaration", how="left")
            art["mois"] = art["date_enregistrement"].str[:7]
            imports = art.groupby(["mf_importateur", "mois"])["valeur_caf_tnd"].sum().to_dict()
        self.articles = art.set_index("id_article") if len(art) else pd.DataFrame()
        self.series = {}
        for mf in self.identites:
            lignes = []
            for m in config.MOIS:
                r = self.declarations.get((mf, m), {})
                lignes.append({"mois": m, "ca_declare": _f(r.get("ca_total_declare"), 3) or 0.0,
                               "imports_caf": round(float(imports.get((mf, m), 0.0)), 3),
                               "tva_deductible": _f(r.get("tva_deductible_biens_services_local"), 3) or 0.0})
            self.series[mf] = lignes

    def _charger_preuves(self):
        a5 = lire_csv("employeur_annexe5.csv", obligatoire=False)
        self.annexe5 = a5.set_index("id_ligne") if len(a5) else pd.DataFrame()
        a2 = lire_csv("employeur_annexe2.csv", obligatoire=False)
        self.annexe2 = a2.set_index("id_ligne") if len(a2) else pd.DataFrame()
        ad = lire_csv("adeb_paiements.csv", obligatoire=False)
        self.adeb = ad.set_index("num_ordonnance") if len(ad) else pd.DataFrame()
        nd = lire_csv("ref_ndp.csv", obligatoire=False)
        self.prix_ref = dict(zip(nd["code_ndp"], nd["prix_reference_tnd"])) if len(nd) and "prix_reference_tnd" in nd else {}

    def _charger_graphe(self):
        a = lire_csv("aretes.csv", dossier=config.GRAPHE, obligatoire=False)
        self.adj = defaultdict(list)
        for r in a.to_dict("records"):
            self.adj[r["source"]].append(r)
            self.adj[r["cible"]].append(r)
        mn = config.GRAPHE / "metriques_noeuds.csv"
        self.coquilles = set()
        if mn.exists():
            m = lire_csv("metriques_noeuds.csv", dossier=config.GRAPHE)
            if "est_profil_coquille" in m:
                m = m[m["est_profil_coquille"].astype(str).str.lower().isin(["true", "1"])]
                self.coquilles = set(zip(m["mf"], m["mois"]))

    # ------------------------------------------------------------------ utilitaires
    def _ligne(self, mf, mois) -> dict:
        r = self.scores.get((mf, mois))
        if r is None:
            if mf not in self.identites:
                raise Introuvable(mf)
            raise Introuvable(f"{mf} au mois {mois}")
        return r

    def _mois_precedent(self, mois):
        i = self.mois_dispo.index(mois) if mois in self.mois_dispo else -1
        return self.mois_dispo[i - 1] if i > 0 else None

    def _enjeu(self, mf, mois) -> dict:
        e = self.enjeux.get((mf, mois), {})
        return {"estime": _f(e.get("enjeu_estime")) or 0.0, "bas": _f(e.get("enjeu_bas")) or 0.0, "haut": _f(e.get("enjeu_haut")) or 0.0,
                "confiance": _f(e.get("confiance"), 2)}

    def _signal(self, mf, mois, code):
        """(valeur_norm, fait_fr, sources, preuves) ; les combinaisons héritent des sources/preuves de leurs 2 signaux."""
        s = self.signaux.get((mf, mois), {})
        if code in config.COMBINAISONS:
            a, b, fait = config.COMBINAISONS[code]
            va, vb = s.get(a, (0.0, "", [], [])), s.get(b, (0.0, "", [], []))
            v = va[0] * vb[0]
            if v < config.SEUIL_ACTIF:
                fait = f"Signal faible ({_nombre(v, 2)} sur 1) : combinaison partielle de {a} et {b}."
            return (v, fait, sorted(set(va[2]) | set(vb[2])), list(dict.fromkeys(va[3] + vb[3]))[:50])
        return s.get(code, (0.0, "", [], []))

    def _est_coquille(self, mf, mois) -> bool:
        return (mf, mois) in self.coquilles

    # ------------------------------------------------------------------ routes
    def synthese(self, mois):
        if mois not in self.par_mois:
            raise Introuvable(f"mois {mois}")
        g = self.par_mois[mois]
        par = {s: int((g["segment"] == s).sum()) for s in config.SEGMENTS}
        prec = self._mois_precedent(mois)
        prio = set(g.loc[g["segment"] == "PRIORITAIRE", "mf"])
        avant = set(self.par_mois[prec].loc[self.par_mois[prec]["segment"] == "PRIORITAIRE", "mf"]) if prec else set()
        enjeu = float(g.loc[g["segment"] == "PRIORITAIRE", "enjeu_estime"].sum()) if "enjeu_estime" in g else 0.0
        return {"mois": mois, "nb_entreprises": int(len(g)), "par_segment": par, "nouveaux_prioritaires_du_mois": len(prio - avant),
                "enjeu_total_prioritaires": round(enjeu, 3), "seuils": dict(config.SEUILS)}

    def items_du_mois(self, mois):
        if mois in self._items_cache:
            return self._items_cache[mois]
        if mois not in self.par_mois:
            raise Introuvable(f"mois {mois}")
        prec = self._mois_precedent(mois)
        items = []
        for r in self.par_mois[mois].to_dict("records"):
            ident = self.identites.get(r["mf"], {})
            sp = self.scores.get((r["mf"], prec), {}).get("score") if prec else None
            e = self._enjeu(r["mf"], mois)
            items.append({
                "mf": r["mf"], "raison_sociale": ident.get("raison_sociale"), "code_nat": ident.get("code_nat"),
                "libelle_nat": ident.get("libelle_nat"), "gouvernorat": ident.get("gouvernorat"),
                "score": _f(r["score"], 1), "score_mois_precedent": _f(sp, 1),
                "delta_score": _f(r["score"] - sp, 1) if sp is not None else None, "segment": r["segment"],
                "enjeu_estime": e["estime"], "enjeu_bas": e["bas"], "enjeu_haut": e["haut"], "rang_priorite": int(r["rang_priorite"]),
                "resume_fr": r["resume_fr"], "action_suggeree": r["action_suggeree"], "derniere_decision": None,
            })
        self._items_cache[mois] = items
        return items

    def entreprise(self, mf, mois):
        r = self._ligne(mf, mois)
        e = self._enjeu(mf, mois)
        contributions = []
        pairs = self._pairs(mf, mois)
        for c in r["contributions"]:
            code, pts = c["code_signal"], float(c["points"])
            if code == config.NOUVEAU_SCHEMA:
                contributions.append({"code_signal": code, "lentille": "COMBINAISON", "points": round(pts, 1), "valeur_norm": None,
                                      "fait_fr": FAIT_NOUVEAU_SCHEMA, "sources": [], "nb_preuves": 0,
                                      "explication": expliquer(self, mf, mois, code, FAIT_NOUVEAU_SCHEMA, pairs)})
                continue
            v, fait, src, pr = self._signal(mf, mois, code)
            contributions.append({"code_signal": code, "lentille": config.LENTILLES.get(code, "COMBINAISON"), "points": round(pts, 1),
                                  "valeur_norm": round(v, 2), "fait_fr": fait, "sources": src, "nb_preuves": len(pr),
                                  "explication": expliquer(self, mf, mois, code, fait, pairs)})
        return {
            "identite": self.identites[mf], "score": _f(r["score"], 1), "segment": r["segment"], "confiance": e["confiance"],
            "enjeu": {"estime": e["estime"], "bas": e["bas"], "haut": e["haut"]}, "action_suggeree": r["action_suggeree"],
            "resume_fr": r["resume_fr"],
            "trajectoire": [{"mois": t["mois"], "score": _f(t["score"], 1), "segment": t["segment"]} for t in self.traj[mf] if t["mois"] <= mois],
            "contributions": contributions, "pairs": pairs,
            "series": [s for s in self.series.get(mf, []) if s["mois"] <= mois],
            "decisions": [], "controles_passes": [c for c in self.controles.get(mf, []) if c["date_avis"][:7] <= mois],
        }

    def _indicateurs_entreprise(self, mf, mois) -> dict:
        fen = [m for m in config.MOIS if _mois_moins(mois, 12) < m <= mois]
        s = [x for x in self.series.get(mf, []) if x["mois"] in fen]
        ca = sum(x["ca_declare"] for x in s)
        imp = sum(x["imports_caf"] for x in s)
        ded = sum(float(self.declarations.get((mf, m), {}).get("tva_deductible_biens_services_local") or 0)
                  + float(self.declarations.get((mf, m), {}).get("tva_deductible_import") or 0) for m in fen)
        col = sum(float(self.declarations.get((mf, m), {}).get("tva_collectee") or 0) for m in fen)
        loc = sum(x["tva_deductible"] for x in s)
        eff = self.identites.get(mf, {}).get("effectif")
        achats = imp + loc / 0.19
        return {"MARGE": (ca - achats) / ca if ca > 0 else None, "TVA_DED_SUR_COLL": ded / col if col > 0 else None,
                "CA_PAR_SALARIE": ca / eff if eff else None, "IMPORTS_SUR_CA": imp / ca if ca > 0 else None}

    def _pairs(self, mf, mois) -> dict:
        g = self.groupes.get(mf)
        if not g:
            return {"groupe": None, "nb_pairs": 0, "indicateurs": []}
        val = self._indicateurs_entreprise(mf, mois)
        ind = []
        for code, nom in INDICATEURS.items():
            st = self.pairs_stats.get((g["groupe"], mois, code))
            if st is None:
                continue
            ind.append({"nom": nom, "entreprise": _f(val.get(code), 3), "mediane_pairs": _f(st["mediane"]), "p10": _f(st["p10"]), "p90": _f(st["p90"])})
        return {"groupe": g.get("libelle_groupe") or g["groupe"], "nb_pairs": int(g.get("nb_pairs") or 0), "indicateurs": ind}

    # ------------------------------------------------------------------ preuves
    def _ligne_preuve(self, ref: str) -> dict:
        table, _, ident = ref.partition(":")
        try:
            if table == "douane_articles" and ident in self.articles.index:
                a = self.articles.loc[ident]
                pref = self.prix_ref.get(a["code_ndp"])
                champs = {"pays_origine": a.get("pays_origine"), "quantite": _f(a.get("quantite"), 3), "unite": a.get("unite"),
                          "prix_unitaire_tnd": _f(a.get("prix_unitaire_tnd")), "circuit": a.get("circuit")}
                if pref is not None:
                    champs["prix_reference_tnd"] = _f(pref)
                return {"source": table, "ref": ident, "date": a.get("date_enregistrement"),
                        "libelle": f"NDP {a['code_ndp']} — {a.get('designation', '')} — {a.get('pays_origine', '')} — {a.get('id_fournisseur_etranger', '')}",
                        "montant": _f(a["valeur_caf_tnd"]), "champs": champs}
            if table == "employeur_annexe5" and ident in self.annexe5.index:
                a = self.annexe5.loc[ident]
                return {"source": table, "ref": ident, "date": f"{int(a['exercice'])}-12-31",
                        "libelle": f"Annexe V {int(a['exercice'])} — {self.noms.get(a['mf_payeur'], a['mf_payeur'])} déclare des achats auprès de "
                                   f"{self.noms.get(a['mf_fournisseur'], a['mf_fournisseur'])}",
                        "montant": _f(a["montant_ttc"]), "champs": {"mf_payeur": a["mf_payeur"], "mf_fournisseur": a["mf_fournisseur"],
                                                                    "exercice": int(a["exercice"]), "premiere_annee_relation": _f(a.get("premiere_annee_relation"), 0)}}
            if table == "employeur_annexe2" and ident in self.annexe2.index:
                a = self.annexe2.loc[ident]
                return {"source": table, "ref": ident, "date": f"{int(a['exercice'])}-12-31",
                        "libelle": f"Annexe II {int(a['exercice'])} — {self.noms.get(a['mf_payeur'], a['mf_payeur'])} → {a.get('id_beneficiaire', '')}",
                        "montant": _f(a.get("montant_brut")), "champs": {"type_montant": _f(a.get("type_montant"), 0), "retenue": _f(a.get("retenue"))}}
            if table == "adeb_paiements" and ident in self.adeb.index:
                a = self.adeb.loc[ident]
                return {"source": table, "ref": ident, "date": a.get("date_paiement"),
                        "libelle": f"Ordonnance de paiement — {self.noms_ap.get(a.get('id_acheteur_public'), a.get('id_acheteur_public'))} — {a.get('nature_achat', '')}",
                        "montant": _f(a["montant_ht"]), "champs": {"montant_ttc": _f(a.get("montant_ttc")), "retenue_tva_25": _f(a.get("retenue_tva_25")),
                                                                   "nature_achat": a.get("nature_achat")}}
            if table == "declarations_mensuelles":
                mf, _, mois = ident.partition(":")
                d = self.declarations.get((mf, mois))
                if d is not None:
                    return {"source": table, "ref": ident, "date": d.get("date_depot") if isinstance(d.get("date_depot"), str) else d.get("date_limite"),
                            "libelle": f"Déclaration mensuelle {mois} — {'déposée' if d.get('statut_depot') == 'DEPOSEE' else 'non déposée'}",
                            "montant": _f(d.get("ca_total_declare")),
                            "champs": {"statut_depot": d.get("statut_depot"), "jours_retard": _f(d.get("jours_retard"), 0),
                                       "tva_collectee": _f(d.get("tva_collectee")),
                                       "tva_deductible_biens_services_local": _f(d.get("tva_deductible_biens_services_local")),
                                       "tva_deductible_import": _f(d.get("tva_deductible_import"))}}
        except (KeyError, ValueError, TypeError) as e:
            log.warning("preuve illisible %s : %s", ref, e)
        return {"source": table, "ref": ident, "date": None, "libelle": ref, "montant": None, "champs": {}}

    def preuves(self, mf, signal, mois):
        r = self._ligne(mf, mois)
        if not signal:
            codes = [c["code_signal"] for c in r["contributions"] if c["code_signal"] != config.NOUVEAU_SCHEMA]
            if not codes:
                raise Introuvable(f"aucun signal pour {mf}")
            signal = codes[0]
        v, fait, _, refs = self._signal(mf, mois, signal)
        lignes = [self._ligne_preuve(x) for x in refs]
        return {"code_signal": signal, "fait_fr": fait, "lignes": lignes}

    # ------------------------------------------------------------------ réseau
    def _noeud(self, i, mois, centre=False) -> dict:
        if i in self.identites:
            seg = self.scores.get((i, mois), {}).get("segment")
            return {"id": i, "label": self.noms[i], "type": "ENTREPRISE", "segment": seg, "est_coquille": self._est_coquille(i, mois), "centre": centre}
        if i in self.noms_ap or i.startswith("AP"):
            return {"id": i, "label": self.noms_ap.get(i, i), "type": "ACHETEUR_PUBLIC", "segment": None, "est_coquille": False, "centre": centre}
        return {"id": i, "label": self.noms_fe.get(i, i), "type": "FOURNISSEUR_ETRANGER", "segment": None, "est_coquille": False, "centre": centre}

    def reseau(self, mf, mois, profondeur, max_noeuds: int = 40):
        self._ligne(mf, mois)
        fin, seuil_nouv = _fin_de_mois(mois), _mois_moins(mois, MOIS_NOUVELLE_RELATION)
        vus, file, aretes = {mf: 0}, deque([mf]), {}
        while file and len(vus) < max_noeuds:
            n = file.popleft()
            if vus[n] >= profondeur:
                continue
            voisins = [a for a in self.adj.get(n, []) if str(a["premiere_date"]) <= fin]
            # priorité aux relations nouvelles puis aux montants élevés
            voisins.sort(key=lambda a: (str(a["premiere_date"])[:7] < seuil_nouv, -float(a["montant_total"] or 0)))
            for a in voisins:
                autre = a["cible"] if a["source"] == n else a["source"]
                if autre not in vus:
                    if len(vus) >= max_noeuds:
                        break
                    vus[autre] = vus[n] + 1
                    file.append(autre)
                aretes[(a["source"], a["cible"], a["type_relation"])] = a
        noeuds = [self._noeud(i, mois, centre=(i == mf)) for i in vus]
        sortie = [{"source": s, "cible": c, "type_relation": t, "montant": _f(a["montant_total"]), "premiere_date": str(a["premiere_date"])[:10],
                   "nouvelle": str(a["premiere_date"])[:7] >= seuil_nouv}
                  for (s, c, t), a in aretes.items() if s in vus and c in vus]
        return {"noeuds": noeuds, "aretes": sortie}

    def evaluation(self):
        if self._evaluation is None:
            raise Introuvable("evaluation.json (lancer scoring.run avec verite_terrain.csv)")
        return self._evaluation

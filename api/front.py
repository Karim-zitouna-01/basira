"""Adaptateur pour l'interface de D (web/) : mêmes formes que son jeu fictif `web/src/data/mockData.json`,
construites à partir des vraies données (A : raw/graphe, B : signaux, C : scores/enjeux).

- `portefeuille()` : toutes les entreprises, résumé + 12 mois compacts (le crossfilter de la liste tourne côté navigateur).
- `fiche(mf)` : l'entreprise au format de D (historique, opérations, réseau, contrôles) + `detail` = fiche du contrat §6
  (contributions, preuves, pairs, décisions) pour le panneau « Pourquoi ce score ».

Aucune formule de risque ici : scores, segments, points et enjeux viennent de C.
« Écart de recoupement » de D = enjeu estimé de C (12 mois glissants) ; source « ANNEXE V » (remplace « TJ » de D) = annexe V (achats déclarés par les
clients / auprès des fournisseurs, exercice rattaché au 31/12) ; « RAFIK » n'a pas de source simulée.
"""

import logging
import time
from collections import defaultdict

import numpy as np
import pandas as pd

from scoring import config
from scoring.config import fmt_dt
from scoring.io import lire_csv

from .store_reel import MOIS_NOUVELLE_RELATION, RealStore, _mois_moins

log = logging.getLogger("basira.front")

FENETRE = config.MOIS[-12:]  # 12 derniers mois affichés par D
DEBUT = f"{FENETRE[0]}-01"
FIN = f"{FENETRE[-1]}-31"

LIBELLES_SIGNAUX = {
    "COH_IMPORT_VS_CA": "Imports en hausse, CA stable",
    "COH_CLIENTS_VS_CA": "Achats des clients > CA déclaré",
    "COH_ADEB_VS_CA": "Paiements publics > CA déclaré",
    "COH_TVA_IMPORT": "TVA import sur-déduite",
    "COH_VALEUR_REF": "Valeur en douane anormalement basse",
    "CHG_CA": "Rupture du CA déclaré",
    "CHG_IMPORTS": "Hausse brutale des imports",
    "CHG_TVA_DEDUCTIBLE": "Hausse de la TVA déductible",
    "CHG_NOUVEAUX_FOURNISSEURS": "Nouveaux fournisseurs",
    "CHG_NOUVELLES_CATEGORIES": "Nouvelles catégories importées",
    "CHG_DEPOTS": "Déclarations manquantes ou tardives",
    "PAI_MARGE": "Marge très inférieure aux pairs",
    "PAI_MAHALANOBIS": "Profil atypique pour le secteur",
    "RES_FOURNISSEUR_PARTAGE": "Nouveau fournisseur partagé",
    "RES_COQUILLE": "Achats auprès de sociétés coquilles",
    "RES_PROXIMITE_REDRESSE": "Proche d'une entité redressée",
    "CMB_IMPORT_X_NOUV_FOURN": "Imports concentrés sur des nouveaux fournisseurs",
    "CMB_COQUILLE_X_TVA": "TVA déduite sur achats à des coquilles",
    config.NOUVEAU_SCHEMA: "Nouveau schéma de risque",
}
ACTIONS = {"AUCUNE": "Aucune action", "RELANCE": "Relance de conformité", "DEMANDE_INFO": "Demande d'information",
           "VERIFICATION": "Vérification approfondie", "SIGNALEMENT_DOUANE": "Signalement à la douane"}
SEG_CODE = {s: i for i, s in enumerate(config.SEGMENTS)}
PAYS = {"AE": "Émirats arabes unis", "AT": "Autriche", "BE": "Belgique", "BR": "Brésil", "CH": "Suisse", "CN": "Chine",
        "CZ": "Tchéquie", "DE": "Allemagne", "DZ": "Algérie", "EG": "Égypte", "ES": "Espagne", "FR": "France", "GB": "Royaume-Uni",
        "GR": "Grèce", "IN": "Inde", "IT": "Italie", "JP": "Japon", "KR": "Corée du Sud", "LY": "Libye", "MA": "Maroc",
        "MY": "Malaisie", "NL": "Pays-Bas", "PK": "Pakistan", "PL": "Pologne", "PT": "Portugal", "RO": "Roumanie",
        "SE": "Suède", "TH": "Thaïlande", "TR": "Turquie", "US": "États-Unis", "VN": "Viêt Nam"}
CIRCUITS = {"V": "Vert", "O": "Orange", "R": "Rouge"}
CATEGORIES_CONTROLE = {"CONFORME": "Conforme", "REDRESSEMENT_MINEUR": "Redressement mineur",
                       "FRAUDE_SIGNIFICATIVE": "Fraude significative"}


def _entier(x) -> int:
    return int(round(float(x))) if x is not None and not (isinstance(x, float) and np.isnan(x)) else 0


def _montant(x) -> float:
    return round(float(x), 3) if x is not None and not (isinstance(x, float) and np.isnan(x)) else 0.0


class FrontStore:
    def __init__(self, store: RealStore):
        t0 = time.time()
        self.s = store
        self.mois = config.MOIS_COURANT
        self._charger_operations()
        self._portefeuille = None
        log.info("FrontStore chargé en %.1f s", time.time() - t0)

    # ------------------------------------------------------------------ chargement des opérations (12 mois)
    def _charger_operations(self):
        s = self.s
        dec = lire_csv("douane_declarations.csv")
        dec = dec[(dec["date_enregistrement"] >= DEBUT) & (dec["date_enregistrement"] <= FIN)]
        art = s.articles.reset_index() if len(s.articles) else pd.DataFrame()
        # contrepartie d'une déclaration = fournisseur de l'article le plus important
        principal = (art[art["num_declaration"].isin(dec["num_declaration"])]
                     .sort_values("valeur_caf_tnd", ascending=False).drop_duplicates("num_declaration")
                     .set_index("num_declaration")[["id_fournisseur_etranger", "pays_origine"]])
        dec = dec.join(principal, on="num_declaration")
        self.douane = {mf: g for mf, g in dec.groupby("mf_importateur")}

        ad = s.adeb.reset_index() if len(s.adeb) else pd.DataFrame()
        ad = ad[(ad["date_paiement"] >= DEBUT) & (ad["date_paiement"] <= FIN)] if len(ad) else ad
        self.adeb = {mf: g for mf, g in ad.groupby("mf_beneficiaire")} if len(ad) else {}
        self.adeb_mois = ad.assign(mois=ad["date_paiement"].str[:7]).groupby(["mf_beneficiaire", "mois"])["montant_ht"].sum().to_dict() \
            if len(ad) else {}

        a5 = s.annexe5.reset_index() if len(s.annexe5) else pd.DataFrame()
        # annexe V : exercice N rattaché au 31/12/N, visible dans la fenêtre si N = 2025 (déposée en février 2026)
        a5 = a5[a5["exercice"].astype(int).map(lambda e: DEBUT <= f"{e}-12-31" <= FIN)] if len(a5) else a5
        self.a5_fournisseur = {mf: g for mf, g in a5.groupby("mf_fournisseur")} if len(a5) else {}
        self.a5_client = {mf: g for mf, g in a5.groupby("mf_payeur")} if len(a5) else {}
        # pour expliquer les profils coquilles : sommes reçues (annexe V 2025) et salariés (annexe I, dernier exercice)
        tout_a5 = s.annexe5.reset_index() if len(s.annexe5) else pd.DataFrame()
        self.a5_recu_2025 = tout_a5[tout_a5["exercice"].astype(int) == 2025].groupby("mf_fournisseur")["montant_ttc"].sum().to_dict() if len(tout_a5) else {}
        a1 = lire_csv("employeur_annexe1_synthese.csv", obligatoire=False)
        self.salaries = a1.sort_values("exercice").drop_duplicates("mf", keep="last").set_index("mf")["nb_salaries"].to_dict() if len(a1) else {}

        # fournisseurs étrangers « nouveaux et partagés » : ≥ 3 importateurs ayant commencé avec eux en moins de 18 mois
        seuil = _mois_moins(self.mois, 18)
        nouveaux = defaultdict(set)
        for mf, aretes in s.adj.items():
            for a in aretes:
                if a["type_relation"] == "IMPORT_FOURNISSEUR" and a["source"] == mf and str(a["premiere_date"])[:7] >= seuil:
                    nouveaux[a["cible"]].add(mf)
        self.fe_partages = {fe for fe, mfs in nouveaux.items() if len(mfs) >= 3}

    # ------------------------------------------------------------------ utilitaires
    def _segment(self, mf, mois=None):
        return self.s.scores.get((mf, mois or self.mois), {}).get("segment")

    def _motif(self, contrepartie: str, mf: str) -> str | None:
        """Pourquoi une contrepartie est signalée (None si elle ne l'est pas) — affiché tel quel dans l'interface."""
        s = self.s
        if contrepartie in s.identites:
            if s._est_coquille(contrepartie, self.mois):
                return "Profil de société coquille : sans salarié, créée récemment, reçoit bien plus que son CA déclaré"
            r = s.scores.get((contrepartie, self.mois))
            if r is not None and r["segment"] == "PRIORITAIRE":
                return f"Entreprise elle-même prioritaire (score {round(r['score'])}/100)"
            return None
        if contrepartie in self.fe_partages:
            nouveau = any(a["cible"] == contrepartie and str(a["premiere_date"])[:7] >= _mois_moins(self.mois, 18)
                          for a in s.adj.get(mf, []) if a["source"] == mf)
            if nouveau:
                n = sum(1 for a in s.adj.get(contrepartie, []) if a["type_relation"] == "IMPORT_FOURNISSEUR"
                        and str(a["premiere_date"])[:7] >= _mois_moins(self.mois, 18))
                return f"Fournisseur étranger adopté en même temps par {n} importateurs en moins de 18 mois"
        return None

    def _signalee(self, contrepartie: str, mf: str) -> bool:
        return self._motif(contrepartie, mf) is not None

    def _motif_detail(self, contrepartie: str, mf: str) -> dict | None:
        """Motif du signalement avec ses preuves chiffrées : {titre, details[]} (affiché dans le panneau du graphe)."""
        titre = self._motif(contrepartie, mf)
        if titre is None:
            return None
        s, details = self.s, []
        if contrepartie in s.identites and s._est_coquille(contrepartie, self.mois):
            ident = s.identites[contrepartie]
            sal = self.salaries.get(contrepartie)
            details.append("Aucun salarié déclaré (annexe I)" if not sal else f"{sal} salarié(s) déclaré(s) (annexe I)")
            debut = str(ident.get("date_debut_activite") or "")[:10]
            if debut:
                mois_age = (int(self.mois[:4]) - int(debut[:4])) * 12 + int(self.mois[5:7]) - int(debut[5:7])
                details.append(f"Créée le {debut[8:10]}/{debut[5:7]}/{debut[:4]}, il y a {mois_age} mois")
            recu = self.a5_recu_2025.get(contrepartie, 0.0)
            ca = sum(_montant(s.declarations.get((contrepartie, f"2025-{m:02d}"), {}).get("ca_total_declare")) for m in range(1, 13))
            if recu:
                ratio = f" (×{recu / ca:,.0f})".replace(",", " ") if ca > 0 else ""
                details.append(f"Ses clients déclarent lui avoir versé {fmt_dt(recu)} en 2025 (annexe V), pour {fmt_dt(ca)} de CA déclaré{ratio}")
            details.append("Ces trois critères réunis sont la définition d'une société écran servant à émettre de fausses factures.")
        elif contrepartie in s.identites:
            r = s.scores[(contrepartie, self.mois)]
            detail = s.entreprise(contrepartie, self.mois)
            for c in sorted(detail["contributions"], key=lambda c: -c["points"])[:3]:
                details.append(f"{LIBELLES_SIGNAUX.get(c['code_signal'], c['code_signal'])} (+{c['points']:.0f} pts) : {c['explication']}")
            details.append(f"Action suggérée par Basira pour cette entreprise : {ACTIONS.get(r['action_suggeree'], r['action_suggeree'])}.")
        else:  # fournisseur étranger nouveau et partagé
            seuil = _mois_moins(self.mois, 18)
            premiere = min((str(a["premiere_date"])[:10] for a in s.adj.get(contrepartie, [])), default="")
            if premiere:
                details.append(f"Connu en douane depuis le {premiere[8:10]}/{premiere[5:7]}/{premiere[:4]}, mais plusieurs importateurs l'ont adopté récemment, au même moment")
            importateurs = [a["source"] for a in s.adj.get(contrepartie, [])
                            if a["type_relation"] == "IMPORT_FOURNISSEUR" and str(a["premiere_date"])[:7] >= seuil]
            noms = [f"{s.noms.get(i, i)} ({(self._segment(i) or 'NORMAL').lower()})" for i in importateurs if i != mf][:5]
            if noms:
                details.append(f"Autres importateurs qui ont commencé avec lui depuis moins de 18 mois : {', '.join(noms)}")
            details.append("Plusieurs entreprises qui adoptent en même temps un fournisseur inconnu : schéma typique d'un réseau "
                           "de sous-facturation ou d'importations non déclarées.")
        return {"titre": titre, "details": details}

    def _declencheur(self, r) -> str:
        # seulement pour les entreprises à surveiller : ailleurs, les signaux faibles ne « déclenchent » rien
        if r["segment"] not in ("PRIORITAIRE", "SURVEILLANCE"):
            return "Aucun signal notable"
        top = [c for c in sorted(r["contributions"], key=lambda c: -c["points"]) if c["points"] >= 5][:2]
        return " · ".join(LIBELLES_SIGNAUX.get(c["code_signal"], c["code_signal"]) for c in top) or "Aucun signal notable"

    def _resume(self, mf) -> dict:
        s, i = self.s, self.s.identites[mf]
        r = s.scores[(mf, self.mois)]
        avant = s.scores.get((mf, _mois_moins(self.mois, 2)), {}).get("score", r["score"])
        delta = _entier(r["score"]) - _entier(avant)
        e = s._enjeu(mf, self.mois)
        imp = [x["imports_caf"] for x in s.series.get(mf, []) if x["mois"] in FENETRE]
        return {
            "company_id": i["matricule_fiscal"], "mf": mf, "company_name": i["raison_sociale"],
            "sector_nacef": f"{i['code_nat']} - {i['libelle_nat']}", "gouvernorat": i["gouvernorat"] or "—",
            "current_risk_score": _entier(r["score"]), "segment": r["segment"], "risk_delta_2m": f"{delta:+d}".replace("+0", "0"),
            "primary_trigger": self._declencheur(r), "sinda_import_vol_dt": _montant(sum(imp)),
            "adeb_contracts_val_dt": _montant(sum(self.adeb_mois.get((mf, m), 0.0) for m in FENETRE)),
            "recoupment_gap_dt": _montant(e["estime"]), "recommended_action": ACTIONS.get(r["action_suggeree"], r["action_suggeree"]),
            "rang_priorite": int(r["rang_priorite"]),
        }

    # ------------------------------------------------------------------ routes
    def portefeuille(self) -> dict:
        """Toutes les entreprises ; `h` = 12 mois compacts [score, segment (index), enjeu, imports]."""
        if self._portefeuille is not None:
            return self._portefeuille
        s = self.s
        entreprises = []
        for mf in s.identites:
            if (mf, self.mois) not in s.scores:
                continue
            d = self._resume(mf)
            serie = {x["mois"]: x for x in s.series.get(mf, [])}
            h = []
            for m in FENETRE:
                r = s.scores.get((mf, m))
                h.append([_entier(r["score"]) if r else 0, SEG_CODE.get(r["segment"], 2) if r else 2,
                          round(s._enjeu(mf, m)["estime"]), round(serie.get(m, {}).get("imports_caf", 0.0))])
            d["h"] = h
            entreprises.append(d)
        self._portefeuille = {"meta": {"mois_reference": self.mois, "mois_couverts": FENETRE, "segments": list(config.SEGMENTS),
                                       "nb_entreprises": len(entreprises)},
                              "entreprises": entreprises}
        return self._portefeuille

    def fiche(self, mf: str) -> dict:
        s = self.s
        if (mf, self.mois) not in s.scores:
            raise KeyError(mf)
        d = self._resume(mf)
        serie = {x["mois"]: x for x in s.series.get(mf, [])}
        d["historique_mensuel"] = []
        for m in FENETRE:
            r = s.scores.get((mf, m), {})
            decl = s.declarations.get((mf, m), {})
            d["historique_mensuel"].append({
                "mois": m, "score": _entier(r.get("score")), "segment": r.get("segment", "NORMAL"),
                "ecart_recoupement_dt": round(s._enjeu(mf, m)["estime"]),
                "declaration_deposee": decl.get("statut_depot") == "DEPOSEE",
                "ca_declare_dt": round(serie.get(m, {}).get("ca_declare", 0.0)),
                "imports_sinda_dt": round(serie.get(m, {}).get("imports_caf", 0.0)),
                "paiements_adeb_dt": round(self.adeb_mois.get((mf, m), 0.0)),
                "factures_tj_dt": 0, "arrieres_rafik_dt": 0,
            })
        d["operations"] = self._operations(mf)
        d["network_nodes"], d["liens_portefeuille"], d["reseau_resume"] = self._reseau(mf)
        d["controles_passes"] = [{"date": c["date_avis"], "type": f"Contrôle {str(c['type_controle']).lower()}",
                                  "resultat": CATEGORIES_CONTROLE.get(c["categorie_resultat"], c["categorie_resultat"]),
                                  "montant_redresse_dt": c["montant_redresse_total"]} for c in s.controles.get(mf, [])]
        detail = s.entreprise_avec_decisions(mf, self.mois)
        for c in detail["contributions"]:
            c["libelle"] = LIBELLES_SIGNAUX.get(c["code_signal"], c["code_signal"])
        d["detail"] = detail
        return d

    def _operations(self, mf) -> list[dict]:
        s, ops = self.s, []

        def ajouter(date, source, type_op, cid, nom, ctype, montant, reference, pays=None, circuit=None, observation=None):
            ops.append({"id": f"{mf}-{len(ops) + 1:04d}", "date": str(date)[:10], "mois": str(date)[:7], "source": source,
                        "type_operation": type_op, "contrepartie_id": cid, "contrepartie": nom, "contrepartie_type": ctype,
                        "contrepartie_signalee": self._signalee(cid, mf), "pays": pays, "montant_dt": _montant(montant),
                        "circuit": circuit, "reference": reference, "observation": observation})

        for r in self.douane.get(mf, pd.DataFrame()).to_dict("records"):
            fe = r.get("id_fournisseur_etranger")
            fe = fe if isinstance(fe, str) else "FE-INCONNU"
            ajouter(r["date_enregistrement"], "SINDA", "Déclaration d'importation", fe, s.noms_fe.get(fe, fe), "Fournisseur étranger",
                    r["valeur_caf_tnd"], r["num_declaration"], PAYS.get(r.get("pays_origine"), r.get("pays_origine")),
                    CIRCUITS.get(r.get("circuit"), r.get("circuit")))
        for r in self.adeb.get(mf, pd.DataFrame()).to_dict("records"):
            ap = r["id_acheteur_public"]
            obs = "Retenue TVA 25 % non constatée" if not float(r.get("retenue_tva_25") or 0) and float(r["montant_ttc"]) >= 1000 else None
            ajouter(r["date_paiement"], "ADEB", "Paiement de marché public", ap, s.noms_ap.get(ap, ap), "Acheteur public",
                    r["montant_ht"], r["num_ordonnance"], observation=obs)
        for r in self.a5_fournisseur.get(mf, pd.DataFrame()).to_dict("records"):
            c = r["mf_payeur"]
            ajouter(f"{int(r['exercice'])}-12-31", "ANNEXE V", "Achat déclaré par un client", c, s.noms.get(c, c), "Client",
                    r["montant_ttc"], r["id_ligne"])
        for r in self.a5_client.get(mf, pd.DataFrame()).to_dict("records"):
            f = r["mf_fournisseur"]
            obs = "Fournisseur à profil coquille" if s._est_coquille(f, self.mois) else None
            ajouter(f"{int(r['exercice'])}-12-31", "ANNEXE V", "Achat déclaré auprès d'un fournisseur", f, s.noms.get(f, f),
                    "Fournisseur local", r["montant_ttc"], r["id_ligne"], observation=obs)
        return sorted(ops, key=lambda o: o["date"])

    # (type de relation, l'entreprise paie ?) → (type de contrepartie, libellé de la relation)
    RELATIONS = {("IMPORT_FOURNISSEUR", True): ("Fournisseur étranger", "Import"),
                 ("ACHAT_LOCAL_A5", True): ("Fournisseur local", "Achat · annexe V"),
                 ("ACHAT_LOCAL_A5", False): ("Client", "Vente · annexe V"),
                 ("HONORAIRES_A2", True): ("Prestataire", "Honoraires"),
                 ("HONORAIRES_A2", False): ("Client (honoraires)", "Honoraires reçus"),
                 ("PAIEMENT_PUBLIC", False): ("Acheteur public", "Paiement public"),
                 # vus depuis un fournisseur étranger ou un acheteur public (graphe déployé)
                 ("IMPORT_FOURNISSEUR", False): ("Importateur", "Import"),
                 ("PAIEMENT_PUBLIC", True): ("Entreprise payée", "Paiement public")}

    def _reseau(self, mf, max_contreparties: int = 40, max_liees: int = 4):
        """Contreparties (flux sur la fenêtre) : `sens` = sortant si l'entreprise paie la contrepartie, entrant sinon."""
        s = self.s
        par_id = {}
        nouveau = _mois_moins(self.mois, MOIS_NOUVELLE_RELATION)
        anciennes = 0
        for a in s.adj.get(mf, []):
            if str(a["derniere_date"])[:10] < DEBUT or str(a["premiere_date"])[:10] > FIN:
                anciennes += 1  # relation arrêtée avant la fenêtre : comptée, pas dessinée
                continue
            t, sortant = a["type_relation"], a["source"] == mf
            autre = a["cible"] if sortant else a["source"]
            if (t, sortant) not in self.RELATIONS:
                continue
            genre, relation = self.RELATIONS[(t, sortant)]
            nom = s.noms.get(autre) or s.noms_fe.get(autre) or s.noms_ap.get(autre) or autre
            n = par_id.setdefault(autre, {"id": autre, "label": nom, "type": genre, "relation": relation,
                                          "sens": "sortant" if sortant else "entrant", "motif": self._motif(autre, mf),
                                          "montant_dt": 0.0, "depuis": str(a["premiere_date"])[:10],
                                          "nouvelle": str(a["premiere_date"])[:7] >= nouveau,
                                          "segment": self._segment(autre) if autre in s.identites else None,
                                          "coquille": s._est_coquille(autre, self.mois)})
            n["montant_dt"] = round(n["montant_dt"] + float(a["montant_total"] or 0), 3)
        for n in par_id.values():
            n["risk_flag"] = n["motif"] is not None
        tous = sorted(par_id.values(), key=lambda n: (not n["risk_flag"], -n["montant_dt"]))
        noeuds = tous[:max_contreparties]
        liens = {}
        for n in noeuds:
            n["nb_liees"] = 0
            n["motif_detail"] = self._motif_detail(n["id"], mf) if n["risk_flag"] else None
            if n["type"] == "Acheteur public":
                continue  # les acheteurs publics paient des centaines d'entreprises : pas de lien de niveau 2
            autres = []
            for a in s.adj.get(n["id"], []):
                x = a["cible"] if a["source"] == n["id"] else a["source"]
                if x != mf and x in s.identites and str(a["derniere_date"])[:10] >= DEBUT and all(o["mf"] != x for o in autres):
                    autres.append({"mf": x, "company_name": s.noms[x], "segment": self._segment(x) or "NORMAL",
                                   "_p": self._segment(x) == "PRIORITAIRE"})
            autres.sort(key=lambda o: not o.pop("_p"))
            n["nb_liees"] = len(autres)
            if autres:
                liens[n["id"]] = autres[:max_liees]
        resume = {"debut": FENETRE[0], "fin": FENETRE[-1], "relations_fenetre": len(tous), "relations_affichees": len(noeuds),
                  "relations_anciennes": anciennes,
                  "sources": "annexe V (achats déclarés, exercice 2025), douane (SINDA), ADEB, annexe II (honoraires)"}
        return noeuds, liens, resume

    def voisins(self, ident: str, limite: int = 8) -> dict:
        """Réseau d'un nœud quelconque (entreprise, fournisseur étranger, acheteur public) pour « déployer » le graphe :
        contreparties signalées d'abord, puis les plus gros flux ; chacune avec son motif détaillé."""
        s = self.s
        if ident not in s.identites and ident not in s.noms_fe and ident not in s.noms_ap:
            raise KeyError(ident)
        noeuds, liens, resume = self._reseau(ident, max_contreparties=limite)
        for n in noeuds:
            n["liees"] = liens.get(n["id"], [])
        r = s.scores.get((ident, self.mois))
        return {"id": ident, "nom": s.noms.get(ident) or s.noms_fe.get(ident) or s.noms_ap.get(ident) or ident,
                "segment": r["segment"] if r else None, "score": round(r["score"]) if r else None,
                "noeuds": noeuds, "total": resume["relations_fenetre"]}

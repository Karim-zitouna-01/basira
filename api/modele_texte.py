"""Repli déterministe de l'assistant (mode « modele_texte ») : phrases construites uniquement
à partir des données (fait_fr, contributions, enjeu, trajectoire). Fonctionne toujours, sans GPU."""

import unicodedata

from scoring.config import DECISIONS, fmt_dt

LIBELLE_LENTILLE = {"COHERENCE": "cohérence", "CHANGEMENT": "changement", "PAIRS": "pairs",
                    "RESEAU": "réseau", "COMBINAISON": "combinaison"}

PIECES = {
    "COH_IMPORT_VS_CA": "les factures d'achat à l'importation et le journal des ventes de la période concernée",
    "CHG_IMPORTS": "les contrats et bons de commande liés aux importations récentes",
    "CHG_NOUVEAUX_FOURNISSEURS": "l'identification complète des nouveaux fournisseurs et les contrats conclus avec eux",
    "RES_FOURNISSEUR_PARTAGE": "les justificatifs de la relation commerciale avec les fournisseurs récemment apparus",
    "CMB_IMPORT_X_NOUV_FOURN": "l'état détaillé des achats auprès des fournisseurs nouveaux (factures, paiements, destination des marchandises)",
    "COH_CLIENTS_VS_CA": "le journal des ventes et les factures émises aux clients de l'exercice",
    "COH_ADEB_VS_CA": "les factures émises aux acheteurs publics et les attestations de retenue à la source",
    "COH_TVA_IMPORT": "les quittances de TVA acquittée en douane et le détail de la TVA déduite sur importations",
    "COH_VALEUR_REF": "les factures commerciales, contrats d'achat et preuves de paiement des marchandises importées",
    "CHG_CA": "les explications et justificatifs de la variation du chiffre d'affaires déclaré",
    "CHG_TVA_DEDUCTIBLE": "les factures d'achat ayant donné lieu à déduction de TVA",
    "CHG_NOUVELLES_CATEGORIES": "la description de la nouvelle activité d'importation et les factures correspondantes",
    "CHG_DEPOTS": "les déclarations mensuelles manquantes ou les justificatifs des retards",
    "PAI_MARGE": "l'état détaillé des achats consommés et des stocks permettant d'expliquer la marge déclarée",
    "PAI_MAHALANOBIS": "les états financiers de l'exercice et leurs annexes",
    "RES_COQUILLE": "les justificatifs de la réalité des prestations et livraisons des fournisseurs concernés",
    "CMB_COQUILLE_X_TVA": "les factures d'achat auprès des fournisseurs concernés et les preuves de livraison et de paiement",
    "RES_PROXIMITE_REDRESSE": "les justificatifs des opérations réalisées avec les partenaires commerciaux concernés",
}


def _normaliser(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", t.lower()) if unicodedata.category(c) != "Mn")


def intention(question: str) -> str:
    q = _normaliser(question)
    if any(m in q for m in ("lettre", "demande d'information", "demande d info", "redige", "courrier")):
        return "lettre"
    if any(m in q for m in ("fournisseur", "reseau", "client", "partenaire")):
        return "reseau"
    return "pourquoi"


def _pts(p: float) -> str:
    return f"{p:+.1f}".replace(".", ",")


def _nom(detail: dict) -> str:
    return detail["identite"]["raison_sociale"]


def _de(nom: str) -> str:
    """« de Beta » / « d'Alpha »."""
    return f"d'{nom}" if _normaliser(nom[:1]) in "aeiouyh" else f"de {nom}"


def _sans_point(t: str) -> str:
    return t.rstrip(" .")


def expliquer(detail: dict, preuves_top: dict | None = None) -> dict:
    traj = detail.get("trajectoire") or []
    score, seg = detail["score"], detail["segment"]
    contribs = sorted(detail.get("contributions") or [], key=lambda c: -c["points"])[:3]
    phrases = []
    if len(traj) >= 3 and abs(score - traj[-3]["score"]) >= 5:
        ref = traj[-3]
        sens = "passé" if score != ref["score"] else "resté"
        phrases.append(f"Le score {_de(_nom(detail))} est {sens} de {ref['score']:.0f} à {score:.0f} entre {ref['mois']} et {traj[-1]['mois']} "
                       f"(segment {seg}).")
    else:
        phrases.append(f"Le score {_de(_nom(detail))} est de {score:.0f} sur 100 (segment {seg}), sans variation marquée sur les derniers mois.")
    if contribs:
        phrases.append("Principales raisons :")
        for i, c in enumerate(contribs, 1):
            phrases.append(f"{i}. {_sans_point(c['fait_fr'])} ({_pts(c['points'])} points, lentille {LIBELLE_LENTILLE.get(c['lentille'], c['lentille'])}, "
                           f"{c.get('nb_preuves', 0)} preuve(s)).")
    else:
        phrases.append("Aucun signal de risque n'est actif pour cette entreprise.")
    e = detail.get("enjeu") or {}
    if e.get("estime"):
        phrases.append(f"Enjeu estimé : {fmt_dt(e['estime'])} (fourchette {fmt_dt(e.get('bas'))} – {fmt_dt(e.get('haut'))}).")
    action = detail.get("action_suggeree")
    if action:
        phrases.append(f"Action suggérée : {DECISIONS.get(action, action)}. La décision appartient à l'inspecteur.")
    citations = [{"type": "signal", "ref": c["code_signal"]} for c in contribs]
    if preuves_top and preuves_top.get("lignes"):
        l0 = preuves_top["lignes"][0]
        phrases.insert(len(contribs) + 2 if contribs else 2,
                       f"Exemple de preuve : {l0['libelle']} ({l0['date']}, {fmt_dt(l0['montant'])}).")
        citations.append({"type": "preuve", "ref": f"{l0['source']}:{l0['ref']}"})
    return {"reponse": "\n".join(phrases), "citations": citations, "mode": "modele_texte"}


def lettre_demande_info(detail: dict) -> dict:
    ident = detail["identite"]
    contribs = sorted(detail.get("contributions") or [], key=lambda c: -c["points"])[:4]
    lignes = [
        "Projet de lettre — à relire et valider par l'inspecteur.",
        "",
        f"Objet : Demande d'information — {ident['raison_sociale']} (matricule fiscal {ident.get('matricule_fiscal', ident['mf'])})",
        "",
        "Madame, Monsieur,",
        "",
        "Dans le cadre du suivi de votre dossier fiscal et des recoupements effectués avec les informations dont dispose "
        "l'administration, les éléments suivants appellent des précisions de votre part :",
    ]
    lignes += [f"- {c['fait_fr']}" for c in contribs if c.get("fait_fr")]
    lignes += ["", "Nous vous prions de bien vouloir nous transmettre, dans un délai de trente jours à compter de la réception "
               "du présent courrier, les documents suivants :"]
    pieces = []
    for c in contribs:
        p = PIECES.get(c["code_signal"])
        if p and p not in pieces:
            pieces.append(p)
    lignes += [f"- {p} ;" for p in pieces] or ["- tout document permettant d'expliquer les écarts relevés ;"]
    lignes += ["", "Cette demande ne préjuge pas de la suite qui sera donnée à votre dossier. Vos explications seront examinées "
               "avant toute décision.", "", "Veuillez agréer, Madame, Monsieur, l'expression de nos salutations distinguées.", "",
               "L'inspecteur chargé du dossier"]
    return {"reponse": "\n".join(lignes), "citations": [{"type": "signal", "ref": c["code_signal"]} for c in contribs],
            "mode": "modele_texte"}


def resumer_reseau(detail: dict, reseau: dict) -> dict:
    mf = detail["identite"]["mf"]
    noeuds = {n["id"]: n for n in reseau.get("noeuds", [])}
    lignes, citations = [], []
    nouvelles = [a for a in reseau.get("aretes", []) if a.get("nouvelle")]
    anciennes = [a for a in reseau.get("aretes", []) if not a.get("nouvelle")]
    lignes.append(f"Réseau {_de(_nom(detail))} : {len(noeuds) - 1} partenaire(s) liés, dont {len(nouvelles)} relation(s) nouvelle(s).")
    for a in nouvelles[:6]:
        autre = a["cible"] if a["source"] == mf else a["source"]
        n = noeuds.get(autre, {"label": autre})
        role = "fournisseur" if a["source"] == mf else "client ou partenaire"
        extra = " — profil coquille" if n.get("est_coquille") else ""
        seg = f" (segment {n['segment']})" if n.get("segment") else ""
        if a["source"] != mf and a["cible"] != mf:
            role = f"partage le fournisseur {noeuds.get(a['cible'], {'label': a['cible']})['label']}"
            lignes.append(f"- {n['label']}{seg} {role} depuis le {a['premiere_date']} ({fmt_dt(a['montant'])}){extra}.")
        else:
            lignes.append(f"- {n['label']}{seg}, {role}, relation nouvelle depuis le {a['premiere_date']} ({fmt_dt(a['montant'])}){extra}.")
    if anciennes:
        lignes.append(f"{len(anciennes)} relation(s) plus ancienne(s) sans changement notable.")
    for c in detail.get("contributions") or []:
        if c["lentille"] == "RESEAU" or c["code_signal"].startswith(("CHG_NOUVEAUX", "CMB_")):
            lignes.append(f"Signal associé : {c['fait_fr']}")
            citations.append({"type": "signal", "ref": c["code_signal"]})
    return {"reponse": "\n".join(lignes), "citations": citations, "mode": "modele_texte"}


def repondre(question: str, detail: dict, preuves_top: dict | None = None, reseau: dict | None = None) -> dict:
    i = intention(question)
    if i == "lettre":
        return lettre_demande_info(detail)
    if i == "reseau" and reseau is not None:
        return resumer_reseau(detail, reseau)
    return expliquer(detail, preuves_top)


def resumer_liste(page: dict, synthese: dict) -> dict:
    """Repli de la liste : synthèse du portefeuille et premières entreprises affichées (données de l'écran)."""
    par = synthese.get("par_segment", {})
    lignes = [f"Portefeuille au {synthese.get('mois', '')} : {synthese.get('nb_entreprises', 0)} entreprises, "
              f"{par.get('PRIORITAIRE', 0)} prioritaires ({synthese.get('nouveaux_prioritaires_du_mois', 0)} nouvelles ce mois), "
              f"{par.get('SURVEILLANCE', 0)} sous surveillance."]
    affichees = page.get("entreprises_affichees") or []
    if affichees:
        lignes.append(f"Premières des {page.get('nb_affichees', len(affichees))} entreprises affichées :")
        for e in affichees[:5]:
            lignes.append(f"- {e.get('nom')} : score {e.get('score')} ({e.get('delta')}), {e.get('statut')}, "
                          f"enjeu {fmt_dt(e.get('ecart_dt') or 0)}, {e.get('action')}.")
    lignes.append("Ouvrez une fiche pour voir le détail du score et ses preuves.")
    return {"reponse": "\n".join(lignes), "citations": [], "mode": "modele_texte"}

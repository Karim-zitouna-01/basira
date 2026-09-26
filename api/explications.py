"""Explications chiffrées : pourquoi un signal pèse dans le score, en une ou deux phrases vérifiables.

Les phrases de B (`fait_fr`) disent *quoi* (« la marge est inférieure à celle des pairs ») ; ici on ajoute *combien* et
*par rapport à quoi*, à partir de `valeur_brute` (B), des statistiques de pairs (B) et du graphe (A). Aucune nouvelle
formule de risque : uniquement une mise en mots des valeurs déjà calculées.
"""

import re
from collections import deque

from scoring import config

_PIECE = re.compile(r"\s*Pièce\s*:?\s*[a-z_0-9]+(:[^\s:]+)+(\s*:\s*[^.]*?\d[\d  ,.]*\s*(DT|MD))?\.?")


def sans_piece(texte: str) -> str:
    """Retire les références de pièces des phrases de B (elles sont montrées à part, dans les preuves)."""
    return re.sub(r"\s{2,}", " ", _PIECE.sub("", texte or "")).strip()


def _n(v: float, d: int = 0) -> str:
    return f"{v:,.{d}f}".replace(",", " ").replace(".", ",")


def _pct(v) -> str:
    return "—" if v is None else f"{round(v * 100)} %"


def _indicateur(pairs: dict, nom: str) -> dict | None:
    return next((i for i in pairs.get("indicateurs", []) if i["nom"] == nom), None)


def entite_redressee_proche(store, mf: str, mois: str, profondeur: int = 3, hub: int = 20):
    """Entreprise redressée pour fraude significative la plus proche dans le graphe (règle de A : les hubs ne relaient pas).
    Renvoie (mf, nom, distance, chemin de noms) ou None."""
    ids = chemin_redresse(store, mf, mois, profondeur, hub)
    if ids is None:
        return None
    x = ids[-1]
    return x, store.noms.get(x, x), len(ids) - 1, [store.noms.get(y, y) for y in ids]


def chemin_redresse(store, mf: str, mois: str, profondeur: int = 3, hub: int = 20) -> list[str] | None:
    """Chemin d'identifiants [mf, …, entreprise redressée] le plus court (annexes V et II), ou None."""
    fin = f"{mois}-31"
    redressees = {m for m, ctl in store.controles.items()
                  for c in ctl if c["categorie_resultat"] == "FRAUDE_SIGNIFICATIVE" and str(c["date_avis"]) <= fin}
    vus, file = {mf: None}, deque([(mf, 0)])
    while file:
        n, d = file.popleft()
        if d >= profondeur:
            continue
        voisins = [a["cible"] if a["source"] == n else a["source"] for a in store.adj.get(n, [])
                   if a["type_relation"] in ("ACHAT_LOCAL_A5", "HONORAIRES_A2") and str(a["premiere_date"]) <= fin]
        if n != mf and len(voisins) > hub:
            continue
        for x in voisins:
            if x in vus:
                continue
            vus[x] = n
            if x in redressees:
                chemin, y = [], x
                while y is not None:
                    chemin.append(y)
                    y = vus[y]
                return list(reversed(chemin))
            file.append((x, d + 1))
    return None


def expliquer(store, mf: str, mois: str, code: str, fait: str, pairs: dict) -> str:
    brute = store.brutes.get((mf, mois), {}).get(code)
    fait = sans_piece(fait)
    if code == config.NOUVEAU_SCHEMA:
        return ("Plusieurs signaux forts présents ensemble, dans une combinaison jamais vue dans les contrôles passés : "
                "chacun pèse peu seul, mais leur réunion mérite un examen.")
    if code in config.COMBINAISONS:
        a, b, texte = config.COMBINAISONS[code]
        return f"{texte} Les deux signaux sont présents en même temps, ce qui renforce chacun d'eux."
    if brute is None:
        return fait
    if code == "COH_IMPORT_VS_CA":
        return (f"Sur les 6 derniers mois déclarés, les importations ont progressé de {_n(brute)} points de plus que le CA déclaré "
                "(par rapport aux 6 mois précédents) : des marchandises entrent sans ventes déclarées en face.")
    if code == "COH_CLIENTS_VS_CA":
        return f"{fait} Les clients déclarent donc {_n(brute, 1)} fois ce que l'entreprise déclare comme chiffre d'affaires."
    if code == "COH_ADEB_VS_CA":
        return f"{fait} Les seuls paiements publics représentent {_n(brute, 2)} fois le CA déclaré."
    if code == "COH_TVA_IMPORT":
        return f"La TVA déduite sur importations représente {_n(brute, 2)} fois la TVA réellement payée en douane sur 12 mois."
    if code == "COH_VALEUR_REF":
        return (f"Sur 6 mois, les prix unitaires déclarés en douane sont en moyenne à {round(brute * 100)} % du prix de référence "
                "des mêmes codes NDP : la valeur en douane est probablement minorée, donc les droits aussi.")
    if code == "CHG_CA":
        sens = "au-dessus" if brute > 0 else "en dessous"
        return f"Le CA déclaré du mois est à {_n(abs(brute), 1)} écarts-types {sens} de son niveau habituel (12 mois précédents)."
    if code == "CHG_IMPORTS":
        return f"Les importations du mois sont à {_n(brute, 1)} écarts-types au-dessus de leur niveau habituel (12 mois précédents)."
    if code == "CHG_TVA_DEDUCTIBLE":
        return f"La TVA déductible sur achats locaux est à {_n(brute, 1)} écarts-types au-dessus de son niveau habituel."
    if code == "CHG_NOUVEAUX_FOURNISSEURS":
        return f"{_n(brute)} fournisseur(s) apparu(s) pour la première fois récemment (douane : 3 derniers mois ; annexe V : dernier exercice)."
    if code == "CHG_NOUVELLES_CATEGORIES":
        return f"{_n(brute)} chapitre(s) douanier(s) importé(s) pour la première fois sur les 3 derniers mois : changement d'activité non déclaré ?"
    if code == "CHG_DEPOTS":
        return f"{_n(brute)} déclaration(s) mensuelle(s) sur les 6 dernières non déposée(s) ou déposée(s) avec plus de 30 jours de retard."
    if code == "PAI_MARGE":
        i = _indicateur(pairs, "Marge apparente")
        if i:
            return (f"Marge apparente de {_pct(i['entreprise'])} sur 12 mois (CA déclaré moins achats observés), contre {_pct(i['mediane_pairs'])} "
                    f"en médiane chez ses {pairs.get('nb_pairs')} pairs ({pairs.get('groupe')}) ; 80 % des pairs entre {_pct(i['p10'])} et {_pct(i['p90'])}. "
                    "Une marge aussi basse suggère des ventes non déclarées ou des achats gonflés.")
        return f"Marge apparente à {_n(brute, 1)} écarts-types sous celle de ses pairs."
    if code == "PAI_MAHALANOBIS":
        detail = fait.split("surtout")[-1].strip(" .") if "surtout" in fait else None
        return (f"L'ensemble marge, TVA déductible/collectée, CA par salarié et imports/CA est atypique pour son groupe de pairs "
                f"(distance {_n(brute, 1)} ; au-delà de 2, moins de 5 % des pairs){f', surtout {detail}' if detail else ''}.")
    if code == "RES_FOURNISSEUR_PARTAGE":
        return (f"{_n(brute)} entreprise(s) ont commencé au même moment avec le même nouveau fournisseur : "
                "schéma typique d'un réseau organisé autour d'un fournisseur écran.")
    if code == "RES_COQUILLE":
        return f"{_n(brute)} % des achats déclarés en annexe V vont à des sociétés au profil de coquille (sans salarié, récentes, encaissant bien plus que leur CA)."
    if code == "RES_PROXIMITE_REDRESSE":
        p = entite_redressee_proche(store, mf, mois)
        if p:
            _, nom, d, chemin = p
            lien = "partenaire direct" if d == 1 else f"à {d} relations ({' → '.join(chemin)})"
            return f"{nom}, redressée pour fraude significative, est {lien} dans le graphe des achats (annexes V et II)."
        return f"Une entreprise redressée pour fraude significative se trouve à {_n(brute)} relation(s) dans le graphe des achats."
    return fait

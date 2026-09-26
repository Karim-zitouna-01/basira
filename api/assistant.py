"""Assistant de l'inspecteur : un appel LLM (Qwen local, API compatible OpenAI) avec quelques outils.

- Répond uniquement à partir des outils ; cite ses sources ; ne décide jamais.
- Garde-fou : tout nombre de la réponse doit se retrouver dans les données renvoyées par les outils.
- Tout échec (URL absente, erreur, > LLM_TIMEOUT s, garde-fou) → repli modele_texte.
"""

import json
import logging
import re
import time

from openai import BadRequestError

from scoring import config

from . import modele_texte
from .store import BaseStore, Introuvable

log = logging.getLogger("basira.assistant")

PROMPT_SYSTEME = """Tu es l'assistant de Basira, un outil d'aide au contrôle fiscal de l'administration tunisienne.
Tu aides un inspecteur à comprendre pourquoi le risque d'une entreprise a changé.

Règles impératives :
1. Tu réponds en français, de façon brève et factuelle (5 à 10 lignes maximum).
2. Tu t'appuies UNIQUEMENT sur les données renvoyées par les outils. Tu n'inventes jamais un chiffre, un nom ou une date :
   chaque nombre de ta réponse doit figurer tel quel dans les données des outils.
3. Tu ne décides jamais. Tu peux rappeler l'action suggérée, mais la décision appartient à l'inspecteur.
4. Si une information n'est pas dans les données, dis-le simplement.
5. Termine ta réponse par une ligne « SOURCES : » suivie des codes de signaux (tels qu'ils figurent dans les données) et des références de
   preuves (ex. douane_articles:2026/401/0034567-001) que tu as utilisés, séparés par des virgules.
6. Les montants sont en dinars tunisiens : écris « DT » (ou « MD » pour les millions), jamais une autre devise.
   Arrondis-les sans décimales (ex. « 44 987 DT », « 1,2 MD »). Mets en forme avec des listes Markdown courtes et du **gras**
   pour les éléments clés ; pas de titres.
7. Pour le réseau, respecte exactement le sens des relations décrit dans le champ « relations » (qui paie qui, qui est client).
8. Si l'inspecteur demande une lettre, appelle rediger_lettre_demande_info et recopie la lettre intégralement, sans la résumer.
9. Le score est sur 100 (jamais en DT). Pour son évolution, nomme le mois de départ et le mois d'arrivée et prends les deux
   scores dans la même « trajectoire » (ex. « de 46 en juin 2026 à 84 en août 2026 ») ; ne mélange pas deux périodes.
10. Pour une contrepartie précise (« qui d'autre travaille avec … ? », « pourquoi … est signalé ? »), appelle
   get_liens_contrepartie. Pour un lien avec une entreprise redressée, une chaîne de fournisseurs ou une source de fraude,
   appelle get_chemin_redresse et décris le chemin étape par étape en reprenant la phrase « relation » de chaque étape
   (« X a payé Y »), sans flèches. Le graphe de l'écran suit ces outils.
"""

PROMPT_LISTE = """Tu es l'assistant de Basira, un outil d'aide au contrôle fiscal de l'administration tunisienne.
L'inspecteur regarde la liste des entreprises de son portefeuille ; les données de son écran sont jointes en JSON.

Règles impératives :
1. Tu réponds en français, de façon brève et factuelle (5 à 10 lignes maximum).
2. Tu t'appuies UNIQUEMENT sur les données jointes. Tu n'inventes jamais un chiffre, un nom ou une date.
3. Tu ne décides jamais : tu aides l'inspecteur à choisir quels dossiers ouvrir en premier.
4. Si une information n'est pas dans les données, dis-le simplement et invite à ouvrir la fiche de l'entreprise.
5. Les montants sont en dinars tunisiens : écris « DT » (ou « MD » pour les millions), jamais une autre devise.
   Arrondis-les sans décimales. Mets en forme avec des listes Markdown courtes et du **gras** ; pas de titres.
"""
TAILLE_MAX_PAGE = 6000  # caractères du contexte de page joints au prompt

OUTILS = [
    {"type": "function", "function": {
        "name": "get_entreprise",
        "description": "Fiche de l'entreprise : identité, score, segment, trajectoire, contributions des signaux (points, fait_fr), enjeu, pairs, action suggérée.",
        "parameters": {"type": "object", "properties": {"mf": {"type": "string"}, "mois": {"type": "string"}}, "required": ["mf"]}}},
    {"type": "function", "function": {
        "name": "get_preuves",
        "description": "Lignes de données brutes (douane, déclarations, annexe V, ADEB) qui justifient un signal.",
        "parameters": {"type": "object", "properties": {"mf": {"type": "string"}, "signal": {"type": "string", "description": "code_signal"},
                                                        "mois": {"type": "string"}}, "required": ["mf", "signal"]}}},
    {"type": "function", "function": {
        "name": "get_reseau",
        "description": "Réseau de l'entreprise : fournisseurs, clients, acheteurs publics, relations nouvelles, coquilles.",
        "parameters": {"type": "object", "properties": {"mf": {"type": "string"}, "mois": {"type": "string"}}, "required": ["mf"]}}},
    {"type": "function", "function": {
        "name": "rediger_lettre_demande_info",
        "description": "Rédige un projet de lettre de demande d'information à partir des signaux actifs (à valider par l'inspecteur).",
        "parameters": {"type": "object", "properties": {"mf": {"type": "string"}, "mois": {"type": "string"}}, "required": ["mf"]}}},
    {"type": "function", "function": {
        "name": "get_liens_contrepartie",
        "description": "Explore le réseau d'une contrepartie de l'entreprise (fournisseur, client, acheteur public) : avec qui d'autre "
                       "elle travaille, montants, entreprises signalées et motif. Déploie ce réseau dans le graphe de l'écran.",
        "parameters": {"type": "object", "properties": {"contrepartie": {"type": "string", "description": "nom (ou identifiant) de la contrepartie"},
                                                        "mf": {"type": "string"}}, "required": ["contrepartie"]}}},
    {"type": "function", "function": {
        "name": "get_chemin_redresse",
        "description": "Plus court chemin (achats déclarés en annexes V et II, 3 relations au plus) entre l'entreprise et une entreprise "
                       "redressée pour fraude significative : étapes, montants, contrôle. Trace ce chemin dans le graphe de l'écran.",
        "parameters": {"type": "object", "properties": {"mf": {"type": "string"}}, "required": ["mf"]}}},
]

ETAPES = {  # ce que l'interface affiche pendant que le copilote travaille
    "get_entreprise": "Lecture de la fiche",
    "get_preuves": "Lecture des pièces",
    "get_reseau": "Lecture du réseau",
    "get_liens_contrepartie": "Exploration du réseau de {contrepartie}",
    "get_chemin_redresse": "Recherche d'un chemin vers une entreprise redressée",
    "rediger_lettre_demande_info": "Rédaction de la lettre",
}


class EchecLLM(Exception):
    pass


# ------------------------------------------------------------------ outils
def _alleger_entreprise(d: dict) -> dict:
    d = dict(d)
    d["trajectoire"] = d.get("trajectoire", [])[-12:]
    d["series"] = d.get("series", [])[-6:]
    return d


def executer_outil(store: BaseStore, nom: str, args: dict, mf_defaut: str, mois_defaut: str, front=None):
    mf, mois = args.get("mf") or mf_defaut, args.get("mois") or mois_defaut
    if nom in ("get_liens_contrepartie", "get_chemin_redresse"):
        if front is None:
            return {"erreur": "exploration du réseau indisponible en mode démonstration"}
        mf = mf_defaut  # le graphe affiché est celui de la fiche ouverte
        if nom == "get_liens_contrepartie":
            return liens_contrepartie(front, mf, args.get("contrepartie", ""))
        return chemin_vers_redresse(store, front, mf, mois)
    if nom == "get_entreprise":
        return _alleger_entreprise(store.entreprise(mf, mois))
    if nom == "get_preuves":
        p = dict(store.preuves(mf, args.get("signal"), mois))
        p["lignes"] = p.get("lignes", [])[:10]
        return p
    if nom == "get_reseau":
        return reseau_lisible(store, mf, mois)
    if nom == "rediger_lettre_demande_info":
        return {"lettre": modele_texte.lettre_demande_info(store.entreprise(mf, mois))["reponse"]}
    raise EchecLLM(f"outil inconnu : {nom}")


_PHRASES_RELATION = {
    "IMPORT_FOURNISSEUR": "{s} importe auprès du fournisseur étranger {c}",
    "ACHAT_LOCAL_A5": "{s} (client) déclare en annexe V avoir payé {c} (fournisseur)",
    "HONORAIRES_A2": "{s} a versé des honoraires ou loyers à {c}",
    "PAIEMENT_PUBLIC": "l'acheteur public {s} a payé {c}",
}


def reseau_lisible(store: BaseStore, mf: str, mois: str) -> dict:
    """Réseau à 1 saut, relations écrites en phrases (le sens source → cible est ambigu pour le modèle)."""
    r = store.reseau(mf, mois, 1)
    noeuds = {n["id"]: n for n in r["noeuds"]}
    nom = lambda i: noeuds.get(i, {}).get("label", i)  # noqa: E731
    relations = [{"relation": _PHRASES_RELATION.get(a["type_relation"], "{s} → {c}").format(s=nom(a["source"]), c=nom(a["cible"])),
                  "montant_total_dt": a["montant"], "depuis": a["premiere_date"], "relation_recente": a["nouvelle"]}
                 for a in sorted(r["aretes"], key=lambda a: -(a["montant"] or 0))]
    centre = noeuds.get(mf, {})
    return {"entreprise": centre.get("label", mf), "entreprise_profil_coquille": centre.get("est_coquille", False),
            "contreparties": [{"nom": n["label"], "type": n["type"], "segment": n["segment"], "profil_coquille": n["est_coquille"]}
                              for n in r["noeuds"] if n["id"] != mf],
            "relations": relations}


# ------------------------------------------------------------------ exploration du graphe (outils + actions sur le graphe de l'écran)
# Les actions `_graphe` sont calculées ici, jamais par le modèle : le graphe ne montre que des relations déclarées.
_SOURCE_RELATION = {"Import": "import déclaré en douane", "Achat · annexe V": "achat déclaré en annexe V",
                    "Vente · annexe V": "achat déclaré en annexe V", "Honoraires": "honoraires, annexe II",
                    "Honoraires reçus": "honoraires, annexe II", "Paiement public": "paiement public ADEB"}


_MOTS_CHEMIN = re.compile(r"redress|chemin|reli[ée]|cha[iî]ne|remont|source de (la )?fraude", re.IGNORECASE)
_FORMES = re.compile(r"\b(soci[ée]t[ée]|ste|sarl|suarl|sa|co|ltd|inc|gmbh|spa)\b", re.IGNORECASE)


def _normaliser(t: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", _FORMES.sub(" ", re.sub(r"[^\w\s]", " ", t.lower())))).strip()


def outils_evidents(front, mf: str, question: str) -> list[tuple[str, dict]]:
    """Outils de réseau appelés d'office quand la question les désigne sans ambiguïté (une contrepartie nommée, un lien avec
    une entreprise redressée) : le graphe réagit toujours et le modèle écrit à partir de ces données."""
    if front is None:
        return []
    q, meilleur = f" {_normaliser(question)} ", None
    for n in front._reseau(mf, max_contreparties=500)[0]:
        nom = _normaliser(n["label"])
        if len(nom) >= 5 and f" {nom} " in q and (meilleur is None or len(nom) > len(meilleur[1])):
            meilleur = (n["label"], nom)
    out = [("get_liens_contrepartie", {"contrepartie": meilleur[0]})] if meilleur else []
    if _MOTS_CHEMIN.search(question):
        out.append(("get_chemin_redresse", {}))
    return out


def _qui_paie(nom_p: str, n: dict) -> str:
    payeur, paye = (nom_p, n["label"]) if n["sens"] == "sortant" else (n["label"], nom_p)
    return f"{payeur} a payé {paye} ({_SOURCE_RELATION.get(n['relation'], n['relation'])})"


def liens_contrepartie(front, mf: str, texte: str) -> dict:
    noeuds = front._reseau(mf, max_contreparties=500)[0]
    t = (texte or "").strip().lower()
    cible = (next((n for n in noeuds if t in (n["id"].lower(), n["label"].lower())), None)
             or next((n for n in noeuds if t and (t in n["label"].lower() or n["label"].lower() in t)), None))
    if cible is None:
        return {"erreur": f"« {texte} » n'est pas une contrepartie de cette entreprise sur les 12 derniers mois",
                "contreparties_signalees": [n["label"] for n in noeuds if n["risk_flag"]][:10]}
    v = front.voisins(cible["id"], limite=8)
    autres = [{"entreprise": x["label"], "relation": _qui_paie(v["nom"], x), "montant_total_dt": round(x["montant_dt"]),
               "depuis": x["depuis"], "signalee": x["risk_flag"], "motif": x["motif"]}
              for x in v["noeuds"] if x["id"] != mf]
    deploiements = []
    if cible["id"] not in front.affiches(mf):  # contrepartie hors des 40 dessinées : on l'ajoute d'abord
        deploiements.append({"id": "__centre", "nom": front.nom(mf), "noeuds": [{**cible, "liees": []}]})
    deploiements.append({"id": cible["id"], "nom": v["nom"], "noeuds": v["noeuds"], "total": v["total"]})
    return {"contrepartie": v["nom"], "type": cible["type"], "relation_avec_l_entreprise": _qui_paie(front.nom(mf), cible),
            "montant_total_dt": round(cible["montant_dt"]), "signalee": cible["risk_flag"], "motif": cible["motif"],
            "nb_relations_de_la_contrepartie": v["total"], "principales_relations_de_la_contrepartie": autres,
            "_graphe": {"type": "deployer", "mf": mf, "cible": cible["id"], "titre": f"Réseau de {v['nom']}", "deploiements": deploiements}}


def chemin_vers_redresse(store, front, mf: str, mois: str) -> dict:
    from .explications import chemin_redresse
    ids = chemin_redresse(store, mf, mois)
    if ids is None:
        return {"resultat": "Aucune entreprise redressée pour fraude significative à 3 relations ou moins dans le graphe des achats "
                            "(annexes V et II)."}
    affiches, etapes, deploiements, noeud = front.affiches(mf), [], [], None
    for p, c in zip(ids, ids[1:]):
        noeud = front.noeud_vu_de(p, c)
        if noeud is None:
            continue
        etapes.append({"relation": _qui_paie(front.nom(p), noeud), "montant_total_dt": round(noeud["montant_dt"]), "depuis": noeud["depuis"]})
        if p != mf:
            deploiements.append({"id": p, "nom": front.nom(p), "noeuds": [noeud]})
        elif c not in affiches:
            deploiements.append({"id": "__centre", "nom": front.nom(mf), "noeuds": [noeud]})
    x = ids[-1]
    fin = f"{mois}-31"
    ctl = sorted((c for c in store.controles.get(x, []) if c["categorie_resultat"] == "FRAUDE_SIGNIFICATIVE" and str(c["date_avis"]) <= fin),
                 key=lambda c: str(c["date_avis"]))
    controle = {"date_avis": str(ctl[-1]["date_avis"])[:10], "montant_redresse_dt": round(float(ctl[-1]["montant_redresse_total"] or 0))} if ctl else {}
    noms = [front.nom(i) for i in ids]
    if noeud is not None and deploiements and deploiements[-1]["noeuds"][0]["id"] == x:
        titre = "Redressée pour fraude significative"
        if controle:
            a, m, j = controle["date_avis"].split("-")
            titre += f" (avis du {j}/{m}/{a})"
        details = [f"Chemin tracé par le copilote : {' → '.join(noms)}"]
        if controle:
            details.insert(0, f"Montant redressé : {config.fmt_dt(controle['montant_redresse_dt'])}")
        deploiements[-1]["noeuds"][0].update({"motif": titre, "risk_flag": True, "motif_detail": {"titre": titre, "details": details}})
    return {"entreprise_redressee": front.nom(x), "distance_en_relations": len(ids) - 1, "chemin": noms, "etapes": etapes,
            "controle": controle,
            "_graphe": {"type": "chemin", "mf": mf, "cible": x, "ids": ids, "titre": f"Chemin vers {front.nom(x)}", "deploiements": deploiements}}


# ------------------------------------------------------------------ garde-fou sur les nombres
_NOMBRE = re.compile(r"(?<![\w])[-+]?\d[\d   ]*(?:[.,]\d+)?")


def _valeurs(texte: str) -> list[float]:
    out = []
    for m in _NOMBRE.findall(texte):
        s = m.replace(" ", "").replace(" ", "").replace(" ", "").replace(",", ".")
        try:
            out.append(float(s))
        except ValueError:
            pass
    return out


def nombres_non_fondes(reponse: str, contexte: str) -> list[float]:
    """Nombres de la réponse absents du contexte (tolérance d'arrondi, %, milliers, millions)."""
    ctx = set()
    for v in _valeurs(contexte):
        for x in (v, v * 100, v / 1000, v / 1_000_000):
            ctx.add(x)
    ctx_l = list(ctx)
    suspects = []
    for v in _valeurs(reponse):
        if abs(v) <= 12 or 2000 <= v <= 2100:  # énumérations, « 3 raisons », années
            continue
        if not any(abs(v - c) <= max(0.051, abs(c) * 0.01) for c in ctx_l):
            suspects.append(v)
    return suspects


def _extraire_sources(texte: str) -> tuple[str, list[dict]]:
    m = re.search(r"\n?\s*\**SOURCES\**\s*:\s*(.*)$", texte, flags=re.IGNORECASE | re.DOTALL)
    if not m:
        return texte.strip(), []
    corps, brut = texte[:m.start()].strip(), m.group(1)
    citations = []
    for ref in re.split(r"[,;\n]", brut):
        ref = ref.strip().strip("`*.- ")
        if not ref:
            continue
        if ref in config.LENTILLES:
            citations.append({"type": "signal", "ref": ref})
        elif ":" in ref:
            citations.append({"type": "preuve", "ref": ref})
    return corps, citations


def _sans_reflexion(texte: str) -> str:
    return re.sub(r"<think>.*?</think>", "", texte or "", flags=re.DOTALL).strip()


# ------------------------------------------------------------------ appel LLM
def _client(restant: float):
    from openai import OpenAI
    return OpenAI(base_url=config.LLM_BASE_URL, api_key=config.LLM_API_KEY, timeout=max(1.0, restant), max_retries=0)


def _texte_page(page: dict | None) -> str:
    """Ce que l'inspecteur voit à l'écran (filtres, période, indicateurs), tronqué."""
    if not page:
        return ""
    return json.dumps(page, ensure_ascii=False, default=str)[:TAILLE_MAX_PAGE]


def _messages_initiaux(mf: str, mois: str, question: str, historique: list[dict], page: dict | None = None) -> list[dict]:
    systeme = PROMPT_SYSTEME + f"\nEntreprise concernée : mf={mf}, mois={mois}."
    if page:
        systeme += "\n\nCe que l'inspecteur voit à l'écran (JSON, période et filtres qu'il a choisis) :\n" + _texte_page(page)
    msgs = [{"role": "system", "content": systeme}]
    for h in (historique or [])[-6:]:
        role = "assistant" if h.get("role") == "assistant" else "user"
        msgs.append({"role": role, "content": h.get("contenu", "")})
    msgs.append({"role": "user", "content": question})
    return msgs


def _sans_evenement(_type: str, _donnees: dict) -> None:
    pass


def repondre_llm(store: BaseStore, mf: str, mois: str, question: str, historique: list[dict], page: dict | None = None,
                 front=None, evenement=_sans_evenement, actions: list | None = None) -> dict:
    if not config.LLM_BASE_URL:
        raise EchecLLM("LLM_BASE_URL non défini")
    fin = time.monotonic() + config.LLM_TIMEOUT
    msgs = _messages_initiaux(mf, mois, question, historique, page)
    contexte: list[str] = [_texte_page(page)]  # les nombres affichés à l'écran sont aussi des données fondées
    citations_outils: list[dict] = []
    actions = [] if actions is None else actions

    final = None
    if config.LLM_TOOLS:
        try:
            final = _boucle_outils(store, mf, mois, msgs, fin, contexte, citations_outils, front, evenement, actions)
        except BadRequestError as e:  # serveur sans tool-calling (llama-server sans --jinja) → plan B
            log.warning("assistant : outils refusés par le serveur, plan B (%s)", e)
            msgs, contexte[:], citations_outils[:] = _messages_initiaux(mf, mois, question, historique, page), [_texte_page(page)], []
    if final is None:  # plan B : tout le contexte dans le prompt, sans outils
        d = store.entreprise(mf, mois)
        ctx = {"entreprise": _alleger_entreprise(d)}
        top = sorted(d.get("contributions") or [], key=lambda c: -c["points"])
        if top:
            ctx["preuves_signal_principal"] = executer_outil(store, "get_preuves", {"signal": top[0]["code_signal"]}, mf, mois)
        texte = json.dumps(ctx, ensure_ascii=False)
        contexte.append(texte)
        # Qwen n'accepte qu'un seul message système, en tête : on y ajoute les données
        msgs[0] = {"role": "system", "content": msgs[0]["content"] + "\n\nDonnées disponibles (JSON) :\n" + texte}
        final = _sans_reflexion(_appel(msgs, fin).choices[0].message.content)

    if time.monotonic() > fin:
        raise EchecLLM("délai dépassé")
    corps, citations = _extraire_sources(final)
    if not corps:
        raise EchecLLM("réponse vide")
    suspects = nombres_non_fondes(corps, "\n".join(contexte))
    if suspects:
        raise EchecLLM(f"nombres non fondés : {suspects[:5]}")
    vus, uniques = set(), []
    donnees = "\n".join(contexte)
    for c in citations + citations_outils:
        # une source citée doit apparaître dans les données consultées (le modèle recopie parfois un exemple)
        if c["type"] != "source" and c.get("ref") and c["ref"] not in donnees:
            continue
        if c.get("ref") and (c["type"], c["ref"]) not in vus:
            vus.add((c["type"], c["ref"]))
            uniques.append(c)
    return {"reponse": corps, "citations": uniques, "mode": "llm", "graphe": actions}


def _appel(msgs: list[dict], fin: float, tools: list | None = None):
    restant = fin - time.monotonic()
    if restant <= 0.5:
        raise EchecLLM("délai dépassé")
    kwargs = {"tools": tools} if tools else {}
    # Qwen 3.5 : pas de phase de réflexion (latence), comme dans le test curl de l'équipe
    extra = {} if config.LLM_THINKING else {"chat_template_kwargs": {"enable_thinking": False}}
    return _client(restant).chat.completions.create(model=config.LLM_MODEL, messages=msgs, temperature=0.1,
                                                    max_tokens=config.LLM_MAX_TOKENS, extra_body=extra, **kwargs)


def _boucle_outils(store: BaseStore, mf: str, mois: str, msgs: list[dict], fin: float, contexte: list[str],
                   citations_outils: list[dict], front=None, evenement=_sans_evenement, actions: list | None = None) -> str | None:
    """Réponse finale, ou None si le modèle répond sans appeler d'outil (→ plan B).
    `evenement(type, données)` : étapes et actions sur le graphe, envoyées à l'interface au fil de l'eau."""
    actions = [] if actions is None else actions

    def executer(ident: str, nom: str, arguments: str) -> None:
        try:
            args = json.loads(arguments or "{}")
            gabarit = ETAPES.get(nom, nom)
            evenement("etape", {"outil": nom, "texte": gabarit.format(contrepartie=args.get("contrepartie", "la contrepartie"))})
            res = executer_outil(store, nom, args, mf, mois, front)
            action = res.pop("_graphe", None) if isinstance(res, dict) else None
            if nom == "get_reseau" and front is not None:
                action = {"type": "afficher", "mf": mf}
            if action:
                actions.append(action)
                evenement("graphe", action)
            if nom == "get_preuves":
                citations_outils.append({"type": "signal", "ref": res.get("code_signal")})
            elif nom in ("get_reseau", "get_liens_contrepartie", "get_chemin_redresse"):
                citations_outils.append({"type": "source", "ref": "réseau (annexe V, douane, ADEB)"})
        except (Introuvable, EchecLLM, KeyError, json.JSONDecodeError) as e:
            res = {"erreur": str(e)}
        texte = json.dumps(res, ensure_ascii=False)
        contexte.append(texte)
        msgs.append({"role": "tool", "tool_call_id": ident, "content": texte})

    # outils désignés sans ambiguïté par la question : exécutés d'office, comme si le modèle les avait appelés
    evidents = [(f"auto{i}", nom, json.dumps(args, ensure_ascii=False)) for i, (nom, args) in enumerate(outils_evidents(front, mf, msgs[-1]["content"]))]
    if evidents:
        msgs.append({"role": "assistant", "content": "",
                     "tool_calls": [{"id": i, "type": "function", "function": {"name": n, "arguments": a}} for i, n, a in evidents]})
        for i, n, a in evidents:
            executer(i, n, a)

    for _ in range(5):
        msg = _appel(msgs, fin, OUTILS).choices[0].message
        if not msg.tool_calls:  # sans outil : acceptable seulement s'il y a des données (écran ou outils)
            return _sans_reflexion(msg.content) if any(contexte) else None
        msgs.append({"role": "assistant", "content": msg.content or "",
                     "tool_calls": [{"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                                    for tc in msg.tool_calls]})
        for tc in msg.tool_calls:
            executer(tc.id, tc.function.name, tc.function.arguments)
    raise EchecLLM("trop d'appels d'outils")


def repondre_modele_texte(store: BaseStore, mf: str, mois: str, question: str) -> dict:
    detail = store.entreprise(mf, mois)
    top = sorted(detail.get("contributions") or [], key=lambda c: -c["points"])
    preuves_top = None
    if top:
        try:
            preuves_top = store.preuves(mf, top[0]["code_signal"], mois)
        except Introuvable:
            pass
    reseau = None
    if modele_texte.intention(question) == "reseau":
        try:
            reseau = store.reseau(mf, mois, 1)
        except Introuvable:
            pass
    return modele_texte.repondre(question, detail, preuves_top, reseau)


def _raison(e: Exception) -> str:
    """Motif de repli lisible par l'inspecteur (affiché dans l'interface)."""
    nom = type(e).__name__
    if isinstance(e, EchecLLM):
        return str(e)
    if "Timeout" in nom:
        return "délai dépassé"
    if "Connection" in nom:
        return "LLM injoignable"
    return f"erreur du LLM ({nom})"


def repondre(store: BaseStore, mf: str | None, mois: str, question: str, historique: list[dict] | None = None,
             page: dict | None = None, front=None, evenement=_sans_evenement) -> dict:
    """`front` (FrontStore, mode réel) : active l'exploration du graphe ; `evenement` : suivi en direct (route /flux)."""
    if not mf:
        return repondre_liste(store, mois, question, historique or [], page)
    store.entreprise(mf, mois)  # lève Introuvable si l'entreprise n'existe pas
    t0 = time.monotonic()
    actions: list = []
    try:
        r = repondre_llm(store, mf, mois, question, historique or [], page, front, evenement, actions)
        log.info("assistant : réponse LLM en %.1f s", time.monotonic() - t0)
        return r
    except Exception as e:  # repli systématique ; les actions déjà montrées sur le graphe restent valables (données réelles)
        log.warning("assistant : repli modele_texte après %.1f s (%s)", time.monotonic() - t0, e)
        return {**repondre_modele_texte(store, mf, mois, question), "raison_repli": _raison(e), "graphe": actions}


# ------------------------------------------------------------------ liste des entreprises (pas d'entreprise précise)
def repondre_liste(store: BaseStore, mois: str, question: str, historique: list[dict], page: dict | None) -> dict:
    donnees = {"ecran": page or {}, "portefeuille": store.synthese(mois)}
    texte = json.dumps(donnees, ensure_ascii=False, default=str)[:TAILLE_MAX_PAGE + 2000]
    t0 = time.monotonic()
    try:
        if not config.LLM_BASE_URL:
            raise EchecLLM("LLM_BASE_URL non défini")
        fin = time.monotonic() + config.LLM_TIMEOUT
        msgs = [{"role": "system", "content": PROMPT_LISTE + "\nDonnées (JSON) :\n" + texte}]
        for h in historique[-6:]:
            msgs.append({"role": "assistant" if h.get("role") == "assistant" else "user", "content": h.get("contenu", "")})
        msgs.append({"role": "user", "content": question})
        corps, _ = _extraire_sources(_sans_reflexion(_appel(msgs, fin).choices[0].message.content))
        if not corps:
            raise EchecLLM("réponse vide")
        suspects = nombres_non_fondes(corps, texte)
        if suspects:
            raise EchecLLM(f"nombres non fondés : {suspects[:5]}")
        log.info("assistant (liste) : réponse LLM en %.1f s", time.monotonic() - t0)
        return {"reponse": corps, "citations": [], "mode": "llm"}
    except Exception as e:
        log.warning("assistant (liste) : repli après %.1f s (%s)", time.monotonic() - t0, e)
        return {**modele_texte.resumer_liste(page or {}, donnees["portefeuille"]), "raison_repli": _raison(e)}

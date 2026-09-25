"""Assistant de l'inspecteur : un appel LLM (Qwen local, API compatible OpenAI) avec quelques outils.

- Répond uniquement à partir des outils ; cite ses sources ; ne décide jamais.
- Garde-fou : tout nombre de la réponse doit se retrouver dans les données renvoyées par les outils.
- Tout échec (URL absente, erreur, > LLM_TIMEOUT s, garde-fou) → repli modele_texte.
"""

import json
import logging
import re
import time

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
5. Termine ta réponse par une ligne « SOURCES : » suivie des codes de signaux (ex. COH_IMPORT_VS_CA) et des références de
   preuves (ex. douane_articles:2026/401/0034567-001) que tu as utilisés, séparés par des virgules.
"""

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
]


class EchecLLM(Exception):
    pass


# ------------------------------------------------------------------ outils
def _alleger_entreprise(d: dict) -> dict:
    d = dict(d)
    d["trajectoire"] = d.get("trajectoire", [])[-12:]
    d["series"] = d.get("series", [])[-6:]
    return d


def executer_outil(store: BaseStore, nom: str, args: dict, mf_defaut: str, mois_defaut: str):
    mf, mois = args.get("mf") or mf_defaut, args.get("mois") or mois_defaut
    if nom == "get_entreprise":
        return _alleger_entreprise(store.entreprise(mf, mois))
    if nom == "get_preuves":
        p = dict(store.preuves(mf, args.get("signal"), mois))
        p["lignes"] = p.get("lignes", [])[:10]
        return p
    if nom == "get_reseau":
        return store.reseau(mf, mois, 1)
    if nom == "rediger_lettre_demande_info":
        return {"lettre": modele_texte.lettre_demande_info(store.entreprise(mf, mois))["reponse"]}
    raise EchecLLM(f"outil inconnu : {nom}")


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


def _messages_initiaux(mf: str, mois: str, question: str, historique: list[dict]) -> list[dict]:
    msgs = [{"role": "system", "content": PROMPT_SYSTEME + f"\nEntreprise concernée : mf={mf}, mois={mois}."}]
    for h in (historique or [])[-6:]:
        role = "assistant" if h.get("role") == "assistant" else "user"
        msgs.append({"role": role, "content": h.get("contenu", "")})
    msgs.append({"role": "user", "content": question})
    return msgs


def repondre_llm(store: BaseStore, mf: str, mois: str, question: str, historique: list[dict]) -> dict:
    if not config.LLM_BASE_URL:
        raise EchecLLM("LLM_BASE_URL non défini")
    fin = time.monotonic() + config.LLM_TIMEOUT
    msgs = _messages_initiaux(mf, mois, question, historique)
    contexte: list[str] = []
    citations_outils: list[dict] = []

    if not config.LLM_TOOLS:  # plan B : tout le contexte dans le prompt, sans outils
        d = store.entreprise(mf, mois)
        ctx = {"entreprise": _alleger_entreprise(d)}
        top = sorted(d.get("contributions") or [], key=lambda c: -c["points"])
        if top:
            ctx["preuves_signal_principal"] = executer_outil(store, "get_preuves", {"signal": top[0]["code_signal"]}, mf, mois)
        texte = json.dumps(ctx, ensure_ascii=False)
        contexte.append(texte)
        msgs.insert(1, {"role": "system", "content": "Données disponibles (JSON) :\n" + texte})
        rep = _client(fin - time.monotonic()).chat.completions.create(model=config.LLM_MODEL, messages=msgs, temperature=0.1)
        final = _sans_reflexion(rep.choices[0].message.content)
    else:
        final = None
        for _ in range(5):
            restant = fin - time.monotonic()
            if restant <= 0.5:
                raise EchecLLM("délai dépassé")
            rep = _client(restant).chat.completions.create(model=config.LLM_MODEL, messages=msgs, tools=OUTILS, temperature=0.1)
            msg = rep.choices[0].message
            if not msg.tool_calls:
                final = _sans_reflexion(msg.content)
                break
            msgs.append({"role": "assistant", "content": msg.content or "",
                         "tool_calls": [{"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                                        for tc in msg.tool_calls]})
            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments or "{}")
                    res = executer_outil(store, tc.function.name, args, mf, mois)
                    if tc.function.name == "get_preuves":
                        citations_outils.append({"type": "signal", "ref": res.get("code_signal")})
                except (Introuvable, EchecLLM, json.JSONDecodeError) as e:
                    res = {"erreur": str(e)}
                texte = json.dumps(res, ensure_ascii=False)
                contexte.append(texte)
                msgs.append({"role": "tool", "tool_call_id": tc.id, "content": texte})
        if final is None:
            raise EchecLLM("trop d'appels d'outils")
        if not contexte:
            raise EchecLLM("réponse sans appel d'outil")

    if time.monotonic() > fin:
        raise EchecLLM("délai dépassé")
    corps, citations = _extraire_sources(final)
    if not corps:
        raise EchecLLM("réponse vide")
    suspects = nombres_non_fondes(corps, "\n".join(contexte))
    if suspects:
        raise EchecLLM(f"nombres non fondés : {suspects[:5]}")
    vus, uniques = set(), []
    for c in citations + citations_outils:
        if c.get("ref") and (c["type"], c["ref"]) not in vus:
            vus.add((c["type"], c["ref"]))
            uniques.append(c)
    return {"reponse": corps, "citations": uniques, "mode": "llm"}


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


def repondre(store: BaseStore, mf: str, mois: str, question: str, historique: list[dict] | None = None) -> dict:
    store.entreprise(mf, mois)  # lève Introuvable si l'entreprise n'existe pas
    try:
        return repondre_llm(store, mf, mois, question, historique or [])
    except Exception as e:  # repli systématique
        log.warning("assistant : repli modele_texte (%s)", e)
        return repondre_modele_texte(store, mf, mois, question)

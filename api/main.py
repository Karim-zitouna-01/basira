"""API Basira (C → D) — contrat d'intégration §6.

Lancement : uv run uvicorn api.main:app --host 0.0.0.0 --port 8000
Mode : BASIRA_MODE=mock | real | auto (défaut : real si data/scores/scores.parquet existe).
L'API ne recalcule rien : elle lit les fichiers au démarrage et les garde en mémoire.
"""

import logging
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from pydantic import BaseModel, Field

from scoring import config

from . import assistant
from .front import FrontStore
from .store import Introuvable, creer_store

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Basira API", version="1.0", description="Score de risque de conformité dynamique et explicable")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1|192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+)(:\d+)?",
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(GZipMiddleware, minimum_size=2000)  # le portefeuille de l'interface pèse ~3 Mo en JSON

store = creer_store()
front = FrontStore(store) if store.mode == "real" else None  # formes de données de l'interface de D (web/)


def _introuvable(e: Introuvable):
    raise HTTPException(status_code=404, detail=f"introuvable : {e}")


class DecisionRequete(BaseModel):
    mois: str = config.MOIS_COURANT
    decision: Literal["AUCUNE", "RELANCE", "DEMANDE_INFO", "VERIFICATION", "SIGNALEMENT_DOUANE"]
    justification: str = Field(min_length=1)
    inspecteur: str = "demo"


class Message(BaseModel):
    role: str
    contenu: str


class AssistantRequete(BaseModel):
    mf: str
    mois: str = config.MOIS_COURANT
    question: str = Field(min_length=1)
    historique: list[Message] = []


@app.get("/api/sante")
def sante():
    return {"mode": store.mode, "llm_configure": bool(config.LLM_BASE_URL), "llm_modele": config.LLM_MODEL,
            "mois_courant": config.MOIS_COURANT}


@app.get("/api/stats/synthese")
def stats_synthese(mois: str = config.MOIS_COURANT):
    return store.synthese(mois)


@app.get("/api/entreprises")
def entreprises(mois: str = config.MOIS_COURANT, segment: str | None = None, code_nat: str | None = None,
                gouvernorat: str | None = None, tri: str = "priorite", page: int = Query(1, ge=1),
                taille: int = Query(50, ge=1, le=500)):
    return store.liste(mois, segment, code_nat, gouvernorat, tri, page, taille)


@app.get("/api/entreprises/{mf}")
def entreprise(mf: str, mois: str = config.MOIS_COURANT):
    try:
        return store.entreprise_avec_decisions(mf, mois)
    except Introuvable as e:
        _introuvable(e)


@app.get("/api/entreprises/{mf}/preuves")
def preuves(mf: str, signal: str | None = None, mois: str = config.MOIS_COURANT):
    try:
        return store.preuves(mf, signal, mois)
    except Introuvable as e:
        _introuvable(e)


@app.get("/api/entreprises/{mf}/reseau")
def reseau(mf: str, mois: str = config.MOIS_COURANT, profondeur: int = Query(2, ge=1, le=3)):
    try:
        return store.reseau(mf, mois, profondeur)
    except Introuvable as e:
        _introuvable(e)


@app.post("/api/entreprises/{mf}/decision")
def decision(mf: str, req: DecisionRequete):
    try:
        d = store.entreprise(mf, req.mois)
    except Introuvable as e:
        _introuvable(e)
    ligne = store.decisions.ajouter(mf, req.mois, req.decision, req.justification.strip(), req.inspecteur,
                                    d.get("score"), d.get("segment"))
    return {"id_decision": ligne["id_decision"], "enregistre": True, "date_heure": ligne["date_heure"]}


@app.post("/api/assistant")
def assistant_route(req: AssistantRequete):
    try:
        return assistant.repondre(store, req.mf, req.mois, req.question, [m.model_dump() for m in req.historique])
    except Introuvable as e:
        _introuvable(e)


@app.get("/api/evaluation")
def evaluation():
    try:
        return store.evaluation()
    except Introuvable as e:
        _introuvable(e)


# ------------------------------------------------------------------ interface de D (web/) : ses propres formes de données
def _front() -> FrontStore:
    if front is None:
        raise HTTPException(status_code=503, detail="mode mock : l'interface utilise son jeu fictif (VITE_API_URL vide)")
    return front


@app.get("/api/front/portefeuille")
def front_portefeuille():
    return _front().portefeuille()


@app.get("/api/front/entreprises/{mf}")
def front_fiche(mf: str):
    try:
        return _front().fiche(mf)
    except (KeyError, Introuvable) as e:
        _introuvable(e)

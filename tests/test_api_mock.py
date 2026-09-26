"""Toutes les routes du contrat §6.2 en mode mock : mêmes clés que les exemples du contrat."""

import pytest
from fastapi.testclient import TestClient

from api.main import app
from scoring.config import HEROS

c = TestClient(app)
ALPHA = "1000001BAM000"

CLES_ITEM = {"mf", "raison_sociale", "code_nat", "libelle_nat", "gouvernorat", "score", "score_mois_precedent", "delta_score",
             "segment", "enjeu_estime", "enjeu_bas", "enjeu_haut", "rang_priorite", "resume_fr", "action_suggeree", "derniere_decision"}
CLES_DETAIL = {"identite", "score", "segment", "confiance", "enjeu", "action_suggeree", "resume_fr", "trajectoire", "contributions",
               "pairs", "series", "decisions", "controles_passes"}
CLES_CONTRIB = {"code_signal", "lentille", "points", "valeur_norm", "fait_fr", "sources", "nb_preuves"}


def test_synthese():
    r = c.get("/api/stats/synthese", params={"mois": "2026-08"}).json()
    assert set(r) == {"mois", "nb_entreprises", "par_segment", "nouveaux_prioritaires_du_mois", "enjeu_total_prioritaires", "seuils"}
    assert set(r["par_segment"]) == {"PRIORITAIRE", "SURVEILLANCE", "NORMAL", "CONFIANCE"}


def test_liste_et_filtres():
    r = c.get("/api/entreprises").json()
    assert set(r) == {"total", "page", "taille", "items"}
    assert r["total"] == 8
    assert set(r["items"][0]) == CLES_ITEM
    assert r["items"][0]["mf"] == ALPHA and r["items"][0]["rang_priorite"] == 1
    assert sorted(i["rang_priorite"] for i in r["items"]) == list(range(1, 9))
    f = c.get("/api/entreprises", params={"segment": "PRIORITAIRE", "code_nat": "46", "gouvernorat": "34"}).json()
    assert [i["mf"] for i in f["items"]] == [ALPHA]
    s = c.get("/api/entreprises", params={"tri": "score"}).json()["items"]
    assert [i["score"] for i in s] == sorted((i["score"] for i in s), reverse=True)


@pytest.mark.parametrize("mf", list(HEROS))
def test_detail_heros(mf):
    d = c.get(f"/api/entreprises/{mf}").json()
    assert set(d) == CLES_DETAIL
    assert len(d["trajectoire"]) == 24 and len(d["series"]) == 24
    for k in d["contributions"]:
        assert set(k) == CLES_CONTRIB
        p = c.get(f"/api/entreprises/{mf}/preuves", params={"signal": k["code_signal"]}).json()
        assert set(p) == {"code_signal", "fait_fr", "lignes"} and len(p["lignes"]) == k["nb_preuves"]
    rs = c.get(f"/api/entreprises/{mf}/reseau").json()
    assert set(rs) == {"noeuds", "aretes"} and any(n["centre"] for n in rs["noeuds"])


def test_segments_heros():
    seg = {mf: c.get(f"/api/entreprises/{mf}").json()["segment"] for mf in HEROS}
    assert seg[ALPHA] == "PRIORITAIRE"
    assert seg["1000006GAM000"] == "NORMAL"
    assert seg["1000007HAM000"] == "CONFIANCE"
    assert c.get("/api/entreprises/1000002CAM000").json()["action_suggeree"] == "SIGNALEMENT_DOUANE"


def test_trajectoire_alpha():
    t = {p["mois"]: p["score"] for p in c.get(f"/api/entreprises/{ALPHA}").json()["trajectoire"]}
    assert (t["2026-06"], t["2026-07"], t["2026-08"]) == (28.0, 52.0, 76.0)


def test_decision_aller_retour():
    r = c.post(f"/api/entreprises/{ALPHA}/decision",
               json={"mois": "2026-08", "decision": "VERIFICATION", "justification": "Écart confirmé.", "inspecteur": "demo"}).json()
    assert r["enregistre"] is True and r["id_decision"].startswith("DEC-")
    d = c.get(f"/api/entreprises/{ALPHA}").json()["decisions"]
    assert d[-1]["decision"] == "VERIFICATION" and d[-1]["segment_au_moment"] == "PRIORITAIRE"
    assert c.get("/api/entreprises").json()["items"][0]["derniere_decision"]["decision"] == "VERIFICATION"
    assert c.post(f"/api/entreprises/{ALPHA}/decision", json={"decision": "VERIFICATION", "justification": ""}).status_code == 422
    assert c.post(f"/api/entreprises/{ALPHA}/decision", json={"decision": "PRISON", "justification": "x"}).status_code == 422


@pytest.mark.parametrize("question", ["Pourquoi le risque d'Alpha a-t-il augmenté ?", "Rédige la demande d'information",
                                      "Quels fournisseurs posent problème ?"])
def test_assistant_modele_texte(question):
    r = c.post("/api/assistant", json={"mf": ALPHA, "mois": "2026-08", "question": question, "historique": []}).json()
    assert set(r) == {"reponse", "citations", "mode", "raison_repli"}  # raison_repli : ajout au contrat (motif du repli)
    assert r["mode"] == "modele_texte" and r["reponse"] and r["citations"]
    assert r["raison_repli"] == "LLM_BASE_URL non défini"


def test_assistant_liste_sans_llm():
    r = c.post("/api/assistant", json={"question": "Quels dossiers ouvrir en premier ?",
                                       "contexte": {"page": "liste", "nb_affichees": 1, "entreprises_affichees": [
                                           {"nom": "Alpha SARL", "score": 76, "delta": "+48", "statut": "Haut Risque", "ecart_dt": 420000,
                                            "action": "Vérification approfondie"}]}}).json()
    assert r["mode"] == "modele_texte" and "Alpha SARL" in r["reponse"]


def test_assistant_pourquoi_alpha():
    r = c.post("/api/assistant", json={"mf": ALPHA, "question": "Pourquoi le risque d'Alpha a-t-il augmenté ?"}).json()
    assert "passé de 28 à 76" in r["reponse"]
    assert {"type": "preuve", "ref": "douane_articles:2026/401/0034567-001"} in r["citations"]


def test_evaluation():
    r = c.get("/api/evaluation").json()
    assert set(r) == {"top_n", "periode_test", "methodes", "note"} and len(r["methodes"]) == 3


def test_404():
    assert c.get("/api/entreprises/0000000XXX000").status_code == 404
    assert c.post("/api/assistant", json={"mf": "0000000XXX000", "question": "?"}).status_code == 404

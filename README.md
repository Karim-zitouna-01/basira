# Basira — lot C : score appris, évaluation, API, assistant

Contrat d'intégration : `idea/contrat_integration.md` (source unique de vérité). Ce dépôt contient `scoring/` et `api/`.

## Installation (WSL / Linux, avec uv)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh   # si uv n'est pas installé
uv sync                                            # crée .venv et installe les dépendances
```

## Commandes

| Quoi | Commande |
|---|---|
| Régénérer les mocks du contrat (`data/mock/`) | `uv run python -m api.mocks` |
| API sur les mocks (pour D, dès 17h) | `BASIRA_MODE=mock uv run uvicorn api.main:app --host 0.0.0.0 --port 8000` |
| Scoring + évaluation sur les données de A/B (`data/`) | `uv run python -m scoring.run` |
| API sur les vraies données | `BASIRA_MODE=real uv run uvicorn api.main:app --host 0.0.0.0 --port 8000` |
| Données de dev de C (`data/dev/`, avant les livraisons A/B) | `uv run python -m scoring.dev_fixtures` puis `BASIRA_DATA_DIR=data/dev uv run python -m scoring.run` |
| Démo boucle d'apprentissage (avant/après) | `uv run python -m scoring.boucle [--demo]` |
| Tests | `uv run pytest -q` |

Pipeline complet (contrat §2) : `python -m generation.run && python -m signaux.run && uv run python -m scoring.run && uv run uvicorn api.main:app`.

## Variables d'environnement

| Variable | Défaut | Rôle |
|---|---|---|
| `BASIRA_DATA_DIR` | `data` | dossier des données (`raw/`, `graphe/`, `signaux/`, `scores/`) |
| `BASIRA_MODE` | `auto` | `mock`, `real`, ou `auto` (real si `scores/scores.parquet` existe) |
| `LLM_BASE_URL` | vide | URL OpenAI-compatible du Qwen distant, ex. `http://192.168.1.20:11434/v1` (Ollama). Vide → mode `modele_texte` |
| `LLM_MODEL` | `qwen3.5:9b` | nom du modèle côté serveur |
| `LLM_TOOLS` | `1` | `0` = plan B : contexte JSON injecté dans le prompt, sans tool-calling |
| `LLM_TIMEOUT` | `20` | budget en secondes ; au-delà → repli `modele_texte` |

## Entrées / sorties

- Lit : `data/signaux/{signaux,enjeux,groupes_pairs,pairs_stats}.parquet` (B), `data/raw/*.csv` et `data/graphe/aretes.csv` (A).
  `data/raw/verite_terrain.csv` n'est lu **que** par `scoring/evaluate.py`.
- Écrit : `data/scores/{scores.parquet, modele.json, evaluation.json, decisions.csv, simulation_boucle.json}`.

## Méthode (résumé pour la note de synthèse)

1. **Apprentissage** (`scoring/train.py`) : un exemple par contrôle passé ; caractéristiques = `valeur_norm` des 16 signaux au mois
   précédant l'avis + 2 combinaisons ; cible = redressement (mineur ou fraude significative, poids 2). Régression logistique L2,
   classes équilibrées, **poids ≥ 0** (signaux à coefficient négatif retirés puis réentraînement, listés dans `modele.json`).
2. **Calibrage** : les petits redressements (≈ 1/3 des entreprises normales) placent l'intercept appris vers 35/100. On garde les
   poids relatifs appris et on fixe l'échelle par deux ancres, calculées sur les seuls contrôles passés : entreprise sans signal = 5,
   profil médian des fraudes significatives confirmées = 70. Détail dans `modele.json` → `calibrage`.
3. **Score** (`scoring/score.py`) : `100·σ(b0 + Σ wᵢxᵢ)` + bonus « nouveau schéma » (0–15) ; points par signal dont la somme
   = score − score de base ; segments, priorité = score × enjeu, action suggérée (contrat §6.3), résumé en français.
4. **Évaluation** (`scoring/evaluate.py`) : top 50 par mois sur les 12 derniers mois, Basira vs règle statique type SAR vs hasard.
5. **Assistant** (`api/assistant.py`) : un appel LLM avec 4 outils ; toute valeur chiffrée de la réponse doit figurer dans les données
   des outils, sinon repli déterministe (`api/modele_texte.py`). L'assistant ne décide jamais.

## Bibliothèques et modèles utilisés (lot C)

Python 3.13, uv · pandas, numpy, pyarrow · scikit-learn (LogisticRegression) · FastAPI, Uvicorn, Pydantic ·
client `openai` (API compatible OpenAI) · **Qwen 3.5 9B** (modèle pré-entraîné, servi en local sur une autre machine,
p. ex. via Ollama) · pytest, httpx.

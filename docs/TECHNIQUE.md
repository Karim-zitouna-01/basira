# Basira — guide technique (installation, commandes, variables, méthode détaillée)

Score de risque de conformité dynamique et explicable. Contrat d'intégration : `docs/specifications/contrat_integration.md`.

| Lot | Dossier | Rôle | Documentation |
|---|---|---|---|
| A | `generation/`, `tools/lan_forward.py` | monde synthétique (`data/raw`, `data/graphe`) | `docs/lot_A/README.md` |
| B | `signaux/`, `scripts/benchmark.sh` | 16 signaux, preuves, enjeux, pairs (`data/signaux`), note de synthèse PDF | `docs/lot_B/` |
| C | `scoring/`, `api/` | score appris, enjeu complété, évaluation, API, assistant (`data/scores`) | ce fichier |
| D | `web/` | interface de l'inspecteur (Vite + React, DC.js/Crossfilter, D3) | ci-dessous |

## Installation (WSL / Linux, avec uv)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh   # si uv n'est pas installé
uv sync                                            # crée .venv et installe les dépendances (Python 3.13)
```

## Pipeline complet (≈ 5 min)

```bash
uv run python -m generation.run --n 5250 --seed 2026   # A : ~1 min, 84 contrôles de cohérence
uv run python -m signaux.run --data-dir data          # B : ~250 s, 2 016 000 lignes
uv run python -m signaux.checks --data-dir data       # B : contrôle des héros → data/signaux/controle_heros.md
uv run python -m scoring.run                          # C : ~7 s, modèle, enjeux, scores, héros, évaluation
```

## Lancer la démo (API + interface)

```bash
bash scripts/demo.sh                                             # sans LLM (réponses de repli)
LLM_BASE_URL=http://192.168.137.222:8200/v1 bash scripts/demo.sh   # avec le Qwen distant (point d'accès)
```

Interface : http://localhost:5173 (depuis Windows aussi) · API : http://localhost:8000/docs. Ctrl+C arrête les deux.
Node 22 est installé dans `~/.local/node` (sans sudo) ; `scripts/demo.sh` lance `npm ci` si `web/node_modules` manque.

### Interface (`web/`)

- `web/.env` : `VITE_API_URL=http://localhost:8000`. Vide → jeu fictif de D (`web/src/data/mockData.json`), sans API.
- L'interface garde ses propres formes de données ; l'API les sert via `api/front.py` :
  `GET /api/front/portefeuille` (5 250 entreprises + 12 mois compacts, ~3 Mo gzip) et `GET /api/front/entreprises/{mf}`
  (historique, opérations douane/ADEB/annexe V, réseau, contrôles + fiche du contrat §6 dans `detail`).
- Ajouts à l'interface de D : panneau « Pourquoi ce score ? » (contributions en points, phrase, preuves brutes, pairs) et
  décision de l'inspecteur (`components/PourquoiScore.jsx`) ; copilote de la liste et de la fiche branché sur `POST /api/assistant` ; table paginée (25/50/100) ; « écart de recoupement » = enjeu estimé.

## Lancer l'API seule

```bash
# sans LLM (réponses modele_texte) :
BASIRA_MODE=real uv run uvicorn api.main:app --host 0.0.0.0 --port 8000
# avec le Qwen distant (via le point d'accès) :
LLM_BASE_URL=http://192.168.137.222:8200/v1 BASIRA_MODE=real uv run uvicorn api.main:app --host 0.0.0.0 --port 8000
# vérifier le LLM depuis WSL avant la démo :
curl http://192.168.137.222:8200/v1/chat/completions -H 'Content-Type: application/json' \
  -d '{"messages":[{"role":"user","content":"Bonjour"}],"chat_template_kwargs":{"enable_thinking":false}}'
```

`GET /api/sante` indique le mode (`mock`/`real`) et si un LLM est configuré. Démarrage en mode real : ~11 s.

## Autres commandes

| Quoi | Commande |
|---|---|
| API sur les mocks du contrat | `BASIRA_MODE=mock uv run uvicorn api.main:app --host 0.0.0.0 --port 8000` |
| Régénérer les mocks (`data/mock/`) | `uv run python -m api.mocks` |
| Tester l'assistant sans le Qwen | `uv run uvicorn tools.faux_llm:app --port 8200` puis `LLM_BASE_URL=http://127.0.0.1:8200/v1` (`FAUX_LLM_SANS_OUTILS=1` simule un serveur sans tool-calling) |
| Démo boucle d'apprentissage (avant/après) | `uv run python -m scoring.boucle [--demo]` |
| Graphe interactif (A) | `uv run python -m generation.visualisation` → `data/graphe/explorateur.html` |
| Note de synthèse PDF (B) | `uv run python -m signaux.report --data-dir data` |
| Tests (A + B + C) | `uv run pytest -q` |

## Variables d'environnement

| Variable | Défaut | Rôle |
|---|---|---|
| `BASIRA_DATA_DIR` | `data` | dossier des données (`raw/`, `graphe/`, `signaux/`, `scores/`) |
| `BASIRA_MODE` | `auto` | `mock`, `real`, ou `auto` (real si `scores/scores.parquet` existe) |
| `LLM_BASE_URL` | vide | URL OpenAI-compatible du Qwen distant (llama-server). Vide → mode `modele_texte` |
| `LLM_MODEL` | `qwen3.5:9b` | nom du modèle (ignoré par llama-server) |
| `LLM_TOOLS` | `1` | `0` = plan B forcé : contexte JSON dans le prompt, sans tool-calling (bascule automatique si le serveur refuse les outils) |
| `LLM_THINKING` | `0` | `0` envoie `enable_thinking=false` (Qwen 3.5, latence) |
| `LLM_TIMEOUT` | `45` | budget en secondes ; au-delà → repli `modele_texte` |
| `LLM_MAX_TOKENS` | `700` | longueur maximale d'une réponse |

## Entrées / sorties de C

- Lit : `data/signaux/{signaux,enjeux,groupes_pairs,pairs_stats}.parquet` (B), `data/raw/*.csv` et `data/graphe/aretes.csv` (A).
  `data/raw/verite_terrain.csv` n'est lu **que** par `scoring/evaluate.py`.
- Écrit : `data/scores/{scores.parquet, enjeux.parquet, modele.json, evaluation.json, decisions.csv, simulation_boucle.json}`.

## Méthode (résumé pour la note de synthèse)

1. **Apprentissage** (`scoring/train.py`) : un exemple par contrôle passé ; caractéristiques = `valeur_norm` des 16 signaux au mois
   précédant l'avis + 2 combinaisons ; cible = redressement (mineur ou fraude significative, poids 2). Régression logistique L2,
   classes équilibrées, **poids ≥ 0** (signaux à coefficient négatif retirés puis réentraînement, listés dans `modele.json`).
   Les signaux **jamais observés** dans les contrôles passés (sélectionnés par une règle type SAR) **ou à coefficient négatif**
   reçoivent un poids a priori égal à la médiane des poids appris : la règle SAR a sur-sélectionné certains signaux (CHG_CA,
   CHG_DEPOTS…) sans redressement, ce qui produit un coefficient négatif par biais de sélection, pas une baisse réelle du risque.
2. **Calibrage par la capacité** : on garde les poids relatifs appris et on fixe l'échelle sans étiquette : entreprise sans signal = 5,
   1 % des couples entreprise × mois les plus à risque ≥ 70 (seuil PRIORITAIRE). Une ancre sur les fraudes confirmées a été abandonnée :
   leurs signaux étaient faibles au moment du contrôle, l'échelle explosait (30 % du portefeuille PRIORITAIRE).
3. **Plancher « preuve forte »** (`scoring/score.py`) : un signal de cohérence (`COH_*`, écart entre deux sources indépendantes) ≥ 0.8
   rend l'entreprise au moins PRIORITAIRE ; les points ajoutés sont attribués à ce signal (la somme des points = score − score de base).
4. **Enjeu complété** (`scoring/enjeux.py`) : max(enjeu de B, droits éludés sur articles sous-évalués en douane + ventes cachées révélées
   par une croissance des imports ≥ 50 points au-dessus de celle du CA). Priorité = score × enjeu.
5. **Score** : `100·σ(b0 + Σ wᵢxᵢ)` + bonus « nouveau schéma » (0–15) ; segments, action suggérée (contrat §6.3), résumé en français.
6. **Évaluation** (`scoring/evaluate.py`) : top 50 par mois sur les 12 derniers mois, Basira vs règle statique type SAR vs hasard.
7. **Assistant** (`api/assistant.py`) : un appel LLM avec 4 outils ; toute valeur chiffrée de la réponse doit figurer dans les données
   des outils, sinon repli déterministe (`api/modele_texte.py`). L'assistant ne décide jamais.

Résultats sur le monde de A (seed 2026, 2026-08) : 208 PRIORITAIRE dont 73 % de fraudes actives ; top 50 mensuel : 87 % de fraudes
contre 23 % pour la règle type SAR et 5 % au hasard (`data/scores/evaluation.json`). Validation (`validation_modele` du même fichier) :
un modèle entraîné sans aucun contrôle de la période de test garde 87 % ; les poids appris ne battent pas des poids égaux
(AUC en validation croisée 0,63 contre 0,62) : la performance vient du croisement des sources.

Note de synthèse : `uv run python -m signaux.report --final` → `docs/note_synthese.pdf` (chiffres lus dans `data/scores/` et
`data/signaux/`, inventaire dans `docs/team_stack.json`).

## Bibliothèques et modèles utilisés

Python 3.13, uv · pandas 3, numpy, pyarrow · scikit-learn (LogisticRegression) · NetworkX (A) · ReportLab (B) · FastAPI, Uvicorn,
Pydantic · client `openai` (API compatible OpenAI) · **Qwen 3.5 9B** (modèle pré-entraîné, servi par llama-server sur une autre
machine du réseau) · pytest, httpx.

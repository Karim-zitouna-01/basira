# Mocks de l'API Basira (écrits par C, régénérés par `uv run python -m api.mocks`)

Nom de fichier = chemin de la route avec `_` (sans les paramètres de requête).

| Route | Fichier |
|---|---|
| `GET /api/stats/synthese` | `api_stats_synthese.json` |
| `GET /api/entreprises` | `api_entreprises.json` (les 8 héros ; les filtres/tri sont appliqués par l'API en mode mock) |
| `GET /api/entreprises/{mf}` | `api_entreprises_{mf}.json` (8 héros) |
| `GET /api/entreprises/{mf}/preuves?signal=X` | `api_entreprises_{mf}_preuves_{X}.json` (un par contribution) ; `api_entreprises_{mf}_preuves.json` = 1re contribution |
| `GET /api/entreprises/{mf}/reseau` | `api_entreprises_{mf}_reseau.json` |
| `POST /api/entreprises/{mf}/decision` | `api_entreprises_{mf}_decision.json` |
| `POST /api/assistant` | `api_assistant.json` |
| `GET /api/evaluation` | `api_evaluation.json` (⚠️ exemples de format, pas des résultats) |

Alpha (`1000001BAM000`) reprend exactement les exemples du contrat §6.2 ; `trajectoire` et `series` sont étendues aux 24 mois.

# Basira — Member B / Lot B

Code Python autonome pour les **16 signaux statistiques**, les preuves en français,
les enjeux financiers, les statistiques de pairs et la note de synthèse.
Les sept documents d'origine sont conservés dans `docs/specifications/`.

## Démarrage immédiat

Un environnement `.venv` et un jeu jouet sont déjà préparés sur cette machine :

```bash
cd ~/Desktop/basira-member-b
source .venv/bin/activate
python -m signaux.run
python -m signaux.checks --strict
python -m signaux.report
pytest -q
```

Sur une autre machine, Python 3.11 ou supérieur :

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.lock.txt
python -m pip install --no-deps -e .
```

Pour créer un jeu jouet dans un **nouveau** répertoire :

```bash
python -m signaux.demo --data-dir /tmp/basira-exemple --n 80
python -m signaux.run --data-dir /tmp/basira-exemple
python -m signaux.checks --data-dir /tmp/basira-exemple --strict
```

Le générateur de test refuse d'écraser un dossier `raw/` ou `graphe/` existant.
Il n'est pas le générateur de population de A : ses scénarios sont des cas de test
lisibles, sans fichier de vérité terrain, sans calibration des scores de C.

## Utilisation avec les vrais fichiers de A

Fournir le dossier `data/` de A sans le modifier :

```bash
python -m signaux.run --data-dir /chemin/vers/basira/data
python -m signaux.checks --data-dir /chemin/vers/basira/data --strict
```

Les sorties sont écrites dans ce dossier sous `signaux/`. Pour les isoler :

```bash
python -m signaux.run \
  --data-dir /chemin/vers/basira/data \
  --output-dir /chemin/vers/livraison/signaux
```

Le mode normal exige les fichiers consommés par B. `--allow-missing` accepte des
sources absentes pour l'échantillon précoce, les indique dans le rapport et
neutralise les signaux qui en dépendent. Une table vide avec ses en-têtes est une
source présente sans opération. Une ligne invalide, une clé dupliquée, une date
invalide ou une jointure orpheline provoque une erreur explicite.

Fichiers requis : `contribuables`, `declarations_mensuelles`,
`douane_declarations`, `douane_articles`, `douane_liquidation`,
`employeur_annexe1_synthese`, `employeur_annexe2`, `employeur_annexe5`,
`adeb_paiements`, `historique_controles`, `ref_ndp` dans `raw/`, et
`metriques_noeuds.csv` dans `graphe/`.
B ne lit jamais `verite_terrain.csv`, les scores ou un modèle appris.
Le champ `section_nat` du registre suffit pour le repli des pairs; `ref_nat` n'est
pas nécessaire aux calculs de B.

## Livraison à C

| Fichier | Contenu |
|---|---|
| `signaux.parquet` | `mf × mois × 16`, y compris signaux inactifs; listes Arrow `list<string>` |
| `enjeux.parquet` | Une ligne par entreprise et mois; montants TND à trois décimales |
| `pairs_stats.parquet` | Groupe, mois, indicateur, médiane, P10, P90, nombre de valeurs valides |
| `groupes_pairs.parquet` | Mapping stable `mf → groupe`, libellé, taille du groupe |
| `audit_signaux.jsonl` | Agrégats de contrôle, périodes et nombre de pièces pour les signaux actifs |
| `rapport_execution.json` | Volumes, durée, avertissements, problèmes de preuves et SHA-256 des entrées |
| `controle_heros.md` | Produit par `signaux.checks`; écarts explicites aux attentes du contrat |

Les quatre premiers fichiers respectent les noms et colonnes du contrat.
`audit_signaux.jsonl` est un complément facultatif; il ne modifie pas l'interface de C.
Les fichiers d'une exécution ne sont publiés qu'après la réussite du calcul;
chaque fichier est remplacé atomiquement. L'ensemble multi-fichiers n'est pas une
transaction : C doit charger après la fin du processus, jamais pendant une écriture.

Exemple de lecture :

```python
import pandas as pd

signals = pd.read_parquet("data/signaux/signaux.parquet")
alpha = signals.query("mf == '1000001BAM000' and mois == '2026-08'")
print(alpha.loc[alpha.valeur_norm >= 0.5, ["code_signal", "fait_fr", "preuves"]])
```

Le calcul des `CMB_*`, des poids, scores, segments et actions suggérées appartient
à C. Le tableau des héros de B n'affirme donc pas qu'Alpha vaut 76 ou que Zeta est
NORMAL : il vérifie leurs signaux, notamment l'absence de `COH_*` actif chez Zeta.

## Organisation du code

| Module | Responsabilité |
|---|---|
| `catalogue.py` | Les 16 codes, lentilles, unités et sources |
| `io.py` | Lecture CSV par liste blanche et validation |
| `data.py` | Jointures, matrices mensuelles et disponibilité à date |
| `statistics.py` | EWMA, normalisation, covariance régularisée, format français |
| `peers.py` | Groupes, replis, comparaisons, statistiques pour `/pairs` |
| `evidence.py` | Références de preuves, chemins réseau, faits français vérifiables |
| `exposure.py` | Reconstitutions HT, droits estimés, confiance, intervalle |
| `engine.py` | Orchestration d'un mois, calcul vectorisé sur les entreprises |
| `run.py` | CLI et publication des Parquet |
| `demo.py`, `checks.py` | Données de test et contrôle des héros |
| `report.py` | Note de synthèse PDF, avec résultats réels fournis par C |

Les choix d'interprétation sont explicités dans [docs/methodologie.md](docs/methodologie.md).
Le code ne modifie pas les documents contractuels originaux ni les CSV de A.

## Vérifications et performance

```bash
pytest -q
ruff check signaux tests
ruff format --check signaux tests
bash scripts/benchmark.sh
```

Le benchmark crée des données isolées sous `/tmp`, exécute les 24 mois pour
5 250 entreprises, conserve les fichiers pour inspection et écrit sa mesure dans
`docs/benchmark_5250.json`. Cible : **2 016 000 lignes, moins de 600 secondes**.
Il mesure le jeu de test de B; le volume réel d'opérations de A doit aussi être
mesuré lors de l'intégration.

## Note de synthèse, deux pages en français

`docs/note_synthese.pdf` est fourni. Le script peut le régénérer :

```bash
python -m signaux.report --data-dir /chemin/vers/basira/data
```

Les chiffres d'impact viennent exclusivement de `data/scores/evaluation.json`.
Sans ce fichier, le PDF indique que l'impact reste à mesurer. Les valeurs exemples
du contrat ne sont jamais copiées comme des résultats.
`docs/team_stack.json` distingue les modèles et bibliothèques prévus chez C/D de
leur usage confirmé. Compléter leur liste et confirmer l'inventaire avant :

```bash
python -m signaux.report --data-dir /chemin/vers/basira/data --final
```

`--final` échoue si l'évaluation de C ou la confirmation de l'inventaire manque.
La note mentionne explicitement Qwen 3.5 9B comme modèle pré-entraîné prévu par
le cahier des charges. Aucune dépendance LLM n'est installée par le lot B.
Les taux employés pour l'enjeu sont ceux du prototype contractuel.

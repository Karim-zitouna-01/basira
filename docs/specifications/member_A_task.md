# Mission — Personne A : le « monde » simulé (données + graphe) puis pitch deck

> À lire d'abord : [`contrat_integration.md`](contrat_integration.md) (§1, §2, §7, §8) et [`modele_donnees.md`](modele_donnees.md) (Parties 2 et 3 — **c'est ta spécification**).

## 1. Ta mission en une phrase
Générer des données synthétiques qui ont **exactement la forme des données réelles** de la DGI, de la douane (SINDA) et d'ADEB, avec des scénarios de fraude crédibles et une vérité terrain cachée, puis construire le graphe des relations. Tout le projet repose sur la qualité de ton travail. À partir de 01h00, tu prends en charge le **pitch deck**.

## 2. Entrées
- `modele_donnees.md` Partie 2 (colonnes, types, codes) et Partie 3 (volumes, distributions, scénarios, cas héros).
- Aucune donnée externe n'est nécessaire. Pour `ref_nat.csv`, `ref_ndp.csv` et `ref_gouvernorats.csv`, écris les valeurs toi-même à partir des tableaux du document (une trentaine de classes NAT, environ 150 codes NDP répartis sur les chapitres 39, 52, 72, 73, 84, 85, 87, 30).

## 3. Sorties (chemins et formats figés)
- `data/raw/*.csv` : toutes les tables de `modele_donnees.md` §2.1 à §2.13, plus `verite_terrain.csv` (§2.15).
- `data/graphe/aretes.csv` et `data/graphe/metriques_noeuds.csv` (§2.14).
- `generation/` : code Python ; `python -m generation.run --n 5250 --seed 2026` régénère tout ; `--n 200` produit l'échantillon.
- `generation/checks.py` : contrôles de cohérence (§5), exécutés à la fin de `run`.

## 4. Étapes, par ordre de priorité
1. **17h00–17h30 — Squelette.** Crée l'arborescence du dépôt (contrat §2). Écris les tables `ref_*.csv` et une fonction `mf(n)` qui produit `NNNNNNN` + lettre clé + `A` + `M` + `000`. Pour la lettre clé, utilise une lettre tirée de l'alphabet sans I, O, U (l'algorithme officiel n'est pas vérifié, n'en invente pas un).
2. **17h30–18h00 — Échantillon (200 entreprises, dont les 8 héros du contrat §7).** `contribuables`, `declarations_mensuelles`, `douane_*` et `employeur_annexe5` suffisent pour débloquer B. Les héros doivent reproduire **exactement** le scénario et la trajectoire attendus (Alpha : imports ×3,4 à partir de 2026-06, CA plat, nouveau fournisseur étranger `FE00231` partagé avec 4 autres importateurs qui démarrent le même mois).
3. **18h00–20h00 — Toutes les tables** : `declarations_is`, annexes I, II et V, `adeb_paiements`, `historique_controles`, `fournisseurs_etrangers`.
   - **Ordre de génération qui garantit la cohérence :**
     1. Entreprises et CA « réel » mensuel (saisonnalité et bruit).
     2. Achats (importations et achats locaux, en fonction de la marge du secteur).
     3. Flux interentreprises : l'annexe V du client est **la même transaction** que la vente du fournisseur.
     4. Déclarations = réel, **sauf** là où un scénario modifie le déclaré.
     5. Liquidation douane et TVA déductible sur importations.
     6. Contrôles passés : sélection biaisée, puis issue tirée selon la vérité terrain (Partie 3.2).
4. **20h00–21h00 — Scénarios A à F, témoins et coquilles** (tableau 3.3), avec `verite_terrain.csv`.
5. **21h00–22h00 — Graphe** (networkx) : `aretes.csv`, puis `metriques_noeuds.csv` pour chaque mois de 2024-09 à 2026-08. Respecte les règles de §2.14 : définition fixe du profil coquille, et pas de contrôle « futur » dans `distance_entite_redressee`.
6. **22h00–23h00 — Volume complet (5 250 entreprises)** ; vérifie le temps d'exécution (moins de 10 min visé).
7. **À partir de 01h00 — Pitch deck** (voir §7).

## 5. Contrôles à automatiser (`checks.py`) — ils doivent tous passer
- Clés uniques (`mf`, `num_declaration`, `id_article`, `id_ligne`, `num_ordonnance`, `id_controle`). Tout `mf_fournisseur`, `mf_beneficiaire` ou `mf_importateur` existe dans `contribuables.csv`.
- `valeur_caf_tnd` d'une déclaration = Σ articles (±0,01) ; montants de liquidation cohérents avec les taux de `ref_ndp`.
- Pour les entreprises **sans scénario** : Σ annexe V reçue par un fournisseur ≤ son CA TTC déclaré de l'exercice ; TVA 105 du mois ≈ `tva_deductible_import` du mois suivant (±5 %) ; CA de la déclaration IS ≈ Σ mensuel (±2 %).
- Pour chaque scénario : la « signature » attendue est bien présente (ex. héros C : `prix_unitaire / prix_reference` < 0,7 sur au moins 3 articles).
- Distribution des circuits proche de 70/22/8 ; taux de contrôle ≈ 3 %/an ; environ 8 % d'entreprises avec un scénario.
- Aucun nombre négatif sauf s'il est justifié ; toutes les dates sont dans la fenêtre 2023-09 → 2026-08.

## 6. Définition de « terminé »
- `python -m generation.run` produit toutes les tables sans erreur et `checks.py` est entièrement vert.
- Les 8 héros ont le comportement décrit au contrat §7 (valide-le avec B dès 20h00).
- Un court `data/raw/README.md` liste les tables, le nombre de lignes et la graine.

## 7. Pitch deck (à partir de 01h00, 10 à 15 diapos, PDF ou PPTX)
Structure imposée par le cahier des charges : problème · données · approche IA · prototype · impact · limites et perspectives. Contenu :
1. **Titre**, Basira, une phrase.
2. **Le problème, dans les mots de l'administration** (citations DGI / budget / douane de `Input/conf*_clean.md`).
3. **Pourquoi c'est difficile aujourd'hui** : scores statiques pondérés à la main, données en silos, 2,5 % de couverture.
4. **Basira : les 4 lentilles** (cohérence, changement, pairs, réseau).
5. **Les données** : sources réelles reproduites (DGI, annexe V, SINDA, ADEB, historique des contrôles), montrées sous forme de schéma ; précise qu'elles sont synthétiques mais ont la forme réelle.
6. **L'IA au bon endroit** : le tableau « IA ou pas » (seulement 2 IA : pondération apprise des contrôles passés, et assistant local).
7. **Parcours inspecteur** : triage → Alpha → preuves → décision (captures de D).
8. **Assistant local et souverain** (aucune donnée ne sort).
9. **Impact** : chiffres de `evaluation.json` comparés à la règle statique et à la sélection aléatoire.
10. **Équité et garde-fous** : l'humain décide, segment CONFIANCE, traçabilité.
11. **Intégration** : couche IA au-dessus des données SADEC 2 / SINDA (sans rien remplacer).
12. **Limites et feuille de route** : référentiel national d'activités, facture électronique, caisses enregistreuses, XGBoost si beaucoup d'étiquettes.
13. **Équipe et demande.**

## 8. Hors périmètre
- Pas de reproduction des fichiers officiels à longueur fixe. Pas de facture électronique ni de caisses enregistreuses (feuille de route seulement).
- Pas de base de données : des CSV suffisent.
- Tu ne calcules aucun signal : c'est le travail de B. Tu fournis seulement les métriques du graphe.

## 9. Avec qui te synchroniser
- **B** à 18h00 (échantillon), 20h00 (validation des héros) et 23h00 (volume complet).
- **C** : `historique_controles` et `verite_terrain` ; C ne lit jamais `verite_terrain` pour l'entraînement.
- **D** : les noms, secteurs et gouvernorats des héros doivent correspondre à leurs mocks.

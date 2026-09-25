# Mission — Personne B : les 4 lentilles (statistiques pures) puis note de synthèse

> À lire d'abord : [`contrat_integration.md`](contrat_integration.md) **§3 (catalogue des signaux) et §4 (ta sortie)**, ce sont ta spécification ; [`modele_donnees.md`](modele_donnees.md) Partie 2 (colonnes que tu lis) et 3.3 (signature attendue de chaque scénario).

## 1. Ta mission en une phrase
Transformer les données brutes de A en **signaux explicables** : un chiffre normalisé, une phrase en français et les preuves (lignes sources). Tu estimes aussi l'**enjeu financier**. Tout est déterministe, sans modèle entraîné. À partir de 02h00, tu prends en charge la **note de synthèse**.

## 2. Entrées
- `data/raw/*.csv` et `data/graphe/metriques_noeuds.csv` (produits par A ; échantillon à 18h00, volume complet à 23h00).
- **Jamais** `verite_terrain.csv`.

## 3. Sorties (figées par le contrat §4)
- `data/signaux/signaux.parquet` : format long, une ligne par `mf` × `mois` × `code_signal`, pour les **16 signaux non-`CMB`** du catalogue et chaque mois de 2024-09 à 2026-08.
- `data/signaux/enjeux.parquet` : une ligne par `mf` × `mois`.
- `signaux/` : code Python ; `python -m signaux.run` régénère tout.

## 4. Étapes, par ordre de priorité
1. **17h00–18h00 — Préparation, sans attendre A.** Écris une petite table « jouet » à la main avec les colonnes du dictionnaire. Code le squelette `run.py`, qui écrit un parquet au bon schéma. Code aussi les utilitaires communs :
   - fenêtres glissantes par `mf` (6 et 12 mois) ;
   - z-score EWMA (α = 0,3, moyenne et écart-type sur les 12 mois précédents, **hors 2 derniers mois**) ;
   - normalisation `clip((z − 1)/3, 0, 1)` ;
   - formatage des montants en français (« 3,2 MD », « 840 000 DT »).
2. **18h00–20h00 — Lentilles Cohérence et Changement** sur l'échantillon : `COH_IMPORT_VS_CA`, `COH_CLIENTS_VS_CA`, `COH_ADEB_VS_CA`, `COH_TVA_IMPORT`, `COH_VALEUR_REF`, `CHG_CA`, `CHG_IMPORTS`, `CHG_TVA_DEDUCTIBLE`, `CHG_NOUVEAUX_FOURNISSEURS`, `CHG_NOUVELLES_CATEGORIES`, `CHG_DEPOTS`. Chaque signal fournit `fait_fr` (quand `valeur_norm` ≥ 0,5) et `preuves` (au plus 50, triées par montant).
   - **Latence des données réelles :** l'annexe V de l'exercice N n'est utilisable qu'à partir du mois **N+1-03**. Pour un mois antérieur, utilise l'exercice N−1.
3. **20h00 — Livraison à C** et validation des 8 héros avec A (contrat §7 : les bons signaux sont-ils actifs ?).
4. **20h00–22h00 — Lentilles Pairs et Réseau.**
   - `PAI_MARGE`, `PAI_MAHALANOBIS` : groupes de pairs définis par division NAT × taille, repli si le groupe compte moins de 30 entreprises (contrat §3). Utilise une **covariance robuste** (ex. `sklearn.covariance.MinCovDet`) ou une covariance régularisée, pour qu'une matrice singulière ne fasse pas planter le calcul. Pour `fait_fr`, décompose la distance et cite la variable qui contribue le plus.
   - `RES_FOURNISSEUR_PARTAGE`, `RES_COQUILLE`, `RES_PROXIMITE_REDRESSE` : simple normalisation des colonnes de `metriques_noeuds.csv`. Les preuves renvoient aux lignes d'annexe V ou de douane concernées.
   - Le endpoint `/pairs` de C a besoin de la médiane et des déciles (P10, P90) des indicateurs par groupe. Écris-les aussi dans `data/signaux/pairs_stats.parquet` (`groupe`, `indicateur`, `mediane`, `p10`, `p90`, `nb`) et ajoute un mapping `mf → groupe` (`data/signaux/groupes_pairs.parquet`). (contrat §4.3).
5. **22h00–23h00 — Enjeux** (`enjeux.parquet`) : formules du contrat §4.2. Fourchette simple ±30 %, élargie quand la confiance est faible. `confiance` = moyenne de trois éléments : (mois d'historique / 24), (nb de sources présentes / 4), et accord entre les deux reconstitutions du CA.
6. **23h00–00h30 — Volume complet** : optimise (calculs vectorisés par `groupby`, pas de boucle Python sur les entreprises × mois) et livre à C.
7. **Monte Carlo (D5), seulement si tu es en avance à 01h00** : 1 000 tirages en perturbant le CA reconstitué (±15 %), la marge des pairs (±5 pts) et le taux applicable ; remplace `enjeu_bas` et `enjeu_haut` par les percentiles 5 et 95.
8. **À partir de 02h00 — Note de synthèse** (§7).

## 5. Règles de qualité
- **Chaque phrase `fait_fr` ne contient que des chiffres vérifiables dans les preuves.** C'est notre argument d'explicabilité devant le jury.
- Pas de fuite du futur : un signal du mois M n'utilise que des données disponibles à la fin de M.
- Témoin « croissance légitime » (héros Zeta) : `CHG_IMPORTS` peut être actif, mais **aucun signal COH_** ne doit l'être. Si c'est le cas, corrige la formule, pas les données.
- Toutes les valeurs de `valeur_norm` sont dans [0, 1] ; aucun NaN (mets 0 et un `fait_fr` vide si la donnée manque).

## 6. Définition de « terminé »
- `signaux.parquet` complet (5 250 × 24 × 16 lignes) avec le bon schéma, et `enjeux.parquet` complet.
- Un tableau de contrôle (notebook ou script) montre les signaux actifs de chaque héros. Il correspond au contrat §7.
- Temps d'exécution inférieur à 10 minutes sur le volume complet.

## 7. Note de synthèse (à partir de 02h00 ; 2 pages maximum, PDF, en français)
Contenu imposé : défi choisi (T20, secondaire T7) · approche technique · données et modèles utilisés · résultats · limites · recommandations pour une mise en production. Points à ne pas oublier :
- **Données** : synthétiques ; leur forme reproduit les sources réelles citées dans `modele_donnees.md` (avec 3 ou 4 références clés) ; loi 2004-63 / INPDP.
- **Modèles** : statistiques pour les signaux ; régression logistique apprise sur les contrôles passés ; Qwen 3.5 9B local pour l'assistant. **Mentionner explicitement tous les modèles pré-entraînés et toutes les bibliothèques utilisés**, c'est obligatoire (cahier des charges §4.1). Récupère la liste auprès de C et D.
- **Résultats** : chiffres de `data/scores/evaluation.json`.
- **Limites** : données synthétiques, biais de sélection des étiquettes, référentiel d'activités non unifié, SAR et SADEC 2 connus seulement par la conférence.
- **Mise en production** : branchement sur le data lake SADEC 2 et sur SINDA 2, hébergement interne, ré-entraînement à partir des décisions des inspecteurs.

## 8. Hors périmètre
- Pas d'apprentissage automatique ni de pondération des signaux (c'est le travail de C). Pas de combinaisons `CMB_*` (C).
- Tu ne modifies pas les données de A : si une donnée est incohérente, signale-le à A.

## 9. Avec qui te synchroniser
- **A** à 18h00, 20h00 et 23h00.
- **C** à 20h00 (première livraison) et à 00h30 (volume complet) ; tout changement de schéma passe par le contrat.
- **D** : relis les `fait_fr` affichés à l'écran (longueur, lisibilité).

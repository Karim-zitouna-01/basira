# Décisions de C à reporter dans le journal des changements du contrat

| # | Sujet | Décision | À valider avec |
|---|---|---|---|
| 1 | Noms des mocks | Chemin de la route avec `_` ; preuves : `api_entreprises_{mf}_preuves_{SIGNAL}.json` (+ `_preuves.json` = 1re contribution). Voir `data/mock/README.md`. | D |
| 2 | Mocks | Les 8 héros ont une fiche complète ; Alpha reprend exactement les exemples du contrat, `trajectoire` et `series` étendues à 24 mois. | D |
| 3 | **Calibrage du score** (révisé à l'intégration, validé par l'équipe) | Sans signal = 5 ; le 1 % des couples entreprise × mois les plus à risque = 70 (capacité, sans étiquette). L'ancre « fraude médiane = 70 » a été abandonnée : sur les données de A, les 15 fraudes avaient des signaux faibles au contrôle → échelle ×9,8 → 1 498 PRIORITAIRE (29 %). | équipe ✓ |
| 3b | Signaux jamais observés ou à coefficient négatif | Poids a priori = médiane des poids appris (jamais observés : COH_CLIENTS_VS_CA, CHG_NOUVELLES_CATEGORIES, RES_COQUILLE, CMB_COQUILLE_X_TVA ; négatifs : COH_ADEB_VS_CA, COH_TVA_IMPORT, CHG_CA, CHG_IMPORTS, CHG_DEPOTS). **Écart au contrat** (« retirer ou fixer à 0 »), décidé le 2026-09-26 : ces coefficients négatifs viennent du biais de sélection de la règle SAR. À 0, le CHG_IMPORTS actif d'Alpha ne comptait pas. | équipe ✓ |
| 3c | Plancher « preuve forte » | Un `COH_*` ≥ 0.8 → score ≥ 70 ; points ajoutés attribués à ce signal. | équipe ✓ |
| 4 | Bonus « nouveau schéma » | Signaux avec `valeur_norm` ≥ 0.8 et poids < médiane des poids positifs ; si ≥ 2 : `min(15, 5 × n × moyenne des valeur_norm)`. Affiché comme contribution `NOUVEAU_SCHEMA`, lentille `COMBINAISON`. | D |
| 5 | Règle statique (évaluation) | Bonus taille = 0.2 × classe (0 : 0–2, 1 : 3–9, 2 : 10–49, 3 : 50+). | B (note) |
| 6 | Évaluation | Fraude comptée à partir de `mois_debut_scenario` ; métriques = moyennes mensuelles ; clé additionnelle `details` (nb de fraudes détectées, délais). | D, B |
| 7 | Pairs : valeur de l'entreprise | Le contrat §4.3 ne fournit que les stats du groupe. C calcule la valeur de l'entreprise (marge, TVA déd./coll., CA/salarié, imports/CA sur 12 mois) à partir des déclarations et de la douane. B peut la fournir s'il préfère. | B |
| 8 | Relation « nouvelle » (réseau) | `premiere_date` dans les 18 derniers mois. | D |
| 9 | Action suggérée | La règle SIGNALEMENT_DOUANE (> 50 % des points sur COH_VALEUR_REF / CHG_NOUVELLES_CATEGORIES) est testée avant VERIFICATION / DEMANDE_INFO. | — |
| 10 | Route en plus | `GET /api/sante` (mode mock/real, LLM configuré). | D |
| 11 | **Enjeu complété** (validé par l'équipe) | `data/scores/enjeux.parquet` = max(enjeu B, droits éludés sur articles < 80 % du prix de référence + ventes cachées si croissance imports − CA ≥ 50 pts). L'API et la priorité l'utilisent. B ne chiffrait ni la douane (Beta : 328 DT) ni la croissance d'imports (Alpha : 22 DT). | B |
| 12 | `fait_fr` des signaux faibles | Quand B ne fournit pas de phrase (signal < 0.5 mais porteur de points), l'API en compose une à partir de `valeur_brute`, préfixée « Signal faible ». | D |
| 13 | Correctif dans `signaux/engine.py` (B) | Les COH_* sont calculés si la déclaration était **due** 12 mois (pas **déposée**) : une déclaration non déposée compte pour 0 au lieu de désactiver le contrôle (Omega, Delta y échappaient). Pairs et enjeu de B inchangés. | B |
| 15 | Correctif 2 dans `signaux/engine.py` (B) | `COH_IMPORT_VS_CA` exige des imports sur les 6 derniers mois : sinon une baisse du CA seule donnait un « écart imports/CA » (Omega, sans aucun import). | B |
| 16 | **Intégration de l'interface de D** | D a construit une app Vite/React sur son propre modèle de données (pas celui du contrat §6). Plutôt que réécrire ses pages, `api/front.py` sert ses formes (`/api/front/*`) à partir des vraies données ; ajouts : panneau « Pourquoi ce score ? » + décision (manquaient), copilote de la fiche sur `/api/assistant`. Sources : TJ → annexe V ; RAFIK sans source. | D |
| 14 | Assistant | `enable_thinking=false` ; un seul message système (contrainte du gabarit Qwen) ; bascule automatique en plan B si le serveur refuse les outils ou si le modèle répond sans outil ; délai 30 s. | — |

## Écarts connus aux héros (contrat §7), acceptés

- **Alpha** : SURVEILLANCE en hausse (33 → 49 → 64), pas PRIORITAIRE. Fraude démarrée en 2026-06 ; la fenêtre de 6 mois de
  `COH_IMPORT_VS_CA`, décalée d'un mois (déclaration de M connue en M+1), dilue l'écart (0.30).
- **Delta** : NORMAL en 2026-08. Imports et CA repartent tous deux de zéro → écart de croissance nul ; CHG_IMPORTS et
  CHG_NOUVELLES_CATEGORIES culminent en 2026-03..05 puis s'effacent. Visible dans la trajectoire.
- **Epsilon** : NORMAL (37), proche de SURVEILLANCE. **Eta** : NORMAL (8) et non CONFIANCE, car PAI_MAHALANOBIS de B était actif en
  2026-02 (règle « aucun signal actif sur 12 mois »).

## Après les premiers essais de l'équipe (2026-09-26)

- **Score plafonné à 99** (`config.SCORE_MAX`) : 3 entreprises affichaient 100 (clients de réseaux de fausses factures, 4 à 5 signaux
  forts + bonus « nouveau schéma »). Mathématiquement attendu, mais 100 se lit comme une certitude.
- **Copilote** : la page liste répondait par un calcul local, pas par le LLM. Désormais les deux pages passent par
  `POST /api/assistant` (`mf` optionnel, `contexte` = données de l'écran). Réponse de repli → champ `raison_repli` affiché.
  Qwen mesuré à 3–19 s par réponse ; délai porté à 45 s.
- **Copilote × graphe** (2026-09-26) : 2 outils de réseau (`get_liens_contrepartie`, `get_chemin_redresse`) et la route
  `POST /api/assistant/flux` (text/event-stream : `etape`, `graphe`, `reponse`). Les actions sur le graphe sont calculées par l'API
  à partir des relations déclarées (jamais par le modèle). Une contrepartie nommée ou une question de lien avec une entreprise
  redressée déclenche l'outil d'office (`outils_evidents`) : sans cela, Qwen répondait parfois sans outil et inventait des chiffres
  (bloqués par le garde-fou). Champ `graphe` ajouté aux réponses de `/api/assistant`.

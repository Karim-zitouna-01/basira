# Mission — Personne C : score appris, évaluation, API et assistant

> À lire d'abord : [`contrat_integration.md`](contrat_integration.md) **§3 (combinaisons), §4 (ton entrée), §5 et §6 (tes sorties et l'API)** ; [`modele_donnees.md`](modele_donnees.md) §2.12 (`historique_controles`) et §2.15 (`verite_terrain`).
> Décisions déjà prises : **régression logistique + 2 combinaisons explicites** (pas de XGBoost, prévu seulement dans la feuille de route) · **FastAPI** · **assistant = Qwen 3.5 9B en local**, avec un repli sur des modèles de texte.

## 1. Ta mission en une phrase
Apprendre, à partir des contrôles passés, **combien pèse chaque signal**, puis produire un score de 0 à 100 explicable, le segment, la priorité (risque × enjeu) et l'action suggérée. Tu prouves le gain face à la règle statique et au hasard. Tu sers le tout à D par l'API, avec un assistant ancré dans les données. Tu es sur le **chemin critique** : commence par ce qui débloque D.

## 2. Entrées
- `data/signaux/signaux.parquet`, `enjeux.parquet`, `pairs_stats.parquet`, `groupes_pairs.parquet` (produits par B ; échantillon à 20h00, volume complet à 00h30).
- `data/raw/historique_controles.csv`, `contribuables.csv`, les tables brutes pour les preuves et les séries, et `data/graphe/aretes.csv` (produits par A).
- `data/raw/verite_terrain.csv` : **uniquement dans l'évaluation**, jamais dans l'entraînement.

## 3. Sorties
- `data/scores/scores.parquet`, `modele.json`, `evaluation.json` et `decisions.csv` (contrat §5).
- `api/` : FastAPI, avec **toutes les routes du contrat §6.2** et exactement les JSON d'exemple. `data/mock/` : un fichier par route, que tu écris à 17h00 en copiant les exemples du contrat.
- `scoring/` : `python -m scoring.run` pour l'entraînement, le scoring et l'évaluation.

## 4. Étapes, par ordre de priorité
1. **17h00–18h00 — Débloquer D.**
   - Écris `data/mock/*.json` à partir du contrat.
   - Démarre une API FastAPI qui sert ces mocks sur les routes exactes, avec CORS ouvert pour `localhost:3000`.
   - Mets en place la structure `scoring/`.
2. **18h00–19h00 — Tester le LLM local (risque n°1).**
   - Lance Qwen 3.5 9B sur le PC GPU, par exemple avec Ollama ou vLLM, via une API compatible OpenAI.
   - Teste le **tool-calling** et la **qualité du français** sur une question du type « Pourquoi le risque d'Alpha a-t-il augmenté ? », avec le JSON mock en contexte.
   - Mesure la latence ; il faut une réponse en moins de 20 s.
   - Si le tool-calling n'est pas fiable, **passe au plan B** : injecte le contexte JSON complet de l'entreprise dans le prompt, sans outils.
3. **19h00–20h00 — Le repli `modele_texte`** : réponses déterministes générées à partir des `fait_fr` et des contributions (« Le score est passé de X à Y. Principales raisons : … »), ainsi qu'une lettre de demande d'information sous forme de gabarit. **Ce repli doit toujours fonctionner, même sans GPU.**
4. **20h00–22h00 — Score appris (sur l'échantillon, puis sur le volume complet).**
   - **Jeu d'entraînement.** Chaque contrôle de `historique_controles` donne un exemple. Les caractéristiques sont les `valeur_norm` des 16 signaux au **mois précédant `date_avis`**, auxquelles s'ajoutent les 2 combinaisons (`CMB_IMPORT_X_NOUV_FOURN`, `CMB_COQUILLE_X_TVA`, calculées d'après le contrat §3). Cible : 1 si le résultat est `REDRESSEMENT_MINEUR` ou `FRAUDE_SIGNIFICATIVE`, 0 si `CONFORME`. Donne un poids d'échantillon de 2 à `FRAUDE_SIGNIFICATIVE`.
   - `LogisticRegression` (scikit-learn) avec régularisation L2, `class_weight` équilibré, et **coefficients contraints à rester ≥ 0**. La contrainte s'obtient en retirant ou en fixant à 0 les signaux dont le coefficient est négatif, puis en réentraînant, et en le documentant. Un signal d'alerte ne doit jamais faire baisser le risque.
   - **Score** : `score = 100·σ(b0 + Σ w_i x_i)` ; `contributions` et `score_base` selon la formule du contrat §5.1 ; **bonus « nouveau schéma »** de 0 à 15 (contrat §5.1), affiché comme une contribution `NOUVEAU_SCHEMA`.
   - Segments, `priorite = score/100 × enjeu_estime`, `rang_priorite` par mois, `action_suggeree` (contrat §6.3) et `resume_fr` (2 ou 3 `fait_fr` avec les meilleurs points, plus l'enjeu).
   - Calcule les scores pour **tous les mois de 2024-09 à 2026-08**, afin d'obtenir les trajectoires.
   - Vérifie les 8 héros (contrat §7). **Si Alpha n'est pas PRIORITAIRE ou si Zeta n'est pas NORMAL, investigue les signaux avec B avant de toucher aux seuils.**
5. **22h00 — Brancher l'API sur les vrais fichiers** (échantillon). Le format ne change pas, seule la source des données change.
6. **22h00–01h30 — Évaluation** (`evaluation.json`, `GET /api/evaluation`).
   - Période de test : les 12 derniers mois. Pour chaque mois, prends les **top N = 50** selon trois méthodes :
     1. Basira (tri par `priorite`) ;
     2. **Règle statique type SAR** : poids fixes égaux sur 5 signaux « classiques » (`COH_IMPORT_VS_CA`, `COH_CLIENTS_VS_CA`, `CHG_CA`, `CHG_DEPOTS`, `PAI_MARGE`), plus un bonus pour la taille, pour reproduire le biais actuel ;
     3. Sélection aléatoire (moyenne sur 100 tirages).
   - Métriques, calculées avec `verite_terrain` :
     - taux de détection dans le top N (une entreprise compte si son scénario ≠ AUCUN, CROISSANCE_LEGITIME ou CITOYEN_MODELE) ;
     - montant moyen de `montant_fraude_reel` par contrôle ;
     - nombre d'entreprises à croissance légitime dans le top N ;
     - avance de détection en mois, comparée à la règle statique (premier mois où l'entreprise entre dans le top N, par rapport à `mois_debut_scenario`).
   - Exporte aussi `poids` et `nb_exemples` dans `modele.json` : ils serviront pour la diapo « IA au bon endroit ».
7. **Assistant complet** (`POST /api/assistant`) :
   - Le prompt système est en français. L'assistant répond **uniquement** à partir des outils `get_entreprise`, `get_preuves`, `get_reseau` et `rediger_lettre_demande_info`, cite ses sources dans `citations`, et n'invente jamais de chiffres.
   - Il **ne décide jamais** : il peut rappeler l'action suggérée, mais la décision appartient à l'inspecteur.
   - Si le LLM échoue ou dépasse 20 s, l'API renvoie la réponse `modele_texte` avec `mode: "modele_texte"`.
8. **Décisions** : `POST /decision` ajoute une ligne dans `decisions.csv` et la renvoie dans `GET /entreprises/{mf}` (`decisions`). Pour la démo de la boucle d'apprentissage, prépare une **simulation « avant/après »** : ajouter les décisions enregistrées comme exemples étiquetés, réentraîner et afficher la variation des poids. Pas de réentraînement en direct pendant la démo.

## 5. Règles
- Ne jamais utiliser `verite_terrain` pour l'entraînement ni pour choisir les seuils. C'est notre argument d'honnêteté.
- Les points des contributions doivent se lire dans l'interface **sans explication supplémentaire** (sinon, change l'arrondi ou le format, pas la formule).
- L'API ne recalcule rien à la volée : elle lit les fichiers de `data/scores/` et `data/signaux/`, qu'elle garde en mémoire au démarrage.

## 6. Définition de « terminé »
- Toutes les routes du contrat répondent avec le bon format, sur les vraies données.
- Les 8 héros correspondent au contrat §7.
- `evaluation.json` montre Basira contre la règle statique et contre le hasard.
- L'assistant répond à « Pourquoi le risque d'Alpha a-t-il augmenté ? » en mode `llm` **et** en mode `modele_texte`.
- Envoie à B (pour la note de synthèse) la liste des bibliothèques et modèles utilisés (scikit-learn, FastAPI, Qwen 3.5 9B, l'outil de service du LLM…).

## 7. Hors périmètre
- Pas de XGBoost, ni de LangGraph ou d'orchestration multi-agents, ni de base vectorielle ou de RAG documentaire. L'assistant, c'est **un appel LLM avec quelques outils**.
- Pas de calcul de signaux (sauf les deux `CMB_*`).

## 8. Avec qui te synchroniser
- **D** à 18h00 (mocks), 22h00 (vraies données) et 01h30 (version complète).
- **B** à 20h00 et à 00h30.
- **A** pour `historique_controles` et `verite_terrain`.
- **Aide possible** : A ou B peuvent reprendre l'assistant en mode `modele_texte` s'ils sont en avance.

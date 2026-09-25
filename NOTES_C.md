# Décisions de C à reporter dans le journal des changements du contrat

| # | Sujet | Décision | À valider avec |
|---|---|---|---|
| 1 | Noms des mocks | Chemin de la route avec `_` ; preuves : `api_entreprises_{mf}_preuves_{SIGNAL}.json` (+ `_preuves.json` = 1re contribution). Voir `data/mock/README.md`. | D |
| 2 | Mocks | Les 8 héros ont une fiche complète ; Alpha reprend exactement les exemples du contrat, `trajectoire` et `series` étendues à 24 mois. | D |
| 3 | **Calibrage du score** | Intercept et échelle fixés par 2 ancres calculées sur les contrôles passés : sans signal = 5 ; profil médian des fraudes significatives = 70. Poids relatifs appris inchangés. Sans cela, score de base ≈ 36 : aucune entreprise CONFIANCE, la moitié en SURVEILLANCE. | équipe |
| 4 | Bonus « nouveau schéma » | Signaux avec `valeur_norm` ≥ 0.8 et poids < médiane des poids positifs ; si ≥ 2 : `min(15, 5 × n × moyenne des valeur_norm)`. Affiché comme contribution `NOUVEAU_SCHEMA`, lentille `COMBINAISON`. | D |
| 5 | Règle statique (évaluation) | Bonus taille = 0.2 × classe (0 : 0–2, 1 : 3–9, 2 : 10–49, 3 : 50+). | B (note) |
| 6 | Évaluation | Fraude comptée à partir de `mois_debut_scenario` ; métriques = moyennes mensuelles ; clé additionnelle `details` (nb de fraudes détectées, délais). | D, B |
| 7 | Pairs : valeur de l'entreprise | Le contrat §4.3 ne fournit que les stats du groupe. C calcule la valeur de l'entreprise (marge, TVA déd./coll., CA/salarié, imports/CA sur 12 mois) à partir des déclarations et de la douane. B peut la fournir s'il préfère. | B |
| 8 | Relation « nouvelle » (réseau) | `premiere_date` dans les 18 derniers mois. | D |
| 9 | Action suggérée | La règle SIGNALEMENT_DOUANE (> 50 % des points sur COH_VALEUR_REF / CHG_NOUVELLES_CATEGORIES) est testée avant VERIFICATION / DEMANDE_INFO. | — |
| 10 | Route en plus | `GET /api/sante` (mode mock/real, LLM configuré). | D |

## Points ouverts

- **Robustesse des héros** : les poids appris dépendent des scénarios que la règle statique a fait contrôler. Sur les données de dev,
  les scénarios D (ADEB) et C (valeur en douane) sont presque absents des contrôles → poids faibles → Gamma et Beta sortent NORMAL ;
  et 4 contrôles « croissance légitime » sur 7 positifs par hasard → CHG_IMPORTS pèse lourd → Zeta PRIORITAIRE.
  À vérifier sur les vraies données de A/B : nombre de contrôles par scénario **après** `mois_debut_scenario`, et contrôles CONFORME
  sur les entreprises à croissance légitime.

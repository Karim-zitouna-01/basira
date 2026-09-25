# Vérification de la livraison

- Suite de régression : **17 tests réussis** (`pytest -q`, 16,78 s lors de la dernière exécution).
- Ruff : aucune erreur; les 15 fichiers Python sont formatés.
- Compilation Python : réussie.
- Exemple livré : **80 entreprises × 24 mois × 16 = 30 720 signaux**.
- Huit héros : aucune divergence sur les signaux attendus; contrôle dans `controle_heros_exemple.md`.
- Benchmark : **5 250 × 24 × 16 = 2 016 000 lignes en 205,854 s** (3 min 26 s), sous la cible de 600 s.
- Benchmark : aucun avertissement d'entrée ni signal actif sans preuve.
- Mesure sur le jeu jouet de B : 5 250 entreprises, 44 mois d'entrées, une opération douanière mensuelle pour presque chaque entreprise. Ce n'est pas le générateur ni la distribution des scénarios de A.
- Le rapport détaillé et les SHA-256 des entrées sont dans `benchmark_5250.json`.
- Les fichiers complets du benchmark de cette session restent dans `/tmp/basira-b-benchmark.Q0Fixa/data`.
- PDF : deux pages A4, texte français; seconde page inspectée visuellement.
- Les quatre sorties d'intégration du jeu exemple sont dans `data/signaux/`.

La vérification ne prétend pas mesurer un gain de détection. La note de synthèse
reste une version de travail tant que `evaluation.json` de C et l'inventaire
confirmé des modèles/bibliothèques de C et D n'ont pas été transmis. L'intégration
sur les fichiers de A reste à exécuter lorsque ceux-ci sont disponibles.

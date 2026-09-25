# Mission — Personne D : l'interface de l'inspecteur (Next.js + Tailwind)

> À lire d'abord : [`contrat_integration.md`](contrat_integration.md) **§6 (API, énumérations, JSON d'exemple)** et §7 (cas héros) ; [`idea_v3.md`](idea_v3.md) §5 (parcours utilisateurs).

## 1. Ta mission en une phrase
Construire ce que voit l'inspecteur : le triage du matin, la fiche entreprise qui explique **pourquoi** le risque a changé (avec les preuves), l'assistant et l'enregistrement de la décision. Tout part des mocks, dès 17h00, puis on bascule sur l'API réelle en changeant **une seule variable d'environnement**. C'est ce que le jury verra pendant 10 minutes.

## 2. Entrées
- `data/mock/*.json` (écrits par C à 17h00 à partir du contrat ; si ce n'est pas prêt, copie toi-même les exemples du contrat §6.2).
- API FastAPI de C : mocks à 18h00, vraies données de l'échantillon à 22h00, version complète à 01h30.

## 3. Sorties
- `web/` : application Next.js (App Router), Tailwind et TypeScript.
- `web/lib/api.ts` : **un seul client API**, typé à partir des JSON du contrat. Si `NEXT_PUBLIC_API_URL` est vide, il lit les fichiers mock ; sinon, il appelle l'API. Aucun `fetch` ailleurs dans le code.
- `web/lib/types.ts` : types TypeScript recopiés exactement des JSON du contrat (mêmes noms de champs, en français).

## 4. Écrans (par ordre de priorité)
1. **Triage du matin** (`/`)
   - Bandeau issu de `GET /stats/synthese` : 🔴 PRIORITAIRE · 🟠 SURVEILLANCE · 🟢 NORMAL · 🔵 CONFIANCE, avec leurs nombres, et l'enjeu total des dossiers prioritaires.
   - Tableau issu de `GET /entreprises` : rang, raison sociale, secteur, gouvernorat, score avec flèche de variation (`delta_score`), segment (pastille de couleur), enjeu (fourchette en info-bulle), `resume_fr` et action suggérée.
   - Filtres : segment, secteur (division NAT), gouvernorat ; tri : priorité, score, variation, enjeu.
2. **Fiche entreprise** (`/entreprise/[mf]`), écran clé de la démo.
   - En-tête : identité, score, segment, confiance, enjeu (fourchette), action suggérée.
   - **Trajectoire** : courbe du score sur 12 mois ou plus, avec zones de couleur par segment. Le moment du changement doit sauter aux yeux (Alpha : 28 → 52 → 76).
   - **« Pourquoi »** : barres horizontales des `contributions` (points), une couleur par lentille, avec la phrase `fait_fr` sous chaque barre et un bouton « Voir les preuves (n) ».
   - **Preuves** : panneau latéral ou tiroir alimenté par `GET /preuves?signal=` : table des lignes sources (source, référence, date, libellé, montant, champs).
   - **Pairs** : pour chaque indicateur, la position de l'entreprise par rapport à la médiane et à P10–P90 (une barre simple suffit).
   - **Séries** : CA déclaré, imports et TVA déductible sur 24 mois (petits graphiques). On doit voir les imports monter pendant que le CA reste plat.
   - **Réseau** (seulement si le temps le permet) : mini-graphe issu de `GET /reseau`. L'entreprise est au centre, les coquilles en rouge, les nouvelles relations en pointillés.
3. **Assistant** : panneau de discussion sur la fiche, qui appelle `POST /assistant`. Il affiche les `citations` sous forme de puces cliquables (une citation de type `signal` ouvre les preuves correspondantes) et un petit badge `LLM local` / `Mode texte` selon `mode`. Prévois trois questions suggérées : « Pourquoi le risque a-t-il augmenté ? », « Quels fournisseurs posent problème ? », « Rédige la demande d'information ».
4. **Décision** : 5 boutons (libellés du contrat §6.1) et une justification **obligatoire**, envoyés par `POST /decision`. Le texte rappelle : « La décision appartient à l'inspecteur ; Basira propose et explique. » Les décisions passées s'affichent sur la fiche.
5. **Impact** (`/evaluation`) : `GET /evaluation` présenté en 3 colonnes (Basira, règle statique, hasard). Deux ou trois grands chiffres et un graphique en barres. Cet écran sert aussi de capture pour la diapo Impact.
6. *Si le temps le permet :* carte thermique du risque par secteur × gouvernorat (utilise `GET /entreprises` sans filtre et agrège côté client), et une page « Candidats à la facilitation » (segment CONFIANCE).

## 5. Étapes et horaires
- **17h00–18h00** : initialisation du projet Next.js (Tailwind, bibliothèque de graphiques, par exemple Recharts), `types.ts`, `api.ts` en mode mock, mise en page générale (barre latérale Basira, en français).
- **18h00–21h00** : triage, puis fiche entreprise (trajectoire, pourquoi, preuves), sur les mocks. **À 21h00 (point mentor)** : parcours Alpha présentable sur les mocks.
- **21h00–01h30** : assistant, décision, pairs, séries, page Impact ; bascule sur l'API réelle à 22h00 et vérification des 8 héros.
- **01h30–04h00** : finitions (lisibilité, états de chargement et d'erreur, textes), réseau et carte thermique si le temps le permet. **Gel fonctionnel à 04h00.**
- **04h00–05h00** : répétition du scénario de démo (§6) avec toute l'équipe.
- **05h00** : **vidéo de démo de secours** (2 à 3 minutes, scénario §6), à déposer avec les livrables, au cas où la démo en direct tombe en panne devant le jury.
- Fournis à A des **captures d'écran** pour le deck, et à B la liste des bibliothèques frontend.

## 6. Scénario de démo (90 secondes, à répéter)
1. Triage : « 5 250 entreprises dans le portefeuille ; ce matin, 17 prioritaires. »
2. Clic sur **Alpha SARL** : la trajectoire montre un score de 28 → 76 en deux mois.
3. « Pourquoi » : les imports ont triplé alors que le CA déclaré est resté stable ; ils viennent d'un nouveau fournisseur étranger, apparu le même mois chez 4 autres importateurs. Clic sur « Voir les preuves » : les lignes douanières s'affichent. Clic sur le réseau pour voir les 5 entreprises.
4. Question à l'assistant : « Pourquoi le risque a-t-il augmenté ? », puis « Rédige la demande d'information ».
5. Décision « Vérification approfondie » avec sa justification.
6. *(Option)* **Omega Négoce** : ses clients déclarent 3 MD d'achats chez elle, mais elle n'a ni salarié ni CA déclaré. C'est le repérage des fausses factures grâce à l'annexe V.
7. Contre-exemple : **Zeta Industries**, forte croissance mais reste NORMAL, car tout est déclaré. « Nous ne punissons pas la croissance. »
8. Page Impact : Basira comparé à la règle statique et au hasard.

## 7. Règles d'interface
- Tout en **français**, montants au format « 420 000 DT » / « 3,2 MD », dates en JJ/MM/AAAA.
- Chaque chiffre de risque est accompagné de sa **raison**. Aucun score n'est affiché sans explication.
- Couleurs fixes pour les segments (rouge, orange, vert, bleu) et pour les lentilles ; mêmes couleurs partout, deck compris.
- Aucune logique métier côté client : pas de calcul de score ni de seuil. Tu affiches ce que l'API renvoie.
- Démo sur le **PC GPU** (celui qui fait tourner Qwen) : teste l'application sur cette machine avant 04h00.

## 8. Hors périmètre
- Pas d'authentification ni de gestion multi-utilisateur (un inspecteur « demo »).
- Pas d'accès direct aux fichiers de données : tout passe par `api.ts`.

## 9. Avec qui te synchroniser
- **C** à 18h00, 22h00 et 01h30. Si un champ te manque, demande qu'il soit ajouté au **contrat** ; ne le contourne pas dans le code.
- **B** : relecture des `fait_fr` à l'écran.
- **A** : captures pour le deck ; les héros doivent être cohérents avec les mocks.

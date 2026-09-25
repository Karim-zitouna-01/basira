# Basira — Contrat d'intégration (source unique de vérité)

> Ce fichier définit **tout ce qui passe d'un lot à l'autre** : conventions, chemins, catalogue des signaux, formats de sortie, API, cas héros. Il **remplace les sections JSON de `Input/architecture.md`**. Le dictionnaire des données brutes est dans [`modele_donnees.md`](modele_donnees.md).
>
> **Règle de changement :** toute modification de ce contrat doit être acceptée par le producteur **et** le consommateur concernés, puis écrite ici (section « Journal des changements » en bas). Pas de format « implicite » dans le code.

---

## 1. Conventions

| Sujet | Règle |
|---|---|
| Clé entreprise | `mf` = matricule fiscal compact à 13 caractères, ex. `1000001BAM000`. **Partout**, jamais d'autre identifiant d'entreprise. |
| Mois | `AAAA-MM` (chaîne), ex. `2026-08` |
| Dates | ISO `AAAA-MM-JJ` |
| Montants | TND, float, 3 décimales |
| Taux | pourcentage (19.0 = 19 %) |
| Fichiers tabulaires | CSV UTF-8 `,` pour `data/raw/` ; **Parquet** pour `data/signaux/` et `data/scores/` |
| Listes dans Parquet | colonnes de type liste (`list<string>`) |
| Langue | noms de colonnes et codes en français sans accents, `snake_case` ; textes affichés en français |
| Aléatoire | graine fixe `SEED = 2026` |
| Mois de calcul | Les signaux et scores sont calculés pour **chaque mois de 2024-09 à 2026-08** (24 mois). Le « mois courant » de la démo est **2026-08**. |

## 2. Arborescence du dépôt

```
basira/
├── data/
│   ├── raw/          ← A : tables de modele_donnees.md Partie 2 (+ ref_*.csv, verite_terrain.csv)
│   ├── graphe/       ← A : aretes.csv, metriques_noeuds.csv
│   ├── signaux/      ← B : signaux.parquet, enjeux.parquet
│   ├── scores/       ← C : scores.parquet, modele.json, evaluation.json, decisions.csv
│   └── mock/         ← exemples JSON de ce contrat (D les utilise dès 17h)
├── generation/       ← A (Python)
├── signaux/          ← B (Python)
├── scoring/          ← C (Python)
├── api/              ← C (FastAPI)
├── web/              ← D (Next.js + Tailwind)
└── README.md         ← commande unique pour tout régénérer
```

Pipeline complet : `python -m generation.run && python -m signaux.run && python -m scoring.run && uvicorn api.main:app`.

---

## 3. Catalogue des signaux (figé)

Chaque signal a une **lentille**, des **sources**, une formule, une normalisation vers `valeur_norm` ∈ [0, 1] (0 = normal, 1 = extrême) et un **modèle de phrase** `fait_fr`. Un signal est dit **actif** si `valeur_norm ≥ 0.5`.

Normalisation par défaut d'un z-score : `valeur_norm = clip((z − 1) / 3, 0, 1)` (z = 1 → 0 ; z = 4 → 1). Normalisations spécifiques indiquées ci-dessous.

| `code_signal` | Lentille | Sources | Calcul (fenêtre) | `valeur_brute` / `unite` | Exemple de `fait_fr` |
|---|---|---|---|---|---|
| `COH_IMPORT_VS_CA` | COHERENCE | douane_articles, declarations_mensuelles | croissance des imports CAF sur 6 mois − croissance du CA déclaré sur 6 mois (vs 6 mois précédents) ; norm : `clip(ecart/200, 0, 1)` | écart en points / `pts` | « Importations sur 6 mois : +240 % ; CA déclaré : +3 %. » |
| `COH_CLIENTS_VS_CA` | COHERENCE | employeur_annexe5 (+ annexe2), declarations_mensuelles | Σ montants payés à l'entreprise déclarés par ses clients (dernier exercice dispo) / Σ CA TTC déclaré du même exercice ; norm : `clip((ratio − 1) / 2, 0, 1)` | ratio / `x` | « 12 clients déclarent 3,2 MD d'achats auprès de l'entreprise en 2025 ; CA déclaré 2025 : 1,1 MD. » |
| `COH_ADEB_VS_CA` | COHERENCE | adeb_paiements, declarations_mensuelles | paiements publics HT reçus sur 12 mois / CA déclaré 12 mois, + écart retenue TVA 25 % ; norm : `clip((ratio − 0.9) / 0.6, 0, 1)` | ratio / `x` | « 840 000 DT reçus d'acheteurs publics sur 12 mois, pour un CA déclaré de 610 000 DT. » |
| `COH_TVA_IMPORT` | COHERENCE | douane_liquidation (105), declarations_mensuelles | TVA déductible sur importations déclarée 12 mois / TVA 105 liquidée en douane 12 mois ; norm : `clip((ratio − 1.1) / 0.9, 0, 1)` | ratio / `x` | « TVA déduite sur importations : 410 000 DT ; TVA payée en douane : 190 000 DT. » |
| `COH_VALEUR_REF` | COHERENCE | douane_articles, ref_ndp | moyenne pondérée (par valeur) de `prix_unitaire / prix_reference` sur 6 mois ; norm : `clip((0.9 − ratio) / 0.4, 0, 1)` | ratio / `x` | « Valeurs unitaires déclarées à 52 % du prix de référence (18 articles, 3 codes NDP). » |
| `CHG_CA` | CHANGEMENT | declarations_mensuelles | z-score EWMA (α = 0.3) du CA mensuel vs moyenne/écart-type des 12 mois précédents (hors 2 derniers) ; baisse **et** hausse | z / `z` | « CA déclaré du mois 2,8 écarts-types sous son niveau habituel. » |
| `CHG_IMPORTS` | CHANGEMENT | douane_articles | idem sur les imports CAF mensuels (hausse seulement) | z / `z` | « Importations ×3,4 par rapport à la moyenne des 12 derniers mois. » |
| `CHG_TVA_DEDUCTIBLE` | CHANGEMENT | declarations_mensuelles | idem sur `tva_deductible_biens_services_local` (hausse) | z / `z` | « TVA déductible sur achats locaux +85 % en 3 mois. » |
| `CHG_NOUVEAUX_FOURNISSEURS` | CHANGEMENT | douane_articles, employeur_annexe5 | nb de fournisseurs (étrangers ou locaux) apparus pour la 1re fois sur les 3 derniers mois (annexe V : dernier exercice) ; norm : `clip(n / 5, 0, 1)` | nombre / `n` | « 3 nouveaux fournisseurs en 3 mois (2 étrangers, 1 local). » |
| `CHG_NOUVELLES_CATEGORIES` | CHANGEMENT | douane_articles | nb de chapitres SH importés pour la 1re fois sur 3 mois ; norm : `clip(n / 3, 0, 1)` | nombre / `n` | « Nouvelle catégorie importée : chapitre 85 (machines électriques). » |
| `CHG_DEPOTS` | CHANGEMENT | declarations_mensuelles | nb de mois non déposés ou en retard > 30 j sur 6 mois ; norm : `clip(n / 4, 0, 1)` | nombre / `n` | « 4 déclarations mensuelles sur 6 non déposées ou en retard. » |
| `PAI_MARGE` | PAIRS | declarations_mensuelles, douane_articles, ref_nat | marge apparente 12 mois = (CA − achats estimés) / CA, où achats estimés = imports CAF + `tva_deductible_biens_services_local` / 0.19 ; z-score **négatif** vs groupe de pairs | z / `z` | « Marge apparente de 3 % contre 18 % en médiane pour les pairs (46.69, 10–49 salariés). » |
| `PAI_MAHALANOBIS` | PAIRS | idem + annexe1 | distance de Mahalanobis sur (marge, TVA déductible / collectée, CA / salarié, imports / CA) au centre du groupe de pairs ; norm : `clip((d − 2) / 4, 0, 1)` ; `fait_fr` cite la variable qui contribue le plus | distance / `d` | « Profil atypique pour son secteur, surtout le ratio TVA déductible / collectée (0,97 contre 0,62). » |
| `RES_FOURNISSEUR_PARTAGE` | RESEAU | graphe/metriques_noeuds | `nb_clients_partageant_fournisseur_nouveau` ; norm : `clip(n / 5, 0, 1)` | nombre / `n` | « Partage 2 nouveaux fournisseurs avec 4 autres entreprises apparues au même moment. » |
| `RES_COQUILLE` | RESEAU | graphe/metriques_noeuds | `part_achats_coquilles` (achats annexe V auprès de fournisseurs à profil coquille / achats totaux) ; norm : `clip(part / 0.3, 0, 1)` | part / `%` | « 38 % des achats déclarés proviennent de fournisseurs sans salarié ni activité déclarée. » |
| `RES_PROXIMITE_REDRESSE` | RESEAU | graphe/metriques_noeuds | `distance_entite_redressee` ; norm : 1 → 1.0, 2 → 0.5, 3 → 0.2, sinon 0 | distance / `d` | « Fournisseur direct d'une entreprise redressée pour fraude significative en 2025. » |
| `CMB_IMPORT_X_NOUV_FOURN` | COMBINAISON | (calculé par **C**) | `norm(CHG_IMPORTS) × norm(CHG_NOUVEAUX_FOURNISSEURS)` | produit / `x` | « Hausse des importations concentrée sur des fournisseurs nouveaux. » |
| `CMB_COQUILLE_X_TVA` | COMBINAISON | (calculé par **C**) | `norm(RES_COQUILLE) × norm(CHG_TVA_DEDUCTIBLE)` | produit / `x` | « Hausse de la TVA déductible liée à des achats auprès de fournisseurs coquilles. » |

**Groupe de pairs** = division NAT (2 chiffres) × classe de taille (0–2, 3–9, 10–49, 50+). Si le groupe compte < 30 entreprises → repli sur la division seule ; si < 30 encore → section NAT.

**Preuves (`preuves`)** : identifiants des lignes brutes qui justifient le signal, dans ce format :
`<table>:<identifiant>` — ex. `douane_articles:2026/301/0012345-002`, `employeur_annexe5:A5-2025-1000001BAM000-000012`, `adeb_paiements:ORD-2025-0001877`, `declarations_mensuelles:1000001BAM000:2026-07`. Au plus 50 préuves par signal (les plus fortes en montant).

---

## 4. Sortie de B → C

### 4.1 `data/signaux/signaux.parquet` (format long)
Une ligne par `mf` × `mois` × `code_signal` (y compris valeur_norm = 0, pour que C ait une matrice complète).

| Colonne | Type | Note |
|---|---|---|
| `mf` | str | |
| `mois` | str | 2024-09 … 2026-08 |
| `code_signal` | str | catalogue §3 (hors `CMB_*`) |
| `lentille` | str | COHERENCE, CHANGEMENT, PAIRS, RESEAU |
| `valeur_brute` | float | |
| `unite` | str | pts, x, z, n, %, d |
| `valeur_norm` | float | [0, 1] |
| `fait_fr` | str | phrase prête à afficher (vide si `valeur_norm` < 0.5) |
| `sources` | list<str> | ex. `["douane", "dgi_declarations"]` — valeurs : dgi_declarations, dgi_annexe5, dgi_annexe2, douane, adeb, graphe |
| `preuves` | list<str> | voir §3 |

### 4.2 `data/signaux/enjeux.parquet` (une ligne par `mf` × `mois`)
| Colonne | Type | Note |
|---|---|---|
| `mf`, `mois` | str | |
| `ca_observe_12m` | float | meilleure estimation du CA réel (max des reconstitutions : clients + ADEB, imports × (1 + marge pairs)) |
| `ca_declare_12m` | float | |
| `base_omise_12m` | float | max(0, observé − déclaré) |
| `tva_surdeduite_12m` | float | TVA déduite en trop (douane + achats coquilles) |
| `enjeu_estime` | float | droits éludés estimés = base_omise × 19 % + base_omise × marge pairs × 20 % + tva_surdeduite |
| `enjeu_bas`, `enjeu_haut` | float | fourchette : ±30 % élargie selon la confiance (D5 : Monte Carlo seulement si B est en avance après 01h00) |
| `confiance` | float | [0, 1] : f(nb de mois d'historique, nb de sources présentes, cohérence entre reconstitutions) |

### 4.3 `data/signaux/pairs_stats.parquet` et `groupes_pairs.parquet` (pour l'affichage « Pairs »)
- `groupes_pairs.parquet` : `mf`, `groupe` (ex. `46|10-49`), `libelle_groupe` (ex. `46 × 10–49 salariés`), `nb_pairs`.
- `pairs_stats.parquet` : `groupe`, `mois`, `indicateur` (MARGE, TVA_DED_SUR_COLL, CA_PAR_SALARIE, IMPORTS_SUR_CA), `mediane`, `p10`, `p90`, `nb`.

---

## 5. Sortie de C

### 5.1 `data/scores/scores.parquet` (une ligne par `mf` × `mois`)
| Colonne | Type | Note |
|---|---|---|
| `mf`, `mois` | str | |
| `score` | float | 0–100 = 100 × σ(logit) + bonus, plafonné à 100 |
| `score_base` | float | 100 × σ(b0) (score d'une entreprise sans aucun signal) |
| `contributions` | list<struct{code_signal: str, points: float}> | points_i = (w_i x_i / Σ w_j x_j) × (score_sans_bonus − score_base) ; + une ligne `NOUVEAU_SCHEMA` si bonus |
| `bonus_nouveau_schema` | float | 0–15 : si ≥ 2 signaux avec `valeur_norm` ≥ 0.8 ont un poids appris sous la médiane |
| `segment` | str | PRIORITAIRE (score ≥ 70), SURVEILLANCE (40–69), NORMAL (< 40), CONFIANCE (score < 15 **et** ≥ 24 mois d'historique **et** aucun signal actif sur 12 mois **et** aucun redressement passé) — seuils ajustables par C, publiés dans `/api/stats/synthese` |
| `priorite` | float | (score / 100) × `enjeu_estime` |
| `rang_priorite` | int | 1 = le plus prioritaire du mois |
| `action_suggeree` | str | voir §6.3 |
| `resume_fr` | str | 1 phrase : les 2–3 faits principaux + enjeu, ex. « Imports ×3,4, CA déclaré stable, 3 nouveaux fournisseurs dont 1 partagé avec 4 entreprises signalées. Enjeu estimé : 420 000 DT. » |

### 5.2 Autres fichiers de C
- `data/scores/modele.json` : `{ "intercept": b0, "poids": {code_signal: w}, "date_entrainement", "nb_exemples", "definition_cible": "REDRESSEMENT_MINEUR ou FRAUDE_SIGNIFICATIVE (poids 2)" }`.
- `data/scores/evaluation.json` : même contenu que `GET /api/evaluation`.
- `data/scores/decisions.csv` : `id_decision, mf, mois, date_heure, decision, justification, inspecteur, score_au_moment, segment_au_moment`.

---

## 6. API (C → D) — FastAPI, préfixe `/api`, JSON

Toutes les réponses d'exemple ci-dessous sont aussi déposées dans `data/mock/` (un fichier par endpoint, nom = chemin avec `_`). D développe sur ces fichiers ; l'URL de l'API est une variable d'environnement `NEXT_PUBLIC_API_URL` (vide = mode mock).

### 6.1 Énumérations
- `segment` : `PRIORITAIRE`, `SURVEILLANCE`, `NORMAL`, `CONFIANCE`
- `lentille` : `COHERENCE`, `CHANGEMENT`, `PAIRS`, `RESEAU`, `COMBINAISON`
- `decision` : `AUCUNE`, `RELANCE`, `DEMANDE_INFO`, `VERIFICATION`, `SIGNALEMENT_DOUANE`
- Libellés d'affichage des décisions : Aucune action · Relance de conformité volontaire · Demande d'information / contrôle sur pièces · Vérification approfondie · Signalement à la douane

### 6.2 Endpoints

**`GET /api/stats/synthese?mois=2026-08`** — bandeau du triage
```json
{
  "mois": "2026-08",
  "nb_entreprises": 5250,
  "par_segment": {"PRIORITAIRE": 17, "SURVEILLANCE": 43, "NORMAL": 4760, "CONFIANCE": 430},
  "nouveaux_prioritaires_du_mois": 9,
  "enjeu_total_prioritaires": 6840000.0,
  "seuils": {"PRIORITAIRE": 70, "SURVEILLANCE": 40, "CONFIANCE": 15}
}
```

**`GET /api/entreprises?mois=2026-08&segment=PRIORITAIRE&code_nat=46&gouvernorat=34&tri=priorite&page=1&taille=50`** — tous les filtres sont optionnels ; `tri` ∈ `priorite` (défaut), `score`, `delta_score`, `enjeu`.
```json
{
  "total": 17, "page": 1, "taille": 50,
  "items": [
    {
      "mf": "1000001BAM000",
      "raison_sociale": "Alpha SARL",
      "code_nat": "46.69", "libelle_nat": "Commerce de gros d'autres machines et équipements",
      "gouvernorat": "Sfax",
      "score": 76.0, "score_mois_precedent": 52.0, "delta_score": 24.0,
      "segment": "PRIORITAIRE",
      "enjeu_estime": 420000.0, "enjeu_bas": 310000.0, "enjeu_haut": 540000.0,
      "rang_priorite": 1,
      "resume_fr": "Imports ×3,4, CA déclaré stable, 3 nouveaux fournisseurs dont 1 partagé avec 4 entreprises signalées. Enjeu estimé : 420 000 DT.",
      "action_suggeree": "VERIFICATION",
      "derniere_decision": null
    }
  ]
}
```

**`GET /api/entreprises/{mf}?mois=2026-08`** — vue détail
```json
{
  "identite": {
    "mf": "1000001BAM000", "matricule_fiscal": "1000001/B/A/M/000",
    "raison_sociale": "Alpha SARL", "forme_juridique": "SARL",
    "code_nat": "46.69", "libelle_nat": "Commerce de gros d'autres machines et équipements",
    "gouvernorat": "Sfax", "date_debut_activite": "2014-03-01",
    "effectif": 23, "statut_oea": false, "centre_gestion": "CRCI"
  },
  "score": 76.0, "segment": "PRIORITAIRE", "confiance": 0.72,
  "enjeu": {"estime": 420000.0, "bas": 310000.0, "haut": 540000.0},
  "action_suggeree": "VERIFICATION",
  "resume_fr": "Imports ×3,4, CA déclaré stable, 3 nouveaux fournisseurs…",
  "trajectoire": [
    {"mois": "2025-09", "score": 27.0, "segment": "NORMAL"},
    {"mois": "2026-06", "score": 28.0, "segment": "NORMAL"},
    {"mois": "2026-07", "score": 52.0, "segment": "SURVEILLANCE"},
    {"mois": "2026-08", "score": 76.0, "segment": "PRIORITAIRE"}
  ],
  "contributions": [
    {"code_signal": "COH_IMPORT_VS_CA", "lentille": "COHERENCE", "points": 18.5, "valeur_norm": 0.95,
     "fait_fr": "Importations sur 6 mois : +240 % ; CA déclaré : +3 %.", "sources": ["douane", "dgi_declarations"], "nb_preuves": 14},
    {"code_signal": "RES_FOURNISSEUR_PARTAGE", "lentille": "RESEAU", "points": 11.2, "valeur_norm": 0.8,
     "fait_fr": "Partage un nouveau fournisseur étranger (FE00231) avec 4 autres entreprises apparues le même mois.", "sources": ["graphe", "douane"], "nb_preuves": 5}
  ],
  "pairs": {
    "groupe": "46 × 10–49 salariés", "nb_pairs": 212,
    "indicateurs": [
      {"nom": "Marge apparente", "entreprise": 0.03, "mediane_pairs": 0.18, "p10": 0.09, "p90": 0.27},
      {"nom": "TVA déductible / collectée", "entreprise": 0.97, "mediane_pairs": 0.62, "p10": 0.45, "p90": 0.78}
    ]
  },
  "series": [
    {"mois": "2026-06", "ca_declare": 95000.0, "imports_caf": 60000.0, "tva_deductible": 14000.0},
    {"mois": "2026-07", "ca_declare": 97000.0, "imports_caf": 150000.0, "tva_deductible": 31000.0}
  ],
  "decisions": [],
  "controles_passes": []
}
```
`series` couvre les 24 mois ; seuls deux mois sont montrés ici.

**`GET /api/entreprises/{mf}/preuves?signal=COH_IMPORT_VS_CA&mois=2026-08`** — drill-down
```json
{
  "code_signal": "COH_IMPORT_VS_CA",
  "fait_fr": "Importations sur 6 mois : +240 % ; CA déclaré : +3 %.",
  "lignes": [
    {"source": "douane_articles", "ref": "2026/401/0034567-001", "date": "2026-07-12",
     "libelle": "NDP 84798997000 — Machines diverses — Chine — FE00231",
     "montant": 88000.0,
     "champs": {"pays_origine": "CN", "quantite": 4, "unite": "U", "prix_unitaire_tnd": 22000.0, "circuit": "V"}}
  ]
}
```

**`GET /api/entreprises/{mf}/reseau?mois=2026-08&profondeur=2`**
```json
{
  "noeuds": [
    {"id": "1000001BAM000", "label": "Alpha SARL", "type": "ENTREPRISE", "segment": "PRIORITAIRE", "est_coquille": false, "centre": true},
    {"id": "FE00231", "label": "Shenzhen Tools Co.", "type": "FOURNISSEUR_ETRANGER", "segment": null, "est_coquille": false, "centre": false},
    {"id": "1000311KAM000", "label": "Kappa Equipements SARL", "type": "ENTREPRISE", "segment": "PRIORITAIRE", "est_coquille": false, "centre": false}
  ],
  "aretes": [
    {"source": "1000001BAM000", "cible": "FE00231", "type_relation": "IMPORT_FOURNISSEUR", "montant": 310000.0, "premiere_date": "2026-06-04", "nouvelle": true},
    {"source": "1000311KAM000", "cible": "FE00231", "type_relation": "IMPORT_FOURNISSEUR", "montant": 275000.0, "premiere_date": "2026-06-11", "nouvelle": true}
  ]
}
```
`type` ∈ `ENTREPRISE`, `FOURNISSEUR_ETRANGER`, `ACHETEUR_PUBLIC`. `type_relation` = valeurs de `graphe/aretes.csv`.

**`POST /api/entreprises/{mf}/decision`**
```json
// requête
{"mois": "2026-08", "decision": "VERIFICATION", "justification": "Écart imports/CA et fournisseur coquille confirmés.", "inspecteur": "demo"}
// réponse
{"id_decision": "DEC-000001", "enregistre": true, "date_heure": "2026-09-26T03:12:00"}
```

**`POST /api/assistant`**
```json
// requête
{"mf": "1000001BAM000", "mois": "2026-08", "question": "Pourquoi le risque d'Alpha a-t-il augmenté ?", "historique": [{"role": "user", "contenu": "..."}, {"role": "assistant", "contenu": "..."}]}
// réponse
{
  "reponse": "Le score est passé de 28 à 76 en deux mois pour trois raisons principales : …",
  "citations": [{"type": "signal", "ref": "COH_IMPORT_VS_CA"}, {"type": "preuve", "ref": "douane_articles:2026/401/0034567-001"}],
  "mode": "llm"
}
```
`mode` ∈ `llm` (Qwen local) ou `modele_texte` (repli déterministe si le LLM est indisponible ou dépasse 20 s). Outils disponibles côté LLM : `get_entreprise`, `get_preuves`, `get_reseau`, `rediger_lettre_demande_info`. **Aucun chiffre ne doit apparaître dans une réponse s'il n'est pas dans les données retournées par ces outils.**

**`GET /api/evaluation`** — pour la page et la slide Impact
```json
{
  "top_n": 50,
  "periode_test": "2025-09 → 2026-08",
  "methodes": [
    {"nom": "Basira", "taux_detection_top_n": 0.78, "montant_moyen_par_controle": 185000.0,
     "fausses_alertes_croissance_legitime": 1, "avance_detection_mois": 2.4},
    {"nom": "Règle statique (type SAR)", "taux_detection_top_n": 0.34, "montant_moyen_par_controle": 72000.0,
     "fausses_alertes_croissance_legitime": 11, "avance_detection_mois": 0.0},
    {"nom": "Sélection aléatoire", "taux_detection_top_n": 0.08, "montant_moyen_par_controle": 15000.0,
     "fausses_alertes_croissance_legitime": 1, "avance_detection_mois": null}
  ],
  "note": "Chiffres calculés sur données synthétiques ; vérité terrain cachée au modèle."
}
```
⚠️ Les nombres ci-dessus sont des **exemples de format**, pas des résultats : C les remplace par les vrais.

### 6.3 Action suggérée (règle fixe, calculée par C)
| Condition | `action_suggeree` |
|---|---|
| PRIORITAIRE et enjeu ≥ 100 000 DT | `VERIFICATION` |
| PRIORITAIRE et enjeu < 100 000 DT | `DEMANDE_INFO` |
| PRIORITAIRE ou SURVEILLANCE, et plus de 50 % des points viennent de `COH_VALEUR_REF` / `CHG_NOUVELLES_CATEGORIES` | `SIGNALEMENT_DOUANE` |
| SURVEILLANCE | `RELANCE` |
| NORMAL, CONFIANCE | `AUCUNE` (CONFIANCE : affiché comme « candidat à la facilitation ») |

---

## 7. Cas héros (identiques pour A, B, C, D)

| `mf` | Raison sociale | Scénario | Attendu au mois 2026-08 |
|---|---|---|---|
| `1000001BAM000` | Alpha SARL | A (minoration) + nouveau fournisseur étranger `FE00231` partagé avec 4 autres importateurs A démarrant le même mois | PRIORITAIRE, trajectoire ~28 (06) → ~52 (07) → ~76 (08), signaux COH_IMPORT_VS_CA, CHG_IMPORTS, CHG_NOUVEAUX_FOURNISSEURS, RES_FOURNISSEUR_PARTAGE, CMB_IMPORT_X_NOUV_FOURN |
| `1000002CAM000` | Beta Import SUARL | C | PRIORITAIRE ou SURVEILLANCE, COH_VALEUR_REF → action SIGNALEMENT_DOUANE |
| `1000003DAM000` | Gamma Travaux SA | D | PRIORITAIRE, COH_ADEB_VS_CA |
| `1000004EAM000` | Delta Trade SARL | E | PRIORITAIRE, CHG_DEPOTS + CHG_IMPORTS |
| `1000005FAM000` | Epsilon Textile SARL | F | SURVEILLANCE, PAI_MARGE, PAI_MAHALANOBIS |
| `1000006GAM000` | Zeta Industries SA | Croissance légitime | NORMAL malgré CHG_IMPORTS élevé (aucun signal de cohérence) |
| `1000007HAM000` | Eta Pharma SA | Citoyen modèle, OEA | CONFIANCE |
| `1000008JAM000` | Omega Négoce SUARL | Coquille d'un réseau B (5 clients non-héros, depuis 2025-03) | PRIORITAIRE, COH_CLIENTS_VS_CA très élevé ; ses 5 clients : RES_COQUILLE + CHG_TVA_DEDUCTIBLE |

Ces 8 entreprises doivent exister dès l'**échantillon de 18h00** de A et dans les **mocks** de D.

---

## 8. Calendrier des livraisons entre lots

| Heure | Producteur → consommateur | Livrable |
|---|---|---|
| 17h00 | contrat → D | `data/mock/*.json` écrits à partir de ce fichier |
| 18h00 | A → B, C | échantillon `data/raw/` (≈ 200 entreprises dont les 8 héros) + `graphe/` |
| 18h00 | C → D | API FastAPI qui sert les mocks (mêmes routes) |
| 20h00 | B → C | `signaux.parquet` + `enjeux.parquet` sur l'échantillon |
| 21h00 | tous | **point mentor** : les 8 héros visibles de bout en bout (signaux réels, score provisoire) |
| 22h00 | C → D | API branchée sur les vrais scores de l'échantillon |
| 23h00 | A → B | volume complet (5 250 entreprises) |
| 00h30 | B → C | signaux sur le volume complet |
| 01h30 | C → D | scores complets, évaluation, assistant |
| 04h00 | tous | **gel fonctionnel** (plus de nouvelle fonctionnalité) |
| 05h00 | D | vidéo de démo de secours |
| 07h30 | tous | dépôt des 3 livrables (gel du code 08h00, annoncé 08h30 à l'oral — à confirmer) |

---

## Journal des changements
| Heure | Qui | Changement |
|---|---|---|
| — | — | version initiale |

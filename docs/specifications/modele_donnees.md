# Basira — Modèle de données (réel → synthétique)

> **But.** Les données synthétiques de Basira doivent avoir **la même forme que les données réelles** des systèmes de l'État sur lesquels Basira viendrait se brancher (DGI, Douane/SINDA, ADEB, déclaration de l'employeur/TEJ). Ce document :
> 1. résume ce que contiennent réellement ces systèmes (recherche documentaire, **sources numérotées [n] en fin de document**) ;
> 2. fixe le **dictionnaire des données synthétiques** que la personne A génère ;
> 3. fixe la **calibration** (volumes, distributions) et les **scénarios de fraude** injectés.
>
> Le format d'échange entre les lots (signaux, scores, API) est dans [`contrat_integration.md`](contrat_integration.md). En cas de conflit, **le contrat fait foi** pour les interfaces, ce document fait foi pour les données brutes.
>
> **Niveaux de confiance :** **[OFF]** = document officiel tunisien · **[SEC]** = source secondaire (presse, cabinets, OCDE/BM citant des données officielles) · **[INF]** = déduction de notre part, à présenter comme hypothèse de conception. **⚠️ NON CONFIRMÉ** = élément qu'on n'a pas pu vérifier publiquement.

---

## Partie 1 — Ce que contiennent les systèmes réels

### 1.1 Identifiant : le matricule fiscal
- Format écrit : `NNNNNNN/K/T/C/EEE`, ex. `1234567/A/A/M/000` [SEC 1, 2] :
  - `NNNNNNN` : 7 chiffres, numéro unique [OFF 3 : champ « Matricule Fiscal N(7) »]
  - `K` : lettre clé de contrôle (23 lettres, sans I, O, U ; algorithme modulo 23 rapporté par des blogs, ⚠️ non vérifié) [OFF 3 pour le champ, SEC 2 pour l'algorithme]
  - `T` : code TVA — **A** assujetti obligatoire, **B** assujetti par option, **P** partiel, **F** forfaitaire, **N** non assujetti [SEC 1, 2]
  - `C` : code catégorie — **M** personne morale, **C** commerçant/industriel personne physique, **P** profession libérale, **N** employeur non soumis [SEC 1, 2]
  - `EEE` : établissement — `000` siège, `001`–`999` établissements secondaires [OFF 3]
- Forme compacte à 13 caractères utilisée dans la facture électronique TTN : `1234567AAM000` [SEC 4]. **C'est la clé de jointure retenue pour Basira (`mf`).**
- Personnes physiques : type d'identifiant du bénéficiaire dans la déclaration de l'employeur : 1 = matricule fiscal, 2 = CIN (8 chiffres), 3 = carte de séjour, 4 = non-résident [OFF 3].
- Depuis la loi 2018-52 (RNE), l'identifiant fiscal est l'identifiant unique de l'entreprise [OFF 5].

### 1.2 Dossier fiscal : la déclaration d'existence
Formulaire officiel (arabe) [OFF 6] :
- identification : matricule fiscal (+ codes TVA, catégorie, établissement), n° CNSS, pièce d'identité, registre de commerce ;
- raison sociale, adresse (gouvernorat, délégation, code postal), nationalité, **forme juridique**, résident/non-résident, **capital social** ;
- **activité principale** (libellé, code administratif, date de début), activité secondaire ;
- **régime** : BIC réel / réel simplifié / régime simplifié art. 18 LF 2016 ; BNC réel / forfait d'assiette ; **statut TVA** (obligatoire / partiel / option) ;
- siège, **nombre de salariés**, établissements secondaires, avantages fiscaux, **date de clôture de l'exercice**, représentant légal (PDG, gérant…).
- Attribués ensuite par l'administration (non présents sur le formulaire) : recette de rattachement, gestion DGE / DME / centre régional [INF].

### 1.3 Nomenclature des activités : NAT 2009
- Norme tunisienne NT 120.01, alignée sur NACE Rév.2 / CITI Rév.4 : **section** (lettre) > **division** (2 chiffres) > **groupe** (3) > **classe** (4), ex. G > 46 > 46.6 > 46.69 [SEC 7, OFF 8].
- La DGI a ses propres codes d'activité (non publiés, ⚠️) ; le panel l'a d'ailleurs souligné : chaque système a son propre référentiel → besoin d'un **référentiel national unique** (voir `Input/conf2_*_clean.md` §3). Nous utilisons NAT 2009 partout et le signalons comme prérequis de mise en production.

### 1.4 Déclaration mensuelle des impôts (formulaire 2023) [OFF 9]
- En-tête : année, mois, **code déclaration** (0 spontanée, 1 régularisation, 2 rectificative, 3 suspension forcée, 4 suspension d'activité), MF, cases des impôts déclarés.
- Retenues à la source : lignes 1–30 (assiette, taux, montant retenu).
- **TVA** : CA taxable par taux **19 %, 13 %, 7 %** ; TVA collectée ; TVA déductible **sur immobilisations**, **sur biens et services locaux**, **sur importations** ; **TVA retenue à la source 25 %** (subie sur paiements publics ≥ 1 000 DT) et 100 % (non-établis) ; régularisations ; **crédit de TVA reporté** ; TVA à payer ou crédit ; exportations, ventes en suspension, CA exonéré.
- Autres : TFP (1 % industrie / 2 % autres), FOPROLOS (1 % masse salariale), droit de consommation, TCL (0,2 % CA local), taxe hôtelière, droits de timbre.
- Échéance : le **28 du mois suivant** pour les personnes morales (15 pour les personnes physiques) [SEC 10].
- Pénalités de retard (CDPF art. 81) : **0,75 % par mois** + 1,25 % (≤ 60 jours) ou 2,5 % (> 60 jours) [SEC 10, 11].
- ⚠️ La page ministérielle « aperçu général sur la fiscalité » est obsolète (taux TVA 18/6/12, IS 25 %) : ne pas l'utiliser.

### 1.5 Déclaration annuelle de l'IS
- Taux (LF 2025, loi 2024-48 art. 37, bénéfices à partir du 1/1/2024) : **20 % taux normal**, 10 % (activités spécifiques), 35 % (télécoms, pétrole, concessionnaires auto), 40 % (banques, assurances) [OFF via 12].
- Minimum d'impôt : 0,2 % du CA TTC (min. 300 DT) [SEC 13]. Trois **acomptes provisionnels** de 30 % (28 juin, 28 sept., 28 déc.) [SEC 14]. Contribution sociale de solidarité (CSS) 3–4 % [SEC 15].
- Échéance de dépôt : 25 mars pour les exercices clos au 31/12 [INF].

### 1.6 Déclaration de l'employeur (cahier des charges officiel) [OFF 3, 16]
- Fichiers texte à longueur fixe : récapitulatif `DECEMP_YY` + annexes `ANXEMP_n_YY`. Seules les annexes avec des montants sont déposées.
- **Annexes** :
  - **I** — salaires, pensions (par salarié : CIN, situation familiale, dates, revenu imposable, avantages, IRPP retenu, CSS, net)
  - **II** — honoraires, commissions, courtages, **loyers**, jetons de présence, rémunérations de performance (type de montant : 1 honoraires, 2 commissions, 3 courtages, 4 loyers, 5 activités non commerciales, 6 performance)
  - III — revenus de capitaux mobiliers
  - IV — paiements aux non-résidents
  - **V — achats ≥ 1 000 DT TTC** : pour chaque **fournisseur** (identifié par son matricule fiscal), montant payé, retenue 0,5 / 1 / 1,5 % selon le régime IS du fournisseur, **retenue TVA**, net payé. ⭐ **C'est la source de recoupement clé** : chaque entreprise déclare ce qu'elle a payé à ses fournisseurs → on reconstitue le CA des fournisseurs.
  - VI — ristournes, ventes aux forfaitaires, recettes en espèces
  - VII — montants payés pour le compte de tiers
- **Code acte** : 0 spontané, 1 régularisation, **2 redressement** (une correction post-contrôle est visible dans les données).
- Taux stockés en N5 (% × 100 : `00150` = 1,5 %), montants en N15.
- **Plateforme TEJ** (tej.finances.gov.tn) : obligatoire pour tous depuis le 1/1/2026 pour les certificats de retenue et la déclaration de l'employeur ; saisie ou import XML (schéma XML ⚠️ non publié) [SEC 17, 18]. Échéance annuelle : 28 février [INF].

### 1.7 Taux de retenue à la source (en vigueur) [OFF 9, 3 ; SEC 19]
| Nature | Taux |
|---|---|
| Honoraires versés aux sociétés et personnes au réel | 3 % |
| Honoraires / commissions / loyers (autres résidents) | 10 % |
| Achats ≥ 1 000 DT TTC (fournisseur IS 10 % / 20 % / 35–40 %) | 0,5 % / 1 % / 1,5 % |
| TVA retenue par l'État, collectivités, entreprises publiques (paiements ≥ 1 000 DT) | 25 % de la TVA |
| Livraisons e-commerce pour vendeurs sans MF (LF 2025, via TEJ en temps réel depuis 2026) | 3 % |

### 1.8 Douane : la déclaration en détail (DDM) dans SINDA
- Dépôt électronique via **TTN** (liasse unique), traitement dans **SINDA** ; affectation automatique à un **circuit vert / orange / rouge** (pas de circuit bleu) [OFF 20].
  - Vert : BAE automatique · Orange : contrôle documentaire (inspecteur liquidateur + réviseur) · Rouge : visite physique.
  - Issues : conforme (BAE), demande de complément, **litige**, **infraction relevée**, reclassement orange → rouge [OFF 20].
- Répartition 2025 : ~**1,5 million** de déclarations, **70 % vert / 22 % orange / 7 % rouge** ; délai de dédouanement 2,5 j (0,7 j pour les OEA) [SEC 21].
- Mai 2026 : ajout d'un **module de machine learning** au système national de sélectivité (entrées : nature, origine, valeur déclarée, historique, profil opérateur) [SEC 22].
- **Types de déclaration** (codes officiels, extraits) [OFF 23] : SA530 admission temporaire pour perfectionnement, SA531 entrepôt industriel, SE737 entrepôt public, SE738–741 entrepôts privés, ET276 exportation temporaire, SE777 / UC830 / TE842 (dépôt sans manifeste). ⚠️ **Le code de la mise à la consommation ordinaire n'a pas été trouvé** → placeholder synthétique `IC100`.
- **Taxes liquidées** (codes officiels du tarif) [OFF 24] : **DD 001** (droit de douane, base CAF), **DC 014** (droit de consommation), **FODEC 093**, **TVA 105** (base = CAF + DD + taxes du groupe 0), **RPD 473** (redevance, 3 % des droits), **AIR 480** (avance d'impôt sur le revenu). Taux TVA 19 / 13 / 7 %, DD moyen NPF 19,4 % [SEC 25].
- **Nomenclature** : SH6 → **NGP 10 chiffres** → **NDP 11 chiffres** (NGP + chiffre clé), ex. `851712` → `8517120000` → `85171200005` ; ~17 500 codes [SEC 26, OFF 27].
- **Valeur en douane** : valeur transactionnelle (CAF) puis méthodes de substitution (marchandises identiques, similaires, déductive, calculée, dernier recours) — Code des douanes art. 22–36 [OFF 28]. La **Direction de la Valeur** gère une **banque de données de la valeur** et compare les valeurs déclarées [OFF 29] → nous modélisons une table de prix de référence par code NDP [INF].
- Champs de la DDM (liste reconstituée ; la numérotation officielle des cases ⚠️ n'est pas publiée) [OFF 20, 30 ; INF] : n° et type de déclaration, bureau, date d'enregistrement, circuit, déclarant (commissionnaire), importateur (MF + **code en douane**), pays d'origine / de provenance, mode de transport, Incoterm, devise, taux de change, valeur facture, fret, assurance, **valeur CAF en TND** ; par article : code NDP, désignation, poids net/brut, colis, quantité et unité (QCS), valeur ; liquidation par taxe (code, base, taux, montant).
- SINDA n'efface jamais une déclaration : les rectifications se font par écritures de contre-passation [SEC 31].
- **OEA** (Code des douanes art. 118–120) : 3 catégories (simplifications / sécurité-sûreté / complet), condition de 3 ans d'historique douanier, fiscal et financier sans reproche ; **165 entreprises certifiées** (mars 2024) [OFF 32, SEC 33].
- ⚠️ **Non confirmés** : format du n° de déclaration, codes bureaux, format du code en douane → placeholders synthétiques documentés en Partie 2.

### 1.9 Dépense publique : ADEB
- ADEB = système d'aide à la décision budgétaire, suivi de toute la chaîne de la dépense (État central, régional, EPA, municipal) ; alimente le portail open data **Mizaniatouna** [SEC 34, OFF 35].
- Chaîne : **engagement** (visa du contrôleur des dépenses, décret 2012-2878) → **liquidation** → **ordonnancement** → visa du comptable assignataire → **paiement** [OFF 36, 37].
- Nomenclature (LOB 2019-15, arrêté du 10/04/2019) : **mission → programme → sous-programme → activité** ; par nature : titre / partie / article / paragraphe [OFF 38, 39].
- Retenues sur paiements publics : **TVA 25 %** (achats ≥ 1 000 DT TTC, depuis 2016) [OFF 40] ; IS/IRPP **1 %** (fournisseur IS 20 %) / 1,5 % [SEC 19].
- Vérification de la situation fiscale du fournisseur avant paiement : service **E-Sit~Fisc** (LF 2014 art. 62) [OFF 41] ; pas de compensation opposable par le débiteur de l'État (Code de la comptabilité publique) [OFF 42].
- ⚠️ La liste exacte des champs d'ADEB n'est pas publiée → schéma **[INF]** ; les jeux « exécution des marchés publics » des communes sur data.gov.tn (extraits ADEB municipal) sont la référence réelle la plus proche [OFF 43].

### 1.10 Contrôle fiscal
- **Vérification préliminaire** : contrôle sur pièces à partir des déclarations et recoupements, sans avis préalable, notification dans les 90 jours [SEC 44].
- **Vérification approfondie** (CDPF art. 38–41) : avis ≥ 15 jours avant, durée sur place ≤ 6 mois (1 an sans comptabilité), totale ou partielle [OFF/SEC 44].
- **Taxation d'office** (CDPF art. 47–52) : en cas de désaccord, non-réponse ou défaut de déclaration [OFF/SEC 44].
- Issues : sans redressement, accord, taxation d'office, contentieux ; montants redressés par impôt + pénalités.
- Statistiques : **aucune publication officielle** du nombre de contrôles ni des montants ⚠️. Taux de couverture ≤ **2,5 %** (≈ 2 200 agents pour ≈ 750 000 contribuables) [SEC 45].

### 1.11 Systèmes de la DGI
- **RAFIK** (Rationalisation de l'Action Fiscale et Comptable) : organisé autour du **compte fiscal** du contribuable, collecte les informations de recoupement [SEC 46].
- **SADEC** (Système d'Aide à la Décision et à l'Encadrement du Contrôle fiscal) : compare les informations recoupées aux déclarations pour programmer les contrôles [SEC 47].
- **SAR** (gestion selon l'approche risque) et **SADEC 2** (data lake + module IA) : ⚠️ **uniquement cités oralement** par le directeur DGI lors de la conférence ; aucune source publique.

### 1.12 Feuille de route (non généré dans le prototype)
- **Facture électronique** (TTN « El Fatoora », format XML **TEIF** 1.8.8, signature XAdES, référence TTN) : obligatoire pour les prestataires de services depuis janvier 2026 (LF 2026) ; les noms de balises (ex. TVA = `I-1602`) sont ⚠️ à vérifier dans le guide officiel [SEC 4, 48, 49].
- **Caisses enregistreuses connectées** (décret 2019-1126) : restauration dès le 1/11/2025, généralisation progressive jusqu'en 2028 [SEC 50].
- Données des **transporteurs/livreurs** (retenue 3 % e-commerce) [SEC 51].

---

## Partie 2 — Dictionnaire des données synthétiques (`data/raw/`)

**Conventions communes** (rappel du contrat) : clé `mf` = 13 caractères (`1234567AAM000`) ; mois `AAAA-MM` ; dates ISO `AAAA-MM-JJ` ; montants en **TND, 3 décimales** ; taux en **pourcentage** (19.0) ; CSV UTF-8, séparateur `,`, en-tête en première ligne. Les identifiants **synthétiques par nature** (non publiés dans la réalité) sont marqués 🧪.

### 2.1 `contribuables.csv` — dossier fiscal (1 ligne par entreprise)
| Colonne | Type | Exemple | Valeurs / règle | Réel |
|---|---|---|---|---|
| `mf` | str(13) | `1000001BAM000` | clé unique | 1.1 |
| `matricule_fiscal` | str | `1000001/B/A/M/000` | forme affichée | 1.1 |
| `code_tva` | str(1) | `A` | A, B, P, F, N | 1.1 |
| `code_categorie` | str(1) | `M` | M (toutes nos entreprises sont des personnes morales) | 1.1 |
| `raison_sociale` | str | `Alpha SARL` | | 1.2 |
| `forme_juridique` | str | `SARL` | SARL, SUARL, SA | 1.2 |
| `code_nat` | str | `46.69` | classe NAT 2009 (voir `ref_nat.csv`) | 1.3 |
| `section_nat` | str(1) | `G` | | 1.3 |
| `date_debut_activite` | date | `2014-03-01` | | 1.2 |
| `gouvernorat_code` | int | `34` | codes INS (voir `ref_gouvernorats.csv`) | 1.2 |
| `regime_fiscal` | str | `REEL` | REEL, REEL_SIMPLIFIE | 1.2 |
| `taux_is` | float | `20.0` | 10, 20, 35 | 1.5 |
| `statut_export` | str | `ONSHORE` | ONSHORE, TOTALEMENT_EXPORTATRICE | 1.8 |
| `centre_gestion` | str | `CRCI` | DGE, DME, CRCI | 1.2 [INF] |
| `effectif_declare` | int | `23` | à la déclaration d'existence (l'effectif réel annuel est dans l'annexe I) | 1.2 |
| `capital_social` | float | `50000.000` | | 1.2 |
| `date_cloture_exercice` | str | `12-31` | | 1.2 |
| `code_en_douane` | str | `CD1000001` 🧪 | vide si jamais importateur | 1.8 |
| `statut_oea` | bool | `false` | | 1.8 |
| `date_oea` | date | | vide si non OEA | 1.8 |
| `date_cessation` | date | | vide si active | 1.2 |

### 2.2 `declarations_mensuelles.csv` — une ligne par entreprise × mois (y compris mois non déposés)
| Colonne | Type | Règle |
|---|---|---|
| `mf`, `mois` | str | clé composite |
| `statut_depot` | str | DEPOSEE, NON_DEPOSEE |
| `code_declaration` | int | 0 spontanée, 1 régularisation, 2 rectificative (vide si non déposée) |
| `date_limite` | date | le 28 du mois suivant |
| `date_depot` | date | vide si non déposée |
| `jours_retard` | int | max(0, date_depot − date_limite) |
| `ca_taxable_19`, `ca_taxable_13`, `ca_taxable_7` | float | CA HT par taux |
| `ca_exonere`, `ca_export` | float | |
| `ca_total_declare` | float | somme des lignes CA (**colonne de référence pour « CA déclaré »**) |
| `tva_collectee` | float | Σ CA × taux |
| `tva_deductible_immobilisations` | float | |
| `tva_deductible_biens_services_local` | float | |
| `tva_deductible_import` | float | à comparer à la TVA liquidée en douane (code 105) |
| `tva_retenue_source_subie` | float | retenue 25 % subie sur paiements publics (à comparer à ADEB) |
| `credit_tva_reporte` | float | crédit du mois précédent |
| `tva_a_payer` | float | ≥ 0 |
| `credit_tva_fin_mois` | float | ≥ 0 |
| `retenues_source_versees` | float | total des retenues opérées par l'entreprise (lignes 1–30) |
| `tfp`, `foprolos`, `tcl` | float | |

### 2.3 `declarations_is.csv` — une ligne par entreprise × exercice (2023, 2024, 2025)
`mf`, `exercice`, `date_depot`, `ca_local`, `ca_export`, `resultat_comptable`, `resultat_fiscal`, `taux_is`, `is_du`, `minimum_impot`, `acomptes_verses`, `retenues_imputees`, `css`, `is_a_payer`, `credit_is`. Règle : `ca_local + ca_export` ≈ Σ `ca_total_declare` des 12 mois (écart ≤ 2 % sauf scénario).

### 2.4 `employeur_annexe1_synthese.csv` — annexe I agrégée (payeur × exercice)
`mf`, `exercice`, `code_acte` (0/1/2), `nb_salaries`, `masse_salariale_brute`, `irpp_retenu`, `css_retenue`. *(Simplification assumée : l'annexe I réelle est nominative par salarié ; nous n'en gardons que l'agrégat.)*

### 2.5 `employeur_annexe2.csv` — honoraires, loyers, commissions
`id_ligne` (ex. `A2-2025-1000001BAM000-000012`), `mf_payeur`, `exercice`, `code_acte`, `type_id_beneficiaire` (1 = MF, 2 = CIN), `id_beneficiaire` (mf si type 1), `type_montant` (1 honoraires, 2 commissions, 3 courtages, 4 loyers, 5 non commercial, 6 performance), `montant_brut`, `taux_retenue`, `retenue`, `montant_net`.

### 2.6 `employeur_annexe5.csv` — ⭐ achats ≥ 1 000 DT TTC (payeur × fournisseur × exercice)
| Colonne | Type | Règle |
|---|---|---|
| `id_ligne` | str | `A5-<exercice>-<mf_payeur>-<n°6>` |
| `mf_payeur` | str | le client qui déclare |
| `exercice` | int | 2023, 2024, 2025 (l'exercice N est disponible à partir de **mars N+1**) |
| `code_acte` | int | 0/1/2 |
| `mf_fournisseur` | str | le fournisseur (doit exister dans `contribuables.csv`) |
| `montant_ttc` | float | total payé dans l'année |
| `taux_retenue` | float | 0.5, 1.0, 1.5 selon `taux_is` du fournisseur |
| `retenue_is` | float | |
| `retenue_tva` | float | > 0 seulement si le payeur est un organisme public (sinon 0) |
| `montant_net` | float | |
| `premiere_annee_relation` | int | première année où ce couple apparaît (sert à la nouveauté) |

### 2.7 `douane_declarations.csv` — en-tête DDM
| Colonne | Type | Exemple / valeurs |
|---|---|---|
| `num_declaration` | str | `2026/301/0012345` 🧪 (année/bureau/séquence) |
| `type_declaration` | str | `IC100` 🧪 (mise à la consommation), `SA530`, `SA531`, `SE737` |
| `bureau_code` | str | voir `ref_codes.csv` 🧪 (301 Radès, 302 La Goulette, 303 Tunis-Carthage, 401 Sfax, 402 Sousse, 501 Bizerte, 601 Ras Jedir) |
| `date_enregistrement` | date | |
| `mf_importateur`, `code_en_douane` | str | |
| `id_declarant` | str | commissionnaire 🧪 `COM0042` |
| `pays_provenance` | str | ISO-2 |
| `mode_transport` | str | MARITIME, AERIEN, ROUTIER |
| `incoterm` | str | FOB, CFR, CIF, EXW, DAP |
| `devise`, `taux_change` | str, float | EUR, USD, CNY… |
| `valeur_facture_devise`, `fret_tnd`, `assurance_tnd` | float | |
| `valeur_caf_tnd` | float | = Σ `valeur_caf_tnd` des articles |
| `circuit` | str | V, O, R |
| `resultat_controle` | str | CONFORME, COMPLEMENT_DEMANDE, LITIGE, INFRACTION |
| `total_droits_taxes_tnd` | float | Σ liquidation |

### 2.8 `douane_articles.csv` — articles de la DDM
`id_article` (`<num_declaration>-<n°3>`), `num_declaration`, `num_article`, `code_ndp` (11 chiffres), `code_sh6`, `chapitre_sh` (2 chiffres), `designation`, `id_fournisseur_etranger`, `pays_origine` (ISO-2), `poids_net_kg`, `quantite`, `unite` (KG, U, L, M2…), `valeur_caf_tnd`, `prix_unitaire_tnd` (= valeur / quantité).

### 2.9 `douane_liquidation.csv` — taxes par article
`id_article`, `code_taxe` (001 DD, 093 FODEC, 105 TVA, 473 RPD, 480 AIR), `base_tnd`, `taux`, `montant_tnd`. Règles : TVA 105 base = CAF + DD + FODEC ; RPD = 3 % de Σ droits ; la **TVA 105 d'un mois** doit correspondre (±5 %) à `tva_deductible_import` de la déclaration mensuelle du mois suivant, **sauf scénario**.

### 2.10 `fournisseurs_etrangers.csv`
`id_fournisseur` (🧪 `FE00001`), `nom`, `pays` (ISO-2), `date_premiere_apparition`, `chapitres_sh_principaux`.

### 2.11 `adeb_paiements.csv` — ordonnances de paiement (schéma [INF])
`num_ordonnance` (🧪 `ORD-2025-0001877`), `exercice`, `mission_code`, `mission_libelle`, `programme_code`, `imputation_nature` (ex. `INVESTISSEMENT`, `FONCTIONNEMENT`), `id_acheteur_public` (voir `ref_acheteurs_publics.csv`), `mf_beneficiaire`, `nature_achat` (MARCHE_TUNEPS, CONSULTATION, BON_COMMANDE), `num_engagement`, `date_engagement`, `date_ordonnancement`, `date_paiement`, `montant_ht`, `montant_tva`, `montant_ttc`, `retenue_tva_25`, `retenue_is` (1 % ou 1,5 %), `net_a_payer`, `comptable_assignataire`.

### 2.12 `historique_controles.csv` — contrôles passés (⭐ étiquettes pour l'apprentissage)
| Colonne | Type | Valeurs |
|---|---|---|
| `id_controle` | str | 🧪 `CTL-2025-000123` |
| `mf` | str | |
| `type_controle` | str | VERIF_PRELIMINAIRE, VERIF_APPROFONDIE_PARTIELLE, VERIF_APPROFONDIE_TOTALE |
| `origine_selection` | str | PROGRAMME_RISQUE (règle statique type SAR), RECOUPEMENT, DENONCIATION, ALEATOIRE |
| `date_avis` | date | entre 2024-10 et 2026-06 |
| `date_debut`, `date_fin` | date | |
| `periode_debut`, `periode_fin` | str (mois) | période vérifiée |
| `impots_verifies` | str | ex. `TVA;IS;RS` |
| `date_notification_resultats` | date | |
| `issue` | str | SANS_REDRESSEMENT, ACCORD, TAXATION_OFFICE, CONTENTIEUX |
| `categorie_resultat` | str | **CONFORME, REDRESSEMENT_MINEUR, FRAUDE_SIGNIFICATIVE** (les « 3 catégories » du directeur DGI) |
| `montant_redresse_tva`, `montant_redresse_is`, `montant_redresse_rs` | float | |
| `penalites` | float | |
| `montant_recouvre` | float | |

### 2.13 Tables de référence (`data/raw/ref_*.csv`)
- `ref_nat.csv` : `code_nat`, `libelle`, `section_nat`, `division`, `marge_brute_reference` (benchmark, voir 3.4), `part_importatrice` (probabilité d'importer).
- `ref_gouvernorats.csv` : `gouvernorat_code`, `libelle`, `poids_entreprises` (les 24 codes INS, voir 3.2).
- `ref_ndp.csv` : `code_ndp`, `code_sh6`, `chapitre_sh`, `designation`, `unite`, `prix_reference_tnd` (par unité), `taux_dd`, `taux_tva`, `taux_fodec`.
- `ref_taux_retenue.csv` : `nature`, `taux` (table 1.7).
- `ref_codes.csv` : `domaine` (CIRCUIT, TYPE_DECLARATION, BUREAU, CODE_TAXE, TYPE_MONTANT, CODE_ACTE…), `code`, `libelle`, `synthetique` (bool 🧪).
- `ref_acheteurs_publics.csv` : `id_acheteur_public`, `libelle` (ministère, commune, entreprise publique), `type`, `gouvernorat_code`.

### 2.14 `graphe/` — produit par A à partir des tables ci-dessus
- `graphe/aretes.csv` : `source`, `cible`, `type_relation` (IMPORT_FOURNISSEUR, ACHAT_LOCAL_A5, HONORAIRES_A2, PAIEMENT_PUBLIC), `montant_total`, `premiere_date`, `derniere_date`. Sens : **l'argent va de `source` vers `cible`** (client → fournisseur).
- `graphe/metriques_noeuds.csv` (une ligne par `mf` × `mois`, de 2024-09 à 2026-08) : `mf`, `mois`, `degre_fournisseurs`, `nb_fournisseurs_nouveaux_12m`, `nb_clients_partageant_fournisseur_nouveau` (autres entreprises ayant commencé avec le même fournisseur — **étranger via la douane, mensuel** ; local via l'annexe V, annuel — dans les 3 mêmes mois), `part_achats_coquilles`, `est_profil_coquille` (bool), `distance_entite_redressee` (1, 2, 3, 99 = aucune).
  - **Profil coquille** (règle fixe) : `nb_salaries` = 0 (annexe I) **et** création < 36 mois **et** montants reçus selon l'annexe V des clients ≥ 3 × `ca_total_declare` de l'exercice.
  - `distance_entite_redressee` n'utilise que les contrôles dont `date_notification_resultats` < fin du `mois` (pas de fuite du futur).

### 2.15 `verite_terrain.csv` — 🔒 caché (lu **uniquement** par l'évaluation de C)
`mf`, `scenario` (A, B, C, D, E, F, CROISSANCE_LEGITIME, CITOYEN_MODELE, COQUILLE, AUCUN), `mois_debut_scenario`, `intensite` (0–1), `montant_fraude_reel` (droits éludés en TND), `id_reseau` (pour le scénario B).

---

## Partie 3 — Calibration

### 3.1 Population et fenêtre
- **Fenêtre : 2023-09 → 2026-08 (36 mois).** Les déclarations de l'employeur couvrent les exercices 2023, 2024, 2025 (2025 disponible depuis mars 2026).
- **Contribuables : 5 250 personnes morales au régime réel** = 5 000 entreprises actives + ~150 coquilles (réseaux B) + ~100 dormantes (dont ~25 réactivées, scénario E). Ordre de grandeur réel : ~104 000 sociétés déposent une déclaration annuelle à la DGI [SEC 52] ; on simule un **portefeuille régional** plausible.
- ~60 acheteurs publics, ~800 fournisseurs étrangers, ~150 codes NDP.

### 3.2 Distributions (source : INS, Répertoire national des entreprises 2023 [OFF 53])
- **Secteurs** (pondérer parmi les sociétés, en surpondérant commerce de gros et industrie qui importent) : commerce 40 % (dont gros 20 %), industrie 22 % (textile, agroalimentaire, métallurgie, plastique), BTP 12 %, transport 8 %, services aux entreprises / TIC 10 %, hôtellerie-restauration 5 %, autres 3 %.
- **Forme juridique** parmi les sociétés : SARL ~73 %, SUARL ~23 %, SA ~3 % (INS : 146 524 SARL, 45 571 SUARL, 6 420 SA).
- **Taille** (salariés) : 0–2 : 45 %, 3–9 : 30 %, 10–49 : 18 %, 50–99 : 4 %, ≥ 100 : 3 %.
- **Gouvernorats** : proportionnels au nombre d'entreprises INS — Tunis 18 %, Sfax 10 %, Sousse 7,7 %, Nabeul 7,4 %, Ariana 7,3 %, Ben Arous 7 %, Monastir 5,2 %, Bizerte 4,4 %, Médenine 4,2 %, autres selon le tableau INS (codes : 11 Tunis, 12 Ariana, 13 Ben Arous, 14 Manouba, 15 Nabeul, 16 Zaghouan, 17 Bizerte, 21 Béja, 22 Jendouba, 23 Le Kef, 24 Siliana, 31 Sousse, 32 Monastir, 33 Mahdia, 34 Sfax, 41 Kairouan, 42 Kasserine, 43 Sidi Bouzid, 51 Gabès, 52 Médenine, 53 Tataouine, 61 Gafsa, 62 Tozeur, 63 Kébili) [OFF 53, 54].
- **CA annuel** : log-normal par classe de taille (médiane ~0,3 MD pour 0–2 salariés, ~1,5 MD pour 10–49, ~15 MD pour ≥ 100) [INF] ; saisonnalité mensuelle ±15 % selon le secteur ; bruit ±5 %.
- **Douane** (importateurs ≈ 35 % des entreprises) : circuits **70 / 22 / 8** (V/O/R) [SEC 21] ; valeur CAF par déclaration log-normale, **médiane ≈ 50 000 TND** (≈ 81 Md TND importés / ~1,5 M déclarations) [SEC 55, INF] ; origines pondérées : Italie 12 %, Chine 11 %, France 10 %, Allemagne 7 %, Turquie 6 %, Algérie 4 %, Espagne 4 %, autres [SEC 56] ; chapitres SH dominants : 85, 84, 87, 39, 30, 52, 72, 73 (on exclut 27 carburants, peu pertinent pour des PME) [SEC 57].
- **Paiements publics** : ~15 % des entreprises (BTP et fournitures surtout) reçoivent des paiements ADEB [INF, cohérent avec la commande publique ≈ 15 % du PIB, OCDE 58].
- **Contrôles** : ~**3 % des entreprises par an** (≈ 300 contrôles sur la fenêtre 2024-10 → 2026-06), origine : PROGRAMME_RISQUE 55 %, RECOUPEMENT 20 %, DENONCIATION 10 %, ALEATOIRE 15 %. Le **biais de sélection** est volontaire : la règle statique sur-sélectionne les grandes entreprises et les secteurs « classiques ». Couverture réelle ≤ 2,5 % [SEC 45] ; on monte légèrement pour avoir assez d'étiquettes.
- **Issues des contrôles** : entreprises à scénario → FRAUDE_SIGNIFICATIVE 70 % / REDRESSEMENT_MINEUR 25 % / CONFORME 5 % ; entreprises sans scénario → CONFORME 65 % / REDRESSEMENT_MINEUR 33 % / FRAUDE_SIGNIFICATIVE 2 % (le bruit est réaliste : presque toujours un petit redressement).
- **Dépôts** : 6 % de retards ponctuels, 2 % de non-dépôts ponctuels pour les entreprises normales.

### 3.3 Scénarios injectés (≈ 8 % des entreprises)
| Code | Scénario | Nb | Ce qui change dans les données (colonnes exactes) | Signaux attendus |
|---|---|---|---|---|
| **A** | **Minoration du CA** | 80 | `douane_articles.valeur_caf_tnd` ×2 à ×4 sur 2–4 mois **et/ou** `employeur_annexe5.montant_ttc` reçu des clients en hausse ; `ca_total_declare` stable (±5 %). Environ 1/3 des cas A sont organisés en petits groupes de 4–6 importateurs qui démarrent **le même mois** avec **le même nouveau fournisseur étranger** (dont Alpha, avec `FE00231`) | COH_IMPORT_VS_CA, COH_CLIENTS_VS_CA, CHG_IMPORTS, CMB_IMPORT_X_NOUV_FOURN |
| **B** | **Réseau de fausses factures** | 10 réseaux × 4–6 clients + 1–2 coquilles | Les clients commencent au même moment à acheter aux mêmes coquilles (`employeur_annexe5`, nouvelle relation) ; `tva_deductible_biens_services_local` des clients +40 à +120 % ; les coquilles : 0 salarié, `ca_total_declare` ≈ 0–10 % de ce que leurs clients déclarent leur payer | CHG_TVA_DEDUCTIBLE, RES_COQUILLE, RES_FOURNISSEUR_PARTAGE, COH_CLIENTS_VS_CA (côté coquille), CMB_COQUILLE_X_TVA |
| **C** | **Sous-évaluation en douane** | 50 | `prix_unitaire_tnd` à 40–70 % du `prix_reference_tnd` sur ≥ 3 articles ; les pairs important le même NDP sont au prix de référence ±15 % | COH_VALEUR_REF, PAI_MAHALANOBIS |
| **D** | **Recettes publiques non déclarées** | 30 | `adeb_paiements` pour 0,3–2 MD sur l'année, non reflétés dans `ca_total_declare` ; `tva_retenue_source_subie` sous-déclarée | COH_ADEB_VS_CA |
| **E** | **Dormante réactivée** (« phoenix ») | 25 | ≥ 12 mois de déclarations à 0 ou non déposées, puis importations soudaines importantes, CA déclaré faible | CHG_IMPORTS, CHG_DEPOTS, COH_IMPORT_VS_CA, CHG_NOUVELLES_CATEGORIES |
| **F** | **Compression de marge** | 50 | Achats (import + local) qui croissent, CA qui croît moins vite → marge apparente dérive de 20–30 % vers 2–5 % alors que les pairs restent stables | PAI_MARGE, PAI_MAHALANOBIS |
| ✔ | **Croissance légitime** (témoin) | 100 | Forte hausse d'activité (imports, nouveaux marchés publics) **entièrement reflétée** dans `ca_total_declare` et la TVA | aucun signal de cohérence → doit rester NORMAL |
| 🔵 | **Citoyen modèle** | ~400 | ≥ 30 mois de dépôts à l'heure, cohérence parfaite, contrôles passés CONFORME, parfois OEA | → CONFIANCE |

Les scénarios démarrent à des mois différents entre 2025-03 et 2026-06 pour montrer des **trajectoires**. Intensités variables (0,3–1) pour peupler PRIORITAIRE et SURVEILLANCE.

### 3.4 Marges de référence (benchmark, faute de source tunisienne)
Marges brutes indicatives [SEC 59, Damodaran jan. 2026, marchés US] : commerce de gros 31 %, commerce de détail 33 %, BTP 15 %, agroalimentaire 23 %, habillement 57 %, services aux entreprises 33 %, restauration 32 %, sidérurgie 12 %. À présenter comme **benchmark international, à remplacer par les ratios sectoriels DGI** en production.

### 3.5 Cas héros (identiques dans tous les lots — voir le contrat)
| `mf` | Raison sociale | NAT | Gouv. | Scénario |
|---|---|---|---|---|
| `1000001BAM000` | Alpha SARL | 46.69 | 34 Sfax | A + fournisseur étranger `FE00231` nouveau, partagé avec 4 autres importateurs A — trajectoire 28 → 76 |
| `1000002CAM000` | Beta Import SUARL | 46.43 | 13 Ben Arous | C |
| `1000003DAM000` | Gamma Travaux SA | 42.11 | 11 Tunis | D |
| `1000004EAM000` | Delta Trade SARL | 46.90 | 52 Médenine | E |
| `1000005FAM000` | Epsilon Textile SARL | 14.13 | 32 Monastir | F |
| `1000006GAM000` | Zeta Industries SA | 25.11 | 31 Sousse | Croissance légitime |
| `1000007HAM000` | Eta Pharma SA | 46.46 | 12 Ariana | Citoyen modèle (OEA) |
| `1000008JAM000` | Omega Négoce SUARL | 46.90 | 11 Tunis | Coquille d'un réseau B (5 clients) |

---

## Sources
1. demarches.tn — Matricule fiscal : https://www.demarches.tn/matricule-fiscal/ [SEC]
2. profiscal.blogspot.com — structure du matricule : http://profiscal.blogspot.com/2011/01/plusieurs-personnes-se-confondent-dans.html [SEC]
3. Ministère des Finances — Cahier des charges déclaration de l'employeur 2022-23 (EMPCCA) : https://www.finances.gov.tn/sites/default/files/2023-04/EMPCCA_22-23.pdf [OFF]
4. ng-sign — En-tête TEIF, identification fournisseur/client : https://www.ng-sign.com/comprendre-lentete-du-format-teif-identification-fournisseur-et-client/ [SEC]
5. Loi 2018-52 relative au RNE : https://legislation-securite.tn/latest-laws/loi-n-2018-52-du-29-octobre-2018-relative-au-registre-national-des-entreprises/ [OFF]
6. Ministère des Finances — Déclaration d'existence : https://www.finances.gov.tn/sites/default/files/2019-08/dclaration_dexistence_contribuable_0.pdf [OFF]
7. INS — Nomenclature d'activités tunisienne : https://www.ins.tn/nomenclatures/nomenclature-dactivites-tunisiennes-nat [SEC/OFF]
8. INS — NAT 2009 (PDF) : https://www.ins.tn/sites/default/files/publication/pdf/NAT%202009.pdf [OFF]
9. Ministère des Finances — Déclaration mensuelle 2023 : https://www.finances.gov.tn/sites/default/files/2023-04/MENSUELLE__2023.pdf [OFF]
10. chaexpert — pénalités de retard : https://chaexpert.com/penalites-de-retard-tarifs/ [SEC]
11. Jurisite — CDPF : https://www.jurisitetunisie.com/tunisie/codes/cdpf/cdpf1055.htm [SEC, texte officiel reproduit]
12. Jurisite — LF 2025 art. 37 : https://www.jurisitetunisie.com/tunisie/codes/lf2025/loifinances2025-37_fr.html [OFF reproduit]
13. Tustex / United Advisers — LF 2025 : https://www.tustex.com/economie-actualites-economiques/loi-de-finances-2025-nouveaux-taux-d-impots-par-united-advisers [SEC]
14. BFC — acomptes provisionnels : https://www.bfc.com.tn/blog/acomptes-provisionnels-tunisie-calcul-echeances [SEC]
15. Deloitte — LF 2026 : https://blog.avocats.deloitte.fr/tunisie-les-principales-mesures-de-la-loi-de-finances-pour-2026/ [SEC]
16. Jibaya — Cahier des charges employeur 2023 : https://jibaya.tn/wp-content/uploads/2024/02/EMPCCA_23_V_Finale.pdf [OFF]
17. chaexpert — plateforme TEJ : https://chaexpert.com/plateforme-retenue-source-tej/ [SEC]
18. La Presse — TEJ obligatoire dès 2026 : https://www.lapresse.tn/2025/11/26/la-plateforme-fiscale-tej-obligatoire-pour-toutes-les-entreprises-des-2026/ [SEC]
19. chaexpert — LF 2025 nouveaux taux IS / retenues : https://chaexpert.com/lf-2025-nouveaux-taux-is/ [SEC]
20. Ministère du Commerce — Manuel des procédures à l'importation (2022) : https://www.ccicentre.org.tn/wp-content/uploads/2025/07/Manuel-des-procedures-a-limportation.pdf [OFF]
21. Tuniscope — Douane : circuits et délais 2025 : https://www.tuniscope.com/article/440995/actualites/societe/douane-432615 [SEC]
22. L'Économiste Maghrébin / Directinfo — ML dans la sélectivité (mai 2026) : https://www.leconomistemaghrebin.com/2026/05/19/ [SEC]
23. Douane tunisienne — Régimes douaniers : https://www.douane.gov.tn/regimes-douaniers/ et https://www.douane.gov.tn/regimes-douaniers-2/ [OFF]
24. Douane tunisienne — Aide du tarif en ligne (codes taxes) : https://www.douane.gov.tn/tarifweb/help.php [OFF]
25. trade.gov — Tunisia import tariffs : https://www.trade.gov/country-commercial-guides/tunisia-import-tariffs [SEC]
26. ddouane.com — Tarif 2026 / nomenclatures : https://ddouane.com/tarif-web-2026 [SEC]
27. Douane tunisienne — Tarif en ligne : https://www.douane.gov.tn/tarifweb2025/ [OFF]
28. Douane tunisienne — Valeur en douane : https://www.douane.gov.tn/valeur-en-douane/ [OFF]
29. Douane tunisienne — Direction de la valeur : https://www.douane.gov.tn/direction-de-la-valeur/ [OFF]
30. Jurisite — Code des douanes art. 99–118 : https://www.jurisitetunisie.com/tunisie/codes/codedouanes/codedouane1210.html [OFF reproduit]
31. WMC — SINDA : https://www.webmanagercenter.com/2009/12/28/84721/ [SEC]
32. Douane tunisienne — Avantages OEA : https://www.douane.gov.tn/avantages-de-la-certification-oea/ [OFF]
33. La Presse — 165 OEA (mars 2024) : https://lapresse.tn/2024/03/18/ [SEC]
34. CIMF — ADEB : http://www.cimf.tn/index.php/systeme-d-aide-a-la-decision-budgetaire [SEC]
35. Banque mondiale — portail Mizaniatouna : https://blogs.worldbank.org/fr/arabvoices/tunisia-open-budget-portal [OFF]
36. Décret 2012-2878 (contrôle des dépenses publiques) : https://legislation-securite.tn/latest-laws/decret-n-2012-2878-du-19-novembre-2012-relatif-au-controle-des-depenses-publiques/ [OFF]
37. Banque mondiale — revue des dépenses publiques Tunisie : https://documents1.worldbank.org/curated/en/818771468311466409/301490TUN0whit1SIA0P08364401Public1.doc [OFF]
38. LOB 2019 : https://www.finances.gov.tn/sites/default/files/2019-08/loi_organique_budget_2019.pdf [OFF]
39. Arrêté du 10/04/2019 — nomenclature des dépenses : https://legislation-securite.tn/latest-laws/arrete-du-ministre-des-finances-du-10-avril-2019-fixant-la-nomenclature-des-depenses-du-budget-de-etat/ [OFF]
40. Ministère des Finances — retenue TVA 25 % : https://www.finances.gov.tn/fr/node/905 [OFF]
41. tunisie.gov.tn — consultation de la situation fiscale des fournisseurs (E-Sit~Fisc) : http://fr.tunisie.gov.tn/service/600/ [OFF]
42. Code de la comptabilité publique : https://www.finances.gov.tn/sites/default/files/2018-11/code_compta_fr.pdf [OFF]
43. data.gov.tn — marchés publics (communes) : https://catalog.data.gov.tn/fr/dataset/metadata/marches-publique [OFF]
44. Jurisite — CDPF contrôle fiscal : https://www.jurisitetunisie.com/tunisie/codes/cdpf/cdpf1045.htm [SEC, texte officiel reproduit]
45. Tuniscope — recettes fiscales, couverture du contrôle : https://www.tuniscope.com/article/430273/business/economie/les-recettes-fiscales-064517 [SEC]
46. CIMF — RAFIK : http://www.cimf.tn/index.php/systeme-de-rationalisation-de-l-action-fiscale-et-comptable [SEC, extrait]
47. CIMF — SADEC : http://www.cimf.tn/index.php/systeme-d-aide-a-la-decision-et-a-l-encadrement-du-controle-fiscal [SEC, extrait]
48. VATupdate — El Fatoora 2026 : https://www.vatupdate.com/2026/01/01/tunisia-2026-electronic-invoicing-el-fatoora-ttn-compliance-guide-for-service-providers/ [SEC]
49. tn-einvoice-validator (codes TEIF) : https://root.packagist.org/packages/ayoubgaouet/tn-einvoice-validator [SEC]
50. La Presse — caisses enregistreuses : https://www.lapresse.tn/2026/05/21/restaurants-salons-de-the-cafes-les-caisses-enregistreuses-digitales-obligatoires-des-le-1er-juillet/ [SEC]
51. La Presse — e-commerce et fisc : https://www.lapresse.tn/2026/03/29/e-commerce-en-tunisie-le-fisc-passe-a-la-vitesse-superieure/ [SEC]
52. L'Économiste Maghrébin / IACE — 103 000 entreprises déclarantes : https://www.leconomistemaghrebin.com/2026/01/29/iace-seulement-103-000-entreprises-declarantes-dgi/ [SEC]
53. INS — Répertoire national des entreprises 2024 (données 2023) : https://www.ins.tn/sites/default/files/files-ftp3/files/publication/pdf/RNE%202024.pdf [OFF]
54. INS — Code géographique : https://www.ins.tn/sites/default/files/publication/pdf/code%20geographique%202012_0.pdf [OFF]
55. African Manager — déficit commercial 2024 : https://en.africanmanager.com/tunisia-ends-2024-with-a-trade-deficit-of-19-billion-dinars/ [SEC, données INS]
56. ilboursa — top fournisseurs 2024 : https://www.ilboursa.com/marches/commerce-exterieur-top-10-des-fournisseurs-et-clients-de-la-tunisie-en-2024_50340 [SEC, données INS]
57. African Manager — top 10 produits importés 2024 : https://en.africanmanager.com/tunisias-top-10-import-and-export-products-in-2024/ [SEC]
58. OCDE (2020) — e-procurement en Tunisie (TUNEPS) : https://institutdesfinances.gov.lb/sites/default/files/2024-06/improving-e-procurement-environment-tunisia-en.pdf [OFF]
59. Damodaran — marges par secteur (jan. 2026) : https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/margin.html [SEC]

# Basira - synthetic world generator (work package A)

Basira is an explainable, dynamic compliance-risk layer for the Tunisian tax administration: every month it
checks whether each company's declarations still match what customs, public spending and partner companies see,
and turns each gap into a ranked, explained priority (see `idea_v3(1).md`).

This repository currently contains work package A: the simulated world everything else runs on. It generates
synthetic data with the exact shape of the real sources (DGI tax declarations, employer declaration annexes,
SINDA customs declarations, ADEB public payments, audit history), injects credible fraud scenarios with a hidden
ground truth, and builds the relationship graph. Packages B (signals), C (scoring, API) and D (web) consume it
through the formats fixed in `contrat_integration.md`.

All data is synthetic. No real taxpayer data is used anywhere.

---

## 1. Quick start

Requirements: Python 3.12 and [uv](https://docs.astral.sh/uv/).

```bash
uv sync                                               # create .venv with the pinned dependencies
uv run python -m generation.run --n 5250 --seed 2026  # full world, about 1 minute, then runs all checks
uv run python -m generation.run --n 200               # 200-company sample (includes the 8 hero cases)
uv run python -m generation.checks                    # re-run the consistency checks on data/
uv run pytest                                         # test suite (sample generation, checks, determinism)
```

Options of `generation.run`:

| Option | Default | Meaning |
|---|---|---|
| `--n` | 5250 | number of companies; at least 35 (heroes and mandatory scenarios), and 200 or more for the distribution checks to hold |
| `--seed` | 2026 | random seed; the same seed always produces byte-identical files |
| `--out` | `data` | output root; `raw/` and `graphe/` are created inside |
| `--skip-checks` | off | do not run `generation.checks` at the end |

The command exits with a non-zero status if any check fails.

Full pipeline once the other packages exist (contract section 2):

```bash
uv run python -m generation.run && uv run python -m signaux.run && uv run python -m scoring.run && uv run uvicorn api.main:app
```

---

## 2. Repository layout

```
.
├── data/
│   ├── raw/              A: source tables (contract section 2) + README.md with row counts and seed
│   ├── graphe/           A: aretes.csv, metriques_noeuds.csv
│   ├── signaux/          B (empty placeholder)
│   ├── scores/           C (empty placeholder)
│   └── mock/             D (empty placeholder)
├── generation/           A: the generator
│   ├── config.py         time window, calibration targets, scenario counts, hero cases
│   ├── referentiels.py   reference tables: NAT classes, NDP codes, governorates, codes, public buyers
│   ├── vocab.py          name vocabularies (built-in + curated LLM enrichment)
│   ├── vocab_llm.py      optional: enrich vocabularies with the local Qwen model
│   ├── vocab/llm_vocab.json   cached LLM vocabulary (read by vocab.py)
│   ├── population.py     taxpayer register and hidden roles, matricule fiscal
│   ├── activite.py       real monthly activity, scenario injection
│   ├── douane.py         customs declarations, articles, liquidation, foreign suppliers
│   ├── adeb.py           public payment orders
│   ├── employeur.py      employer declaration annexes I, II and V
│   ├── declarations.py   monthly tax returns and annual IS returns
│   ├── controles.py      audit history and ground truth
│   ├── graphe.py         relationship graph and monthly node metrics
│   ├── visualisation.py  interactive offline explorer (data/graphe/explorateur.html)
│   ├── assets/           vis-network 9.1.9 (embedded in the explorer)
│   ├── checks.py         consistency checks (section 8)
│   └── run.py            entry point
├── tests/                pytest suite
├── signaux/ scoring/ api/ web/   placeholders for packages B, C, D
├── contrat_integration.md, modele_donnees.md, member_A_task.md, idea_v3(1).md   specifications
├── pyproject.toml, uv.lock, .python-version
└── README.md
```

---

## 3. Output tables

Figures below are for the default run (`--n 5250 --seed 2026`). Column definitions follow
`modele_donnees.md` Part 2 exactly; this section only adds what the specification leaves open.

| File | Rows | Content |
|---|---:|---|
| `raw/contribuables.csv` | 5,250 | tax register: matricule, legal form, NAT class, governorate, regime, IS rate, OEA status... |
| `raw/declarations_mensuelles.csv` | 184,871 | one row per company and month from 2023-09 (or creation) to 2026-08, including unfiled months |
| `raw/declarations_is.csv` | 15,220 | annual IS returns for 2023, 2024, 2025 |
| `raw/employeur_annexe1_synthese.csv` | 13,359 | salaries, aggregated per employer and year |
| `raw/employeur_annexe2.csv` | 20,131 | fees, commissions and rents paid (beneficiary by matricule or CIN) |
| `raw/employeur_annexe5.csv` | 70,972 | purchases of 1,000 TND or more per client, supplier and year (the key cross-check source) |
| `raw/douane_declarations.csv` | 156,968 | DDM headers (SINDA) |
| `raw/douane_articles.csv` | 298,768 | DDM articles with NDP code, supplier, origin, quantity, value |
| `raw/douane_liquidation.csv` | 931,554 | taxes per article: DD 001, FODEC 093, TVA 105, RPD 473 |
| `raw/fournisseurs_etrangers.csv` | 918 | foreign suppliers seen in the published customs data |
| `raw/adeb_paiements.csv` | 17,925 | public payment orders (engagement, ordering, payment, withholdings) |
| `raw/historique_controles.csv` | 276 | past audits: selection origin, dates, outcome category, amounts |
| `raw/verite_terrain.csv` | 5,250 | hidden ground truth: scenario, start month, intensity, evaded duties, ring id |
| `raw/ref_nat.csv` | 44 | NAT 2009 classes with benchmark gross margin and import propensity |
| `raw/ref_ndp.csv` | 157 | customs codes (chapters 30, 39, 52, 72, 73, 84, 85, 87) with reference prices and rates |
| `raw/ref_gouvernorats.csv` | 24 | INS governorate codes and share of companies |
| `raw/ref_codes.csv` | 75 | code lists, with a `synthetique` flag for placeholders that are not official |
| `raw/ref_taux_retenue.csv` | 7 | withholding rates (modele_donnees.md 1.7) |
| `raw/ref_acheteurs_publics.csv` | 60 | ministries, public establishments, public enterprises, municipalities |
| `graphe/aretes.csv` | 43,135 | money flows between entities, aggregated over the window |
| `graphe/metriques_noeuds.csv` | 124,793 | graph metrics per company and month, 2024-09 to 2026-08 |

Formats (contract section 1): UTF-8 CSV with `,`, header row; amounts in TND rounded to 3 decimals; rates in
percent (`19.0`); dates ISO `YYYY-MM-DD`; months `YYYY-MM`; booleans `true`/`false`; empty cell = no value.
`taux_change` keeps 5 decimals and `part_achats_coquilles` 4.

`data/raw/README.md` is rewritten on every run with the actual row counts, the seed and the scenario counts.

---

## 4. How the world is simulated

The generation order follows `member_A_task.md` section 4, so that every cross-source identity holds by
construction rather than by patching.

1. **Population** (`population.py`). 5,250 companies: the 8 hero cases, the scenario companies, look-alikes,
   then a normal population drawn from the INS distributions (sector, legal form, size class, governorate).
   Creation dates follow an exponential age distribution; 4 % of normal companies are created during the window.
   Matricules are numbered in creation order (older companies have smaller numbers, as in reality).
2. **Real activity** (`activite.py`). Monthly real turnover = size-class median x sector multiplier x log-normal
   company effect x growth trend x sector seasonality (within +/-15 %) x 4 % noise. 4 % of normal companies have
   a one-off legitimate spike (a large order), which is fully declared. Purchases follow the company's gross
   margin; goods purchases are split between imports (for importers) and local purchases, plus local overheads.
   A share of turnover can come from public buyers (sector-dependent propensity) and from exports.
3. **Scenarios** (`activite.py`). Each scenario changes only the columns listed in modele_donnees.md 3.3
   (section 5 below). The declared turnover equals the real one everywhere else.
4. **Customs** (`douane.py`). Each importer has a portfolio of 3 to 10 NDP codes and 1 to 12 regular foreign
   suppliers that churn at about 1 % per month. The monthly import value becomes a Poisson number of
   declarations (median value around 50,000 TND), each with 1 to 6 articles. Unit prices are the reference price
   +/-15 %; quantities are derived from values and prices, then the value is recomputed so that
   `quantite x prix_unitaire = valeur`. Header CAF is the exact sum of its articles. Circuits are drawn
   70 / 22 / 8 (OEA operators get 92 % green). Scenario imports go to suppliers that are new for the importer.
5. **Liquidation** (`douane.py`). Only release for consumption (`IC100`) is liquidated; suspension regimes
   (`SA530`, `SA531`, `SE737`, used by fully exporting companies) pay nothing at entry.
   DD 001 = CAF x `taux_dd` (0 for EU and Turkish origins, association agreement and FTA); FODEC 093 = 1 % of CAF
   (0 for chapter 30); TVA 105 = (CAF + DD + FODEC) x `taux_tva` (7 % for medicines, 19 % otherwise);
   RPD 473 = 3 % of DD + FODEC + TVA. `total_droits_taxes_tnd` is the sum of the article lines.
6. **Public payments** (`adeb.py`). Public sales accrue monthly and are paid in lumps to 1 to 4 buyers chosen by
   sector affinity and governorate. Each payment has an engagement (one per company, buyer and year, with the
   purchase nature derived from its total), an ordering date 5 to 45 days earlier, the 25 % VAT withholding
   (payments of 1,000 TND or more) and the IS withholding (0.5 / 1 / 1.5 % by the supplier's IS rate).
7. **Employer annexes** (`employeur.py`).
   - Annex I: headcount follows the company's activity; payroll = headcount x sector salary.
   - Annex II: accounting fees (75 % of companies, usually a firm in the same governorate), consulting or
     advertising fees (20 % a year), rents to individuals identified by CIN (55 %). What a firm receives is capped
     at 60 % of its declared turnover.
   - Annex V: each client spends 25 % to 60 % of its local purchases (TTC) with suppliers inside the simulated
     portfolio (the rest goes to companies outside the regional portfolio, whose matricule is not in the
     register). Suppliers are drawn by sector affinity, governorate and size; relationships churn about 12 % a
     year and carry `premiere_annee_relation`. The client line is the same transaction as the supplier's sale:
     for honest suppliers the total received is capped at 90 % x B2B share x declared turnover TTC, minus the
     annex II fees they receive.
8. **Declarations** (`declarations.py`). Declared turnover is split by VAT rate (19 / 13 / 7 / exempt) according
   to the sector, plus exports. Deductible VAT: fixed assets (occasional capex), local goods and services
   (19 % of local purchases), imports (customs TVA 105 of the previous month). The VAT credit is carried forward
   month to month. Withholding paid, TFP, FOPROLOS and TCL are derived from the annexes and payroll. IS returns
   use the sum of the filed monthly turnover (+/-1.5 %), a company net margin, the minimum tax, advance
   payments (90 % of the previous year's IS) and the withholdings suffered (annex V, annex II and ADEB).
9. **Filing behaviour.** 80 % of companies are punctual (2.5 % late, 0.8 % missed); 20 % are sloppy (22 % late,
   7 % missed). Model citizens and heroes are never late. Missed returns of a closed fiscal year (2025 and
   before) are regularised later (code 1, 35 to 300 days late); missed 2026 returns may still be missing at the
   extraction date.
10. **Audits** (`controles.py`). About 3 % of companies a year are audited between 2024-10 and 2026-06. Selection
    is biased on purpose: `PROGRAMME_RISQUE` (55 %) uses a SAR-like static score (size, classic sectors,
    filing incidents); `RECOUPEMENT` (20 %) and `DENONCIATION` (10 %) over-select companies whose fraud has
    started; `ALEATOIRE` (15 %) is uniform. The outcome is then drawn from the ground truth: fraud active during
    the audited period gives 70 % significant fraud / 25 % minor / 5 % compliant; otherwise 65 % compliant /
    33 % minor / 2 % significant. Model citizens are always compliant. Reassessed amounts are based on the fraud
    actually accrued over the audited period.
11. **Ground truth** (`controles.py`). `montant_fraude_reel` = duties evaded over the whole window:
    hidden turnover x (19 % VAT + margin x 20 % IS) for A, D, E, F; fake purchases x (19 % + 20 %) for B clients;
    uncollected VAT on invoiced amounts for shells; duty and VAT difference on undervalued articles for C.
12. **Graph** (`graphe.py`), built only from the published raw tables (section 6).

Each stage draws from its own random stream (`numpy.random.SeedSequence(seed).spawn`), so the whole run is
reproducible and changing one stage does not reshuffle the others.

---

## 5. Scenarios and hero cases

Scenarios start between 2025-03 and 2026-06 with an intensity between 0.3 and 1, so that both the priority and
the watch segments are populated and trajectories are visible.

| Code | Scenario | Count | What changes in the data | Signals expected (catalogue section 3) |
|---|---|---:|---|---|
| A | Under-declared turnover | 80 | imports x2 to x4 (ramp of 1 to 3 months) served by new foreign suppliers, and/or clients' annex V payments above the declared turnover; declared turnover keeps its previous path. About a third are in groups of 4 to 6 importers starting the same month with the same brand-new supplier | COH_IMPORT_VS_CA, COH_CLIENTS_VS_CA, CHG_IMPORTS, CHG_NOUVEAUX_FOURNISSEURS, RES_FOURNISSEUR_PARTAGE |
| B | Fake-invoice ring | 51 clients in 10 rings | clients start buying from the same 1 or 2 shells in the same month (2025); local deductible VAT +40 % to +120 %; the fake invoices appear in the clients' annex V 2025 | CHG_TVA_DEDUCTIBLE, RES_COQUILLE, RES_FOURNISSEUR_PARTAGE |
| COQUILLE | Shell of a ring | 13 | created 2024, no staff (no annex I), declares 0 to 10 % of what its clients report paying it | COH_CLIENTS_VS_CA, shell profile |
| C | Customs undervaluation | 50 | unit values at 35 % to 69 % of the reference price after the start month; peers stay within +/-15 % | COH_VALEUR_REF, PAI_MAHALANOBIS |
| D | Undeclared public revenue | 30 | ADEB payments of 0.3 to 2 MD a year not in the declared turnover; the 25 % VAT withholding suffered is under-declared (0 to 30 % declared) | COH_ADEB_VS_CA |
| E | Dormant then active | 25 | at least 12 months of zero or missing returns, then sudden imports (100 to 800 kTND a month, new chapters), declared turnover 5 % to 20 % of reality, erratic filing | CHG_IMPORTS, CHG_DEPOTS, COH_IMPORT_VS_CA, CHG_NOUVELLES_CATEGORIES |
| F | Margin compression | 50 | purchases grow 30 % to 80 %; declared turnover is set so that the apparent margin drifts to 2 % to 5 % over 6 to 12 months | PAI_MARGE, PAI_MAHALANOBIS |
| CROISSANCE_LEGITIME | Legitimate growth (control group) | 100 | activity x1.8 to x3 over 3 to 6 months, new suppliers, sometimes new public contracts, all fully declared | CHG_* only, no coherence signal: must stay NORMAL |
| CITOYEN_MODELE | Model citizen | 400 | created before 2019, every return on time, audits always compliant, 15 % of the larger importers are OEA | should reach CONFIANCE |

Look-alikes without any scenario (ground truth `AUCUN`), there to make the signals honest:
75 dormant companies that never wake up, 135 recent companies with no staff (honest shell look-alikes),
one-off spikes, sloppy filers, and fully exporting companies with permanent VAT credits.

Share of companies with a fraud scenario: 5.7 %. The header of modele_donnees.md 3.3 says "about 8 %", but the
per-scenario counts in the same table add up to 5.7 %; the generator follows the explicit counts.

### Hero cases (contract section 7), with the values verified by `checks.py` on the default run

| mf | Company | NAT, governorate | Scenario | What the data shows |
|---|---|---|---|---|
| 1000001BAM000 | Alpha SARL | 46.69, 34 Sfax | A | imports x3.3 from 2026-06 against the previous 12 months, declared turnover -3 %; new supplier `FE00231` "Shenzhen Tools Co." (first seen 2026-06) shared with 4 other A importers starting 2026-06, including `1000311KAM000` Kappa Equipements SARL from the contract example; 3 new foreign suppliers in total |
| 1000002CAM000 | Beta Import SUARL | 46.43, 13 Ben Arous | C (2026-01) | 50 articles priced at about 52 % of the reference price |
| 1000003DAM000 | Gamma Travaux SA | 42.11, 11 Tunis | D (2025-06) | 1.4 MD of public payments a year, ADEB receipts / declared turnover over 12 months = 2.78, no VAT withholding declared |
| 1000004EAM000 | Delta Trade SARL | 46.90, 52 Médenine | E (2026-03) | 30 dormant months, then 1.8 MTND of imports via Ras Jedir (from Libya, Chinese and Turkish origins), 4 of the last 6 returns missing or more than 30 days late |
| 1000005FAM000 | Epsilon Textile SARL | 14.13, 32 Monastir | F (2025-09) | apparent margin 40 % (12 months to 2025-08), 11 % (12 months to 2026-08), 2 % over the last 6 months |
| 1000006GAM000 | Zeta Industries SA | 25.11, 31 Sousse | legitimate growth (2026-02) | imports x2.9 and declared turnover x2.8, VAT consistent |
| 1000007HAM000 | Eta Pharma SA | 46.46, 12 Ariana | model citizen | OEA since 2021-05-17, every return on time, one audit in 2025, compliant |
| 1000008JAM000 | Omega Négoce SUARL | 46.90, 11 Tunis | shell of ring RB01 (2025-03) | no staff, created 2024-11; its 5 clients report paying it 5.85 MTND in 2025 against 0.18 MTND declared; shell profile true from 2026-03; its clients have 63 % or more of their annex V purchases from shells |

The heroes have fixed identities whatever the seed, and are never selected for audits (except Eta's compliant
audit), so their stories stay clean. Kappa is also fixed.

---

## 6. Graph (`data/graphe/`)

`aretes.csv`: `source` pays `cible` (money flow).

| `type_relation` | Source | Target | Amount | Dates |
|---|---|---|---|---|
| IMPORT_FOURNISSEUR | importer mf | foreign supplier id | sum of CAF | first and last customs registration |
| ACHAT_LOCAL_A5 | client mf | supplier mf | sum of annex V TTC | 1 January of the first year and 31 December of the last year, clipped to the window |
| HONORAIRES_A2 | payer mf | beneficiary mf (matricule only) | sum of gross amounts | same as annex V |
| PAIEMENT_PUBLIC | public buyer id | company mf | sum of TTC payments | first and last payment |

`metriques_noeuds.csv`: one row per company and month from 2024-09 to 2026-08, for companies that exist in that
month. Availability rules of the real sources are respected at every month M:

- customs data is known monthly;
- annex V, annex I and the IS return of year N are only used from March N+1 (employer declaration due 28 February);
- an audit counts only if its results were notified before the end of month M.

| Column | Definition |
|---|---|
| `degre_fournisseurs` | distinct foreign suppliers over the last 12 months + distinct annex V suppliers of the latest available year |
| `nb_fournisseurs_nouveaux_12m` | foreign suppliers first seen in the last 12 months + annex V suppliers whose relationship started in the latest available year |
| `nb_clients_partageant_fournisseur_nouveau` | number of other companies that started with the same new supplier in the same period (foreign: last 3 months; local: same annex V year), counted only for suppliers that are onboarding clients simultaneously: at least 2 new clients, and new clients at least half of the supplier's active clients. Without that rule every new client of a large wholesaler would count |
| `est_profil_coquille` | fixed rule from modele_donnees.md 2.14: no salaried staff in annex I, created less than 36 months ago, annex V receipts at least 3 x the declared turnover of the same year (IS return), and receipts > 0 |
| `part_achats_coquilles` | annex V purchases from companies with the shell profile / total annex V purchases (latest available year) |
| `distance_entite_redressee` | shortest distance (1, 2, 3, else 99) to another company found in significant fraud (`FRAUDE_SIGNIFICATIVE`), on the annex V and annex II graph known at month M. Hubs (more than 20 partners, such as accounting firms and large wholesalers) can be reached but do not relay a path; otherwise almost every company would sit two hops from any sanctioned company |

### Seeing the graph

```bash
uv run python -m generation.visualisation        # writes data/graphe/explorateur.html (about 3 s)
xdg-open data/graphe/explorateur.html            # or open it in any browser
```

A single self-contained page (the vis-network library is embedded, so it works offline). Search any company,
supplier or public buyer, or click a hero case. The network around it is drawn with arrows following the
money; relations started in 2025-2026 are dashed, shells are red, companies found in significant fraud have a
thick border. Filters select the relation types (imports, annex V, annex II, public payments), 1 or 2 hops, and
recent relations only. Double-click a node to move to it. The side panel shows the company's identity, its
graph metrics at 2026-08, monthly declared turnover against imports, public payments and local purchases, the
graph signals over time, what its clients report paying it each year (annex V) against its declared turnover,
and its past audits. The "Show answer key" switch colours companies by their hidden scenario and marks the
scenario start on the charts: use it for testing, not in the demo of the detection.

### How good the graph metrics are

The graph code reads only the published raw tables: no hero identifier, scenario or ground truth appears in
`graphe.py`. Two independent validations:

1. **Correctness.** `tests/test_graph_audit.py` recomputes every metric from the raw CSV files with separate,
   brute-force code (plain breadth-first search, no NetworkX, no shared helpers) and compares it with
   `metriques_noeuds.csv`. On the full run, 412 company-months (random rows, the hero months, and rows where
   the distance or shared-supplier metric is non-trivial) matched exactly on all six columns.
2. **Separation.** Share of company-months where the contract's signal would be active (normalised value
   >= 0.5), fraud companies counted from their scenario start:

| Signal | Companies without fraud | Companies with fraud |
|---|---:|---|
| RES_FOURNISSEUR_PARTAGE (3 or more companies share a new supplier) | 1.3 % (0.4 to 0.6 % from 2025-03) | 100 % of B clients once annex V 2025 is available (2026-03); 100 % of grouped A importers in their first 3 months |
| RES_COQUILLE (30 % or more of purchases from shells) | 0 % | 100 % of B clients once annex V 2025 is available |
| RES_PROXIMITE_REDRESSE (distance 1 or 2) | 6 % | 23 % to 36 % for A, B, C, D, F |

Known limits, stated plainly:

- The graph finds what the generator planted. This validates that the metrics are computed correctly and
  behave sensibly on honest companies; it does not prove performance on real data.
- The shell profile is perfectly precise here (13 flagged, 13 real shells) because no honest company is built
  to receive 3 times its declared turnover. Real data would have false positives (for example unfiled returns).
- The shared-supplier signal has legitimate noise: a genuinely new supplier onboarding several clients looks the
  same. It is higher from 2024-09 to 2025-02 (4 %), when the latest annex V year is 2023 and more suppliers
  were created that year.
- B-ring signals appear only from 2026-03, because annex V 2025 is filed in February 2026. This is the real
  delay of the source, not a defect.
- Proximity relies on 15 sanctioned companies and on the fraud-homophily assumption above; without that
  assumption the signal would be close to uninformative.

---

## 7. Interpretations and assumptions to confirm with B and C

The contract requires every interface detail to be agreed by producer and consumer. These are the points the
specifications left open and how the generator settles them.

1. **Extraction date 2026-09-30.** The return for 2026-08 is due 2026-09-28, so filing dates (`date_depot`,
   `date_limite`) may run until 2026-09-30. All event dates (customs, payments, audits) stay within
   2023-09-01 .. 2026-08-31. B must use `date_depot` if it wants an as-of view of filings.
2. **Unfiled months** (`statut_depot = NON_DEPOSEE`) have empty amounts, `code_declaration` and `jours_retard`.
   Dormant companies that do file declare zeros (`DEPOSEE`, all amounts 0).
3. **Novelty burn-in.** A foreign supplier counts as new only if first seen from 2024-09 on, so that 12 months of
   history exist before it. Otherwise every supplier first seen in late 2023 would look new.
4. **Shared new supplier rule** as described in section 6 (simultaneous onboarding).
5. **Distance to a sanctioned entity:** `FRAUDE_SIGNIFICATIVE` only (minor reassessments are too common to
   carry information), the company itself excluded, annex V and annex II edges, hub rule.
6. **Shell profile** uses the IS turnover of the year (the monthly table only covers 4 months of 2023).
7. **Annex V dates in `aretes.csv`** are derived from the fiscal years, since annex V has no transaction dates.
8. **Customs:** the code for release for consumption was not found, so `IC100` is a documented placeholder;
   DC 014 and AIR 480 are listed in `ref_codes.csv` but not liquidated; the RPD base is DD + FODEC + TVA;
   DD exemption depends on the origin country (EU, Turkey). Office codes, declaration numbers, declarant codes
   and customs codes are synthetic (flagged in `ref_codes.csv`).
9. **Annex V `retenue_tva`** is always 0: all payers are private companies (public buyers pay through ADEB).
10. **Audit periods** (`periode_debut`, `periode_fin`) are clipped to the window start 2023-09.
11. **Label volume for C.** The 276 audits give 189 compliant, 72 minor reassessments and 15 significant fraud
    outcomes (87 positives with the contract's target definition). This is realistic (scenarios start late,
    audits are few and biased); C should expect small-sample weights.
12. **Size of the fraud population:** 5.7 %, see section 5.

---

## 8. Consistency checks (`generation/checks.py`)

Run automatically at the end of `generation.run`; they read the CSV files back from disk. The default run and the
200-company sample both pass 84 of 84.

- **Keys:** uniqueness of every key (`mf`, `num_declaration`, `id_article`, annex line ids, `num_ordonnance`,
  `id_controle`, composite keys); matricule format (7 digits, key letter without I, O, U, VAT code, category,
  establishment) and consistency with the displayed form.
- **Referential integrity:** every `mf_fournisseur`, `mf_payeur`, `mf_beneficiaire`, `mf_importateur`, annex II
  matricule beneficiary, audit, metric and ground-truth `mf` exists in `contribuables.csv`; articles point to
  existing declarations, suppliers and NDP codes; payments to existing buyers.
- **Customs arithmetic:** header CAF = sum of articles (+/-0.01); quantity x unit price = value; every
  liquidation line = base x rate; DD, FODEC and TVA rates equal `ref_ndp`, DD only for non-preferential origins
  and present whenever due; TVA base = CAF + DD + FODEC; RPD = 3 %; no liquidation for suspension regimes;
  header total = sum of its lines.
- **Honest companies:** annex V received <= declared turnover TTC (2024 and 2025, max ratio 0.86);
  TVA 105 of month M = deductible import VAT of M+1 (+/-5 %, 37,500 importer-months); IS turnover = sum of
  the monthly returns (+/-2 %).
- **Scenario signatures:** at least 90 % of each scenario's companies show the expected pattern (observed 97 % to
  100 %); every hero reproduces its contract behaviour (section 5 figures).
- **Distributions:** circuits 69.9 / 22.2 / 7.9 %; audits 3.0 % a year; importers 34.2 %; companies paid by
  public buyers 13.6 %; filing incidents of normal companies 7.8 % late, 1.2 % missing.
- **Signs and dates:** no negative number except accounting results; event dates inside the window; filing
  dates by the extraction date; audit and payment steps in chronological order.
- **Graph:** 24 months present, distance values in {1, 2, 3, 99}, no audit used before its notification, edge
  types, the shell profile flags only ring shells (13 of 13). `tests/test_graph_audit.py` recomputes the metrics
  independently (section 6).

The test suite (`uv run pytest`) also checks that the same seed gives byte-identical files, that another seed
gives another world with the same heroes, and that the register does not leak the ground truth.

---

## 9. Tools and libraries

| Need | Tool | Why |
|---|---|---|
| Environment and dependency pinning | uv (`pyproject.toml`, `uv.lock`) | fast, reproducible installs; `uv run` everywhere |
| Monthly simulation (N x 44 months matrices) | NumPy 2.x | vectorised activity, filing, VAT credit and liquidation computations; `SeedSequence.spawn` for independent, reproducible random streams |
| Tables, joins, CSV output | pandas 3.x | long-format tables, group-bys for annexes, aggregations for checks |
| Graph distances and structure | NetworkX | trading graph per fiscal year and bounded breadth-first search with the hub rule |
| Graph visualisation | vis-network 9.1.9 (embedded JavaScript) | interactive network drawing in a single offline HTML page |
| Parquet support for B and C | PyArrow | contract formats for `data/signaux/` and `data/scores/` |
| Tests | pytest | end-to-end generation, checks and determinism |
| Linting | ruff (via `uvx`) | unused code and common bugs |
| Name vocabulary enrichment | local Qwen3.5-9B served by Locally Uncensored (`lu-llama-server`, OpenAI-compatible API, port auto-detected) | more varied Tunisian company stems and foreign supplier names; nothing leaves the machine |

### Use of the local LLM

`uv run python -m generation.vocab_llm` finds the chat model running in Locally Uncensored (it scans for the
`lu-llama-server` process that is not the embeddings server and reads its port; `--url` or `BASIRA_LLM_URL`
override this) and asks it for Tunisian commercial name stems, Tunisian
family names and per-country words for foreign supplier names, and caches the answer in
`generation/vocab/llm_vocab.json`. The output is filtered before use: malformed or truncated stems are dropped,
and a blocklist removes the names of public figures and politically loaded families that the model proposed.
The data pipeline never calls the model: it only reads the cached file, so runs stay deterministic and work
offline. Re-running `vocab_llm` changes company names, so regenerate the data afterwards and tell the other
packages.

Qdrant is not used by package A: the contract defines raw data as CSV files and asks for no database. It
becomes relevant for package C's assistant if the team wants semantic retrieval, but the contract requires the
assistant to answer only from the tool outputs (`get_entreprise`, `get_preuves`...), which structured lookups
already cover.

---

## 10. Performance

Default run on this machine (24 cores, single-threaded code): about 50 seconds end to end, including the checks
(target under 10 minutes). The customs stage is the most expensive (about 30 s, 157,000 declarations). Output
size: 164 MB of CSV, largest file 45 MB, so every file fits under GitHub's 100 MB limit. Since the output is
deterministic, the team can also regenerate it instead of sharing it.

---

## 11. Handover notes

- **B (signals):** read `data/raw/` and `data/graphe/` only; never read `verite_terrain.csv`. Use `date_depot`
  and the March N+1 availability of annexes if signals must be computed as of each month. Section 7 lists the
  definitions to confirm.
- **C (scoring):** labels are in `historique_controles.csv` (`categorie_resultat`); `verite_terrain.csv` is for
  evaluation only. Hero audits are excluded by design, except Eta's compliant one.
- **D (web):** hero names, NAT classes and governorates are those of contract section 7; the Alpha network
  example of the contract (Kappa Equipements SARL, Shenzhen Tools Co.) exists in the data.

## 12. Not done in this package

- The pitch deck (member A task, section 7) is scheduled after the other packages deliver: it needs C's
  `evaluation.json` and D's screenshots.
- Out of scope by specification: fixed-length official file formats, e-invoices, connected cash registers,
  any database.

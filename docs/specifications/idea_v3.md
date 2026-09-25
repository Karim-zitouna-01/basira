# BASIRA: dynamic, explainable compliance risk intelligence

> **Idea v3.** It merges v1 (the vision and user story), v2 (the dynamic drift, peer comparison, network signals and grounded assistant) and the lessons from the conferences (`Input/conf*_clean.md`).
> **Scope of this document:** the idea, how it's used, and the data. The technology choices (models, LLM, stack) are deliberately left for later.
> *Working name: **Basira** (بصيرة, "insight, clear-sightedness"). It means seeing clearly what is hidden, which is exactly the promise: not just a score, but a clear view of *what changed and why*. It also reads easily in French and English. Alternatives if needed: **Boussole** (compass: guides the inspector), **Tawazun** (توازن, balance), **Nibras** (نبراس, lantern).*

---

## 1. The idea in one sentence

**Basira checks every month whether each company's declarations still match what the other administrations can see about it, over time and against its peers. It turns each gap into an explainable, ranked priority, so inspectors spend their limited audits on the cases that really changed, and stable, compliant companies are left alone.**

---

## 2. The problem, in the administration's own words

| What they said | Implication |
|---|---|
| DGI: *"The core question of the fisc: is the spontaneous declaration true? Are the figures real?"* | The heart of the product is **coherence between declared and observed**, not "anomaly detection" in the abstract. |
| DGI: *"Millions of pieces of information… how do we exploit them?"* The sources are SINDA (customs), ADEB (public spending), the employer declaration, and soon e-invoices and cash registers. | The data already exists but sits in silos. The cross-referencing is where the value is. |
| DGI: *"For 50 years we've done tax controls. Now we want the machine to learn which dossier to put under vérification."* | We must **learn from past control outcomes**, not only apply hand-set weights. |
| Budget: *"Don't tell me to audit everything. Tell me where the risk is, which part, which sector."* | We need a **portfolio/sector view** as well as the per-company view. |
| Customs: *"Facilitation first, control second."* Opérateur de confiance / OEA (authorised operator status). | Low risk must be **rewarded**, not just ignored. |
| Round table: *"We can't use public generative AI. The models and data must stay inside the institution."* | Sovereignty is a design principle, not an afterthought. |
| Advice: *"A prototype ends in a drawer when it answers your need, not the client's."* | Fit into their existing tools (SAR, SADEC 2), not beside them. |

**The problem, reframed:** the administration can audit only a tiny fraction of companies each year. Existing risk scoring (e.g. SAR at the DGI, selectivity channels at customs) is **static and hand-weighted**. It says *that* a company is risky but not *what changed* or *why*. It doesn't learn from the results of past audits, and it barely connects tax and customs data. So audits are spent on the wrong cases, real behaviour shifts are caught late, and honest companies get controlled for nothing.

---

## 3. Positioning: an AI layer for what already exists

Basira is **not** a new system that replaces SAR or customs selectivity. It is the **intelligence layer that plugs into the data they are already gathering** in the SADEC 2 data lake: it reads those sources, produces explained priorities and hands them to the existing control workflow.

> Pitch line: *"SADEC 2 gathers the data. SAR gives a score. Basira tells the inspector **what changed, why, how much is at stake, and what to do next**, and it learns from every audit."*

What's new compared with today:
1. **Coherence across administrations:** tax vs customs vs public procurement vs what partner companies report.
2. **Dynamic:** it tracks each company's *trajectory*, not a one-off snapshot.
3. **Explainable by construction:** every point of risk traces back to facts and the underlying operations.
4. **Learns from outcomes:** past audit results and each new inspector decision improve the ranking.
5. **Risk × stakes:** ranking by *expected recoverable amount*, not just likelihood, because audit capacity is limited.
6. **Two-sided:** the same engine identifies **trusted companies** (fast-track) as well as risky ones.

---

## 4. The four lenses (the heart of the product)

Every company is looked at through four lenses. Each produces **signals**, and each signal carries both a number and a **plain-language fact**.

### Lens 1: Coherence ("does what they declare match what others see?")
The tax administration's *recoupement*, automated and continuous.
- Declared turnover vs imports of goods (customs): *"Imports up 240% over 6 months; declared turnover flat."*
- Declared turnover vs what other companies report paying it (employer declaration withholdings): *"12 clients report paying 3.2 MD; declared turnover is 1.1 MD."*
- Declared turnover vs payments received from the state (ADEB): *"Received 800 KD from public buyers in Q2; not reflected in declarations."*
- VAT consistency: *"Deductible VAT rising while sales VAT falls for 4 months."*
- Customs declared value vs reference price for the product: *"Unit value 45% below the reference price for this HS code."*

### Lens 2: Change ("does it behave like it used to?")
The company against **its own history**.
- Sudden jumps or drops in volumes, values or margins, and their **speed** (acceleration, not just level).
- Novelty: new suppliers, new product categories, new countries of origin, new activity.
- Filing behaviour: late or missing declarations starting to appear, repeated "zero" declarations.

### Lens 3: Peers ("does it behave like similar companies?")
The company against **companies with the same activity, size and region**.
- Ratios far from the sector norm: margin, VAT ratio, imports per employee, turnover per employee.
- *"Declared margin 3%; median for peers in this activity is 18%."*

### Lens 4: Network ("who is it connected to?")
Relationships reconstructed from the data: who buys from whom, who pays whom.
- Shared new suppliers across several companies at the same time (possible fake-invoice supplier).
- Proximity to entities already reassessed or flagged.
- Suppliers with a lot of activity but no declared staff or turnover (shell pattern).

### From signals to a risk profile
- The signals are combined into a **risk score from 0 to 100, updated every month**, with its **trajectory** (e.g. 28 → 76 in two months).
- The combination is **learned from past control outcomes**, while staying explainable: each signal's contribution is shown.
- Each company also gets an **estimated amount at stake** (e.g. the gap between observed and declared turnover × the applicable rate).
- The **priority** for audit is based on *risk × stakes*.
- A **confidence** indicator says how much data backs the score (new companies and sparse data get lower confidence and are not overclaimed).

### Segments
| Segment | Meaning | Default treatment |
|---|---|---|
| 🔴 **Priority** | Strong, converging signals and high stakes | Proposed for audit |
| 🟠 **Watch** | Emerging or single signals | Request for information / reminder |
| 🟢 **Normal** | Nothing significant | No action |
| 🔵 **Trusted** | Long record of coherence, stable, and past audits clean | Candidate for **facilitation** (fast-track, fewer controls, faster refunds) |

---

## 5. Users and how they use it

### Personas
1. **Tax inspector / vérificateur (DGI):** investigates cases. The main daily user.
2. **Audit programming manager (chef de brigade / programmation des contrôles):** has N inspectors for the quarter and must choose *which* dossiers to open.
3. **Customs risk analyst (Direction de gestion des risques):** same engine, customs-centred view. Receives cross-signals from the tax side and sends signals back.
4. **Director / decision-maker:** wants the sector/region picture and results ("did targeting improve?").

### Journey 1: Morning triage (inspector)
> **08:00.** 10,000 companies in the portfolio.
> 🔴 **17** companies rose sharply in priority this month · 🟠 **43** show emerging signals · 🔵 **120** qualify as trusted · 🟢 the rest: no significant change.
> The list is sorted by **priority (risk × stakes)**, and each line has a one-sentence reason: *"Alpha SARL: imports ×3.4, declared turnover flat, 3 new suppliers (1 shared with 4 other flagged companies). Est. at stake: 420 KD."*

### Journey 2: Investigating a company (inspector + assistant)
Opening **Alpha SARL** shows:
- **Trajectory:** score 28 → 76 over 2 months, with the moment it changed.
- **Why:** the signals ranked by contribution, each with its fact sentence and its source administration.
- **Evidence:** drill down into the operations behind each signal (the customs declarations, the payers, the invoices).
- **Peers:** Alpha compared with its activity group.
- **Network:** a small graph showing the shared new supplier.
- **Assistant:** the inspector asks *"Why did Alpha's risk rise?"*, *"Which clients' payments aren't reflected?"*, *"Draft the request-for-information letter."* The assistant answers **only from Basira's computed facts and records** and cites them. It never invents figures or decides.

### Journey 3: The inspector decides (the human keeps the decision)
Graduated options, each **recorded with a justification**:
1. No action (with reason: e.g. "explained by a known new public contract")
2. Voluntary-compliance reminder (courtesy letter inviting correction, the cheapest option and one that builds trust)
3. Request for information / desk audit (*contrôle sur pièces*)
4. Full audit (*vérification approfondie*)
5. Signal to customs (or from customs to the tax side)

Every decision and later audit result **flows back into Basira** to refine future rankings. This is the learning loop.

### Journey 4: Planning the audit programme (manager)
> *"I have 12 inspectors and 60 audit slots this quarter."* Basira proposes a portfolio that **maximises expected recovery** under that capacity, balanced across sectors/regions, and shows what's being left out and why.

### Journey 5: Sector and region view (director)
A heatmap of risk by activity and governorate, plus trends: *"Risk rising in construction-materials importers in Sfax. 9 companies share 2 new suppliers."* This answers *"tell me which sector to target."* It also shows results: *"hit rate of audits proposed by Basira vs the rest."*

### Journey 6: The trusted lane
Companies in 🔵 get a positive signal (a facilitation candidate, e.g. an input to OEA status at customs or faster VAT refunds). This makes the system **fair and not purely repressive**, echoing the call for voluntary compliance and trust.

---

## 6. The data

All data is **synthetic**, generated to mirror the structure of the real Tunisian systems (as described by the speakers) without using any real data. It is reproducible from a fixed seed.

### 6.1 Sources to simulate (mirroring the real systems)

| # | Simulated source | Real counterpart | Key content | Frequency |
|---|---|---|---|---|
| 1 | **Tax register** | Dossier fiscal (DGI) | tax ID (*matricule fiscal*), legal form, activity code, region, size class, creation date, tax regime | static (+ changes) |
| 2 | **Tax declarations** | Télédéclaration | declared turnover, sales VAT, deductible VAT, taxes paid, filing date / late / missing | monthly (+ annual income tax) |
| 3 | **Customs declarations** | SINDA | date, supplier, country of origin, HS code, quantity, declared value, customs regime | per operation |
| 4 | **Employer declaration** | Déclaration de l'employeur (TEJ) | payer → payee, amount paid, withholding rate/type (goods, fees…), payroll, headcount | annual (withholdings detail) |
| 5 | **Public procurement payments** | ADEB | public buyer → company, amount, date | per payment |
| 6 | **Past control history** | Control / reassessment records | control date, type, outcome category (*compliant / minor reassessment / significant fraud*), amount reassessed | historical (5 years) |
| 7 | **Reference data** | Nomenclatures & reference prices | activity nomenclature, HS codes + reference unit prices, withholding rates | static |
| 8 | **Inspector decisions** | *(new, created by Basira's use)* | decision, justification, follow-up outcome | live during the demo |
| — | *Later (roadmap, not built):* e-invoices, connected cash registers, transporter data | E-invoice platform, cash registers | issuer/recipient/amount; daily tickets | — |

The **tax ID (*matricule fiscal*) is the common key** across all sources. In reality the codification differs between systems (the activity-code problem raised by the ministry's IT centre). We'll simulate a little of that inconsistency and state it as a production requirement: a unified national activity reference.

### 6.2 The synthetic population
- **~5,000–10,000 companies** over **36 months** (enough history for "change" and for past audits).
- A realistic mix of activities (importers/distributors, manufacturing, construction, services, liberal professions), sizes and regions.
- **Normal behaviour is not flat:** seasonality, gradual growth or decline, noise, occasional one-off events.
- **Legitimate big changes exist:** a new public contract, a real expansion, a new product line that *is* reflected in the declarations. These must **not** be flagged, which proves the system doesn't punish growth.
- **Past controls are biased:** only ~3–5% of companies were audited each year, mostly the large or already-suspected ones. The labels are therefore partial, like in reality, and we say so.
- **Imperfect data quality:** a few missing declarations and late filings, plus some code mismatches.
- A **hidden ground truth** per company (the injected scenario, if any) is used **only to evaluate**, never shown to the system.

### 6.3 Injected fraud scenarios (the stories the demo tells)

| # | Scenario | What it looks like in the data | Lenses that catch it |
|---|---|---|---|
| A | **Under-declared turnover** | Imports and client payments rise; declared turnover stays flat | Coherence + Change |
| B | **Fake-invoice ring** | Several companies simultaneously start buying from the same new suppliers. Those suppliers have high flows, no staff and few declarations. Deductible VAT jumps | Network + Coherence (VAT) |
| C | **Customs undervaluation** | Unit values well below the reference price and below peers for the same HS code | Coherence + Peers |
| D | **Undeclared public revenue** | ADEB payments not reflected in declarations | Coherence |
| E | **Dormant then active** ("phoenix") | Years of zero or minimal declarations, then a sudden large import activity | Change + Coherence |
| F | **Margin compression** | Declared margin drifts far below sector peers while volumes grow | Peers + Change |
| ✔ | **Legitimate growth (control case)** | Big jump in activity **fully reflected** in declarations | Should stay 🟢, the "false alarm avoided" story |
| 🔵 | **Model citizen** | Years of coherence, clean past audits | Should reach 🔵 Trusted |

**Hero cases for the demo:** one company per scenario, with a name and a story (e.g. *Alpha SARL*, scenario A+B: the v1 story, now with a coherence angle).

### 6.4 What "good" looks like: evaluation
Measured on the synthetic ground truth and compared with **two baselines**: random selection and a SAR-like static weighted rule.
- **Hit rate in the top N** proposed audits (e.g. top 50): *"Same number of audits, X× more fraud found."*
- **Amount recovered per audit** (thanks to the risk × stakes ranking).
- **False alarms avoided:** legitimate-growth companies not flagged.
- **Early detection:** how many months earlier a drift is caught than with the static rule.
- **Explanation quality:** every flagged case has at least one verifiable fact that links to its evidence.

These numbers are the **Impact** slide.

---

## 7. Principles and guardrails

- **The human decides.** Basira proposes and explains; no sanction or control is ever triggered automatically.
- **Every score is justified.** No score is shown without its reasons and evidence. A score that can't be explained isn't shown.
- **Contestable and traceable.** Every score, explanation and decision is logged with its date, so it can be audited later (Cour des comptes, internal control).
- **Fairness.** Size, region and legal form are never risk factors on their own; only behaviour is. We check that flag rates aren't driven by size or region.
- **Not purely repressive.** The trusted lane and voluntary-compliance reminders come first; audits are for converging signals.
- **Sovereignty and data protection.** It is designed to run entirely **inside the administration's perimeter**, with no data leaving it, and it complies with law 2004-63 (INPDP). The prototype uses only synthetic data.
- **Proportionality.** Each administration sees only what it's entitled to see. Cross-signals between tax and customs are shared as *signals*, not full records.

---

## 8. Hackathon scope

**In the prototype (must show):**
- Synthetic data generator with the scenarios above
- The four lenses → signals with fact sentences
- A monthly risk score with trajectory, stakes, priority and segment
- Inspector triage list, company deep-dive with evidence drill-down, and the grounded assistant
- Decision recording (the feedback loop is shown, even if simplified)
- Evaluation results vs the baselines

**Nice to have (if time):** the audit-programme planner, the sector/region heatmap, the trusted-lane view.

**Roadmap only (slides):** e-invoices, cash registers and transporter data; full integration with SADEC 2 / SINDA 2; national activity reference; model retraining in production; a taxpayer-side view (self-check before filing).

---

## 9. Challenges covered and how it scores

- **Main challenge: T20** (dynamic compliance risk scoring).
- **Secondary (one only, per the brief):** recommend **T7** (cross-referencing tax, customs and financial data). It is the core of Lens 1 and was stressed by every speaker. *Alternative:* T4 (the trusted lane).
- Naturally touches **T5** (dynamic segmentation), **T2** (control targeting), **T1/T12** (data mining, weak signals).

| Criterion | Our answer |
|---|---|
| **Pertinence (25%)** | Directly the DGI's #1 stated AI priority. It fits their existing tools (SAR, SADEC 2, SINDA) and uses their vocabulary. |
| **Feasibility (25%)** | Working prototype on realistic synthetic data. Scope is controlled, and every piece is demonstrable. |
| **Innovation (20%)** | Cross-administration coherence, dynamic trajectory, explanation by construction, learning from audit outcomes, risk × stakes ranking, trusted lane. |
| **Impact (20%)** | Measured gain vs today's approach: more fraud found per audit, earlier detection, fewer honest companies bothered. |
| **Clarity (10%)** | One strong story (Alpha SARL) told from morning triage to decision. |

---

## 10. Open questions for the mentor (21:00 checkpoint)
1. Is the **tax-side focus** (with customs as a source and partner) the right primary audience, or does the mentor lean customs?
2. Are the scenario categories (under-declaration, fake invoices, undervaluation, undeclared public revenue) the ones that matter most to them? Any missing?
3. Is the **three-category outcome** (compliant / minor / significant) the right reading of what the DGI speaker meant?
4. Is "risk × stakes" prioritisation aligned with how they programme audits today?
5. Is it acceptable to position ourselves explicitly as an AI module for **SADEC 2**?

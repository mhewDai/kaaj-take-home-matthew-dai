# Design Decisions

This document covers which lender requirements were prioritized, the
simplifications made (and why), the key architectural choices, and what I'd add
with more time.

---

## 1. Architecture: a declarative rule engine

The single most important decision was to model every policy criterion as a
**declarative rule** — `rule_type` + `config` JSON + `severity` — evaluated by a
**registry of evaluators**, rather than hard-coding each lender's logic.

Why: the brief weights *extensibility* and *policy modeling* heavily, and the five
lenders have genuinely different shapes. A registry-backed rule model means:

- **Editing a policy is a data change** (change a `config` value), not a code
  change — exposed through the API and the policy-editor UI.
- **Adding a new kind of check is one local change** — write an evaluator,
  decorate it with `@rule(...)`. That same registration declares the rule's
  editable parameters, so the UI can render an editor for it automatically.
- The engine stays **pure** (no DB/web imports), so the matching logic is
  isolated and fully unit-tested.

Rules carry one of four **severities** that determine how they participate:
`knockout` (lender-wide hard stop), `qualification` (program gate),
`prerequisite` (program applicability gate — produces *not applicable*, not a
rejection), and `preference` (soft signal; never blocks, only nudges
warnings/score).

**Programs/tiers are first-class.** Each lender has one or more ranked programs;
the engine picks the best-ranked program the applicant qualifies for. Mutually
exclusive paths (Stearns' standard vs. no-PayNet vs. corp-only; start-up vs.
established) are modeled with prerequisite rules so only the applicable program is
considered.

---

## 2. Which lender requirements I prioritized

I prioritized the criteria the brief calls out explicitly and that actually gate
eligibility, and modeled them faithfully across all five lenders:

| Requirement | How it's modeled |
|---|---|
| FICO / PayNet / TIB thresholds (tiered) | `min_fico`, `min_paynet`, `min_time_in_business` per program tier |
| Min/max loan amounts (incl. app-only caps) | `loan_amount_range` per program |
| Industry exclusions | `excluded_industries` (knockout) + `allowed_industries` whitelist (Apex A+, Falcon manufacturing) |
| Geographic restrictions | `excluded_states` (Apex CA/NV/ND/VT, Citizens CA) |
| Equipment type/age | `excluded_equipment_types`, `max_equipment_age` |
| Bankruptcy / derog credit | `no_bankruptcy_within_years`, `no_open_judgments`, `no_foreclosures`, `no_repossessions`, `no_tax_liens`, `no_recent_collections` |
| Borrower gates | `requires_homeownership`, `requires_us_citizen`, `requires_cdl`, `requires_personal_guarantee` |
| Comparable business credit | `min_comparable_credit_pct` (flat or amount-tiered — Apex's 50%/75%) |
| Revolving-debt limit | `max_personal_revolving` (Stearns' $30k / $50k-combined rule) |
| Non-trucking / trucking sub-rules | `non_trucking_only`, `requires_trucking`, `min_trucks_operating` |
| Term, soft costs, down payment, private-party | `max_loan_term`, `max_soft_costs_pct`, `min_down_payment_pct`, `no_private_party_sale` |

Lender-specific highlights captured:
- **Stearns** — three credit-box variants (standard / no-PayNet / corp-only), each
  with three tiers, selected via prerequisites; revolving-debt knockout; 13
  industry exclusions; no-BK-7-years.
- **Apex** — A+/A/B/C + Medical A/B + Corp-Only (7% buy rate) programs; state
  exclusions; ~20 industry/equipment exclusions; A+ eligible-industry whitelist
  and 5-year collateral cap; amount-tiered comparable-credit; 25% soft-cost cap.
- **Advantage+** — single $75k non-trucking ICP with established vs. start-up
  programs (680 vs. 700 FICO, 10% vs. 20% down); hard derog knockouts; US-citizen.
- **Citizens** — General / Start-Up / Non-Homeowner / Full-Financials tiers with
  all-in caps; homeownership; CA + cannabis exclusions; 5-year BK seasoning.
- **Falcon** — base credit guidelines (680 FICO / 660 PayNet / 3yr / 70%
  comparable / 15yr BK) applied lender-wide, plus industry-capped app-only
  programs (manufacturing $350k, commercial $250k, trucking $150k with A/B-only
  sub-rules).

---

## 3. Simplifications made (and why)

These are conscious trade-offs to stay within the time box while keeping the core
matching correct and the model honest.

1. **Personal credit unified as `fico`.** Citizens uses TransUnion and Advantage+
   uses "Equifax FICO v5"; I store a single personal-credit score and note the
   bureau in program metadata. Modeling per-bureau scores on the application would
   be a small, additive change (a `scores` map + a `bureau` param on the rule) but
   adds form/UX weight for little decision impact here.

2. **"Does not finance bankruptcies" → a very large seasoning window.** Advantage+
   ("No") is encoded as `no_bankruptcy_within_years: 100` rather than a separate
   boolean rule, reusing one evaluator for both "never" and "N years" cases.

3. **Citizens' equipment-age→term matrices are simplified.** The PDF has detailed
   per-equipment year-model→max-term tables (Class 8, dump, construction, etc.).
   I model a global `max_loan_term` (60) and per-program `max_equipment_age` where
   relevant, and flag the full matrix as future work. A dedicated
   `term_by_equipment_age` rule type is the natural extension.

4. **Comparable credit, soft costs, down payment treated as documentation/soft
   gates where the PDFs imply verification.** Missing values degrade to a
   *warning* (`on_missing: "warn"`) instead of hard-failing, so a thin application
   isn't rejected for a doc item. The `on_missing` knob (`fail`/`warn`/`pass`) is
   per-rule and editable.

5. **Underwriting runs synchronously within the request.** The run is created,
   executed by the orchestrator, and the completed result returned in one call
   (status is still tracked and pollable via `GET /runs/{id}`). True async
   initiation (202 + background worker) is the Hatchet path below.

6. **`create_all` instead of migrations.** Tables are created on startup so the
   project runs with one command. Production would use Alembic.

7. **Industry/equipment vocabularies are a curated enum** with an `other`
   fallback, not an exhaustive taxonomy. A few exclusion items without a clean
   enum (e.g. "non-essential use", "leasehold improvements", "sale-leaseback") are
   omitted from matching and noted; they'd map to new enum values + rules.

8. **No auth / multi-tenancy.** Out of scope for the assignment.

---

## 4. Workflow: in-process, Hatchet-shaped

Per the assignment options, the orchestration layer is an **in-process
orchestrator** that demonstrates the required parallelization + retry, structured
to map directly onto Hatchet:

| This project | Hatchet |
|---|---|
| `step_validate`, `step_derive_features`, `step_rank_and_score` | `@hatchet.step()` |
| `step_evaluate_lenders` (asyncio fan-out) | parent step spawning a child workflow per lender |
| `with_retries(..., retries=N, backoff=...)` | `@hatchet.step(retries=N, backoff=...)` |
| `step_persist` wrapped in retry | `@hatchet.step(retries=1)` |
| `run_underwriting_sync` (request-time) | `workflow.run()` / event trigger, polled via run status |

I chose this so the project runs with zero extra infrastructure while still
exercising the concepts. Migrating is mechanical: move each step under a Hatchet
worker and replace the `asyncio.gather` fan-out with child-workflow spawns.

---

## 5. Fit score

Documented and intentionally simple (`app/matching/scoring.py`):

- **Eligible** lenders score in **[60, 100]**, **ineligible** in **[0, 55]** — so
  eligibility dominates ranking.
- Among eligible: weighted blend of *threshold buffer* (how comfortably the
  application cleared minimums — each numeric evaluator reports a 0–1 margin),
  *tier quality* (better program rank), and *cleanliness* (fewer warnings).
- Among ineligible: fraction of gating criteria passed, so "closest to
  qualifying" surfaces first.

This is a transparent heuristic, not a calibrated model — easy to read in the UI
and easy to tune.

---

## 6. Adding a new lender

The intended onboarding flow for "we got a new lender PDF":

1. Read the PDF once and express it as a lender dict in
   `app/seed/lender_data.py` using the `ko/qual/prereq/pref` helpers (or POST the
   same shape to `/api/lenders`).
2. If a criterion needs a check that doesn't exist yet, add one evaluator in
   `app/rules/evaluators.py` with `@rule(...)` — it's immediately usable and
   editable in the UI.
3. Re-seed (or it's live immediately if added via the API).

```python
NEWCO = {
    "name": "NewCo Capital", "slug": "newco-capital",
    "rules": [ ko("excluded_states", states=["FL"]),
               ko("no_bankruptcy_within_years", years=7) ],
    "programs": [
        {"name": "Prime", "rank": 1, "rate": 7.5, "rules": [
            qual("min_fico", min=700),
            qual("min_time_in_business", min_years=3),
            qual("loan_amount_range", min=10000, max=250000),
        ]},
    ],
}
```

No engine, schema, or UI code changes required.

---

## 7. What I'd add with more time

- **Per-bureau credit scores** and FICO-version awareness.
- **`term_by_equipment_age` rule type** to model Citizens' full age→term matrices
  and Falcon's reefer/Class-8 age rules precisely.
- **Real Hatchet integration** with a worker, async run initiation (202 + polling
  / websocket), and durable retries.
- **Policy versioning & audit log** — every rule edit captured, with effective
  dates, so a run records exactly which policy version produced it.
- **Rule config validation** against each rule type's param schema on write (today
  the registry validates the type and tolerates loose config).
- **A PDF-assisted ingestion tool** (LLM-extraction → proposed lender dict that a
  human reviews) to speed up step 1 of onboarding.
- **Optimistic UI / loading states, toasts, and form validation** polish; an
  "explain this score" breakdown; and saved applicant scenarios.
- **More tests**: property-based tests for scoring monotonicity, and frontend
  component tests.
```

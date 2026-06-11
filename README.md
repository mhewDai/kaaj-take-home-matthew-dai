# Lender Matching Platform

A loan underwriting and lender-matching system for equipment finance. It parses
five real lender credit policies into a **normalized, editable rule model**,
evaluates a loan application against every lender in parallel, and returns ranked
matches with a clear, per-criterion explanation of *why* each lender did or
didn't qualify.

> Built for the Kaaj founding-engineer assignment. Stack: **FastAPI + SQLAlchemy
> + PostgreSQL** backend, **React + TypeScript + Tailwind (Vite)** frontend, with
> an in-process, Hatchet-shaped workflow orchestrator.

---

## Table of contents
- [What it does](#what-it-does)
- [Quick start](#quick-start)
- [Architecture overview](#architecture-overview)
- [The policy model (the core idea)](#the-policy-model-the-core-idea)
- [Matching engine & fit score](#matching-engine--fit-score)
- [The workflow](#the-workflow)
- [Adding / editing lenders & rules](#adding--editing-lenders--rules)
- [API documentation](#api-documentation)
- [Testing](#testing)
- [Project layout](#project-layout)

---

## What it does

- **Normalizes** 5 lender PDFs (Stearns Bank, Apex Commercial Capital, Advantage+
  Financing, Citizens Bank, Falcon Equipment Finance) into one declarative schema.
- **Underwrites** a loan application against all active lenders, deriving features
  (equipment age, start-up status, trucking flag, …) and evaluating each lender's
  programs/tiers in parallel.
- For each lender returns **eligibility (yes/no)**, the **best matching
  program/tier**, **specific rejection reasons**, and a **fit score (0–100)** for
  ranking.
- Renders it all in a web UI: application form, results with a full
  met/not-met-and-why breakdown, and an editable lender-policy screen.

---

## Quick start

### Option A — Docker Compose (everything)

```bash
docker compose up --build
# frontend  -> http://localhost:5173
# backend   -> http://localhost:8000  (Swagger at /docs)
# postgres  -> localhost:5432
```

The backend creates its tables and seeds the 5 lenders automatically on first
boot.

### Option B — Postgres in Docker, apps on the host (verified path)

```bash
# 1. Database
docker compose up -d db          # or use a local Postgres; see backend/.env.example

# 2. Backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env             # default DATABASE_URL points at the compose db
uvicorn app.main:app --reload    # :8000  (auto-seeds on first run)

# 3. Frontend (new terminal)
cd frontend
npm install
npm run dev                      # :5173, proxies /api -> :8000
```

A `Makefile` wraps these: `make install`, `make db`, `make backend`,
`make frontend`, `make seed`, `make test`.

### No Docker at all?

Point `DATABASE_URL` at any Postgres you have, **or** use SQLite for a zero-infra
run:

```bash
cd backend
DATABASE_URL=sqlite:///./local.db uvicorn app.main:app --reload
```

The test-suite always runs on SQLite, so `make test` needs no database.

---

## Architecture overview

```
                         ┌─────────────────────────────────────────────┐
  React + TS (Vite) ───► │  FastAPI  /api                               │
  - Application form      │   ├─ applications  (CRUD)                    │
  - Results + reasoning   │   ├─ lenders/programs/rules (CRUD, editable) │
  - Policy editor         │   └─ underwriting (run + status + results)   │
                          │                                              │
                          │  Workflow orchestrator (in-process)          │
                          │   validate → derive features →               │
                          │   evaluate lenders (parallel + retry) →      │
                          │   rank & score → persist                     │
                          │                     │                        │
                          │            Matching engine (pure)            │
                          │   evaluate_lender(policy, features)          │
                          │            │                                 │
                          │      Rule registry  ◄── declarative rules    │
                          │   (37 evaluators, each = one policy check)   │
                          └───────────────────────┬──────────────────────┘
                                                  │ SQLAlchemy
                                            PostgreSQL
```

**Separation of concerns** is the organizing principle:

| Layer | Package | Responsibility | Depends on |
|---|---|---|---|
| Rule engine | `app/rules` | Declarative checks + registry. **Pure Python.** | nothing |
| Matching | `app/matching` | Feature derivation, engine, scoring, ORM adapter | rules |
| Workflow | `app/workflow` | Orchestration (parallel/retry/persist) | matching, models |
| Models | `app/models` | SQLAlchemy schema | db |
| API | `app/api` | REST endpoints, validation | everything |

The rule engine and matching engine have **no database or web dependency**, which
is why the critical matching logic is trivially unit-testable.

---

## The policy model (the core idea)

Five lenders with wildly different formats (Stearns' tiered credit box, Apex's
rate grades, Advantage+'s single ICP questionnaire, Citizens' tier programs,
Falcon's A–E grid) all reduce to:

```
Lender ──*  Program ──*  PolicyRule
   └───────────────────*  PolicyRule        (lender-wide knockouts)
```

- A **`PolicyRule`** is one declarative check: a `rule_type` (key into the rule
  registry) + a `config` JSON (thresholds/lists) + a `severity`
  (`knockout` / `qualification` / `prerequisite` / `preference`).
- A **`Program`** is one tier / rate-grade / credit-box variant, with its own
  rules and a `rank` (1 = best tier).
- A **`Lender`** owns programs plus lender-wide knockout rules.

Each `rule_type` is backed by an **evaluator** registered in a central registry.
Registering an evaluator also declares its editable parameters, which is what
lets the policy-editor UI render an edit form for any rule with **zero bespoke
code**. See `app/rules/evaluators.py` for the full library (FICO/PayNet/TIB
minimums, loan caps, term/equipment-age limits, industry/state/equipment
exclusions, bankruptcy & derog knockouts, homeownership/CDL/citizenship gates,
comparable-credit, revolving-debt, prerequisites, preferences, …).

This split is deliberate:
- **Editing an existing policy** (change a threshold, add a state to an exclusion
  list) = a *data* change on a `PolicyRule` (API/UI), no deploy.
- **Adding a new kind of check** = add one evaluator function + `@rule(...)`.

---

## Matching engine & fit score

For each lender the engine (`app/matching/engine.py`) runs:

1. **Knockouts** — lender-wide rules; any failure ⇒ ineligible.
2. **Programs** — for each, evaluate **prerequisites** (applicability gate, e.g.
   "corp-only", "no PayNet", "trucking") then **qualification** rules. A program
   *qualifies* iff it's applicable and nothing blocks.
3. **Eligibility** = no knockout fired **and** ≥1 program qualifies. The **best
   program** is the qualifying one with the lowest `rank`.
4. **Fit score** — eligible lenders score in **[60, 100]**, ineligible in
   **[0, 55]**, so an eligible lender always outranks an ineligible one. Among
   eligible lenders the score rewards buffer above thresholds, better tier, and a
   cleaner profile. Among ineligible ones it reflects how close they came (for a
   "closest to qualifying" view). Formula in `app/matching/scoring.py`.

Every check yields a structured `CriterionResult` (status, expected, actual,
human message), e.g. *"Minimum FICO not met: minimum required is 700 but the
application's FICO is 600."* — which is exactly what the UI renders.

---

## The workflow

`app/workflow/orchestrator.py` implements the required flow as explicit steps:

`validate → derive features → evaluate lenders (parallel + retry) → rank & score → persist`

- **Parallelization** — every lender is evaluated concurrently with
  `asyncio.gather` + `asyncio.to_thread`. ORM access is confined to the main
  thread; workers only touch pure dataclasses.
- **Retry** — `with_retries` wraps per-lender evaluation and the persist step with
  bounded attempts + linear backoff (configurable via env). A single failing
  lender is isolated and never fails the whole run.

It's intentionally **Hatchet-shaped**: each step maps 1:1 onto a Hatchet
`@hatchet.step()` (with `retries=`), and the lender fan-out maps onto Hatchet
child-workflow spawning. We kept it in-process so the project runs with zero
extra infrastructure — see [DECISIONS.md](./DECISIONS.md) for the migration path.

---

## Adding / editing lenders & rules

- **Edit a threshold** — Lenders → pick a lender → change a rule's parameter →
  *Save*. (`PATCH /api/rules/{id}`.)
- **Add a check to a program** — *+ Add rule*, choose a type, fill its params.
  (`POST /api/programs/{id}/rules`.)
- **Add a lender** — `POST /api/lenders` with a normalized payload (same shape as
  the seed data in `app/seed/lender_data.py`), or via the API/UI.
- **Onboard a new lender from a PDF** — read the PDF once, express it as a lender
  dict in `app/seed/lender_data.py` (or POST it). No engine changes. See the
  worked example and checklist in [DECISIONS.md](./DECISIONS.md#adding-a-new-lender).

---

## API documentation

Interactive docs (Swagger UI) are served at **`http://localhost:8000/docs`**.
Summary:

### Applications
| Method | Path | Description |
|---|---|---|
| `GET` | `/api/applications` | List application summaries |
| `POST` | `/api/applications` | Create an application (nested business/guarantor/credit/loan/equipment) |
| `GET` | `/api/applications/{id}` | Get full application |
| `PUT` | `/api/applications/{id}` | Replace an application |
| `PATCH` | `/api/applications/{id}` | Update provided sections |
| `DELETE` | `/api/applications/{id}` | Delete |

### Underwriting
| Method | Path | Description |
|---|---|---|
| `POST` | `/api/applications/{id}/underwrite` | Run underwriting; returns the completed run + ranked results |
| `GET` | `/api/applications/{id}/runs` | List runs for an application |
| `GET` | `/api/runs/{id}` | Get a run (status, derived features, results) |
| `GET` | `/api/runs/{id}/results` | Get just the match results |

### Lenders & policies
| Method | Path | Description |
|---|---|---|
| `GET` | `/api/lenders` | List lenders |
| `GET` | `/api/lenders/{id}` | Lender with programs + rules |
| `POST` | `/api/lenders` | Create a lender (normalized payload) |
| `PATCH` / `DELETE` | `/api/lenders/{id}` | Update / delete a lender |
| `POST` | `/api/lenders/{id}/programs` | Add a program |
| `PATCH` / `DELETE` | `/api/programs/{id}` | Update / delete a program |
| `POST` | `/api/lenders/{id}/rules` | Add a lender-wide rule |
| `POST` | `/api/programs/{id}/rules` | Add a program rule |
| `PATCH` / `DELETE` | `/api/rules/{id}` | Update / delete a rule |

### Reference
| Method | Path | Description |
|---|---|---|
| `GET` | `/api/rule-types` | All rule types + their editable params (drives the editor UI) |
| `GET` | `/api/enums` | Controlled vocabularies (industries, equipment types, severities) |
| `GET` | `/api/health` | Health check |

---

## Testing

```bash
cd backend && DATABASE_URL=sqlite:///./test.db .venv/bin/python -m pytest -q
# or: make test
```

50 tests on SQLite (no infra):
- `tests/test_rules.py` — unit tests for individual evaluators.
- `tests/test_matching.py` — scenario tests against the **real seeded policies**
  for every lender (tier selection, corp-only/no-PayNet paths, knockouts,
  near-miss ranking).
- `tests/test_api.py` — full HTTP flow incl. editing a policy and seeing the
  outcome change, and creating a lender via the API.

Frontend type-check / build: `cd frontend && npm run build`.

---

## Project layout

```
backend/
  app/
    rules/        # declarative rule engine: registry + evaluators (pure)
    matching/     # feature derivation, engine, scoring, ORM adapter
    workflow/     # in-process orchestrator (parallel + retry)
    models/       # SQLAlchemy models + enums
    schemas/      # Pydantic API schemas
    api/          # FastAPI routers
    seed/         # normalized policy data for the 5 lenders + seeder
  tests/          # pytest suite (SQLite)
frontend/
  src/
    pages/        # applications list/new/detail, lenders list/detail
    components/   # layout, match-result card, criterion row, form fields
    api/          # typed API client
docker-compose.yml, Makefile, DECISIONS.md
```

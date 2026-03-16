# CareerSidekick

[![CI](https://github.com/akashadsare/careersidekick/actions/workflows/ci.yml/badge.svg)](https://github.com/akashadsare/careersidekick/actions/workflows/ci.yml)

**CareerSidekick: Your trusty job-hunting buddy.**

Building CareerOps AI — a production-grade job application operations platform with human-in-the-loop approval, multi-portal ATS execution, and outcome analytics.

**Current Phase:** Phase 0 (TinyFish validation) + Phase 1 (MVP workflow) in progress.  
**Status:** Building candidate profile onboarding (M1.1) with resume upload, parsing, and answer library.

## Project Philosophy

This scaffold prioritizes the **hardest half** of the workflow first:

1. **Phase 0:** TinyFish portal integration and failure mode documentation
2. **Phase 1:** Candidate onboarding → approval workflow → live submission → dashboard
3. Phase 2+: Multi-portal coverage, analytics, agency features

## Why this structure

- **Frontend:** SvelteKit + TypeScript for responsive, production-friendly UX
- **Backend:** FastAPI + SQLAlchemy for Python-first orchestration and TinyFish integration
- **Data:** Postgres + Redis (via docker compose) for persistence and async jobs
- **Testing:** Vitest (frontend), pytest (backend) — green before every push
- **Docs First:** PRD, architecture, milestones, portal prompts, failure modes documented upfront

## Reference sources used

Implementation patterns were grounded in the local docs/cookbook files:

- `tiny_fish_documentation.md` (endpoint behavior, SSE events, run lifecycle)
- `what_to_make.md` (challenge constraints and judging rubric)
- `tinyfish-cookbook/README.md` (reference architecture and recipe patterns)
- `tinyfish-cookbook/bestbet/app/webagent.ts` (SSE parsing pattern)
- `tinyfish-cookbook/fast-qa/lib/mino-client.ts` (buffered SSE parsing)
- `tinyfish-cookbook/tinyskills/lib/mino-client.ts` (callbacks and error flow)

## Project layout

```text
careersidekick/
  backend/
    app/
      main.py
      config.py
      models.py
      routes/
        packages.py
        executions.py
      services/
        tinyfish_client.py
  frontend/
    src/
      lib/components/
        ApprovalPanel.svelte
        LiveRunViewer.svelte
      routes/
        +page.svelte
        approval/+page.svelte
        live-run/+page.svelte
```

## Environment setup

1. Copy `.env.example` to `.env` in the project root.
2. Add your TinyFish key:

```bash
TINYFISH_API_KEY=sk-tinyfish-...
```

3. Optional infra for upcoming phases:

```bash
docker compose up -d
```

## Run backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

## Database migrations (Alembic)

Start infra first if needed:

```bash
docker compose up -d
```

Run migrations:

```bash
cd backend
source .venv/bin/activate
alembic upgrade head
```

Current revisions:

- `0001_initial` creates core domain tables
- `0002_submission_run_timing` adds `started_at`, `finished_at`, `duration_ms` on submission runs
- `0003_alert_incidents` adds persisted dashboard incident timeline events
- `0004_resume_and_profile_expansion` adds resume upload, candidate profile fields, and answer library (M1.1)

Create a new migration after schema changes:

```bash
alembic revision --autogenerate -m "describe change"
```

Seed the answer library with 20+ common ATS questions:

```bash
cd backend
source .venv/bin/activate
python -m scripts.seed_answer_library
```

Backend health check:

- `GET http://localhost:8000/health`

## API Endpoints

### Phase 0: TinyFish Portal Integration

See [TINYFISH_PORTAL_PROMPTS.md](./TINYFISH_PORTAL_PROMPTS.md) for goal prompts and field mappings for Greenhouse, Lever, Workday, LinkedIn.

See [PORTAL_FAILURE_MODES.md](./PORTAL_FAILURE_MODES.md) for documented failure modes and workarounds across portals.

### Phase 1: Candidate Profile Onboarding (M1.1)

**Candidate Profile Management:**
- `POST /api/v1/candidates` — Create candidate profile (name, email, location, work auth, preferences)
- `GET /api/v1/candidates/{candidate_id}` — Retrieve candidate profile
- `PATCH /api/v1/candidates/{candidate_id}` — Update candidate profile fields

**Resume Upload & Parsing (M1.1):**
- `POST /api/v1/candidates/{candidate_id}/resumes` — Upload resume (PDF/DOCX), auto-parse to extracted fields
- Returns parsed data: `name`, `email`, `phone`, `location`, `years_experience`, `skills`
- First resume automatically set as primary and pre-populates candidate profile if fields empty

**Answer Library (M1.1):**
- `GET /api/v1/answer-library?category={category}&limit=50` — Get common ATS questions from library
- Categories: `work_auth`, `experience`, `location`, `compensation`, `availability`, `education`, `culture`, `skills`, `compliance`
- `GET /api/v1/candidates/{candidate_id}/answers` — Get all candidate answers to library questions
- `POST /api/v1/candidates/{candidate_id}/answers` — Add/update candidate answer to a library question

### Phase 1: Core Workflow

**Submissions & Execution:**
- `POST /api/v1/packages/preview` — Generate application package preview (fit score, answers, cover note)
- `POST /api/v1/executions/run-sse` — Initiate TinyFish SSE run with streaming iframe URL
- `GET /api/v1/executions` (supports `status`, `draft_id`, `limit`, `offset` query filters)
- `GET /api/v1/executions/page` (supports `status`, `draft_id`, `limit`, `cursor`, `sort_direction`)
- `GET /api/v1/executions/metrics` (supports `days`, default `30`)
- `GET /api/v1/executions/incidents` (supports `limit`, optional `cursor`, optional `days`, optional `state`)
- `POST /api/v1/executions/incidents` — Log incident event (warning, critical, recovered)
- `GET /api/v1/executions/{id}` — Retrieve execution details
- `PATCH /api/v1/executions/{id}/status` — Update execution status with state transitions

**Jobs & Drafts:**
- `GET /api/v1/jobs`, `POST /api/v1/jobs` — Job posting management
- `GET /api/v1/drafts`, `GET /api/v1/drafts/{id}`, `PATCH /api/v1/drafts/{id}` — Application draft management
- `GET /api/v1/drafts/{id}/runs` — Retrieve submission runs for a draft

For migration-first deployments, set `AUTO_CREATE_SCHEMA=false` and run Alembic migrations at startup.

Draft and execution statuses are now enum-constrained (`draft|approved|submitted|failed` and `running|completed|failed|cancelled`) across ORM and API models.

Manual execution status transitions are state-validated:

- `running -> running|completed|failed|cancelled`
- `failed -> failed|running`
- `cancelled -> cancelled|running`
- `completed -> completed` only

Execution timing behavior:

- Runs set `started_at` at start.
- Terminal states set `finished_at` and compute `duration_ms`.
- Resuming to `running` clears terminal timing fields from prior attempts.

## Run frontend

```bash
cd frontend
npm install
npm run dev
```

Deployment output is configured with `@sveltejs/adapter-node`.

From repository root, shortcut scripts are also available:

```bash
npm run dev
npm run preview
npm run check
npm run test
```

Frontend validation:

```bash
cd frontend
npm run check
npm run test
```

Current frontend test scope includes Live Run Viewer coverage for:

- pagination `total_count` and duration formatting
- failed status update rollback behavior
- successful status update refresh behavior
- dashboard metrics and recent-runs rendering/error states

Open:

- `http://localhost:5173/dashboard`
- `http://localhost:5173/approval`
- `http://localhost:5173/live-run`

## Theme

Light mode palette provided by product owner:

- `#ffc4eb`
- `#ffe4fa`
- `#f1dedc`
- `#e1dabd`
- `#abc798`

Dark mode palette is custom-defined for contrast and readability.

## Current status

This is a planning-to-prototype scaffold, not production yet.

Implemented now:

1. Backend SSE proxy to TinyFish `/run-sse`
2. Operations dashboard route for run health, failure trends, status filter, threshold alerts, sustained degradation detection, mute controls, incident timeline, persisted preferences, and auto-refresh
3. Approval panel UI with editable package preview
4. Live run viewer with progress log + streaming iframe + final result
5. Postgres persistence for candidates, jobs, drafts, and submission runs
6. Alembic migration scaffolding with timing revision for run telemetry
7. State-validated execution transitions with cursor-based history pagination
8. Live execution metrics panel (success rate, average duration, failures by day + trend chart)
9. Backend unit tests for execution timing transition logic (`pytest`)
10. Backend-persisted dashboard incident timeline (cross-session and auditable) with server-side `days` and `state` filtering

Dashboard recent-run rows now deep-link into Live Run Viewer with URL query params (`status`, `run_id`, `limit`, `sort_direction`) so operators land directly on filtered history and selected run detail.

Next hard milestones:

1. Add real package generation from profile + answer library
2. Add portal-specific TinyFish prompt templates
3. Add run records and confirmation artifacts
4. Add auth, RBAC, and audit logging for team workflows

## Backend tests

```bash
cd backend
source .venv/bin/activate
ruff check .
pytest -q
```

From repository root:

```bash
npm run backend:lint
npm run backend:test
```

Current test scope includes:

- execution timing transition behavior in `tests/test_execution_timing.py`
- execution status transition and pagination contract checks in `tests/test_executions_api.py`
- run-sse stream event contract checks in `tests/test_run_sse_contract.py`
- execution metrics aggregation checks in `tests/test_execution_metrics.py`
- alert incident create/list API checks in `tests/test_incidents_api.py`

## Continuous integration

GitHub Actions runs on each push and pull request:

- backend: dependency install + `ruff check .` + `pytest -q`
- frontend: dependency install + `npm run check` + `npm run test` + `npm run build`

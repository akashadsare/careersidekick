# CareerSidekick

[![CI](https://github.com/akashadsare/careersidekick/actions/workflows/ci.yml/badge.svg)](https://github.com/akashadsare/careersidekick/actions/workflows/ci.yml)

CareerSidekick is a minimal, testing-first prototype for a full CareerOps platform.

Tagline: **Your trusty job-hunting buddy.**

This scaffold focuses on the hardest workflow screens first:

1. Application Approval Panel
2. Live TinyFish Run Viewer (SSE + streaming iframe)

## Why this structure

- Frontend: **SvelteKit + TypeScript** for responsive, production-friendly UX.
- Backend: **FastAPI** for Python-first orchestration and TinyFish integration.
- Data infra: Postgres + Redis ready via docker compose.

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

Create a new migration after schema changes:

```bash
alembic revision --autogenerate -m "describe change"
```

Backend health check:

- `GET http://localhost:8000/health`

Main prototype endpoints:

- `POST /api/v1/packages/preview`
- `POST /api/v1/executions/run-sse`
- `GET /api/v1/executions` (supports `status`, `draft_id`, `limit`, `offset` query filters)
- `GET /api/v1/executions/page` (supports `status`, `draft_id`, `limit`, `cursor`, `sort_direction`)
- `GET /api/v1/executions/metrics` (supports `days`, default `30`)
- `GET /api/v1/executions/{id}`
- `PATCH /api/v1/executions/{id}/status`
- `GET /api/v1/candidates`, `POST /api/v1/candidates`
- `GET /api/v1/jobs`, `POST /api/v1/jobs`
- `GET /api/v1/drafts`, `GET /api/v1/drafts/{id}`, `PATCH /api/v1/drafts/{id}`
- `GET /api/v1/drafts/{id}/runs`

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
2. Operations dashboard route for run health, failure trends, status filter, threshold alerts, and persisted preferences
3. Approval panel UI with editable package preview
4. Live run viewer with progress log + streaming iframe + final result
5. Postgres persistence for candidates, jobs, drafts, and submission runs
6. Alembic migration scaffolding with timing revision for run telemetry
7. State-validated execution transitions with cursor-based history pagination
8. Live execution metrics panel (success rate, average duration, failures by day + trend chart)
9. Backend unit tests for execution timing transition logic (`pytest`)

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

Current test scope includes:

- execution timing transition behavior in `tests/test_execution_timing.py`
- execution status transition and pagination contract checks in `tests/test_executions_api.py`
- run-sse stream event contract checks in `tests/test_run_sse_contract.py`
- execution metrics aggregation checks in `tests/test_execution_metrics.py`

## Continuous integration

GitHub Actions runs on each push and pull request:

- backend: dependency install + `ruff check .` + `pytest -q`
- frontend: dependency install + `npm run check` + `npm run test` + `npm run build`

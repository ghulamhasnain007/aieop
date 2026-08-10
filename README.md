# AIEOP — AI Engineering Operations Platform

A working implementation covering all six phases of the project plan: a
FastAPI backend with real auth, RBAC, the unified data model, self-registering
integration adapters, four specialized agents behind a Coordinator, a RAG
knowledge base, risk/health/predictive intelligence, event-driven proactive
detection, a risk-based approval workflow with a full audit log, and a React
dashboard.

## What's implemented and tested

**Foundation**
- Real auth (FR-001) — password + JWT via `POST /api/auth/register|login`,
  `GET /api/auth/me`. A dev-mode `X-User-Role` header bypass exists only
  when `ENVIRONMENT=development` and no bearer token is sent — a real
  deployment (`ENVIRONMENT=production`) always requires a valid token.
- **RBAC** (FR-021/040) — human roles + per-agent tool permissions. An
  agent's effective permission set is always the intersection of its own
  allow-list, an "AI agent ceiling," and the acting user's own role.
- **Unified data model** (FR-005) — all core entities as SQLAlchemy tables,
  managed by Alembic migrations (`backend/alembic/`).
- **Adapter architecture** (FR-004) — `BaseIntegration` with self-registration.
  Real GitHub (repos/PRs/commits/workflow runs/issues/branches), Taiga,
  and Discord adapters, plus a simulated monitoring adapter standing in
  for Prometheus/Grafana. All degrade to "not configured" rather than
  fabricating data when credentials are missing.

**Agents & reasoning**
- Rule-based intent classifier (FR-008), Coordinator + Project/Developer/
  Incident agents (FR-009–012), root-cause analysis with fact-vs-hypothesis
  evidence (FR-013/014), conversation memory (FR-025).
- RAG knowledge base (FR-015/038) — chunking, a deterministic dependency-free
  embedding (documented swap seam for a real model), cosine-similarity
  retrieval, honest "couldn't find relevant documentation" fallback.

**Intelligence**
- Risk detection across project/code/deployment/incident categories (FR-016).
- Project Health Score — real weighted formula over 5 sub-scores, each
  independently computed and documented (FR-017).
- Predictive sprint-risk model — a small, genuinely explainable logistic
  regression over 4 engineered features, distinct from the deterministic
  scoring (FR-018).
- Timeline reconstruction — walks commit → build → deployment → alert →
  incident chronologically (FR-036).
- Dependency awareness — BFS over `Service.depends_on` to answer "what's
  affected if X fails" (FR-037).
- Technical debt detection — correlates incident frequency with commit
  churn per service (FR-039).

**Autonomous actions**
- Event-driven proactive detection (FR-026/027) — reuses the Incident
  Agent's own correlation logic to auto-create incidents with **no user
  interaction**, verified live: a deployment + alert 3 minutes apart
  auto-creates an incident at 95% confidence.
- Risk-based approval workflow (FR-020–024) — low-risk actions auto-execute,
  medium/high-risk actions queue for human approval; every outcome (success,
  failure, rejection, denial) is written to a complete audit trail.

**Dashboard** — six panels wired to the backend: Overview (health score + risk
signals), Chat, Incidents (list → click for the full timeline reconstruction,
dependency blast-radius, and technical debt signal), Knowledge Base (ingest +
grounded query), Approval Center, and Integration health. A "Load demo data"
button in the top bar seeds one realistic, fully interconnected scenario —
a 4-service dependency chain, a live investigated incident, a sprint in
progress, and a runbook — so a first-time visitor sees a working product
immediately instead of an empty database.

**70/70 backend tests pass** (`pytest`). Frontend builds cleanly (`npm run build`).

## What's still not built

- Global engineering search (FR-035) and full report generation (FR-029) —
  explicitly deprioritized in the project plan.
- Notification management/preferences UI (FR-028).
- A real login screen — JWT auth is fully implemented and tested
  (`POST /api/auth/register|login`, `GET /api/auth/me`), but the dashboard
  still uses a role dropdown for convenience rather than a login form.
- Deployment to a real host (Render/Railway) — deliberately not done yet.

## Running it

### Option A — Docker Compose (Postgres + Redis + backend + frontend)

```bash
cp backend/.env.example backend/.env   # already done in this package; edit to add real tokens
docker compose up --build
```

- Backend: http://localhost:8000 (docs at `/docs`)
- Frontend: http://localhost:5173

### Option B — run the backend locally without Docker (SQLite)

```bash
cd backend
pip install -r requirements.txt --break-system-packages
uvicorn app.main:app --reload
```

Uses a local `aieop.db` SQLite file automatically (`app/config.py`) — no
Postgres needed for local dev/testing. Tables are created automatically on
startup; see the Migrations section below for how schema changes are
actually managed once you're past this bootstrap step.

### Frontend locally

```bash
cd frontend
npm install
npm run dev
```

Proxies `/api` to `http://localhost:8000` by default — set
`VITE_API_PROXY_TARGET` to point elsewhere.

### Running tests

```bash
cd backend
pytest -v
```

### Database migrations (Alembic)

`app.main`'s startup hook calls `Base.metadata.create_all()` as a
convenience for a totally fresh database — it never *alters* an existing
table, so it's always safe to run alongside Alembic. Alembic is the actual
source of truth for schema changes:

```bash
cd backend
alembic revision --autogenerate -m "describe your change"
alembic upgrade head      # apply
alembic downgrade base    # roll all the way back (tested, works cleanly)
```

`alembic/env.py` reads `DATABASE_URL` from `app.config.settings`, so it
targets whatever database your `.env`/environment points at (SQLite locally,
Postgres in docker-compose) — no separate config to keep in sync.

## Trying it out

The fastest way to see the whole system working: start it (Docker or
local, see below), open the dashboard, and click **"Load demo data"** in
the top bar. That seeds one realistic scenario — a 4-service dependency
chain, a live investigated incident (95% root-cause confidence), a sprint
in progress, and a runbook — and every panel immediately has real data to
show. From there:

- **Overview** — see the computed health score and risk signals
- **Incidents** — click the seeded incident to see its full timeline,
  what would be affected if the service failed, and any tech-debt signal
- **Knowledge Base** — ask *"what should I do about payment timeouts?"*
  and get a grounded answer citing the seeded runbook
- **Chat** — ask *"will we finish sprint 14?"* or *"why did the payment
  service fail?"*

To reproduce the same scenario by hand instead (e.g. to see the raw API
calls), the seed logic lives in `backend/app/demo/seed.py` and is also
exposed as `POST /api/demo/seed`.

## Project layout

```
backend/
  alembic/                    schema migrations
  app/
    config.py                  settings (env-driven)
    database.py                 SQLAlchemy engine/session
    models/entities.py          unified data model (FR-005)
    auth/security.py            password hashing + JWT (FR-001)
    rbac/permissions.py         roles + agent permission intersection (FR-021)
    integrations/                BaseIntegration + GitHub/Taiga/Discord/simulated-monitoring
    agents/
      intent_classifier.py
      coordinator.py
      project_agent.py / developer_agent.py / incident_agent.py
    knowledge/                   embeddings.py + rag_service.py (FR-015)
    intelligence/
      risk_detection.py          FR-016
      health_score.py            FR-017
      predictive.py               FR-018
      timeline.py                 FR-036
      dependencies.py             FR-037
      tech_debt.py                 FR-039
    events/proactive_detection.py  FR-026/027
    actions/service.py               approval workflow + audit log (FR-020-024)
    demo/seed.py                      one-click demo data (interconnected scenario)
    memory/conversation_memory.py
    api/                          FastAPI routers
  tests/                          pytest suite (70 tests)
frontend/
  src/
    App.jsx                       sidebar + view routing
    context/AppStateContext.jsx    shared project selection + role, across all panels
    components/
      Overview.jsx                  health score + risk signals
      ChatPanel.jsx                  natural-language interface
      Incidents.jsx                  list + timeline + dependencies + tech debt
      KnowledgeBase.jsx               document ingestion + grounded RAG query
      ApprovalCenter.jsx              human-in-the-loop actions + audit trail
      IntegrationHealth.jsx
      ProjectSwitcher.jsx             project picker + demo seed + quick create
      EvidenceTrail.jsx               fact/hypothesis evidence chain visualization
docker-compose.yml
```

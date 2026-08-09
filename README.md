# AIEOP — AI Engineering Operations Platform

Implementation of Phases 0–4 (and slices of 5–6) from the project plan: a
working FastAPI backend with RBAC, the unified data model, self-registering
integration adapters, a rule-based intent classifier, and three specialized
agents (Project, Developer, Incident) behind a Coordinator — plus a React
dashboard with a chat interface and an integration health panel.

## What's actually implemented and tested right now

- **Unified data model** (FR-005) — all core entities as SQLAlchemy tables.
- **RBAC** (FR-021/040) — human roles + per-agent tool permissions. An
  agent's effective permission set is always the intersection of its own
  allow-list, an "AI agent ceiling," and the acting user's own role — an
  agent can never do more than the human it's acting for could do. See
  `backend/app/rbac/permissions.py` and `backend/tests/test_rbac.py`.
- **Adapter architecture** (FR-004) — `BaseIntegration` abstract class with
  self-registration. Real GitHub, Taiga, and Discord adapters (they degrade
  to "not configured" rather than fabricating data if you haven't added
  credentials yet), plus a simulated monitoring adapter standing in for
  Prometheus/Grafana.
- **Intent classifier** (FR-008) — rule-based, returns the exact
  `{intent, domain, confidence, requires_write, risk_level}` contract.
- **Coordinator + Project/Developer/Incident agents** (FR-009/010/011/012) —
  routes natural-language requests, calls the right agent, and returns an
  evidence-backed answer. Low-confidence requests trigger clarification
  instead of a guess.
- **Root-cause analysis with evidence** (FR-013/014) — the Incident Agent
  correlates alerts → deployments → builds → commits by time proximity,
  assigns a confidence score, and explicitly labels each piece of evidence
  as `fact` or `hypothesis`. Verified end-to-end against a seeded scenario:
  a deployment followed 3 minutes later by an error-rate alert produces a
  95%-confidence root cause with a full evidence chain and rollback
  recommendation — see `backend/tests/test_incident_agent.py`.
- **Never fabricates** (FR-032/033) — when there's no data to reason from,
  agents say so explicitly instead of inventing an answer. Also tested.
- **Dashboard** — chat interface with an "evidence trail" visualization
  (fact vs. hypothesis, connected chain) and an integration health panel.

19/19 backend tests pass (`pytest`). Frontend builds cleanly (`npm run build`).

## What's still a stub / not yet built

- Real JWT auth (`app/api/deps.py` is a dev-mode header stub — see the
  warning in that file. Don't deploy this beyond local dev as-is).
- Vector DB / RAG pipeline (Phase 3), predictive sprint-risk model,
  project health scoring, risk-based approval workflow + audit log UI
  (Phase 5–6), event-driven proactive detection (FR-026/027).
- GitHub Actions / CI adapter.
- Alembic migrations (currently `Base.metadata.create_all` on startup).

These are the next things to build, in the order laid out in the project
plan's Phase 3 → Phase 6.

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

This uses a local `aieop.db` SQLite file automatically (see
`app/config.py`) — no Postgres needed for local development/testing.

### Frontend locally

```bash
cd frontend
npm install
npm run dev
```

By default it proxies `/api` to `http://localhost:8000` — point
`VITE_API_PROXY_TARGET` elsewhere if your backend runs somewhere else.

### Running tests

```bash
cd backend
pytest -v
```

## Trying the incident-investigation demo scenario by hand

The seed script below reproduces the FR-013 example from the requirements
doc (deployment → error spike 3 minutes later → alert). Run it against a
fresh `aieop.db`, then ask the chat interface (or `POST /api/chat`) *"why
did the payment service fail?"* — you'll get a real evidence-backed root
cause, not a canned response.

```bash
cd backend
python3 - <<'PY'
from datetime import datetime, timedelta
from app.database import SessionLocal, Base, engine
from app.models.entities import Project, Service, Repository, Commit, Build, Deployment, Alert

Base.metadata.create_all(bind=engine)
db = SessionLocal()

project = Project(name="Payments Platform"); db.add(project); db.commit(); db.refresh(project)
service = Service(project_id=project.id, name="payment-service", owner="ahmed")
db.add(service); db.commit(); db.refresh(service)
repo = Repository(project_id=project.id, provider="github", external_id="org/payments", name="payments")
db.add(repo); db.commit(); db.refresh(repo)
commit = Commit(repository_id=repo.id, sha="abc123def456", author="ahmed",
                 message="Change token expiration handling", committed_at=datetime.utcnow()-timedelta(hours=1))
db.add(commit); db.commit(); db.refresh(commit)
build = Build(repository_id=repo.id, provider="github_actions", external_id="run-382",
              status="passed", triggered_by_commit_id=commit.id)
db.add(build); db.commit(); db.refresh(build)
deploy_time = datetime.utcnow() - timedelta(minutes=40)
deployment = Deployment(service_id=service.id, build_id=build.id, environment="production",
                         status="completed", deployed_at=deploy_time)
db.add(deployment); db.commit(); db.refresh(deployment)
alert = Alert(service_id=service.id, source="simulated", severity="critical",
              message="Error rate for payment-service exceeded 5% threshold",
              triggered_at=deploy_time + timedelta(minutes=3))
db.add(alert); db.commit()

print("SERVICE_ID:", service.id)
PY
```

Then: `curl -X POST localhost:8000/api/chat -H "Content-Type: application/json" -d '{"message":"why did the payment service fail? service: <SERVICE_ID>"}'`

## Project layout

```
backend/
  app/
    config.py            settings (env-driven)
    database.py           SQLAlchemy engine/session
    models/entities.py    unified data model (FR-005)
    rbac/permissions.py   roles + agent permission intersection (FR-021)
    integrations/         BaseIntegration + GitHub/Taiga/Discord/simulated-monitoring adapters
    agents/
      intent_classifier.py
      coordinator.py
      project_agent.py
      developer_agent.py
      incident_agent.py
    memory/conversation_memory.py
    api/                  FastAPI routers
  tests/                  pytest suite (19 tests)
frontend/
  src/
    App.jsx                sidebar + view routing
    components/
      ChatPanel.jsx         natural-language interface
      EvidenceTrail.jsx      fact/hypothesis evidence chain visualization
      IntegrationHealth.jsx
docker-compose.yml
```

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import Base, engine
from app import models  # noqa: F401  - ensures models are registered on Base.metadata
from app import integrations  # noqa: F401  - triggers adapter self-registration
from app.api import (
    routes_chat, routes_integrations, routes_projects, routes_health,
    routes_actions, routes_knowledge, routes_predictions, routes_events, routes_auth,
    routes_intelligence,
)

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten before anything beyond local dev
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    # Dev convenience: create tables directly if they don't exist yet
    # (e.g. a fresh SQLite file, or a first `docker compose up`). This is
    # a fallback, NOT the source of truth for schema changes - once you
    # have a real deployment, manage schema changes with Alembic instead:
    #   cd backend && alembic revision --autogenerate -m "..." && alembic upgrade head
    # `create_all` never alters existing tables, so running Alembic
    # migrations afterward is always safe.
    Base.metadata.create_all(bind=engine)


app.include_router(routes_health.router)
app.include_router(routes_chat.router)
app.include_router(routes_integrations.router)
app.include_router(routes_projects.router)
app.include_router(routes_actions.router)
app.include_router(routes_actions.audit_router)
app.include_router(routes_knowledge.router)
app.include_router(routes_predictions.router)
app.include_router(routes_events.router)
app.include_router(routes_auth.router)
app.include_router(routes_intelligence.router)

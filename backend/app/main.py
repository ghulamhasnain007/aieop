from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import Base, engine
from app import models  # noqa: F401  - ensures models are registered on Base.metadata
from app import integrations  # noqa: F401  - triggers adapter self-registration
from app.api import routes_chat, routes_integrations, routes_projects, routes_health

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten before anything beyond local dev
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    # For the FYP's dev/sqlite path, create tables directly. Once on
    # Postgres, replace this with Alembic migrations (see README).
    Base.metadata.create_all(bind=engine)


app.include_router(routes_health.router)
app.include_router(routes_chat.router)
app.include_router(routes_integrations.router)
app.include_router(routes_projects.router)

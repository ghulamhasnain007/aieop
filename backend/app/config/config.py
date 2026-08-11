"""
Central configuration. All values overridable via environment variables / .env.

DATABASE_URL defaults to a local SQLite file so the backend can be run and
tested WITHOUT docker/postgres during early development. In docker-compose,
this is overridden to the Postgres connection string.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "AI Engineering Operations Platform"
    environment: str = "development"

    database_url: str = "sqlite:///./aieop.db"
    redis_url: str = "redis://localhost:6379/0"

    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 12

    # GitHub - the sole external integration (see project decision: GitHub-only focus)
    github_token: str | None = None

    # LLM (Anthropic) - optional. Without a key, the platform still works:
    # RAG falls back to extractive excerpts and agent answers fall back to
    # their deterministic templates. See app.llm.client for the fallback logic.
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-5"

    # Agent behaviour
    max_agent_loop_iterations: int = 8
    low_confidence_threshold: float = 0.55


settings = Settings()

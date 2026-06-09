"""
Central settings for every Vitrine service (pydantic-settings).

Reads from the repo-root `.env`. Defaults are chosen so the whole stack runs
with ZERO external services: SQLite file + in-memory event bus + in-memory
cache. Flip DATABASE_URL/EVENT_BUS/CACHE to Postgres+Redis later.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # core ---------------------------------------------------------------
    ENV: str = "local"
    SECRET_KEY: str = "dev-only-change-me"
    # DEFAULT = SQLite (now). Postgres later:
    #   postgresql+asyncpg://vitrine:vitrine@localhost:5432/vitrine
    DATABASE_URL: str = "sqlite+aiosqlite:///./vitrine.db"
    FRONTEND_ORIGIN: str = "http://localhost:5173"

    # infra selection: 'memory' (zero-dep dev) | 'redis'
    EVENT_BUS: str = "memory"
    CACHE: str = "memory"
    REDIS_URL: str = "redis://localhost:6379/0"

    # auth ---------------------------------------------------------------
    JWT_ALG: str = "HS256"
    JWT_ACCESS_TTL: int = 900           # 15 min
    JWT_REFRESH_TTL: int = 1209600      # 14 days

    # openai -------------------------------------------------------------
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_EMBED_MODEL: str = "text-embedding-3-small"
    OPENAI_DAILY_LIMIT_USD: float = 5.0
    AGENT_MAX_RETRIES: int = 2
    AGENT_RUN_BUDGET_TOKENS: int = 20000

    # commerce -----------------------------------------------------------
    PAYMENT_PROVIDER: str = "mock"      # mock | stripe
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""

    # hosting / previews -------------------------------------------------
    ALLOWED_PREVIEW_HOSTS: str = "vercel.app,preview.vitrine.app,demo.vitrine.app"

    # negotiation rules --------------------------------------------------
    MAX_ACTIVE_REPS_PER_BUYER: int = 2  # see AGENTS.md Buyer Negotiator

    # file storage -------------------------------------------------------
    FILES_ROOT: str = "files"
    CHAT_ATTACHMENT_MAX_BYTES: int = 4 * 1024 * 1024

    # ------------------------------------------------------------------
    @property
    def is_sqlite(self) -> bool:
        return self.DATABASE_URL.startswith("sqlite")

    @property
    def allowed_preview_hosts(self) -> list[str]:
        return [h.strip() for h in self.ALLOWED_PREVIEW_HOSTS.split(",") if h.strip()]

    @property
    def files_root(self) -> Path:
        # backend/shared/settings.py -> repo root
        return Path(__file__).resolve().parents[2] / self.FILES_ROOT


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

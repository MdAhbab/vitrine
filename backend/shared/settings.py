"""
Central settings for every Vitrine service (pydantic-settings).

Reads from the repo-root `.env`. Defaults are chosen so the whole stack runs
with ZERO external services: SQLite file + in-memory event bus + in-memory
cache. Flip DATABASE_URL/EVENT_BUS/CACHE to Postgres+Redis later.
"""
from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


# Sentinel default. `assert_production_safe()` refuses to boot ENV=prod with it.
DEFAULT_SECRET_KEY = "dev-only-change-me"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # core ---------------------------------------------------------------
    ENV: str = "local"
    SECRET_KEY: str = DEFAULT_SECRET_KEY
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

    # gemini (fallback provider) ------------------------------------------
    # Used automatically when OpenAI fails/quota-limits. Each Gemini model
    # carries its own quota, so the client walks GEMINI_MODELS in order.
    GEMINI_API_KEY: str = ""
    GEMINI_MODELS: str = (
        "gemini-2.5-flash,gemini-2.5-flash-lite,gemini-3-flash-preview,"
        "gemini-3.1-flash-lite,gemini-3.5-flash,gemini-3.5-flash-lite,"
        "gemini-2.5-pro,gemini-3-pro-preview,gemini-3.1-pro-preview"
    )
    GEMINI_EMBED_MODEL: str = "gemini-embedding-001"

    # commerce -----------------------------------------------------------
    PAYMENT_PROVIDER: str = "mock"      # mock | stripe
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""

    # hosting / previews -------------------------------------------------
    ALLOWED_PREVIEW_HOSTS: str = "vercel.app,preview.vitrine.app,demo.vitrine.app"

    # security -----------------------------------------------------------
    # Only honour X-Forwarded-For when we sit behind a trusted reverse proxy
    # (nginx in the cloud deploy). Off by default so the rate limiter can't be
    # bypassed by a spoofed header in direct-exposure/dev setups.
    TRUST_PROXY_HEADERS: bool = False
    # Domains accepted as evidence of student status for the discounted tier.
    ACADEMIC_EMAIL_SUFFIXES: str = ".edu,.ac.uk,.edu.bd,.ac.bd,.edu.au,.ac.in,.edu.pk,.edu.my,.ac.nz"

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
    def is_prod(self) -> bool:
        return self.ENV.lower() in ("prod", "production")

    def assert_production_safe(self) -> None:
        """Refuse to boot a production server with dev-grade secrets.

        SECRET_KEY signs every JWT *and* derives the Fernet key that encrypts
        stored third-party API keys (see shared/crypto.py). Shipping the default
        means anyone can mint an admin token and decrypt the key vault, so this
        is a hard failure rather than a warning.
        """
        if not self.is_prod:
            return
        problems: list[str] = []
        if self.SECRET_KEY == DEFAULT_SECRET_KEY or len(self.SECRET_KEY) < 32:
            problems.append(
                "SECRET_KEY is unset, default, or shorter than 32 chars — "
                "generate one with: python -c \"import secrets;print(secrets.token_urlsafe(48))\""
            )
        if problems:
            raise RuntimeError(
                "Refusing to start in ENV=prod:\n  - " + "\n  - ".join(problems)
            )

        # Not fatal — a directly-exposed server is a legitimate (if unusual)
        # setup — but behind the shipped nginx it silently breaks rate limiting:
        # every request then buckets under the proxy's own address, so all
        # visitors share one counter and any single user can 429 the whole site.
        if not self.TRUST_PROXY_HEADERS:
            logging.getLogger("vitrine.settings").warning(
                "TRUST_PROXY_HEADERS is off in production. If a reverse proxy "
                "sits in front of this server, rate limits apply to the proxy's "
                "IP instead of the real client — set TRUST_PROXY_HEADERS=true."
            )

    @property
    def allowed_preview_hosts(self) -> list[str]:
        return [h.strip() for h in self.ALLOWED_PREVIEW_HOSTS.split(",") if h.strip()]

    @property
    def gemini_models(self) -> list[str]:
        return [m.strip() for m in self.GEMINI_MODELS.split(",") if m.strip()]

    @property
    def academic_email_suffixes(self) -> list[str]:
        return [s.strip().lower() for s in self.ACADEMIC_EMAIL_SUFFIXES.split(",") if s.strip()]

    @property
    def files_root(self) -> Path:
        # backend/shared/settings.py -> repo root
        return Path(__file__).resolve().parents[2] / self.FILES_ROOT


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

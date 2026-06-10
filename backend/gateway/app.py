"""
API Gateway — the single public entrypoint.

Two ways to run, same code:
  * MONOLITH (recommended for SQLite dev): this app includes every service's
    router, so `uvicorn backend.gateway.app:app` serves the whole API in one
    process. The in-memory event bus then works end-to-end.
  * MICROSERVICES (later): run each `backend.services.<svc>.app:app` on its own
    port; the gateway becomes a thin reverse-proxy/auth layer (TODO Phase 5)
    and EVENT_BUS=redis carries events across processes.

In dev the gateway auto-creates SQLite tables on startup so the API boots with
zero setup. See backend.md §"Step-by-step".
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.shared.settings import settings
from backend.shared.storage import ensure_buckets

# Each service exposes an APIRouter named `router`.
from backend.services.identity.app import router as identity_router
from backend.services.media.app import router as media_router
from backend.services.catalog.app import router as catalog_router
from backend.services.search.app import router as search_router
from backend.services.orders.app import router as orders_router
from backend.services.notifications.app import router as notifications_router
from backend.services.hosting.app import router as hosting_router
from backend.services.reviews.app import router as reviews_router
from backend.services.chats.app import router as chats_router
from backend.ai.app import router as ai_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.ENV == "local" and settings.is_sqlite:
        from backend.shared.db import create_all
        await create_all()
    ensure_buckets()
    # Monolith mode: include-router doesn't run sub-app lifespans, so wire the
    # event-driven agent pipeline (listing.created -> intake -> verify -> score)
    # and notification handlers here.
    from backend.ai.workers import register_handlers
    import backend.services.notifications.app  # noqa: F401 (registers order.paid handler)
    register_handlers()
    if settings.EVENT_BUS == "redis":
        from backend.shared.events import bus
        if hasattr(bus, "start_consumer"):
            await bus.start_consumer()
    yield


app = FastAPI(title="Vitrine API Gateway", version="0.1.0", lifespan=lifespan)

# In local dev, accept ANY localhost/127.0.0.1 port — Vite hops to 5174/5175…
# when 5173 is busy, and a hardcoded origin would silently break every API call
# (the #1 "nothing happens in the UI" cause). In prod, lock to FRONTEND_ORIGIN.
if settings.ENV == "local":
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.FRONTEND_ORIGIN],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

for r in (
    identity_router, catalog_router, search_router, orders_router,
    notifications_router, hosting_router, reviews_router, chats_router, ai_router,
    media_router,
):
    app.include_router(r)

files_dir = settings.files_root
files_dir.mkdir(parents=True, exist_ok=True)
app.mount("/files", StaticFiles(directory=str(files_dir)), name="files")


@app.get("/health")
async def health() -> dict:
    return {"ok": True, "service": "gateway", "env": settings.ENV}


frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if frontend_dist.exists():
    frontend_root = frontend_dist.resolve()
    index_html = frontend_root / "index.html"

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_frontend(full_path: str):
        candidate = (frontend_root / full_path).resolve()
        if candidate.is_file() and (candidate == frontend_root or frontend_root in candidate.parents):
            return FileResponse(candidate)
        return FileResponse(index_html)

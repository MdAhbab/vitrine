"""
Hosting service — preview URL validation, demo health checks, managed hosting.

Scaffold: validates a preview URL against ALLOWED_PREVIEW_HOSTS and returns a
health verdict shape. Real HTTP health polling + managed native-VM hosting are
Phase 2/4 (see backend.md §14 managed preview hosting).
"""
from __future__ import annotations

from urllib.parse import urlparse
import httpx

from fastapi import APIRouter, FastAPI

from backend.shared.settings import settings

router = APIRouter(tags=["hosting"])


def _host_allowed(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(host == h or host.endswith("." + h) for h in settings.allowed_preview_hosts)


@router.get("/hosting/validate")
async def validate(url: str) -> dict:
    return {"url": url, "allowed": _host_allowed(url)}


@router.get("/hosting/health")
async def health_check(url: str) -> dict:
    if not _host_allowed(url):
        return {"url": url, "health": "down", "reason": "host not allow-listed"}
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            res = await client.get(url)
            if res.is_success:
                return {"url": url, "health": "live"}
            else:
                return {"url": url, "health": "degraded", "reason": f"HTTP status {res.status_code}"}
    except Exception as e:
        return {"url": url, "health": "down", "reason": str(e)}


app = FastAPI(title="Vitrine hosting")
app.include_router(router)


@app.get("/health")
async def health() -> dict:
    return {"ok": True, "service": "hosting"}

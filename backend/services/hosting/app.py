"""
Hosting service — preview URL validation, demo health checks, managed hosting.

Scaffold: validates a preview URL against ALLOWED_PREVIEW_HOSTS and returns a
health verdict shape. Real HTTP health polling + managed native-VM hosting are
Phase 2/4 (see backend.md §14 managed preview hosting).
"""
from __future__ import annotations

from urllib.parse import urlparse
import httpx

from fastapi import APIRouter, Depends, FastAPI

from backend.shared.security import rate_limit
from backend.shared.settings import settings

router = APIRouter(tags=["hosting"])

# Preview demos are always public HTTPS pages. Following more hops than this is
# a sign of a redirect loop or an attempt to walk somewhere we shouldn't go.
_MAX_REDIRECTS = 3
_hosting_rate_limit = rate_limit(limit=30, window=60, scope="hosting")


def _host_allowed(url: str) -> bool:
    parsed = urlparse(url)
    # Reject non-HTTP schemes outright: `file://`, `gopher://` and friends are
    # never valid previews and are classic SSRF pivots.
    if parsed.scheme not in ("http", "https"):
        return False
    host = (parsed.hostname or "").lower()
    return any(host == h or host.endswith("." + h) for h in settings.allowed_preview_hosts)


@router.get("/hosting/validate", dependencies=[Depends(_hosting_rate_limit)])
async def validate(url: str) -> dict:
    return {"url": url, "allowed": _host_allowed(url)}


@router.get("/hosting/health", dependencies=[Depends(_hosting_rate_limit)])
async def health_check(url: str) -> dict:
    if not _host_allowed(url):
        return {"url": url, "health": "down", "reason": "host not allow-listed"}
    try:
        # Redirects are followed MANUALLY so every hop is re-checked against the
        # allow-list. With httpx's follow_redirects=True only the first URL is
        # validated, so an allow-listed `*.vercel.app` page could 302 us into
        # the cloud metadata endpoint or an internal service.
        async with httpx.AsyncClient(timeout=5.0, follow_redirects=False) as client:
            target = url
            for _ in range(_MAX_REDIRECTS + 1):
                res = await client.get(target)
                if not res.is_redirect:
                    if res.is_success:
                        return {"url": url, "health": "live"}
                    return {"url": url, "health": "degraded",
                            "reason": f"HTTP status {res.status_code}"}
                target = str(res.next_request.url) if res.next_request else ""
                if not _host_allowed(target):
                    return {"url": url, "health": "down",
                            "reason": "redirected off the allow-listed host"}
            return {"url": url, "health": "down", "reason": "too many redirects"}
    except Exception as e:
        return {"url": url, "health": "down", "reason": str(e)}


app = FastAPI(title="Vitrine hosting")
app.include_router(router)


@app.get("/health")
async def health() -> dict:
    return {"ok": True, "service": "hosting"}

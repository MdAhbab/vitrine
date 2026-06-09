"""Search service — hybrid constraint + semantic search over live listings."""
from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from backend.shared.db import get_session
from backend.ai.searching import search_listings
from backend.shared.security import Principal, optional_user

router = APIRouter(tags=["search"])


@router.get("/search")
async def search(
    q: str = "",
    category: str | None = None,
    price_max: float | None = None,
    has_demo: bool | None = None,
    user: Principal | None = Depends(optional_user),
    db: AsyncSession = Depends(get_session)
) -> list[dict]:
    use_ai = user is not None
    rows = await search_listings(db, q, k=40, category=category, price_max=price_max, has_demo=has_demo, use_ai=use_ai)
    return [
        {
            "id": r.id,
            "slug": r.slug,
            "name": r.name,
            "tagline": r.tagline,
            "category": r.category,
            "framework": r.framework,
            "price": r.price_cents / 100,
            "hasDemo": bool(r.demo_url),
            "score": r.vitrine_score,
        }
        for r in rows
    ]


app = FastAPI(title="Vitrine search")
app.include_router(router)


@app.get("/health")
async def health() -> dict:
    return {"ok": True, "service": "search"}

"""
Search service — hybrid (vector + facet + full-text) over listings.

Scaffold: a simple name/tag SQL filter so the UI works today. Phase 2 swaps in
the vector store (ai/vectorstore.py) for semantic ranking. See backend.md §9.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.shared.db import get_session
from backend.shared.models import Listing

from backend.ai.vectorstore import vector_store
from backend.ai.client import client

router = APIRouter(tags=["search"])


@router.get("/search")
async def search(
    q: str = "",
    category: str | None = None,
    price_max: float | None = None,
    has_demo: bool | None = None,
    db: AsyncSession = Depends(get_session)
) -> list[dict]:
    stmt = select(Listing).where(Listing.status == "live")
    if category:
        stmt = stmt.where(Listing.category == category)
    if price_max is not None:
        stmt = stmt.where(Listing.price_cents <= int(price_max * 100))
    if has_demo is not None:
        if has_demo:
            stmt = stmt.where(Listing.demo_url.isnot(None))
        else:
            stmt = stmt.where(Listing.demo_url.is_(None))

    if not q:
        stmt = stmt.order_by(Listing.vitrine_score.desc()).limit(40)
        rows = (await db.execute(stmt)).scalars().all()
        return [{"id": r.id, "slug": r.slug, "name": r.name, "score": r.vitrine_score} for r in rows]

    try:
        query_vec = await client.embed(q)
        matches = await vector_store.search(db, query_vec, k=100)
        
        listing_ids = [m[0] for m in matches]
        scores = {m[0]: m[1] for m in matches}
        
        if not listing_ids:
            return []
            
        stmt = stmt.where(Listing.id.in_(listing_ids))
        rows = (await db.execute(stmt)).scalars().all()
        
        res = []
        for r in rows:
            res.append({
                "id": r.id,
                "slug": r.slug,
                "name": r.name,
                "score": scores.get(r.id, 0.0)
            })
        res.sort(key=lambda x: x["score"], reverse=True)
        return res[:40]
    except Exception:
        stmt = stmt.where((Listing.name.ilike(f"%{q}%")) | (Listing.tagline.ilike(f"%{q}%")))
        stmt = stmt.order_by(Listing.vitrine_score.desc()).limit(40)
        rows = (await db.execute(stmt)).scalars().all()
        return [{"id": r.id, "slug": r.slug, "name": r.name, "score": r.vitrine_score} for r in rows]


app = FastAPI(title="Vitrine search")
app.include_router(router)


@app.get("/health")
async def health() -> dict:
    return {"ok": True, "service": "search"}

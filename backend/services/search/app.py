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
async def search(q: str = "", db: AsyncSession = Depends(get_session)) -> list[dict]:
    if not q:
        stmt = select(Listing).where(Listing.status == "live")
        stmt = stmt.order_by(Listing.vitrine_score.desc()).limit(40)
        rows = (await db.execute(stmt)).scalars().all()
        return [{"id": r.id, "slug": r.slug, "name": r.name, "score": r.vitrine_score} for r in rows]

    try:
        query_vec = await client.embed(q)
        matches = await vector_store.search(db, query_vec, k=40)
        
        listing_ids = [m[0] for m in matches]
        scores = {m[0]: m[1] for m in matches}
        
        if not listing_ids:
            return []
            
        stmt = select(Listing).where(Listing.id.in_(listing_ids), Listing.status == "live")
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
        return res
    except Exception:
        stmt = select(Listing).where((Listing.name.ilike(f"%{q}%")) | (Listing.tagline.ilike(f"%{q}%")), Listing.status == "live")
        stmt = stmt.order_by(Listing.vitrine_score.desc()).limit(40)
        rows = (await db.execute(stmt)).scalars().all()
        return [{"id": r.id, "slug": r.slug, "name": r.name, "score": r.vitrine_score} for r in rows]


app = FastAPI(title="Vitrine search")
app.include_router(router)


@app.get("/health")
async def health() -> dict:
    return {"ok": True, "service": "search"}

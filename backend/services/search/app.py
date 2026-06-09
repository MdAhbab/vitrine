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

router = APIRouter(tags=["search"])


@router.get("/search")
async def search(q: str = "", db: AsyncSession = Depends(get_session)) -> list[dict]:
    stmt = select(Listing).where(Listing.status == "live")
    if q:
        stmt = stmt.where(Listing.name.ilike(f"%{q}%"))
    stmt = stmt.order_by(Listing.vitrine_score.desc()).limit(40)
    rows = (await db.execute(stmt)).scalars().all()
    # TODO Phase 2: hybrid vector + facet fusion via VectorStore.
    return [{"id": r.id, "slug": r.slug, "name": r.name, "score": r.vitrine_score} for r in rows]


app = FastAPI(title="Vitrine search")
app.include_router(router)


@app.get("/health")
async def health() -> dict:
    return {"ok": True, "service": "search"}

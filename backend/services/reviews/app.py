"""
Reviews service — verified-purchase reviews + reputation rollups.

Scaffold: list reviews for a listing (read slice). Creating a review (with
verified-purchase check) + recomputing the listing rating rollup and emitting
`review.created` is Phase 3.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.shared.db import get_session
from backend.shared.models import Review
from backend.shared.security import Principal, current_user

router = APIRouter(tags=["reviews"])


@router.get("/listings/{listing_id}/reviews")
async def list_reviews(listing_id: str, db: AsyncSession = Depends(get_session)) -> list[dict]:
    rows = (await db.execute(
        select(Review).where(Review.listing_id == listing_id)
        .order_by(Review.created_at.desc()))).scalars().all()
    return [{"id": r.id, "rating": r.rating, "body": r.body,
             "verified": r.verified_purchase,
             "ts": int(r.created_at.timestamp() * 1000)} for r in rows]


@router.post("/reviews")
async def create_review(body: dict, user: Principal = Depends(current_user)) -> dict:
    # TODO Phase 3: verify the buyer purchased the listing, insert, recompute
    # rating rollup on the listing, emit review.created (-> Curation re-score).
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "create_review — TODO Phase 3")


app = FastAPI(title="Vitrine reviews")
app.include_router(router)


@app.get("/health")
async def health() -> dict:
    return {"ok": True, "service": "reviews"}

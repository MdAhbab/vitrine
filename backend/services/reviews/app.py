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
from backend.shared.events import bus
from backend.shared.models import Listing, Order, Review
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
async def create_review(body: dict, user: Principal = Depends(current_user),
                        db: AsyncSession = Depends(get_session)) -> dict:
    listing_id = body.get("listing_id")
    rating = body.get("rating")
    review_body = body.get("body", "")
    
    if not listing_id or rating is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Missing listing_id or rating")
        
    rating = int(rating)
    if not (1 <= rating <= 5):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Rating must be between 1 and 5")
        
    # Check purchase verification
    orders = (await db.execute(
        select(Order).where(
            Order.buyer_id == user.id,
            Order.listing_id == listing_id,
            Order.status.in_(["paid", "delivered"])
        )
    )).scalars().all()
    
    verified_purchase = len(orders) > 0
    if not verified_purchase:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only verified buyers can leave a review")
        
    rev = Review(
        listing_id=listing_id,
        buyer_id=user.id,
        rating=rating,
        body=review_body,
        verified_purchase=verified_purchase
    )
    db.add(rev)
    await db.commit()
    
    # Recompute rating rollup
    all_revs = (await db.execute(
        select(Review).where(Review.listing_id == listing_id)
    )).scalars().all()
    
    cnt = len(all_revs)
    avg_rating = sum(r.rating for r in all_revs) / cnt if cnt > 0 else 0.0
    
    dist = [0, 0, 0, 0, 0]
    for star in [5, 4, 3, 2, 1]:
        star_cnt = sum(1 for r in all_revs if r.rating == star)
        dist[5 - star] = round(star_cnt * 100 / cnt) if cnt > 0 else 0
        
    listing = await db.get(Listing, listing_id)
    if listing:
        listing.rating = round(avg_rating, 2)
        listing.reviews_count = cnt
        listing.rating_distribution = dist
        db.add(listing)
        await db.commit()
        
    await bus.publish("review.created", {"listing_id": listing_id}, actor=f"user:{user.id}")
    
    return {"status": "success", "rating": avg_rating, "reviews_count": cnt}


app = FastAPI(title="Vitrine reviews")
app.include_router(router)


@app.get("/health")
async def health() -> dict:
    return {"ok": True, "service": "reviews"}

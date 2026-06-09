"""
Catalog service — listings CRUD, intake trigger, feature requests.

Working slice: browse list + fetch-by-slug (the storefront's core reads).
Write paths (create/intake/update/delete/submit) are stubbed with the right
shapes for the next AI to implement. See backend.md step-by-step Phase 2.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.shared.db import get_session
from backend.shared.events import bus
from backend.shared.ids import slugify
from backend.shared.models import Listing, ListingField, ListingTier, User
from backend.shared.schemas.listing import IntakeIn, ListingCreateIn, ProductOut
from backend.shared.security import Principal, current_user, require_role

from .serializers import to_product

router = APIRouter(tags=["catalog"])


async def _load(db: AsyncSession, listing: Listing) -> ProductOut:
    seller = await db.get(User, listing.owner_id)
    tiers = (await db.execute(select(ListingTier).where(ListingTier.listing_id == listing.id))).scalars().all()
    fields = (await db.execute(select(ListingField).where(ListingField.listing_id == listing.id))).scalars().all()
    return to_product(listing, seller, list(tiers), list(fields))


@router.get("/listings", response_model=list[ProductOut])
async def list_listings(
    db: AsyncSession = Depends(get_session),
    category: str | None = None,
    tag: str | None = None,
    sort: str = "vitrine_score",
    q: str | None = None,
    limit: int = Query(60, le=200),
    offset: int = 0,
) -> list[ProductOut]:
    stmt = select(Listing).where(Listing.status == "live")
    if category:
        stmt = stmt.where(Listing.category == category)
    if q:
        stmt = stmt.where(Listing.name.ilike(f"%{q}%"))
    order = Listing.vitrine_score.desc() if sort == "vitrine_score" else Listing.created_at.desc()
    stmt = stmt.order_by(order).limit(limit).offset(offset)
    rows = (await db.execute(stmt)).scalars().all()
    out = [await _load(db, r) for r in rows]
    if tag:  # simple post-filter on JSON tags (pgvector/GIN later)
        out = [p for p in out if tag in p.tags]
    return out


@router.get("/listings/{slug}", response_model=ProductOut)
async def get_listing(slug: str, db: AsyncSession = Depends(get_session)) -> ProductOut:
    listing = (await db.execute(select(Listing).where(Listing.slug == slug))).scalar_one_or_none()
    if not listing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Listing not found")
    return await _load(db, listing)


@router.post("/listings", response_model=ProductOut, status_code=201)
async def create_listing(
    body: ListingCreateIn,
    user: Principal = Depends(require_role("seller", "admin")),
    db: AsyncSession = Depends(get_session),
) -> ProductOut:
    listing = Listing(
        owner_id=user.id, name=body.name, slug=slugify(body.name),
        tagline=body.tagline, category=body.category,
        price_cents=int(body.price * 100), status="draft",
    )
    db.add(listing)
    await db.commit()
    await db.refresh(listing)
    await bus.publish("listing.created", {"listing_id": listing.id}, actor=f"user:{user.id}")
    return await _load(db, listing)


@router.post("/listings/{listing_id}/intake")
async def trigger_intake(
    listing_id: str, body: IntakeIn,
    user: Principal = Depends(require_role("seller", "admin")),
) -> dict:
    # Publishing the event lets the Repo-Intake agent fill the form sheet async.
    await bus.publish(
        "listing.created",
        {"listing_id": listing_id, "repo_url": body.repo_url, "readme_text": body.readme_text},
        actor=f"user:{user.id}",
    )
    return {"status": "enriching", "listing_id": listing_id}


@router.patch("/listings/{listing_id}", response_model=ProductOut)
async def update_listing(listing_id: str, patch: dict,
                         user: Principal = Depends(require_role("seller", "admin")),
                         db: AsyncSession = Depends(get_session)) -> ProductOut:
    # TODO: validate ownership + apply field patches into listing_fields/listing.
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "update_listing — TODO Phase 2")


@router.delete("/listings/{listing_id}", status_code=204)
async def delete_listing(listing_id: str,
                         user: Principal = Depends(require_role("seller", "admin")),
                         db: AsyncSession = Depends(get_session)) -> None:
    listing = await db.get(Listing, listing_id)
    if not listing or (listing.owner_id != user.id and user.role != "admin"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Listing not found")
    await db.delete(listing)
    await db.commit()


# feature-requests live here (catalog owns the listing relationship)
@router.post("/feature-requests")
async def create_feature_request(body: dict,
                                 user: Principal = Depends(current_user)) -> dict:
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "feature-requests — TODO Phase 3")


app = FastAPI(title="Vitrine catalog")
app.include_router(router)


@app.get("/health")
async def health() -> dict:
    return {"ok": True, "service": "catalog"}

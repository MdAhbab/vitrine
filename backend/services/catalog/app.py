"""
Catalog service — listings CRUD, intake trigger, feature requests.

Working slice: browse list + fetch-by-slug (the storefront's core reads).
Write paths (create/intake/update/delete/submit) are stubbed with the right
shapes for the next AI to implement. See backend.md step-by-step Phase 2.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, status, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.shared.db import get_session
from backend.shared.events import bus
from backend.shared.ids import slugify
from backend.shared.models import Listing, ListingField, ListingTier, User, FeatureRequest
from backend.shared.schemas.listing import IntakeIn, ListingCreateIn, ProductOut
from backend.shared.security import Principal, current_user, require_role, optional_user

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
    owner: str | None = None,
    user: Principal | None = Depends(optional_user),
) -> list[ProductOut]:
    if owner == "me":
        if not user:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication required for owner=me")
        stmt = select(Listing).where(Listing.owner_id == user.id)
    else:
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
    listing = await db.get(Listing, listing_id)
    if not listing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Listing not found")
    if listing.owner_id != user.id and user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Forbidden")
    
    if "name" in patch:
        listing.name = patch["name"]
        listing.slug = slugify(patch["name"])
    if "tagline" in patch:
        listing.tagline = patch["tagline"]
    if "category" in patch:
        listing.category = patch["category"]
    if "framework" in patch:
        listing.framework = patch["framework"]
    if "price" in patch:
        listing.price_cents = int(patch["price"] * 100)
    if "description" in patch:
        listing.description = patch["description"]
    if "cover" in patch:
        listing.cover = patch["cover"]
    if "screenshots" in patch:
        listing.screenshots = patch["screenshots"]
    if "tags" in patch:
        listing.tags = patch["tags"]
    if "sdlc" in patch:
        listing.sdlc = patch["sdlc"]
    if "business_model" in patch:
        listing.business_model = patch["business_model"]
    if "businessModel" in patch:
        listing.business_model = patch["businessModel"]
    if "tech_stack" in patch:
        listing.tech_stack = patch["tech_stack"]
    if "techStack" in patch:
        listing.tech_stack = patch["techStack"]
    if "ai_draft" in patch:
        listing.ai_draft = patch["ai_draft"]
    if "aiDraft" in patch:
        listing.ai_draft = patch["aiDraft"]
        
    await db.commit()
    await db.refresh(listing)
    
    await bus.publish("listing.updated", {"listing_id": listing.id}, actor=f"user:{user.id}")
    return await _load(db, listing)


@router.delete("/listings/{listing_id}", status_code=204)
async def delete_listing(listing_id: str,
                         user: Principal = Depends(require_role("seller", "admin")),
                         db: AsyncSession = Depends(get_session)):
    listing = await db.get(Listing, listing_id)
    if not listing or (listing.owner_id != user.id and user.role != "admin"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Listing not found")
    await db.delete(listing)
    await db.commit()
    return Response(status_code=204)


# feature-requests live here (catalog owns the listing relationship)
@router.post("/feature-requests")
async def create_feature_request(body: dict,
                                 user: Principal = Depends(current_user),
                                 db: AsyncSession = Depends(get_session)) -> dict:
    listing_id = body.get("listing_id")
    description = body.get("description", "")
    if not listing_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Missing listing_id")
    
    listing = await db.get(Listing, listing_id)
    if not listing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Listing not found")
        
    from backend.ai.agents.feature_estimator import estimate
    try:
        est = await estimate(listing_id, description)
        charge_cents = int(est.get("estimated_charge", 0) * 100)
    except Exception:
        charge_cents = (280 + len(description) * 12) * 100

    req = FeatureRequest(
        buyer_id=user.id,
        listing_id=listing_id,
        description=description,
        estimated_charge_cents=charge_cents,
        status="pending_dev_approval",
    )
    db.add(req)
    await db.commit()
    await db.refresh(req)
    
    return {
        "id": req.id,
        "listing_id": req.listing_id,
        "description": req.description,
        "estimated_charge_cents": req.estimated_charge_cents,
        "status": req.status,
    }


@router.patch("/feature-requests/{id}/quote")
async def quote_feature_request(id: str, body: dict,
                                 user: Principal = Depends(require_role("seller", "admin")),
                                 db: AsyncSession = Depends(get_session)) -> dict:
    req = await db.get(FeatureRequest, id)
    if not req:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Feature request not found")
        
    listing = await db.get(Listing, req.listing_id)
    if not listing or (listing.owner_id != user.id and user.role != "admin"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Forbidden")
        
    dev_charge = body.get("developer_charge")
    if dev_charge is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Missing developer_charge")
        
    req.developer_charge_cents = int(dev_charge * 100)
    req.developer_approved = True
    req.status = "pending_buyer_approval"
    
    await db.commit()
    await db.refresh(req)
    return {
        "id": req.id,
        "status": req.status,
        "developer_charge_cents": req.developer_charge_cents,
    }


@router.post("/feature-requests/{id}/approve")
async def approve_feature_request(id: str,
                                   user: Principal = Depends(current_user),
                                   db: AsyncSession = Depends(get_session)) -> dict:
    req = await db.get(FeatureRequest, id)
    if not req:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Feature request not found")
    if req.buyer_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Forbidden")
        
    req.status = "approved"
    await db.commit()
    await db.refresh(req)
    return {
        "id": req.id,
        "status": req.status,
    }


app = FastAPI(title="Vitrine catalog")
app.include_router(router)


@app.get("/health")
async def health() -> dict:
    return {"ok": True, "service": "catalog"}

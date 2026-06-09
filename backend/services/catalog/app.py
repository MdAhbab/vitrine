"""
Catalog service — listings CRUD, intake trigger, feature requests.

Working slice: browse list + fetch-by-slug (the storefront's core reads).
Write paths (create/intake/update/delete/submit) are stubbed with the right
shapes for the next AI to implement. See backend.md step-by-step Phase 2.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, status, Response
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from backend.shared.db import get_session
from backend.shared.events import bus
from backend.shared.ids import slugify
from backend.shared.models import Listing, ListingField, ListingTier, User, FeatureRequest, Chat, ChatMessage, AnalyticEvent, Order, AdminConfig
from backend.shared.schemas.listing import IntakeIn, ListingCreateIn, ProductOut, AnalyticsEventIn, SellerAnalyticsOut, AdminAnalyticsOut
from backend.shared.security import Principal, current_user, require_role, optional_user, ai_rate_limit


from .serializers import to_product

router = APIRouter(tags=["catalog"])


async def _unique_slug(db: AsyncSession, name: str, exclude_id: str | None = None) -> str:
    """slug is UNIQUE; append -2, -3… on collision so duplicate names don't 500."""
    base = slugify(name)
    slug, i = base, 2
    while True:
        existing = (await db.execute(
            select(Listing).where(Listing.slug == slug))).scalar_one_or_none()
        if not existing or existing.id == exclude_id:
            return slug
        slug, i = f"{base}-{i}", i + 1


async def _load(db: AsyncSession, listing: Listing) -> ProductOut:
    seller = await db.get(User, listing.owner_id)
    tiers = (await db.execute(select(ListingTier).where(ListingTier.listing_id == listing.id))).scalars().all()
    fields = (await db.execute(select(ListingField).where(ListingField.listing_id == listing.id))).scalars().all()
    return to_product(listing, seller, list(tiers), list(fields))


async def cleanup_expired_listings(db: AsyncSession) -> None:
    try:
        now = datetime.now(timezone.utc)
        three_months_ago = now - timedelta(days=90)
        stmt = delete(Listing).where(Listing.expires_at < now, Listing.updated_at < three_months_ago)
        await db.execute(stmt)
        await db.commit()
    except Exception as e:
        print("Error cleaning up expired listings:", e)


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
    await cleanup_expired_listings(db)
    
    if owner == "me":
        if not user:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication required for owner=me")
        stmt = select(Listing).where(Listing.owner_id == user.id)
    else:
        now = datetime.now(timezone.utc)
        stmt = select(Listing).where(
            Listing.status == "live",
            (Listing.expires_at == None) | (Listing.expires_at > now)
        )

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
async def get_listing(slug: str, db: AsyncSession = Depends(get_session),
                      user: Principal | None = Depends(optional_user)) -> ProductOut:
    listing = (await db.execute(select(Listing).where(Listing.slug == slug))).scalar_one_or_none()
    if not listing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Listing not found")
    now = datetime.now(timezone.utc)
    is_expired = listing.expires_at is not None and listing.expires_at < now
    if listing.status != "live" or is_expired:
        is_owner = user and listing.owner_id == user.id
        is_admin = user and user.role == "admin"
        if not is_owner and not is_admin:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Listing not found")

    try:
        event = AnalyticEvent(
            listing_id=listing.id,
            event_type="view",
            actor_id=user.id if user else None
        )
        db.add(event)
        await db.commit()
    except Exception:
        pass

    return await _load(db, listing)



@router.post("/listings", response_model=ProductOut, status_code=201)
async def create_listing(
    body: ListingCreateIn,
    user: Principal = Depends(require_role("seller", "admin")),
    db: AsyncSession = Depends(get_session),
) -> ProductOut:
    listing = Listing(
        owner_id=user.id, name=body.name, slug=await _unique_slug(db, body.name),
        tagline=body.tagline, category=body.category,
        price_cents=int(body.price * 100), status="draft",
    )
    db.add(listing)
    await db.commit()
    await db.refresh(listing)
    await bus.publish("listing.created", {"listing_id": listing.id}, actor=f"user:{user.id}")
    return await _load(db, listing)


@router.post("/listings/{listing_id}/intake", dependencies=[Depends(ai_rate_limit)])
async def trigger_intake(
    listing_id: str, body: IntakeIn,
    user: Principal = Depends(require_role("seller", "admin")),
    db: AsyncSession = Depends(get_session),
) -> dict:
    listing = await db.get(Listing, listing_id)
    if not listing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Listing not found")
    if listing.owner_id != user.id and user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Forbidden")
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
        listing.slug = await _unique_slug(db, patch["name"], exclude_id=listing.id)
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
    if "demo_url" in patch:
        listing.demo_url = patch["demo_url"]
    if "demoUrl" in patch:
        listing.demo_url = patch["demoUrl"]
        
    await db.commit()
    await db.refresh(listing)
    
    await bus.publish("listing.updated", {"listing_id": listing.id}, actor=f"user:{user.id}")
    return await _load(db, listing)


@router.post("/listings/{listing_id}/submit", dependencies=[Depends(ai_rate_limit)])
async def submit_listing(listing_id: str,
                         user: Principal = Depends(require_role("seller", "admin")),
                         db: AsyncSession = Depends(get_session)) -> dict:
    listing = await db.get(Listing, listing_id)
    if not listing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Listing not found")
    if listing.owner_id != user.id and user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Forbidden")
    listing.status = "review"
    db.add(listing)
    await db.commit()
    # Run the Verification gate now (not on create) — see workers._on_listing_submitted.
    await bus.publish("listing.submitted", {"listing_id": listing.id}, actor=f"user:{user.id}")
    return {"id": listing.id, "status": listing.status}


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
@router.get("/feature-requests/{id}")
async def get_feature_request(id: str,
                              user: Principal = Depends(current_user),
                              db: AsyncSession = Depends(get_session)) -> dict:
    req = await db.get(FeatureRequest, id)
    if not req:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Feature request not found")
    if req.buyer_id != user.id:
        listing = await db.get(Listing, req.listing_id)
        if not listing or (listing.owner_id != user.id and user.role != "admin"):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Forbidden")
            
    return {
        "id": req.id,
        "buyer_id": req.buyer_id,
        "listing_id": req.listing_id,
        "description": req.description,
        "estimated_charge_cents": req.estimated_charge_cents,
        "developer_charge_cents": req.developer_charge_cents,
        "developer_approved": req.developer_approved,
        "status": req.status,
    }


@router.post("/feature-requests", dependencies=[Depends(ai_rate_limit)])
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
    await db.flush()

    # Find or create chat thread
    stmt = select(Chat).where(
        Chat.buyer_id == user.id,
        Chat.seller_id == listing.owner_id,
        Chat.listing_id == listing_id
    )
    chat = (await db.execute(stmt)).scalars().first()
    if not chat:
        chat = Chat(
            buyer_id=user.id,
            seller_id=listing.owner_id,
            listing_id=listing_id,
            is_agent=False,
            status="open",
            unread_for=["seller"]
        )
        db.add(chat)
        await db.flush()
    else:
        chat.status = "open"
        unread = list(chat.unread_for or [])
        if "seller" not in unread:
            unread.append("seller")
        chat.unread_for = unread
        db.add(chat)

    buyer_user = await db.get(User, user.id)
    msg_text = (
        f"⚙️ **New Custom Feature Request Submitted**\n"
        f"Description: {description}\n"
        f"AI Cost Estimate: ${charge_cents / 100:.2f}\n"
        f"<!-- feature_request_id: {req.id} -->"
    )
    msg = ChatMessage(
        chat_id=chat.id,
        sender_id=user.id,
        sender_name=buyer_user.display_name if buyer_user else "Buyer",
        text=msg_text,
        is_agent_rep=False
    )
    db.add(msg)
    
    await db.commit()
    await db.refresh(req)
    
    await bus.publish("chat.message_sent", {"chat_id": chat.id, "sender_id": user.id})
    
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
    
    # Notify via chat
    stmt = select(Chat).where(
        Chat.buyer_id == req.buyer_id,
        Chat.listing_id == req.listing_id
    )
    chat = (await db.execute(stmt)).scalars().first()
    if chat:
        chat.status = "open"
        unread = list(chat.unread_for or [])
        if "buyer" not in unread:
            unread.append("buyer")
        chat.unread_for = unread
        db.add(chat)
        
        seller_user = await db.get(User, user.id)
        msg_text = (
            f"⚙️ **Developer Submitted Quote**\n"
            f"Developer Quote: ${dev_charge:.2f}\n"
            f"<!-- feature_request_id: {req.id} -->"
        )
        msg = ChatMessage(
            chat_id=chat.id,
            sender_id=user.id,
            sender_name=seller_user.display_name if seller_user else "Seller",
            text=msg_text,
            is_agent_rep=False
        )
        db.add(msg)
        
    await db.commit()
    await db.refresh(req)
    
    if chat:
        await bus.publish("chat.message_sent", {"chat_id": chat.id, "sender_id": user.id})
        
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
    
    # Notify via chat
    stmt = select(Chat).where(
        Chat.buyer_id == req.buyer_id,
        Chat.listing_id == req.listing_id
    )
    chat = (await db.execute(stmt)).scalars().first()
    if chat:
        chat.status = "open"
        unread = list(chat.unread_for or [])
        if "seller" not in unread:
            unread.append("seller")
        chat.unread_for = unread
        db.add(chat)
        
        buyer_user = await db.get(User, user.id)
        msg_text = (
            f"⚙️ **Custom Feature Request Approved**\n"
            f"Quote of ${req.developer_charge_cents / 100:.2f} approved.\n"
            f"<!-- feature_request_id: {req.id} -->"
        )
        msg = ChatMessage(
            chat_id=chat.id,
            sender_id=user.id,
            sender_name=buyer_user.display_name if buyer_user else "Buyer",
            text=msg_text,
            is_agent_rep=False
        )
        db.add(msg)
        
    await db.commit()
    await db.refresh(req)
    
    if chat:
        await bus.publish("chat.message_sent", {"chat_id": chat.id, "sender_id": user.id})
        
    return {
        "id": req.id,
        "status": req.status,
    }


@router.post("/analytics/event", status_code=201)
async def create_analytics_event(
    body: AnalyticsEventIn,
    db: AsyncSession = Depends(get_session),
    user: Principal | None = Depends(optional_user),
):
    listing_id = body.listing_id
    if not listing_id and body.slug:
        listing = (await db.execute(select(Listing).where(Listing.slug == body.slug))).scalar_one_or_none()
        if listing:
            listing_id = listing.id

    event = AnalyticEvent(
        listing_id=listing_id,
        event_type=body.event_type,
        actor_id=user.id if user else None
    )
    db.add(event)
    await db.commit()
    return {"ok": True}


@router.get("/seller/analytics", response_model=SellerAnalyticsOut)
async def get_seller_analytics(
    db: AsyncSession = Depends(get_session),
    user: Principal = Depends(require_role("seller", "admin")),
) -> dict:
    listings = (await db.execute(select(Listing).where(Listing.owner_id == user.id))).scalars().all()
    listing_ids = [l.id for l in listings]

    today = datetime.now(timezone.utc).date()
    if not listing_ids:
        history = []
        for i in range(14):
            d_date = today - timedelta(days=13 - i)
            history.append({"d": d_date.strftime("%b %d"), "views": 0, "launches": 0})
        return {
            "views_14d": 0,
            "launches_14d": 0,
            "conversion_rate": 0.0,
            "earnings_all_time": 0.0,
            "history": history
        }

    cutoff = datetime.now(timezone.utc) - timedelta(days=14)
    events = (await db.execute(
        select(AnalyticEvent)
        .where(AnalyticEvent.listing_id.in_(listing_ids))
        .where(AnalyticEvent.created_at >= cutoff)
    )).scalars().all()

    views_by_date = {}
    launches_by_date = {}
    for i in range(14):
        d_date = today - timedelta(days=13 - i)
        views_by_date[d_date] = 0
        launches_by_date[d_date] = 0

    for event in events:
        e_date = event.created_at.date()
        if e_date in views_by_date:
            if event.event_type == "view":
                views_by_date[e_date] += 1
            elif event.event_type == "launch":
                launches_by_date[e_date] += 1

    history = []
    for i in range(14):
        d_date = today - timedelta(days=13 - i)
        history.append({
            "d": d_date.strftime("%b %d"),
            "views": views_by_date[d_date],
            "launches": launches_by_date[d_date]
        })

    views_14d = sum(views_by_date.values())
    launches_14d = sum(launches_by_date.values())
    conversion_rate = (launches_14d / views_14d * 100) if views_14d > 0 else 0.0

    orders = (await db.execute(
        select(Order)
        .where(Order.seller_id == user.id)
        .where(Order.status.in_(["paid", "delivered"]))
    )).scalars().all()
    earnings_all_time = sum(o.amount_cents - o.commission_cents for o in orders) / 100.0

    return {
        "views_14d": views_14d,
        "launches_14d": launches_14d,
        "conversion_rate": round(conversion_rate, 2),
        "earnings_all_time": earnings_all_time,
        "history": history
    }


@router.get("/admin/analytics", response_model=AdminAnalyticsOut)
async def get_admin_analytics(
    db: AsyncSession = Depends(get_session),
    user: Principal = Depends(require_role("admin")),
) -> dict:
    cutoff = datetime.now(timezone.utc) - timedelta(days=14)
    events = (await db.execute(
        select(AnalyticEvent)
        .where(AnalyticEvent.created_at >= cutoff)
    )).scalars().all()

    today = datetime.now(timezone.utc).date()
    views_by_date = {}
    launches_by_date = {}
    for i in range(14):
        d_date = today - timedelta(days=13 - i)
        views_by_date[d_date] = 0
        launches_by_date[d_date] = 0

    for event in events:
        e_date = event.created_at.date()
        if e_date in views_by_date:
            if event.event_type == "view":
                views_by_date[e_date] += 1
            elif event.event_type == "launch":
                launches_by_date[e_date] += 1

    history = []
    for i in range(14):
        d_date = today - timedelta(days=13 - i)
        history.append({
            "d": d_date.strftime("%b %d"),
            "views": views_by_date[d_date],
            "launches": launches_by_date[d_date]
        })

    views_14d = sum(views_by_date.values())
    launches_14d = sum(launches_by_date.values())

    return {
        "views_14d": views_14d,
        "launches_14d": launches_14d,
        "history": history
    }


@router.get("/public-config")
async def public_config(db: AsyncSession = Depends(get_session)) -> dict:
    from backend.shared.form_schema import FORM_SCHEMA
    
    rows = {r.key: r.value for r in (await db.execute(select(AdminConfig))).scalars()}
    
    categories = rows.get("categories") or ['Dashboards','Analytics','E-commerce','AI','Finance','CRM','CMS','Productivity','Auth','Enterprise','Healthcare']
    frameworks = rows.get("frameworks") or ['Next.js', 'React', 'Vue', 'Svelte', 'Remix', 'Astro', 'Go']
    sections = rows.get("sections") or ["Planning", "Design", "Development", "Architecture", "Data", "Testing", "Security", "Deployment"]
    forms = rows.get("forms") or FORM_SCHEMA
    
    return {
        "categories": categories,
        "frameworks": frameworks,
        "sections": sections,
        "forms": forms
    }


@router.post("/listings/{listing_id}/repost", response_model=ProductOut, dependencies=[Depends(ai_rate_limit)])
async def repost_listing(
    listing_id: str,
    user: Principal = Depends(require_role("seller", "admin")),
    db: AsyncSession = Depends(get_session)
) -> ProductOut:
    listing = await db.get(Listing, listing_id)
    if not listing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Listing not found")
    if listing.owner_id != user.id and user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Forbidden")
        
    from backend.ai.agents import pricing
    agent_res = await pricing.run(listing_id)
    if not agent_res or "error" in agent_res:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "AI agent failed to generate pitch")
        
    listing.tagline = agent_res.get("tagline", listing.tagline)
    listing.description = agent_res.get("long_description") or agent_res.get("short_description") or listing.description
    
    suggested_tiers = agent_res.get("suggested_tiers", [])
    if suggested_tiers:
        await db.execute(delete(ListingTier).where(ListingTier.listing_id == listing_id))
        for t in suggested_tiers:
            new_tier = ListingTier(
                listing_id=listing_id,
                name=t["name"],
                price_cents=int(t["price"] * 100),
                features=t.get("features", []),
                recommended=t.get("recommended", False)
            )
            db.add(new_tier)
            
    listing.status = "live"
    listing.expires_at = datetime.now(timezone.utc) + timedelta(days=30)
    db.add(listing)
    await db.commit()
    await db.refresh(listing)
    
    await bus.publish("listing.updated", {"listing_id": listing.id}, actor=f"user:{user.id}")
    return await _load(db, listing)


app = FastAPI(title="Vitrine catalog")
app.include_router(router)



@app.get("/health")
async def health() -> dict:
    return {"ok": True, "service": "catalog"}

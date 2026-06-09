"""
Orders service — checkout, deliver, payouts, subscriptions, ledger.

Working slice: mock checkout that creates a paid order, computes the platform
commission from the seller's plan, and emits `order.paid` (Notifications then
prompts the seller to deliver). Other endpoints are stubbed for Phase 3.
"""
from __future__ import annotations

import time

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.shared.db import get_session
from backend.shared.events import bus
from backend.shared.models import Listing, ListingTier, Order, User, Payout, Subscription, Delivery
from backend.shared.schemas.commerce import CheckoutIn, OrderOut, DeliverIn, PayoutRequestIn, SubscribeIn
from backend.shared.security import Principal, current_user, require_role

from .providers import get_provider

router = APIRouter(tags=["orders"])

# Default commission % by plan (runtime override lives in admin_configs.fees).
COMMISSION_PCT = {"free": 12, "studio": 8, "atelier": 5, "maison": 3}
STUDENT_FREE_PCT = 7.5  # non-subscribed students


def _commission_cents(amount_cents: int, plan: str, is_student: bool) -> int:
    pct = COMMISSION_PCT.get(plan, 12)
    if plan == "free" and is_student:
        pct = STUDENT_FREE_PCT
    return round(amount_cents * pct / 100)


def _order_out(o: Order, listing: Listing, buyer: User, seller: User, delivery: Delivery | None = None) -> OrderOut:
    return OrderOut(
        id=o.id, productId=o.listing_id, productName=listing.name,
        buyerId=o.buyer_id, buyerName=buyer.display_name or buyer.email,
        sellerId=o.seller_id, sellerName=seller.display_name or seller.email,
        tier=o.tier_name, amount=o.amount_cents / 100, commission=o.commission_cents / 100,
        status=o.status, ts=int(o.created_at.timestamp() * 1000),
        delivered=bool(delivery) if delivery else (o.status == "delivered"),
        licenseKey=delivery.license_key if delivery else None,
    )


@router.post("/checkout", response_model=OrderOut)
async def checkout(body: CheckoutIn, user: Principal = Depends(current_user),
                   db: AsyncSession = Depends(get_session)) -> OrderOut:
    listing = await db.get(Listing, body.listing_id)
    if not listing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Listing not found")
    if listing.owner_id == user.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot purchase your own listing")
    seller = await db.get(User, listing.owner_id)
    buyer = await db.get(User, user.id)

    tiers = (await db.execute(
        select(ListingTier).where(ListingTier.listing_id == listing.id))).scalars().all()
    if tiers and 0 <= body.tier_index < len(tiers):
        tier = tiers[body.tier_index]
        amount_cents, tier_name, tier_id = tier.price_cents, tier.name, tier.id
    else:
        amount_cents, tier_name, tier_id = listing.price_cents, "Source", None

    provider = get_provider()
    session = await provider.create_checkout(order_id="pending", amount_cents=amount_cents)

    order = Order(
        buyer_id=buyer.id, listing_id=listing.id, seller_id=seller.id,
        tier_id=tier_id, tier_name=tier_name, amount_cents=amount_cents,
        commission_cents=_commission_cents(amount_cents, seller.plan, seller.is_student),
        kind=body.kind, status=session.status, provider=provider.__class__.__name__,
        provider_ref=session.provider_ref,
    )
    db.add(order)
    await db.commit()
    await db.refresh(order)

    if order.status == "paid":
        await bus.publish("order.paid", {"order_id": order.id, "seller_id": seller.id,
                                         "listing_id": listing.id}, actor=f"user:{buyer.id}")
    delivery = (await db.execute(select(Delivery).where(Delivery.order_id == order.id))).scalar_one_or_none()
    return _order_out(order, listing, buyer, seller, delivery)


@router.post("/webhooks/payments")
async def payments_webhook(request: Request, db: AsyncSession = Depends(get_session)) -> dict:
    provider = get_provider()
    event = await provider.verify_webhook(dict(request.headers), await request.body())
    
    order = (await db.execute(
        select(Order).where(Order.provider_ref == event.provider_ref)
    )).scalar_one_or_none()
    
    if order and order.status != event.status:
        order.status = event.status
        await db.commit()
        
        if event.status == "paid":
            await bus.publish(
                "order.paid",
                {"order_id": order.id, "seller_id": order.seller_id, "listing_id": order.listing_id},
                actor=f"user:{order.buyer_id}"
            )
            
    return {"received": True, "status": event.status}


@router.post("/orders/{order_id}/deliver")
async def deliver(order_id: str, body: DeliverIn | None = None,
                  user: Principal = Depends(require_role("seller", "admin")),
                  db: AsyncSession = Depends(get_session)) -> dict:
    import uuid
    from datetime import datetime, timezone
    
    o = await db.get(Order, order_id)
    if not o or (o.seller_id != user.id and user.role != "admin"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Order not found")
        
    o.status = "delivered"
    
    delivery = (await db.execute(
        select(Delivery).where(Delivery.order_id == o.id)
    )).scalar_one_or_none()
    
    artifact_url = (body.artifact_url if body else None) or "https://vitrine.io/downloads/stub"
    license_key = f"LIC-{uuid.uuid4().hex[:8].upper()}"
    
    if not delivery:
        delivery = Delivery(
            order_id=o.id,
            artifact_url=artifact_url,
            license_key=license_key,
            delivered_at=datetime.now(timezone.utc)
        )
        db.add(delivery)
    else:
        delivery.artifact_url = artifact_url
        delivery.license_key = license_key
        delivery.delivered_at = datetime.now(timezone.utc)
        
    await db.commit()
    return {"status": "delivered", "order_id": order_id}


@router.get("/orders", response_model=list[OrderOut])
async def list_orders(user: Principal = Depends(current_user),
                      db: AsyncSession = Depends(get_session)) -> list[OrderOut]:
    stmt = select(Order)
    if user.role != "admin":
        stmt = stmt.where((Order.buyer_id == user.id) | (Order.seller_id == user.id))
    stmt = stmt.order_by(Order.created_at.desc())
    rows = (await db.execute(stmt)).scalars().all()
    
    out = []
    for o in rows:
        listing = await db.get(Listing, o.listing_id)
        buyer = await db.get(User, o.buyer_id)
        seller = await db.get(User, o.seller_id)
        delivery = (await db.execute(select(Delivery).where(Delivery.order_id == o.id))).scalar_one_or_none()
        if listing and buyer and seller:
            out.append(_order_out(o, listing, buyer, seller, delivery))
    return out


@router.get("/orders/{order_id}", response_model=OrderOut)
async def get_order(order_id: str, user: Principal = Depends(current_user),
                     db: AsyncSession = Depends(get_session)) -> OrderOut:
    o = await db.get(Order, order_id)
    if not o or (user.id not in (o.buyer_id, o.seller_id) and user.role != "admin"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Order not found")
    delivery = (await db.execute(select(Delivery).where(Delivery.order_id == o.id))).scalar_one_or_none()
    return _order_out(o, await db.get(Listing, o.listing_id),
                      await db.get(User, o.buyer_id), await db.get(User, o.seller_id), delivery)


@router.get("/transactions/ledger")
async def ledger(user: Principal = Depends(require_role("admin")),
                 db: AsyncSession = Depends(get_session)) -> list[dict]:
    stmt = select(Order).order_by(Order.created_at.desc())
    rows = (await db.execute(stmt)).scalars().all()
    out = []
    for o in rows:
        listing = await db.get(Listing, o.listing_id)
        buyer = await db.get(User, o.buyer_id)
        seller = await db.get(User, o.seller_id)
        out.append({
            "id": o.id,
            "productName": listing.name if listing else "Unknown",
            "buyerName": buyer.display_name if buyer else "Unknown",
            "sellerName": seller.display_name if seller else "Unknown",
            "tier": o.tier_name,
            "amount": o.amount_cents / 100,
            "commission": o.commission_cents / 100,
            "status": o.status,
            "ts": int(o.created_at.timestamp() * 1000),
        })
    return out


@router.get("/payouts")
async def list_payouts(user: Principal = Depends(require_role("seller", "admin")),
                       db: AsyncSession = Depends(get_session)) -> list[dict]:
    stmt = select(Payout)
    if user.role != "admin":
        stmt = stmt.where(Payout.seller_id == user.id)
    stmt = stmt.order_by(Payout.created_at.desc())
    rows = (await db.execute(stmt)).scalars().all()
    return [{
        "id": p.id,
        "amount": p.amount_cents / 100,
        "status": p.status,
        "payout_method": p.payout_method,
        "ts": int(p.created_at.timestamp() * 1000)
    } for p in rows]


@router.post("/payouts/request")
async def request_payout(body: PayoutRequestIn,
                         user: Principal = Depends(require_role("seller", "admin")),
                         db: AsyncSession = Depends(get_session)) -> dict:
    orders_stmt = select(Order).where(Order.seller_id == user.id, Order.status == "delivered")
    paid_orders = (await db.execute(orders_stmt)).scalars().all()
    earned_cents = sum(o.amount_cents - o.commission_cents for o in paid_orders)
    
    payouts_stmt = select(Payout).where(Payout.seller_id == user.id, Payout.status.in_(["pending", "processed"]))
    payouts = (await db.execute(payouts_stmt)).scalars().all()
    payouts_cents = sum(p.amount_cents for p in payouts)
    
    available_cents = earned_cents - payouts_cents
    requested_cents = int(body.amount * 100)
    
    if requested_cents <= 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Amount must be greater than zero")
        
    if requested_cents > available_cents:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Insufficient balance. Available: {available_cents / 100}")
        
    p = Payout(
        seller_id=user.id,
        amount_cents=requested_cents,
        status="pending",
        payout_method=body.payout_method,
        payout_details=body.details
    )
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return {"id": p.id, "status": p.status, "amount": body.amount}


@router.post("/subscriptions/subscribe")
async def subscribe(body: SubscribeIn,
                    user: Principal = Depends(require_role("seller", "admin")),
                    db: AsyncSession = Depends(get_session)) -> dict:
    u = await db.get(User, user.id)
    if not u:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
        
    u.plan = body.tier
    
    sub = Subscription(
        seller_id=user.id,
        tier=body.tier,
        price_cents=0,
        active=True
    )
    db.add(sub)
    await db.commit()
    return {"status": "subscribed", "tier": body.tier}


@router.get("/subscriptions/status")
async def subscription_status(user: Principal = Depends(current_user),
                              db: AsyncSession = Depends(get_session)) -> dict:
    u = await db.get(User, user.id)
    if not u:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return {"tier": u.plan, "active": True}


app = FastAPI(title="Vitrine orders")
app.include_router(router)


@app.get("/health")
async def health() -> dict:
    return {"ok": True, "service": "orders"}

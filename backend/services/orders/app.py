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
from backend.shared.models import Listing, ListingTier, Order, User
from backend.shared.schemas.commerce import CheckoutIn, OrderOut
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


def _order_out(o: Order, listing: Listing, buyer: User, seller: User) -> OrderOut:
    return OrderOut(
        id=o.id, productId=o.listing_id, productName=listing.name,
        buyerId=o.buyer_id, buyerName=buyer.display_name or buyer.email,
        sellerId=o.seller_id, sellerName=seller.display_name or seller.email,
        tier=o.tier_name, amount=o.amount_cents / 100, commission=o.commission_cents / 100,
        status=o.status, ts=int(o.created_at.timestamp() * 1000),
    )


@router.post("/checkout", response_model=OrderOut)
async def checkout(body: CheckoutIn, user: Principal = Depends(current_user),
                   db: AsyncSession = Depends(get_session)) -> OrderOut:
    listing = await db.get(Listing, body.listing_id)
    if not listing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Listing not found")
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
    return _order_out(order, listing, buyer, seller)


@router.post("/webhooks/payments")
async def payments_webhook(request: Request) -> dict:
    provider = get_provider()
    event = await provider.verify_webhook(dict(request.headers), await request.body())
    # TODO Phase 3: look up order by provider_ref, update status idempotently, emit event.
    return {"received": True, "status": event.status}


@router.post("/orders/{order_id}/deliver")
async def deliver(order_id: str, user: Principal = Depends(require_role("seller", "admin"))) -> dict:
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "deliver — TODO Phase 3")


@router.get("/orders/{order_id}", response_model=OrderOut)
async def get_order(order_id: str, user: Principal = Depends(current_user),
                    db: AsyncSession = Depends(get_session)) -> OrderOut:
    o = await db.get(Order, order_id)
    if not o or (user.id not in (o.buyer_id, o.seller_id) and user.role != "admin"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Order not found")
    return _order_out(o, await db.get(Listing, o.listing_id),
                      await db.get(User, o.buyer_id), await db.get(User, o.seller_id))


@router.get("/transactions/ledger")
async def ledger(user: Principal = Depends(require_role("admin"))) -> list[dict]:
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "ledger — TODO Phase 3")


@router.get("/payouts")
async def list_payouts(user: Principal = Depends(require_role("seller", "admin"))) -> list[dict]:
    return []  # TODO Phase 3


@router.post("/payouts/request")
async def request_payout(user: Principal = Depends(require_role("seller", "admin"))) -> dict:
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "request_payout — TODO Phase 3")


@router.post("/subscriptions/subscribe")
async def subscribe(user: Principal = Depends(require_role("seller", "admin"))) -> dict:
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "subscribe — TODO Phase 3")


@router.get("/subscriptions/status")
async def subscription_status(user: Principal = Depends(current_user)) -> dict:
    return {"tier": "free", "active": True}  # TODO Phase 3


app = FastAPI(title="Vitrine orders")
app.include_router(router)


@app.get("/health")
async def health() -> dict:
    return {"ok": True, "service": "orders"}

"""
Notifications service — in-app feed + (later) email/webhooks.

Demonstrates event consumption: on `order.paid` it creates a "deliver the full
app" notification for the seller. Same pattern for listing.flagged / review.created
/ chat.message_sent. Email + seller webhooks are Phase 3.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.shared.db import SessionLocal, get_session
from backend.shared.events import bus
from backend.shared.models import Notification, Listing, Chat
from backend.shared.security import Principal, current_user

router = APIRouter(tags=["notifications"])


@router.get("/notifications")
async def feed(user: Principal = Depends(current_user),
               db: AsyncSession = Depends(get_session)) -> list[dict]:
    rows = (await db.execute(
        select(Notification).where(Notification.user_id == user.id)
        .order_by(Notification.created_at.desc()).limit(50))).scalars().all()
    return [{"id": n.id, "kind": n.kind, "title": n.title, "body": n.body,
             "read": n.read, "ts": int(n.created_at.timestamp() * 1000)} for n in rows]


# ── event handlers ──────────────────────────────────────────────────────
async def _on_order_paid(event: dict) -> None:
    p = event["payload"]
    async with SessionLocal() as db:
        db.add(Notification(
            user_id=p["seller_id"], kind="order.paid",
            title="You made a sale — deliver the full app",
            body="A buyer paid. Upload the full/upgraded build to fulfil the order.",
            meta={"order_id": p.get("order_id"), "listing_id": p.get("listing_id")},
        ))
        await db.commit()


async def _on_listing_flagged(event: dict) -> None:
    p = event["payload"]
    async with SessionLocal() as db:
        listing = await db.get(Listing, p["listing_id"])
        if listing:
            db.add(Notification(
                user_id=listing.owner_id, kind="listing.flagged",
                title="Your listing has been flagged",
                body=f"Your listing '{listing.name}' has been flagged: {p.get('reason', 'no reason provided')}",
                meta={"listing_id": listing.id, "reason": p.get("reason")},
            ))
            await db.commit()


async def _on_review_created(event: dict) -> None:
    p = event["payload"]
    async with SessionLocal() as db:
        listing = await db.get(Listing, p["listing_id"])
        if listing:
            db.add(Notification(
                user_id=listing.owner_id, kind="review.created",
                title="New review received",
                body=f"Your listing '{listing.name}' has received a new review.",
                meta={"listing_id": listing.id},
            ))
            await db.commit()


async def _on_chat_message_sent(event: dict) -> None:
    p = event["payload"]
    chat_id = p["chat_id"]
    sender_id = p["sender_id"]
    async with SessionLocal() as db:
        chat = await db.get(Chat, chat_id)
        if chat:
            # Send notification to the other party
            recipient_id = chat.seller_id if (sender_id == chat.buyer_id or sender_id == "agent") else chat.buyer_id
            db.add(Notification(
                user_id=recipient_id, kind="chat.message_sent",
                title="New message received",
                body="You have a new message in your chat thread.",
                meta={"chat_id": chat_id},
            ))
            await db.commit()


bus.subscribe("order.paid", _on_order_paid)
bus.subscribe("listing.flagged", _on_listing_flagged)
bus.subscribe("review.created", _on_review_created)
bus.subscribe("chat.message_sent", _on_chat_message_sent)


app = FastAPI(title="Vitrine notifications")
app.include_router(router)


@app.get("/health")
async def health() -> dict:
    return {"ok": True, "service": "notifications"}

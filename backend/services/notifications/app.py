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
from backend.shared.models import Notification
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


bus.subscribe("order.paid", _on_order_paid)
# TODO: subscribe("listing.flagged"), subscribe("review.created"), subscribe("chat.message_sent")


app = FastAPI(title="Vitrine notifications")
app.include_router(router)


@app.get("/health")
async def health() -> dict:
    return {"ok": True, "service": "notifications"}

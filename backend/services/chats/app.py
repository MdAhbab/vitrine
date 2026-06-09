"""
Chats service — direct messaging + AI-rep negotiation threads.

Backs the frontend Inbox + BargainModal (store.ts threads/messages). The actual
agent reply text comes from the AI orchestrator (`POST /ai/negotiate`); this
service owns the chat/message/negotiation rows and the "max 2 active reps" rule.

NOTE: the frontend calls a chat a "thread" (threadId). The serializer maps
chat.id -> threadId.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.shared.db import get_session
from backend.shared.events import bus
from backend.shared.models import Chat, ChatMessage, Listing, Negotiation, User
from backend.shared.schemas.chat import (
    MessageOut,
    SendMessageIn,
    StartNegotiationIn,
    ThreadOut,
)
from backend.shared.settings import settings
from backend.shared.security import Principal, current_user

router = APIRouter(tags=["chats"])


async def _thread_out(db: AsyncSession, c: Chat) -> ThreadOut:
    listing = await db.get(Listing, c.listing_id)
    buyer = await db.get(User, c.buyer_id)
    seller = await db.get(User, c.seller_id)
    return ThreadOut(
        id=c.id, productId=c.listing_id,
        productName=listing.name if listing else "",
        productCover=(listing.cover or "") if listing else "",
        buyerId=c.buyer_id, buyerName=buyer.display_name if buyer else "",
        sellerId=c.seller_id, sellerName=seller.display_name if seller else "",
        isAgent=c.is_agent,
        agentBudget=(c.agent_budget_cents / 100) if c.agent_budget_cents else None,
        status=c.status, unreadFor=c.unread_for or [],
        createdAt=int(c.created_at.timestamp() * 1000),
    )


@router.get("/chats", response_model=list[ThreadOut])
async def list_chats(user: Principal = Depends(current_user),
                     db: AsyncSession = Depends(get_session)) -> list[ThreadOut]:
    if user.role == "admin":
        stmt = select(Chat)
    else:
        stmt = select(Chat).where((Chat.buyer_id == user.id) | (Chat.seller_id == user.id))
    rows = (await db.execute(stmt.order_by(Chat.created_at.desc()))).scalars().all()
    return [await _thread_out(db, c) for c in rows]


@router.get("/chats/{chat_id}/messages", response_model=list[MessageOut])
async def messages(chat_id: str, db: AsyncSession = Depends(get_session)) -> list[MessageOut]:
    rows = (await db.execute(
        select(ChatMessage).where(ChatMessage.chat_id == chat_id)
        .order_by(ChatMessage.created_at))).scalars().all()
    return [MessageOut(id=m.id, threadId=m.chat_id, authorId=m.sender_id,
                       authorName=m.sender_name, isAgent=m.is_agent_rep, body=m.text,
                       ts=int(m.created_at.timestamp() * 1000)) for m in rows]


@router.post("/chats/{chat_id}/messages", response_model=MessageOut)
async def send_message(chat_id: str, body: SendMessageIn,
                       user: Principal = Depends(current_user),
                       db: AsyncSession = Depends(get_session)) -> MessageOut:
    chat = await db.get(Chat, chat_id)
    if not chat:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Chat not found")
    sender = await db.get(User, user.id)
    msg = ChatMessage(chat_id=chat_id, sender_id=user.id,
                      sender_name=sender.display_name if sender else "",
                      text=body.body, is_agent_rep=body.as_agent)
    chat.unread_for = ["seller"] if user.id == chat.buyer_id else ["buyer"]
    db.add(msg)
    await db.commit()
    await db.refresh(msg)
    await bus.publish("chat.message_sent", {"chat_id": chat_id, "sender_id": user.id})
    return MessageOut(id=msg.id, threadId=chat_id, authorId=user.id,
                      authorName=msg.sender_name, isAgent=msg.is_agent_rep,
                      body=msg.text, ts=int(msg.created_at.timestamp() * 1000))


@router.post("/chats/negotiate/start", response_model=ThreadOut)
async def start_negotiation(body: StartNegotiationIn,
                            user: Principal = Depends(current_user),
                            db: AsyncSession = Depends(get_session)) -> ThreadOut:
    if user.role != "buyer":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only buyers can dispatch a rep")
    # Enforce "max N active AI reps per buyer" (settings.MAX_ACTIVE_REPS_PER_BUYER).
    active = (await db.execute(
        select(func.count()).select_from(Chat)
        .where(Chat.buyer_id == user.id, Chat.is_agent.is_(True), Chat.status == "open")
    )).scalar_one()
    if active >= settings.MAX_ACTIVE_REPS_PER_BUYER:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            f"Max {settings.MAX_ACTIVE_REPS_PER_BUYER} active reps reached")

    listing = await db.get(Listing, body.listing_id)
    if not listing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Listing not found")
    chat = Chat(buyer_id=user.id, seller_id=listing.owner_id, listing_id=listing.id,
                is_agent=True, agent_budget_cents=int(body.budget * 100),
                status="open", unread_for=["seller"])
    db.add(chat)
    await db.flush()
    db.add(Negotiation(chat_id=chat.id, buyer_id=user.id, status="active",
                       budget_cents=int(body.budget * 100),
                       buyer_readme_context=body.readme_context))
    await db.commit()
    await db.refresh(chat)
    # The AI rep's opening message is produced by POST /ai/negotiate {chat_id}.
    return await _thread_out(db, chat)


app = FastAPI(title="Vitrine chats")
app.include_router(router)


@app.get("/health")
async def health() -> dict:
    return {"ok": True, "service": "chats"}

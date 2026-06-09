"""
Chats service — direct messaging + AI-rep negotiation threads.

Backs the frontend Inbox + BargainModal (store.ts threads/messages). The actual
agent reply text comes from the AI orchestrator (`negotiator.next_message`);
this service owns the chat/message/negotiation rows and the "max 2 active reps" rule.

NOTE: the frontend calls a chat a "thread" (threadId). The serializer maps
chat.id -> threadId.
"""
from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Depends, FastAPI, HTTPException, status, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.shared.db import get_session
from backend.shared.events import bus
from backend.shared.models import Chat, ChatMessage, Listing, Negotiation, User
from backend.shared.schemas.chat import (
    AttachmentOut,
    MessageOut,
    SendMessageIn,
    StartNegotiationIn,
    ThreadOut,
)
from backend.shared.settings import settings
from backend.shared.security import Principal, current_user, ai_rate_limit

router = APIRouter(tags=["chats"])
log = logging.getLogger(__name__)


def _can_access_chat(chat: Chat, user: Principal) -> bool:
    if user.role == "admin":
        return True
    return user.id in (chat.buyer_id, chat.seller_id)


async def _require_chat(chat_id: str, user: Principal, db: AsyncSession) -> Chat:
    chat = await db.get(Chat, chat_id)
    if not chat:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Chat not found")
    if not _can_access_chat(chat, user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Forbidden")
    return chat


def _msg_out(m: ChatMessage) -> MessageOut:
    atts = [
        AttachmentOut(**a) for a in (m.attachments or [])
        if isinstance(a, dict) and a.get("url")
    ]
    return MessageOut(
        id=m.id, threadId=m.chat_id, authorId=m.sender_id,
        authorName=m.sender_name, isAgent=m.is_agent_rep, body=m.text,
        attachments=atts, ts=int(m.created_at.timestamp() * 1000),
    )


_active_agent_replies: set[str] = set()


async def _trigger_agent_reply(chat_id: str) -> None:
    if chat_id in _active_agent_replies:
        return
    _active_agent_replies.add(chat_id)
    try:
        from backend.ai.agents.negotiator import next_message
        await next_message(chat_id)
    except Exception:
        log.exception("AI rep failed for chat %s", chat_id)
    finally:
        _active_agent_replies.discard(chat_id)


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
async def messages(chat_id: str, user: Principal = Depends(current_user),
                   db: AsyncSession = Depends(get_session)) -> list[MessageOut]:
    await _require_chat(chat_id, user, db)
    rows = (await db.execute(
        select(ChatMessage).where(ChatMessage.chat_id == chat_id)
        .order_by(ChatMessage.created_at))).scalars().all()
    return [_msg_out(m) for m in rows]


@router.post("/chats/{chat_id}/messages", response_model=MessageOut)
async def send_message(chat_id: str, body: SendMessageIn,
                       request: Request,
                       user: Principal = Depends(current_user),
                       db: AsyncSession = Depends(get_session)) -> MessageOut:
    if not body.body.strip() and not body.attachments:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Message body or attachment required")
    chat = await _require_chat(chat_id, user, db)
    sender = await db.get(User, user.id)
    atts = [a.model_dump() for a in body.attachments]
    msg = ChatMessage(
        chat_id=chat_id, sender_id=user.id,
        sender_name=sender.display_name if sender else "",
        text=body.body, is_agent_rep=body.as_agent,
        attachments=atts,
    )
    chat.unread_for = ["seller"] if user.id == chat.buyer_id else ["buyer"]
    db.add(msg)
    await db.commit()
    await db.refresh(msg)
    await bus.publish("chat.message_sent", {"chat_id": chat_id, "sender_id": user.id})

    if chat.is_agent and user.id == chat.seller_id:
        await ai_rate_limit(request)
        asyncio.create_task(_trigger_agent_reply(chat_id))

    return _msg_out(msg)


@router.post("/chats/negotiate/start", response_model=ThreadOut, dependencies=[Depends(ai_rate_limit)])
async def start_negotiation(body: StartNegotiationIn,
                            user: Principal = Depends(current_user),
                            db: AsyncSession = Depends(get_session)) -> ThreadOut:
    if user.role != "buyer":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only buyers can dispatch a rep")
    if body.budget <= 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Budget must be greater than zero")
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
    asyncio.create_task(_trigger_agent_reply(chat.id))
    return await _thread_out(db, chat)


@router.post("/chats/{chat_id}/deactivate-rep", response_model=ThreadOut)
async def deactivate_rep(chat_id: str,
                         user: Principal = Depends(current_user),
                         db: AsyncSession = Depends(get_session)) -> ThreadOut:
    chat = await _require_chat(chat_id, user, db)
    if chat.buyer_id != user.id and user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the buyer can deactivate the AI rep")

    chat.is_agent = False

    nego = (await db.execute(
        select(Negotiation).where(Negotiation.chat_id == chat_id, Negotiation.status == "active")
    )).scalar_one_or_none()
    if nego:
        nego.status = "closed"

    await db.commit()
    await db.refresh(chat)
    return await _thread_out(db, chat)


app = FastAPI(title="Vitrine chats")
app.include_router(router)


@app.get("/health")
async def health() -> dict:
    return {"ok": True, "service": "chats"}

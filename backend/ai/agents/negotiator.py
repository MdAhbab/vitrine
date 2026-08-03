"""Buyer Negotiator (AI Rep) — bargains on the buyer's behalf within budget.

Powers the frontend BargainModal / agent threads. Warm but firm, never exceeds
the authorized budget, references the buyer's brief. See AGENTS.md (negotiator).
"""
from __future__ import annotations

import re

from sqlalchemy import select

from backend.shared.db import SessionLocal
from backend.shared.models import Chat, ChatMessage, Negotiation, User, Order, Listing

from .base import run_agent, system_prompt_for

SYSTEM = system_prompt_for("Buyer Representative Agent",
                           "You are the buyer's negotiating rep. Warm but firm. Never exceed budget.")


_PLACEHOLDER_RE = re.compile(r"\[(?:your|seller|buyer|product|company|recipient)[^\]]{0,30}\]", re.I)

# Context budget. Every one of these is resent on each reply, so an unbounded
# thread or order ledger turned a ~2k-token call into an ever-growing one.
_MAX_ORDERS = 8
_MAX_HISTORY_MSGS = 20
_MAX_MSG_CHARS = 600
_MAX_README_CHARS = 4000


def _clip(text: str | None, limit: int) -> str:
    text = (text or "").strip()
    return text if len(text) <= limit else text[:limit].rstrip() + " …[truncated]"


def _strip_placeholders(text: str, seller_name: str, rep_name: str) -> str:
    """Belt-and-braces for the prompt rule above.

    A model that still slips a "[Your Name]" through would otherwise post it into
    a thread the seller reads, so substitute the names we already know and drop
    the leftover mail-merge scaffolding.
    """
    if not text:
        return text
    out = re.sub(r"(?im)^\s*subject:.*$\n?", "", text)
    out = re.sub(r"\[(?:your name|my name|rep name)[^\]]{0,20}\]", rep_name, out, flags=re.I)
    out = re.sub(r"\[(?:seller'?s? name|recipient'?s? name)[^\]]{0,20}\]", seller_name, out, flags=re.I)
    out = _PLACEHOLDER_RE.sub("", out)
    return re.sub(r"\n{3,}", "\n\n", out).strip()


async def next_message(chat_id: str) -> dict:
    async with SessionLocal() as db:
        chat = await db.get(Chat, chat_id)
        if not chat or not chat.is_agent:
            return {"error": "not an agent chat"}
        nego = (await db.execute(
            select(Negotiation).where(Negotiation.chat_id == chat_id))).scalar_one_or_none()
        buyer = await db.get(User, chat.buyer_id)
        seller = await db.get(User, chat.seller_id)
        buyer_name = (buyer.display_name if buyer else "") or "the buyer"
        seller_name = (seller.display_name if seller else "") or "there"
        rep_name = f"{buyer_name}'s AI Rep"


        # Recent orders only. This is anchoring context for a discount argument,
        # not an audit trail — an unbounded dump made prompt cost grow with the
        # buyer's lifetime order count and eventually blew the context window.
        orders_stmt = (select(Order)
                       .where(Order.buyer_id == chat.buyer_id)
                       .order_by(Order.created_at.desc())
                       .limit(_MAX_ORDERS))
        orders = list((await db.execute(orders_stmt)).scalars().all())
        orders_summary = [
            f"Order: Product ID {o.listing_id}, Price ${o.amount_cents/100:.2f}, Status {o.status}"
            for o in orders
        ]
        orders_text = "\n".join(orders_summary) if orders_summary else "No previous orders."

        # Fetch listing details
        listing = await db.get(Listing, chat.listing_id)
        listing_details = ""
        if listing:
            listing_details = (
                f"Product: {listing.name}\n"
                f"Original Price: ${listing.price_cents/100:.2f}\n"
                f"Rating: {listing.rating} ({listing.reviews_count} reviews)\n"
                f"Category: {listing.category}\n"
                f"Tech Stack: {listing.tech_stack}\n"
            )
            
        # Most recent turns, re-ordered chronologically for the prompt. A long
        # negotiation would otherwise resend the entire thread on every reply.
        msgs_stmt = (select(ChatMessage)
                     .where(ChatMessage.chat_id == chat_id)
                     .order_by(ChatMessage.created_at.desc())
                     .limit(_MAX_HISTORY_MSGS))
        history_msgs = list((await db.execute(msgs_stmt)).scalars().all())[::-1]
        history_text = "\n".join(
            f"{m.sender_name}: {_clip(m.text, _MAX_MSG_CHARS)}" for m in history_msgs
        )

        budget = (chat.agent_budget_cents or 0) / 100
        # Buyer-supplied free text — clipped so a pasted repo can't dominate
        # (or blow) the context window.
        context = _clip(nego.buyer_readme_context if nego else "", _MAX_README_CHARS)
        
        prompt = (
            f"You are negotiating on behalf of the buyer {buyer_name}.\n"
            f"You are writing to the seller, {seller_name}. You sign as \"{rep_name}\".\n"
            f"Buyer constraints & target: Authorized Max Budget is ${budget}.\n"
            f"Product Context:\n{listing_details}\n"
            f"Buyer's Custom Product Context/Readme Brief:\n{context}\n"
            f"Buyer's Past Orders & History:\n{orders_text}\n"
            f"Conversation History:\n{history_text}\n\n"
            f"Draft the next negotiation message to the seller. Disclose clearly that you are the buyer's AI Representative. "
            f"Be warm but firm. Propose a specific price offer or custom milestone terms that are within the budget and align with the context. "
            f"Do not exceed the authorized budget of ${budget} under any circumstances.\n"
            # The model was shipping literal "Dear [Seller's Name]" / "My name is
            # [Your Name]" straight into seller-visible threads.
            f"Write the finished message only. Address the seller as {seller_name} and sign as {rep_name}. "
            f"NEVER emit bracketed placeholders such as [Your Name], [Seller's Name] or [Product] — "
            f"every name you need is given above. Do not include a subject line."
        )
        
        result = await run_agent("negotiator", SYSTEM, prompt, trigger="api")

        # A degraded run (budget cap hit, every provider down, no key) returns
        # internal diagnostic text — never a negotiation message. Posting it
        # would put scaffolding like "[Budget exceeded — heuristic-only mode]"
        # into a thread the seller reads. Fail loudly to the buyer instead, and
        # leave the thread untouched so the rep can retry cleanly.
        if result.stub:
            return {"chat_id": chat_id, "stub": True,
                    "error": "The AI representative is temporarily unavailable. "
                             "Please try again shortly."}

        text = _strip_placeholders(result.text, seller_name, rep_name)
        if not text.strip():
            return {"chat_id": chat_id, "stub": True,
                    "error": "The AI representative could not draft a message. "
                             "Please try again."}

        msg = ChatMessage(chat_id=chat_id, sender_id="agent",
                          sender_name=rep_name,
                          text=text,
                          is_agent_rep=True)
        chat.unread_for = ["seller"]
        db.add(msg)
        await db.commit()
        await db.refresh(msg)
        # Return the sanitised text — the raw draft may still carry mail-merge
        # scaffolding that the stored message no longer has.
        return {"chat_id": chat_id, "message": text,
                "message_id": msg.id, "stub": False}

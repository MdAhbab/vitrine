"""Buyer Negotiator (AI Rep) — bargains on the buyer's behalf within budget.

Powers the frontend BargainModal / agent threads. Warm but firm, never exceeds
the authorized budget, references the buyer's brief. See AGENTS.md (negotiator).
"""
from __future__ import annotations

from sqlalchemy import select

from backend.shared.db import SessionLocal
from backend.shared.models import Chat, ChatMessage, Negotiation, User, Order, Listing

from .base import run_agent, system_prompt_for

SYSTEM = system_prompt_for("Buyer Representative Agent",
                           "You are the buyer's negotiating rep. Warm but firm. Never exceed budget.")


async def next_message(chat_id: str) -> dict:
    async with SessionLocal() as db:
        chat = await db.get(Chat, chat_id)
        if not chat or not chat.is_agent:
            return {"error": "not an agent chat"}
        nego = (await db.execute(
            select(Negotiation).where(Negotiation.chat_id == chat_id))).scalar_one_or_none()
        buyer = await db.get(User, chat.buyer_id)
        
        # Fetch buyer's past orders
        orders_stmt = select(Order).where(Order.buyer_id == chat.buyer_id)
        orders = (await db.execute(orders_stmt)).scalars().all()
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
            
        # Fetch message history
        msgs_stmt = select(ChatMessage).where(ChatMessage.chat_id == chat_id).order_by(ChatMessage.created_at.asc())
        history_msgs = (await db.execute(msgs_stmt)).scalars().all()
        history_text = "\n".join([f"{m.sender_name}: {m.text}" for m in history_msgs])

        budget = (chat.agent_budget_cents or 0) / 100
        context = nego.buyer_readme_context if nego else ""
        
        prompt = (
            f"You are negotiating on behalf of the buyer {buyer.display_name if buyer else 'Buyer'}.\n"
            f"Buyer constraints & target: Authorized Max Budget is ${budget}.\n"
            f"Product Context:\n{listing_details}\n"
            f"Buyer's Custom Product Context/Readme Brief:\n{context}\n"
            f"Buyer's Past Orders & History:\n{orders_text}\n"
            f"Conversation History:\n{history_text}\n\n"
            f"Draft the next negotiation message to the seller. Disclose clearly that you are the buyer's AI Representative. "
            f"Be warm but firm. Propose a specific price offer or custom milestone terms that are within the budget and align with the context. "
            f"Do not exceed the authorized budget of ${budget} under any circumstances."
        )
        
        result = await run_agent("negotiator", SYSTEM, prompt, trigger="api")

        msg = ChatMessage(chat_id=chat_id, sender_id="agent",
                          sender_name=f"{buyer.display_name if buyer else 'Buyer'}'s AI Rep",
                          text=result.text, is_agent_rep=True)
        chat.unread_for = ["seller"]
        db.add(msg)
        await db.commit()
        await db.refresh(msg)
        return {"chat_id": chat_id, "message": result.text,
                "message_id": msg.id, "stub": result.stub}

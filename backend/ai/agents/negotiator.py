"""Buyer Negotiator (AI Rep) — bargains on the buyer's behalf within budget.

Powers the frontend BargainModal / agent threads. Warm but firm, never exceeds
the authorized budget, references the buyer's brief. See AGENTS.md (negotiator).
"""
from __future__ import annotations

from sqlalchemy import select

from backend.shared.db import SessionLocal
from backend.shared.models import Chat, ChatMessage, Negotiation, User

from .base import run_agent, system_prompt_for

SYSTEM = system_prompt_for("Buyer Concierge Agent",  # buyerRep prompt lives in admin_configs
                           "You are the buyer's negotiating rep. Warm but firm. Never exceed budget.")


async def next_message(chat_id: str) -> dict:
    async with SessionLocal() as db:
        chat = await db.get(Chat, chat_id)
        if not chat or not chat.is_agent:
            return {"error": "not an agent chat"}
        nego = (await db.execute(
            select(Negotiation).where(Negotiation.chat_id == chat_id))).scalar_one_or_none()
        buyer = await db.get(User, chat.buyer_id)
        last = (await db.execute(
            select(ChatMessage).where(ChatMessage.chat_id == chat_id)
            .order_by(ChatMessage.created_at.desc()).limit(1))).scalar_one_or_none()

        budget = (chat.agent_budget_cents or 0) / 100
        context = nego.buyer_readme_context if nego else ""
        prompt = (f"Buyer {buyer.display_name if buyer else ''}. Authorized budget ${budget}. "
                  f"Brief: {context}. Seller's last message: "
                  f"{last.text if last else '(none)'}. Write the next negotiation message.")
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

"""Buyer Concierge Agent — NL discovery (streamed). See AGENTS.md §3."""
from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy import select

from backend.shared.db import SessionLocal
from backend.shared.models import Listing
from backend.ai.vectorstore import vector_store
from backend.shared.settings import settings

from ..client import client
from .base import resolve_system_prompt, system_prompt_for

_SYSTEM_FALLBACK = system_prompt_for(
    "Buyer Concierge Agent",
    "Help buyers find software in the catalog. Never invent products.",
)


async def _candidates(query: str, k: int = 4) -> list[Listing]:
    async with SessionLocal() as db:
        if query:
            try:
                query_vec = await client.embed(query)
                matches = await vector_store.search(db, query_vec, k=40)
                listing_ids = [m[0] for m in matches]
                if listing_ids:
                    stmt = select(Listing).where(Listing.id.in_(listing_ids), Listing.status == "live")
                    rows = (await db.execute(stmt)).scalars().all()
                    scores = {m[0]: m[1] for m in matches}
                    rows = list(rows)
                    rows.sort(key=lambda x: scores.get(x.id, 0.0), reverse=True)
                    return rows[:k]
            except Exception:
                pass
        
        stmt = select(Listing).where(Listing.status == "live")
        if query:
            stmt = stmt.where((Listing.name.ilike(f"%{query}%")) | (Listing.tagline.ilike(f"%{query}%")))
        return list((await db.execute(stmt.order_by(Listing.vitrine_score.desc()).limit(k))).scalars())


async def stream(query: str, history: list[dict] | None = None) -> AsyncIterator[dict]:
    """Yields SSE-ready dicts: {'type': 'token'|'results'|'done', ...}."""
    rows = await _candidates(query)
    yield {"type": "results", "results": [
        {"id": r.id, "slug": r.slug, "name": r.name, "tagline": r.tagline,
         "price": r.price_cents / 100, "vitrineScore": r.vitrine_score} for r in rows]}

    msg = (f"You are the Concierge. Query: {query!r}. "
           f"Recommend from: {[r.name for r in rows]} with one-line reasons.")
    
    system = await resolve_system_prompt("concierge", _SYSTEM_FALLBACK)
    messages = [{"role": "system", "content": system}]
    if history:
        for h in history:
            messages.append({"role": h.get("role", "user"), "content": h.get("content", "")})
    messages.append({"role": "user", "content": msg})

    if not await client._ensure_client():
        stub_res = client._stub(messages, settings.OPENAI_MODEL)
        for word in stub_res.text.split(" "):
            yield {"type": "token", "text": word + " "}
            import asyncio
            await asyncio.sleep(0.03)
    else:
        try:
            resp = await client._client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=messages,
                stream=True
            )
            async for chunk in resp:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield {"type": "token", "text": chunk.choices[0].delta.content}
        except Exception as e:
            yield {"type": "token", "text": f"Error: {e}"}

    yield {"type": "done"}

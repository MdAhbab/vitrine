"""Buyer Concierge Agent — NL discovery (streamed). See AGENTS.md §3."""
from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy import select

from backend.shared.db import SessionLocal
from backend.shared.models import Listing

from ..client import client
from .base import system_prompt_for

SYSTEM = system_prompt_for("Buyer Concierge Agent",
                           "Help buyers find software in the catalog. Never invent products.")


async def _candidates(query: str, k: int = 4) -> list[Listing]:
    async with SessionLocal() as db:
        stmt = select(Listing).where(Listing.status == "live")
        if query:
            stmt = stmt.where(Listing.name.ilike(f"%{query}%"))
        return list((await db.execute(stmt.order_by(Listing.vitrine_score.desc()).limit(k))).scalars())
    # TODO Phase 2: embed query -> vector_store.search -> hybrid fuse with facets.


async def stream(query: str, history: list[dict] | None = None) -> AsyncIterator[dict]:
    """Yields SSE-ready dicts: {'type': 'token'|'results'|'done', ...}."""
    rows = await _candidates(query)
    yield {"type": "results", "results": [
        {"id": r.id, "slug": r.slug, "name": r.name, "tagline": r.tagline,
         "price": r.price_cents / 100, "vitrineScore": r.vitrine_score} for r in rows]}

    msg = (f"You are the Concierge. Query: {query!r}. "
           f"Recommend from: {[r.name for r in rows]} with one-line reasons.")
    res = await client.chat([{"role": "system", "content": SYSTEM},
                             {"role": "user", "content": msg}])
    # Scaffold streams the whole reply as one token; Phase 2 uses real streaming.
    yield {"type": "token", "text": res.text}
    yield {"type": "done"}

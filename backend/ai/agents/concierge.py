"""Buyer Concierge Agent — NL discovery (streamed). See AGENTS.md §3."""
from __future__ import annotations

from collections.abc import AsyncIterator

from backend.shared.db import SessionLocal
from backend.shared.models import Listing
from backend.shared.settings import settings
from backend.ai.searching import parse_query, search_listings

from ..client import client
from .base import resolve_system_prompt, system_prompt_for

_SYSTEM_FALLBACK = system_prompt_for(
    "Buyer Concierge Agent",
    "Help buyers find software in the catalog. Never invent products.",
)


async def _candidates(query: str, k: int = 4) -> list[Listing]:
    async with SessionLocal() as db:
        return await search_listings(db, query, k=k)


def _catalog_context(rows: list[Listing]) -> str:
    return "\n".join(
        (
            f"- {r.name} ({r.slug}): ${r.price_cents / 100:.0f}, "
            f"{r.framework or 'stack not listed'}, {r.category}, "
            f"tags={', '.join(str(t) for t in (r.tags or []))}; "
            f"tagline={r.tagline}"
        )
        for r in rows
    )


def _fallback_answer(query: str, rows: list[Listing]) -> str:
    parsed = parse_query(query)
    if not rows:
        return "I could not find a live listing that matches those constraints. Try relaxing the budget or framework."

    qualifiers = []
    if parsed.price_max is not None:
        qualifiers.append(f"under ${parsed.price_max:.0f}")
    if parsed.has_demo:
        qualifiers.append("with live demos")
    scope = f" {' and '.join(qualifiers)}" if qualifiers else ""
    names = ", ".join(r.name for r in rows[:3])
    return f"I found {names}{scope}. These are grounded in the live catalog rows shown below."


async def stream(query: str, history: list[dict] | None = None) -> AsyncIterator[dict]:
    """Yields SSE-ready dicts: {'type': 'token'|'results'|'done', ...}."""
    rows = await _candidates(query)
    yield {"type": "results", "results": [
        {"id": r.id, "slug": r.slug, "name": r.name, "tagline": r.tagline,
         "price": r.price_cents / 100, "vitrineScore": r.vitrine_score} for r in rows]}

    from ..budget import budget, BudgetExceeded
    from backend.shared.models import AgentRun
    from backend.shared.cache import content_hash

    try:
        budget.check()
    except BudgetExceeded:
        answer = _fallback_answer(query, rows)
        for word in answer.split(" "):
            yield {"type": "token", "text": word + " "}
            import asyncio
            await asyncio.sleep(0.02)
        yield {"type": "done"}
        return

    msg = (
        f"Buyer query: {query!r}\n"
        "Use only these live catalog rows. Do not invent products, prices, features, or demos.\n"
        f"{_catalog_context(rows)}\n\n"
        "Write a concise recommendation. If no exact match exists, say what constraint was relaxed."
    )
    
    system = await resolve_system_prompt("concierge", _SYSTEM_FALLBACK)
    messages = [{"role": "system", "content": system}]
    if history:
        for h in history:
            messages.append({"role": h.get("role", "user"), "content": h.get("content", "")})
    messages.append({"role": "user", "content": msg})

    is_stub = False
    cost = 0.0
    tokens_in = 0
    tokens_out = 0
    model_used = settings.OPENAI_MODEL

    try:
        resp = await client.chat(messages, model=settings.OPENAI_MODEL)
        answer = resp.text.strip() if resp.text else _fallback_answer(query, rows)
        is_stub = resp.stub
        cost = resp.cost_usd
        tokens_in = resp.tokens_in
        tokens_out = resp.tokens_out
        model_used = resp.model
    except Exception:
        answer = _fallback_answer(query, rows)
        is_stub = True

    budget.record(cost)
    async with SessionLocal() as db:
        db.add(AgentRun(agent="concierge", trigger_event="api",
                        input_hash=f"concierge:{content_hash(query)}",
                        model=model_used, tokens_in=tokens_in,
                        tokens_out=tokens_out, cost_usd=cost,
                        status="degraded" if is_stub else "ok"))
        await db.commit()

    for word in answer.split(" "):
        yield {"type": "token", "text": word + " "}
        import asyncio
        await asyncio.sleep(0.02)

    yield {"type": "done"}

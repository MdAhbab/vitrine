"""Grounded catalog search helpers shared by Search and Concierge."""
from __future__ import annotations

from dataclasses import dataclass
import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.ai.client import client
from backend.ai.vectorstore import vector_store
from backend.shared.models import Listing


STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "by", "for", "from", "i", "in",
    "is", "it", "me", "of", "on", "or", "that", "the", "this", "to",
    "under", "below", "less", "than", "with", "without", "live", "demo",
    "preview", "runnable", "find", "need", "want", "show", "software",
}

CATEGORY_TERMS = {
    "dashboard": "Dashboards",
    "dashboards": "Dashboards",
    "analytics": "Analytics",
    "commerce": "E-commerce",
    "ecommerce": "E-commerce",
    "storefront": "E-commerce",
    "shop": "E-commerce",
    "ai": "AI",
    "chat": "AI",
    "crm": "CRM",
    "cms": "CMS",
    "finance": "Finance",
    "auth": "Auth",
    "security": "Auth",
    "productivity": "Productivity",
    "enterprise": "Enterprise",
    "healthcare": "Healthcare",
    "telehealth": "Healthcare",
}


@dataclass(frozen=True)
class ParsedQuery:
    raw: str
    terms: tuple[str, ...]
    price_max: float | None = None
    has_demo: bool | None = None
    category_hint: str | None = None


def parse_query(query: str) -> ParsedQuery:
    raw = query.strip()
    lower = raw.lower()

    price_max: float | None = None
    price_patterns = [
        r"(?:under|below|less\s+than|up\s+to|max(?:imum)?|budget(?:\s+of)?|<=)\s*\$?\s*(\d+(?:\.\d+)?)",
        r"\$\s*(\d+(?:\.\d+)?)\s*(?:or\s+less|max|budget)",
    ]
    for pattern in price_patterns:
        match = re.search(pattern, lower)
        if match:
            price_max = float(match.group(1))
            break

    has_demo = True if re.search(r"\b(live\s+demo|demo|preview|runnable)\b", lower) else None

    category_hint = None
    for term, category in CATEGORY_TERMS.items():
        if re.search(rf"\b{re.escape(term)}\b", lower):
            category_hint = category
            break

    terms = []
    for term in re.findall(r"[a-z0-9][a-z0-9.+#-]*", lower):
        if term not in STOPWORDS and not term.replace(".", "", 1).isdigit():
            terms.append(term)

    return ParsedQuery(raw=raw, terms=tuple(dict.fromkeys(terms)), price_max=price_max, has_demo=has_demo, category_hint=category_hint)


def _text_for(listing: Listing) -> str:
    parts = [
        listing.name,
        listing.tagline,
        listing.category,
        listing.subcategory or "",
        listing.framework or "",
        listing.description or "",
        " ".join(str(t) for t in (listing.tags or [])),
        " ".join(str(t) for t in (listing.tech_stack or [])),
    ]
    return " ".join(parts).lower()


def _score(listing: Listing, parsed: ParsedQuery, vector_scores: dict[str, float]) -> float:
    text = _text_for(listing)
    score = (listing.vitrine_score or 0) / 100
    score += max(vector_scores.get(listing.id, 0.0), 0.0) * 1.5

    if parsed.category_hint and listing.category == parsed.category_hint:
        score += 3.0

    if parsed.has_demo is True and listing.demo_url:
        score += 1.0

    if parsed.price_max is not None:
        price = listing.price_cents / 100
        score += max(0.0, (parsed.price_max - price) / max(parsed.price_max, 1)) * 0.75

    for term in parsed.terms:
        if term in text:
            score += 1.0
        if term in [str(t).lower() for t in (listing.tags or [])]:
            score += 1.5
        if listing.framework and term in listing.framework.lower():
            score += 1.5
        if term == "react" and listing.framework and listing.framework.lower() in {"next.js", "nextjs", "remix"}:
            score += 0.75
        if term == "stripe" and "stripe" in text:
            score += 2.5

    return score


async def search_listings(
    db: AsyncSession,
    query: str,
    *,
    k: int = 40,
    category: str | None = None,
    price_max: float | None = None,
    has_demo: bool | None = None,
    use_ai: bool = True,
) -> list[Listing]:
    parsed = parse_query(query)
    effective_price_max = price_max if price_max is not None else parsed.price_max
    effective_has_demo = has_demo if has_demo is not None else parsed.has_demo

    stmt = select(Listing).where(Listing.status == "live")
    if category:
        stmt = stmt.where(Listing.category == category)
    if effective_price_max is not None:
        stmt = stmt.where(Listing.price_cents <= int(effective_price_max * 100))
    if effective_has_demo is not None:
        stmt = stmt.where(Listing.demo_url.isnot(None) if effective_has_demo else Listing.demo_url.is_(None))

    rows = list((await db.execute(stmt)).scalars().all())
    if not rows:
        return []

    vector_scores: dict[str, float] = {}
    if query.strip() and use_ai:
        try:
            query_vec = await client.embed(query)
            vector_scores = dict(await vector_store.search(db, query_vec, k=100))
        except Exception:
            vector_scores = {}

    if not query.strip():
        rows.sort(key=lambda r: r.vitrine_score or 0, reverse=True)
        return rows[:k]

    rows.sort(key=lambda r: _score(r, parsed, vector_scores), reverse=True)
    return rows[:k]

"""Curation & Ranking Agent — the Vitrine Score. See AGENTS.md §5 + README §6.

Mostly deterministic (cheap); the only LLM/vision cost is a one-time UI score.
"""
from __future__ import annotations

from backend.shared.db import SessionLocal
from backend.shared.models import Listing

WEIGHTS = {  # see README §6 (tunable via VITRINE_SCORE_WEIGHTS)
    "completeness": 0.20, "verification": 0.15, "reviews": 0.20,
    "ui": 0.15, "demo_health": 0.10, "recency": 0.10, "engagement": 0.10,
}


def _score(signals: dict[str, float]) -> float:
    return round(100 * sum(WEIGHTS[k] * signals.get(k, 0) for k in WEIGHTS), 1)


async def run(listing_id: str) -> dict:
    # TODO Phase 2: compute real signals (completeness from listing_fields,
    # bayesian rating, demo uptime, recency decay, engagement) + cached
    # vision_score_ui on the cover. Scaffold uses placeholder signals.
    signals = {"completeness": 0.9, "verification": 1.0, "reviews": 0.85,
               "ui": 0.9, "demo_health": 0.95, "recency": 0.8, "engagement": 0.7}
    score = _score(signals)
    breakdown = [{"label": k, "value": round(v * 100)} for k, v in signals.items()]
    async with SessionLocal() as db:
        listing = await db.get(Listing, listing_id)
        if listing:
            listing.vitrine_score = score
            listing.score_breakdown = breakdown
            await db.commit()
    return {"listing_id": listing_id, "vitrine_score": score, "breakdown": breakdown}

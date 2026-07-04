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


async def _engagement(listing_id: str) -> float:
    """Engagement signal from real analytic events (was a hardcoded 0.7).

    Views count once, demo launches 3x (stronger intent), scaled so ~150
    weighted events over 14 days saturates the signal. Floor of 0.3 keeps new
    listings from being buried purely for lack of traffic history.
    """
    from datetime import datetime, timedelta, timezone
    from sqlalchemy import func, select
    from backend.shared.models import AnalyticEvent

    cutoff = datetime.now(timezone.utc) - timedelta(days=14)
    async with SessionLocal() as db:
        rows = (await db.execute(
            select(AnalyticEvent.event_type, func.count())
            .where(AnalyticEvent.listing_id == listing_id, AnalyticEvent.created_at >= cutoff)
            .group_by(AnalyticEvent.event_type)
        )).all()
    counts = {etype: n for etype, n in rows}
    weighted = counts.get("view", 0) + 3 * counts.get("launch", 0)
    return round(min(1.0, max(0.3, weighted / 150)), 2)


async def run(listing_id: str) -> dict:
    from backend.ai.tools import compute_features, bayesian_rating, vision_score_ui
    
    feats = await compute_features(listing_id)
    completeness = feats.get("completeness", 80) / 100.0
    recency = feats.get("recency", 80) / 100.0
    
    async with SessionLocal() as db:
        listing = await db.get(Listing, listing_id)
        if not listing:
            return {"listing_id": listing_id, "error": "Listing not found"}
        verification = 1.0 if listing.status == "live" else 0.5
        demo_health = {"live": 1.0, "degraded": 0.5, "down": 0.0}.get(listing.demo_health, 1.0)
        cover_url = listing.cover or ""
        
    rating_res = await bayesian_rating(listing_id)
    reviews = rating_res.get("rating", 4.0) / 5.0

    ui_res = await vision_score_ui(cover_url)
    ui = ui_res.get("ui_score", 0.8)

    engagement = await _engagement(listing_id)

    signals = {
        "completeness": completeness,
        "verification": verification,
        "reviews": reviews,
        "ui": ui,
        "demo_health": demo_health,
        "recency": recency,
        "engagement": engagement
    }
    
    score = _score(signals)
    breakdown = [{"label": k, "value": round(v * 100)} for k, v in signals.items()]
    
    async with SessionLocal() as db:
        listing = await db.get(Listing, listing_id)
        if listing:
            listing.vitrine_score = score
            listing.score_breakdown = breakdown
            # IMPORTANT: only emit badge keys the frontend Badge component knows
            # ('verified' | 'best-ui' | 'new' | 'live-demo'). Anything else
            # crashes <Badge>. Derive from real signals; don't clobber identity.
            from datetime import datetime, timezone
            badges: list[str] = []
            if listing.status == "live":
                badges.append("verified")
            if listing.demo_url and listing.demo_health == "live":
                badges.append("live-demo")
            if score >= 93:
                badges.append("best-ui")
            created = listing.created_at
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            if (datetime.now(timezone.utc) - created).days <= 14:
                badges.append("new")
            listing.badges = badges
            db.add(listing)
            await db.commit()
            
    return {"listing_id": listing_id, "vitrine_score": score, "breakdown": breakdown}

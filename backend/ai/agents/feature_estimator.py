"""Feature Cost Estimator — auto-quotes custom-feature requests.

Returns a coherent quote: the price and the rationale come from the SAME model
call (no more "$150" charge next to a "$4,000" rationale), and the rationale is
clean prose, not a raw JSON dump. Backs the frontend RequestFeaturesModal.
"""
from __future__ import annotations

from backend.shared.db import SessionLocal
from backend.shared.models import Listing

from .base import run_json, system_prompt_for

SYSTEM = system_prompt_for(
    "Pricing & Pitch Agent",
    "You are Vitrine's Feature Cost Estimator. Estimate a fair price range for a "
    "custom software feature. Be transparent: this is a starting point for the "
    "seller, not a final invoice.",
)


def _fallback(description: str) -> dict:
    charge = max(150, min(8000, len(description) * 25))
    return {
        "estimated_charge": charge,
        "range_low": round(charge * 0.7),
        "range_high": round(charge * 1.5),
        "rationale": ("Rough estimate based on scope. Connect with the seller to "
                      "refine against your exact requirements and timeline."),
        "stub": True,
    }


async def estimate(listing_id: str, description: str) -> dict:
    async with SessionLocal() as db:
        listing = await db.get(Listing, listing_id)

    ctx = ""
    if listing:
        ctx = (f"Listing: {listing.name} ({listing.category}), base price "
               f"${listing.price_cents / 100:.0f}, stack {listing.tech_stack}.")

    prompt = (
        f"{ctx}\n"
        f"Requested custom feature: {description}\n\n"
        "Estimate the cost to build this feature. Return ONLY a JSON object:\n"
        '  "estimated_charge": integer USD (your single best point estimate)\n'
        '  "range_low": integer USD\n'
        '  "range_high": integer USD\n'
        '  "rationale": 2-3 sentences of PLAIN PROSE (no markdown, no JSON, no '
        'code fences) explaining complexity, rough developer-hours, and why this price.\n'
        "The estimated_charge MUST sit inside [range_low, range_high] and MUST be "
        "consistent with the rationale's reasoning."
    )

    data, stub = await run_json("feature_estimator", SYSTEM, prompt,
                                listing_id=listing_id, trigger="feature.requested")
    if stub or not data or "estimated_charge" not in data:
        return _fallback(description)

    try:
        charge = int(float(data["estimated_charge"]))
        low = int(float(data.get("range_low", charge * 0.7)))
        high = int(float(data.get("range_high", charge * 1.5)))
    except (TypeError, ValueError):
        return _fallback(description)

    low = min(low, charge)
    high = max(high, charge)
    return {
        "estimated_charge": charge,
        "range_low": low,
        "range_high": high,
        "rationale": str(data.get("rationale", "")).strip(),
        "stub": False,
    }

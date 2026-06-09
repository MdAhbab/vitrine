"""Feature Cost Estimator — auto-quotes custom-feature requests (a Pricing-agent
specialization). Backs the frontend RequestFeaturesModal."""
from __future__ import annotations

from .base import run_agent, system_prompt_for

SYSTEM = system_prompt_for("Pricing & Pitch Agent",
                           "Estimate a fair price range for a custom software feature request. "
                           "Be transparent: this is a starting point for the seller, not an invoice.")


async def estimate(listing_id: str, description: str) -> dict:
    # TODO Phase 2: ground in comparable feature work in the same category.
    result = await run_agent("feature_estimator", SYSTEM,
                             f"Estimate cost for this feature on listing {listing_id}:\n{description}",
                             listing_id=listing_id, trigger="feature.requested")
    # Scaffold heuristic range; replace with model-extracted numbers.
    base = max(150, min(5000, len(description) * 3))
    return {"estimated_charge": base, "range_low": round(base * 0.7),
            "range_high": round(base * 1.6), "rationale": result.text, "stub": result.stub}

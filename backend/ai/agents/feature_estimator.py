"""Feature Cost Estimator — auto-quotes custom-feature requests (a Pricing-agent
specialization). Backs the frontend RequestFeaturesModal."""
from __future__ import annotations

from backend.shared.db import SessionLocal
from backend.shared.models import Listing
from backend.ai.tools import estimate_feature_cost

from .base import run_agent, system_prompt_for

SYSTEM = system_prompt_for("Pricing & Pitch Agent",
                           "Estimate a fair price range for a custom software feature request. "
                           "Be transparent: this is a starting point for the seller, not an invoice.")


async def estimate(listing_id: str, description: str) -> dict:
    async with SessionLocal() as db:
        listing = await db.get(Listing, listing_id)
        
    listing_context = ""
    if listing:
        listing_context = (
            f"Listing Name: {listing.name}\n"
            f"Category: {listing.category}\n"
            f"Price: ${listing.price_cents/100:.2f}\n"
            f"Tech Stack: {listing.tech_stack}\n"
        )
        
    prompt = (
        f"You are the Feature Cost Estimator Agent.\n"
        f"Target Listing Context:\n{listing_context}\n"
        f"Requested custom feature description:\n{description}\n\n"
        f"Please analyze the requested feature and write a brief, professional rationale detailing the complexity, "
        f"estimated developer hours, and a recommended price range. Explain why this estimation makes sense."
    )
    
    result = await run_agent("feature_estimator", SYSTEM, prompt, listing_id=listing_id, trigger="feature.requested")
    
    tool_res = await estimate_feature_cost(listing_id, description)
    charge = tool_res["estimated_charge"]
    
    return {
        "estimated_charge": charge,
        "range_low": tool_res["range_low"],
        "range_high": tool_res["range_high"],
        "rationale": result.text,
        "stub": result.stub
    }

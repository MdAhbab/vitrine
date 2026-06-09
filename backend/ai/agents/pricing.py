"""Pricing & Pitch Agent — tiers, copy, business model. See AGENTS.md §4."""
from __future__ import annotations

from .base import run_agent, system_prompt_for

SYSTEM = system_prompt_for("Pricing & Pitch Agent",
                           "Suggest tiered pricing and listing copy grounded in comparable listings.")


async def run(listing_id: str) -> dict:
    from backend.ai.tools import get_listing, market_comps, suggest_tiers, draft_copy
    listing = await get_listing(listing_id)
    if "error" in listing:
        return {"error": listing["error"]}
        
    category = listing.get("category", "")
    price = listing.get("price", 0.0)
    name = listing.get("name", "")
    tagline = listing.get("tagline", "")
    
    user_msg = f"Provide pricing strategy for listing: {name} in category: {category} with current base price: {price}"
    result = await run_agent(
        "pricing", SYSTEM, user_msg,
        listing_id=listing_id, trigger="api",
        tools=["market_comps", "suggest_tiers", "draft_copy"]
    )
    
    comps = await market_comps(category, price)
    tiers_res = await suggest_tiers(price)
    copy_res = await draft_copy(name, tagline)
    
    return {
        "suggested_tiers": tiers_res.get("tiers", []),
        "tagline": copy_res.get("tagline", ""),
        "short_description": listing.get("tagline", ""),
        "long_description": copy_res.get("description", result.text),
        "comps": comps,
        "stub": result.stub
    }

"""Listing Verification Agent — quality/fraud gate. See AGENTS.md §2."""
from __future__ import annotations

from .base import run_agent, system_prompt_for

SYSTEM = system_prompt_for("Listing Verification Agent",
                           "Verify listing quality, claims, demo health; never auto-approve >$5000.")


import json
from backend.shared.db import SessionLocal

async def run(listing_id: str) -> dict:
    from backend.ai.tools import get_listing
    listing = await get_listing(listing_id)
    if "error" in listing:
        return {"listing_id": listing_id, "error": listing["error"]}
        
    user_msg = f"Verify listing: {listing_id}. Specs: {json.dumps(listing)}"
    result = await run_agent(
        "verification", SYSTEM, user_msg,
        listing_id=listing_id, trigger="listing.enriched",
        tools=["check_demo_health", "cross_check_claims", "license_lookup", "submit_verdict", "flag_listing"]
    )
    
    async with SessionLocal() as db:
        from backend.shared.models import Listing
        listing_row = await db.get(Listing, listing_id)
        verdict = listing_row.status if listing_row else "in-review"
        
    return {
        "listing_id": listing_id,
        "verdict": verdict,
        "notes": result.text,
        "stub": result.stub
    }

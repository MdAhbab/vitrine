"""Listing Verification Agent — quality/fraud gate. See AGENTS.md §2."""
from __future__ import annotations

from .base import run_agent, system_prompt_for

SYSTEM = system_prompt_for("Listing Verification Agent",
                           "Verify listing quality, claims, demo health; never auto-approve >$5000.")


async def run(listing_id: str) -> dict:
    # TODO Phase 2: demo health check + claim cross-check + license sanity ->
    # verdict (approve|request_changes|flag) and emit listing.verified/flagged.
    result = await run_agent("verification", SYSTEM,
                             f"Verify listing {listing_id}. Return a verdict.",
                             listing_id=listing_id, trigger="listing.enriched")
    return {"listing_id": listing_id, "verdict": "request_changes",
            "reasons": ["scaffold: implement checks"], "notes": result.text, "stub": result.stub}

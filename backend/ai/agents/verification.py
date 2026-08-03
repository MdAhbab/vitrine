"""Listing Verification Agent — quality/fraud gate. See AGENTS.md §2."""
from __future__ import annotations

from .base import run_agent, system_prompt_for

SYSTEM = system_prompt_for("Listing Verification Agent",
                           "Verify listing quality, claims, demo health; never auto-approve >$5000.")


import json

from backend.shared.db import SessionLocal

# Fields the verdict actually turns on. The rest of the form sheet is reachable
# via the get_listing tool if the model needs it.
_BRIEF_KEYS = ("id", "name", "category", "price", "license", "demo_url", "status",
               "framework", "tech_stack")
_MAX_TEXT_CHARS = 1200
_MAX_FIELDS = 40


def _brief(listing: dict) -> dict:
    """Compact verification brief.

    The whole listing used to be json.dumps'd into the prompt, so token cost grew
    with how complete a spec sheet was — the most thorough sellers were the most
    expensive to verify.
    """
    out = {k: listing.get(k) for k in _BRIEF_KEYS if listing.get(k) is not None}
    desc = (listing.get("description") or "").strip()
    if desc:
        out["description"] = desc[:_MAX_TEXT_CHARS]
    fields = listing.get("fields") or {}
    if fields:
        out["fields"] = {
            k: (v[:400] if isinstance(v, str) else v)
            for k, v in list(fields.items())[:_MAX_FIELDS]
        }
    tiers = listing.get("tiers") or []
    if tiers:
        out["tiers"] = [{"name": t.get("name"), "price": t.get("price")} for t in tiers[:6]]
    return out


async def run(listing_id: str) -> dict:
    from backend.ai.tools import get_listing
    listing = await get_listing(listing_id)
    if "error" in listing:
        return {"listing_id": listing_id, "error": listing["error"]}

    user_msg = (f"Verify listing: {listing_id}.\n"
                f"Specs: {json.dumps(_brief(listing), default=str)}")
    result = await run_agent(
        "verification", SYSTEM, user_msg,
        listing_id=listing_id, trigger="listing.enriched",
        tools=["get_listing", "check_demo_health", "cross_check_claims",
               "license_lookup", "submit_verdict", "flag_listing"]
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

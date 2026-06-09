"""Pricing & Pitch Agent — tiers, copy, business model. See AGENTS.md §4."""
from __future__ import annotations

from .base import run_agent, system_prompt_for

SYSTEM = system_prompt_for("Pricing & Pitch Agent",
                           "Suggest tiered pricing and listing copy grounded in comparable listings.")


async def run(listing_id: str) -> dict:
    # TODO Phase 2: pull market comps (category + embedding) before quoting.
    result = await run_agent("pricing", SYSTEM,
                             f"Propose 3 tiers + tagline + descriptions for listing {listing_id}.",
                             listing_id=listing_id, trigger="api")
    return {
        "suggested_tiers": [
            {"name": "Source", "price": 0, "features": ["Full source", "License", "Email support"]},
            {"name": "Source + Setup", "price": 80, "features": ["Onboarding call", "30 days fixes"]},
            {"name": "Bespoke", "price": 280, "features": ["Reskin", "Domain setup", "90 days support"]},
        ],
        "tagline": "", "short_description": "", "long_description": result.text,
        "stub": result.stub,
    }

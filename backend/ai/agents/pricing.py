"""Pricing & Pitch Agent — tiers, copy, business model. See AGENTS.md §4.

Returns the MODEL's real, structured pricing (grounded in live market comps),
not a hardcoded formula. Tiers scale sensibly with the base price.
"""
from __future__ import annotations

from .base import run_json, system_prompt_for

SYSTEM = system_prompt_for(
    "Pricing & Pitch Agent",
    "You are Vitrine's Pricing & Pitch agent. Propose tiered pricing and listing "
    "copy grounded in comparable listings. Be specific to the product; pricing is "
    "a starting point for the seller, not a final invoice.",
)


def _fallback(name: str, tagline: str, price: float) -> dict:
    p = price or 49
    return {
        "suggested_tiers": [
            {"name": "Source", "price": round(p), "features": ["Full source code", "License", "Email support"]},
            {"name": "Source + Setup", "price": round(p * 1.4), "recommended": True,
             "features": ["Everything in Source", "Onboarding call", "30 days of fixes"]},
            {"name": "Bespoke", "price": round(p * 2.2),
             "features": ["Everything in Source + Setup", "Brand reskin", "90 days priority support"]},
        ],
        "tagline": tagline or f"{name} — production-ready, beautifully built.",
        "short_description": tagline,
        "long_description": f"{name} is a polished, production-ready codebase you can ship today.",
    }


async def run(listing_id: str) -> dict:
    from backend.ai.tools import get_listing, market_comps

    listing = await get_listing(listing_id)
    if "error" in listing:
        return {"error": listing["error"]}

    name = listing.get("name", "")
    tagline = listing.get("tagline", "")
    category = listing.get("category", "")
    price = listing.get("price", 0.0) or 0.0
    comps = await market_comps(category, price)

    prompt = (
        f"Product: {name} — {tagline}\n"
        f"Category: {category}. Current base price: ${price}.\n"
        f"Live market comps (avg ${comps.get('average_market_price')}): "
        f"{comps.get('comps')}\n\n"
        "Propose a pricing & pitch strategy. Return ONLY a JSON object with keys:\n"
        '  "tiers": array of EXACTLY 3 objects {"name","price"(number, USD),'
        '"features"(3-4 short strings),"recommended"(bool, true on the middle tier)}\n'
        '  "tagline": one punchy line (<= 80 chars)\n'
        '  "short_description": one sentence\n'
        '  "long_description": 2-3 sentences specific to THIS product\n'
        "Rules: tier prices MUST scale with the base price (premium tiers are a "
        "meaningful percentage above base — NOT a flat +$80). Anchor against the comps. "
        "All copy must be specific to this product, never generic boilerplate."
    )

    data, stub = await run_json("pricing", SYSTEM, prompt, listing_id=listing_id)
    if stub or not data or not data.get("tiers"):
        out = _fallback(name, tagline, price)
        out["comps"] = comps
        out["stub"] = stub
        return out

    return {
        "suggested_tiers": data.get("tiers", []),
        "tagline": data.get("tagline", tagline),
        "short_description": data.get("short_description", tagline),
        "long_description": data.get("long_description", ""),
        "comps": comps,
        "stub": False,
    }

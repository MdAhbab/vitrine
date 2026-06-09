"""
Seed demo data so the storefront + dashboards aren't empty.

    python -m backend.seed        (or: python backend/seed.py)

Idempotent: skips if the demo admin already exists. Creates tables first.
Mirrors a slice of frontend/src/app/lib/mockData.ts so the UI feels populated.
Demo logins:  admin@vitrine.io / admin   ·   maker@vitrine.io / maker   ·   buyer@vitrine.io / buyer
"""
from __future__ import annotations

import asyncio

from sqlalchemy import select

from backend.shared.db import SessionLocal, create_all
from backend.shared.ids import slugify
from backend.shared.models import (
    AdminConfig,
    Listing,
    ListingField,
    ListingTier,
    User,
)
from backend.shared.security import hash_password

COVER = "https://images.unsplash.com/photo-1551288049-bebda4e38f71?auto=format&fit=crop&w=1600&q=80"
SHOTS = [COVER,
         "https://images.unsplash.com/photo-1460925895917-afdab827c52f?auto=format&fit=crop&w=1600&q=80"]

DEMO_LISTINGS = [
    # name, tagline, category, price$, framework, score, tags
    ("Halcyon", "A quiet operations cockpit", "Dashboards", 89, "Next.js", 96, ["saas", "admin", "charts"]),
    ("Atrium AI", "A chat surface that respects you", "AI", 79, "React", 95, ["ai", "chat", "sse"]),
    ("Maison ERP", "A full enterprise resource platform", "Enterprise", 18500, "Next.js", 97, ["enterprise", "erp"]),
]

DEFAULT_CONFIG = {
    "system_prompts": {
        "concierge": "You are Vitrine's Concierge. Help buyers find the right software piece.",
        "buyerRep": "You are a buyer's negotiating rep. Warm but firm. Never exceed the budget.",
        "pricingAgent": "You are Vitrine's Pricing & Pitch agent. Auto-quote custom-feature requests.",
        "verification": "You are Vitrine's Verification agent. Flag, do not auto-approve, anything > $5,000.",
    },
    "flags": {"aiBargain": True, "conciergeSearch": True, "enterpriseTier": True,
              "studentDiscount": True, "newSignupsOpen": True},
    "fees": {"commissionFree": 12, "commissionStudio": 8, "commissionAtelier": 5,
             "commissionMaison": 3, "enterprise": 2, "processing": 2.5},
    "escrow": {"holdHours": 48, "refundWindow": 7, "autoRelease": True},
    "branding": {"headline": "Software, but make it editorial.",
                 "tagline": "A boutique marketplace for live, runnable software.",
                 "supportEmail": "curator@vitrine.io"},
    "notes": "",
    "api_keys": [],
}


async def seed() -> None:
    await create_all()
    async with SessionLocal() as db:
        if (await db.execute(select(User).where(User.email == "admin@vitrine.io"))).scalar_one_or_none():
            print("[seed] already seeded — skipping.")
            return

        admin = User(email="admin@vitrine.io", password_hash=hash_password("admin"),
                     role="admin", display_name="Vitrine Curator")
        maker = User(email="maker@vitrine.io", password_hash=hash_password("maker"),
                     role="seller", display_name="Atelier Foxglove", handle="@foxglove",
                     verified=True, plan="studio")
        buyer = User(email="buyer@vitrine.io", password_hash=hash_password("buyer"),
                     role="buyer", display_name="June Park")
        db.add_all([admin, maker, buyer])
        await db.flush()

        for name, tagline, cat, price, fw, score, tags in DEMO_LISTINGS:
            listing = Listing(
                owner_id=maker.id, name=name, slug=slugify(name), tagline=tagline,
                category=cat, tags=tags, framework=fw, price_cents=price * 100,
                license="MIT", status="live", demo_url="https://vercel.com",
                demo_health="live", vitrine_score=score, cover=COVER, screenshots=SHOTS,
                badges=["verified", "live-demo", "best-ui"],
                description="A meticulously crafted, production-ready application.",
                rating=4.7, reviews_count=128, rating_distribution=[2, 3, 8, 24, 63],
                score_breakdown=[{"label": "Completeness", "value": 92},
                                 {"label": "UI craft", "value": score - 2},
                                 {"label": "Demo health", "value": 96}],
                sdlc={"problem": f"Teams stitch together five tools for {cat.lower()} work.",
                      "solution": "A focused codebase shipping the 80% you actually use.",
                      "methodology": "Designed in the open; built in two-week cycles.",
                      "discussions": "How opinionated should the data layer remain?"},
                business_model={"kind": "for-profit",
                                "pitch": "A commercial codebase you can rebrand and bill against.",
                                "revenueStreams": ["Source license sales", "Bespoke commissions"]},
                tech_stack=[fw, "TypeScript", "Tailwind CSS", "PostgreSQL"],
            )
            db.add(listing)
            await db.flush()
            db.add_all([
                ListingTier(listing_id=listing.id, name="Source", price_cents=price * 100,
                            features=["Full source code", "MIT license", "Email support"]),
                ListingTier(listing_id=listing.id, name="Source + Setup",
                            price_cents=(price + 80) * 100, recommended=True,
                            features=["Onboarding call", "30 days of fixes"]),
                ListingField(listing_id=listing.id, section="Development", key="Stack",
                             value=f"{fw} · TypeScript · Tailwind", source="ai", confidence=0.9),
                ListingField(listing_id=listing.id, section="Data", key="Database",
                             value="Postgres", source="ai", confidence=0.85),
            ])

        for key, value in DEFAULT_CONFIG.items():
            db.add(AdminConfig(key=key, value=value))

        await db.commit()
        print("[seed] inserted demo users, listings, and admin config.")


if __name__ == "__main__":
    asyncio.run(seed())

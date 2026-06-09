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
    ListingEmbedding,
)
from backend.shared.security import hash_password
from backend.ai.client import client

COVER = "https://images.unsplash.com/photo-1551288049-bebda4e38f71?auto=format&fit=crop&w=1600&q=80"
SHOTS = [
    COVER,
    "https://images.unsplash.com/photo-1460925895917-afdab827c52f?auto=format&fit=crop&w=1600&q=80"
]

COVERS = {
    "dashboard": "https://images.unsplash.com/photo-1551288049-bebda4e38f71?auto=format&fit=crop&w=1600&q=80",
    "analytics": "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?auto=format&fit=crop&w=1600&q=80",
    "ecommerce": "https://images.unsplash.com/photo-1481437156560-3205f6a55735?auto=format&fit=crop&w=1600&q=80",
    "ai": "https://images.unsplash.com/photo-1677442136019-21780ecad995?auto=format&fit=crop&w=1600&q=80",
    "finance": "https://images.unsplash.com/photo-1554224155-6726b3ff858f?auto=format&fit=crop&w=1600&q=80",
    "crm": "https://images.unsplash.com/photo-1556761175-5973dc0f32e7?auto=format&fit=crop&w=1600&q=80",
    "cms": "https://images.unsplash.com/photo-1481487196290-c152efe083f5?auto=format&fit=crop&w=1600&q=80",
    "productivity": "https://images.unsplash.com/photo-1454165804606-c3d57bc86b40?auto=format&fit=crop&w=1600&q=80",
    "auth": "https://images.unsplash.com/photo-1563986768609-322da13575f3?auto=format&fit=crop&w=1600&q=80",
    "enterprise": "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?auto=format&fit=crop&w=1600&q=80",
    "healthcare": "https://images.unsplash.com/photo-1576091160399-112ba8d25d1d?auto=format&fit=crop&w=1600&q=80",
}

DEMO_LISTINGS = [
    # Dashboards
    (
        "Halcyon",
        "A quiet operations cockpit",
        "Dashboards",
        89,
        "Next.js",
        96,
        ["saas", "admin", "charts"],
        "dashboard",
        "A quiet operations cockpit for early-stage startup operators, designed with a focus on restrained typography and zero clutter. Integrates with Stripe, Github, and Vercel APIs to provide a single view of your company health.",
    ),
    (
        "Cantata Dash",
        "Charts as composition",
        "Dashboards",
        119,
        "Vue",
        93,
        ["dashboard", "vue", "charts"],
        "dashboard",
        "A beautiful modular dashboard for audio-processing workflows and music metadata metrics. Fully themed with smooth dark transitions and WebAudio visualisations.",
    ),

    # Analytics
    (
        "Foxglove Analytics",
        "Editorial analytics for serious teams",
        "Analytics",
        129,
        "React",
        94,
        ["analytics", "charts", "b2b"],
        "analytics",
        "Privacy-first, self-hostable analytics designed for creators. Generates editorial-grade report pages and handles high throughput tracking via serverless functions.",
    ),
    (
        "Plumb Line",
        "Deep-nested funnel analytics",
        "Analytics",
        149,
        "Svelte",
        91,
        ["analytics", "funnels", "saas"],
        "analytics",
        "A specialized analytics application for visualising nested user conversions and multi-path checkout tunnels. Built using Svelte for extremely fast rendering.",
    ),

    # E-commerce
    (
        "Lumen Commerce",
        "Headless storefront with taste",
        "E-commerce",
        149,
        "Next.js",
        92,
        ["commerce", "stripe", "headless"],
        "ecommerce",
        "A gorgeous storefront built on top of Stripe and Shopify APIs. Features instant page loads, client-side cart synchronization, and fluid layout-shift animations.",
    ),
    (
        "Maisonette",
        "Boutique digital goods checkout",
        "E-commerce",
        79,
        "Remix",
        90,
        ["commerce", "checkout", "digital"],
        "ecommerce",
        "Minimal checkout application optimized for authors, designers, and developers selling digital downloads, software licenses, or artwork direct to buyers.",
    ),

    # AI
    (
        "Atrium AI",
        "A chat surface that respects you",
        "AI",
        79,
        "React",
        95,
        ["ai", "chat", "sse"],
        "ai",
        "A modular chat interface for LLMs with full support for Markdown formatting, LaTeX formulas, code editing highlights, and customizable streaming parameters.",
    ),
    (
        "Hermes Vector",
        "Semantic search pipeline in a box",
        "AI",
        159,
        "Next.js",
        93,
        ["ai", "vector", "search"],
        "ai",
        "A ready-to-run search wrapper that indexes local folders and hosts a clean web GUI for lightning-fast semantic queries using local transformer models.",
    ),

    # Finance
    (
        "Ledger Field",
        "Finance dashboards, restrained",
        "Finance",
        199,
        "React",
        91,
        ["finance", "charts", "ledger"],
        "finance",
        "Double-entry bookkeeping frontend that makes ledger auditing beautiful. Built with keyboard shortcut navigations and offline synchronization models.",
    ),
    (
        "Compass Trading Desk",
        "Production-grade trading desk",
        "Finance",
        24900,
        "React",
        96,
        ["finance", "trading", "full-app", "enterprise"],
        "finance",
        "A high-frequency dashboard interface built with canvas-based stock charting libraries, order execution workflows, and multi-exchange API sync adapters.",
    ),

    # CRM
    (
        "Korr CRM",
        "A CRM you actually open on Mondays",
        "CRM",
        99,
        "Remix",
        90,
        ["crm", "pipeline", "sales"],
        "crm",
        "A CRM that avoids complex forms and instead focuses on a visual drag-and-drop kanban pipeline, keyboard-focused notes entry, and automatic emails followups.",
    ),
    (
        "Apex Contact",
        "High-velocity sales pipeline",
        "CRM",
        149,
        "React",
        89,
        ["crm", "sales", "contacts"],
        "crm",
        "Contact management utility designed for small teams. Syncs with Google Contacts, extracts social links automatically, and records history timeline events.",
    ),

    # CMS
    (
        "Margins",
        "A writing-first CMS",
        "CMS",
        59,
        "Astro",
        89,
        ["cms", "markdown", "mdx"],
        "cms",
        "A light publishing engine focused on MDX articles, beautiful typographic layouts, and instant static-site deployments to Github Pages or Netlify.",
    ),
    (
        "Vellum Press",
        "Headless publishing engine",
        "CMS",
        89,
        "Next.js",
        91,
        ["cms", "publishing", "headless"],
        "cms",
        "A headless CMS offering a sleek editor surface, media organizer, version control history, and quick webhook deployments to any web backend service.",
    ),

    # Productivity
    (
        "Quiet Hours",
        "Personal productivity, distilled",
        "Productivity",
        39,
        "React",
        88,
        ["productivity", "pwa", "focus"],
        "productivity",
        "A distraction-free task organizer featuring focus timers, minimalist note pads, calendar integration, and a highly customizable theme manager.",
    ),
    (
        "North Inbox",
        "A team inbox in monochrome",
        "Productivity",
        89,
        "React",
        90,
        ["inbox", "team", "productivity"],
        "productivity",
        "A clean team inbox tool designed to group client messages from email, SMS, and WhatsApp into one unified visual surface without the bloated clutter.",
    ),

    # Auth
    (
        "Foundry Auth",
        "Auth that disappears",
        "Auth",
        69,
        "Next.js",
        86,
        ["auth", "oauth", "security"],
        "auth",
        "Self-contained login gate with support for social OAuth providers, email magic links, passkeys, and built-in user invitation managers.",
    ),
    (
        "Keykeep",
        "Multi-tenant authorization proxy",
        "Auth",
        129,
        "Go",
        89,
        ["auth", "security", "rbac"],
        "auth",
        "A lightweight auth middleware component running side-car style to enforce role-based access rules on existing microservices instantly.",
    ),

    # Enterprise
    (
        "Maison ERP",
        "A full enterprise resource platform",
        "Enterprise",
        18500,
        "Next.js",
        97,
        ["enterprise", "erp", "full-app"],
        "enterprise",
        "An enterprise portal designed to connect inventory management, purchase orders, client invoicing, and human resources under a single deployment.",
    ),
    (
        "Aegis Governance",
        "Compliance and audit log engine",
        "Enterprise",
        15000,
        "Next.js",
        95,
        ["enterprise", "compliance", "audit"],
        "enterprise",
        "A regulatory dashboard designed to track compliance across team permissions, system event logging, security audits, and key rotations.",
    ),

    # Healthcare
    (
        "Vitrine Telehealth",
        "HIPAA-aware telehealth platform",
        "Healthcare",
        32000,
        "Next.js",
        95,
        ["healthcare", "enterprise", "telehealth"],
        "healthcare",
        "A telehealth application offering video consultations, patient scheduling portals, prescription tracking, and full compliance auditing reports.",
    ),
    (
        "CardioSync",
        "Patient vitals monitoring client",
        "Healthcare",
        18000,
        "React",
        93,
        ["healthcare", "vitals", "iot"],
        "healthcare",
        "Dashboard connecting to cardiac IoT devices. Displays real-time ECG readings, records event logs, and alerts healthcare staff to custom trigger conditions.",
    ),
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

        for name, tagline, cat, price, fw, score, tags, cover_key, desc in DEMO_LISTINGS:
            cover_url = COVERS.get(cover_key, COVER)
            listing = Listing(
                owner_id=maker.id, name=name, slug=slugify(name), tagline=tagline,
                category=cat, tags=tags, framework=fw, price_cents=price * 100,
                license="MIT", status="live", demo_url="https://vercel.com",
                demo_health="live", vitrine_score=score, cover=cover_url, screenshots=[cover_url] + SHOTS,
                badges=["verified", "live-demo", "best-ui"],
                description=desc,
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

            # Generate and add listing embedding
            embedding = await client.embed(f"{name} {tagline} {cat} {' '.join(tags)}")
            db.add(ListingEmbedding(listing_id=listing.id, embedding=embedding))

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

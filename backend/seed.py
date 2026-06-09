"""
Seed demo data so the storefront + dashboards aren't empty.

    python -m backend.seed        (or: python backend/seed.py)

Creates tables, then seeds v2 demo data (idempotent via seed_version flag).
Mirrors frontend mock IDs where possible.

Demo logins (password = email local-part):
  admin@vitrine.io   / admin
  june@vitrine.io    / june      (buyer)
  marco@vitrine.io   / marco     (buyer)
  sana@vitrine.io    / sana      (buyer)
  maker@vitrine.io   / maker     (seller — Atelier Foxglove)
  dev@vitrine.io     / dev       (seller — Studio Korr)
  studio@vitrine.io  / studio    (seller — Studio Vellum)
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import random
import asyncio


from backend.shared.db import SessionLocal, create_all, drop_all
from backend.shared.ids import slugify
from backend.shared.models import (
    AdminConfig,
    Chat,
    ChatMessage,
    Listing,
    ListingEmbedding,
    ListingField,
    ListingTier,
    Negotiation,
    User,
    AnalyticEvent,
    Order,
)
from backend.shared.security import hash_password
from backend.ai.client import client

SEED_VERSION = "7"
DEMO_URL = "https://nextgram.vercel.app"

COVER = "https://images.unsplash.com/photo-1551288049-bebda4e38f71?auto=format&fit=crop&w=1600&q=80"
SHOTS = [
    COVER,
    "https://images.unsplash.com/photo-1460925895917-afdab827c52f?auto=format&fit=crop&w=1600&q=80",
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

# (name, tagline, category, price, framework, score, tags, cover_key, description, seller_key)
# seller_key: "foxglove" | "korr" | "vellum"
LISTINGS = [
    # ── Atelier Foxglove (maker) ──────────────────────────────────────────
    ("Halcyon", "A quiet operations cockpit", "Dashboards", 89, "Next.js", 96,
     ["saas", "admin", "charts"], "dashboard",
     "A quiet operations cockpit for early-stage startup operators.", "foxglove"),
    ("Cantata Dash", "Charts as composition", "Dashboards", 119, "Vue", 93,
     ["dashboard", "vue", "charts"], "dashboard",
     "Modular dashboard for audio-processing workflows and music metadata.", "foxglove"),
    ("Foxglove Analytics", "Editorial analytics for serious teams", "Analytics", 129, "React", 94,
     ["analytics", "charts", "b2b"], "analytics",
     "Privacy-first, self-hostable analytics designed for creators.", "foxglove"),
    ("Plumb Line", "Deep-nested funnel analytics", "Analytics", 149, "Svelte", 91,
     ["analytics", "funnels", "saas"], "analytics",
     "Specialized analytics for nested user conversions and checkout tunnels.", "foxglove"),
    ("Lumen Commerce", "Headless storefront with taste", "E-commerce", 149, "Next.js", 92,
     ["commerce", "stripe", "headless"], "ecommerce",
     "Gorgeous storefront on Stripe and Shopify APIs with fluid animations.", "foxglove"),
    ("Maisonette", "Boutique digital goods checkout", "E-commerce", 79, "Remix", 90,
     ["commerce", "checkout", "digital"], "ecommerce",
     "Minimal checkout for authors and developers selling digital downloads.", "foxglove"),
    ("Atrium AI", "A chat surface that respects you", "AI", 79, "React", 95,
     ["ai", "chat", "sse"], "ai",
     "Modular LLM chat interface with Markdown, LaTeX, and streaming.", "foxglove"),
    ("Hermes Vector", "Semantic search pipeline in a box", "AI", 159, "Next.js", 93,
     ["ai", "vector", "search"], "ai",
     "Ready-to-run search wrapper with a clean web GUI for semantic queries.", "foxglove"),
    ("Pulse Board", "Realtime ops metrics wall", "Dashboards", 109, "React", 92,
     ["dashboard", "realtime", "metrics"], "dashboard",
     "Wall-mounted ops display with WebSocket feeds and alert thresholds.", "foxglove"),
    ("Drift Commerce", "Subscription storefront kit", "E-commerce", 169, "Next.js", 91,
     ["commerce", "subscriptions", "stripe"], "ecommerce",
     "Stripe Billing integration with proration, trials, and customer portal.", "foxglove"),
    ("Ledger Field", "Finance dashboards, restrained", "Finance", 199, "React", 91,
     ["finance", "charts", "ledger"], "finance",
     "Double-entry bookkeeping frontend with keyboard shortcut navigation.", "foxglove"),

    # ── Studio Korr (dev) ─────────────────────────────────────────────────
    ("Korr CRM", "A CRM you actually open on Mondays", "CRM", 99, "Remix", 90,
     ["crm", "pipeline", "sales"], "crm",
     "Visual kanban pipeline with keyboard-focused notes and follow-ups.", "korr"),
    ("Apex Contact", "High-velocity sales pipeline", "CRM", 149, "React", 89,
     ["crm", "sales", "contacts"], "crm",
     "Contact management for small teams with Google Contacts sync.", "korr"),
    ("Margins", "A writing-first CMS", "CMS", 59, "Astro", 89,
     ["cms", "markdown", "mdx"], "cms",
     "Light publishing engine focused on MDX and typographic layouts.", "korr"),
    ("Vellum Press", "Headless publishing engine", "CMS", 89, "Next.js", 91,
     ["cms", "publishing", "headless"], "cms",
     "Headless CMS with media organizer and version control history.", "korr"),
    ("Quiet Hours", "Personal productivity, distilled", "Productivity", 39, "React", 88,
     ["productivity", "pwa", "focus"], "productivity",
     "Distraction-free task organizer with focus timers and theme manager.", "korr"),
    ("North Inbox", "A team inbox in monochrome", "Productivity", 89, "React", 90,
     ["inbox", "team", "productivity"], "productivity",
     "Unified inbox for email, SMS, and WhatsApp without the clutter.", "korr"),
    ("Foundry Auth", "Auth that disappears", "Auth", 69, "Next.js", 86,
     ["auth", "oauth", "security"], "auth",
     "Self-contained login gate with OAuth, magic links, and passkeys.", "korr"),
    ("Keykeep", "Multi-tenant authorization proxy", "Auth", 129, "Go", 89,
     ["auth", "security", "rbac"], "auth",
     "Lightweight auth middleware for role-based access on microservices.", "korr"),
    ("Signal CRM", "Outbound sales sequencer", "CRM", 129, "Next.js", 90,
     ["crm", "outbound", "sequences"], "crm",
     "Email sequences, LinkedIn touchpoints, and pipeline scoring in one app.", "korr"),
    ("Nimbus CMS", "Multilingual content hub", "CMS", 119, "Next.js", 92,
     ["cms", "i18n", "headless"], "cms",
     "Headless CMS with locale fallbacks, translation workflows, and webhooks.", "korr"),
    ("Compass Trading Desk", "Production-grade trading desk", "Finance", 24900, "React", 96,
     ["finance", "trading", "enterprise"], "finance",
     "Canvas-based charting, order execution, and multi-exchange API sync.", "korr"),
    ("Vitrine Telehealth", "HIPAA-aware telehealth platform", "Healthcare", 32000, "Next.js", 95,
     ["healthcare", "enterprise", "telehealth"], "healthcare",
     "Video consultations, scheduling, and compliance auditing reports.", "korr"),

    # ── Studio Vellum (studio) ────────────────────────────────────────────────
    ("Maison ERP", "A full enterprise resource platform", "Enterprise", 18500, "Next.js", 97,
     ["enterprise", "erp", "full-app"], "enterprise",
     "Complete ERP codebase — inventory, HR, finance, and procurement in one branded surface.", "vellum"),
    ("Meridian Suite", "Enterprise workflow orchestration", "Enterprise", 12000, "React", 94,
     ["enterprise", "workflow", "saas"], "enterprise",
     "Multi-tenant workflow engine with role hierarchies, audit trails, and SSO integration.", "vellum"),
    ("Solace Health", "Patient engagement and care coordination", "Healthcare", 499, "React", 93,
     ["healthcare", "patient", "portal"], "healthcare",
     "Patient portal with appointment booking, messaging, and document upload — HIPAA-aware.", "vellum"),
    ("Epoch Analytics", "Long-horizon trend analytics", "Analytics", 169, "Next.js", 92,
     ["analytics", "trends", "time-series"], "analytics",
     "Time-series analytics dashboard with anomaly detection and exportable PDF reports.", "vellum"),
    ("Tableau Fin", "Portfolio and wealth tracking", "Finance", 229, "React", 91,
     ["finance", "portfolio", "wealth"], "finance",
     "Personal and family wealth tracker with multi-currency support and allocation charts.", "vellum"),
    ("Arcade CRM", "Lightweight CRM for indie consultants", "CRM", 59, "Svelte", 88,
     ["crm", "consulting", "solo"], "crm",
     "Minimal CRM built for solo consultants — contacts, notes, and follow-up reminders.", "vellum"),
    ("Prism Storefront", "Design-led commerce for creative studios", "E-commerce", 189, "Next.js", 93,
     ["commerce", "creative", "portfolio"], "ecommerce",
     "Portfolio-forward product pages with a fluid, magazine-style checkout flow.", "vellum"),
    ("Fieldnotes CMS", "Structured content for research teams", "CMS", 99, "Astro", 90,
     ["cms", "research", "structured"], "cms",
     "CMS built around typed content schemas, citation management, and offline drafting.", "vellum"),
    ("Coda Auth", "Zero-config passkey authentication", "Auth", 89, "Next.js", 91,
     ["auth", "passkey", "webauthn"], "auth",
     "Drop-in passkey and biometric auth layer with session management and device registry.", "vellum"),
    ("Canvas Dash", "Visual project status board", "Dashboards", 99, "React", 91,
     ["dashboard", "projects", "kanban"], "dashboard",
     "Drag-and-drop project dashboard with milestone tracking and team velocity charts.", "vellum"),
    ("Bloom Tasks", "Collaborative task management, refined", "Productivity", 49, "Svelte", 89,
     ["productivity", "tasks", "collaboration"], "productivity",
     "Team task manager with threaded comments, priority lanes, and calendar sync.", "vellum"),
    ("Orbit AI", "Embedded AI assistant framework", "AI", 199, "Next.js", 94,
     ["ai", "assistant", "embeddings"], "ai",
     "Plug-in AI assistant layer for existing apps — context injection, RAG, and tool calling.", "vellum"),
]

DEFAULT_CONFIG = {
    "system_prompts": {
        "concierge": "You are Vitrine's Concierge. Help buyers find the right software piece.",
        "buyerRep": "You are a buyer's negotiating rep. Warm but firm. Never exceed the budget.",
        "pricingAgent": "You are Vitrine's Pricing & Pitch agent. Auto-quote custom-feature requests.",
        "verification": "You are Vitrine's Verification agent. Flag, do not auto-approve, anything > $5,000.",
    },
    "flags": {
        "aiBargain": True, "conciergeSearch": True, "enterpriseTier": True,
        "studentDiscount": True, "newSignupsOpen": True,
    },
    "fees": {
        "commissionFree": 12, "commissionStudio": 8, "commissionAtelier": 5,
        "commissionMaison": 3, "enterprise": 2, "processing": 2.5,
    },
    "escrow": {"holdHours": 48, "refundWindow": 7, "autoRelease": True},
    "branding": {
        "headline": "Software, but make it editorial.",
        "tagline": "A boutique marketplace for live, runnable software.",
        "supportEmail": "curator@vitrine.io",
    },
    "notes": "",
    "api_keys": [],
    "featured_ids": [],
}


async def _add_listing(db, owner_id: str, spec: tuple) -> Listing:
    name, tagline, cat, price, fw, score, tags, cover_key, desc, _seller = spec
    cover_url = COVERS.get(cover_key, COVER)
    expires = datetime.now(timezone.utc) + timedelta(days=30)
    if name == "Quiet Hours":
        expires = datetime.now(timezone.utc) - timedelta(days=5)
    listing = Listing(
        owner_id=owner_id, name=name, slug=slugify(name), tagline=tagline,
        category=cat, tags=tags, framework=fw, price_cents=price * 100,
        license="MIT", status="live", demo_url=DEMO_URL,
        demo_health="live", vitrine_score=score, cover=cover_url,
        expires_at=expires,
        screenshots=[cover_url] + SHOTS,
        badges=["verified", "live-demo"] + (["best-ui"] if score >= 93 else []),
        description=desc,
        rating=round(4.2 + (score % 8) / 10, 1),
        reviews_count=24 + (score % 50),
        rating_distribution=[56, 28, 10, 4, 2],  # 5★→1★ (matches ProductPage[5-star])
        score_breakdown=[
            {"label": "Completeness", "value": 90},
            {"label": "UI craft", "value": score - 2},
            {"label": "Demo health", "value": 94},
        ],
        sdlc={
            "problem": f"Teams stitch together five tools for {cat.lower()} work.",
            "solution": "A focused codebase shipping the 80% you actually use.",
            "methodology": "Designed in the open; built in two-week cycles.",
            "discussions": "How opinionated should the data layer remain?",
        },
        business_model={
            "kind": "for-profit",
            "pitch": "A commercial codebase you can rebrand and bill against.",
            "revenueStreams": ["Source license sales", "Bespoke commissions"],
        },
        tech_stack=[fw, "TypeScript", "Tailwind CSS", "PostgreSQL"],
    )
    db.add(listing)
    await db.flush()

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
    return listing


async def _add_chat(
    db,
    *,
    buyer: User,
    seller: User,
    listing: Listing,
    is_agent: bool = False,
    budget_dollars: int | None = None,
    messages: list[tuple[str, str, str, bool]],
) -> Chat:
    """messages: (sender_id, sender_name, text, is_agent_rep)"""
    chat = Chat(
        buyer_id=buyer.id, seller_id=seller.id, listing_id=listing.id,
        is_agent=is_agent,
        agent_budget_cents=int(budget_dollars * 100) if budget_dollars else None,
        status="open",
        unread_for=["seller"] if messages and messages[-1][0] == buyer.id else ["buyer"],
    )
    db.add(chat)
    await db.flush()

    if is_agent and budget_dollars:
        db.add(Negotiation(
            chat_id=chat.id, buyer_id=buyer.id, status="active",
            budget_cents=budget_dollars * 100,
            buyer_readme_context="Internal admin dashboard for a 12-person startup. Needs SSO within 30 days.",
        ))

    for sender_id, sender_name, text, is_rep in messages:
        db.add(ChatMessage(
            chat_id=chat.id, sender_id=sender_id, sender_name=sender_name,
            text=text, is_agent_rep=is_rep,
        ))
    return chat


async def seed() -> None:
    await create_all()
    async with SessionLocal() as db:
        version_row = await db.get(AdminConfig, "seed_version")
        if version_row and version_row.value == SEED_VERSION:
            print(f"[seed] already at v{SEED_VERSION} — skipping.")
            return

    print(f"[seed] (re)building database to v{SEED_VERSION}…")
    await drop_all()
    await create_all()

    async with SessionLocal() as db:
        admin = User(
            email="admin@vitrine.io", password_hash=hash_password("admin"),
            role="admin", display_name="Vitrine Curator",
        )
        buyer_june = User(
            email="june@vitrine.io", password_hash=hash_password("june"),
            role="buyer", display_name="June Park",
        )
        buyer_marco = User(
            email="marco@vitrine.io", password_hash=hash_password("marco"),
            role="buyer", display_name="Marco Rivers",
        )
        seller_foxglove = User(
            email="maker@vitrine.io", password_hash=hash_password("maker"),
            role="seller", display_name="Atelier Foxglove", handle="@foxglove",
            verified=True, plan="studio",
        )
        seller_korr = User(
            email="dev@vitrine.io", password_hash=hash_password("dev"),
            role="seller", display_name="Studio Korr", handle="@korr",
            verified=True, plan="atelier",
        )
        seller_vellum = User(
            email="studio@vitrine.io", password_hash=hash_password("studio"),
            role="seller", display_name="Studio Vellum", handle="@vellum",
            verified=True, plan="maison",
        )
        buyer_sana = User(
            email="sana@vitrine.io", password_hash=hash_password("sana"),
            role="buyer", display_name="Sana Iqbal",
        )
        db.add_all([admin, buyer_june, buyer_marco, buyer_sana, seller_foxglove, seller_korr, seller_vellum])
        await db.flush()

        sellers = {"foxglove": seller_foxglove, "korr": seller_korr, "vellum": seller_vellum}
        listing_by_name: dict[str, Listing] = {}
        for spec in LISTINGS:
            owner = sellers[spec[-1]]
            listing = await _add_listing(db, owner.id, spec)
            listing_by_name[listing.name] = listing

        halcyon = listing_by_name["Halcyon"]
        atrium = listing_by_name["Atrium AI"]
        korr_crm = listing_by_name["Korr CRM"]
        lumen = listing_by_name["Lumen Commerce"]
        signal_crm = listing_by_name["Signal CRM"]

        # June ↔ Foxglove on Halcyon (AI rep negotiation)
        await _add_chat(
            db, buyer=buyer_june, seller=seller_foxglove, listing=halcyon,
            is_agent=True, budget_dollars=79,
            messages=[
                ("agent", "June Park's AI Rep",
                 "Hi — I represent June Park. She loves Halcyon and is ready to buy the Source tier today. "
                 "Could you do $79 instead of $89 for a same-day commit? She'd leave a verified review.", True),
                (seller_foxglove.id, seller_foxglove.display_name,
                 "Appreciate the directness. $79 works if she takes Source + Setup at listed price next month.", False),
                ("agent", "June Park's AI Rep",
                 "Noted. June can commit to Source today at $79 and schedule Source + Setup for next quarter. "
                 "Does that work for a signed agreement this week?", True),
            ],
        )

        # Marco ↔ Korr on Korr CRM (direct buyer question)
        await _add_chat(
            db, buyer=buyer_marco, seller=seller_korr, listing=korr_crm,
            messages=[
                (buyer_marco.id, buyer_marco.display_name,
                 "Hey — does Korr CRM support custom pipeline stages out of the box, or is that a fork?", False),
                (seller_korr.id, seller_korr.display_name,
                 "Custom stages are built-in — you define them in settings. No fork needed. "
                 "Happy to hop on a 15-min walkthrough if useful.", False),
            ],
        )

        # Marco ↔ Foxglove on Atrium AI (feature scoping)
        await _add_chat(
            db, buyer=buyer_marco, seller=seller_foxglove, listing=atrium,
            messages=[
                (buyer_marco.id, buyer_marco.display_name,
                 "We're evaluating Atrium for an internal copilot. Does the SSE layer handle tool-calling loops?", False),
                (seller_foxglove.id, seller_foxglove.display_name,
                 "Yes — the streaming handler supports multi-turn tool calls with a 5-step cap. "
                 "I can share the architecture doc if you'd like.", False),
                (buyer_marco.id, buyer_marco.display_name,
                 "That would be great. Also curious about rate-limit hooks for our API gateway.", False),
            ],
        )

        # June ↔ Korr on Lumen Commerce (AI rep, higher budget)
        await _add_chat(
            db, buyer=buyer_june, seller=seller_korr, listing=lumen,
            is_agent=True, budget_dollars=130,
            messages=[
                ("agent", "June Park's AI Rep",
                 "June is building a headless storefront for a design studio. She's authorized up to $130 "
                 "for Lumen Commerce Source + white-label reskin. Can we close at $125 with a case study?", True),
                (seller_korr.id, seller_korr.display_name,
                 "$125 for Source + reskin is tight but doable if she provides logo assets and copy by Friday.", False),
            ],
        )

        # June ↔ Korr on Signal CRM (closed thread — settled)
        settled = await _add_chat(
            db, buyer=buyer_june, seller=seller_korr, listing=signal_crm,
            messages=[
                (buyer_june.id, buyer_june.display_name,
                 "Is Signal CRM a good fit for a 3-person outbound team?", False),
                (seller_korr.id, seller_korr.display_name,
                 "Absolutely — it's built for small outbound teams. Sequences + pipeline in one surface.", False),
                (buyer_june.id, buyer_june.display_name,
                 "Sold. I'll take Source + Setup at $209.", False),
            ],
        )
        settled.status = "settled"
        settled.unread_for = []

        # Seed Analytic Events for the last 14 days
        today = datetime.now(timezone.utc)
        
        # We will add events for the last 14 days
        for day_offset in range(14):
            day_time = today - timedelta(days=day_offset)
            
            # Seed some general site-wide views (listing_id is None)
            num_general_views = random.randint(100, 200)
            for _ in range(num_general_views):
                event_time = day_time.replace(
                    hour=random.randint(0, 23),
                    minute=random.randint(0, 59),
                    second=random.randint(0, 59)
                )
                db.add(AnalyticEvent(
                    listing_id=None,
                    event_type="view",
                    created_at=event_time
                ))
            
            # Seed views/launches for each listing
            for listing in listing_by_name.values():
                popularity_factor = (hash(listing.name) % 3) + 1
                num_views = random.randint(5, 20) * popularity_factor
                num_launches = random.randint(0, int(num_views * 0.15))
                
                for _ in range(num_views):
                    event_time = day_time.replace(
                        hour=random.randint(0, 23),
                        minute=random.randint(0, 59),
                        second=random.randint(0, 59)
                    )
                    db.add(AnalyticEvent(
                        listing_id=listing.id,
                        event_type="view",
                        created_at=event_time
                    ))
                for _ in range(num_launches):
                    event_time = day_time.replace(
                        hour=random.randint(0, 23),
                        minute=random.randint(0, 59),
                        second=random.randint(0, 59)
                    )
                    db.add(AnalyticEvent(
                        listing_id=listing.id,
                        event_type="launch",
                        created_at=event_time
                    ))

        # Seed some paid orders to represent realistic earnings
        orders_to_create = [
            (buyer_june, halcyon, 89),
            (buyer_marco, atrium, 79),
            (buyer_sana, lumen, 149),
            (buyer_june, listing_by_name["Foxglove Analytics"], 129),
            (buyer_marco, listing_by_name["Plumb Line"], 149),
            (buyer_sana, listing_by_name["Cantata Dash"], 119),
            
            # Dev / Studio Korr listings
            (buyer_june, korr_crm, 99),
            (buyer_marco, signal_crm, 129),
            
            # Studio Vellum listings
            (buyer_sana, listing_by_name["Maison ERP"], 18500),
        ]
        
        for buyer, listing, price_dollars in orders_to_create:
            gross = price_dollars * 100
            rate = 0.12 # default
            seller_user = next((s for s in sellers.values() if s.id == listing.owner_id), None)
            if seller_user:
                if seller_user.plan == "studio":
                    rate = 0.08
                elif seller_user.plan == "atelier":
                    rate = 0.05
                elif seller_user.plan == "maison":
                    rate = 0.03
            commission = int(gross * rate)
            
            db.add(Order(
                buyer_id=buyer.id,
                listing_id=listing.id,
                seller_id=listing.owner_id,
                tier_name="Source",
                amount_cents=gross,
                commission_cents=commission,
                kind="purchase",
                status="paid",
                escrow_status="released",
                provider="mock",
                created_at=today - timedelta(days=random.randint(1, 10))
            ))

        featured_listings = [
            listing_by_name["Maison ERP"].id,
            listing_by_name["Atrium AI"].id,
            listing_by_name["Halcyon"].id,
        ]

        for key, value in DEFAULT_CONFIG.items():
            if key == "featured_ids":
                db.add(AdminConfig(key=key, value=featured_listings))
            else:
                db.add(AdminConfig(key=key, value=value))
        db.add(AdminConfig(key="seed_version", value=SEED_VERSION))

        await db.commit()

        foxglove_count = sum(1 for s in LISTINGS if s[-1] == "foxglove")
        korr_count = sum(1 for s in LISTINGS if s[-1] == "korr")
        vellum_count = sum(1 for s in LISTINGS if s[-1] == "vellum")
        total_count = foxglove_count + korr_count + vellum_count
        print(
            f"[seed] v{SEED_VERSION}: 1 admin, 3 buyers, 3 sellers, "
            f"{total_count} listings "
            f"({foxglove_count} Foxglove / {korr_count} Korr / {vellum_count} Vellum), "
            f"5 chat threads."
        )
        print("[seed] logins:")
        print("  admin@vitrine.io  / admin")
        print("  june@vitrine.io   / june    (buyer)")
        print("  marco@vitrine.io  / marco   (buyer)")
        print("  sana@vitrine.io   / sana    (buyer)")
        print("  maker@vitrine.io  / maker   (seller — Atelier Foxglove)")
        print("  dev@vitrine.io    / dev     (seller — Studio Korr)")
        print("  studio@vitrine.io / studio  (seller — Studio Vellum)")


if __name__ == "__main__":
    asyncio.run(seed())

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
from backend.shared.plans import split_sale
from backend.shared.security import hash_password
from backend.ai.client import client

SEED_VERSION = "9"
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
# The catalog now spans more kinds of software than it has distinct cover
# photographs. Rather than invent Unsplash IDs that 404 in the gallery, the new
# kinds alias onto the images above — swap in real art per key when there is any.
COVERS.update({
    "mobile": COVERS["productivity"],
    "devtools": COVERS["enterprise"],
    "games": COVERS["ai"],
    "design": COVERS["cms"],
    "dataml": COVERS["analytics"],
    "desktop": COVERS["dashboard"],
    "extension": COVERS["auth"],
    "infra": COVERS["enterprise"],
    "education": COVERS["cms"],
    "iot": COVERS["finance"],
})

# Catalogue taxonomy. Seeded into admin config so the storefront's category and
# framework filters actually list what the gallery contains.
CATEGORIES = [
    "Dashboards", "Analytics", "E-commerce", "AI", "Finance", "CRM", "CMS",
    "Productivity", "Auth", "Enterprise", "Healthcare", "Mobile",
    "Developer Tools", "Infrastructure", "Data & ML", "Desktop",
    "Browser Extensions", "Design Systems", "Games", "Education",
    "IoT & Hardware",
]
FRAMEWORKS = [
    "Next.js", "React", "Vue", "Svelte", "Remix", "Astro", "Go", "Rust",
    "Python", "React Native", "Flutter", "Electron", "Tauri", "Godot",
    "FastAPI", "Node.js", "SwiftUI", "Kotlin", "Django", "Laravel",
]

def L(name, tagline, category, price, framework, score, tags, cover, description,
      seller, repo, *, demo=DEMO_URL, license="MIT", stack=None, model="for-profit"):
    """One catalogue entry.

    `demo=None` means the piece genuinely has no hosted preview — a CLI, a
    firmware image, a mobile binary. That flows through to `hasLiveDemo` and the
    "Live demo" facet, so the gallery stops promising a demo that cannot exist.
    """
    return {
        "name": name, "tagline": tagline, "category": category, "price": price,
        "framework": framework, "score": score, "tags": tags, "cover": cover,
        "description": description, "seller": seller, "repo": repo, "demo": demo,
        "license": license, "model": model,
        "stack": stack or [framework, "TypeScript", "Tailwind CSS", "PostgreSQL"],
    }


GH = "https://github.com"

# seller: "foxglove" | "korr" | "vellum"
LISTINGS = [
    # ── Atelier Foxglove — web craft, interface-led ───────────────────────
    L("Halcyon", "A quiet operations cockpit", "Dashboards", 89, "Next.js", 96,
      ["saas", "admin", "charts"], "dashboard",
      "A quiet operations cockpit for early-stage startup operators.",
      "foxglove", f"{GH}/atelier-foxglove/halcyon"),
    L("Cantata Dash", "Charts as composition", "Dashboards", 119, "Vue", 93,
      ["dashboard", "vue", "charts"], "dashboard",
      "Modular dashboard for audio-processing workflows and music metadata.",
      "foxglove", f"{GH}/atelier-foxglove/cantata-dash",
      stack=["Vue 3", "Pinia", "D3", "Web Audio API"]),
    L("Foxglove Analytics", "Editorial analytics for serious teams", "Analytics", 129, "React", 94,
      ["analytics", "charts", "b2b"], "analytics",
      "Privacy-first, self-hostable analytics designed for creators.",
      "foxglove", f"{GH}/atelier-foxglove/foxglove-analytics", license="AGPL-3.0",
      stack=["React", "ClickHouse", "Fastify", "Docker"]),
    L("Plumb Line", "Deep-nested funnel analytics", "Analytics", 149, "Svelte", 91,
      ["analytics", "funnels", "saas"], "analytics",
      "Specialized analytics for nested user conversions and checkout tunnels.",
      "foxglove", f"{GH}/atelier-foxglove/plumb-line"),
    L("Lumen Commerce", "Headless storefront with taste", "E-commerce", 149, "Next.js", 92,
      ["commerce", "stripe", "headless"], "ecommerce",
      "Gorgeous storefront on Stripe and Shopify APIs with fluid animations.",
      "foxglove", f"{GH}/atelier-foxglove/lumen-commerce"),
    L("Maisonette", "Boutique digital goods checkout", "E-commerce", 79, "Remix", 90,
      ["commerce", "checkout", "digital"], "ecommerce",
      "Minimal checkout for authors and developers selling digital downloads.",
      "foxglove", f"{GH}/atelier-foxglove/maisonette"),
    L("Atrium AI", "A chat surface that respects you", "AI", 79, "React", 95,
      ["ai", "chat", "sse"], "ai",
      "Modular LLM chat interface with Markdown, LaTeX, and streaming.",
      "foxglove", f"{GH}/atelier-foxglove/atrium-ai",
      stack=["React", "Vercel AI SDK", "KaTeX", "Tailwind CSS"]),
    L("Bezel", "A component library with a spine", "Design Systems", 149, "React", 94,
      ["design-system", "components", "tokens"], "design",
      "Forty-two accessible React primitives, design tokens, and a Storybook that doubles as the docs site.",
      "foxglove", f"{GH}/atelier-foxglove/bezel", license="Apache-2.0",
      stack=["React", "Radix UI", "Storybook", "Style Dictionary"]),
    L("Inkwell", "Read-it-later, in the toolbar", "Browser Extensions", 29, "TypeScript", 89,
      ["extension", "chrome", "firefox"], "extension",
      "Manifest V3 extension that clips articles to clean Markdown and syncs to Obsidian, Notion, or a local folder.",
      "foxglove", f"{GH}/atelier-foxglove/inkwell", demo=None, license="MIT",
      stack=["TypeScript", "WebExtensions API", "Vite", "Turndown"],
      model="open-source"),
    L("Pocket Ledger", "Expense tracking that survives offline", "Mobile", 119, "React Native", 91,
      ["mobile", "ios", "android", "offline"], "mobile",
      "Cross-platform expense tracker with an offline-first sync engine, receipt OCR, and CSV export.",
      "foxglove", f"{GH}/atelier-foxglove/pocket-ledger", demo=None,
      stack=["React Native", "Expo", "WatermelonDB", "Tesseract.js"]),

    # ── Studio Korr — systems, tooling, and heavier builds ────────────────
    L("Korr CRM", "A CRM you actually open on Mondays", "CRM", 99, "Remix", 90,
      ["crm", "pipeline", "sales"], "crm",
      "Visual kanban pipeline with keyboard-focused notes and follow-ups.",
      "korr", f"{GH}/studio-korr/korr-crm"),
    L("Signal CRM", "Outbound sales sequencer", "CRM", 129, "Next.js", 90,
      ["crm", "outbound", "sequences"], "crm",
      "Email sequences, LinkedIn touchpoints, and pipeline scoring in one app.",
      "korr", f"{GH}/studio-korr/signal-crm"),
    L("Margins", "A writing-first CMS", "CMS", 59, "Astro", 89,
      ["cms", "markdown", "mdx"], "cms",
      "Light publishing engine focused on MDX and typographic layouts.",
      "korr", f"{GH}/studio-korr/margins", license="BSD-3-Clause",
      stack=["Astro", "MDX", "Shiki", "Satori"]),
    L("Nimbus CMS", "Multilingual content hub", "CMS", 119, "Next.js", 92,
      ["cms", "i18n", "headless"], "cms",
      "Headless CMS with locale fallbacks, translation workflows, and webhooks.",
      "korr", f"{GH}/studio-korr/nimbus-cms"),
    L("Quiet Hours", "Personal productivity, distilled", "Productivity", 39, "React", 88,
      ["productivity", "pwa", "focus"], "productivity",
      "Distraction-free task organizer with focus timers and theme manager.",
      "korr", f"{GH}/studio-korr/quiet-hours"),
    L("Foundry Auth", "Auth that disappears", "Auth", 69, "Next.js", 86,
      ["auth", "oauth", "security"], "auth",
      "Self-contained login gate with OAuth, magic links, and passkeys.",
      "korr", f"{GH}/studio-korr/foundry-auth"),
    L("Keykeep", "Multi-tenant authorization proxy", "Auth", 129, "Go", 89,
      ["auth", "security", "rbac"], "auth",
      "Lightweight auth middleware for role-based access on microservices.",
      "korr", f"{GH}/studio-korr/keykeep", license="Apache-2.0",
      stack=["Go", "Envoy", "OPA", "Redis"]),
    L("Compass Trading Desk", "Production-grade trading desk", "Finance", 24900, "React", 96,
      ["finance", "trading", "enterprise"], "finance",
      "Canvas-based charting, order execution, and multi-exchange API sync.",
      "korr", f"{GH}/studio-korr/compass-desk", license="Proprietary",
      stack=["React", "Rust", "WebSocket", "TimescaleDB"]),
    L("Vitrine Telehealth", "HIPAA-aware telehealth platform", "Healthcare", 32000, "Next.js", 95,
      ["healthcare", "enterprise", "telehealth"], "healthcare",
      "Video consultations, scheduling, and compliance auditing reports.",
      "korr", f"{GH}/studio-korr/telehealth", license="Proprietary"),
    L("Hermes Vector", "Semantic search pipeline in a box", "AI", 159, "Python", 93,
      ["ai", "vector", "search", "rag"], "ai",
      "Ingest, chunk, embed, and serve. A batteries-included RAG service with a FastAPI surface and a pgvector store.",
      "korr", f"{GH}/studio-korr/hermes-vector",
      stack=["Python", "FastAPI", "pgvector", "LangChain"]),
    L("Tessera", "Scaffold a service in one command", "Developer Tools", 49, "Rust", 92,
      ["cli", "scaffolding", "templates"], "devtools",
      "A fast project generator with composable templates, post-generate hooks, and no runtime dependency.",
      "korr", f"{GH}/studio-korr/tessera", demo=None, license="MIT",
      stack=["Rust", "clap", "Tera", "cargo-dist"], model="open-source"),
    L("Driftwood", "Database migrations without ceremony", "Developer Tools", 79, "Go", 90,
      ["cli", "migrations", "postgres"], "devtools",
      "Single-binary migration runner with dry-run diffs, advisory locking, and CI-friendly exit codes.",
      "korr", f"{GH}/studio-korr/driftwood", demo=None, license="Apache-2.0",
      stack=["Go", "PostgreSQL", "MySQL", "GitHub Actions"]),
    L("Switchyard", "Webhook routing and replay", "Infrastructure", 139, "Go", 91,
      ["webhooks", "queue", "self-hosted"], "infra",
      "Receive, verify, fan out, and replay webhooks with signature validation and an exponential-backoff dead-letter queue.",
      "korr", f"{GH}/studio-korr/switchyard",
      stack=["Go", "NATS", "PostgreSQL", "Docker Compose"]),
    L("Beacon Status", "A status page your users trust", "Infrastructure", 69, "Svelte", 89,
      ["uptime", "monitoring", "status-page"], "infra",
      "Self-hosted uptime monitoring with incident timelines, subscriber notifications, and a public status page.",
      "korr", f"{GH}/studio-korr/beacon-status", license="MIT", model="open-source",
      stack=["SvelteKit", "SQLite", "Node.js", "Resend"]),
    L("Grainsight", "ELT pipelines you can read", "Data & ML", 189, "Python", 90,
      ["etl", "data", "airflow"], "dataml",
      "Declarative extract-load-transform pipelines with lineage tracking, column-level tests, and a lightweight scheduler.",
      "korr", f"{GH}/studio-korr/grainsight", demo=None,
      stack=["Python", "DuckDB", "dbt", "Prefect"]),
    L("Verso", "A Markdown editor that stays out of the way", "Desktop", 59, "Electron", 90,
      ["desktop", "markdown", "editor"], "desktop",
      "Cross-platform desktop editor with live preview, Zotero citations, Git-backed versioning, and Pandoc export.",
      "korr", f"{GH}/studio-korr/verso", demo=None, license="GPL-3.0",
      stack=["Electron", "CodeMirror 6", "Pandoc", "isomorphic-git"],
      model="open-source"),

    # ── Studio Vellum — enterprise breadth and specialised builds ─────────
    L("Maison ERP", "A full enterprise resource platform", "Enterprise", 18500, "Next.js", 97,
      ["enterprise", "erp", "full-app"], "enterprise",
      "Complete ERP codebase — inventory, HR, finance, and procurement in one branded surface.",
      "vellum", f"{GH}/studio-vellum/maison-erp", license="Proprietary"),
    L("Meridian Suite", "Enterprise workflow orchestration", "Enterprise", 12000, "React", 94,
      ["enterprise", "workflow", "saas"], "enterprise",
      "Multi-tenant workflow engine with role hierarchies, audit trails, and SSO integration.",
      "vellum", f"{GH}/studio-vellum/meridian", license="Proprietary"),
    L("Solace Health", "Patient engagement and care coordination", "Healthcare", 499, "React", 93,
      ["healthcare", "patient", "portal"], "healthcare",
      "Patient portal with appointment booking, messaging, and document upload — HIPAA-aware.",
      "vellum", f"{GH}/studio-vellum/solace-health"),
    L("Epoch Analytics", "Long-horizon trend analytics", "Analytics", 169, "Next.js", 92,
      ["analytics", "trends", "time-series"], "analytics",
      "Time-series analytics dashboard with anomaly detection and exportable PDF reports.",
      "vellum", f"{GH}/studio-vellum/epoch-analytics"),
    L("Tableau Fin", "Portfolio and wealth tracking", "Finance", 229, "React", 91,
      ["finance", "portfolio", "wealth"], "finance",
      "Personal and family wealth tracker with multi-currency support and allocation charts.",
      "vellum", f"{GH}/studio-vellum/tableau-fin"),
    L("Prism Storefront", "Design-led commerce for creative studios", "E-commerce", 189, "Next.js", 93,
      ["commerce", "creative", "portfolio"], "ecommerce",
      "Portfolio-forward product pages with a fluid, magazine-style checkout flow.",
      "vellum", f"{GH}/studio-vellum/prism-storefront"),
    L("Fieldnotes CMS", "Structured content for research teams", "CMS", 99, "Astro", 90,
      ["cms", "research", "structured"], "cms",
      "CMS built around typed content schemas, citation management, and offline drafting.",
      "vellum", f"{GH}/studio-vellum/fieldnotes"),
    L("Coda Auth", "Zero-config passkey authentication", "Auth", 89, "Next.js", 91,
      ["auth", "passkey", "webauthn"], "auth",
      "Drop-in passkey and biometric auth layer with session management and device registry.",
      "vellum", f"{GH}/studio-vellum/coda-auth"),
    L("Canvas Dash", "Visual project status board", "Dashboards", 99, "React", 91,
      ["dashboard", "projects", "kanban"], "dashboard",
      "Drag-and-drop project dashboard with milestone tracking and team velocity charts.",
      "vellum", f"{GH}/studio-vellum/canvas-dash"),
    L("Bloom Tasks", "Collaborative task management, refined", "Productivity", 49, "Svelte", 89,
      ["productivity", "tasks", "collaboration"], "productivity",
      "Team task manager with threaded comments, priority lanes, and calendar sync.",
      "vellum", f"{GH}/studio-vellum/bloom-tasks"),
    L("Orbit AI", "Embedded AI assistant framework", "AI", 199, "Next.js", 94,
      ["ai", "assistant", "embeddings"], "ai",
      "Plug-in AI assistant layer for existing apps — context injection, RAG, and tool calling.",
      "vellum", f"{GH}/studio-vellum/orbit-ai"),
    L("Cairn", "Trail tracking that works without signal", "Mobile", 89, "Flutter", 90,
      ["mobile", "gps", "maps", "offline"], "mobile",
      "Offline-first hiking companion — vector map tiles, GPX import and export, elevation profiles, and trip journals.",
      "vellum", f"{GH}/studio-vellum/cairn", demo=None,
      stack=["Flutter", "Dart", "MapLibre", "SQLite"]),
    L("Northwind Desk", "A support desk that lives on the desktop", "Desktop", 249, "Tauri", 92,
      ["desktop", "support", "tickets"], "desktop",
      "Native-feeling support console in a 12 MB bundle — ticket triage, canned replies, and a local full-text index.",
      "vellum", f"{GH}/studio-vellum/northwind-desk", demo=None,
      stack=["Tauri", "Rust", "SolidJS", "Tantivy"]),
    L("Tidepool", "Recommendations without the black box", "Data & ML", 349, "Python", 93,
      ["ml", "recsys", "notebooks"], "dataml",
      "Trained two-tower recommender with feature pipelines, an evaluation notebook suite, and a served inference API.",
      "vellum", f"{GH}/studio-vellum/tidepool", demo=None,
      stack=["Python", "PyTorch", "FastAPI", "MLflow"]),
    L("Foundry Arcade", "A 2D platformer, ready to reskin", "Games", 129, "Godot", 91,
      ["game", "2d", "platformer"], "games",
      "Complete Godot 4 platformer template — tilemap toolkit, save system, controller remapping, and eight sample levels.",
      "vellum", f"{GH}/studio-vellum/foundry-arcade", demo=None, license="MIT",
      stack=["Godot 4", "GDScript", "Aseprite", "FMOD"]),
    L("Lantern Learn", "Course delivery for small institutions", "Education", 299, "Django", 90,
      ["lms", "education", "courses"], "education",
      "Self-hosted LMS with cohort scheduling, graded assignments, SCORM import, and offline-capable student apps.",
      "vellum", f"{GH}/studio-vellum/lantern-learn", license="AGPL-3.0",
      stack=["Django", "PostgreSQL", "Celery", "HTMX"], model="non-profit"),
    L("Meadow", "Sensor mesh from firmware to chart", "IoT & Hardware", 279, "Rust", 89,
      ["iot", "firmware", "esp32", "mqtt"], "iot",
      "ESP32 firmware, an MQTT ingest service, and a provisioning dashboard — the whole path from sensor to time-series chart.",
      "vellum", f"{GH}/studio-vellum/meadow", demo=None, license="Apache-2.0",
      stack=["Rust", "embassy-rs", "MQTT", "InfluxDB"]),
    L("Palette OS", "Design tokens that survive handoff", "Design Systems", 99, "TypeScript", 90,
      ["tokens", "figma", "theming"], "design",
      "Figma plugin plus a build pipeline that compiles one token source into CSS variables, Tailwind config, iOS, and Android themes.",
      "vellum", f"{GH}/studio-vellum/palette-os", demo=None, license="MIT",
      stack=["TypeScript", "Figma Plugin API", "Style Dictionary", "Tailwind CSS"],
      model="open-source"),
]

# Work-in-progress listings. These exercise the drafts lane: a draft is not a
# published listing, does not count against the plan's active-listing quota, and
# can be deleted from the seller's Drafts tab.
DRAFT_LISTINGS = [
    L("Solstice Booking", "Appointment scheduling for small studios", "Productivity", 79, "Next.js", 62,
      ["booking", "calendar", "scheduling"], "productivity",
      "Draft — scheduling app with calendar sync and deposit collection. Copy still being written.",
      "foxglove", f"{GH}/atelier-foxglove/solstice-booking", demo=None),
    L("Rivet", "Load testing from a YAML file", "Developer Tools", 59, "Go", 58,
      ["cli", "load-testing", "performance"], "devtools",
      "Draft — scenario-driven load generator. Pricing and tiers not settled yet.",
      "korr", f"{GH}/studio-korr/rivet", demo=None),
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
    # The storefront's facet lists are served from here (catalog GET /config).
    # Seeding them keeps the filters in step with what the catalogue holds.
    "categories": CATEGORIES,
    "frameworks": FRAMEWORKS,
    "sections": ["Planning", "Design", "Development", "Architecture", "Data",
                 "Testing", "Security", "Deployment"],
}


_PITCH_BY_MODEL = {
    "for-profit": ("A commercial codebase you can rebrand and bill against.",
                   ["Source license sales", "Bespoke commissions"]),
    "open-source": ("Free to run, paid to support. The licence stays permissive.",
                    ["Priority support", "Sponsored features"]),
    "non-profit": ("Cost-recovery pricing for institutions that cannot buy enterprise.",
                   ["Institutional licences", "Grant funding"]),
    "sole-purpose": ("Built for one job and priced to be bought once.",
                     ["One-time source licence"]),
}


async def _add_listing(db, owner_id: str, spec: dict, *, status: str = "live") -> Listing:
    """Insert one catalogue row.

    `status="draft"` seeds the seller's Drafts lane: unpublished, unscored in the
    gallery sense, and deliberately outside the plan's active-listing quota.
    """
    name, cat, price = spec["name"], spec["category"], spec["price"]
    fw, score, tags = spec["framework"], spec["score"], spec["tags"]
    cover_url = COVERS.get(spec["cover"], COVER)
    demo = spec["demo"]
    is_draft = status == "draft"
    # Demo listings are evergreen (NULL = never expires). The seeded vitrine.db
    # is committed and shipped, so a fixed `now + 30 days` stamp meant the whole
    # gallery silently emptied out 30 days after whoever last ran the seed —
    # GET /listings filters on `expires_at > now`. "Quiet Hours" stays expired on
    # purpose: it is the fixture that demonstrates the expiry/repost flow.
    expires = None
    if name == "Quiet Hours":
        expires = datetime.now(timezone.utc) - timedelta(days=5)

    # Only claim a live demo when one was actually supplied. A CLI, a firmware
    # image and a mobile binary have no hosted preview, and badging them
    # "live-demo" is the kind of unevidenced claim the Verification agent exists
    # to catch.
    badges: list[str] = []
    if not is_draft:
        badges = ["verified"] + (["live-demo"] if demo else []) + (["best-ui"] if score >= 93 else [])

    listing = Listing(
        owner_id=owner_id, name=name, slug=slugify(name), tagline=spec["tagline"],
        category=cat, tags=tags, framework=fw, price_cents=price * 100,
        license=spec["license"], status=status,
        demo_url=demo, repo_url=spec["repo"],
        demo_health="live", vitrine_score=score, cover=cover_url,
        expires_at=expires,
        ai_draft=is_draft,
        screenshots=[cover_url] + SHOTS,
        badges=badges,
        description=spec["description"],
        rating=0 if is_draft else round(4.2 + (score % 8) / 10, 1),
        reviews_count=0 if is_draft else 24 + (score % 50),
        # 5★→1★ (matches ProductPage[5-star])
        rating_distribution=[0, 0, 0, 0, 0] if is_draft else [56, 28, 10, 4, 2],
        score_breakdown=[
            {"label": "Completeness", "value": 55 if is_draft else 90},
            {"label": "UI craft", "value": score - 2},
            {"label": "Demo health", "value": 0 if not demo else 94},
        ],
        sdlc={
            "problem": f"Teams stitch together five tools for {cat.lower()} work.",
            "solution": "A focused codebase shipping the 80% you actually use.",
            "methodology": "Designed in the open; built in two-week cycles.",
            "discussions": "How opinionated should the data layer remain?",
        },
        business_model={
            "kind": spec["model"],
            "pitch": _PITCH_BY_MODEL[spec["model"]][0],
            "revenueStreams": _PITCH_BY_MODEL[spec["model"]][1],
        },
        tech_stack=spec["stack"],
    )
    db.add(listing)
    await db.flush()

    embedding = await client.embed(f"{name} {spec['tagline']} {cat} {' '.join(tags)}")
    db.add(ListingEmbedding(listing_id=listing.id, embedding=embedding))
    if not is_draft:
        db.add_all([
            ListingTier(listing_id=listing.id, name="Source", price_cents=price * 100,
                        features=["Full source code", f"{spec['license']} license", "Email support"]),
            ListingTier(listing_id=listing.id, name="Source + Setup",
                        price_cents=(price + 80) * 100, recommended=True,
                        features=["Onboarding call", "30 days of fixes"]),
            ListingField(listing_id=listing.id, section="Development", key="Stack",
                         value=" · ".join(spec["stack"]), source="ai", confidence=0.9),
            ListingField(listing_id=listing.id, section="Deployment", key="Live demo",
                         value=bool(demo), source="ai", confidence=0.95),
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
            owner = sellers[spec["seller"]]
            listing = await _add_listing(db, owner.id, spec)
            listing_by_name[listing.name] = listing

        for spec in DRAFT_LISTINGS:
            owner = sellers[spec["seller"]]
            await _add_listing(db, owner.id, spec, status="draft")

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
            # Reuse the live checkout economics rather than re-deriving the rate
            # table here — a fourth copy of it is exactly how the seeded ledger
            # drifted from what checkout actually charges (see shared/plans.py).
            seller_user = next((s for s in sellers.values() if s.id == listing.owner_id), None)
            plan = seller_user.plan if seller_user else "free"
            is_student = bool(seller_user and seller_user.is_student and plan == "free")
            gross, commission, _net = split_sale(price_dollars * 100, plan, is_student)

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

        foxglove_count = sum(1 for s in LISTINGS if s["seller"] == "foxglove")
        korr_count = sum(1 for s in LISTINGS if s["seller"] == "korr")
        vellum_count = sum(1 for s in LISTINGS if s["seller"] == "vellum")
        total_count = foxglove_count + korr_count + vellum_count
        kinds = len({s["category"] for s in LISTINGS})
        print(
            f"[seed] v{SEED_VERSION}: 1 admin, 3 buyers, 3 sellers, "
            f"{total_count} live listings across {kinds} categories "
            f"({foxglove_count} Foxglove / {korr_count} Korr / {vellum_count} Vellum), "
            f"{len(DRAFT_LISTINGS)} drafts, 5 chat threads."
        )
        print("[seed] logins:")
        print("  admin@vitrine.io  / admin   (ADMIN — curator console)")
        print("  june@vitrine.io   / june    (buyer)")
        print("  marco@vitrine.io  / marco   (buyer)")
        print("  sana@vitrine.io   / sana    (buyer)")
        print("  maker@vitrine.io  / maker   (seller — Atelier Foxglove)")
        print("  dev@vitrine.io    / dev     (seller — Studio Korr)")
        print("  studio@vitrine.io / studio  (seller — Studio Vellum)")


if __name__ == "__main__":
    asyncio.run(seed())

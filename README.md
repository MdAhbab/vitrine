# Vitrine — *Try the software. Then own it.*

> A boutique software marketplace where every product ships with a **live, runnable preview**, and where AI agents do the heavy lifting: reading repos, filling technical specs, verifying quality, ranking listings, advising sellers on price, and guiding buyers to the right product.

**Vitrine** (French: *a glass display case / boutique shop window*) is not your usual "app store grid." It is a curated gallery where indie developers and students put their software *on display* — and shoppers can actually test-drive a product before paying for it. The boring, repetitive work of publishing and curating software is handed to a fleet of cooperating **OpenAI-powered agents**.

---

## Table of Contents

1. [The Problem & Impact](#1-the-problem--impact)
2. [What Vitrine Is](#2-what-vitrine-is)
3. [Core User Journeys](#3-core-user-journeys)
4. [Feature Map (Primary + Subsidiary)](#4-feature-map-primary--subsidiary)
5. [The AI-Native Core — The Vitrine Agent Fleet](#5-the-ai-native-core--the-vitrine-agent-fleet)
6. [The Vitrine Score (AI Ranking Model)](#6-the-vitrine-score-ai-ranking-model)
7. [The Listing Intake Form Sheet (Detailed)](#7-the-listing-intake-form-sheet-detailed)
8. [System Architecture](#8-system-architecture)
9. [OpenAI Usage Details (for judging) + $10 Budget Plan](#9-openai-usage-details-for-judging--10-budget-plan)
10. [Security & Infrastructure](#10-security--infrastructure)
11. [Tech Stack](#11-tech-stack)
12. [Repository Structure](#12-repository-structure)
13. [How to Run](#13-how-to-run)
14. [Roadmap — Built vs. Planned](#14-roadmap--built-vs-planned)
15. [Submission Checklist](#15-submission-checklist)
16. [Social Post Draft](#16-social-post-draft)
17. [Team & License](#17-team--license)

---

## 1. The Problem & Impact

### The problem
Independent developers and students build genuinely good software — but selling it is broken:

- **Buyers can't try before they buy.** Screenshots and feature lists lie. There is no widely-adopted marketplace that pairs a listing with a *live, runnable demo* of the actual software.
- **Publishing is tedious and inconsistent.** Writing out the stack, architecture, testing approach, deployment story, and a compelling pitch is hours of work most builders skip — so listings are thin, unsearchable, and untrustworthy.
- **Curation doesn't scale.** A human team cannot vet thousands of submissions for quality, plausibility, and fraud.
- **Sellers don't know how to price or package** their work, or how to turn a side-project into a product.
- **Discovery is bad.** Keyword search can't answer "find me a React dashboard with Stripe, under $40, that I can actually run right now."

### The solution & its impact
Vitrine fixes all five with **preview-hosted listings + an agentic publishing pipeline**:

- **Buyers** get to *run* the software in a sandboxed preview before paying — drastically lowering purchase risk.
- **Developers & students** paste a GitHub URL (or upload a README) and an agent **auto-fills an industry-grade technical spec**, **verifies** the listing, **prices** it, and **writes the pitch** — turning a 2-hour chore into a 2-minute one.
- **The platform** stays high-quality and trustworthy at scale because **agents curate and rank** every listing automatically (the *Vitrine Score*).
- **Local impact (Bangladesh):** students and indie devs get a near-zero-friction storefront, discounted promotion slots, and an AI co-pilot that helps them actually commercialize their work — directly serving the *Local Problem Solving*, *Community Impact*, and *Business Automation* categories.

**Who benefits:** indie developers, students, small software studios (sellers); businesses and individuals shopping for ready-made software (buyers); and the wider developer community that gets a trustworthy, try-before-you-buy market.

---

## 2. What Vitrine Is

A **marketplace + managed preview hosting + agentic curation layer** for software products (not businesses).

Three things make it different:

1. **Preview-first listings.** Every product card opens into a sandboxed, embedded **live preview** (developer-supplied `*.vercel.app` link today; Vitrine-managed native hosting as a paid tier). A health-checker keeps demos honest.
2. **Agentic publishing.** A fleet of OpenAI agents reads the repo/README, fills the technical form, verifies the submission, ranks it, and helps the seller price & pitch it.
3. **Boutique, premium experience.** A gallery, not a flea market — curated sections, editorial layout, dark/light, slow elegant motion. (See [frontend.md](./frontend.md).)

### The commercial model (how Vitrine makes money)
- **Preview hosting fees** — charged by hosting *duration* + deployment/infra-management fee when a developer wants Vitrine to host the demo (or the full app) instead of using their own Vercel link.
- **Marketplace take rate** — a percentage of each sale / advance payment.
- **Promotion slots** — featured placement; **discounted for Bangladeshi students** (Local Problem Solving category).
- **Pro seller tools** — AI Pricing & Pitch, analytics, and managed deployment as a subscription.

### The "demo-then-deliver" sales flow
1. Developer lists a product with **only a demo frontend** (preview link) + the AI-filled spec.
2. A buyer **purchases or pays an advance**.
3. The **Notification service** alerts the developer.
4. The developer **delivers** the full app / upgraded / customized build to the buyer (via Vitrine's secure delivery + license flow).

---

## 3. Core User Journeys

### A) Developer / Student (Seller)
1. Sign up → choose **Developer** role.
2. **New Listing** → paste GitHub URL *or* upload README → **Repo-Intake Agent** crawls and **auto-fills the technical form sheet** (stack, frameworks, tests, deploy, architecture, suggested category & tags).
3. Review/edit the auto-filled fields; add the **Vercel preview URL**; set price/tiers (with **Pricing & Pitch Agent** suggestions).
4. Submit → **Verification Agent** checks quality/plausibility/red-flags → approve / request-changes / flag.
5. Listing goes live; **Curation & Ranking Agent** computes its **Vitrine Score**.
6. On purchase/advance → **notified** → deliver full build to buyer.

### B) Buyer
1. Browse the gallery (curated sections, filters, sorts) or ask the **Buyer Concierge**: *"React dashboard with Stripe, under $40, live demo."*
2. Open a listing → **run the live preview** in a sandboxed device frame.
3. Read AI-summarized spec + verified badges + reviews + Vitrine Score.
4. Buy / pay advance → receive delivery → review the product.

### C) Admin / Curator
1. Review the Verification Agent's queue (approve overrides, handle flags).
2. Monitor agent runs, costs, and the event stream.
3. Manage categories, featured slots, and disputes.

---

## 4. Feature Map (Primary + Subsidiary)

### Primary features
- **Preview-hosted listings** — embedded sandboxed live demo per product + automated **demo health checks**.
- **Agentic intake** — GitHub crawl / README upload → auto-filled **technical form sheet**.
- **Agentic verification** — automated quality/fraud gate before go-live.
- **Vitrine Score** — AI + heuristic ranking (recency, completeness, reviews, UI beauty, demo health, engagement).
- **Buyer Concierge** — semantic search + chat assistant + compare.
- **Pricing & Pitch** — seller-side AI for tiers, copy, and business model.
- **Demo-then-deliver** commerce flow with **advance payments** + seller notification.
- **Boutique storefront** — curated sections, rich filtering/sorting/subsections, dark/light.

### Subsidiary / supporting features
- **Managed preview hosting tier** (Vitrine hosts the demo / full app on native cloud VM; billed by duration).
- **Reputation system** — reviews, ratings (Bayesian), verified-purchase badges, seller trust score.
- **Collections & curated editorials** ("Staff picks", "Built this week", "Best UI").
- **Seller analytics** — views, demo launches, conversion, revenue.
- **Wishlist / follow developer / notify on update.**
- **Versioning & changelogs** for products; "notify buyers of upgrade."
- **License & secure delivery** (signed download links / license keys).
- **Promotion / featured slots** (student-discounted).
- **Webhooks** for sellers (sale, advance, review).
- **Admin curation console** + agent run dashboard + cost meter.
- **Full-text + vector hybrid search** with facets.
- **Audit log & moderation trail.**

---

## 5. The AI-Native Core — The Vitrine Agent Fleet

Vitrine treats AI as the **core of the product**, not a feature bolted on. Five cooperating agents run an **event-driven workflow** (full specs, tools, memory, and orchestration in [AGENTS.md](./AGENTS.md)).

| # | Agent | Trigger | What it does | Key tools |
|---|-------|---------|--------------|-----------|
| 1 | **Repo-Intake Agent** | New/updated listing | Crawls GitHub repo or reads uploaded README; **fills the entire technical form sheet**; suggests category, tags, summary, highlights. | `fetch_repo_tree`, `fetch_file`, `read_readme`, `detect_stack`, `embed_text`, `write_listing_fields` |
| 2 | **Listing Verification Agent** | Listing submitted | Vets quality, completeness, plausibility (README ↔ claims), license sanity, spam/fraud signals → approve / request-changes / flag. | `check_demo_health`, `cross_check_claims`, `license_lookup`, `flag_listing` |
| 3 | **Buyer Concierge Agent** | Buyer search/chat | Hybrid semantic + filter search; answers natural-language queries; compares & recommends with reasons. | `semantic_search`, `apply_filters`, `compare_products`, `get_listing` |
| 4 | **Pricing & Pitch Agent** | Seller drafting | Suggests price tiers, writes listing copy & highlights, proposes a business model + advance-payment/upsell strategy. | `market_comps`, `get_listing`, `draft_copy`, `suggest_tiers` |
| 5 | **Curation & Ranking Agent** | Listing live / nightly | Computes the **Vitrine Score** from recency, completeness, reviews, UI beauty (vision), demo health, engagement; assigns to curated sections. | `compute_features`, `vision_score_ui`, `bayesian_rating`, `rank_and_section` |

### How the agents work together (the publishing pipeline)
```
Developer submits ──▶ [event: listing.created]
        │
        ├─▶ Repo-Intake Agent ──▶ fills form ──▶ [event: listing.enriched]
        │
        ├─▶ Verification Agent ──▶ approve/flag ──▶ [event: listing.verified | listing.flagged]
        │
        └─▶ Curation & Ranking Agent ──▶ Vitrine Score ──▶ [event: listing.scored] ──▶ live in gallery

Seller drafting ──▶ Pricing & Pitch Agent (on-demand, interactive)
Buyer searching ──▶ Buyer Concierge Agent (on-demand, streaming)
```

**Design principles** (mapped to the *Agent Design & Workflow Engineering* criterion):
- **AGENTS.md** defines every agent's role, tools, guardrails, and budget.
- **Tools, not freeform prompts** — agents call typed function tools (OpenAI tool/function calling) with validated JSON I/O.
- **Memory** — per-agent short-term scratch (run context) + long-term project memory in Redis/Postgres (e.g., market comps, category embeddings, prior verifications).
- **Orchestration** — Redis Streams event bus; each agent is a stateless worker subscribing to events; the AI Orchestration service supervises retries, budgets, and idempotency.
- **Determinism where possible** — heuristics do the cheap work; the LLM is invoked only where judgment is needed, with **prompt caching** + **result caching** to protect the budget.

---

## 6. The Vitrine Score (AI Ranking Model)

Every live listing gets a 0–100 **Vitrine Score** recomputed on changes and nightly. It blends cheap heuristics with one cached LLM/vision judgment, so it's accurate *and* budget-safe.

| Signal | Weight | Source |
|---|---|---|
| **Spec completeness** | 20% | % of form-sheet fields filled + Repo-Intake confidence |
| **Verification status** | 15% | Verification Agent result (verified > pending > flagged) |
| **Reviews / rating** | 20% | Bayesian average (guards against few-review bias) |
| **UI quality** | 15% | One-time **vision score** of the preview screenshot (cached) |
| **Demo health** | 10% | Live preview uptime / response checks |
| **Recency** | 10% | Time-decay on publish/update date |
| **Engagement** | 10% | Views, demo launches, conversion rate |

```
VitrineScore = 100 * Σ(weightᵢ · normalize(signalᵢ))
```
Tunable weights live in config. The score drives default sort, "Top of the Gallery," and curated-section assignment. (Implementation: [backend.md](./backend.md#curation--ranking).)

---

## 7. The Listing Intake Form Sheet (Detailed)

This is the **canonical technical form** every product is described by. The **Repo-Intake Agent auto-fills it** from a GitHub repo or an uploaded README; the seller reviews/edits. It's intentionally industry-grade — *planning → design → development → testing → deployment* — so listings are trustworthy and searchable. (DB mapping in [backend.md](./backend.md#data-model).)

> Field legend: **`[req]`** required · **`[ai]`** AI auto-fills · **`[ai*]`** AI suggests, seller confirms · **`[enum]`** controlled vocabulary · **`[multi]`** multiple values · **`[md]`** markdown.

### Section 0 — Identity & Commercial `[req]`
| Field | Type | Notes |
|---|---|---|
| Product name | text `[req]` | |
| Tagline | text `[ai*]` | ≤ 80 chars |
| Category | enum `[req][ai*]` | Web App, Mobile App, API/Backend, Dev Tool, AI/ML, Game, Desktop, Library/SDK, Template/Theme, Automation/Script, Data/Analytics, Other |
| Subcategory | enum `[ai*]` | depends on category |
| Tags | multi `[ai*]` | free + suggested |
| Pricing model | enum `[req]` | One-time, Subscription, Tiered, Free+Paid upgrade, Advance+Custom |
| Price / tiers | structured `[ai*]` | Pricing & Pitch Agent suggests |
| License | enum `[req][ai]` | MIT, Apache-2.0, GPL-3.0, Proprietary, Custom… |
| Delivery method | enum `[req]` | Source download, License key, Hosted handoff, Custom build |
| Short description | text `[ai]` | ≤ 200 chars |
| Long description | `[md][ai]` | AI draft, seller edits |

### Section 1 — Planning & Product
| Field | Type | Notes |
|---|---|---|
| Problem it solves | `[md][ai]` | |
| Target users | multi `[ai*]` | |
| Key features | list `[ai]` | bullet highlights |
| Use cases | list `[ai*]` | |
| Project maturity | enum `[ai*]` | Prototype, MVP, Beta, Production, Mature |
| Roadmap / known limitations | `[md][ai*]` | |

### Section 2 — Design & UX
| Field | Type | Notes |
|---|---|---|
| UI framework / design system | multi `[ai]` | Tailwind, MUI, Chakra, Bootstrap… |
| Responsive | bool `[ai]` | |
| Theming | enum `[ai]` | Dark, Light, Both, N/A |
| Accessibility notes | `[md][ai*]` | |
| Design assets | files `[ai*]` | Figma link, screenshots |
| Demo screenshots | files `[req]` | used for **UI vision score** |

### Section 3 — Development
| Field | Type | Notes |
|---|---|---|
| Primary language(s) | multi `[req][ai]` | detected from repo |
| Frameworks | multi `[ai]` | React, FastAPI, Next, Express, Django… |
| Key libraries / packages | multi `[ai]` | from manifests |
| Runtime / platform | multi `[ai]` | Node, Python, Browser, iOS… |
| Package manager | enum `[ai]` | npm, pnpm, pip, poetry, cargo… |
| Code size / structure | auto `[ai]` | LOC, top-level layout |
| Repo URL | url `[ai]` | public link if available |
| README quality | auto `[ai]` | scored |

### Section 4 — Architecture
| Field | Type | Notes |
|---|---|---|
| Architecture style | enum `[ai*]` | Monolith, Modular monolith, Microservices, Serverless, Static, Client-only |
| Architecture summary | `[md][ai]` | AI-generated overview |
| Integrations / external APIs | multi `[ai]` | Stripe, OpenAI, Auth0… |
| Event/async model | text `[ai*]` | queues, streams, webhooks |
| Diagram | file/`[ai*]` | optional mermaid |

### Section 5 — Data & Storage
| Field | Type | Notes |
|---|---|---|
| Databases | multi `[ai]` | Postgres, MySQL, Mongo, Redis, SQLite… |
| ORM / data layer | multi `[ai]` | Prisma, SQLAlchemy… |
| Data model summary | `[md][ai*]` | |
| Migrations tooling | text `[ai]` | Alembic, Prisma Migrate… |

### Section 6 — Testing & Quality
| Field | Type | Notes |
|---|---|---|
| Test frameworks | multi `[ai]` | Jest, Pytest, Vitest, Cypress… |
| Test coverage | text `[ai*]` | if reported |
| CI configured | bool `[ai]` | from `.github/workflows` etc. |
| Linting / formatting | multi `[ai]` | ESLint, Ruff, Prettier… |
| Type safety | enum `[ai]` | TS, mypy, none… |

### Section 7 — Security & Compliance
| Field | Type | Notes |
|---|---|---|
| Auth model | enum `[ai*]` | JWT, OAuth, Session, API key, None |
| Secrets management | text `[ai*]` | env, vault… |
| Known sensitive scopes | multi `[ai*]` | payments, PII, uploads |
| Compliance notes | `[md][ai*]` | |

### Section 8 — Deployment & Infrastructure
| Field | Type | Notes |
|---|---|---|
| Deploy targets | multi `[ai]` | Vercel, Netlify, VM, AWS, Render… |
| Live demo URL | url `[req]` | `*.vercel.app` (embedded preview) |
| Build command | text `[ai]` | from scripts/manifests |
| Run command | text `[ai]` | |
| Env vars required | list `[ai]` | names only |
| System requirements | text `[ai*]` | |
| Vitrine-managed hosting? | enum `[req]` | No / Demo only / Full app (billed by duration) |

### Section 9 — Performance & Ops (optional, `[ai*]`)
Benchmarks, scalability notes, monitoring/observability, rate limits.

### Section 10 — Media & Proof `[req]`
Screenshots `[req]`, demo video (optional), GIFs, sample data.

> **Repo-Intake confidence** per field is stored; low-confidence fields are highlighted for the seller to confirm. This confidence feeds both the **Vitrine Score** (completeness) and the **Verification Agent**.

---

## 8. System Architecture

**Event-driven microservices**, native (no Docker), minimal moving parts. Full detail in [backend.md](./backend.md).

```
                         ┌──────────────────────────────────────────────┐
   React + Vite + TW ───▶│              API Gateway (FastAPI)           │
   (frontend.md)         │   auth · routing · rate-limit · validation   │
                         └───────┬───────────────┬──────────────┬───────┘
                                 │               │              │
                ┌────────────────┘     ┌─────────┘      ┌───────┘
                ▼                      ▼                ▼
        ┌──────────────┐      ┌──────────────┐   ┌──────────────┐
        │ Identity/Auth│      │   Catalog    │   │   Search     │
        │   service    │      │  (listings)  │   │ (pgvector)   │
        └──────────────┘      └──────┬───────┘   └──────────────┘
                                     │
        ┌──────────────┐      ┌──────┴───────┐   ┌──────────────┐
        │ Orders/Pay   │      │ AI Orchestr. │   │ Hosting/     │
        │ (mock→Stripe)│      │ (agent fleet)│   │ Preview      │
        └──────┬───────┘      └──────┬───────┘   └──────────────┘
               │                     │
        ┌──────┴───────┐      ┌──────┴───────┐
        │ Notification │      │ Reviews/     │
        │   service    │      │ Reputation   │
        └──────────────┘      └──────────────┘

   ╔══════════════════════════════════════════════════════════════╗
   ║   Redis Streams  =  event bus  +  cache  +  rate-limit         ║
   ║   PostgreSQL + pgvector  =  primary store  +  vector search    ║
   ╚══════════════════════════════════════════════════════════════╝
```

- **Event bus:** Redis Streams (lightweight, no Kafka, no Docker). Events like `listing.created`, `listing.enriched`, `order.paid`.
- **Primary store:** PostgreSQL; **pgvector** extension gives semantic search without a separate vector DB.
- **Cache / queues / rate-limit / sessions:** Redis.
- **Agents:** stateless workers in the AI Orchestration service, subscribing to events, calling OpenAI with typed tools.
- **Local dev:** one process-manager spawns each service (uvicorn per service) + workers + Vite. **Cloud:** native systemd services behind nginx (see `cloudrun.py`).

---

## 9. OpenAI Usage Details (for judging) + $10 Budget Plan

### Models used
| Capability | Model | Why |
|---|---|---|
| All agent reasoning + tool calling | **`gpt-4o-mini`** (swap via `OPENAI_MODEL`; can drop to `gpt-4.1-mini`/`nano`) | Cheapest capable tool-calling model; great cost/quality for structured extraction & short reasoning. |
| Semantic search & similarity | **`text-embedding-3-small`** | $0.02 / 1M tokens — effectively free for a catalog this size. |
| UI quality scoring | **`gpt-4o-mini` (vision)** | One cached image score per listing; multimodal at the cheap tier. |

### How OpenAI is integrated
- **Function/tool calling** for every agent — typed JSON in/out, validated with Pydantic, so the model fills the form sheet and returns structured verdicts rather than prose.
- **Structured outputs / JSON mode** to guarantee parseable results.
- **Embeddings** power the Buyer Concierge's hybrid semantic search (pgvector) and category suggestions.
- **Vision** for the one-time UI quality score feeding the Vitrine Score.
- **Streaming** responses for the Buyer Concierge chat.

### Why these choices
$10 + 1–2 days demands a **cheap-but-capable** model and **ruthless cost control**. `gpt-4o-mini` + `text-embedding-3-small` give tool calling, vision, and embeddings at the lowest tier, and the architecture only invokes the LLM where judgment is actually needed.

### Budget math (illustrative, `gpt-4o-mini` @ ~$0.15/1M in, $0.60/1M out)
| Operation | ~Tokens | ~Cost each |
|---|---|---|
| Repo-Intake (fill full form) | ~10k | **~$0.002** |
| Verification | ~3k | ~$0.001 |
| Concierge query | ~2k | ~$0.0007 |
| Pricing & Pitch | ~4k | ~$0.0013 |
| Embedding a listing | ~1k | ~$0.00002 |
| UI vision score (1×) | 1 image | ~$0.002 |

➡️ **$10 covers well over 1,000 full publish-pipeline runs** — far more than a demo needs.

### Cost-control mechanisms (built into the design)
- **Per-agent + global token budgets** enforced by the Orchestration service (hard caps, kill-switch).
- **Redis result cache** keyed by content hash (re-running Intake on an unchanged repo costs $0).
- **Prompt caching** of long static system prompts.
- **Heuristics first** — regex/manifest parsing fills most fields; the LLM only handles ambiguity.
- **Cheap-model default + env override** (`OPENAI_MODEL`) to trade down further.
- **Live cost meter** in the admin console + `OPENAI_DAILY_LIMIT_USD` guard.

---

## 10. Security & Infrastructure

- **AuthN/Z:** JWT access/refresh, RBAC (`buyer` / `developer` / `admin`), short-lived tokens.
- **Input validation:** Pydantic schemas at every boundary; strict CORS; request size limits.
- **Rate limiting & abuse control:** Redis token-bucket per IP/user; agent budget caps.
- **Sandboxed previews:** embedded demos run in `<iframe sandbox>` with a strict **CSP**; no access to parent; preview URLs validated/allow-listed (`*.vercel.app` + Vitrine-managed domains).
- **Payments:** mock provider behind a `PaymentProvider` interface; **Stripe-ready** with signed webhooks; no card data touches Vitrine.
- **Secrets:** `.env` locally, environment/secret store on the VM; never committed; `OPENAI_API_KEY` server-side only.
- **Secure delivery:** signed, expiring download links / license keys for "demo-then-deliver."
- **Audit trail:** moderation actions, agent runs, and payments logged.
- **Least privilege** DB roles; parameterized queries; output encoding to prevent XSS.

---

## 11. Tech Stack

| Layer | Choice |
|---|---|
| Frontend | **React + Vite + TypeScript + Tailwind CSS**, Framer Motion, TanStack Query, Zustand |
| Backend | **FastAPI** (Python 3.11+), Pydantic v2, SQLAlchemy 2.0, Alembic |
| Data | **PostgreSQL + pgvector**, **Redis** (Streams/cache/rate-limit) |
| AI | **OpenAI** `gpt-4o-mini`, `text-embedding-3-small`, tool calling, vision, embeddings |
| Comms | Redis Streams event bus, REST (+ SSE for streaming chat) |
| Auth | JWT + RBAC |
| Payments | Mock provider → Stripe adapter |
| Deploy | Native cloud VM: uvicorn/gunicorn + systemd + nginx (no Docker) |

---

## 12. Repository Structure

```
vitrine/
├── README.md              ← this file (master plan)
├── AGENTS.md              ← agent roster, tools, memory, workflows
├── backend.md             ← backend architecture, data model, deploy
├── frontend.md            ← Claude-design build prompt for the storefront
├── run.py                 ← top-level launcher (→ local or cloud)
├── localrun.py            ← local dev orchestration (services + Vite)
├── cloudrun.py            ← native cloud VM deploy (systemd + nginx)
├── .env.example
├── backend/
│   ├── gateway/           ├── services/{identity,catalog,search,
│   ├── ai/   (agent fleet)│            orders,notifications,hosting,reviews}
│   ├── shared/ (db, events, schemas, security)
│   └── requirements.txt
└── frontend/              ← React + Vite + Tailwind (built per frontend.md)
```

---

## 13. How to Run

> **Prerequisites (native, no Docker):** Python 3.11+, Node 18+, PostgreSQL 15+ (with the `pgvector` extension), Redis 7+, and an `OPENAI_API_KEY`. Copy `.env.example` → `.env` and fill it in.

### One command — local
```bash
python run.py            # defaults to local; bootstraps + starts everything
```
`run.py` dispatches to **`localrun.py`**, which:
1. checks prerequisites (Python/Node/Postgres/Redis),
2. creates a virtualenv + installs `backend/requirements.txt`,
3. ensures the DB + `pgvector` + runs Alembic migrations + seeds demo data,
4. installs frontend deps,
5. starts all backend services (uvicorn per service) + agent workers + the Vite dev server, with unified logs.

```bash
python run.py local       # explicit local
python run.py local --seed --fresh-db   # reset + reseed demo data
```

### Deploy to a cloud VM (native build, no Docker)
```bash
python run.py cloud       # dispatches to cloudrun.py
# or directly on the VM:
python cloudrun.py deploy --domain vitrine.example.com
```
`cloudrun.py`:
1. installs system packages (Python/Node/Postgres/Redis/nginx) if missing,
2. builds the frontend (`vite build`) to static assets,
3. sets up the venv + migrations + seed,
4. writes **systemd** unit files for each service + agent workers (gunicorn/uvicorn workers),
5. configures **nginx** as reverse proxy + static host + TLS (certbot),
6. starts/enables all units and runs health checks.

Full flags and the deployment topology are documented in [backend.md](./backend.md#deployment).

---

## 14. Roadmap — Built vs. Planned

This repository delivers the **complete, deployment-ready plan and orchestration scaffolding**. Implementation phases:

| Phase | Scope | Status |
|---|---|---|
| **0 — Planning** | README, AGENTS.md, backend.md, frontend.md, run scripts | ✅ this repo |
| **1 — MVP** | Auth, listing CRUD, Repo-Intake agent, Vercel preview embed, mock payments + notify | ▢ planned |
| **2 — AI fleet** | Verification, Concierge (semantic search), Pricing & Pitch, Vitrine Score | ▢ planned |
| **3 — Commerce** | Stripe adapter, advance payments, secure delivery, reviews | ▢ planned |
| **4 — Managed hosting** | Native VM preview hosting tier (billed by duration) | ▢ planned |
| **5 — Polish** | Editorials, analytics, promotion slots (student discounts) | ▢ planned |

---

## 15. Submission Checklist

| Requirement | Where |
|---|---|
| **Project name** | Vitrine |
| **Short description** | A boutique software marketplace with live previews + an OpenAI agent fleet that publishes, verifies, ranks, prices, and recommends. |
| **Team name** | _TODO: add your team name_ |
| **Demo (link/video)** | _TODO: add live demo or recorded video_ |
| **Public source code** | _TODO: add GitHub repo URL_ |
| **OpenAI usage details** | [§9](#9-openai-usage-details-for-judging--10-budget-plan) |
| **Problem & impact** | [§1](#1-the-problem--impact) |
| **Social post** | [§16](#16-social-post-draft) |
| **Screenshots** | _TODO: add after frontend build_ |

**Judging alignment:** *AI-Native Thinking* → agent fleet is the product core (§5). *Agent Design & Workflow Engineering* → [AGENTS.md](./AGENTS.md), tools, memory, event orchestration. *Creativity & Originality* → preview-first boutique gallery (§2, [frontend.md](./frontend.md)). *Practical Impact* → §1 + Bangladesh student focus.

---

## 16. Social Post Draft

> 🪟 Introducing **Vitrine** — *try the software, then own it.*
>
> A boutique marketplace where every product ships with a **live preview**, and an **OpenAI agent fleet** reads your repo, fills the spec, verifies quality, ranks listings, and helps you price & pitch.
>
> Built with FastAPI · Postgres+pgvector · React · OpenAI `gpt-4o-mini`.
>
> 🔗 demo: _<link>_ · code: _<repo>_  #OpenAI #buildinpublic

---

## 17. Team & License

- **Team:** _TODO_
- **Contact:** _TODO_
- **License:** MIT (suggested) — see `LICENSE`.

> Next: read [AGENTS.md](./AGENTS.md) for the agent fleet, [backend.md](./backend.md) for the architecture & deployment, and [frontend.md](./frontend.md) to generate the premium storefront.

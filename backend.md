# backend.md — Vitrine Backend Plan

> Event-driven microservices, **native (no Docker)**, minimal infra: FastAPI + PostgreSQL/pgvector + Redis Streams + an OpenAI agent fleet. This document is the implementation blueprint and the deployment runbook for `localrun.py` and `cloudrun.py`.

## Contents
1. [Principles & topology](#1-principles--topology)
2. [Services](#2-services)
3. [Event bus & contracts](#3-event-bus--contracts)
4. [Data model](#4-data-model)
5. [The form sheet → schema mapping](#5-the-form-sheet--schema-mapping)
6. [AI Orchestration service & tools](#6-ai-orchestration-service--tools)
7. [Curation & ranking](#7-curation--ranking)
8. [Payments (mock → Stripe)](#8-payments-mock--stripe)
9. [Search (pgvector hybrid)](#9-search-pgvector-hybrid)
10. [Security](#10-security)
11. [API surface](#11-api-surface)
12. [Project layout](#12-project-layout)
13. [Local run (`localrun.py`)](#13-local-run-localrunpy)
14. [Deployment (`cloudrun.py`)](#14-deployment-cloudrunpy)
15. [Config & env](#15-config--env)

---

## 1. Principles & topology

- **Microservices, but pragmatic.** Each service is an independent FastAPI app (own port, own module, own DB schema/tables). They share a single Postgres instance (separate schemas) and a single Redis to keep infra tiny and VM-friendly. They communicate **asynchronously via Redis Streams** and **synchronously via the API Gateway** only where a request/response is needed.
- **No Docker.** Locally: a Python process-manager spawns each uvicorn app + workers + Vite. On the VM: one **systemd unit per service** behind **nginx**.
- **Stateless services.** All state in Postgres/Redis → services restart freely; workers scale by adding consumer-group members.
- **Cheap & secure by default.** pgvector avoids a separate vector DB; Redis Streams avoids Kafka; OpenAI calls are budgeted and cached.

```
        nginx (TLS, static frontend, reverse proxy)
                       │
              ┌────────┴────────┐
              │  API Gateway    │  :8000   (auth, routing, validation, rate-limit)
              └───┬───┬───┬──┬──┘
   identity:8001 ─┘   │   │  └─ orders:8004 ─┐
   catalog :8002 ─────┘   └─ search :8003   ├─ notifications:8005
   hosting :8006 ─────────── reviews :8007  ┘
   ai-orchestrator:8010 (+ N stream-worker processes)
              │
   ┌──────────┴───────────┐
   │ PostgreSQL (+pgvector)│   Redis (Streams + cache + rate-limit)
   └──────────────────────┘
```

---

## 2. Services

| Service | Port | Responsibility | Sync API | Events emitted | Events consumed |
|---|---|---|---|---|---|
| **gateway** | 8000 | Auth check, routing, rate-limit, request validation, CORS, SSE proxy, direct messaging routing | all public routes, `/chats/*` | — | — |
| **identity** | 8001 | Signup/login (including admin auth), JWT issue/refresh, roles, profiles, student status verification | `/auth/*`, `/users/*` | `user.created` | — |
| **catalog** | 8002 | Listings CRUD, form-sheet persistence, state machine, media, and feature requests management | `/listings/*`, `/feature-requests/*` | `listing.created/updated/enriched/verified/flagged/scored`, `feature.requested` | `listing.enriched/verified/scored` |
| **search** | 8003 | Hybrid pgvector + facet search, suggestions | `/search/*` | — | `listing.scored` (reindex) |
| **orders** | 8004 | Cart, checkout, advance payments, payouts ledger, seller subscriptions, commissions tracking | `/orders/*`, `/checkout/*`, `/subscriptions/*`, `/webhooks/payments` | `order.created/paid/refunded`, `subscription.created/expired` | — |
| **notifications** | 8005 | In-app + email; "deliver the full app" prompts; seller webhooks; chat notifications | `/notifications/*` | — | `order.paid`, `listing.flagged`, `review.created`, `chat.message_sent` |
| **hosting** | 8006 | Preview URL validation, demo health checks, managed-hosting jobs | `/hosting/*` | `demo.health_changed` | `listing.created/updated` |
| **reviews** | 8007 | Reviews/ratings, verified-purchase, reputation | `/reviews/*` | `review.created` | `order.paid` |
| **ai-orchestrator** | 8010 | Runs the agent fleet (including buyer negotiator & feature cost estimator), OpenAI client, budgets, cost meter | `/ai/*` (intake, concierge, pricing, negotiate, estimate) | per-agent events | `listing.created/enriched/verified`, `review.created`, `feature.requested`, `cron.*` |

> All services import from `backend/shared/` (db session, event bus, JWT, schemas, settings) so cross-cutting concerns are written once.

---

## 3. Event bus & contracts

Redis Streams, one stream per topic, consumer groups per service. Envelope:

```json
{
  "event_id": "uuid",
  "type": "listing.created",
  "occurred_at": "2026-06-09T12:00:00Z",
  "actor": "user:uuid | system",
  "idempotency_key": "listing:uuid:v1",
  "payload": { "...": "..." }
}
```

Core topics: `user.*`, `listing.*`, `order.*`, `review.*`, `demo.*`, `cron.*`.

- **At-least-once** delivery; consumers are **idempotent** (dedupe on `idempotency_key`).
- **Dead-letter** stream per consumer group after `MAX_DELIVERIES`.
- A tiny `EventBus` helper in `shared/events.py`: `publish(type, payload)`, `subscribe(group, topics, handler)`.

---

## 4. Data model

PostgreSQL, schema-per-service. Highlights (Pydantic v2 + SQLAlchemy 2.0; Alembic migrations).

```sql
-- identity
users(id pk, email uniq, password_hash, role enum[buyer,developer,admin],
      display_name, avatar_url, trust_score numeric default 0, is_student bool default false, student_verified bool default false, created_at)

-- catalog
listings(id pk, seller_id fk users, name, slug uniq, tagline,
         category, subcategory, pricing_model, price_cents, currency,
         license, delivery_method, status enum[draft,enriching,review,
         live,flagged,paused,archived], demo_url, managed_hosting enum,
         vitrine_score numeric, score_breakdown jsonb, 
         sdlc_notes text, problem_statement text, solution_methodology text, 
         business_model_draft text, tech_stack_draft jsonb, discussion_board jsonb, 
         created_at, updated_at)

listing_fields(id pk, listing_id fk, section, key, value jsonb,
               source enum[ai,seller,heuristic], confidence numeric)
-- the entire form sheet lives here as typed rows (flexible + auditable)

listing_media(id pk, listing_id fk, kind enum[screenshot,video,gif],
              url, position, is_primary)

listing_embeddings(listing_id fk, embedding vector(1536), text_hash)  -- pgvector

listing_tiers(id pk, listing_id fk, name, price_cents, features jsonb)

feature_requests(id pk, buyer_id fk users, listing_id fk listings, description text, 
                 estimated_charge_cents int, developer_charge_cents int, developer_approved bool default false,
                 status enum[pending_estimate, pending_dev_approval, pending_buyer_approval, approved, rejected], created_at)

-- orders
orders(id pk, buyer_id fk, listing_id fk, tier_id fk, amount_cents,
       kind enum[purchase,advance], status enum[pending,paid,delivered,
       refunded,disputed], provider, provider_ref, created_at)
deliveries(id pk, order_id fk, artifact_url, license_key, delivered_at)
payouts(id pk, seller_id fk, order_id fk null, amount_cents, status enum[pending, processed, failed],
        payout_method enum[bank, mobile_wallet], payout_details jsonb, requested_at, processed_at)

subscriptions(id pk, seller_id fk users, tier enum[free, monthly_pro], price_cents,
              start_date, end_date, active bool, is_student bool default false, created_at)

-- chats (direct messages and negotiation chats)
chats(id pk, buyer_id fk users, seller_id fk users, listing_id fk listings, created_at)
chat_messages(id pk, chat_id fk chats, sender_id fk users, text text, is_agent_rep bool default false, created_at)

negotiations(id pk, chat_id fk chats, buyer_id fk users, status enum[active, closed], 
             budget_cents int, target_cents int, active_rep_count_at_creation int, 
             buyer_readme_context text, created_at)

-- reviews
reviews(id pk, listing_id fk, buyer_id fk, rating int, body,
        verified_purchase bool, created_at)

-- ai / ops
agent_runs(id pk, agent, listing_id fk null, trigger_event, input_hash,
           model, tokens_in, tokens_out, cost_usd, latency_ms,
           verdict jsonb, confidence numeric, status, created_at)
ai_cache(key pk, value jsonb, created_at, ttl)   -- also mirrored in Redis
admin_configs(key pk, value text, description text, is_encrypted bool default false, updated_at)
audit_log(id pk, actor, action, target, meta jsonb, created_at)
```

Indexes: `listings(status, category, vitrine_score)`, GIN on `listing_fields.value`, `listing_embeddings` IVFFlat/HNSW vector index, full-text GIN on name/description, `chat_messages(chat_id, created_at)`, `subscriptions(seller_id, active)`.

---

## 5. The form sheet → schema mapping

The full [Listing Intake Form Sheet](./README.md#7-the-listing-intake-form-sheet-detailed) is stored as **typed rows in `listing_fields`** (one row per field), keyed `section.key`, with `source` (`ai`/`seller`/`heuristic`) and `confidence`. Hot/queryable fields (name, category, price, demo_url, license, status) are **denormalized onto `listings`** for fast filtering.

Why rows, not 60 columns:
- The form evolves without migrations.
- Per-field `source` + `confidence` powers the "confirm low-confidence fields" UX and the **completeness** signal of the Vitrine Score.
- Full audit of what the AI filled vs. what the seller edited.

A `FORM_SCHEMA` constant (`shared/form_schema.py`) is the single source of truth: field key, section, type, required, ai-fill policy, enum options, validation. Both the **Repo-Intake Agent** (to know what to fill) and the **frontend wizard** (to render the form) read from it.

---

## 6. AI Orchestration service & tools

`ai-orchestrator` is the only service that talks to OpenAI. Responsibilities:

- **OpenAI client** (`backend/ai/client.py`) — wraps chat/tool-calling, embeddings, vision; centralizes retries, timeouts, token counting, and **cost accounting** (writes `agent_runs`).
- **Budget guard** — per-run, per-agent-daily, and global (`OPENAI_DAILY_LIMIT_USD`) caps; raises `BudgetExceeded`.
- **Tool registry** (`backend/ai/tools/`) — each tool = a Pydantic input schema + handler; exposed to the model as OpenAI function tools. (Catalogue in [AGENTS.md §6](./AGENTS.md#6-shared-tool-catalogue-typed-functions).)
- **Agent runners** (`backend/ai/agents/`) — one module per agent; loads its [AGENTS.md](./AGENTS.md) section as the system prompt, declares allowed tools, runs the tool-calling loop, validates output, caches by input hash.
- **Workers** (`backend/ai/workers.py`) — subscribe to streams and dispatch to runners. Run as separate processes (scale by count).
- **HTTP endpoints** for interactive agents: `POST /ai/intake`, `POST /ai/concierge` (SSE stream), `POST /ai/pricing`.

Tool-calling loop (pseudo):
```python
async def run_agent(agent, ctx):
    if cached := cache.get(agent, ctx.input_hash): return cached
    budget.check(agent, ctx)
    messages = [system(agents_md_section(agent)), user(ctx.payload)]
    while True:
        resp = openai.chat(model, messages, tools=agent.tools, tool_choice="auto")
        if resp.tool_calls:
            for call in resp.tool_calls:
                out = registry.invoke(call.name, validate(call.args))
                messages.append(tool_result(call.id, out))
        else:
            result = validate_output(agent.schema, resp)
            cache.set(agent, ctx.input_hash, result)
            record_run(agent, ctx, resp.usage)
            return result
```

**Budget protections:** Redis content-hash cache, prompt caching of static system prompts, heuristic pre-fill, cheap default model, hard daily kill-switch.

---

## 7. Curation & ranking

`compute_features(listing)` (deterministic) gathers: completeness %, verification status, Bayesian rating, demo-health uptime, recency decay, engagement. `vision_score_ui(primary_screenshot)` runs **once per image** (cached by image hash). Weighted blend → `vitrine_score` + `score_breakdown` (stored for transparency). Recomputed on `listing.verified`, `review.created`, `listing.updated`, and nightly `cron.recompute_scores`. Drives default sort + section assignment ("Top of the Gallery", "Best UI", "Built this week"). Weights: `VITRINE_SCORE_WEIGHTS` (see [README §6](./README.md#6-the-vitrine-score-ai-ranking-model)).

---

## 8. Payments (mock → Stripe)

`PaymentProvider` interface decouples commerce from any gateway:

```python
class PaymentProvider(Protocol):
    async def create_checkout(self, order) -> CheckoutSession: ...
    async def verify_webhook(self, headers, body) -> PaymentEvent: ...

class MockProvider(PaymentProvider): ...     # demo: instant "paid" + signed fake webhook
class StripeProvider(PaymentProvider): ...   # drop-in later; signed webhooks
```

- **Demo flow:** checkout → `MockProvider` marks paid → `order.paid` event → Notification service alerts the **developer** ("buyer paid — deliver the full/upgraded/custom app") → seller uploads artifact → `deliveries` row + signed, expiring download link / license key to buyer.
- **Advance payments:** `orders.kind = advance`; partial amount; same notify-and-deliver loop with milestone status.
- **Switch to Stripe** = set `PAYMENT_PROVIDER=stripe` + keys; webhook route already exists, signature-verified.

---

## 9. Search (pgvector hybrid)

- **Index:** on `listing.scored`/`updated`, embed (name + tagline + description + tags) with `text-embedding-3-small` → `listing_embeddings`.
- **Query:** Buyer Concierge parses NL → filters; `search` service runs **vector ANN** (pgvector, HNSW/IVFFlat) ∪ **SQL facets** ∪ **full-text**, fuses by score, then orders by **Vitrine Score**.
- **Facets:** category, subcategory, tags, price range, license, has-demo, theming, frameworks, language.
- No external search engine — Postgres does it all.

---

## 10. Security

- **JWT** access (short TTL) + refresh; **RBAC** (`buyer`/`developer`/`admin`) enforced at the gateway and per-route dependencies.
- **Validation** everywhere via Pydantic; request size limits; strict CORS allow-list.
- **Rate limiting** — Redis token bucket per IP + per user; stricter on `/ai/*`.
- **Preview sandboxing** — embeds served only for allow-listed hosts (`*.vercel.app`, Vitrine domains); rendered in `<iframe sandbox="allow-scripts allow-same-origin allow-forms">` under a strict **CSP**; URL re-validated server-side.
- **OpenAI key** server-side only (in `ai-orchestrator`); never reaches the browser.
- **Payments** — no card data stored; webhook signatures verified; idempotent order updates.
- **Secure delivery** — signed, expiring artifact URLs / license keys.
- **Secrets** — `.env` locally; on the VM use environment files with `0600` perms (or a secrets manager); never committed.
- **DB** — least-privilege roles, parameterized queries; **audit_log** for moderation/payments/agent actions.

---

## 11. API surface (representative)

```
POST   /auth/signup | /auth/login | /auth/refresh
POST   /auth/admin/login                  # admin login
GET    /users/me
POST   /users/verify-student              # student status upload

POST   /listings                         # create draft
POST   /listings/{id}/intake             # trigger Repo-Intake (repo_url | readme upload)
PATCH  /listings/{id}                     # seller edits form fields (draft update)
DELETE /listings/{id}                     # delete listing (CRUD)
GET    /listings/{id}
GET    /listings?category=&tags=&sort=vitrine_score&...

POST   /ai/intake                         # interactive intake (sync)
POST   /ai/concierge   (SSE)              # buyer chat/search stream
POST   /ai/pricing                        # pricing & pitch suggestions
POST   /ai/negotiate                      # active AI representative bargaining step
POST   /ai/estimate-feature               # AI custom feature request cost estimation

GET    /search?q=...                      # hybrid search

POST   /checkout                          # create order (purchase|advance)
POST   /webhooks/payments                 # provider webhook (signed)
POST   /orders/{id}/deliver               # seller uploads full app
GET    /orders/{id}                       # detailed order status (milestones, delivery)
GET    /transactions/ledger               # transaction auditing (admin-only)
GET    /payouts                           # list payout request history for seller
POST   /payouts/request                   # request payout transfer

POST   /subscriptions/subscribe           # subscribe to Pro Monthly Tier
GET    /subscriptions/status              # check current subscription tier

GET    /chats                             # list conversations
GET    /chats/{id}/messages               # get message history
POST   /chats/{id}/messages              # send message (direct or as agent)
POST   /chats/negotiate/start             # spawn buyer agent representative (max 2 active)

POST   /feature-requests                  # submit feature request
PATCH  /feature-requests/{id}/quote       # developer sets/approves feature charge
POST   /feature-requests/{id}/approve     # buyer accepts custom charge and pays

POST   /reviews                           # verified-purchase review
GET    /notifications                     # in-app feed

# admin
GET    /admin/verification-queue
POST   /admin/listings/{id}/decision
GET    /admin/agent-runs                  # cost meter + observability
GET    /admin/chats                       # view all user chats (moderation)
GET    /admin/config                      # retrieve late-stage curator configurations & alternative keys
PATCH  /admin/config                      # edit prompts, rotate API keys at runtime
```

---

## 12. Project layout

```
backend/
├── requirements.txt
├── shared/
│   ├── settings.py        # pydantic-settings, all env
│   ├── db.py              # async SQLAlchemy engine/session
│   ├── events.py          # Redis Streams EventBus
│   ├── security.py        # JWT, RBAC deps, rate-limit
│   ├── form_schema.py     # FORM_SCHEMA single source of truth
│   └── schemas/           # shared Pydantic models
├── gateway/app.py
├── services/
│   ├── identity/app.py
│   ├── catalog/app.py
│   ├── search/app.py
│   ├── orders/app.py        # + providers/{mock,stripe}.py
│   ├── notifications/app.py
│   ├── hosting/app.py
│   └── reviews/app.py
├── ai/
│   ├── client.py            # OpenAI wrapper + cost accounting
│   ├── budget.py
│   ├── tools/               # typed tool handlers
│   ├── agents/              # one runner per agent
│   ├── workers.py           # stream consumers
│   └── app.py               # ai-orchestrator HTTP
├── migrations/              # Alembic
└── seed.py                  # demo users + listings
```

---

## 13. Local run (`localrun.py`)

`localrun.py` is a **native process orchestrator** (no Docker). It:

1. **Preflight:** checks Python 3.11+, Node 18+, `psql`, `redis-cli`; verifies Postgres + Redis are reachable (offers `brew services start` hints on macOS).
2. **Backend env:** creates `.venv`, installs `backend/requirements.txt`.
3. **Database:** creates DB + role if missing, enables `pgvector` (`CREATE EXTENSION`), runs `alembic upgrade head`; `--seed` runs `seed.py`; `--fresh-db` drops & recreates first.
4. **Frontend:** `npm install` in `frontend/` if needed.
5. **Launch (concurrently, prefixed logs):**
   - each service: `uvicorn backend.services.<svc>.app:app --port <port> --reload`
   - gateway on `:8000`
   - `ai-orchestrator` on `:8010` + `N` worker processes (`python -m backend.ai.workers`)
   - frontend: `npm run dev` (Vite on `:5173`)
6. **Health:** waits for `/health` on each service; prints a summary table + the storefront URL.
7. **Teardown:** Ctrl-C stops all child processes cleanly.

```bash
python localrun.py                    # start everything
python localrun.py --seed --fresh-db  # reset + reseed demo data
python localrun.py --only gateway,catalog,ai-orchestrator
python localrun.py --no-frontend
```

---

## 14. Deployment (`cloudrun.py`)

Native build on a single cloud VM (Ubuntu), **no Docker**, **systemd + nginx**.

`cloudrun.py deploy --domain vitrine.example.com` performs:

1. **System packages** (idempotent, `apt`): `python3.11`, `nodejs`, `postgresql`, `postgresql-contrib` (+ `pgvector`), `redis-server`, `nginx`, `certbot`.
2. **App user & dirs:** `vitrine` system user, `/opt/vitrine`, pull/copy code.
3. **Backend:** create `.venv`, install deps; create DB/role; enable `pgvector`; `alembic upgrade head`; optional seed.
4. **Frontend:** `npm ci && npm run build` → static assets to `/opt/vitrine/frontend/dist`.
5. **systemd units** (one per service + workers), e.g. `vitrine-gateway.service`, `vitrine-catalog.service`, `vitrine-ai.service`, `vitrine-ai-worker@.service` (templated for N workers). Backend served by **gunicorn + uvicorn workers**; `Restart=always`; `EnvironmentFile=/opt/vitrine/.env` (`0600`).
6. **nginx:** reverse-proxy `/api/*` → gateway `:8000`; SSE passthrough for `/api/ai/concierge`; serve the built frontend as static; gzip; security headers + CSP.
7. **TLS:** `certbot --nginx -d <domain>`.
8. **Enable + start** all units; run **health checks**; print status.

```bash
python cloudrun.py deploy  --domain vitrine.example.com [--seed] [--workers 3]
python cloudrun.py update             # git pull, rebuild FE, migrate, restart units
python cloudrun.py status             # systemctl status for all units + health
python cloudrun.py logs <service>     # journalctl -u vitrine-<service> -f
python cloudrun.py rollback           # restart on previous release dir
```

**Topology on the VM:** nginx (443) → gateway (8000) → internal services (8001–8010, bound to `127.0.0.1`); Postgres/Redis local sockets. Everything on one VM keeps cost low; services can later move to separate VMs unchanged (they're already network-addressable).

> **Managed preview hosting (Phase 4):** the `hosting` service gains a deploy worker that, for paid listings, clones the seller's repo into `/opt/vitrine/hosted/<id>`, runs the detected build/run commands under a dedicated unprivileged user + its own systemd unit, and exposes it at `https://<slug>.preview.vitrine.app` via an nginx vhost — **billed by duration** (a timer unit tears it down at expiry). Same native, no-Docker pattern.

---

## 15. Config & env

`.env.example` (consumed by `shared/settings.py`):

```ini
# core
ENV=local
SECRET_KEY=change-me
DATABASE_URL=postgresql+asyncpg://vitrine:vitrine@localhost:5432/vitrine
REDIS_URL=redis://localhost:6379/0
FRONTEND_ORIGIN=http://localhost:5173

# auth
JWT_ACCESS_TTL=900
JWT_REFRESH_TTL=1209600

# openai
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
OPENAI_EMBED_MODEL=text-embedding-3-small
OPENAI_DAILY_LIMIT_USD=5
AGENT_MAX_RETRIES=2
AGENT_RUN_BUDGET_TOKENS=20000

# payments
PAYMENT_PROVIDER=mock          # mock | stripe
STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=

# hosting / previews
ALLOWED_PREVIEW_HOSTS=vercel.app,preview.vitrine.app
```

> See [AGENTS.md](./AGENTS.md) for agent behaviour and HCD mobile design guidelines.

# backend.md — Vitrine Backend Plan

> Event-driven service scaffold with a pragmatic current runtime: FastAPI gateway monolith + SQLite/in-memory dev, Dockerized cloud VM deployment, and a later PostgreSQL/pgvector + Redis scale-out path. This document is the implementation blueprint and the deployment runbook for `run.py` and `cloudrun.py`.

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
13. [Local run (`run.py`)](#13-local-run-runpy)
14. [Deployment (`cloudrun.py`)](#14-deployment-cloudrunpy)
15. [Config & env](#15-config--env)

---

## 1. Principles & topology

- **Microservices, but pragmatic.** Each service still has an independent FastAPI module, but the current development and VM run use the gateway monolith so SQLite and the in-memory event bus work end-to-end.
- **Docker for cloud.** Locally: `run.py` starts Python + Vite directly. On the VM: `cloudrun.py` builds a Docker image and runs it with a Caddy container through Docker Compose.
- **State now, scale later.** Current state is persisted in SQLite and Docker volumes; Postgres/pgvector and Redis remain the later scale-out path.
- **Cheap & secure by default.** SQLite/in-memory avoids setup friction now; OpenAI calls are budgeted and cached.

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
   │ SQLite now            │   In-memory bus/cache now
   │ Postgres/Redis later  │   for split-service scale-out
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

## 9. Search (portable now, pgvector later)

- **Index:** on `listing.scored`/`updated`, embed (name + tagline + description + tags) with `text-embedding-3-small` → `listing_embeddings`.
- **Query now:** Buyer Concierge parses NL → filters; `search` service uses the portable vector-store path and SQL facets, then orders by **Vitrine Score**.
- **Query later:** Postgres can switch the same `listing_embeddings` flow to pgvector HNSW/IVFFlat ANN.
- **Facets:** category, subcategory, tags, price range, license, has-demo, theming, frameworks, language.
- No external search engine is required.

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

## 13. Local run (`run.py`)

`run.py` is a **native process orchestrator** (no Docker). It:

1. **Preflight:** checks Python 3.11+ and Node 18+. Postgres/Redis are only checked if `.env` opts into them.
2. **Backend env:** creates `.venv`, installs `backend/requirements.txt`.
3. **Database:** defaults to SQLite via `backend.shared.db_setup --ensure`; `--seed` runs `seed.py`; `--fresh-db` drops & recreates first.
4. **Frontend:** `npm ci` in `frontend/` when a lockfile is present.
5. **Launch (concurrently, prefixed logs):**
   - default monolith gateway: `uvicorn backend.gateway.app:app --port 8000 --reload`
   - optional split services with `EVENT_BUS=redis` and `--all`
   - `ai-orchestrator` on `:8010` + `N` worker processes (`python -m backend.ai.workers`)
   - frontend: `npm run dev -- --port <port> --strictPort`
6. **Ports:** picks the next available API/frontend ports if defaults are occupied, then prints the real URLs.
7. **Teardown:** Ctrl-C stops all child processes cleanly.

```bash
python run.py                    # start everything
python run.py --seed --fresh-db  # reset + reseed demo data
python run.py --only gateway,catalog,ai-orchestrator
python run.py --no-frontend
```

---

## 14. Deployment (`cloudrun.py`)

Docker build on a single cloud VM. The default domain is `vitrine.ahbab.dev`.

`cloudrun.py deploy --domain vitrine.ahbab.dev` performs:

1. **System packages:** install Docker Engine and the Compose plugin if missing.
2. **App dir:** sync the current checkout to `/opt/vitrine`.
3. **Cloud env:** write `/opt/vitrine/.env.cloud` with `ENV=prod`, `FRONTEND_ORIGIN=https://<domain>`, `DATABASE_URL=sqlite+aiosqlite:////data/vitrine.db`, `EVENT_BUS=memory`, and `CACHE=memory`.
4. **Docker build:** run `docker compose build --pull app`; the Dockerfile builds Vite in a Node stage and installs/runs FastAPI in a Python runtime stage.
5. **Runtime:** start two containers: `app` (`gunicorn backend.gateway.app:app`) and `web` (`caddy:2-alpine` for TLS and `/api/*` proxying).
6. **Persistence:** SQLite lives in the `vitrine-data` Docker volume and uploads live in `vitrine-files`.
7. **Health:** run `docker compose ps` and an in-container `/health` check.

```bash
python cloudrun.py deploy --domain vitrine.ahbab.dev [--seed]
python cloudrun.py update             # resync checkout, rebuild image, restart containers
python cloudrun.py status             # docker compose ps + app health
python cloudrun.py logs [app|web]     # docker compose logs -f
python cloudrun.py rollback           # restart current containers
python cloudrun.py teardown           # stop containers; add --volumes to delete data
```

**Topology on the VM:** Caddy container (80/443) -> FastAPI gateway container (`8000`) -> SQLite volume. The gateway serves both API routes and the compiled frontend SPA fallback, so the complete site is available at `https://vitrine.ahbab.dev` once DNS points at the VM.

> **Managed preview hosting (Phase 4):** keep this Docker-first pattern. Preview workers should build/run seller projects as isolated containers rather than adding native VM builds.

---

## 15. Config & env

`.env.example` (consumed by `shared/settings.py`):

```ini
# core
ENV=local
SECRET_KEY=change-me
DATABASE_URL=sqlite+aiosqlite:///./vitrine.db
EVENT_BUS=memory
CACHE=memory
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
ALLOWED_PREVIEW_HOSTS=vercel.app,preview.vitrine.app,demo.vitrine.app
```

> See [AGENTS.md](./AGENTS.md) for agent behaviour and HCD mobile design guidelines.

---
---

# Part II — Implementation Plan (added)

> This part is the build guide for the **existing React frontend** + the
> **scaffolded `backend/`**. It covers (16) every frontend↔backend wire, (17)
> the SQLite-now/Postgres-later database plan, (18) a phased step-by-step plan,
> and (19) a map of the scaffold. The first AI to pick this up should work
> phase-by-phase; each phase is independently runnable.

## 16. Frontend ↔ Backend wiring

### 16.0 Reconciliation (frontend is the source of truth)
The built frontend fixes a few choices the original plan left open. The backend
scaffold already follows these — keep them:

| Topic | Decision (matches `frontend/src/app/lib`) |
|---|---|
| Roles | `buyer · seller · admin` (use **seller**, not "developer") |
| Seller plans | `free · studio · atelier · maison` (not free/monthly_pro) |
| Commission % | `12 / 8 / 5 / 3` by plan; student-free = 7.5 — **runtime-editable** via `admin_configs.fees` |
| Listing lookup | by **slug** (`/p/:slug`) for detail; id for mutations |
| Chat = "thread" | frontend says `threadId`; backend table is `chats.id` → serializer maps `chat.id → threadId` |
| Messaging | dedicated **chats** service (gateway proxies `/chats/*` to it) |
| Money | dollars on the wire (frontend), **cents** in the DB (`*_cents`) |
| AdminConfig | one object assembled from keyed `admin_configs` rows |

### 16.1 The frontend integration layer (to add)
The frontend currently runs **100% on the in-memory Zustand store + mock data**
(no network calls). Wire it without rewriting the UI:

1. **Add `frontend/.env`** (see `frontend/.env.example`):
   ```ini
   VITE_API_BASE=/api                         # same-origin API path
   VITE_PROXY_TARGET=http://localhost:8000   # Vite dev proxy target
   VITE_USE_MOCKS=false                       # true = keep current mock store
   ```
2. **Add `frontend/src/app/lib/api.ts`** — a typed client (ready to paste below).
3. **Refactor `store.ts` actions** to call `api.*` when `VITE_USE_MOCKS !== 'true'`,
   otherwise keep the current local behaviour. Keep the store's *types* — they are
   already the response contract (the backend serializers mirror them).
4. **Token storage:** persist `access_token`/`refresh_token` in `localStorage`;
   `api.ts` attaches `Authorization: Bearer` and refreshes on 401.

```ts
// frontend/src/app/lib/api.ts  — drop-in integration layer
const BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000';
export const USE_MOCKS = (import.meta.env.VITE_USE_MOCKS ?? 'true') === 'true';

const tok = {
  get access() { return localStorage.getItem('vitrine_access'); },
  get refresh() { return localStorage.getItem('vitrine_refresh'); },
  set(a: string, r: string) {
    localStorage.setItem('vitrine_access', a);
    localStorage.setItem('vitrine_refresh', r);
  },
  clear() { localStorage.removeItem('vitrine_access'); localStorage.removeItem('vitrine_refresh'); },
};

async function req<T>(path: string, init: RequestInit = {}, retry = true): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(tok.access ? { Authorization: `Bearer ${tok.access}` } : {}),
      ...(init.headers ?? {}),
    },
  });
  if (res.status === 401 && retry && tok.refresh) {
    // TODO: POST /auth/refresh, store new tokens, replay once
  }
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.status === 204 ? (undefined as T) : res.json();
}

export const api = {
  // auth
  signup: (b: any) => req('/auth/signup', { method: 'POST', body: JSON.stringify(b) }),
  login: (b: any) => req('/auth/login', { method: 'POST', body: JSON.stringify(b) }),
  adminLogin: (b: any) => req('/auth/admin/login', { method: 'POST', body: JSON.stringify(b) }),
  me: () => req('/users/me'),
  setTokens: tok.set, clearTokens: tok.clear,

  // catalog
  listings: (qs = '') => req<any[]>(`/listings${qs}`),
  listing: (slug: string) => req(`/listings/${slug}`),
  createListing: (b: any) => req('/listings', { method: 'POST', body: JSON.stringify(b) }),
  intake: (id: string, b: any) => req(`/listings/${id}/intake`, { method: 'POST', body: JSON.stringify(b) }),
  updateListing: (id: string, b: any) => req(`/listings/${id}`, { method: 'PATCH', body: JSON.stringify(b) }),
  deleteListing: (id: string) => req(`/listings/${id}`, { method: 'DELETE' }),

  // commerce
  checkout: (b: any) => req('/checkout', { method: 'POST', body: JSON.stringify(b) }),
  subscribe: (tier: string) => req('/subscriptions/subscribe', { method: 'POST', body: JSON.stringify({ tier }) }),
  payouts: () => req('/payouts'),

  // chats / negotiation
  chats: () => req<any[]>('/chats'),
  messages: (id: string) => req<any[]>(`/chats/${id}/messages`),
  send: (id: string, body: string, as_agent = false) =>
    req(`/chats/${id}/messages`, { method: 'POST', body: JSON.stringify({ body, as_agent }) }),
  startNegotiation: (b: any) => req('/chats/negotiate/start', { method: 'POST', body: JSON.stringify(b) }),
  negotiate: (chat_id: string) => req('/ai/negotiate', { method: 'POST', body: JSON.stringify({ chat_id }) }),

  // ai
  pricing: (listing_id: string) => req('/ai/pricing', { method: 'POST', body: JSON.stringify({ listing_id }) }),
  estimateFeature: (b: any) => req('/ai/estimate-feature', { method: 'POST', body: JSON.stringify(b) }),
  featureRequest: (b: any) => req('/feature-requests', { method: 'POST', body: JSON.stringify(b) }),

  // misc
  notifications: () => req<any[]>('/notifications'),
  reviews: (listingId: string) => req(`/listings/${listingId}/reviews`),
  health: (url: string) => req(`/hosting/health?url=${encodeURIComponent(url)}`),

  // admin
  adminConfig: () => req('/admin/config'),
  patchAdminConfig: (b: any) => req('/admin/config', { method: 'PATCH', body: JSON.stringify(b) }),
  agentRuns: () => req('/admin/agent-runs'),
};

// Concierge SSE (POST + stream). Use fetch + ReadableStream reader.
export async function conciergeStream(query: string, onChunk: (c: any) => void) {
  const res = await fetch(`${BASE}/ai/concierge`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json',
               ...(tok.access ? { Authorization: `Bearer ${tok.access}` } : {}) },
    body: JSON.stringify({ query, history: [] }),
  });
  const reader = res.body!.getReader();
  const dec = new TextDecoder();
  let buf = '';
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    for (const line of buf.split('\n\n')) {
      const m = line.match(/^data: (.*)$/m);
      if (m) onChunk(JSON.parse(m[1]));
    }
    buf = buf.slice(buf.lastIndexOf('\n\n') + 2);
  }
}
```

### 16.2 Every wire (store action / page / modal → endpoint)
> `{slug}`/`{id}` substituted at call time. Dollars↔cents handled by serializers.

| Frontend touchpoint (`lib`/page/component) | Action | HTTP | Auth |
|---|---|---|---|
| `store.signIn` / `Auth.tsx` (login) | login | `POST /auth/login` → tokens → `GET /users/me` | public |
| `Auth.tsx` (signup) | register | `POST /auth/signup` → tokens | public |
| `Auth.tsx` (admin mode) | admin login | `POST /auth/admin/login` | public |
| `store.signOut` | clear tokens | — (client) | — |
| `store.toggleStudent` | verify student | `POST /users/verify-student` | buyer/seller |
| `Home.tsx` rails | curated lists | `GET /listings?sort=vitrine_score&limit=…` | public |
| `Browse.tsx` | filtered grid | `GET /listings?category=&tag=&q=&sort=` | public |
| `Browse.tsx` search box | search | `GET /search?q=` | public |
| `ProductPage.tsx` | detail | `GET /listings/{slug}` | public |
| `ProductPage.tsx` reviews | reviews | `GET /listings/{id}/reviews` | public |
| `PreviewFrame.tsx` | demo health | `GET /hosting/health?url=` (optional) | public |
| `ConciergePanel.tsx` | AI search | `POST /ai/concierge` (SSE) | optional |
| `Sell.tsx` step 1 | create draft | `POST /listings` | seller |
| `Sell.tsx` step 1 import | repo/README intake | `POST /listings/{id}/intake` | seller |
| `Sell.tsx` step 2 edits | save fields | `PATCH /listings/{id}` | seller |
| `Sell.tsx` step 4 | price & pitch | `POST /ai/pricing` | seller |
| `ListingEditor.tsx` / `store.upsertListing` | update | `PATCH /listings/{id}` | seller |
| `store.deleteListing` | delete | `DELETE /listings/{id}` | seller |
| `CheckoutModal` / `store.recordTransaction` | buy / advance | `POST /checkout` → `order.paid` | buyer |
| `RequestFeaturesModal` | feature + AI quote | `POST /feature-requests` + `POST /ai/estimate-feature` | buyer |
| `BargainModal` / `store.startThread(agent)` | dispatch AI rep | `POST /chats/negotiate/start` (max 2) | buyer |
| `store.agentReply` | rep's next msg | `POST /ai/negotiate {chat_id}` | buyer |
| `Inbox.tsx` / `store.sendMessage` | send message | `POST /chats/{id}/messages` | any party |
| `Inbox.tsx` | list threads / history | `GET /chats` · `GET /chats/{id}/messages` | any party |
| `Pricing.tsx` / `store.setUserPlan` | subscribe | `POST /subscriptions/subscribe` | seller |
| `SellerDashboard.tsx` | my listings / orders | `GET /listings?owner=me` · `GET /orders?role=seller` | seller |
| `SellerDashboard` payouts | payouts | `GET /payouts` · `POST /payouts/request` | seller |
| `OrderDetail.tsx` deliver | deliver app | `POST /orders/{id}/deliver` | seller |
| `BuyerDashboard.tsx` | orders / notifications | `GET /orders?role=buyer` · `GET /notifications` | buyer |
| `AdminDashboard` / `CuratorConsole` | config | `GET /admin/config` · `PATCH /admin/config` | admin |
| `AdminDashboard` api keys | rotate keys | `PATCH /admin/config {apiKeys}` | admin |
| `AdminDashboard` cost meter | agent runs | `GET /admin/agent-runs` | admin |
| `AdminDashboard` moderation | queue/decision/chats | `GET /admin/verification-queue` · `POST /admin/listings/{id}/decision` · `GET /admin/chats` | admin |

### 16.3 Auth & CORS notes
- Gateway sets CORS `allow_origins=[FRONTEND_ORIGIN]`. In dev that's
  `http://localhost:5173`; keep `VITE_API_BASE=http://localhost:8000`.
- In prod, nginx serves the SPA and proxies `/api/*`→gateway, so set
  `VITE_API_BASE=/api`. (cloudrun already strips `/api`.)
- Concierge/negotiate streams pass through nginx with buffering off (already in
  the nginx template, §14).

---

## 17. Database plan — SQLite now → Postgres later

**One portable model set** (`backend/shared/models.py`) runs on both engines.
Switch by changing only `DATABASE_URL`.

### 17.1 Why it's portable
| Concern | SQLite (now) | Postgres (later) | How |
|---|---|---|---|
| Driver | `sqlite+aiosqlite` | `postgresql+asyncpg` | `DATABASE_URL` only |
| Primary keys | `String(32)` uuid hex | same | `PK` mixin |
| Money | integer **cents** | same | `*_cents` columns |
| JSON/JSONB | `JSON`→TEXT | `JSON`→JSONB | SQLAlchemy generic `JSON` |
| Enums | plain `String` + Pydantic validation | same (or native ENUM) | avoids fragile SQLite ALTERs |
| Timestamps | `DateTime` (UTC) | `timestamptz` | `default=_now` |
| Vectors | JSON float-array + brute-force cosine | `pgvector` + HNSW index | `ai/vectorstore.py` factory |
| Schemas | single file, flat tables | (optional) schema-per-service | not required |

### 17.2 Zero-dependency dev
With the defaults the **whole stack runs with no Postgres and no Redis**:
- `DATABASE_URL=sqlite+aiosqlite:///./vitrine.db`
- `EVENT_BUS=memory` (in-process asyncio pub/sub) — works because dev runs the
  **gateway monolith** (all services in one process; events stay in-process).
- `CACHE=memory`.
- `OPENAI_API_KEY=` empty → `ai/client.py` returns deterministic **stubs** so
  agents/Concierge "work" offline; set the key to go live.

### 17.3 Tables (as built in the scaffold)
`users · listings · listing_fields · listing_tiers · listing_media ·
listing_embeddings · orders · deliveries · payouts · subscriptions ·
feature_requests · chats · chat_messages · negotiations · reviews ·
notifications · agent_runs · ai_cache · admin_configs · audit_log`.
The intake **form sheet** persists as `listing_fields` rows (`section.key`,
`source`, `confidence`) and is composed into the frontend `spec` by
`catalog/serializers.py`. `FORM_SCHEMA` (`shared/form_schema.py`) is the single
source of truth for both intake and the Sell wizard.

### 17.4 Migrating to Postgres (when ready)
1. `createdb vitrine` + `CREATE EXTENSION vector;`
2. Set `DATABASE_URL=postgresql+asyncpg://…`, `EVENT_BUS=redis`, `CACHE=redis`.
3. `cd backend && alembic revision --autogenerate -m "init" && alembic upgrade head`
   (Alembic env already converts the async URL to sync + `render_as_batch`).
4. Swap `listing_embeddings.embedding` JSON→`vector(1536)` in that migration and
   implement `PgVector` in `ai/vectorstore.py` (the factory picks it by dialect).
5. Implement the Redis `EventBus`/`Cache` branches (already stubbed) and run the
   services as separate processes (or keep the monolith — your call).
No model or endpoint code changes required.

---

## 18. Step-by-step implementation plan

> Status legend: ✅ done in scaffold · ◐ partial / harden · ▢ to build. Run after each phase.

### Phase 0 — Boot the scaffold ✅
- `python run.py` (or `uvicorn backend.gateway.app:app --reload`).
- Gateway auto-creates SQLite tables; `python -m backend.seed` adds demo data.
- Verify `GET /health`, `GET /listings`, `POST /auth/signup`, `POST /auth/login`.

### Phase 1 — Auth + catalog read (vertical slice) ✅/◐
- ✅ signup/login/admin-login/me; ✅ `GET /listings`, `GET /listings/{slug}`.
- ◐ token refresh on 401; ownership checks; pagination/facets; `owner=me` filter.
- **Wire FE:** add `api.ts` + `.env`; switch `Auth`, `Home`, `Browse`,
  `ProductPage` off mocks. *Done when the storefront renders from the DB.*

### Phase 2 — AI publishing pipeline ▢ (core differentiator)
- Implement real **tool handlers** (`ai/tools/`): `fetch_repo_tree`, `read_readme`,
  `detect_stack`, `embed_text`, `write_listing_fields`, `check_demo_health`.
- Flesh out **Repo-Intake** (heuristics → 1 LLM call → fill `listing_fields` +
  embed), **Verification** (verdict + `listing.verified/flagged`), **Curation**
  (real signals + cached `vision_score_ui`).
- Implement the multi-tool loop + retries in `agents/base.run_agent`.
- Real **Concierge** streaming + hybrid search (`vector_store.search`).
- **Wire FE:** `Sell.tsx` intake/edit/submit; `ConciergePanel` SSE.
- ◐ Budget guard persists spend via `agent_runs`; Redis result cache.

### Phase 3 — Commerce, chat, reviews ▢
- Orders: `deliver`, ledger, payouts, subscriptions; signed delivery links.
- Feature-requests CRUD + quote/approve flow (uses `feature_estimator`).
- Reviews create (verified-purchase) → rating rollup → `review.created` re-score.
- Chats: already working; add admin moderation `GET /admin/chats`.
- **Wire FE:** `CheckoutModal`, `RequestFeaturesModal`, `BargainModal`/`Inbox`,
  `Pricing`, dashboards (seller/buyer/admin), `AdminDashboard` config + cost meter.

### Phase 4 — Hardening & Postgres ▢
- Rate limiting (`/ai/*` stricter), CSP/sandbox on previews, audit log everywhere.
- Switch to Postgres + pgvector + Redis (§17.4); implement Redis bus/cache.
- Real Stripe provider + signed webhooks.

### Phase 5 — Managed preview hosting ▢ (see §14)
- `hosting` deploy worker: clone -> Docker build/run in an isolated container ->
  `*.preview.vitrine.app` route -> duration-billed teardown timer.

---

## 19. Scaffold map (what's already there)

```
backend/
├── shared/          settings, db, models(all tables), events(memory|redis),
│                    cache, security(JWT/RBAC), form_schema, ids, schemas/*,
│                    db_setup.py
├── gateway/app.py   MONOLITH: includes every router + lifespan(create_all +
│                    wires event handlers). Run this for SQLite dev.
├── services/        identity(✅auth) · catalog(✅read, ▢write) · search(basic) ·
│                    orders(✅mock checkout +providers) · notifications(✅order.paid)
│                    · hosting(url/health) · reviews(read) · chats(✅msg+negotiate)
├── ai/              client(stub-safe) · budget · vectorstore(sqlite brute-force)
│                    · tools(registry+stubs) · agents/(7 runners) · workers ·
│                    app(intake/concierge SSE/pricing/negotiate/estimate + admin)
├── seed.py          demo admin/maker/buyer + listings + default admin_config
├── migrations/      Alembic (Postgres-ready) · alembic.ini
└── requirements.txt
```
**Run the monolith (fastest path):**
```bash
cd backend && pip install -r requirements.txt
cd .. && uvicorn backend.gateway.app:app --reload --port 8000   # tables auto-create
python -m backend.seed                                          # demo data
# open http://localhost:8000/health and /listings
```
Demo logins: `admin@vitrine.io/admin` · `maker@vitrine.io/maker` · `buyer@vitrine.io/buyer`.

> Each stubbed endpoint raises `501` or returns a typed placeholder and is tagged
> `TODO Phase N` in code, so the next AI can grep `TODO Phase` and work the list.

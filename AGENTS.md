# AGENTS.md — The Vitrine Agent Fleet

> This file is the contract for every AI agent in Vitrine: its role, its tools, its memory, its guardrails, and how it is orchestrated. It is written to be read by **both humans and agents** (an agent loads the relevant section as part of its system prompt). It maps directly to the *Agent Design & Workflow Engineering* judging criterion.

- **Provider:** OpenAI
- **Default model:** `gpt-4o-mini` (override with `OPENAI_MODEL`; can drop to `gpt-4.1-mini`/`nano`)
- **Embeddings:** `text-embedding-3-small`
- **Vision:** `gpt-4o-mini` (multimodal)
- **Calling convention:** function/tool calling with **strict JSON** (Pydantic-validated) I/O
- **Orchestration:** event-driven workers on a **Redis Streams** bus, supervised by the **AI Orchestration service**

---

## 0. Operating principles (apply to ALL agents)

1. **Tools over prose.** Agents return structured tool calls / JSON, never free-form text that the system must parse. Each tool has a Pydantic schema; invalid output is rejected and retried (max `AGENT_MAX_RETRIES`, default 2).
2. **Heuristics first, LLM last.** Cheap deterministic code (manifest parsing, regex, DB lookups) fills everything it can. The model is invoked only for genuine judgment. This is both a quality and a **budget** decision.
3. **Budgeted.** Every agent run carries a token/cost budget. The Orchestration service enforces per-run, per-agent-daily, and global daily caps (`OPENAI_DAILY_LIMIT_USD`). Exceeding a cap raises `BudgetExceeded` and the run degrades gracefully (heuristic-only result + `needs_human_review`).
4. **Idempotent & cached.** Runs are keyed by a content hash (e.g., repo commit SHA + form version). Identical inputs hit the Redis cache and cost $0.
5. **Confidence-scored.** Agents attach a `confidence` (0–1) to each field/verdict. Low confidence → surfaced to a human (seller or admin).
6. **Observable.** Every run logs: agent, trigger event, input hash, tokens, cost, latency, tool calls, verdict, confidence → `agent_runs` table + admin cost meter.
7. **Safe by default.** No agent has write access outside its declared tools. No agent can publish a listing on its own — it can only *recommend* a state transition that the Catalog service applies.

---

## 1. Repo-Intake Agent

**Role:** Turn a GitHub repo *or* an uploaded README into a fully-filled [Listing Intake Form Sheet](./README.md#7-the-listing-intake-form-sheet-detailed).

**Triggers (events):** `listing.created`, `listing.repo_updated`, or direct API call from the New-Listing wizard.

**Inputs:** `{ listing_id, repo_url? , readme_text?, uploaded_files?[] }`

**Workflow:**
1. **Acquire context (heuristic):**
   - If `repo_url` (public): `fetch_repo_tree` → top-level layout; `fetch_file` for manifests (`package.json`, `pyproject.toml`, `requirements.txt`, `Cargo.toml`, `go.mod`, `Dockerfile`, `.github/workflows/*`, `vercel.json`), `read_readme`.
   - If private or no repo: use `readme_text` / uploaded README/files only.
2. **Deterministic extraction:** `detect_stack` parses manifests → languages, frameworks, libs, package manager, test frameworks, CI, deploy targets, build/run commands, env-var names. Fills as many Section 3–8 fields as possible **without the LLM**.
3. **LLM enrichment (one call, tool-calling):** the model fills the *judgment* fields — problem statement, target users, feature highlights, architecture summary, category/subcategory/tags suggestions, long description draft — via `write_listing_fields`, each with a confidence.
   - **Business Model / Purpose Draft**: The model drafts the business purpose of the software (commercial SaaS, non-profiting utility, open-source tool, or student project).
   - **Tech Stack Draft**: The model compiles a draft of the primary frameworks, libraries, and languages.
4. **Embed:** `embed_text` on (name + tagline + description + tags) → vector stored for search.
5. Emit `listing.enriched` with the filled form + per-field confidence.

**Tools:** `fetch_repo_tree`, `fetch_file`, `read_readme`, `detect_stack` (deterministic), `embed_text`, `write_listing_fields`, `suggest_taxonomy`.

**Memory:** long-term category/tag embeddings (for consistent taxonomy); short-term run scratch (the assembled repo context).

**Guardrails:** never invents a demo URL or license it can't evidence; unverifiable fields get low confidence + `needs_seller_confirmation`. Caps repo fetch size; respects GitHub rate limits via cache. All output business models and tech stacks are tagged as editable drafts for the seller.

**Output schema (abridged):**
```json
{
  "listing_id": "uuid",
  "fields": { "<form_field>": { "value": "...", "confidence": 0.0 } },
  "suggested_category": "Web App",
  "suggested_tags": ["react","stripe","dashboard"],
  "embedding_id": "uuid",
  "needs_seller_confirmation": ["price","license"]
}
```

---

## 2. Listing Verification Agent

**Role:** Quality + plausibility + fraud gate before a listing goes live. Automates human curation at scale.

**Triggers:** `listing.enriched`, `listing.submitted_for_review`.

**Workflow:**
1. **Demo health (deterministic):** `check_demo_health` pings the preview URL (allow-listed `*.vercel.app` / Vitrine domains), checks 2xx + render signal.
2. **Claim cross-check (LLM):** `cross_check_claims` compares README/spec claims against detected stack & form fields (e.g., "uses Postgres" but no DB dependency found → discrepancy).
3. **License sanity:** `license_lookup` validates the declared license vs. repo license file.
4. **Risk signals (LLM + heuristic):** spam, plagiarism markers, impossible claims, missing media, low completeness.
5. Verdict via `submit_verdict`: `approve | request_changes | flag` with reasons + confidence. `flag` routes to admin queue.

**Tools:** `check_demo_health`, `cross_check_claims`, `license_lookup`, `get_listing`, `submit_verdict`, `flag_listing`.

**Memory:** known-fraud patterns, previously flagged repos/sellers (Postgres); seller trust history.

**Guardrails:** cannot hard-reject — `flag` always escalates to a human; conservative on plagiarism (flag, don't accuse). Emits `listing.verified` / `listing.flagged`.

---

## 3. Buyer Concierge Agent

**Role:** Natural-language discovery + comparison + recommendation. The buyer-facing "find me exactly this" assistant.

**Triggers:** buyer search/chat (on-demand, **streamed** via SSE).

**Workflow:**
1. **Parse intent (LLM, tool-calling):** turn "React dashboard with Stripe under $40 with a live demo" into structured filters (`category`, `tags`, `price_max`, `has_demo`, free-text).
2. **Hybrid retrieve:** `semantic_search` (pgvector on the query embedding) + `apply_filters` (SQL facets) → candidate set, ordered by Vitrine Score.
3. **Reason & present (LLM, streamed):** explain *why* each result fits; offer `compare_products` on request.
4. Optionally `recommend_similar` from embeddings.

**Tools:** `embed_text`, `semantic_search`, `apply_filters`, `get_listing`, `compare_products`, `recommend_similar`.

**Memory:** session context (conversation + shown results); optional buyer preference profile.

**Guardrails:** only surfaces *live* listings; never fabricates products/prices — always grounded in retrieved rows (RAG); cites listing IDs. Budget-capped per session.

---

## 4. Pricing & Pitch Agent

**Role:** Seller co-pilot — pricing, packaging into tiers, listing copy, and a lightweight business model. Hits the *Business Automation* category.

**Triggers:** seller "Help me price / write this" actions in the wizard (on-demand, interactive).

**Workflow:**
1. `market_comps`: pull comparable live listings (category + embedding similarity) for price anchoring.
2. **Suggest tiers (LLM):** `suggest_tiers` → e.g., Demo (free) / Standard / Pro / Custom-build (advance), with rationale.
3. **Draft copy (LLM):** `draft_copy` → tagline, short + long description, feature highlights, upsell/advance-payment strategy.
4. Returns suggestions the seller accepts/edits (never auto-applied).

**Tools:** `market_comps`, `get_listing`, `suggest_tiers`, `draft_copy`.

**Memory:** category price distributions, conversion stats (Postgres).

**Guardrails:** advisory only; no auto-pricing; grounds comps in real data; flags when comps are too sparse to be confident.

---

## 5. Curation & Ranking Agent

**Role:** Compute the **Vitrine Score** and assign listings to curated sections. Keeps the gallery high-quality and discoverable.

**Triggers:** `listing.verified`, `review.created`, `listing.updated`, nightly `cron.recompute_scores`.

**Workflow:**
1. **Feature assembly (deterministic):** `compute_features` → completeness %, verification status, Bayesian rating, demo-health uptime, recency decay, engagement (views/launches/conversions).
2. **UI quality (vision, once + cached):** `vision_score_ui` scores the preview screenshot for visual quality/polish; cached by image hash so it runs once.
3. **Score:** weighted blend (weights in config; see [README §6](./README.md#6-the-vitrine-score-ai-ranking-model)) → 0–100.
4. **Section assignment:** `rank_and_section` → "Top of the Gallery", "Best UI", "Built this week", category leaderboards.
5. Emit `listing.scored`.

**Tools:** `compute_features` (deterministic), `bayesian_rating`, `vision_score_ui`, `rank_and_section`.

**Memory:** rolling engagement aggregates; cached UI scores; tunable weight config.

**Guardrails:** mostly deterministic to stay cheap; vision call is once-per-image; score is explainable (stores the per-signal breakdown for transparency + admin audit).

---

## 5.1. Buyer Representative Agent

**Role:** Represent the buyer to negotiate pricing, terms, custom milestones, or bundle deals with the seller/developer, fully context-aware of the user's order details and transaction history.

**Triggers:** Buyer activates negotiation on a listing.

**Workflow:**
1. **Load Context:** Retrieve listing details, buyer-defined constraints (target budget, maximum budget, timeline requirements), previous messages, and **active/past order details and purchase history** for this specific buyer.
2. **Formulate Negotiation Strategy:** Evaluate the listing's market comps, seller's tier/rating, and buyer's order history to determine a reasonable offer and contextual arguments (e.g., volume discount for returning buyers).
3. **Draft Message:** Call `draft_negotiation_message` with order details and historical context to generate the next response in the chat thread.
4. **Respond to Seller:** Post the message to the chat channel. The seller can reply directly, triggering the agent to evaluate the response and draft a counter-offer.

**Tools:** `get_listing`, `draft_negotiation_message`, `market_comps`.

**Memory:** Buyer preferences, active negotiation parameters (budget, target price), chat history, and past order ledger summaries.

**Guardrails:**
- Buyers must be logged in to spawn representatives.
- Enforce a strict limit of **maximum 2 active representatives** per buyer at any time.
- The agent cannot exceed the buyer's declared maximum budget.
- The agent must tailor arguments based on verified order logs and never fabricate past purchases.
- Cleanly disclose to the seller that they are interacting with an AI agent representative of the buyer.

---

## 5.2. Feature Cost Estimator Agent

**Role:** Analyze requested additional features/customizations for a software listing and estimate development cost, effort, and recommended charges.

**Triggers:** Buyer submits a custom feature request on a listing.

**Workflow:**
1. **Analyze Request:** Parse the buyer's detailed description of the requested customization.
2. **Reference Listing Stack:** Load the listing's spec sheet (frameworks, databases, third-party integrations) to evaluate implementation complexity.
3. **Estimate Cost:** Run `estimate_feature_cost` to calculate development hours, complexity weight, and recommend a dollar charge.
4. **Suggest Milestones:** Propose structured payment milestones for high-value customization scopes.
5. **Persist Suggestion:** Write the estimated invoice fields to the catalog database for developer/seller review and approval.

**Tools:** `get_listing`, `estimate_feature_cost`.

**Memory:** Context of the target software, standard engineering task rates, and prior feature requests.

**Guardrails:**
- Costs are recommendations only; both seller and buyer must explicitly approve the estimate before a milestone contract is created.
- Detects impossible/malicious requests and flags them for human review rather than generating an estimate.

---

## 6. Shared tool catalogue (typed functions)

> All tools are server-side functions exposed to the model via OpenAI tool calling. Schemas live in `backend/ai/tools/`. Agents may only call tools listed in their section.

| Tool | Kind | Summary |
|---|---|---|
| `fetch_repo_tree(repo_url)` | deterministic | GitHub tree (cached, size-capped) |
| `fetch_file(repo_url, path)` | deterministic | single file contents |
| `read_readme(repo_url \| text)` | deterministic | normalized README |
| `detect_stack(files)` | deterministic | languages/frameworks/tests/deploy from manifests |
| `embed_text(text)` | OpenAI | `text-embedding-3-small` vector |
| `semantic_search(vector, filters)` | deterministic | pgvector ANN + facets |
| `apply_filters(filters)` | deterministic | SQL facet query |
| `get_listing(id)` | deterministic | fetch listing row |
| `compare_products(ids[])` | deterministic | side-by-side matrix |
| `recommend_similar(id)` | deterministic | nearest neighbours |
| `check_demo_health(url)` | deterministic | preview uptime/render check |
| `cross_check_claims(spec)` | LLM-assisted | claims vs. detected reality |
| `license_lookup(repo)` | deterministic | license file vs. declared |
| `market_comps(category, vector)` | deterministic | comparable listings for pricing |
| `suggest_tiers(context)` | LLM | tiered pricing proposal |
| `draft_copy(context)` | LLM | listing copy |
| `compute_features(id)` | deterministic | ranking signals |
| `bayesian_rating(id)` | deterministic | smoothed rating |
| `vision_score_ui(image)` | OpenAI vision | UI quality 0–1 (cached) |
| `rank_and_section(id, score)` | deterministic | assign sections |
| `write_listing_fields(id, fields)` | deterministic | persist form fields |
| `submit_verdict(id, verdict)` | deterministic | persist verification verdict |
| `flag_listing(id, reason)` | deterministic | escalate to admin |
| `draft_negotiation_message(buyer_id, seller_id, listing_id, context, order_details?)` | LLM | Drafts next negotiation message based on bounds, chat history, and buyer's order context |
| `estimate_feature_cost(listing_id, feature_description)` | LLM-assisted | Evaluates feature request against codebase specs and estimates pricing |

---

## 7. Orchestration & workflow engineering

### Event bus (Redis Streams)
```
listing.created ──▶ Repo-Intake ──▶ listing.enriched ──▶ Verification ──┬─▶ listing.verified ──▶ Curation ──▶ listing.scored ──▶ LIVE
                                                                        └─▶ listing.flagged ──▶ admin queue
order.paid ──▶ Notification (email/in-app to developer: "deliver the full app")
review.created / listing.updated / cron.nightly ──▶ Curation (recompute)
```

- **Workers** are stateless; each subscribes to a stream consumer group → at-least-once delivery + acks.
- **Idempotency keys** (`{event_id}:{input_hash}`) prevent double-spend of tokens on retries.
- **The AI Orchestration service** owns: budget enforcement, retries/backoff, dead-letter handling, the OpenAI client, prompt assembly (loads the right AGENTS.md section), and the cost meter.

### Memory model
| Scope | Store | Examples |
|---|---|---|
| **Run scratch** (short-term) | in-process / Redis (TTL) | assembled repo context, conversation turns |
| **Result cache** | Redis (content-hash key) | Intake output, UI vision scores |
| **Long-term project memory** | PostgreSQL (+ pgvector) | taxonomy embeddings, market comps, fraud patterns, seller trust, engagement aggregates |

### Skills / capabilities (`skills.md` equivalent)
Each tool above is a registered **skill**; an agent's section declares which skills it may use. Skills are versioned and individually testable, so the fleet is composable and auditable.

### Failure & degradation
- OpenAI error / timeout → exponential backoff → fall back to **heuristic-only** result + `needs_human_review`.
- Budget exceeded → same graceful degradation; admin alerted.
- Bad/invalid model output → schema-reject → retry → escalate.

---

## 8. Configuration (env)

| Var | Default | Purpose |
|---|---|---|
| `OPENAI_API_KEY` | — | server-side key |
| `OPENAI_MODEL` | `gpt-4o-mini` | reasoning model |
| `OPENAI_EMBED_MODEL` | `text-embedding-3-small` | embeddings |
| `OPENAI_DAILY_LIMIT_USD` | `5` | global kill-switch |
| `AGENT_MAX_RETRIES` | `2` | schema/transient retries |
| `AGENT_RUN_BUDGET_TOKENS` | `20000` | per-run cap |
| `VITRINE_SCORE_WEIGHTS` | see README §6 | ranking weights |

> See [backend.md](./backend.md) for how the Orchestration service, tools, and stores are implemented and deployed.

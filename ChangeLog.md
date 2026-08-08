# Changelog

## Unreleased — Run the stack locally, publish a listing without losing half of it

Working tree on top of `7f579ae`. Not yet committed.

This began as "get the project running" and turned into a run of bugs that only
appear once a **real** listing exists. Every fixture in the seed is complete —
populated tiers, a five-bucket rating histogram, absolute Unsplash cover URLs.
A listing a person actually creates has none of those, and four separate parts
of the app assumed otherwise. Publishing one end to end is what surfaced them.

---

### 1. Local environment

**`.venv` rebuilt on Python 3.12.** The tree shipped a 3.14 virtualenv holding
nothing but pip. Several pins — `cryptography==43.*`, `asyncpg==0.30.*`,
`greenlet==3.*` — publish no cp314 wheels, so a bootstrap on 3.14 falls back to
source builds and needs a Rust toolchain. All 54 packages install from wheels on
3.12.

Worth knowing: `run.py` picks its interpreter via
`shutil.which("python3.11") or sys.executable`, which on Windows finds neither
and lands back on 3.14. Invoke the venv's own interpreter
(`.\.venv\Scripts\python.exe run.py`) rather than a bare `python`.

`SECRET_KEY` was still the shipped `change-me-…` placeholder. Replaced with a
generated value — safe to rotate here only because `admin_configs.api_keys` was
`[]`, so nothing encrypted was invalidated.

---

### 2. Login refused a correct password

**`backend/shared/schemas/auth.py`, `frontend/src/app/pages/Auth.tsx`**

`admin@vitrine.io` / `admin` returned 401 through the UI while the same
credentials returned 200 through the API. The user row is matched on an **exact
string**, and the email box rendered as `type="text"` with no `autoCapitalize` —
so a touch keyboard sends `Admin@vitrine.io`, which is a different account.
`Auth.tsx` reports any 401 as "Incorrect email or password", making a
capitalisation artefact look like a wrong password.

- A shared `_EmailNormalized` base lowercases and strips the address.
  `SignupIn` and `LoginIn` both inherit it, so an address can never be *stored*
  in a form login would fail to find. One point covers signup, login and admin
  login, and fixes it for every client rather than only this UI.
- Email inputs are now `type="email"` with `autoCapitalize="none"`,
  `autoCorrect="off"`, `spellCheck={false}` and proper `autoComplete`.

The password is deliberately **not** trimmed — silently stripping whitespace
from a password weakens it. `admin ` is still rejected.

---

### 3. A local model provider, so the fleet runs without a key

**`backend/shared/settings.py`, `backend/ai/client.py`, `.env.example`**

Neither hosted key could serve: OpenAI returns `429 You have no credits
remaining` (there is no free API tier), and the Gemini key is an Antigravity
credential — it lists models fine but every `generateContent` **and**
`embedContent` returns `403 PERMISSION_DENIED`. Ollama is appended **after**
both, so a working key always wins and local inference is the safety net.

Four things that each had to be right for this to work at all:

- **Local calls cost nothing.** `estimate_cost` prices unknown model names at
  the `gpt-4o-mini` rate, so running on Ollama would have marched
  `OPENAI_DAILY_LIMIT_USD` toward its cap and eventually refused to answer.
  `FREE_PROVIDERS` zeroes it.
- **A separate 300s timeout** for local calls; the shared 30s ceiling kills a
  cold start while weights load.
- **Embeddings zero-pad 768 → 1536.** `nomic-embed-text` is 768-dim and the
  store is 1536; the old code silently dropped any mismatched width. Padding
  preserves cosine similarity *exactly* — zeros contribute nothing to either
  the dot product or the magnitudes.
- `json_mode` extended to the Ollama endpoint.

**Model choice is a measurement, not a preference.** On a 4 GB GTX 1050 Ti:

| Model | Placement | Speed | Tool calls |
|---|---|---|---|
| `qwen3:4b` | 4.4 GB — 44% on CPU | 3m36s / 20 tok | answer lands in `reasoning`, `content` empty |
| `llama3.2:3b` | fits GPU | 7.8s | **malformed, `tool_calls: null`** |
| **`qwen2.5:3b`** | 2.4 GB, **100% GPU** | 1.7s | proper `tool_calls` |

Repo-Intake and Verification dispatch typed tools, so a model that cannot emit
`tool_calls` breaks them regardless of how fast it is. Gemma was never a
candidate for the same reason. Both rejects are recorded in `.env.example` so
the choice is not silently undone later.

**Consequence: the catalogue had to be re-embedded.** Every stored vector was
written by `_stub_embedding` while no provider worked, so a real query scored
against them is noise — search looked functional and ranked nothing. All 46
listings rebuilt; `mobile app for tracking expenses` now returns Pocket Ledger
at 0.748.

---

### 4. The product page crashed on every new listing

**`frontend/src/app/pages/ProductPage.tsx`** and four components

`/#/p/<slug>` rendered the error boundary while the API returned a valid 200.

```js
product.tiers?.[tier].price.toLocaleString()   // tiers: [] -> throws
```

The `?.` guards `tiers` being null but **not the index being out of range**, and
`tier` state defaults to `1`. `ratingDistribution[5 - star]` had the same shape.
Both are the normal state of a freshly published listing.

- `tierIndex` is clamped into range; `buyPrice` falls back to the listing's own
  price, so the button reads `Buy · $89` instead of throwing. With no tiers the
  box becomes a "Price / One-time purchase" row rather than vanishing — the buy
  path stays visually anchored.
- Rating bars render only when there are reviews *and* a non-zero distribution;
  otherwise the heading reads "Not yet rated".
- Empty spec / SDLC / revenue sections state "not documented yet" instead of
  rendering empty containers.

Three latent crashes of the same family, not yet hit but reachable from the same
data: `Badge` destructured `undefined` on an unrecognised badge string and took
the page down, `VitrineScoreRing` emitted `strokeDashoffset="NaN"` on a null
score (silently dropping the whole arc), and `ProductCard` had unguarded
`badges`/`tags`/`price`.

---

### 5. Uploaded images never displayed

**`frontend/src/app/components/ImageWithFallback.tsx`** + 13 call sites

The upload itself always worked — file on disk, `cover` set, backend serving it
at 200. Uploaded media is a **relative** `/files/…` path while every seeded
listing uses an **absolute** Unsplash URL, and Vite proxies only `/api`. So the
browser asked :5173 for the file and got a 404. `mediaUrl()` existed for exactly
this and was not called on the display path.

`ImageWithFallback` now resolves `src` through `mediaUrl()` internally, which
repairs `ProductCard` and every other consumer at once; absolute `http(s):` and
`data:` URLs pass through untouched. The remaining raw `<img>` tags were wrapped
individually across `ConciergePanel`, `CuratorConsole`, `Inbox`, `Modals`,
`OrderDetail`, `Home`, `AdminDashboard`, `BuyerDashboard` and `SellerDashboard`.

Two incidental bugs fixed in passing: the error state was a sticky boolean, so
once any image failed the component kept showing the placeholder for later valid
images (visible when navigating between products); it now records *which* src
failed. And the placeholder used a hardcoded light gray — the one visual state
guaranteed to look wrong in dark mode — now a theme token.

---

### 6. Pricing tiers were discarded on the way to the database

**`backend/services/catalog/app.py`, `frontend/src/app/lib/store.ts`,
`ListingEditor.tsx`, `SellerDashboard.tsx`, `Sell.tsx`**

A published listing came back with `"tiers": []` even though the seller had run
the Pricing agent. **Four independent drops on one path**, each sufficient on
its own:

1. `PATCH /listings/{id}` had **no `tiers` branch**. It maps ~20 keys onto the
   `listings` row, but `listing_tiers` is a separate table and was never
   touched — a `tiers` array was accepted and silently discarded. This is why
   `price_cents` survived while the ladder did not.
2. `store.ts` `upsertListing` never sent `tiers`.
3. `ListingEditor.tsx` never read the agent's tiers — `aiRedraft` used only
   `tagline` / `short_description` / `long_description` and threw the ladder
   away in the browser.
4. `Sell.tsx` — the listing wizard — displayed the agent's ladder at step 4 and
   then omitted it from `handleSubmit`. Its local tier shape was also lossy,
   keeping `features[0]` as a `note` and discarding the rest; it now carries the
   full tier and derives the note at render time.

Backend hardening: `_tier_rows()` validates name/price/features, caps at 8 tiers
and 12 features, and truncates to the column width. Validation runs **before**
any field mutation, so a bad tier rejects the whole patch instead of
half-applying it. `repost_listing` reuses the same validator — it previously did
`t["name"]` and would 500 on a malformed agent tier.

`SellerDashboard.aiDraftNew` seeded three **invented** tiers
(`Source $49` / `Source + Setup $129` / `Bespoke $329`). Harmless while tiers
never persisted; now it would write pricing the seller never chose. Seeds `[]`.

---

### 7. Seller chooses AI pricing or sets it by hand

**`frontend/src/app/components/ListingEditor.tsx`**

A segmented choice in the editor:

- **AI path** — the proposal renders in a card marked *"Proposed · not applied
  yet"*, every field editable **before** accepting. Nothing reaches
  `draft.tiers` without an explicit "Use these tiers" click, per the AGENTS.md
  §4 advisory contract.
- **Manual path** — add/remove/edit tiers; "recommended" behaves as a radio.

`askPricing` checks `res.stub` **before** reading `suggested_tiers`. This matters
more than it looks: on a stub, `pricing.run()` still returns a fully populated
*fabricated* fallback ladder, so without the guard the seller would be shown
invented pricing as though the agent had produced it — exactly what AGENTS.md §7
forbids.

---

### 8. One dead provider no longer floods the log

**`backend/ai/client.py`**

Every AI call printed the full provider error blob:

```
[ai] fell back to ollama/qwen2.5:3b after: Error code: 403 - [{'error': ...}]
```

This was not a malfunction — it is the fallback chain working — but a dead
provider fails the *same* way forever, and a raw `print()` per call drowned the
real logs.

All `print()` calls are now a module logger (`vitrine.ai.client`), matching the
existing `vitrine.*` convention. Failures are keyed by *kind* (provider +
exception class + status + truncated message): first occurrence at WARNING with
the readable message, identical repeats at DEBUG, and one compact reminder every
50 occurrences or 15 minutes. A **different** error hashes differently and is
reported immediately, so a new fault is never masked. The full JSON payload
remains available at DEBUG, and a `_scrub()` pass redacts credential-shaped
tokens before any text reaches a log record.

Ten consecutive calls now produce five lines once, then silence. The run also
surfaced two facts the single-line print had hidden: `gpt-4-turbo` 404s on this
key, and the Gemini models split into 429-quota and 403-denied groups rather
than failing uniformly.

---

### 9. The curator's featured picks were visible to nobody but the curator

**`backend/services/catalog/app.py`, `store.ts`, `Home.tsx`, `Browse.tsx`**

Reported as "Featured pieces is not showing the selected listing". The
selection mechanism was fine — three picks were stored and all three resolved
to live listings. The delivery was not.

`featuredIds` was only ever read from `GET /admin/config`, which is role-gated
to admins, and the store only fetches it `if (user.role === 'admin')`. So a
signed-out visitor or a buyer always held the default `[]`, the home hero hit
its "top 3 by Vitrine Score" fallback, and the curator's choice changed nothing
about the storefront — while looking perfectly correct in the console that set
it. An admin testing their own change was the one person who could not see the
bug.

- `GET /public-config` (already unauthenticated, already consumed by the store
  for categories and frameworks) now also returns `featuredIds`. Only `live`
  listings are emitted — a draft or archived pick must not be advertised, and
  the storefront cannot render one — and curator order is preserved, because it
  is an editorial ordering rather than a set.
- The store gained a top-level `featuredIds`, matching how `categories` and
  `frameworks` already flow. `updateAdminConfig` already re-calls
  `loadPublicConfig()`, so a curator's toggle refreshes the storefront with no
  extra wiring.
- `Home.tsx` reads the public field instead of `adminConfig`. Its score-based
  fallback stays: the hero is the landing page's centrepiece and must never be
  empty.

**The Hero Showcase.** `Browse.tsx` never consumed the picks at all, so the
gallery had no featured section. There is now one at the top of the gallery —
eyebrow "Chosen by the house", heading "Hero Showcase", the picks rendered as
full `ProductCard`s in curator order.

Two deliberate differences from the home hero:

- **It does not fall back to top-by-score.** An empty showcase is a truthful
  "the house has not chosen anything"; a shelf labelled as curated must not
  quietly fill itself with an algorithm's picks.
- **It hides as soon as the visitor starts steering** — any active filter, or
  any page past the first. Someone who narrowed to "Games under $50" should not
  be shown three unrelated pieces above their results.

Featured pieces still appear in the grid below, so the "43 pieces on display"
count stays honest and nothing is hidden from a filtered search.

Six tests in `backend/tests/test_public_config_featured.py` cover anonymous
access, order preservation under reordering, withholding non-live picks,
surviving stale/malformed IDs without a 500, and the public payload never
carrying the API keys and system prompts that live in the same table.

---

### 10. Frontend typecheck was broken before any of this

**`frontend/tsconfig.json`**

`tsc --noEmit` exited 2 on `TS5101: Option 'baseUrl' is deprecated` under the
pinned TypeScript 6.0.3 — reproduced on a clean tree, so it predates this work.
`baseUrl` was dead config: there is not one `@/` import or baseUrl-relative
import in `src/`. Removed rather than silenced with `ignoreDeprecations`, since
TypeScript 7 drops the option outright. `paths` is kept and still resolves
(relative to the tsconfig, since TS 5), matching the alias in `vite.config.ts`.

---

### 11. Operator scripts have a home

`backend/scripts/` — `check_ai` (verifies every provider, embedding, vision and
agent) and `reembed` (rebuilds the catalogue's vectors). Run as
`python -m backend.scripts.check_ai`, matching the existing
`python -m backend.seed` convention. They sit apart from `seed.py` deliberately:
that one *is* invoked by `run.py`, the Docker entrypoint and `run_onVM.py`,
while these are on-demand diagnostics wired into no runtime path. README §12
updated.

---

## Verification

- **Backend — 80 passing** (`pytest backend/tests -q`), 14 new: 8 in
  `test_listing_tiers.py` (tier round-trip, copy-only patch leaving tiers
  intact, nameless and negative-price tiers rejected with 422 and the existing
  ladder untouched) and 6 in `test_public_config_featured.py`.
- **Frontend** — `tsc --noEmit` clean (`noUnusedLocals`/`noUnusedParameters`
  both on), `npm run build` succeeds, `vitest run` 3 passing.
  `ProductPage.test.tsx` renders the verbatim crashing payload plus a listing
  missing every optional collection, asserting `Buy · $89`, no
  `$undefined`/`NaN`, and `/files/…` resolving to the API origin.
- **End to end over HTTP** — fresh seller → create → `POST /ai/pricing`
  (`stub: false`, real local-model output) → accept with a hand-edited price →
  submit → tiers present on read-back. The wizard payload shape was verified
  separately against `listing_tiers`, including cascade cleanup on delete.
- **AI chain** — `check_ai` reports OpenAI and Gemini dead, Ollama serving,
  `client.embed` returning a real vector rather than the stub.

## Known gaps

- **Vision scoring is not real.** `qwen2.5:3b` is not multimodal, so
  `vision_score_ui` returns its heuristic 0.7 — 15% of the Vitrine Score weight
  is currently a constant. A small local vision model would close this.
- **Tier ordering is by price, not authored order.** `listing_tiers` has no
  `position` column, so read order was undefined and only *looked* stable
  (SQLite rowid). `ORDER BY price_cents, id` was chosen over a schema migration
  against the live `vitrine.db`; a manual ladder therefore re-sorts by price on
  save.
- **Multiple `recommended` tiers are stored faithfully.** The local model
  returned two in one run. The manual editor's radio behaviour lets a seller fix
  it, but the invariant is not enforced server-side.
- **`repost_listing` still auto-applies agent tiers**, overwriting a manual
  ladder. Read as consent from the explicit "repost & optimize with AI" click,
  but it sits awkwardly against the advisory rule.
- Listings published **before** this change keep `tiers: []`. Nothing
  backfills them — the page now renders them correctly as a single one-time
  price, and the seller can add a ladder in the editor.

---

## b502be4 — Seed a real catalogue, fix AI drafting, free drafts from the quota

Range: `58a92ce..b502be4` on `main`.

Six issues were reported together: the platform shipped with no demo data, the
"AI-draft a listing" dialog was slow to appear, the draft form had nowhere to
put a repository link, drafts consumed listing slots and could not be deleted,
and there was no seeded admin account. A full listing → approval → purchase run
was requested as the acceptance check.

---

### 1. Demo data — a catalogue that looks like a marketplace

**`backend/seed.py`**

The seed held 36 entries that were, in substance, the same product: a web app
codebase, MIT licensed, for-profit, all pointing at one shared demo URL. It now
holds **44 live listings across 21 categories**, spanning kinds of software the
seed previously had none of:

| Kind | Examples |
|---|---|
| CLI / developer tools | Tessera (Rust), Driftwood (Go), Rivet |
| Mobile | Cairn (Flutter), Pocket Ledger (React Native) |
| Desktop | Verso (Electron), Northwind Desk (Tauri) |
| Browser extension | Inkwell (Manifest V3) |
| Games | Foundry Arcade (Godot 4) |
| IoT / firmware | Meadow (ESP32, embassy-rs) |
| Data & ML | Tidepool (PyTorch), Grainsight (dbt/Prefect) |
| Design systems | Bezel, Palette OS (Figma plugin) |
| Education | Lantern Learn (Django LMS) |
| Infrastructure | Switchyard, Beacon Status |

Structural changes to support that:

- Listing specs moved from positional 10-tuples to an `L(...)` helper returning
  dicts. Adding a field no longer means editing every row.
- Every entry carries a **repository URL**.
- **Licences vary** — MIT, Apache-2.0, AGPL-3.0, GPL-3.0, BSD-3-Clause,
  Proprietary — as do business models (for-profit, open-source, non-profit).
- **Tech stacks are per-listing** rather than derived from one framework field.
- `CATEGORIES` and `FRAMEWORKS` are seeded into admin config, so the storefront
  facet lists match what the catalogue actually contains (21 and 20 entries).
- `_add_listing` takes a `status` parameter; drafts skip tiers, ratings and
  review counts.

**Honesty fix.** Twelve entries have `demo=None`, because a CLI, a firmware
image and a mobile binary have no hosted preview. That flows through to
`hasLiveDemo`, and such listings no longer receive the `live-demo` badge.

**Cover images.** New categories alias onto the eleven existing verified
Unsplash URLs rather than inventing photo IDs that would 404. Swap in real art
per key when it exists — see the comment on `COVERS.update`.

**`frontend/src/app/pages/ProductPage.tsx`**

The hero carried a hardcoded "live demo" label on every listing. It is now
gated on `product.hasLiveDemo`, so the catalogue stops promising a demo that
cannot exist.

---

### 2. Admin account

Already present in the seed and working — `admin@vitrine.io` / `admin`, role
`admin`. No code change was needed; the seed simply had not been run. The seed
output now marks the row explicitly as the curator console login.

Full set (password = the email's local part):

| Email | Role | Identity |
|---|---|---|
| `admin@vitrine.io` | admin | Vitrine Curator |
| `june@vitrine.io` | buyer | June Park |
| `marco@vitrine.io` | buyer | Marco Rivers |
| `sana@vitrine.io` | buyer | Sana Iqbal |
| `maker@vitrine.io` | seller | Atelier Foxglove — Studio plan, 10 listings |
| `dev@vitrine.io` | seller | Studio Korr — Atelier plan, 16 listings |
| `studio@vitrine.io` | seller | Studio Vellum — Maison plan, 18 listings |

Sellers sit on different plans deliberately: Foxglove is at 10/10 and is the
fixture that exercises the quota behaviour below.

---

### 3. "AI-draft a listing" opened slowly

**`frontend/src/app/pages/dashboards/SellerDashboard.tsx`**

`aiDraftNew` awaited `createListing`, then `updateListing`, then a full
`loadData()` before rendering anything — so the dialog appeared seconds after
the click.

It now opens on the same tick. The create still fires immediately, but the
editor receives the **promise of the listing id** (`resolveId`) rather than
blocking on it, and every write inside the editor awaits that promise first.
No request is ever addressed to the placeholder id.

---

### 4. AI drafting had nowhere for a repository link

**`frontend/src/app/components/ListingEditor.tsx`**

A **Links** section adds *Repository URL* and *Demo URL* fields, with
placeholders and a hint explaining what each unlocks.

The drafting button now routes to one of two agents:

- **Repository URL present** → runs **Repo-Intake** (`AGENTS.md` §1), which
  reads the repo and fills the whole form sheet — stack, spec, description,
  tags. This is the path sellers expect from "AI-draft" and it was unreachable
  from this editor, because there was no field to put a repository in.
- **No repository URL** → falls back to Pricing & Pitch, which drafts copy from
  the name and category alone — all it can honestly do. The success toast says
  so and points at the repo field.

Supporting changes: staged progress labels ("Reading the repository…"), a
failure branch when the agent returns `stub` or writes no fields, `save()` made
async with error handling for the case where the background create failed, and
a "saving draft…" indicator while the row is being created.

**Backend — the URL now survives the run**

`listings.repo_url` did not exist. The URL lived only inside the event payload,
so the seller reopened the editor to an empty field and a re-run had nothing to
work from.

- `backend/shared/models.py` — `repo_url` column (`String(512)`, nullable).
- `backend/migrations/versions/a1b2c3d4e5f6_add_listing_repo_url.py` — **new
  migration.** `run.py` executes `alembic upgrade head` on start, so the column
  needed a revision, not just a model change. Verified to apply on a fresh DB.
- `backend/shared/schemas/listing.py`, `backend/services/catalog/serializers.py`
  — `repoUrl` on `ProductOut`.
- `backend/services/catalog/app.py` — `PATCH /listings/{id}` accepts
  `repo_url`/`repoUrl`; `POST /listings/{id}/intake` persists it before
  dispatching.
- `backend/ai/app.py` — `POST /ai/intake` persists it before the run.

---

### 5. Drafts consumed listing slots and could not be deleted

**Backend — `backend/services/catalog/app.py`**

Two changes, the second found by the end-to-end run:

1. `_ACTIVE_LISTING_STATUSES` no longer includes `draft`, so drafts are not
   counted.
2. **The quota moved from create to submit.** Excluding drafts from the *count*
   was not sufficient: `POST /listings` still refused at quota, and every
   listing is born a draft — so a seller at their limit could not start
   anything at all. Creation is now always allowed; the slot is claimed at
   `POST /listings/{id}/submit`, which is where a draft actually becomes
   inventory. Re-submitting something already in the pipeline is a no-op
   against the quota. Admins remain exempt. The refusal message names the limit
   and the remedy.

**Frontend — `SellerDashboard.tsx`**

- A dedicated **Drafts** tab, separate from Listings, with a banner stating
  drafts hold no slot.
- **Delete** on every row, with a confirmation whose wording differs for a
  draft ("discard") and a published listing ("buyers will no longer see it").
- A quota bar on the Listings tab reading `used / limit`, turning red at the
  cap, noting how many drafts are excluded, and offering an upgrade link.
- **Submit for review** on draft rows, disabled with an explanatory tooltip
  when the seller is at quota — matching the new backend rule.
- The duplicated row markup was extracted into a shared `ListingRow` component
  used by both lanes.

**Frontend — `lib/store.ts`**

`paused` and `archived` no longer collapse into `draft` in `STATUS_MAP`. The
backend still counts a paused listing against the quota, so folding the two
together made the dashboard file paused work under "drafts" and promise a free
slot the API would refuse. `Listing['status']` gained both values.
`upsertListing` now sends `repo_url` and `demo_url`.

---

### 6. Admin queue had two identical X buttons

**`frontend/src/app/pages/dashboards/AdminDashboard.tsx`**

Reject and Delete both rendered `<X size={14} />` with identical hover styling.
Only the invisible `aria-label` distinguished a reversible verdict from
permanent destruction, and they sat adjacent. Delete now uses `Trash2`, the
icon already used for delete in the seller dashboard, curator console and
listing editor.

---

## Verification

**Tests — 66 passing** (`python -m pytest backend/tests -q`), five of them new
in `backend/tests/test_listing_quota_and_repo.py`:

- drafts do not consume the plan quota
- the quota is charged on submit, not on create
- submit succeeds when a slot is free, with drafts in the way
- `repo_url` round-trips through `PATCH`
- the intake trigger persists `repo_url`

**Frontend** — `tsc --noEmit` clean (`noUnusedLocals` and `noUnusedParameters`
are both on) and `npm run build` succeeds.

**Migration** — applies to an empty database; `listings.repo_url` present,
revision `a1b2c3d4e5f6`.

**End-to-end, against a live gateway** — every step passed:

1. Seller, admin and buyer authenticate
2. Catalogue serves 43 live listings (44 minus the deliberately expired
   *Quiet Hours* fixture) across 21 categories; all carry repo URLs; 12 report
   no live demo
3. A seller at 10/10 can still create a draft — and is refused on submit, with
   the limit named
4. Seller lists a piece; repo URL persists through `PATCH`
5. Submit moves it to `review`; **checkout is refused with 409 before approval**
6. Admin sees it in the verification queue and approves it
7. Buyer checks out — $39.78 charged ($39 + 2% processing), $2.73 platform take
   honouring the seller's Atelier 5% rate
8. Seller marks it delivered
9. Seller deletes their own draft

---

## Known gaps

- The repo-driven drafting path is verified for routing and persistence, but
  the **agent's output quality on a real repository was not exercised** — that
  needs a provider key and a public repo. `OPENAI_API_KEY` and `GEMINI_API_KEY`
  are both empty in `.env`; until one is set, agent calls return `stub=True`
  and the UI reports the agent as unavailable.
- New categories **reuse existing cover photographs**. Functional, but several
  categories share an image.
- In the admin queue, **reject still fires without confirmation** while delete
  asks — the less severe action is the unguarded one. All four row buttons also
  render regardless of listing state, so already-live listings still offer
  "Approve" (a harmless no-op).
- **`vitrine.db` is committed to the repository** and contains the seeded
  accounts, including an admin with a known password. This predates these
  changes and is reasonable for a demo fixture, but it is a live credential in
  version control if the project is ever deployed from this tree.

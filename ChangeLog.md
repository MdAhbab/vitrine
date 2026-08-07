# Changelog

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

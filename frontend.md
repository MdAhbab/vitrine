# frontend.md — Build Prompt for **Vitrine** (paste into Claude)

> **How to use this file:** copy everything from the line `===== BEGIN BUILD PROMPT =====` to the end into Claude (Claude Code / claude.ai). It is a complete, self-contained brief to design and build the Vitrine storefront. It assumes the backend described in [backend.md](./backend.md); where the backend isn't running, build against the typed mock API layer described below so the UI is fully demoable on its own.

---

===== BEGIN BUILD PROMPT =====

You are designing and building the front end for **Vitrine** — a *boutique* software marketplace where every product ships with a **live, runnable preview** ("try the software, then own it"). This is **not** a generic app-store grid. It should feel like a curated design gallery / premium boutique: confident, editorial, calm, and expensive. A human designer with great taste made this — **avoid the "AI-generated template" look** (no purple-blue gradients everywhere, no emoji-as-icons, no clip-art, no generic SaaS hero with three feature cards).

## 0. Tech & non-negotiables
- **React 18 + Vite + TypeScript + Tailwind CSS.** State: Zustand. Data: TanStack Query. Animation: Framer Motion. Icons: a single consistent line set (Lucide). Forms: react-hook-form + zod.
- **Dark mode AND light mode**, both first-class and equally polished. Toggle persisted to `localStorage`, respects `prefers-color-scheme` on first load. Use CSS variables for theme tokens (below) so both modes share one component layer.
- **Accessible:** semantic HTML, focus-visible rings, keyboard navigable, WCAG AA contrast in both themes, `prefers-reduced-motion` respected, alt text.
- **Responsive:** mobile-first, beautiful at 375px, 768px, 1280px, 1536px.
- **Performance:** route-level code splitting, lazy images, skeletons (not spinners), no layout shift.
- Build it so it runs standalone on mock data, then swaps to the real API by flipping `VITE_USE_MOCKS=false`.

## 1. Brand & art direction
**Name:** Vitrine. **Wordmark:** set in a refined serif or a high-contrast grotesk, letter-spaced, lowercase optional. **Tagline:** "Try the software. Then own it."

**Personality:** boutique gallery × developer-grade precision. Think a luxury watch boutique that happens to sell software. Generous negative space, strong typographic hierarchy, restrained color, one tasteful accent, slow and deliberate motion.

**Logo mark:** a minimal "display window" glyph — a thin rounded rectangle with a subtle inner frame (the *vitrine*), optionally a small dot/play denoting "live preview". Monoline, scalable, works in one color.

### Color tokens (CSS variables; define both themes)
Lean **ink + paper + a single warm accent**. Do **not** use the default Tailwind blue/indigo/violet palette as the brand color.

```css
/* Light ("Paper") */
--bg:            #FAF8F4;   /* warm paper */
--surface:      #FFFFFF;
--surface-2:    #F1EEE8;
--border:       #E6E1D7;
--text:         #1A1714;   /* near-black ink */
--text-muted:   #6B645B;
--accent:       #B8862F;   /* muted antique gold */
--accent-ink:   #1A1714;   /* text on accent */
--success:      #3F7D5B;
--danger:       #B4452F;

/* Dark ("Ink") */
--bg:            #0E0D0C;   /* near-black, warm */
--surface:      #16140F;
--surface-2:    #1F1C16;
--border:       #2A2620;
--text:         #F3EFE7;
--text-muted:   #A39B8C;
--accent:       #D8A94A;   /* brighter gold on dark */
--accent-ink:   #14120D;
--success:      #6FBF92;
--danger:       #E0795F;
```
Map these to Tailwind via `theme.extend.colors` referencing the CSS vars (e.g. `bg-bg`, `text-text`, `border-border`, `text-accent`). Use the gold accent **sparingly** — for the active state, the "Run preview" action, the Vitrine Score ring, and small flourishes only.

### Typography
- **Display / headings:** a high-contrast serif (e.g. *Fraunces*, *Newsreader*) for editorial weight, OR a refined grotesk (*Space Grotesk*) — pick one and commit. Tight leading on large sizes.
- **Body / UI:** a clean humanist sans (e.g. *Inter*, *Geist*).
- **Code / specs / labels:** a mono (e.g. *JetBrains Mono*, *Geist Mono*) — used for technical metadata, tags, and the "spec sheet" to reinforce the dev-grade feel.
- Use a **type scale** with real hierarchy; big confident headlines, small precise metadata. Numbers (price, score) in tabular/mono.

### Texture & depth
- Soft, low-contrast shadows; **hairline 1px borders** in `--border` do most of the structural work (gallery/editorial feel).
- Optional very subtle paper grain/noise overlay at low opacity in light mode; a faint vignette in dark mode. Keep it tasteful, never busy.
- Rounded corners: medium (`rounded-xl`/`2xl`), consistent. Cards feel like framed objects.

### Motion (Framer Motion)
- Slow, eased, intentional. Page/section reveals: short fade + 8–12px rise, staggered. Hover on product cards: gentle lift + border-accent + the preview thumbnail subtly "wakes up". The **"Run preview"** action expands a device frame with a satisfying spring. Respect `prefers-reduced-motion`.

## 2. Signature UX idea (make this shine)
The defining interaction is **the live preview**. Every product card has a **"Run preview"** affordance. Activating it opens the product in a **device frame** (browser/phone toggle) embedding the live `*.vercel.app` demo in a sandboxed iframe, with a small **"live" pulse** and a demo-health dot (green/amber). This is the moment that sells the platform — make it feel like opening a vitrine case. On product pages it's the hero.

## 3. Pages / routes
1. **Home / Gallery (`/`)** — editorial hero (wordmark + tagline + one-line value prop + a single primary CTA), then curated sections rendered as horizontal editorial rails *and* a refined grid:
   - "Top of the Gallery" (highest Vitrine Score)
   - "Best UI" · "Built this week" · category leaderboards
   - A **Concierge search bar** front and center: a single elegant input ("Describe what you need…") that opens the AI Concierge.
   Not a wall of identical cards — vary rhythm with one or two large "feature" cards and editorial captions.
2. **Browse / Search (`/browse`)** — left (or top, on mobile) **facet rail**: category, subcategory, tags, price range, license, has-live-demo, theming, framework/language. Sort: Vitrine Score (default), Newest, Price, Rating. Results in a responsive masonry-ish grid with skeletons. URL-synced filters.
3. **Concierge (`/concierge` or a slide-over)** — a chat panel: user types natural language ("React dashboard with Stripe, under $40, live demo"), streamed assistant responses (SSE) with **inline product result cards** and reasons + a "compare" affordance. Feels like talking to a knowledgeable shop curator, not a chatbot widget.
4. **Product page (`/p/:slug`)** —
   - Hero: name, tagline, seller, price/tiers, **Vitrine Score ring**, verified badge, **live preview device frame** (the star).
   - **The Spec Sheet:** the technical form sheet rendered as a beautiful, scannable, mono-accented spec table grouped by section (Planning, Design, Development, Architecture, Data, Testing, Security, Deployment). AI-filled fields show a subtle "auto-filled" marker; confidence-flagged fields look intentional, not broken.
   - Screenshots gallery, long description (markdown), reviews + rating distribution, "similar products" rail, and a sticky **Buy / Pay advance** panel.
5. **Sell — New Listing wizard (`/sell/new`)** — the agentic flow:
   - Step 1: **Import** — paste a GitHub URL *or* drag-drop/upload a README/files. A tasteful "AI is reading your repo…" state (progress, not a spinner soup).
   - Step 2: **Review the auto-filled spec** — the full form sheet pre-filled; AI-filled fields marked; low-confidence fields gently highlighted for confirmation; inline editing.
   - Step 3: **Preview & media** — add the `*.vercel.app` demo URL (with a live health check), screenshots.
   - Step 4: **Price & pitch** — call the **Pricing & Pitch Agent**: suggested tiers + drafted copy the seller accepts/edits.
   - Step 5: **Submit** → verification status view.
6. **Seller dashboard (`/dashboard`)** — listings table with status + Vitrine Score, views/launches/conversion analytics (clean charts), orders + "deliver the full app" prompts, payouts ledger, webhooks.
7. **Buyer area (`/orders`, `/library`)** — purchases, advance-payment status, delivered artifacts / license keys / download links, leave-a-review.
8. **Admin (`/admin`)** — verification queue (approve / request changes / flag), agent-run cost meter + observability, category/featured management. Keep it functional but on-brand.
9. **Auth (`/login`, `/signup`)** — minimal, elegant; role select (Buyer / Developer).

## 4. Key components (build a small, consistent kit)
- `ThemeToggle` (sun/moon, animated), `Logo`, `TopNav` (transparent over hero, solidifies on scroll), `Footer`.
- `ProductCard` — framed object: primary screenshot, name, seller, price, **Vitrine Score chip**, tag row (mono), `Run preview` button, demo-health dot. Hover = lift + accent hairline.
- `PreviewFrame` — device-framed sandboxed iframe (browser/phone toggle, reload, open-in-new, live pulse, health dot, graceful "demo unavailable" state).
- `VitrineScoreRing` — circular gauge (gold), tooltip showing the per-signal breakdown (completeness, reviews, UI, demo health, recency, engagement).
- `SpecSheet` — sectioned technical table with `source`/confidence markers and mono labels.
- `FacetRail`, `SortMenu`, `SearchBar`, `ConciergePanel` (streaming chat + inline result cards).
- `Wizard` + `FormSheetEditor` (renders fields from the shared `FORM_SCHEMA`).
- `TierTable`, `BuyPanel` (purchase vs. pay-advance), `ReviewList` + `RatingBars`.
- `Badge` (Verified / Live demo / Best UI / New), `Skeleton`, `Toast`, `Modal`, `Tabs`, `Tooltip`, `EmptyState`.

## 5. Data layer & API contract
Create `src/api/` with a typed client and a **mock implementation** toggled by `VITE_USE_MOCKS`. Match [backend.md §11](./backend.md#11-api-surface):
```
GET  /listings?category&tags&sort=vitrine_score&price_max&has_demo&page
GET  /listings/:slug
POST /listings              POST /listings/:id/intake     PATCH /listings/:id
POST /ai/concierge  (SSE stream)    POST /ai/pricing      POST /ai/intake
GET  /search?q
POST /checkout             POST /orders/:id/deliver
POST /reviews              GET  /notifications
auth: /auth/signup /auth/login /auth/refresh   GET /users/me
```
Provide rich **mock data**: ~24 fictional but believable products across categories (each with screenshots via placeholder services, a Vercel-style demo URL, full spec sheet, tiers, reviews, a Vitrine Score + breakdown). Seed the Concierge mock to return sensible filtered results + streamed reasoning so the AI experience is demoable without keys.

## 6. Definition of done
- Both themes pixel-polished; toggle smooth; AA contrast verified.
- Home, Browse, Product (with working `PreviewFrame` against a real `*.vercel.app` URL), Concierge, and the Sell wizard all fully interactive on mock data.
- Feels premium and editorial — a stranger would never guess it's a hackathon build. No generic-template tells.
- Responsive, accessible, reduced-motion safe, no console errors.
- `README` in `/frontend` explaining `npm install`, `npm run dev`, the mock toggle, and the theme tokens.

Deliver clean, well-structured, typed React. Prioritize taste, hierarchy, restraint, and the **live-preview** moment above all.

===== END BUILD PROMPT =====

---

## Notes for you (not part of the prompt)
- The accent is **gold** by design — it reads "premium/boutique" and avoids the AI-template blue. If you prefer a different single accent (deep teal, oxblood, sage), change the two `--accent` vars and everything follows.
- If you want the demo to use **real** AI, point the client at the running `ai-orchestrator` (`VITE_USE_MOCKS=false`, set `VITE_API_BASE`) — Concierge will stream live results from `gpt-4o-mini`.
- Fonts suggested are Google-Fonts-available; swap freely. Commit to **one** display face.
- Keep the `PreviewFrame` sandbox attributes and host allow-list aligned with [backend.md §10](./backend.md#10-security).

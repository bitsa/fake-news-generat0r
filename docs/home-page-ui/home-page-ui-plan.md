# Plan — Home Page (Feed) UI, first vertical slice

## Context

Iteration 1 is backend-complete. The `frontend/` directory has a clean Vite + React 18 + TS + Tailwind v3 scaffold whose only page (`FeedPage.tsx`) currently shows a `/health` indicator. The design bundle at `design/AutonomyAI/src-locked/` is the locked visual reference (variant: `layout=split`, `fakeLevel=medium`, `branding=dot`).

The goal of this task is the **first real UI slice**: render the home/feed page against live data from `GET /api/articles` so we are componentizing as we port (not pure-UI-then-rewire later). To keep the slice tight, we exclude — for now — the right cluster of the header, the filter rail, and the metadata block. We include the header logo + tagline + functional satire/original toggle, the hero (`Today's headlines, slightly off`), and the article-card grid. Card-level affordances (`Ask about this article`, `Compare to original`, card click) render exactly as designed but are inert; routing/chat live in a later task.

Per your decisions: toggle is **functional**, no spec/qa cycle (UI port — design bundle is the spec), card affordances are **rendered but inert**.

## Approach

**Branch:** `feature/home-page-ui` off `main`.

Port a small, named slice of [design/AutonomyAI/src-locked/atoms.jsx](design/AutonomyAI/src-locked/atoms.jsx) and [design/AutonomyAI/src-locked/feed.jsx](design/AutonomyAI/src-locked/feed.jsx) to TypeScript components under [frontend/src/components/](frontend/src/components/). Wire `FeedPage` to `GET /api/articles` via React Query. Lift design tokens into [frontend/tailwind.config.js](frontend/tailwind.config.js) `theme.extend` and import `tokens.css` once for the body radial-glow background, type-scale helpers, animations, and selection/scrollbar styles.

Default `fakeMode = true`. Toggle in `FeedHeader` flips `fakeMode`; `ArticleCard` picks `fake.{title,description}` when `fakeMode === true`, otherwise the `article.{title,description}` returned by the API.

### Explicitly excluded from this slice

- Header right cluster: `last scrape`, `Admin` button, `Refresh feed` button.
- Filter rail: source chips + sort buttons.
- Metadata block: `N ARTICLES IN FEED / 3 SOURCES / UPDATED Xm AGO`.
- Routing to article detail; chat panel; admin modal.
- The featured/large-card-first layout treatment is **kept** (matches locked design); affordance links inside cards are inert.

## Files to create / modify

### New components ([frontend/src/components/](frontend/src/components/))

- `Logo.tsx` — port [atoms.jsx:3-8](design/AutonomyAI/src-locked/atoms.jsx#L3-L8). `FAKE` + accent `LINE` wordmark.
- `Tag.tsx` — port [atoms.jsx:124-129](design/AutonomyAI/src-locked/atoms.jsx#L124-L129). Mono uppercase label.
- `SatireBadge.tsx` — port [atoms.jsx:12-40](design/AutonomyAI/src-locked/atoms.jsx#L12-L40). Hard-code `level="medium"` (locked variant); skip the `subtle`/`loud` branches.
- `SourcePill.tsx` — port [atoms.jsx:42-75](design/AutonomyAI/src-locked/atoms.jsx#L42-L75). Hard-code `branding="dot"`; skip monogram/text branches. Takes a `Source` object (id, name, color).
- `ArticleCard.tsx` — port [feed.jsx:69-114](design/AutonomyAI/src-locked/feed.jsx#L69-L114). Props: `{ item: FeedItem; fakeMode: boolean; featured?: boolean }`. `onClick` is a no-op (`(e) => e.preventDefault()`); affordance rows render as inert spans, not buttons. Hard-code `fakeLevel="medium"`, `branding="dot"`.
- `FeedHeader.tsx` — port [feed.jsx:3-44](design/AutonomyAI/src-locked/feed.jsx#L3-L44) **stripped**: keep `Logo`, the mono tagline `Satirical news, generated`, and the toggle. **Drop** `last scrape`, `Admin`, `Refresh feed`.
- `FeedHero.tsx` — port [feed.jsx:200-209](design/AutonomyAI/src-locked/feed.jsx#L200-L209). Eyebrow `Tag` (`THE FRONT PAGE · {locale-formatted date}`), display `H1` with accent on `SLIGHTLY OFF`, body intro.
- `FeedSkeleton.tsx` — port [feed.jsx:116-131](design/AutonomyAI/src-locked/feed.jsx#L116-L131). Used during initial fetch.
- `FeedEmpty.tsx` — port [feed.jsx:133-155](design/AutonomyAI/src-locked/feed.jsx#L133-L155) **stripped**: drop the `Run scrape now` button (admin action — out of scope). Keep the headline + body + source dots.
- `FeedError.tsx` — port [feed.jsx:157-173](design/AutonomyAI/src-locked/feed.jsx#L157-L173) **stripped**: drop the `Retry` button (would require a refetch hook we're not exposing in the header). Keep the message + dismiss icon, where dismiss just clears local state.

### New hook + API + types

- [frontend/src/api/articles.ts](frontend/src/api/articles.ts) — `getArticles(): Promise<ArticlesResponse>` using existing `apiFetch` from [frontend/src/api/client.ts:13](frontend/src/api/client.ts#L13).
- [frontend/src/hooks/useArticles.ts](frontend/src/hooks/useArticles.ts) — `useQuery({ queryKey: ['articles'], queryFn: getArticles })`.
- [frontend/src/types/api.ts](frontend/src/types/api.ts) — extend with:
  - `SourceId = 'nyt' | 'npr' | 'grd'`
  - `Article` (id, source, title, description, url, published_at, created_at)
  - `ArticleFake` (id, title, description, model, temperature, created_at)
  - `FeedItem` (`{ id; article: Article; fake: ArticleFake }`)
  - `ArticlesResponse` (`{ total: number; pending: number; articles: FeedItem[] }`)
- [frontend/src/lib/sources.ts](frontend/src/lib/sources.ts) — single `SOURCES` map keyed by `SourceId` → `{ id, name, color }`. Names: `The New York Times` / `NPR News` / `The Guardian`. Colors mirror tokens (`var(--nyt|npr|grd)` → Tailwind tokens added below).

### Page rewrite

- [frontend/src/pages/FeedPage.tsx](frontend/src/pages/FeedPage.tsx) — replace current health-status body with: `<FeedHeader fakeMode setFakeMode>` + `<main>` containing `<FeedHero />` + state branches (loading: `<FeedSkeleton />`; error: `<FeedError />`; empty `articles.length === 0`: `<FeedEmpty />`; ready: featured first card + responsive grid). State: a single `useState<boolean>(true)` for `fakeMode`. No filtering, no sorting — render the API order (already `published_at DESC NULLS LAST`).

### Tokens + Tailwind

- Copy [design/AutonomyAI/tokens.css](design/AutonomyAI/tokens.css) → [frontend/src/styles/tokens.css](frontend/src/styles/tokens.css). Import once from [frontend/src/main.tsx](frontend/src/main.tsx) (after `index.css`).
- Extend [frontend/tailwind.config.js](frontend/tailwind.config.js) `theme.extend` with:
  - `colors`: `bg/bg-2/bg-3/bg-4`, `line/line-2`, `text/text-2/text-3/text-4`, `accent/accent-2/accent-ink`, `good/bad/warn`, `nyt/npr/grd` — values from [design/AutonomyAI/tokens.css](design/AutonomyAI/tokens.css).
  - `fontFamily`: `display`, `serif`, `sans`, `mono` mirroring the CSS vars.
  - `borderRadius`: `DEFAULT: 12px`, `sm: 8px`, `lg: 18px`.
- Apply `fl-app-bg` (defined in tokens.css) to `<body>` via [frontend/index.html](frontend/index.html) body class, or wrap `<App>` in a div with that class.
- **Porting rule:** the JSX uses inline `style={{...}}` everywhere. Per [design/AutonomyAI/CLAUDE.md:78-79](design/AutonomyAI/CLAUDE.md#L78-L79), the real components must use Tailwind utilities (no inline styles, except dynamic values like the toggle thumb's `left`). Translate each `style` literal into utility classes against the tokens we just added.

### Files left untouched (intentionally)

- [frontend/src/components/HealthStatus.tsx](frontend/src/components/HealthStatus.tsx), [frontend/src/hooks/useHealth.ts](frontend/src/hooks/useHealth.ts) — orphaned by this task but kept; cheap to delete in a later cleanup pass and may be reused by a future status indicator.
- Backend, docker-compose, env wiring — no changes required. The `vite` dev container already proxies fine because `apiFetch` uses relative paths and Vite is on the same network as the backend in compose. Confirm during verification; if not, add a Vite proxy entry in [frontend/vite.config.ts](frontend/vite.config.ts) pointing `/api` and `/health` at `http://backend:8000` (compose) / `http://localhost:8000` (host).

## Step-by-step

1. Create branch `feature/home-page-ui` from `main`.
2. Add tokens: copy `tokens.css` to `src/styles/`, import from `main.tsx`, extend Tailwind config, add `fl-app-bg` class to body.
3. Write `types/api.ts` additions and `lib/sources.ts`.
4. Write `api/articles.ts` and `hooks/useArticles.ts`.
5. Port atoms: `Logo`, `Tag`, `SatireBadge`, `SourcePill` — Tailwind only.
6. Port `ArticleCard` (with inert affordances).
7. Port `FeedHeader` (stripped), `FeedHero`, `FeedSkeleton`, `FeedEmpty` (no button), `FeedError` (no retry).
8. Rewrite `FeedPage.tsx` to compose header + hero + state branches against `useArticles()`.
9. Confirm Vite proxy or relative fetch works inside the compose network; add proxy if needed.
10. Run `make frontend-typecheck`; fix any TS errors.
11. Run `make up`; visually verify in browser; toggle satire/original; verify empty state by clearing the DB or filtering to a window with no completed fakes.

## Verification

- `make up-d` → `make health` returns ok.
- Open `http://localhost:5173`. Expect:
  - Header: FAKELINE wordmark, mono tagline, satire/original toggle on the right side. **No** `last scrape` / `Admin` / `Refresh feed`.
  - Hero with today's date, `TODAY'S HEADLINES, SLIGHTLY OFF`, intro paragraph.
  - **No** filter chips, **no** metadata block.
  - First article rendered as the featured card (28px padding, larger title), the rest in the responsive `minmax(360px,1fr)` grid.
  - Each card shows `SourcePill` (dot + source name), `SATIRE` badge, relative time, satire title + description from the API.
- Click the toggle → all card titles/descriptions swap to the originals from `article.title/description`. Click again → back to satire.
- Hover a card → border highlights; clicking does nothing visible (inert by design).
- Empty path: with `articles: []` from the API, `FeedEmpty` renders with the source dots; no crash.
- Error path: stop the backend (`docker compose stop backend`), reload → `FeedError` shows.
- `make frontend-typecheck` passes with zero errors.

## Out of scope (next tasks)

- Filter rail (source chips + sort) — pulls in URL-param state per [context.md:72](context.md#L72).
- Metadata block (counts + last update).
- Header right cluster: `last scrape`, `Admin` modal, `Refresh feed` (POST `/api/scrape`).
- Article detail page + chat panel routing (`/articles/:id`).
- Polling / refetch-on-focus tuning for `useArticles`.
- Empty-state CTA `Run scrape now` and error-state `Retry` (depend on the admin/refresh wiring above).

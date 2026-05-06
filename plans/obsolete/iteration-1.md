# Iteration 1 — Walking Skeleton (MVP)

**Goal:** Every architectural component wired and proven end-to-end with minimum viable depth. After this iteration, the brief's core requirements are met functionally if not polished.

**Time budget:** 8-10 hours

**Definition of done:** User can `docker compose up`, click a "Scrape" button, see fake articles populate the feed, click into an article, and have a streaming chat conversation about it. All data persists across restarts.

**Hard checkpoint:** If this iteration is not working end-to-end, do not proceed to Iter 2. Fix foundations first.

---

## Tasks

### 1.1 — Database Schema + First Migration

**Spec scope:**

- Tables created exactly as defined in `contracts.md`
- Initial migration creates the `source_type` Postgres enum (`'NYT', 'NPR', 'Guardian'`) and **three** application tables: `articles` (originals only), `article_fakes` (1:1 with `articles`, all `NOT NULL`, PK = FK on `article_id` per ADR-5), and `chat_messages`. There is no `sources` DB table (ADR-16) and no `article_versions` table (ADR-5).
- Source identity lives as a Python `StrEnum` named `Source` in `backend/app/sources.py`; the same module exports `FEED_URLS: dict[Source, str]`. The Postgres enum is generated from `Source` so the two cannot drift.
- Migration is hand-written, reversible (downgrade works — including `DROP TYPE source_type`)

**Acceptance criteria (for QA):**

- After `alembic upgrade head` on empty DB, the `source_type` enum exists with values exactly `('NYT', 'NPR', 'Guardian')` and all three tables exist with correct columns and indexes per `contracts.md`
- `articles.source` column rejects any value outside the enum (verifiable by attempting an INSERT with an invalid string)
- `articles` carries only original-side fields (`title`, `description`, `url`, `published_at`, `content_hash`, `created_at`); no fake-side columns; no `prompt_version` / `prompt_hash`
- `article_fakes` carries `article_id` (PRIMARY KEY = FOREIGN KEY → `articles(id)` ON DELETE CASCADE), `fake_title`, `fake_description`, `model`, `temperature`, `created_at` — all `NOT NULL`. Inserting two rows with the same `article_id` is rejected by the PK; deleting an article cascades to delete its `article_fakes` row.
- No `sources` table and no `article_versions` table are present in the schema
- `Source` `StrEnum` and `FEED_URLS` dict expose three entries; `FEED_URLS` keys are members of `Source`
- `alembic downgrade base` cleanly reverses (drops the tables and the enum type)

**Out of scope:**

- pgvector extension (deferred to Iter 3)
- Embeddings table
- A `sources` DB table or `enabled` toggle (enum + config only, no runtime mutation — see ADR-16)
- An `article_versions` table or 1:N fake-side relationship (1:1 PK=FK in `article_fakes` per ADR-5; multi-version is Iteration 3 stretch task 3.6)

---

### 1.2 — RSS Scraper Module

**Spec scope:**

- Function takes a feed URL (resolved by the orchestrator from `app.sources.FEED_URLS`), fetches its RSS feed, parses entries, returns structured data
- For each entry: extract title, description, URL, published_at
- Compute `content_hash` (SHA256 of title + description) for dedup
- Pure function: no DB writes here, just returns data

**Acceptance criteria:**

- Given a fixture RSS XML, returns expected list of parsed entries
- Handles malformed entries gracefully (skip + log, don't crash)
- Returns empty list (not error) on network failure or empty feed
- Hashes are deterministic for same input

**Out of scope:**

- DB persistence (handled by orchestrator task)
- Scheduling (Iter 3)

---

### 1.3 — Scrape Orchestrator + Endpoint

**Spec scope:**

- `POST /api/scrape` triggers scrape of every source in the config module (sources are always active — no `enabled` flag per ADR-16)
- For each source: call scraper, take at most `SCRAPE_MAX_PER_SOURCE` entries (default 10), upsert articles by `content_hash` (skip duplicates via `INSERT ... ON CONFLICT DO NOTHING`), enqueue transformation job per new article
- Returns `{enqueued: N, skipped_duplicates: M, sources_scraped: K}`
- Idempotent: on the first run all N articles are processed, so `enqueued=N` and `skipped_duplicates=0`; on an immediate second run no new articles are inserted, so `enqueued=0` and `skipped_duplicates=N`
- Concurrency-guarded: while a scrape is in flight, additional `POST /api/scrape` calls return 409 immediately rather than running in parallel
- Hard-fails (5xx) when Postgres or Redis is unavailable

**Acceptance criteria:**

- Endpoint returns 200 with correct counts
- DB shows new article rows after first call
- DB shows no new articles after immediate second call (dedup works)
- ARQ queue contains transformation jobs equal to new article count
- Per-source cap is honored: a feed with 50+ entries produces at most `SCRAPE_MAX_PER_SOURCE` rows for that source
- A second `POST /api/scrape` arriving while the first is still running returns 409 and does not start a parallel run
- Endpoint completes in <2s even when each source returns 50+ entries (cap + DB writes only, transformation is async)

---

### 1.4 — Transformation Job (ARQ Worker)

**Spec scope:**

- ARQ task that takes an `article_id`, calls OpenAI to generate satirical title + description, and `INSERT`s a row into `article_fakes` (`article_id`, `fake_title`, `fake_description`, `model`, `temperature`) per ADR-5. Re-runs use `INSERT ... ON CONFLICT (article_id) DO UPDATE` so a regenerated fake replaces the prior one.
- ARQ worker runs each job once (`max_tries=1` per ADR-2). On failure, log and skip — no `article_fakes` row is inserted (ADR-15)
- No LLM response cache (per ADR-9 — `INSERT … ON CONFLICT (content_hash) DO NOTHING` upstream means a hit can never happen)

**Acceptance criteria:**

- Given an article, after job runs, an `article_fakes` row exists for that `article_id` with all persisted columns non-null — the four worker-written fields (`fake_title`, `fake_description`, `model`, `temperature`) plus DB-default `created_at`
- On simulated OpenAI failure, exactly one attempt is made; no `article_fakes` row is inserted; worker continues processing queue
- Mocked OpenAI per ADR-10

**Out of scope:**

- Streaming the transformation (transformations are short, no value in streaming)
- Multi-model A/B (Iter 3 stretch)
- Retry / backoff (deliberately removed — see ADR-2)
- LLM response caching (deliberately removed — see ADR-9)

---

### 1.5 — Articles Read API

**Spec scope:**

- `GET /api/articles` — list of **all** articles via `LEFT JOIN article_fakes`; each row is flattened to a single object with fake-side fields (`fake_title`, `fake_description`, `model`, `temperature`, `fake_created_at`) `null` when no `article_fakes` row exists (no pagination, no server-side source filter — both deferred to future_work; frontend filters by source client-side)
- `GET /api/articles/{id}` — single article, same flat `LEFT JOIN` shape as a list-item
- `GET /api/sources` — list sources (used by Admin UI and to render source filter pills even when a source has 0 articles)
- Response shapes match `contracts.md` exactly

**Acceptance criteria:**

- List endpoint returns every article in the DB (no filtering)
- Articles without a successful transformation yet are still returned, with `fake_title`, `fake_description`, `model`, `temperature`, `fake_created_at` all `null`
- 404 on unknown article ID
- Response shape passes contract validation

---

### 1.6 — Chat API with SSE Streaming

**Spec scope:**

- `POST /api/articles/{id}/chat` — body: `{message: string}`, returns SSE stream
- Server inserts user message immediately
- Calls OpenAI with article context (original + fake) + chat history + user message, streams tokens back via SSE
- After stream completes, inserts full assistant message
- `GET /api/articles/{id}/messages` — returns chronological history
- SSE event format: `data: {"token": "..."}\n\n` for each token, `data: [DONE]\n\n` at end, `data: {"error": "..."}\n\n` on failure

**Acceptance criteria:**

- Chat completes end-to-end and persists both user and assistant messages
- Stream emits tokens incrementally (not all at once at the end)
- History endpoint returns messages in chronological order
- New chat after restart still has prior history visible
- OpenAI errors mid-stream produce error event, don't leave dangling connection

**Out of scope:**

- Cancellation mid-stream (Iter 2 polish if time)
- Semantic cache for chat (future_work)

---

### 1.7 — Frontend: Design System + Static Feed UI

**Spec scope:**

- Lift design tokens from `design/AutonomyAI/tokens.css` into `frontend/tailwind.config.js theme.extend` (colors, fonts, radii, source-color safelist) per ADR-13
- Load Google Fonts (Anton, Oswald, Fraunces, Inter, JetBrains Mono) via `<link>` in `frontend/index.html`
- Add `lucide-react` for icons (every icon in the design's hand-rolled `icons.jsx` maps 1:1 to a Lucide icon)
- Port reusable atoms from `design/AutonomyAI/src-locked/atoms.jsx` to TypeScript: `Logo`, `Btn`, `Chip`, `SourcePill` (dot variant), `SatireBadge` (medium variant)
- Port feed-specific composites: `FeedHeader`, `FilterRail`, `ArticleCard` (featured + standard variants)
- Replace `frontend/src/pages/FeedPage.tsx` to render the full design against a hardcoded `MOCK_ARTICLES` array (~6 items)
- No API calls, no routing, no React Query usage on this page yet — pure presentational port

**Acceptance criteria:**

- `npm run dev` shows the feed page visually matching `design/AutonomyAI/Fake News v2 (Locked).html` (fonts, colors, sticky header, hero, filter rail, responsive card grid via `auto-fill minmax(360px, 1fr)`)
- Filter chips render the hardcoded source list (All sources, NYT, NPR, Guardian) and clicking a chip narrows the rendered mock cards client-side; "All sources" returns to the unfiltered list. No network requests in DevTools.
- `npm run build` passes with strict TypeScript
- No backend calls fire from the feed page (DevTools Network shows only Google Fonts)

**Out of scope:**

- API wiring (1.8)
- Article detail page, chat panel (1.9)
- `react-router-dom` setup (1.8)
- `InlineDiff`, `EntitiesCard`, scrape-runs modal (not in MVP API contract)

---

### 1.8 — Frontend: Wire News Feed to API

**Spec scope:**

- Replace `MOCK_ARTICLES` with `useQuery(['articles'], …)` hitting `GET /api/articles`
- Wire "Refresh feed" button to `POST /api/scrape` followed by query invalidation
- Add loading, empty, and error states to the feed
- Filter chips keep working against the real article data — chip selection narrows the rendered list client-side. Chip source list stays hardcoded (NYT / NPR / Guardian, matching the seed); replacing it with `GET /api/sources` is task 2.1
- Set up `react-router-dom` with `<BrowserRouter>` and a placeholder `/articles/:id` route
- Click a card → navigate to `/articles/{id}`
- React Query manages fetching, caching, refetch

**Acceptance criteria:**

- Empty state when no articles
- Loading state during fetch
- Error state on API failure
- After scrape, new articles appear within reasonable time (poll or manual refresh OK in MVP)
- Page survives refresh (data comes from DB, not local state)

---

### 1.9 — Frontend: Article Detail + Chat UI Port

**Spec scope:**

- Port the article detail page chrome from `design/AutonomyAI/src-locked/article.jsx` and `chat.jsx` to TypeScript, against the design tokens and atoms landed in 1.7
- Add new atoms: `Tag` (uppercase mono label), `Skeleton` (loading block), and a `monogram` variant for `SourcePill`
- New composites: `ArticleDetailPage` (split layout, max-width 1320, grid `minmax(0, 1fr) 420px`, sticky chat aside), `ArticleHeader`, `ArticleBody`, `ChatPanel`, `ChatMessage`
- Render against a hardcoded `MOCK_ARTICLE` + ~3 mock chat messages in `frontend/src/pages/ArticleDetailPage.mocks.ts`
- Page reachable through the placeholder `/articles/:id` route set up in 1.8; render against mock data only in this task
- All buttons and the chat send/quick-prompts are visually present but inert; clicks `console.log` the button name (e.g. `console.log("Original tab clicked")`) so interaction is observable in DevTools without faking behavior. Quick-prompt chips additionally pre-fill the chat input on click but do not auto-send.
- No API calls, no SSE, no React Query — pure presentational port

**Out of scope (design elements not in MVP API contract):**

- **Diff button + InlineDiff** — omitted entirely; no `/api/articles/{id}/diff` endpoint
- **EntitiesCard / structured entity message rendering** — omitted; chat returns plain text only
- **Structured chat messages** (`kind: 'entities'` etc.) — omitted; SSE stream is `{token: "..."}` plain text
- **Original toggle wiring** — toggle is rendered as visual chrome, but clicking "Original" is a no-op (real wiring lands in Iter 2 task 2.2)
- **Real article detail wiring at `/articles/:id`** — the placeholder route from 1.8 stays in place; replacing it with the live page is deferred to 1.10
- **Drawer / stacked layouts** — split layout only (locked variant)

**Acceptance criteria:**

- `npm run dev` shows the article detail page visually matching the locked HTML design (article pane left, sticky chat aside right, large serif headline, orange-left-border description, source pill + topic tag + timestamp + satire badge meta row, "View original" link, Scraped / Transformed timestamps with Lucide icons)
- Chat panel renders the header (sparkle icon + "Article assistant" + "Grounded on:" + GPT-4o pill), mock message thread, quick-prompt chip row, and input + send button
- Quick-prompt chips visibly pre-fill the input on click; no network requests fire (verify via DevTools Network)
- `npm run build` passes with strict TypeScript

---

### 1.10 — Frontend: Wire Article Detail + SSE Chat

**Spec scope:**

- Replace the placeholder `/articles/:id` route (set up in 1.8) with the real article detail page mounted at that route
- Replace mock article with `useQuery` against `GET /api/articles/{id}`; show skeleton while loading, error state on failure, 404 redirect / fallback on missing id
- Load chat history via `useQuery(['messages', id], …)` against `GET /api/articles/{id}/messages` on mount
- Wire send button + Enter key to `POST /api/articles/{id}/chat` via `@microsoft/fetch-event-source`; tokens accumulate into a "streaming" assistant bubble; on `[DONE]` the bubble finalizes and history is invalidated (or optimistically appended)
- Error events from the SSE stream render an inline error in the thread; UI does not lock — user can retry
- Quick-prompt chips auto-send their label as the user message

**Acceptance criteria:**

- Streaming tokens visibly accumulate in real time (not all at once at the end)
- Multiple back-and-forth messages work in one session
- Refresh preserves chat history (loaded from DB)
- Error during streaming shows error state, doesn't lock the UI
- Page survives refresh — article + history come from API, not local state

**Out of scope:**

- Original toggle wiring (Iter 2 task 2.2)
- Source filter (Iter 2)
- Cancel button mid-stream (Iter 2 / Iter 3)
- Diff view, EntitiesCard, structured chat (not in MVP contract)

---

## Iteration 1 Acceptance Criteria

- [ ] All 10 tasks done with passing tests
- [ ] `docker compose up` works clean
- [ ] User flow works end-to-end: scrape → wait briefly → see articles → click → chat with streaming
- [ ] Restart preserves all data
- [ ] No console errors / unhandled exceptions in normal flow

## Notes

- **Mocking OpenAI in tests is mandatory from this iteration.** Set up the fixture in 1.4 and reuse.
- **Don't over-style.** Functional > pretty in this iteration.
- **Check the hard checkpoint** before moving on. If something's flaky, fix it now.

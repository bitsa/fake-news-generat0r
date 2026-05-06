# Iteration 2 — Depth + CI

**Goal:** Take the working skeleton and add the features that make it submittable: filtering, original toggle, error handling, observability, and CI.

**Time budget:** 5-6 hours

**Definition of done:** App feels intentional and robust. CI runs on every PR. Tests cover the critical paths. Errors are handled gracefully.

---

## Tasks

### 2.1 — Source Filter: API + URL Sync

**Context:** The filter UI (chip rail with All sources / NYT / NPR / Guardian) was already ported in 1.7 against a hardcoded source list, and 1.8 wired chip selection to narrow the article list client-side. This task replaces the hardcoded chip list with the real source list from the API and persists the active filter in the URL. There is no backend filtering — per the renumbered 1.5 spec, server-side filtering is deferred to `future_work.md`; the feed is filtered entirely client-side.

**Spec scope:**

- Replace the hardcoded source list in `FilterRail` with `useQuery({ queryKey: ['sources'], queryFn: … })` hitting `GET /api/sources` — the API is the source of truth so a newly-added source (or one with zero articles) still appears as a filter chip
- Sync chip selection to a `?source=<source>` URL query param (where `<source>` is the canonical `Source` enum value the API returns, e.g. `NYT`): changing selection updates the URL (`history.replaceState` / `useSearchParams`), and on initial load the URL drives the chip selection
- Source counts on chips (e.g. "NYT (12)") computed client-side from the loaded articles array — kept under the same task because it falls out of the existing data

**Acceptance criteria:**

- Filter narrows visible articles client-side; selecting "All sources" returns to the unfiltered list
- URL is shareable: pasting a filtered URL in a new tab shows the feed pre-filtered to that source
- Refreshing the page preserves the active filter (URL is the source of truth, not local state)
- A source with zero articles still appears as a chip (proves the chip list comes from `/api/sources`, not from articles)
- Counts on chips update when articles arrive / refetch

**Out of scope:**

- Backend `?source=` query param on `GET /api/articles` — deferred to `future_work.md`. The frontend filters client-side over the full list (acceptable while the feed is small; if the article volume grows, server-side filtering moves into a future iteration).
- Multi-select (chips remain single-select)

---

### 2.2 — Original ↔ Fake Toggle

**Context:** The Satirical / Original toggle UI was ported in 1.9 as visual chrome with `console.log("Original tab clicked")` as the click handler. The article detail page (wired in 1.10) currently renders only the satirical title + description from `GET /api/articles/{id}`'s `fake_title` / `fake_description` fields. This task replaces the `console.log` with real state and conditionally renders the original title + description (which the API already returns flat alongside the fake-side fields). The "View original on {source}" link in the article meta row is already wired to `article.url` from 1.9 — no change needed there.

**Spec scope:**

- Replace the toggle's `console.log` click handler with a `useState` setter (`'fake' | 'original'`, defaulting to `'fake'`)
- `ArticleBody` conditionally renders `article.fake_title / article.fake_description` (fake) or `article.title / article.description` (original) based on the toggle state
- Keep the orange left-border accent on the description for the fake view; switch to a neutral border (`var(--line-2)`) for the original view, matching `design/AutonomyAI/src-locked/article.jsx:89`
- Toggle state is local component state — no URL param, no persistence
- Verify mobile usability of the existing toggle chrome at narrow widths (responsive behavior already comes from the 1.9 port; this is a verification pass, not a re-style)

**Acceptance criteria:**

- Toggle visibly swaps title + description with no flicker (use the design's `key={view}` + `.fadein` pattern from `article.jsx:73` for the soft fade)
- "View original on {source}" link in the meta row continues to open the source URL in a new tab
- Toggle remains usable and visually correct on viewports down to 360px wide (chip pill stays on screen, tap targets ≥ 44px)
- Switching tabs does not refetch the article — both versions come from the single existing query

**Out of scope:**

- Diff view button (omitted entirely — not in MVP API contract)
- Persisting toggle preference across navigations (would need URL param or store; not needed for MVP)
- Animation beyond the existing fade — no slide / crossfade between panes

---

### 2.3 — Error Handling Pass

**Spec scope:**

- Custom exception hierarchy on backend with FastAPI exception handlers (per `conventions.md`)
- Standardized error response shape: `{error: {code, message, details?}}`
- Frontend: error boundaries on routes, friendly error UI for failed fetches, toast/banner for transient errors
- Specific scenarios covered:
  - OpenAI rate limit / failure during chat → user-friendly message, retry option
  - DB unavailable → 503 with clear message
  - Invalid article ID → 404 page
  - Scrape partial failure (one source down) → return successful sources + error list
- Logging at appropriate levels: info for normal flow, warning for recoverable, error for unhandled

**Acceptance criteria:**

- Killing the OpenAI mock mid-chat shows graceful error to user
- Stopping Postgres returns 503 with message, doesn't crash backend
- Random invalid IDs in URL show 404 UI, not blank screen
- Backend logs are structured JSON with request_id per request

---

### 2.4 — Integration Tests (Backend)

**Spec scope:**

- pytest test suite covering API + pipeline integration (not just unit tests from Iter 1)
- Test fixtures spin up fresh DB schema per test (or per session with cleanup)
- OpenAI is mocked via fixture returning canned responses (deterministic)
- Coverage targets:
  - Scrape endpoint: dedup behavior, multi-source success, partial failure
  - Article endpoints: filtering, 404
  - Chat endpoint: full SSE flow, error mid-stream, history persistence
  - Transformation worker: cache hit/miss, retry behavior

**Acceptance criteria:**

- `pytest` runs locally and passes
- Tests are deterministic (no flaky network calls, no unmocked OpenAI)
- Tests run in <60s total
- Coverage report generated (target: ~70% backend lines, more important: critical paths covered)

---

### 2.5 — GitHub Actions CI

**Spec scope:**

- `.github/workflows/ci.yml` runs on every PR and push to main
- Pipeline:
  1. Backend job: lint (`ruff`), typecheck (`mypy`), unit + integration tests with Postgres + Redis service containers
  2. Frontend job: lint (`eslint`), typecheck (`tsc --noEmit`), build (`vite build`)
  3. Tests run in parallel with backend lint
- Status checks block merging on failure
- Caching: pip cache + npm cache to keep CI fast

**Acceptance criteria:**

- Open a PR → CI runs automatically
- CI completes in under 5 minutes
- Breaking lint or test produces failed check
- README badge shows CI status

---

### 2.6 — Structured Logging + Observability Hooks

**Spec scope:**

- `structlog` configured: JSON logs in production mode, human-readable in dev
- Every API request logged with: method, path, status, duration_ms, request_id
- Pipeline jobs logged with: job_id, article_id, duration_ms, cache_hit (bool), tokens_used (if available)
- No secrets or full prompts/responses in logs (log hashes/lengths)
- Frontend: minimal — `console.error` for caught errors with context

**Acceptance criteria:**

- Log lines are valid JSON when `LOG_FORMAT=json`
- Request IDs trace a request across log lines (middleware adds it to context)
- No env values, API keys, or full prompts visible in any log

---

### 2.7 — Cache Hit Visibility (Polish)

**Spec scope:**

- LLM cache from Iter 1.4 exposes hit/miss counts (in-memory counter or Redis INCR)
- Cache stats are exposed via structured logs/metrics (not via `/health`, which stays minimal `{status}` per contract). Surface mechanism (admin endpoint vs. log-only) is decided in the 2.7 spec.
- Optional: small badge in frontend dev mode showing cache hit rate

**Acceptance criteria:**

- Repeated scrapes of same articles show high cache hit rate
- Stats reset cleanly on Redis flush

---

### 2.8 — Zustand Reassessment (Conditional)

**Spec scope:**

- Audit current frontend: are you prop-drilling state more than 2 levels? Are multiple components needing the same client state (selected filter, panel open, etc.)?
- If yes: introduce Zustand for that state only. Don't migrate React Query stuff.
- If no: skip and document the call in `decisions.md`

**Acceptance criteria:**

- Either Zustand introduced cleanly with a single store, or decision documented as "not needed at this scale"

---

## Iteration 2 Acceptance Criteria

- [ ] All listed tasks complete or explicitly deferred with reason
- [ ] CI green on main
- [ ] Killing any single component (OpenAI, DB) produces graceful UX, not crashes
- [ ] Logs are useful for debugging
- [ ] App feels intentional, not a prototype

## Notes

- 2.5 (CI) and 2.4 (tests) are the highest interview-signal items in this iteration. Don't skip.
- 2.7 and 2.8 are nice-to-haves; cut if running short.

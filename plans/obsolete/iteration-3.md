# Iteration 3 — Bonuses

**Goal:** Add the bonus features from the brief that demonstrate depth: scheduled scraping, similarity detection, and chat polish.

**Time budget:** 4-5 hours

**Definition of done:** At least scheduled scraping + similarity detection are working. Stretch goals tackled if time permits. Submission is polished and the README + Loom are ready.

**Order of priority** (cut from bottom if running short):

1. Scheduled scraping (cheap, high signal)
2. Similarity detection with pgvector (medium cost, very high signal)
3. Admin: Scrape & Transform Panel (medium cost, demos the pipeline visibly — useful in the Loom)
4. Chat cancellation mid-stream (low cost, nice UX win)
5. Stretch items
6. Full-stack integration tests (3.8) — last, only if time remains

---

## Tasks

### 3.1 — Scheduled Scraping (ARQ Cron)

**Spec scope:**

- ARQ cron job runs scrape orchestrator every `SCRAPE_INTERVAL_MINUTES` (env var, default 60)
- Same orchestrator code as manual `/api/scrape` — no duplication
- Worker logs each scheduled run (count enqueued, skipped duplicates)
- Configurable via env: can be disabled with `SCRAPE_INTERVAL_MINUTES=0`

**Acceptance criteria:**

- Setting interval to 1 minute and waiting produces a new scrape entry in logs
- Disabling via env results in no scheduled runs
- Manual scrape still works alongside scheduled
- Doesn't conflict with manual scrape (no double-processing)

---

### 3.2 — Article Similarity Detection (pgvector)

**Spec scope:**

- Add pgvector extension to Postgres (via migration enabling extension, requires `pgvector/pgvector` Postgres image)
- New `article_embeddings` table: `article_id` (FK), `embedding` (vector(1536)), `model`, `created_at`
- During scrape pipeline: after upserting article, enqueue embedding job
- Embedding job: call OpenAI `text-embedding-3-small` on title+description, store vector
- Before enqueuing transformation: check if any existing article in last N days has cosine similarity > threshold (env var, default 0.95). If yes, mark as near-duplicate and skip transformation
- Optional: surface similar articles in detail view (`GET /api/articles/{id}/similar`)

**Acceptance criteria:**

- pgvector extension loads on fresh DB
- Embeddings stored after scrape (verify by row count)
- Scraping the same RSS twice with slightly modified text (test fixture) detects similarity correctly
- Similarity threshold tunable via env
- Falls back gracefully if embedding API fails (don't block transformation)

**Out of scope:**

- Semantic search UI for users
- Re-embedding when prompt or model changes

---

### 3.3 — Admin: Scrape & Transform Panel

**Context:** The Admin button in the feed header (rendered as inert chrome since 1.7) opens nothing today. This task wires it to a modal that visually represents a "Run full pipeline" action over the three sources. The design for this panel lives in `design/AutonomyAI/src-locked/admin.jsx`. The progress display is **emulated client-side** — there is no backend run-state tracking. The modal completes in lockstep with `POST /api/scrape` resolving.

**No backend changes.** This task uses only the existing `POST /api/scrape` endpoint from 1.3. No Redis run state, no new endpoints, no polling, no `scrape_runs` table. Per [design/AutonomyAI/CLAUDE.md](../design/AutonomyAI/CLAUDE.md): we are not inventing new backend contracts — the design's full progress modal is approximated with client-side animation.

**Spec scope:**

- Port the modal layout from `admin.jsx`: header ("SCRAPE & TRANSFORM" + subtitle), three per-source rows, action buttons row, log area at bottom
- Per-source row contents: source pill + status text ("Connecting…" / "Fetching feed…" / "Parsing entries…" / "Done" / error message) + status pill (`Idle` / `Running` / `Done` / `Error`) + progress bar. **No numeric counters on the row.**
- Wire the existing inert "Admin" button in `FeedHeader` to open the modal (controlled local state — no router change). X button and backdrop close it.
- The actions row contains exactly one button: "Run full pipeline". It calls existing `POST /api/scrape` and disables while in flight.
- **Client-side progress emulation per source row** during the run:
  - On click: status flips to `Running`, progress bar starts animating from 0
  - Over ~2 seconds the bar fills to ~90% with a smooth ease-out animation; status text steps through fake checkpoints ("Connecting…" → "Fetching feed…" → "Parsing entries…")
  - At ~90%, animation **holds** — last segment is pending the real response
  - When `POST /api/scrape` resolves: bars complete to 100%, status pills flip to `Done`, status text becomes "Done". If the response returns in under 2s, bars jump straight to 100%.
  - On error response: bars freeze at hold position, status pill becomes `Error`, status text shows the error message
- Log area renders aggregate observations only ("Started run", "Run complete: N scraped, M duplicates", "Run failed: …") — derived from the `POST /api/scrape` aggregate response (`{enqueued, skipped_duplicates, sources_scraped}`). No log endpoint, no streaming, no per-source breakdown needed.

**Explicit DOM exclusions** (the rendered modal must not contain these elements at any point):

- **No "Re-transform existing" button.** The actions row contains only "Run full pipeline".
- **No "transformed" counter** anywhere on the per-source rows or in the log area. The async transformation phase is invisible to this UI on purpose — we have no signal for it without polling, and we will not fake one.
- **No per-source numeric counters** ("0 scraped", "12 scraped", etc.). Status is communicated only through the status pill and status text.

**Out of scope:**

- Real per-source progress tracking (no Redis run state, no `scrape_runs` table, no polling, no new endpoints)
- Visibility into the async transformation phase — the modal completes when scrape completes; transformation continues in the background and surfaces via the feed refetch
- Run history — modal shows only the current/most-recent run, lost on refresh
- Authentication on the modal (out of scope for the take-home; future_work)

**Acceptance criteria:**

- Clicking the Admin button opens the modal; clicking the X or backdrop closes it without aborting any in-flight request
- With a fresh stack, all three source rows show idle state (`Idle` pill, empty bar, "Ready to run")
- Clicking "Run full pipeline" disables the button, sets all rows to `Running`, and animates progress bars to ~90% over ~2s
- Bars hold at ~90% if the scrape request is still pending after the animation completes
- On scrape success, bars complete to 100%, pills flip to `Done`, status text becomes "Done", and the aggregate run summary renders in the log area (e.g. "Run complete: 12 scraped, 0 duplicates")
- On scrape error, bars freeze, pills flip to `Error`, status text shows the error, and the failure renders in the log area
- Run button re-enables after the response (success or error)
- Closing and reopening the modal mid-run preserves the in-flight state (animation continues; the open `fetch` promise is not aborted)
- A subsequent "Run full pipeline" click after a complete run resets all three rows and starts fresh

---

### 3.4 — Chat Cancellation Mid-Stream

**Spec scope:**

- Frontend exposes a "Stop" button while streaming
- Click aborts the SSE connection (via AbortController)
- Backend detects disconnection and stops calling OpenAI mid-stream
- Partial response is saved as the assistant message (with a `cancelled: true` flag in metadata, optional)

**Acceptance criteria:**

- Clicking Stop visibly halts incoming tokens
- DB shows partial assistant message
- Subsequent chat still works normally

---

### 3.5 — Stretch: Loom-Ready Polish

**Spec scope:**

- README finalization: setup, env vars, architecture diagram, screenshots, "what I'd do with more time" section pointing to `future_work.md`
- Default styling pass: spacing, typography, hover states. Goal: looks intentional, not pretty
- Empty/loading/error states reviewed for consistency
- Add a screenshot or two to README

**Acceptance criteria:**

- README is self-contained: someone unfamiliar can set up + run
- App doesn't look broken in any state

---

### 3.6 — Stretch: Prompt Versioning Demo

**Spec scope:**

- Demonstrate the `prompt_version` infrastructure by including 2 versions of the transformation prompt
- Env var `PROMPT_VERSION_TRANSFORM` selects active one
- Show in Loom: switching versions, re-running, seeing different transformations linked to same article

**Acceptance criteria:**

- Two distinct prompts produce visibly different fake versions of same article
- DB shows multiple `article_fakes` rows linked to the same article, each with a different `prompt_version` (this stretch task relaxes the 1:1 PK=FK constraint from ADR-5 — drops the PK on `article_id`, adds `id SERIAL PRIMARY KEY` and a unique index on `(article_id, prompt_version)`. Migration steps documented in ADR-5.)

---

### 3.7 — Stretch: Cost Tracking

**Spec scope:**

- After each OpenAI call, log estimated cost based on input/output tokens × model price
- Optional: aggregate total cost in admin stats endpoint
- Useful interview talking point about LLM ops

**Acceptance criteria:**

- Logs include `tokens_in`, `tokens_out`, `estimated_cost_usd` per call
- Admin endpoint shows running total

---

### 3.8 — Full-Stack Integration Tests (Final Step)

**Run order:** This is the **last task of the iteration** — and of the project. Skip if the iteration runs short; per-task QA already covers in-process tests, so this is the cross-task safety net, not a blocker for shipping.

**Spec scope:**

- A small integration suite that runs against the full Docker Compose stack (real Postgres, real Redis, mocked OpenAI) and exercises the golden-path scenarios end-to-end across iterations 1–3.
- Suggested coverage (one test per scenario, not exhaustive):
  - Manual scrape → article appears in `GET /api/articles` with fake fields populated.
  - Scheduled scrape (3.1) fires once and produces a new run.
  - Similarity detection (3.2) marks a near-duplicate and skips transformation.
  - Chat round-trip: `POST /api/articles/:id/chat` streams tokens, history is persisted.
- OpenAI is always mocked — never real API calls.
- Tests live under `backend/tests/integration_e2e/` (separate from per-task in-process tests).
- A single `make integration` target spins up Compose, runs the suite, tears down.

**Acceptance criteria:**

- `make integration` exits 0 on a clean checkout.
- Suite runs in under 3 minutes including stack boot.
- No test depends on real network beyond the Compose-internal services.
- Failures surface a single clear error per scenario (no flaky retries).

**Out of scope:**

- Re-testing every per-task acceptance criterion — that's already covered by in-process QA.
- Browser-driven (Playwright/Cypress) tests — pure HTTP / DB observation only.

---

## Iteration 3 Acceptance Criteria

- [ ] Scheduled scraping working (3.1)
- [ ] Similarity detection working (3.2)
- [ ] At least one stretch item delivered OR explicitly mentioned in `future_work.md`
- [ ] README is submission-ready
- [ ] Loom recorded covering: demo, schema, pipeline, LLM integration, decisions, AI workflow, what's next
- [ ] (Optional, time-permitting) Full-stack integration suite (3.8) green

## Notes

- 3.2 (pgvector) is the **highest-signal item in this iteration.** It demonstrates RAG-adjacent thinking. Prioritize.
- If you're running really short, skip 3.3-3.7 and just polish what's there.
- The Loom recording itself is part of the deliverable. Budget ~1 hour for it (script + record + maybe one retake).

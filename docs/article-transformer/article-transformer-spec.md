# Spec: article-transformer

## Source

`plans/article-transformer.md` — the task plan document authored during the design session for
this project. Quoted scope verbatim:

> "Wire the ARQ transform pipeline — when articles are scraped, create `article_fakes` rows with
> `transform_status='pending'` and enqueue ARQ jobs. The worker picks up jobs and writes static
> mock content (real LLM call deferred). `POST /api/scrape` returns an additional `enqueued`
> count. The pipeline is durable: `pending` rows survive crashes, and startup recovery
> re-enqueues stale pending rows."

---

## Goal

Introduce the ARQ-backed transform pipeline between scraping and fake-content delivery. After
this task, every newly inserted article gets a companion `article_fakes` row created synchronously
(status: `pending`), and an ARQ job is enqueued to fill it with content. The ARQ worker job
writes static mock content (same strings for every article — real OpenAI call is a future
drop-in). `POST /api/scrape` grows an `enqueued` field in its response. The pipeline is durable:
`pending` rows are the source of truth, so crashes or queue wipes do not silently lose work —
startup recovery re-enqueues any stale pending rows older than five minutes.

---

## User-Facing Behavior

- **`POST /api/scrape` response** — the response shape is unchanged: `{"inserted": N, "fetched": M}`.
  Status code remains `202 Accepted`. Enqueueing is an implementation detail; the caller does not
  need to know whether jobs were submitted — the durability model ensures they will eventually be
  processed.

- **Article fake row creation** — immediately after a successful scrape, the database contains
  one `article_fakes` row per newly inserted article, with `transform_status = 'pending'`.
  Pre-existing articles (already in the DB before this scrape) do not gain new rows.

- **Worker completes transform** — if the ARQ worker is running, `article_fakes` rows transition
  from `pending` to `completed` shortly after insertion. The completed row has non-null
  `title`, `description`, `model`, and `temperature`. (In this task the content is static mock
  text — not real LLM output.)

- **Worker not running / enqueue failure** — rows remain `pending`. The scrape still succeeds.
  No error is surfaced to the caller for a failed enqueue.

- **Crash recovery on startup** — on every app startup, the lifespan hook re-enqueues any
  `article_fakes` row with `transform_status = 'pending'` and
  `created_at < NOW() - settings.transform_recovery_threshold_minutes`.
  Rows created within the threshold window are left alone (assumed in-flight).

- **Non-existent article** — if a worker job fires for an `article_id` that does not exist in
  the DB, the job exits silently (logs the skip, returns). No exception propagates to ARQ.

---

## Acceptance Criteria

### `POST /api/scrape` response shape

- [ ] The endpoint response shape is unchanged: `{"inserted": N, "fetched": M}` — both values
  are non-negative integers with the same semantics as before this task.
- [ ] Status code is `202 Accepted` on success.
- [ ] 503 error path (all sources fail) is unchanged — the endpoint still returns 503 when all
  RSS sources fail.

### `article_fakes` row creation

- [ ] After a successful scrape, every newly inserted article has exactly one `article_fakes` row
  with `transform_status = 'pending'`, `title = NULL`, `description = NULL`.
- [ ] Articles that were already in the DB before this scrape (duplicates, on-conflict-do-nothing
  path) do **not** gain new or updated `article_fakes` rows.
- [ ] The `article_fakes` row for a new article is present in the DB before the HTTP response
  is returned.

### ARQ worker job — `transform_article`

- [ ] When the job runs for an existing `article_id`, the `article_fakes` row for that article
  transitions to `transform_status = 'completed'`.
- [ ] The completed row has non-null `title` and `description` values (static mock strings).
- [ ] The completed row's `model` equals `settings.openai_model_transform`.
- [ ] The completed row's `temperature` equals `settings.openai_temperature_transform`.
- [ ] When the job runs for a non-existent `article_id`, no exception is raised, the DB is
  unchanged, and a log event records the skip.

### Error handling and durability

- [ ] If enqueueing one article's ARQ job fails (simulated), the remaining articles still receive
  `pending` rows and their enqueue attempts proceed — the failure does not abort the run.
- [ ] A failed enqueue emits exactly one `WARNING`-level log event (not `ERROR`).
- [ ] If `transform_article` raises an unexpected exception mid-run, the `article_fakes` row for
  that article is **deleted** (not left as `pending`), and the error is logged. No retry occurs.
- [ ] After the deletion, the `articles` row for the same article still exists (delete is
  targeted at `article_fakes` only).

### Startup recovery

- [ ] On app startup, `article_fakes` rows with `transform_status = 'pending'` AND
  `created_at < NOW() - interval '<transform_recovery_threshold_minutes> min'` are re-enqueued
  before the regular scrape runs (threshold is `settings.transform_recovery_threshold_minutes`,
  default `5`).
- [ ] `article_fakes` rows with `transform_status = 'pending'` AND
  `created_at >= NOW() - interval '<transform_recovery_threshold_minutes> min'` are **not**
  re-enqueued.
- [ ] `article_fakes` rows with `transform_status = 'completed'` are never re-enqueued by the
  recovery step.

### `scraper.py` immutability

- [ ] `backend/app/services/scraper.py` is unmodified — its public API (`ingest_all`,
  `IngestResult`) and behavior are identical to the `rss-scraper` task deliverable.

---

## Out of Scope

- **Real OpenAI API calls** — the LLM integration is deferred. This task uses fixed static
  strings for `fake_title` and `fake_description`.
- **Frontend changes** — no UI work in this task.
- **Docker Compose worker service wiring** — the worker container definition is an infra task
  outside this scope. The worker binary can be started manually for testing.
- **Scheduled / periodic scraping** — triggering scrapes on a timer is future work.
- **Retry logic or dead-letter queue** — ARQ is configured with `max_tries=1`. Failed jobs are
  deleted, not retried.
- **`failed` / `processing` transform states** — the schema intentionally has only `pending` and
  `completed`; see `context.md`.
- **`GET /api/articles` changes** — exposure of `transform_status` or fake content in the feed
  API is the responsibility of the `get-articles` task.

---

## Open Questions / Assumptions

1. **Static mock content strings** — the plan says "fixed satirical placeholder strings" but does
   not name them. The dev must choose concrete strings; any non-empty, non-null value satisfies
   the spec. **Human sign-off not required** — any static content is acceptable for this task.

2. **Recovery timing relative to `ingestor.run()`** — the plan states recovery runs before
   `ingestor.run()` in the lifespan hook. This ordering is assumed correct: recovery re-enqueues
   stale rows, then the fresh scrape creates new pending rows and enqueues new jobs.

3. **`get-articles` task is concurrently in dev** — the `GET /api/articles` endpoint is currently
   `in_dev`. This task does not depend on it, but if `get-articles` merges first and exposes
   `article_fakes` data, its tests should account for rows in `pending` state (mock content will
   be null). **Flag to dev: coordinate merge order or ensure `get-articles` handles null fake
   content gracefully.**

4. **ARQ pool not yet wired** — `backend/app/arq_client.py` and the ARQ pool on `app.state` do
   not exist yet. This task creates them. The `get_arq_pool` FastAPI dependency assumes
   `request.app.state.arq_pool` is always set by the lifespan; if startup fails before pool
   creation, any request using this dependency will 500. This is acceptable for MVP.

5. **`openai_api_key` is a required `Settings` field** — even though no real LLM call is made in
   this task, the field is required by Pydantic Settings. The dev environment must have
   `OPENAI_API_KEY=sk-fake-key-for-dev` (or equivalent) in `.env`. This is already documented
   in `plans/article-transformer.md` decisions table and requires no spec change — but QA must
   ensure tests do not fail due to a missing env var.

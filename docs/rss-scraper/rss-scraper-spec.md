# RSS Scraper Spec

## Source

**File:** `/Users/bitsa/.claude/plans/i-want-to-work-tingly-waffle.md` (task draft authored by
user), supplemented by inline additions:

- *"add a validator when fetched. If the description or title is empty — drop such a pulled entity"*
- *"only write a warning about it in logs. That's it — no retry no need for more"*

This spec covers raw article ingestion and its HTTP trigger: fetch RSS feeds, validate entries,
persist to the `articles` table, and expose `POST /api/scrape` to trigger ingestion on demand.
No LLM calls, no `article_fakes` writes, no ARQ — pure scrape-and-store. LLM transformation is
a separate task.

---

## Goal

Fetch all three configured RSS feeds, validate entries, and upsert valid rows into `articles` with
`ON CONFLICT (url) DO NOTHING`. Triggered two ways: automatically on startup and on-demand via
`POST /api/scrape`. The endpoint returns 202 Accepted once at least one feed has been successfully
scraped, giving callers a reliable signal that new articles may be available.

---

## User-Facing Behavior

- `docker-compose up` starts the app; the lifespan trigger immediately runs ingestion.
- After startup, `articles` contains up to `SCRAPE_MAX_PER_SOURCE` rows per source (NYT, NPR,
  Guardian).
- `POST /api/scrape` triggers ingestion on demand and returns `202 Accepted` with
  `{"inserted": N, "fetched": M}` — `inserted` is the count of new DB rows written, `fetched`
  is the total valid entries pulled from feeds in this run (before dedup).
- If all three sources fail, `POST /api/scrape` returns `503 Service Unavailable` with a clear
  error message.
- Running `docker-compose up` or calling `POST /api/scrape` again inserts zero duplicate rows.
- Entries missing title, URL, or description are silently dropped — one `WARNING` log line per
  dropped entry, no error surfaced, no retry.
- If fetching one source fails (network error, bad HTTP status), that source is skipped with a
  `WARNING`; the other sources still run.

---

## Acceptance Criteria

1. **Lifespan trigger** — `scraper.ingest_all(session)` is called from the FastAPI lifespan after
   `_run_migrations()` completes. The app starts successfully even if ingestion partially fails.

2. **Fetch** — `scraper.fetch_feed(source: Source) -> list[RawEntry]` fetches the feed URL from
   `FEED_URLS` (defined in `backend/app/sources.py` — the canonical registry for all feed sources
   alongside the `Source` StrEnum) via `httpx`, passes `response.text` to `feedparser.parse()`,
   and returns a list of raw feedparser entries capped at `settings.scrape_max_per_source`.
   Feedparser's own network fetch is never used.

3. **Entry cap** — `fetch_feed` returns at most `settings.scrape_max_per_source` entries per
   source call, regardless of feed size. `scrape_max_per_source` is declared in `Settings` as
   `scrape_max_per_source: int = 10` reading from `SCRAPE_MAX_PER_SOURCE` env var (already in
   `config.py` and `.env.example`).

4. **Entry parsing and validation** — `scraper.parse_entry(entry, source) -> Article | None` maps
   a raw feedparser entry to an `Article` ORM model. Returns `None` for any entry where title,
   URL, or description is missing or blank. The caller logs exactly one `WARNING` per `None` result
   (e.g. `"Skipping entry: missing required field source=NYT url=..."`). No exception is raised;
   no retry is attempted.

5. **Upsert** — articles are inserted with `INSERT ... ON CONFLICT (url) DO NOTHING`. Running the
   pipeline twice against the same feed produces exactly the same number of `articles` rows as
   running it once.

6. **Per-source commit** — after processing each source (upsert complete), the session commits
   immediately. If source 2 fails, source 1's rows are already durable.

7. **Per-source error isolation** — if `fetch_feed` raises for a source (network error, non-2xx
   response, feedparser exception), that source is skipped with exactly one `WARNING` log line.
   The remaining sources still run. The batch does not abort. If every source fails, `ingest_all`
   raises `ServiceUnavailableError` (defined in `app/exceptions.py`, maps to 503).

8. **Return value** — `ingest_all` returns `IngestResult(inserted: list[Article], fetched: int)`
   where `inserted` contains the ORM objects for rows actually written (excluding `ON CONFLICT`
   skips) and `fetched` is the total count of valid entries seen across all sources before dedup.
   Returning the full objects means the next pipeline stage can iterate over new articles without
   a follow-up DB query; `fetched` gives the endpoint the pre-dedup count for the response body.

9. **Source coverage** — all three sources in `FEED_URLS` (`NYT`, `NPR`, `GUARDIAN`) are fetched
   on every `ingest_all` call. No source is hardcoded or skipped.

10. **Cap respected per source** — with `SCRAPE_MAX_PER_SOURCE=3`, each source contributes at
    most 3 articles, for a maximum of 9 new rows per run.

11. **Unit test isolation** — no real network calls or real DB connections in unit tests:
    - `fetch_feed` tests mock `httpx.AsyncClient` and `feedparser.parse`.
    - `parse_entry` tests pass hand-crafted feedparser entry dicts directly — no mock needed.
    - `ingest_all` tests mock `fetch_feed` and `AsyncSession`.

12. **`POST /api/scrape` — happy path** — calls `ingest_all`, returns `202 Accepted` with body
    `{"inserted": N, "fetched": M}` where `N` is the count of new `articles` rows written and
    `M` is the total number of valid entries fetched across all sources in this run (before dedup).

13. **`POST /api/scrape` — all sources failed** — if `ingest_all` raises `ServiceUnavailableError`,
    the endpoint returns `503 Service Unavailable` with `{"detail": "All RSS sources failed"}`.
    The existing `AppError` exception handler in `main.py` handles this automatically.

14. **`POST /api/scrape` — idempotent** — calling the endpoint twice in a row returns `202` both
    times; the second call inserts 0 rows (`{"inserted": 0, "fetched": M}`). No error is raised.

---

## Out of Scope

- LLM transformation and `article_fakes` writes (separate task)
- `article_fakes` table or `transform_status` field (not touched)
- ARQ queue or worker process (separate task / Iteration 3)
- Scheduled / periodic scraping (Iteration 3 bonus)
- API endpoints that expose or read articles (next task)
- Frontend (later task)
- Retry logic or dead-letter queue (Iteration 2)
- Any feed validation beyond title, URL, and description presence

---

## Decisions

1. **`httpx` fetch + `feedparser.parse(text)`** — feedparser's own network fetch is never used.
   Reason: testability — mock `httpx`, control exactly what feedparser sees.

2. **Per-source commit** — commit after each source completes (AC 6). A source-level failure
   never rolls back already-persisted sources. Simpler than per-article commits since there is
   no LLM call between upsert and commit.

3. **Bulk insert via `insert().on_conflict_do_nothing()`** — single SQL statement per source,
   returns `rowcount` to determine how many rows were actually inserted. Cleaner than
   `session.add_all()` for counting new rows without a follow-up query.

4. **Validation drops on missing title, URL, or description** — `parse_entry` returns `None`;
   caller logs `WARNING` and continues. No exception, no retry. URL is also validated (not just
   title and description) because a row without a URL cannot satisfy the `UNIQUE` constraint and
   would error at insert time.

5. **Per-source error isolation** — `ingest_all` wraps each source's fetch in a try/except.
   Reason: one unavailable feed should not prevent the other two from running.

6. **202 over 200 for `POST /api/scrape`** — 202 Accepted is the right status now and stays
   correct when the next task adds ARQ: the endpoint will trigger jobs and return before
   transformation completes. Using 202 from day one avoids a status-code change later.

7. **Response carries both `inserted` and `fetched`** — `inserted` tells the caller how many
   new articles landed in the DB; `fetched` tells how many the feeds returned before dedup.
   The gap between them is visible dedup signal, useful for debugging and future monitoring.

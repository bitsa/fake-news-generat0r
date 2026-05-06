# Task Plan: article-transformer

## Context

`rss-scraper` is complete. `scraper.ingest_all(session)` runs on startup, upserts articles, and
returns an `IngestResult` containing the list of newly inserted `Article` rows. No `article_fakes`
rows exist yet. ARQ is installed and Redis is running via Docker Compose, but no worker jobs or
ARQ pool wiring exist.

---

## What This Task Adds

### 1. Ingestor coordinator — `backend/app/services/ingestor.py`

A new `async def run(session: AsyncSession, arq_pool: ArqRedis) -> int` function:

- Calls `scraper.ingest_all(session)` → `IngestResult`
- For each newly inserted `Article`, inserts an `article_fakes` row with
  `transform_status='pending'`
- Enqueues an ARQ job `transform_article(article_id)` for each (best-effort — log a `WARNING`
  if enqueue fails, do not abort the whole run)
- Returns the count of jobs successfully enqueued

`scraper.py` is **not modified**.

### 2. ARQ worker job — `backend/app/worker.py`

`async def transform_article(ctx, article_id: int)`:

- Fetches the `Article` from DB (skip gracefully if not found — log and return)
- Generates mock fake content: static lorem ipsum strings — **no OpenAI call**
  - `fake_title`: fixed satirical placeholder string
  - `fake_description`: fixed satirical placeholder string
- On success: `UPDATE article_fakes SET transform_status='completed', title=<fake_title>,
  description=<fake_description>, model=settings.openai_model_transform,
  temperature=settings.openai_temperature_transform`
- On failure: `DELETE FROM article_fakes WHERE article_id=...`, log the error. No retry
  (`max_tries=1`).

Also includes a `WorkerSettings` class (ARQ convention) so the worker process can be launched via
`arq app.worker.WorkerSettings`:

```python
class WorkerSettings:
    functions = [transform_article]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
```

### 3. ARQ pool module — `backend/app/arq_client.py`

Mirrors `redis_client.py` in style. Exposes:

- `async def create_arq_pool() -> ArqRedis` — creates the pool on startup
- `async def close_arq_pool(pool: ArqRedis) -> None` — closes on shutdown
- `def get_arq_pool(request: Request) -> ArqRedis` — FastAPI dependency that reads
  `request.app.state.arq_pool`

### 4. Lifespan update — `backend/app/main.py`

- Creates the ARQ pool via `arq_client.create_arq_pool()` and stores it on `app.state.arq_pool`
- Switches from `scraper.ingest_all(session)` to `ingestor.run(session, app.state.arq_pool)`
- Closes the pool in the shutdown phase via `arq_client.close_arq_pool(app.state.arq_pool)`
- Recovery on startup: re-enqueue any `article_fakes` rows where
  `transform_status = 'pending' AND created_at < NOW() - interval '5 min'` (handles
  crash-during-flight from a prior run). This runs before `ingestor.run()`.

### 5. Scrape endpoint update — `backend/app/routers/scrape.py`

`POST /api/scrape` now calls `ingestor.run(session, arq_pool)` instead of
`scraper.ingest_all(session)` directly.

Response changes: `{"inserted": N, "fetched": M, "enqueued": K}` — adds `enqueued` count.
Status stays `202 Accepted`. Error path unchanged (503 if all sources fail).

---

## Decisions (locked in design session)

| Topic | Decision |
|---|---|
| OpenAI call | **Not implemented in this task.** Static mock content only. Real call deferred. |
| Mock content | Fixed static strings — same for every article. No per-article derivation. |
| Stored `model`/`temperature` | Written as `settings.openai_model_transform` / `settings.openai_temperature_transform` even for mock, so the column schema stays valid and the real call is a drop-in replacement later. |
| `openai_api_key` | Remains a required `Settings` field. Set `OPENAI_API_KEY=sk-fake-key-for-dev` in `.env`. No code change. |
| ARQ pool | New `arq_client.py` module (mirrors `redis_client.py`). Stored on `app.state`. Injected via `get_arq_pool` dependency. |
| `WorkerSettings` | Included in `worker.py` this task so the worker container can be started. |
| `/api/scrape` | Updated to call `ingestor.run()` — full flow including pending rows + job enqueue. |
| Enqueue failure | Best-effort: log `WARNING`, do not raise, do not abort the scrape run. |
| Pending row durability | `article_fakes` with `transform_status='pending'` is the source of truth. Queue is fast-path only. |
| Recovery | On startup, re-enqueue stale pending rows (`created_at < NOW() - 5 min`). |

---

## Files to Create

```text
backend/app/arq_client.py
backend/app/services/ingestor.py
backend/app/worker.py
backend/tests/unit/test_ingestor.py
backend/tests/unit/test_worker.py
```

## Files to Modify

```text
backend/app/main.py         — wire ARQ pool; switch lifespan call; add recovery step
backend/app/routers/scrape.py — call ingestor.run(); add enqueued to response
```

---

## Out of Scope

- Real OpenAI call (separate task — deferred)
- Frontend changes
- Scheduled / periodic scraping
- Retry logic, dead-letter queue
- `failed` / `processing` transform states (schema intentionally omits them — see context.md)
- Any change to `scraper.py`
- Docker Compose worker service wiring (infra task)

# ARQ Transform Pipeline — Dev Plan

## MUST READ FIRST

- [`context.md`](../context.md) — decisions, standards (async-only, type hints, `AppError`,
  Pydantic Settings, logging rules, ARQ durability model, `max_tries=1`)
- [`plans/plan.md`](../plans/plan.md) — workflow and doc structure
- [`docs/article-transformer-spec.md`](article-transformer-spec.md) — source of truth for this task

Key source files examined:

- `backend/app/models.py` — `Article` (PK `id`) and `ArticleFake` (PK = FK `article_id`,
  `transform_status` CHECK constraint: `'pending' | 'completed'`, `server_default='pending'`,
  nullable `title`, `description`, `model`, `temperature`)
- `backend/app/services/scraper.py` — **immutable**; `IngestResult.inserted: list[Article]`
  carries DB-assigned `id` values returned via `RETURNING`; `ingest_all` commits per source
- `backend/app/routers/scrape.py` — currently returns `{"inserted": N, "fetched": M}`; needs
  `enqueued` added; no ARQ dependency yet
- `backend/app/main.py` — lifespan: migrations → startup scrape → yield → `close_redis`; no ARQ
  pool, no recovery step yet
- `backend/app/config.py` — `openai_model_transform: str = "gpt-4o-mini"`,
  `openai_temperature_transform: float = 0.9` already declared
- `backend/app/redis_client.py` — `get_redis()` returns `redis.asyncio.Redis`; separate from ARQ
  pool (ARQ manages its own connection)
- `backend/app/exceptions.py` — `AppError`, `ServiceUnavailableError` already defined
- `backend/tests/conftest.py` — sets `OPENAI_API_KEY=sk-test-placeholder`; `app` and `client`
  fixtures
- `backend/tests/routers/test_scrape.py` — `scrape_client` fixture patches migrations, session,
  `scraper.ingest_all`, and `close_redis`; assertions currently expect only
  `{"inserted": N, "fetched": M}` — **these will break and must be updated**

---

## Files to Touch / Create

| Action | Path |
|--------|------|
| **CREATE** | `backend/app/arq_client.py` |
| **CREATE** | `backend/app/services/transformer.py` |
| **CREATE** | `backend/app/workers/__init__.py` |
| **CREATE** | `backend/app/workers/transform.py` |
| **MODIFY** | `backend/app/main.py` — lifespan: add ARQ pool, recovery, transformer call |
| **MODIFY** | `backend/app/config.py` — add `transform_recovery_threshold_minutes` field |
| **MODIFY** | `backend/app/routers/scrape.py` — add `arq_pool` dep, call transformer; response shape unchanged |
| **CREATE** | `backend/tests/unit/test_transformer.py` |
| **CREATE** | `backend/tests/unit/test_transform_worker.py` |
| **MODIFY** | `backend/tests/routers/test_scrape.py` — update fixture + assertions for new response shape |

---

## Interfaces / Contracts to Expose

### `backend/app/arq_client.py`

```python
from arq.connections import ArqRedis
from fastapi import Request

async def create_arq_pool() -> ArqRedis: ...
async def close_arq_pool(pool: ArqRedis) -> None: ...
async def get_arq_pool(request: Request) -> ArqRedis: ...
```

`get_arq_pool` reads `request.app.state.arq_pool` (set by the lifespan). Any request that
arrives before lifespan completes pool creation will 500 — acceptable for MVP per spec open
question 4.

### `backend/app/services/transformer.py`

```python
from arq.connections import ArqRedis
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Article

async def create_and_enqueue(
    session: AsyncSession,
    arq_pool: ArqRedis,
    articles: list[Article],
) -> None:
    """
    Insert one ArticleFake(pending) per article, commit, then enqueue one ARQ job per article.
    Enqueue failures are caught per-article, logged at WARNING, and do not abort the loop.
    """
    ...

async def recover_stale_pending(
    session: AsyncSession,
    arq_pool: ArqRedis,
) -> int:
    """
    Re-enqueue article_fakes rows where transform_status='pending'
    AND created_at < NOW() - 5 minutes.
    Returns count of rows re-enqueued.
    """
    ...
```

### `backend/app/workers/transform.py`

```python
from arq.connections import RedisSettings

MOCK_TITLE: str   # constant, non-empty
MOCK_DESCRIPTION: str   # constant, non-empty

async def transform_article(ctx: dict, article_id: int) -> None: ...

class WorkerSettings:
    functions = [transform_article]
    redis_settings: RedisSettings  # derived from settings.redis_url at class-body time
    max_tries = 1
```

### `POST /api/scrape` contract — unchanged

```text
POST /api/scrape
  → 202 Accepted  {"inserted": int, "fetched": int}   (same as before)
  → 503           {"detail": "All RSS sources failed"}
```

---

## Implementation Plan

### Step 1 — Modify `backend/app/config.py`

Add one field to `Settings`:

```python
transform_recovery_threshold_minutes: int = 5
```

### Step 3 — Create `backend/app/arq_client.py`

- Import `create_pool` from `arq`, `RedisSettings` from `arq.connections`, `Request` from
  `fastapi`, `settings` from `app.config`.
- `create_arq_pool`: call `await create_pool(RedisSettings.from_dsn(settings.redis_url))`.
- `close_arq_pool(pool)`: call `await pool.aclose()`.
- `get_arq_pool(request)`: return `request.app.state.arq_pool`.

### Step 4 — Create `backend/app/services/transformer.py`

#### 4a. `create_and_enqueue`

1. If `articles` is empty, return immediately (no DB or queue work needed).
2. Batch-insert `ArticleFake` rows via `session.add_all([ArticleFake(article_id=a.id) for a in
   articles])`. The `transform_status` server default handles the `'pending'` value.
3. `await session.commit()` — fakes are now durable before any enqueue attempt.
4. Loop over `articles`; for each: `await arq_pool.enqueue_job("transform_article", article.id)`.
   Wrap in `try/except Exception`: on failure log at `WARNING` level
   (`"transformer.enqueue.failed article_id=%d"`), do **not** re-raise, do not roll back the
   committed fake row.

#### 4b. `recover_stale_pending`

1. Compute `stale_threshold = datetime.now(UTC) - timedelta(minutes=settings.transform_recovery_threshold_minutes)`.
2. Query: `SELECT article_id FROM article_fakes WHERE transform_status = 'pending' AND created_at
   < :stale_threshold` using `sa.select(ArticleFake.article_id).where(...)`.
3. For each returned `article_id`: `await arq_pool.enqueue_job("transform_article", article_id)`.
   Wrap in `try/except Exception`; log `WARNING` on failure; do not re-raise.
4. Return count of successfully re-enqueued rows.

### Step 5 — Create `backend/app/workers/__init__.py`

Empty file.

### Step 6 — Create `backend/app/workers/transform.py`

#### 6a. Constants

Choose two non-empty, non-null static strings for `MOCK_TITLE` and `MOCK_DESCRIPTION`. Any
satirical placeholder text satisfies the spec — real content comes in a later task.

#### 6b. `transform_article(ctx, article_id)`

Logging convention: one start line + one termination line per code path (logging standard).

1. `log.info("worker.transform.start article_id=%d", article_id)`
2. Open `async with AsyncSessionLocal() as session:` — the worker runs outside FastAPI; use
   `AsyncSessionLocal` directly (imported from `app.db`).
3. `fake = await session.get(ArticleFake, article_id)`.
4. If `fake is None`: `log.info("worker.transform.skip article_id=%d", article_id)`; return.
   No exception raised.
5. In a `try` block:
   - Set `fake.title = MOCK_TITLE`, `fake.description = MOCK_DESCRIPTION`,
     `fake.model = settings.openai_model_transform`,
     `fake.temperature = settings.openai_temperature_transform`,
     `fake.transform_status = "completed"`.
   - `await session.commit()`.
   - `log.info("worker.transform.done article_id=%d", article_id)`.
6. In the `except Exception` block:
   - `await session.rollback()` to discard the partial update.
   - Execute a targeted delete: `await session.execute(sa.delete(ArticleFake).where(
     ArticleFake.article_id == article_id))`.
   - `await session.commit()` to persist the deletion.
   - `log.error("worker.transform.failed article_id=%d", article_id, exc_info=True)`.
   - Do **not** re-raise — ARQ `max_tries=1` means no retry; silencing prevents ARQ from logging
     a spurious job failure.

#### 6c. `WorkerSettings`

```python
class WorkerSettings:
    functions = [transform_article]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    max_tries = 1
```

### Step 7 — Modify `backend/app/main.py`

Add imports: `from app import arq_client`, `from app.services import transformer`.

Replace the lifespan body as follows:

```text
await _run_migrations()
app.state.arq_pool = await arq_client.create_arq_pool()
try:
    async with AsyncSessionLocal() as session:
        await transformer.recover_stale_pending(session, app.state.arq_pool)
        result = await scraper.ingest_all(session)
        await transformer.create_and_enqueue(session, app.state.arq_pool, result.inserted)
    log.info("startup.scrape.complete")
except Exception:
    log.warning("startup.scrape.failed", exc_info=True)
yield
await arq_client.close_arq_pool(app.state.arq_pool)
await close_redis()
```

Recovery runs before `ingest_all` per spec open question 2 (assumed ordering confirmed in spec).

### Step 8 — Modify `backend/app/routers/scrape.py`

1. Add imports: `ArqRedis` from `arq.connections`, `get_arq_pool` from `app.arq_client`,
   `transformer` from `app.services`.
2. Add `arq_pool: ArqRedis = Depends(get_arq_pool)` parameter to `scrape()`.
3. After calling `await scraper.ingest_all(session)`, call:
   `await transformer.create_and_enqueue(session, arq_pool, result.inserted)`.
4. Return value and type annotation are unchanged: `{"inserted": len(result.inserted), "fetched": result.fetched}`.

### Step 9 — Write `tests/unit/test_transformer.py`

See "Unit Tests Required" section.

### Step 10 — Write `tests/unit/test_transform_worker.py`

See "Unit Tests Required" section.

### Step 11 — Update `tests/routers/test_scrape.py`

1. **`scrape_client` fixture** — add patches for the new lifespan callables:
   - `app.main.arq_client.create_arq_pool` → `AsyncMock(return_value=AsyncMock())`
   - `app.main.arq_client.close_arq_pool` → `AsyncMock()`
   - `app.main.transformer.recover_stale_pending` → `AsyncMock()`
   - `app.main.transformer.create_and_enqueue` → `AsyncMock()`
   - Add `dependency_overrides[get_arq_pool] = lambda: AsyncMock()` (for router-level tests).
2. **Existing assertions** — `r.json() == {"inserted": N, "fetched": M}` is unchanged; no
   update needed for the response shape itself.
3. **Router test patches** — each router-level test that patches `scraper.ingest_all` should also
   patch `app.routers.scrape.transformer.create_and_enqueue` to an `AsyncMock()` so the router
   can complete without a real ARQ pool.

---

## Unit Tests Required

All tests mock I/O. `AsyncSession` is mocked via `AsyncMock`. ARQ pool is mocked via `AsyncMock`.
`AsyncSessionLocal` is patched in worker tests.

### `tests/unit/test_transformer.py` — `transformer.create_and_enqueue`

| Test name | Criterion |
|-----------|-----------|
| `test_create_and_enqueue_inserts_pending_fake_for_each_new_article` | AC: every newly inserted article has one `article_fakes` row with `pending` status |
| `test_create_and_enqueue_commits_session_after_inserting_fakes` | AC: fakes present in DB before response returned |
| `test_create_and_enqueue_does_nothing_when_articles_list_is_empty` | AC: no DB writes or enqueue calls when inserted list is empty |
| `test_create_and_enqueue_failed_enqueue_does_not_abort_remaining_articles` | AC: one failed enqueue doesn't abort the loop |
| `test_create_and_enqueue_failed_enqueue_emits_warning_log` | AC: failed enqueue emits exactly one `WARNING`-level log event |

### `tests/unit/test_transformer.py` — `transformer.recover_stale_pending`

| Test name | Criterion |
|-----------|-----------|
| `test_recover_stale_pending_enqueues_rows_older_than_5_minutes` | AC: stale pending rows are re-enqueued |
| `test_recover_stale_pending_skips_rows_created_within_5_minutes` | AC: recent pending rows are NOT re-enqueued |
| `test_recover_stale_pending_skips_completed_rows` | AC: completed rows are never re-enqueued |

### `tests/unit/test_transform_worker.py` — `transform_article`

| Test name | Criterion |
|-----------|-----------|
| `test_transform_article_sets_completed_status_and_fills_mock_content` | AC: transitions to `completed`, non-null `title`/`description` |
| `test_transform_article_completed_row_model_equals_settings_openai_model_transform` | AC: `model == settings.openai_model_transform` |
| `test_transform_article_completed_row_temperature_equals_settings_openai_temperature_transform` | AC: `temperature == settings.openai_temperature_transform` |
| `test_transform_article_skips_nonexistent_article_id_without_raising` | AC: non-existent `article_id` raises no exception |
| `test_transform_article_skips_nonexistent_article_id_logs_skip_event` | AC: log event records the skip |
| `test_transform_article_deletes_fake_row_on_unexpected_exception` | AC: `article_fakes` row deleted on exception |
| `test_transform_article_preserves_article_row_when_fake_deleted_on_exception` | AC: `articles` row untouched after fake deletion |

---

## Definition of Done

- [ ] `POST /api/scrape` response shape is unchanged: `{"inserted": N, "fetched": M}`, `202`
- [ ] A failed enqueue emits one `WARNING` and does not abort other articles
- [ ] Every newly inserted article has exactly one `article_fakes` row (`pending`, `title=NULL`,
  `description=NULL`) committed to the DB before the HTTP response returns
- [ ] Duplicate articles (on-conflict-do-nothing path) receive no new `article_fakes` rows
- [ ] 503 path from `ingest_all` is unchanged
- [ ] When `transform_article` runs for an existing article: row transitions to `completed` with
  non-null `title`, `description`, `model == settings.openai_model_transform`,
  `temperature == settings.openai_temperature_transform`
- [ ] When `transform_article` runs for a non-existent `article_id`: no exception, DB unchanged,
  skip is logged
- [ ] When `transform_article` raises an unexpected exception mid-run: `article_fakes` row deleted,
  `articles` row preserved, error logged
- [ ] On app startup: stale `pending` rows (older than 5 min) are re-enqueued; recent `pending`
  rows and `completed` rows are untouched
- [ ] `backend/app/services/scraper.py` is unmodified (diff is empty for that file)
- [ ] All unit tests pass with no real DB, Redis, or LLM calls
- [ ] `ruff` + `black` pass on all touched files

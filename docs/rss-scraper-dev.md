# RSS Scraper — Dev Plan

## MUST READ FIRST

- [`context.md`](../context.md) — decisions, standards (async-only, type hints, `AppError`, Pydantic Settings, logging rules)
- [`plans/plan.md`](../plans/plan.md) — workflow and doc structure
- [`docs/rss-scraper-spec.md`](rss-scraper-spec.md) — source of truth for this task

Key source files examined:

- `backend/app/models.py` — `Article` ORM model; `description` is `Mapped[str | None]` (nullable), `url` has `unique=True`
- `backend/app/sources.py` — `Source` StrEnum (`NYT`, `NPR`, `GUARDIAN`) and `FEED_URLS` dict; both already exist
- `backend/app/config.py` — `Settings` already declares `scrape_max_per_source: int = 10`
- `backend/app/exceptions.py` — `AppError`, `ServiceUnavailableError` (status 503) already defined
- `backend/app/main.py` — lifespan runs `_run_migrations()` then yields; `AppError` handler registered; no scrape call yet
- `backend/app/db.py` — `AsyncSessionLocal` (async_sessionmaker) exists; no `get_session` dependency yet
- `backend/tests/routers/test_health.py` — router test pattern: `patch` at module level, `client` fixture from conftest
- `backend/pyproject.toml` — `httpx` and `feedparser` already in dependencies

---

## Files to Touch / Create

| Action | Path |
|--------|------|
| **NEW** | `backend/app/services/scraper.py` |
| **NEW** | `backend/app/routers/scrape.py` |
| **MODIFY** | `backend/app/db.py` — add `get_session` FastAPI dependency |
| **MODIFY** | `backend/app/main.py` — call `ingest_all` in lifespan; include scrape router |
| **NEW** | `backend/tests/unit/test_scraper.py` |
| **NEW** | `backend/tests/routers/test_scrape.py` |

---

## Interfaces / Contracts to Expose

### `backend/app/db.py` — new addition

```python
from collections.abc import AsyncGenerator

async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
```

### `backend/app/services/scraper.py`

```python
from typing import Any
from dataclasses import dataclass

# feedparser entry dict-like object; supports both .attr and ["key"] access
type RawEntry = Any

@dataclass
class IngestResult:
    inserted: list[Article]
    fetched: int

async def fetch_feed(source: Source) -> list[RawEntry]: ...
def parse_entry(entry: RawEntry, source: Source) -> Article | None: ...
async def ingest_all(session: AsyncSession) -> IngestResult: ...
```

### `backend/app/routers/scrape.py`

```text
POST /api/scrape
  → 202 Accepted  {"inserted": int, "fetched": int}
  → 503           {"detail": "All RSS sources failed"}   (via AppError handler)
```

---

## Implementation Plan

### Step 1 — Add `get_session` to `db.py`

Add an async generator dependency after `AsyncSessionLocal`. Import `AsyncGenerator` from `collections.abc`. The yielded session is the caller's responsibility to commit; `ingest_all` commits internally per-source.

### Step 2 — Create `backend/app/services/scraper.py`

#### 2a. Imports and types

- `logging`, `Any`, `dataclass`, `datetime`, `timezone`, `calendar`
- `httpx`
- `feedparser`
- SQLAlchemy: `AsyncSession`, `insert` from `sqlalchemy.dialects.postgresql` (use the pg-dialect `insert` for `on_conflict_do_nothing`)
- `Article`, `Source`, `FEED_URLS`, `settings`, `ServiceUnavailableError`
- Define `type RawEntry = Any` and `@dataclass IngestResult`

#### 2b. `fetch_feed(source: Source) -> list[RawEntry]`

- Open `httpx.AsyncClient()`, GET `FEED_URLS[source]`
- Call `response.raise_for_status()` — any non-2xx raises `httpx.HTTPStatusError`
- Pass `response.text` to `feedparser.parse()` — never use feedparser's own network fetch
- Return `feed.entries[:settings.scrape_max_per_source]`

#### 2c. `parse_entry(entry: RawEntry, source: Source) -> Article | None`

- Extract: `title = (entry.get("title") or "").strip()`
- Extract: `url = (entry.get("link") or "").strip()`
- Extract: `description = (entry.get("summary") or "").strip()`
- If any of the three is empty after strip → return `None`
- Parse `published_at`: if `entry.get("published_parsed")` is not None, convert via
  `datetime(*entry["published_parsed"][:6], tzinfo=timezone.utc)`; else `None`
- Return `Article(source=source, title=title, url=url, description=description, published_at=published_at)`

#### 2d. `ingest_all(session: AsyncSession) -> IngestResult`

```python
all_inserted: list[Article] = []
total_fetched: int = 0
failed: int = 0

for source in Source:
    try:
        raw_entries = await fetch_feed(source)
        valid_articles: list[Article] = []
        for entry in raw_entries:
            article = parse_entry(entry, source)
            if article is None:
                log.warning("scraper.entry.dropped source=%s url=%s", source, entry.get("link"))
                continue
            valid_articles.append(article)

        total_fetched += len(valid_articles)

        if valid_articles:
            stmt = (
                pg_insert(Article)
                .values([
                    {c.key: getattr(a, c.key) for c in Article.__mapper__.column_attrs}
                    for a in valid_articles
                ])
                .on_conflict_do_nothing(index_elements=["url"])
                .returning(Article)
            )
            result = await session.execute(stmt)
            all_inserted.extend(result.scalars().all())

        await session.commit()

    except Exception:
        log.warning("scraper.source.failed source=%s", source, exc_info=True)
        failed += 1
        continue

if failed == len(list(Source)):
    raise ServiceUnavailableError("All RSS sources failed")

return IngestResult(inserted=all_inserted, fetched=total_fetched)
```

Note on bulk values dict: use only the columns that `parse_entry` populates —
`source`, `title`, `url`, `description`, `published_at`. Do not include `id` or
`created_at` (server defaults). Build the dict explicitly to avoid mapping noise.

### Step 3 — Create `backend/app/routers/scrape.py`

- `router = APIRouter(prefix="/api")`
- `@router.post("/scrape", status_code=202)`
- Signature: `async def scrape(session: AsyncSession = Depends(get_session)) -> dict`
- Body: call `await ingest_all(session)`, return `{"inserted": len(result.inserted), "fetched": result.fetched}`
- Do not catch `ServiceUnavailableError` — let it propagate to the `AppError` handler in `main.py`

### Step 4 — Modify `backend/app/main.py`

**4a. Lifespan** — after `await _run_migrations()`, add:

```python
try:
    async with AsyncSessionLocal() as session:
        await scraper.ingest_all(session)
    log.info("startup.scrape.complete")
except Exception:
    log.warning("startup.scrape.failed", exc_info=True)
```

The app must start even if all sources fail — catch `Exception` broadly, log as WARNING.

**4b. Include scrape router** — `app.include_router(scrape.router)`

**4c. Imports** — add `log = logging.getLogger(__name__)`, import `AsyncSessionLocal` from `app.db`,
import `scraper` from `app.services`, import `scrape` router.

### Step 5 — Write `tests/unit/test_scraper.py`

See "Unit Tests Required" section.

### Step 6 — Write `tests/routers/test_scrape.py`

See "Unit Tests Required" section.

---

## Unit Tests Required

All tests mock I/O per AC11. `fetch_feed` tests mock `httpx.AsyncClient` and `feedparser.parse`.
`parse_entry` tests pass hand-crafted dicts. `ingest_all` tests mock `fetch_feed` and `AsyncSession`.

### `tests/unit/test_scraper.py`

| Test name | Criterion |
|-----------|-----------|
| `test_fetch_feed_passes_response_text_to_feedparser` | AC2 — httpx GET used; `feedparser.parse` called with `response.text`, not the URL |
| `test_fetch_feed_caps_at_scrape_max_per_source` | AC3, AC10 — feed has 20 entries, cap=3; only 3 returned |
| `test_parse_entry_returns_article_for_valid_entry` | AC4 — all fields present; returns `Article` with correct field mapping |
| `test_parse_entry_returns_none_for_missing_title` | AC4 — entry without `title`; returns `None` |
| `test_parse_entry_returns_none_for_missing_url` | AC4 — entry without `link`; returns `None` |
| `test_parse_entry_returns_none_for_missing_description` | AC4 — entry without `summary`; returns `None` |
| `test_parse_entry_returns_none_for_blank_title` | AC4 — title is whitespace-only; returns `None` |
| `test_parse_entry_returns_none_for_blank_url` | AC4 — link is whitespace-only; returns `None` |
| `test_parse_entry_returns_none_for_blank_description` | AC4 — summary is whitespace-only; returns `None` |
| `test_ingest_all_fetches_all_three_sources` | AC9 — `fetch_feed` called once per source in `Source` |
| `test_ingest_all_commits_after_each_source` | AC6 — `session.commit` called once per source, not once at end |
| `test_ingest_all_returns_inserted_articles_and_fetched_count` | AC8 — `IngestResult.inserted` is the list returned by RETURNING; `fetched` equals total valid entries seen |
| `test_ingest_all_uses_on_conflict_do_nothing` | AC5 — `session.execute` called; second call with same data inserts 0 (mock returns empty list) |
| `test_ingest_all_logs_warning_for_dropped_entry` | AC4 — `ingest_all` emits one `WARNING` per `None` from `parse_entry` |
| `test_ingest_all_skips_failed_source_continues_others` | AC7 — one source raises; remaining sources still processed; result includes their articles |
| `test_ingest_all_logs_warning_per_failed_source` | AC7 — WARNING logged for each failed source |
| `test_ingest_all_raises_service_unavailable_when_all_sources_fail` | AC7 — all three sources raise; `ServiceUnavailableError` raised |

### `tests/routers/test_scrape.py`

| Test name | Criterion |
|-----------|-----------|
| `test_lifespan_calls_ingest_all_after_migrations` | AC1 — mock `_run_migrations` and `scraper.ingest_all`; verify `ingest_all` called after migrations |
| `test_post_scrape_happy_path_returns_202_with_inserted_and_fetched` | AC12 — mock `ingest_all` returns `IngestResult`; response is 202 with correct counts |
| `test_post_scrape_all_sources_failed_returns_503` | AC13 — mock `ingest_all` raises `ServiceUnavailableError`; response is 503 with `{"detail": "All RSS sources failed"}` |
| `test_post_scrape_second_call_returns_202_with_zero_inserted` | AC14 — mock `ingest_all` returns `IngestResult(inserted=[], fetched=M)`; response is 202 with `inserted=0` |

---

## Definition of Done

- [ ] `POST /api/scrape` returns 202 with `{"inserted": N, "fetched": M}` on happy path
- [ ] `POST /api/scrape` returns 503 with `{"detail": "All RSS sources failed"}` when all sources fail
- [ ] Second call to `POST /api/scrape` returns 202 with `inserted=0` (no duplicates)
- [ ] `fetch_feed` uses `httpx` + `feedparser.parse(text)` — never feedparser's own fetch
- [ ] `fetch_feed` returns at most `scrape_max_per_source` entries
- [ ] `parse_entry` returns `None` for any entry missing or blank title, URL, or description
- [ ] One WARNING log per dropped entry; no exception raised; no retry
- [ ] Per-source commit: source 1's rows durable even if source 2 fails
- [ ] Per-source error isolation: one failing source does not abort the others
- [ ] All three sources (`NYT`, `NPR`, `GUARDIAN`) fetched on every `ingest_all` call
- [ ] App starts successfully even if all sources fail at startup
- [ ] 18 unit tests pass (17 in `test_scraper.py` + 1 lifespan test); no real network or DB calls
- [ ] `ruff` + `black` pass on all touched files

# GET /api/articles — Dev Plan

## MUST READ FIRST

- `context.md` — decisions, standards, conventions (async-only, type hints required, `black`/`ruff`, logging rules)
- `plans/plan.md` — workflow philosophy and doc structure
- `docs/get-articles-spec.md` — acceptance criteria (14 criteria, this task's source of truth)
- `backend/app/models.py` — `Article` and `ArticleFake` ORM models (examined directly)
- `backend/app/routers/scrape.py` — existing router pattern (`APIRouter(prefix="/api")`, `Depends(get_session)`)
- `backend/app/main.py` — how routers are registered (`include_router`)
- `backend/app/schemas/health.py` — existing Pydantic schema pattern
- `backend/app/sources.py` — `Source` StrEnum values (`NYT`, `NPR`, `Guardian`)
- `backend/tests/routers/test_scrape.py` — router test pattern (mock service, `ASGITransport`, `dependency_overrides`)
- `backend/tests/conftest.py` — shared `app` and `client` fixtures

---

## Files to Touch / Create

| Action | Path |
|---|---|
| Create | `backend/app/schemas/articles.py` |
| Create | `backend/app/services/articles.py` |
| Create | `backend/app/routers/articles.py` |
| Modify | `backend/app/main.py` |
| Create | `backend/tests/routers/test_articles.py` |
| Create | `backend/tests/unit/test_articles_service.py` |

---

## Interfaces / Contracts to Expose

### Pydantic schemas — `backend/app/schemas/articles.py`

```python
class ArticleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    source: str          # StrEnum serialises to its .value ("NYT", "NPR", "Guardian")
    title: str
    description: str | None
    url: str
    published_at: datetime | None
    created_at: datetime

class FakeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int = Field(validation_alias="article_id")  # PK on ArticleFake is article_id, not id
    title: str | None
    description: str | None
    model: str | None
    temperature: float | None
    created_at: datetime

class ArticlePairOut(BaseModel):
    id: int
    article: ArticleOut
    fake: FakeOut

class ArticlesResponse(BaseModel):
    total: int
    pending: int
    articles: list[ArticlePairOut]
```

### Service function — `backend/app/services/articles.py`

```python
async def get_articles(session: AsyncSession) -> ArticlesResponse: ...
```

Returns `ArticlesResponse` built from three queries (see Implementation plan below).

### Router endpoint — `backend/app/routers/articles.py`

```text
GET /api/articles → 200 ArticlesResponse
```

No path parameters. No query parameters. No auth. Registered under the `/api` prefix via
`APIRouter(prefix="/api")`, consistent with `scrape.py`.

---

## Implementation Plan

### 1. Create `backend/app/schemas/articles.py`

Define `ArticleOut`, `FakeOut`, `ArticlePairOut`, `ArticlesResponse` exactly as shown in the
contracts section above.

Key notes:

- `FakeOut.id` uses `Field(validation_alias="article_id")` — the `ArticleFake` ORM model's PK
  column is named `article_id`, not `id`. This remap satisfies criterion 9 ("`fake.id` equals
  `article.id`") without touching the ORM model.
- `ArticleOut.source: str` — `Source` is a `StrEnum` so `from_attributes=True` serialises it as
  the string value (criterion 11). No explicit validator needed.
- All `datetime` fields are `DateTime(timezone=True)` in the DB; Pydantic serialises them as
  ISO 8601 with `+00:00` offset, satisfying criterion 12.

### 2. Create `backend/app/services/articles.py`

Import: `Article`, `ArticleFake` from `app.models`; `ArticlesResponse`, `ArticleOut`,
`FakeOut`, `ArticlePairOut` from `app.schemas.articles`; SQLAlchemy `select`, `func`;
`AsyncSession`.

Three queries executed sequentially on the provided session:

**Query 1 — total:**

```python
select(func.count()).select_from(Article)
```

Use `session.scalar(...)`. Coerce `None` → `0` with `or 0`.

**Query 2 — pending:**

```python
select(func.count()).select_from(ArticleFake)
    .where(ArticleFake.transform_status == "pending")
```

Same scalar pattern.

**Query 3 — completed pairs:**

```python
select(Article, ArticleFake)
    .join(ArticleFake, Article.id == ArticleFake.article_id)
    .where(ArticleFake.transform_status == "completed")
    .order_by(Article.published_at.desc().nullslast())
```

Use `session.execute(...)`. Call `.all()` to get a list of `Row(Article, ArticleFake)`.

Build `ArticlePairOut` objects by unpacking each row:

```python
ArticlePairOut(
    id=article.id,
    article=ArticleOut.model_validate(article),
    fake=FakeOut.model_validate(fake),
)
```

Return `ArticlesResponse(total=total, pending=pending, articles=pairs)`.

Add one `logger.info("articles.get total=%d pending=%d completed=%d", total, pending, len(pairs))`
log line (context.md logging standard: one log event per significant action).

### 3. Create `backend/app/routers/articles.py`

Mirror the structure of `scrape.py`:

```python
router = APIRouter(prefix="/api")

@router.get("/articles", response_model=ArticlesResponse)
async def get_articles(session: AsyncSession = Depends(get_session)) -> ArticlesResponse:
    return await articles_service.get_articles(session)
```

Import `articles_service` from `app.services.articles` (same pattern as `from app.services
import scraper` in `scrape.py`).

### 4. Update `backend/app/main.py`

Add two lines:

- `from app.routers import health, scrape, articles` (extend existing import)
- `app.include_router(articles.router)` (after `app.include_router(scrape.router)`)

No lifespan changes needed.

### 5. Write `backend/tests/routers/test_articles.py`

Router-level tests using the pattern established in `test_scrape.py`:

- A `pytest_asyncio.fixture` named `articles_client` that uses `app.dependency_overrides[get_session]`
  and patches `app.main._run_migrations`, `app.main.AsyncSessionLocal`,
  `app.main.scraper.ingest_all`, and `app.main.close_redis` to bypass lifespan side-effects.
- Each test patches `app.routers.articles.articles_service.get_articles` with an `AsyncMock`
  that returns a hand-crafted `ArticlesResponse` object.

See **Unit tests required** below for the test function names and what each covers.

### 6. Write `backend/tests/unit/test_articles_service.py`

Service-level tests that mock `session.scalar` and `session.execute` directly to verify that
the three queries produce the correct `ArticlesResponse`. Focus on: ordering is applied correctly,
completed/pending/no-fake filtering logic, and the `article_id` → `id` remapping in `FakeOut`.

---

## Unit Tests Required

Tests in `backend/tests/routers/test_articles.py` (router-level, service mocked):

| Test function | Criterion |
|---|---|
| `test_get_articles_happy_path_completed_pair_returns_200` | 1 |
| `test_get_articles_pending_fake_excluded_from_articles_counted_in_pending` | 2 |
| `test_get_articles_no_fake_article_excluded_from_articles_and_not_in_pending` | 3 |
| `test_get_articles_total_counts_all_articles_regardless_of_fake_status` | 4 |
| `test_get_articles_pending_counts_only_pending_fakes` | 5 |
| `test_get_articles_empty_db_returns_200_with_zeros_and_empty_array` | 6 |
| `test_get_articles_response_shape_has_exactly_three_top_level_keys` | 8 |
| `test_get_articles_each_pair_has_id_article_and_fake_with_all_required_fields` | 9 |
| `test_get_articles_nullable_fields_may_be_null_in_both_article_and_fake` | 10 |
| `test_get_articles_source_field_serialised_as_string_value_not_enum_index` | 11 |
| `test_get_articles_datetime_fields_serialised_as_iso8601_with_timezone` | 12 |
| `test_get_articles_no_auth_required_returns_200` | 13 |
| `test_get_articles_registered_under_api_prefix` | 14 |

Tests in `backend/tests/unit/test_articles_service.py` (service-level, session mocked):

| Test function | Criterion |
|---|---|
| `test_get_articles_service_ordering_later_published_at_appears_first` | 7 |
| `test_get_articles_service_null_published_at_appears_after_dated_articles` | 7 (null ordering) |
| `test_get_articles_service_fake_id_equals_article_id` | 9 (`id` remapping) |

---

## Definition of Done

- [ ] `GET /api/articles` returns `200 OK` for all DB states (empty, pending, completed, mixed)
- [ ] Response body has exactly `total`, `pending`, `articles` at top level
- [ ] Each element in `articles` has `id`, `article`, `fake` with all fields from criterion 9
- [ ] Articles ordered `published_at DESC NULLS LAST`
- [ ] `pending` fakes and no-fake articles absent from `articles`; pending count is correct
- [ ] `source` serialised as StrEnum string value (`NYT`, `NPR`, `Guardian`)
- [ ] All `datetime` fields serialised as ISO 8601 with timezone offset
- [ ] Endpoint reachable at `/api/articles` (no auth)
- [ ] `ruff` and `black` pass with no changes
- [ ] All 16 unit tests pass
- [ ] `tracker.md` updated to `in_qa`

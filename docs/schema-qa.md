# Schema QA Plan

## What to Test

Each numbered test case maps 1-to-1 to an acceptance criterion in `docs/schema-spec.md`.

### Sources Module

**S-1** — `Source` inherits `StrEnum` and has exactly three members with the correct values:
`NYT = "NYT"`, `NPR = "NPR"`, `GUARDIAN = "Guardian"`.

**S-2** — `FEED_URLS` maps `Source.NYT` → `https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml`,
`Source.NPR` → `https://feeds.npr.org/1001/rss.xml`, and `Source.GUARDIAN` → `https://www.theguardian.com/world/rss`.

**S-3** — `FEED_URLS` has exactly three keys — no extras, no missing.

### Alembic Migration

**M-1** — Exactly one migration file exists under `backend/migrations/versions/` (excluding
`__init__.py`); it is the base migration (`down_revision = None`); its filename or docstring
identifies it as the initial schema (slug/description contains `initial_schema`).

**M-2** — `alembic upgrade head` against a fresh Postgres instance exits 0 with no error output.

**M-3** — Running `alembic upgrade head` a second time (DB already at head) exits 0 and produces no
error.

**M-4** — `alembic downgrade base` removes all objects created by the migration (`articles` table,
`article_fakes` table, `source_type` enum, all indexes) and exits 0.

### `source_type` Enum

**E-1** — After migration, the `source_type` enum exists in the `public` schema (visible in
`pg_type`).

**E-2** — The enum's labels are exactly `NYT`, `NPR`, `Guardian` — no others.

### `articles` Table

**A-1** — Table exists with the following columns and types (verified via `information_schema` or
`\d articles`):

- `id`: integer, primary key, not null, autoincrement
- `source`: `source_type` enum, not null
- `title`: text, not null
- `description`: text, nullable
- `url`: text, not null, unique
- `published_at`: timestamptz, nullable
- `created_at`: timestamptz, not null, default `now()`

**A-2** — Index `ix_articles_source` exists on column `source`.

**A-3** — Index `ix_articles_published_at` exists and is defined with `DESC NULLS LAST` ordering
on `published_at`.

**A-4** — Inserting two rows with identical `url` via `INSERT ... ON CONFLICT (url) DO NOTHING`:
the second insert raises no error and exactly one row exists in `articles`.

**A-5** — Inserting a row with a `source` value not in `source_type` (e.g. `'BBC'`) raises a
Postgres `DataError` or `InvalidTextRepresentation` error.

### `article_fakes` Table

**F-1** — Table exists with the following columns and types:

- `article_id`: integer, primary key, foreign key → `articles.id` ON DELETE CASCADE, not null
- `transform_status`: varchar(20), not null, default `'pending'`
- `title`: text, nullable
- `description`: text, nullable
- `model`: varchar(100), nullable
- `temperature`: double precision, nullable
- `created_at`: timestamptz, not null, default `now()`
- Check constraint `ck_article_fakes_transform_status` enforcing `transform_status IN ('pending',
  'completed')`

**F-2** — Inserting a second `article_fakes` row for the same `article_id` raises a Postgres
`UniqueViolation` (primary key constraint).

**F-3** — Inserting an `article_fakes` row with `transform_status = 'failed'` (or any value other
than `'pending'` or `'completed'`) raises a Postgres `CheckViolation` error.

**F-4** — Deleting an `articles` row that has an associated `article_fakes` row: the `article_fakes`
row is automatically deleted. A subsequent `SELECT` from `article_fakes` for that `article_id`
returns zero rows.

**F-5** — Inserting an `article_fakes` row with an `article_id` that does not exist in `articles`
raises a Postgres `ForeignKeyViolation` error.

### SQLAlchemy ORM Models

**O-1** — `Article` class in `backend/app/models.py` maps `__tablename__ = "articles"` with
columns `id: Mapped[int]`, `source: Mapped[Source]`, `title: Mapped[str]`,
`description: Mapped[str | None]`, `url: Mapped[str]`, `published_at: Mapped[datetime | None]`,
`created_at: Mapped[datetime]`.

**O-2** — `ArticleFake` class maps `__tablename__ = "article_fakes"` with columns
`article_id: Mapped[int]`, `transform_status: Mapped[str]`, `title: Mapped[str | None]`,
`description: Mapped[str | None]`, `model: Mapped[str | None]`, `temperature: Mapped[float | None]`,
`created_at: Mapped[datetime]`.

**O-3** — `Article.fake` is a relationship to `ArticleFake` with `uselist=False` (single-object
accessor, not a list). Accessing `article_instance.fake` on an article that has a fake row returns
an `ArticleFake` instance; on an article with no fake row returns `None`.

**O-4** — `ArticleFake.article` is a back-reference to its parent `Article`. Accessing
`fake_instance.article` returns the associated `Article` instance.

**O-5** — A `SELECT * FROM articles` equivalent executed via `AsyncSession.execute(select(Article))`
against a live database returns `Article` instances, not raw rows.

### Query Correctness

**Q-1** — The canonical feed query runs without error against a DB that contains at least one
article with `transform_status = 'completed'` and returns only those articles.

**Q-2** — An article whose `article_fakes` row has `transform_status = 'pending'` is **not**
returned by the canonical feed query.

**Q-3** — An article that has no `article_fakes` row at all is **not** returned by the canonical
feed query (INNER JOIN semantics exclude it).

---

## How to Test

All tests that interact with the database are **integration tests** against a running Postgres
container (started via `docker-compose up db` or the project's test Compose profile). Tests that
only inspect Python module state are **unit tests** requiring no database.

| Test | Method |
|---|---|
| S-1 | Unit — `import Source; assert list(Source) == [Source.NYT, Source.NPR, Source.GUARDIAN]` and assert values. |
| S-2 | Unit — assert `FEED_URLS[Source.NYT]`, `FEED_URLS[Source.NPR]`, `FEED_URLS[Source.GUARDIAN]` equal the spec URLs. |
| S-3 | Unit — assert `len(FEED_URLS) == 3`. |
| M-1 | Unit — `glob("backend/migrations/versions/*.py")` finds exactly one `.py` file (excluding `__init__.py`); its `down_revision` attribute is `None` (base migration); its filename or docstring contains `initial_schema`. Do **not** assert the specific hex revision ID. |
| M-2 | Integration — `alembic upgrade head` on a freshly created DB exits 0. Assert the three objects exist post-upgrade via `information_schema` queries. |
| M-3 | Integration — run `alembic upgrade head` again immediately after M-2. Assert exit code 0. |
| M-4 | Integration — `alembic downgrade base` after M-2. Assert `articles`, `article_fakes`, and `source_type` are gone via `information_schema`/`pg_type` queries. |
| E-1 | Integration — `SELECT typname FROM pg_type WHERE typname = 'source_type'` returns one row. |
| E-2 | Integration — `SELECT enumlabel FROM pg_enum JOIN pg_type ON pg_enum.enumtypid = pg_type.oid WHERE typname = 'source_type' ORDER BY enumsortorder` returns exactly `['NYT', 'NPR', 'Guardian']`. |
| A-1 | Integration — `SELECT column_name, data_type, is_nullable FROM information_schema.columns WHERE table_name = 'articles'` and `SELECT constraint_type FROM information_schema.table_constraints WHERE table_name = 'articles'`. Assert each column name, type, and nullable flag. |
| A-2 | Integration — `SELECT indexname FROM pg_indexes WHERE tablename = 'articles' AND indexname = 'ix_articles_source'` returns one row. |
| A-3 | Integration — `SELECT indexdef FROM pg_indexes WHERE indexname = 'ix_articles_published_at'` returns a row whose `indexdef` contains `DESC NULLS LAST`. |
| A-4 | Integration — Insert article row; repeat with same URL using `ON CONFLICT (url) DO NOTHING`; assert no exception; assert `COUNT(*) = 1`. |
| A-5 | Integration — Insert article row with `source = 'BBC'` via raw SQL; assert `DataError`/`InvalidTextRepresentation` is raised. |
| F-1 | Integration — `SELECT column_name, data_type, is_nullable FROM information_schema.columns WHERE table_name = 'article_fakes'` plus constraint queries. Assert each column. |
| F-2 | Integration — Insert one `article_fakes` row; attempt second insert for same `article_id`; assert `UniqueViolation`. |
| F-3 | Integration — Insert `article_fakes` with `transform_status = 'failed'`; assert `CheckViolation`. |
| F-4 | Integration — Insert article + fake; delete article via ORM or raw SQL; assert `SELECT COUNT(*) FROM article_fakes WHERE article_id = <id>` returns 0. |
| F-5 | Integration — Insert `article_fakes` row with `article_id = 99999` (non-existent); assert `ForeignKeyViolation`. |
| O-1 | API contract — import `Article` from `app.models`; inspect `Article.__table__.columns` and assert each column name, type, and nullable setting. |
| O-2 | API contract — import `ArticleFake` from `app.models`; inspect `ArticleFake.__table__.columns` similarly. |
| O-3 | Integration — Insert article + fake row; query via `AsyncSession`; assert `article.fake` is an `ArticleFake` instance. Insert article without fake; assert `article.fake is None`. |
| O-4 | Integration — Load `ArticleFake` via `AsyncSession`; assert `fake.article` is an `Article` instance with matching `id`. |
| O-5 | Integration — `await session.execute(select(Article))`; assert result scalars are `Article` instances. |
| Q-1 | Integration — Seed one article with `transform_status = 'completed'` and populated fake content. Run canonical query. Assert one row returned with `fake_title` and `fake_description` present. |
| Q-2 | Integration — Seed article with `transform_status = 'pending'`. Run canonical query. Assert that article's `id` is not in results. |
| Q-3 | Integration — Seed article with no `article_fakes` row. Run canonical query. Assert that article is not in results. |

---

## Test Data Setup

### Pure Python / API contract tests (S-1–S-3, O-1–O-2)

No database required. Import from `backend/app/sources.py` and `backend/app/models.py` directly.

### Migration tests (M-1–M-4, E-1–E-2)

- **M-1**: no DB needed; reads the migration file from disk.
- **M-2 to M-4**: requires a fresh Postgres database. The test fixture should create an empty
  database (separate from the app DB to avoid contamination), run Alembic against it, and drop it
  in teardown.
- Use `DATABASE_URL` pointing to the test DB (e.g. `postgresql+asyncpg://.../<test_db_name>`).

### Schema / constraint / ORM / query tests (A-1–A-5, F-1–F-5, O-3–O-5, Q-1–Q-3)

DB state before each test:

1. Fresh database with migrations applied (`alembic upgrade head`).
2. No rows in `articles` or `article_fakes` unless the test seeds them explicitly.
3. Each test must set up its own rows and clean up (or rely on transaction rollback).

**Seed rows for constraint tests (A-4, A-5, F-2, F-3, F-4, F-5)**:

```text
articles seed row (valid):
  source = 'NYT', title = 'Test Article', url = 'https://example.com/test-1',
  published_at = NULL, created_at = NOW()

article_fakes seed row (valid):
  article_id = <id from above>, transform_status = 'pending'
```

**Seed rows for query correctness tests (Q-1–Q-3)**:

```text
completed_article:
  source = 'NPR', title = 'Real Title', url = 'https://example.com/q-1'
  → article_fakes: transform_status = 'completed', title = 'Fake Title',
    description = 'Fake Desc', model = 'gpt-4o', temperature = 0.7

pending_article:
  source = 'NPR', title = 'Pending Title', url = 'https://example.com/q-2'
  → article_fakes: transform_status = 'pending', title = NULL, description = NULL

orphan_article (no fake):
  source = 'NPR', title = 'No Fake Title', url = 'https://example.com/q-3'
  → no article_fakes row
```

---

## Edge Cases to Cover

These are derived from the spec's acceptance criteria and "out of scope" list — not from reading
the implementation.

**EC-1** — `description` in `articles` can be `NULL`: inserting an article row without a
`description` must succeed (nullable column). Relevant to A-1.

**EC-2** — `published_at` in `articles` can be `NULL`: inserting without `published_at` must
succeed. The `ix_articles_published_at` index uses `NULLS LAST` — a NULL value should sort after
all non-null values. Relevant to A-3, Q-1.

**EC-3** — `article_fakes` row with `title = NULL`, `description = NULL`, `model = NULL`,
`temperature = NULL` and `transform_status = 'pending'` must be valid (all are nullable). Relevant
to F-1.

**EC-4** — Downgrade removes the `source_type` enum entirely — subsequent `alembic upgrade head`
must recreate it from scratch. Relevant to M-4, M-2 (run after downgrade).

**EC-5** — `FEED_URLS` keys must be `Source` enum members, not plain strings. Accessing
`FEED_URLS["NYT"]` (string key) should raise `KeyError`; `FEED_URLS[Source.NYT]` must work.
Relevant to S-2.

**EC-6** — `Source` values double as `source_type` enum labels in Postgres. `Source.GUARDIAN.value`
is `"Guardian"` (mixed case) — the DB enum label must match exactly. Relevant to E-2, A-5.

**EC-7** — The canonical feed query uses `INNER JOIN`, not `LEFT JOIN` — articles with no fake row
are structurally excluded, not filtered by a WHERE clause. This distinction matters if the JOIN
condition changes. Relevant to Q-3.

---

## Pass / Fail Criteria

QA passes for the `schema` task when all of the following are true:

1. **All 28 test cases pass** (S-1 through S-3, M-1 through M-4, E-1 through E-2, A-1 through A-5,
   F-1 through F-5, O-1 through O-5, Q-1 through Q-3) with no skips.

2. **All edge cases are exercised**: EC-1 through EC-7 are covered by at least one passing test
   case (most are covered within the primary cases above — they are not additional tests but
   boundary conditions to verify within those tests).

3. **No unexpected schema objects**: after `alembic upgrade head`, `information_schema` shows no
   tables other than `articles` and `article_fakes`, and no enum types other than `source_type`.

4. **Downgrade is clean**: after `alembic downgrade base`, none of the above objects exist in the
   database.

5. **No test leaks state**: each integration test leaves the database in the same state it found it
   (via transaction rollback or explicit cleanup).

QA fails if any test case fails, any test is skipped without documented justification, or the DB
state after upgrade does not match the spec's table/column/constraint definitions.

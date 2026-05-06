# Schema Spec

## Source

**File:** `docs/schema.md`

This spec covers the complete database schema layer: the `Source` Python enum, the
`source_type` Postgres enum, the `articles` table, the `article_fakes` table, and the
SQLAlchemy ORM models that map to them. It does **not** cover `chat_messages` (separate
task) or any API/worker logic that uses these tables.

Verbatim scope from `docs/schema.md`:

> Single source of truth for source identity. The Postgres `source_type` enum is derived
> from `Source` at migration time — labels are never hardcoded separately. Adding a source
> means one line here plus one `ALTER TYPE` migration.

---

## Goal

Implement the foundational persistence layer so that every other iteration task can assume
the correct tables, constraints, and ORM models exist. This layer enforces the core data
integrity invariants — URL-level article dedup, one fake per article by construction, and
the two-value transform status lifecycle — so that no application code needs to re-implement
them.

---

## User-Facing Behavior

- Running `docker-compose up` (or `alembic upgrade head` inside the container) leaves the
  database in a state where `articles`, `article_fakes`, and the `source_type` enum exist
  and are ready to receive data.
- A second scrape of the same article URL produces no duplicate row and no error; the
  article count is unchanged.
- When an article has been scraped but its transform job has not finished, a query for that
  article returns a row with `transform_status = 'pending'` and NULL fake content — the UI
  will render a "Processing…" placeholder.
- Deleting an article (e.g. via an admin operation) automatically removes its associated
  fake row; no orphaned `article_fakes` rows can exist.
- Attempting to insert a second fake for the same article is rejected by the database at the
  constraint level.

---

## Acceptance Criteria

### Sources module

- `backend/app/sources.py` defines a `Source` class that inherits from `StrEnum` with
  exactly three members: `NYT = "NYT"`, `NPR = "NPR"`, `GUARDIAN = "Guardian"`.
- `FEED_URLS` is a `dict[Source, str]` mapping each `Source` member to its RSS URL:
  - `Source.NYT` → `https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml`
  - `Source.NPR` → `https://feeds.npr.org/1001/rss.xml`
  - `Source.GUARDIAN` → `https://www.theguardian.com/world/rss`
- `FEED_URLS` has exactly three entries — no extras, no missing.

### Alembic migration

- A migration file exists under `backend/migrations/versions/` with revision id
  `0001_initial_schema` (or equivalent).
- Running `alembic upgrade head` against a fresh Postgres instance succeeds without error.
- Running `alembic upgrade head` a second time (already at head) is a no-op and exits
  successfully.
- Running `alembic downgrade base` removes all objects created by the migration (tables,
  enum, indexes) without error.

### `source_type` enum

- A Postgres enum named `source_type` exists in the database after migration.
- Its labels are exactly `NYT`, `NPR`, `Guardian` — no others.

### `articles` table

- Table exists with columns: `id SERIAL PRIMARY KEY`, `source source_type NOT NULL`,
  `title TEXT NOT NULL`, `description TEXT` (nullable), `url TEXT NOT NULL UNIQUE`,
  `published_at TIMESTAMPTZ` (nullable), `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`.
- An index `ix_articles_source` exists on `(source)`.
- An index `ix_articles_published_at` exists on `(published_at DESC NULLS LAST)`.
- Inserting two rows with the same `url` value: the second `INSERT ... ON CONFLICT (url)
  DO NOTHING` succeeds without raising an error, and the table contains exactly one row.
- Inserting a row with a `source` value not in `source_type` raises a Postgres error.

### `article_fakes` table

- Table exists with columns: `article_id INTEGER PRIMARY KEY REFERENCES articles(id) ON
  DELETE CASCADE`, `transform_status VARCHAR(20) NOT NULL DEFAULT 'pending'` with
  `CHECK (transform_status IN ('pending', 'completed'))`, `title TEXT` (nullable),
  `description TEXT` (nullable), `model VARCHAR(100)` (nullable), `temperature DOUBLE
  PRECISION` (nullable), `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`.
- `article_id` is simultaneously the primary key and the foreign key — verified by
  attempting to insert a second `article_fakes` row for the same `article_id`, which must
  be rejected.
- Inserting a `transform_status` value other than `'pending'` or `'completed'` raises a
  Postgres check-constraint error.
- Deleting an `articles` row cascades to delete its `article_fakes` row; querying
  `article_fakes` after deletion returns no row for that `article_id`.
- Inserting an `article_fakes` row with `article_id` referencing a non-existent `articles`
  row raises a foreign-key error.

### SQLAlchemy ORM models

- `backend/app/models.py` (or equivalent) defines an `Article` model mapping to `articles`
  with the correct column types and constraints.
- `backend/app/models.py` defines an `ArticleFake` model mapping to `article_fakes` with
  the correct column types and constraints.
- `Article` exposes a relationship to `ArticleFake` (e.g. `article.fake`).
- `ArticleFake` exposes a back-reference or back-populates to its `Article`.
- Querying `Article` objects via `AsyncSession` works against a live database — a
  `SELECT * FROM articles` equivalent via ORM returns `Article` instances.

### Query correctness

- The canonical feed query —
  `SELECT a.*, f.title AS fake_title, f.description AS fake_description FROM articles a INNER JOIN article_fakes f ON f.article_id = a.id WHERE f.transform_status = 'completed' ORDER BY a.published_at DESC NULLS LAST`
  — runs without error and returns only articles whose fake is fully processed.
- An article whose `article_fakes` row has `transform_status = 'pending'` is **not**
  returned by this query.
- An article with no `article_fakes` row at all is **not** returned by this query.

---

## Out of Scope

- `chat_messages` table — separate task.
- Any API endpoint or router that reads or writes these tables.
- The ARQ worker or scraping logic.
- Adding a `sources` DB table (the decision is Python StrEnum only, no DB table).
- Recovery/re-enqueue logic.
- Any `ALTER TYPE` migration for adding future sources.

---

## Assumptions (resolved)

1. **Migration auto-run at startup.** `alembic upgrade head` runs automatically as part of
   the application startup — either in the FastAPI lifespan or as a Docker Compose
   entrypoint step before the server starts. Dev chooses the mechanism; either is
   acceptable.

2. **Models file location.** `backend/app/models.py` (single file). Fine to split later.

3. **`published_at` nullable.** RSS feeds sometimes omit publish dates — nullable is
   correct.

4. **`description` nullable.** RSS feeds sometimes omit descriptions. The column is
   `TEXT` (nullable). The scraper passes `None` when the field is absent; the LLM
   transformation works from `title` alone in that case. Articles are never dropped
   solely because they lack a description.

5. **`sources.py` and `models.py` are created in this task.** Neither file exists yet;
   both are in scope for the implementation.

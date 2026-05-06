# Contracts

> **AGENTS: Read this before writing any code.** This document is the single source of truth for schema, API shapes, TypeScript types, and env vars. If your implementation diverges from anything here, update this document first and surface the discrepancy.
>
> **Who reads this:** All agents (Spec, Dev, QA). QA agents read this alongside the spec doc — never the dev doc.
>
> **Doc workflow:** This doc is produced in Session 0.A. Per-task docs live in `docs/iteration-{N}/`:
> `{task-id}-spec.md` → `{task-id}-dev.md` → `{task-id}-qa.md`. QA agents never read dev docs.

---

## DB Schema

Database: PostgreSQL 16 via `pgvector/pgvector:pg16` image. All migrations are hand-written Alembic — no autogenerate. Migrations live in `backend/migrations/versions/`.

### Sources (Python `StrEnum` is the single source of truth, no `sources` table)

Source identity is a Python `StrEnum` named `Source` in `backend/app/sources.py`. The Postgres enum type `source_type` is generated from that `StrEnum` by SQLAlchemy; the migration imports the same enum. There is no `sources` DB table. See ADR-16 for rationale.

**Config module (Python — single source of truth):**

```python
# backend/app/sources.py
from enum import StrEnum


class Source(StrEnum):
    NYT      = "NYT"
    NPR      = "NPR"
    GUARDIAN = "Guardian"


FEED_URLS: dict[Source, str] = {
    Source.NYT:      "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
    Source.NPR:      "https://feeds.npr.org/1001/rss.xml",
    Source.GUARDIAN: "https://www.theguardian.com/world/rss",
}
```

**Enum type (DB):** generated from `Source` — equivalent to:

```sql
CREATE TYPE source_type AS ENUM ('NYT', 'NPR', 'Guardian');
```

In the SQLAlchemy ORM:

```python
source: Mapped[Source] = mapped_column(
    sa.Enum(Source, name="source_type", values_callable=lambda e: [m.value for m in e])
)
```

In the Alembic migration:

```python
from app.sources import Source

source_type = postgresql.ENUM(*[s.value for s in Source], name="source_type", create_type=False)

def upgrade() -> None:
    source_type.create(op.get_bind())
    ...
```

- `articles.source` is of type `source_type` — the enum value IS the source identity. There is no integer `source_id` and no `source_name` denormalization.
- All sources are always active. Adding/removing a source = update `Source` enum + `FEED_URLS` + `ALTER TYPE` migration + restart.
- Drift between the Python enum and the Postgres enum is unrepresentable: there is only one Python definition; both the SQLAlchemy column and the migration derive the Postgres labels from it.

---

### `articles`

Stores only the original (scraped) article. Generated satirical content lives in `article_fakes` (see below) — see ADR-5.

```sql
CREATE TABLE articles (
    id            SERIAL PRIMARY KEY,
    source        source_type NOT NULL,       -- enum value; see "Sources" above and ADR-16
    title         TEXT NOT NULL,              -- original headline
    description   TEXT NOT NULL,              -- original summary
    url           TEXT NOT NULL UNIQUE,
    published_at  TIMESTAMPTZ,
    content_hash  CHAR(64) NOT NULL UNIQUE,   -- SHA256 hex of (title + description)
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_articles_source       ON articles(source);
CREATE INDEX ix_articles_published_at ON articles(published_at DESC NULLS LAST);
```

`content_hash` is used for deduplication: scraper computes SHA256 of `title + description` before insert and skips if already present. The `UNIQUE` constraint on `content_hash` already creates a unique B-tree index, which serves the dedup equality lookup — no additional non-unique index is needed.

**`articles` is `INSERT`-only after creation.** Originals are never UPDATEd; re-running a transformation only touches `article_fakes`. This is what guarantees the "originals never overwritten" property structurally.

---

### `article_fakes`

Stores the LLM-generated satirical version of an article. 1:1 with `articles`, enforced at the schema level by making `article_id` simultaneously the primary key and the foreign key (see ADR-5).

```sql
CREATE TABLE article_fakes (
    article_id        INTEGER PRIMARY KEY REFERENCES articles(id) ON DELETE CASCADE,
    fake_title        TEXT NOT NULL,
    fake_description  TEXT NOT NULL,
    model             VARCHAR(100) NOT NULL,         -- model used for this fake (e.g. "gpt-4o-mini")
    temperature       DOUBLE PRECISION NOT NULL,     -- temperature used for this fake
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

- `PRIMARY KEY = FOREIGN KEY` on `article_id` enforces 1:1 by construction. No unique index or CHECK needed.
- All columns are `NOT NULL` — a row exists if and only if a transformation succeeded.
- `ON DELETE CASCADE` cleans up the fake automatically when an article is deleted.
- The transformation worker `INSERT`s on first success and `UPDATE`s on regeneration (re-runs touch only this table). On failure, no row is inserted (ADR-15) — the API surfaces this as `null` fake-side fields, which the UI renders as "Processing…".
- No additional indexes — the PK on `article_id` doubles as the lookup index used by the article-list `LEFT JOIN`.

---

### `chat_messages`

```sql
-- MVP: no user_id — chat is shared per article across all users.
-- Migration path when auth is added:
--   1. ALTER TABLE chat_messages ADD COLUMN user_id INTEGER;
--   2. Backfill with NULL or a sentinel "legacy" user_id.
--   3. Add FK constraint after auth table exists.
--   4. Enforce NOT NULL in a subsequent migration once backfill is confirmed.
CREATE TABLE chat_messages (
    id          SERIAL PRIMARY KEY,
    article_id  INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    role        VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant')),
    content     TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_chat_messages_article_id ON chat_messages(article_id);
```

---

### `article_embeddings` (planned — not created until Iteration 3)

```sql
-- Requires: pgvector extension enabled via migration
-- CREATE EXTENSION IF NOT EXISTS vector;
--
-- CREATE TABLE article_embeddings (
--     id          SERIAL PRIMARY KEY,
--     article_id  INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE UNIQUE,
--     embedding   vector(1536) NOT NULL,      -- text-embedding-3-small dimensions
--     model       VARCHAR(100) NOT NULL,
--     created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
-- );
--
-- CREATE INDEX ix_article_embeddings_article_id ON article_embeddings(article_id);
-- CREATE INDEX ix_article_embeddings_embedding
--     ON article_embeddings USING ivfflat (embedding vector_cosine_ops)
--     WITH (lists = 100);
```

---

## REST API Contracts

Base URL (inside docker network): `http://backend:8000`
Base URL (host machine): `http://localhost:8000`
All JSON. All timestamps are ISO 8601 with timezone.

**Canonical routes:**

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/sources` | List sources (read from config module) |
| `GET` | `/api/articles` | List all articles (frontend filters by source client-side) |
| `GET` | `/api/articles/:id` | Single article (no separate versions array) |
| `POST` | `/api/scrape` | Trigger scrape of all configured sources |
| `GET` | `/api/articles/:id/messages` | Chat history for an article |
| `POST` | `/api/articles/:id/chat` | Stream assistant response via SSE |
| `GET` | `/health` | Health check (DB connectivity) |

---

### `GET /health`

Health check. Probes PostgreSQL on each call and returns its status. Used by Docker Compose `healthcheck`, the Vite frontend smoke check, and CI.

**Required dependencies** (failure → 503):

- PostgreSQL — needed for every read/write path.

Redis is the ARQ broker (ADR-9) — its availability is required for `POST /api/scrape` (which 503s if Redis is unreachable) but is **not** probed by `/health`. The read-path (article list / detail / chat history) does not depend on Redis, so degrading the health endpoint when Redis flaps would be a false positive.

**Response 200 — all required dependencies healthy:**

```json
{
  "status": "ok"
}
```

**Response 503 — one or more required dependencies unreachable:**

```json
{
  "status": "error"
}
```

- `status`: `"ok"` when all required dependencies are reachable; `"error"` otherwise.
- Per-dependency results are not exposed in the response body. Backend still probes each required dependency on every call; the overall status is the AND of those probes.

**State → HTTP mapping:**

| State | `status` | HTTP |
|---|---|---|
| All required deps healthy | `"ok"` | 200 |
| Any required dep unavailable | `"error"` | 503 |

---

### `POST /api/scrape`

Triggers a scrape of every source defined in the sources config module. Synchronous scrape + upsert; transformation jobs are enqueued and run asynchronously.

**Request:** No body required.

**Response 200:**

```json
{
  "enqueued": 12,
  "skipped_duplicates": 3,
  "sources_scraped": 3
}
```

- `enqueued`: new articles whose transformation job was enqueued.
- `skipped_duplicates`: articles skipped because `content_hash` already in DB.
- `sources_scraped`: number of sources successfully fetched (max = total count of sources in the config).

**Response 409 — scrape already in progress:**

```json
{ "detail": "A scrape is already running" }
```

Only one scrape may run at a time; concurrent calls receive 409 immediately and do not enqueue work or alter counts. The single-flight guard is a process-local asyncio lock — sufficient for the single-instance MVP. A multi-instance deployment would need a Redis-backed lock; deferred to `future_work.md`.

**Response 503:** Returned when Postgres or Redis is unavailable; the scrape is not attempted.

---

### `GET /api/sources`

Reads from the sources config module (see "Sources" above). Always returns the full configured list — there is no `enabled` filter and no integer `id`.

**Response 200:**

```json
{
  "sources": [
    { "name": "NYT", "feed_url": "https://..." }
  ]
}
```

`name` values are exactly the values of the `source_type` Postgres enum.

---

### `GET /api/articles`

Returns all articles. The MVP frontend loads the full list once and filters by source client-side (see [architecture.md](architecture.md) — Read Article Feed). Server-side filtering will be reintroduced when pagination lands.

**Response 200:**

```json
{
  "articles": [
    {
      "id": 1,
      "source": "NYT",
      "title": "Original title",
      "description": "Original description",
      "url": "https://...",
      "published_at": "2024-01-15T10:30:00Z",
      "content_hash": "a3f...",
      "created_at": "2024-01-15T10:30:00Z",
      "fake_title": "Satirical title",
      "fake_description": "Satirical description",
      "model": "gpt-4o-mini",
      "temperature": 0.9,
      "fake_created_at": "2024-01-15T10:30:05Z"
    }
  ]
}
```

- `created_at` is when the article was scraped (`articles.created_at`).
- `fake_title`, `fake_description`, `model`, `temperature`, `fake_created_at` are sourced from a `LEFT JOIN article_fakes` and are `null` when no `article_fakes` row exists (transform pending or permanently failed — see ADR-5 / ADR-15). They are non-null together: either all five (`fake_title`, `fake_description`, `model`, `temperature`, `fake_created_at`) are present, or all five are `null`.
- Pagination is deferred to future work; the endpoint returns all articles for the MVP.

---

### `GET /api/articles/:id`

Single article. Same flat shape as a list-item.

**Response 200:**

```json
{
  "id": 1,
  "source": "NYT",
  "title": "Original title",
  "description": "Original description",
  "url": "https://...",
  "published_at": "2024-01-15T10:30:00Z",
  "content_hash": "a3f...",
  "created_at": "2024-01-15T10:30:00Z",
  "fake_title": "Satirical title",
  "fake_description": "Satirical description",
  "model": "gpt-4o-mini",
  "temperature": 0.9,
  "fake_created_at": "2024-01-15T10:30:05Z"
}
```

**Response 404:**

```json
{ "detail": "Article not found" }
```

---

### `GET /api/articles/:id/messages`

Returns chat history for an article in chronological order.

**Response 200:**

```json
{
  "messages": [
    {
      "id": 1,
      "article_id": 1,
      "role": "user",
      "content": "What's the real story?",
      "created_at": "2024-01-15T10:35:00Z"
    },
    {
      "id": 2,
      "article_id": 1,
      "role": "assistant",
      "content": "The real story is...",
      "created_at": "2024-01-15T10:35:05Z"
    }
  ]
}
```

**Response 404:**

```json
{ "detail": "Article not found" }
```

---

### `POST /api/articles/:id/chat`

Streams assistant response via SSE.

**Request body:**

```json
{ "message": "What is the real story here?" }
```

**Response:** `Content-Type: text/event-stream`

SSE event stream format:

```text
data: {"token": "The"}

data: {"token": " real"}

data: {"token": " story..."}

data: [DONE]

```

On error mid-stream:

```text
data: {"error": "OpenAI rate limit exceeded"}

```

- User message is inserted to DB before streaming begins.
- Assistant message (full content) is inserted after stream completes.
- On error, partial content is not saved.
- Connection closes after `[DONE]` or error event.

**Response 404:** Article not found — returns JSON 404 before opening stream.

---

### `GET /api/admin/stats` (Iteration 2+)

Pipeline stats. Shape TBD in 2.7 spec.

---

## Error Response Shape

All non-2xx JSON responses use FastAPI's default envelope:

```json
{ "detail": "Human-readable message" }
```

The HTTP status code carries the error category — there is no separate `code` field and no `details` object.

Standard mappings:

- 404 — resource not found (e.g. unknown article id)
- 409 — conflict (e.g. scrape already in progress)
- 422 — request validation failed (FastAPI default for body / query / path validation)
- 503 — required dependency unavailable (DB on `/health`; DB or Redis on `POST /api/scrape`)
- 500 — unhandled exception

---

## TypeScript Types

These mirror the API response shapes exactly. Frontend treats them as canonical — do not add fields on the frontend side without updating this doc.

```typescript
interface HealthResponse {
  status: "ok" | "error";
}

// Mirrors the Postgres `source_type` enum (and the Python `Source` StrEnum) exactly.
type SourceName = "NYT" | "NPR" | "Guardian";

interface Source {
  name: SourceName;
  feed_url: string;
}

interface Article {
  id: number;
  source: SourceName;                 // matches Postgres source_type enum
  title: string;                      // original
  description: string;                // original
  url: string;
  published_at: string | null;        // ISO 8601
  content_hash: string;
  created_at: string;                 // scraped at — articles.created_at
  // The five fields below come from a LEFT JOIN on article_fakes (ADR-5).
  // Either all five are non-null (transform succeeded) or all five are null
  // (transform pending or permanently failed — UI renders "Processing…").
  fake_title: string | null;
  fake_description: string | null;
  model: string | null;
  temperature: number | null;
  fake_created_at: string | null;     // transformed at — article_fakes.created_at
}

interface ChatMessage {
  id: number;
  article_id: number;
  role: "user" | "assistant";
  content: string;
  created_at: string;
}

interface ScrapeResponse {
  enqueued: number;
  skipped_duplicates: number;
  sources_scraped: number;
}

interface ArticlesListResponse {
  articles: Article[];
}

interface SourcesListResponse {
  sources: Source[];
}

interface MessagesListResponse {
  messages: ChatMessage[];
}

// SSE event payloads (derived from each `data:` line).
// Parsing rule (consumers MUST follow this order):
//   1. If the raw `data:` value === "[DONE]", emit the "[DONE]" variant and stop. Do NOT JSON.parse.
//   2. Otherwise, JSON.parse the value and treat it as { token: string } | { error: string }.
type ChatSSEEvent =
  | { token: string }
  | { error: string }
  | "[DONE]";
```

---

## Environment Variables

Every variable here must appear in `.env.example` with a placeholder value and inline comment.

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://fakenews:fakenews@postgres:5432/fakenews` | Async SQLAlchemy connection string. Must use `asyncpg` driver. |
| `REDIS_URL` | `redis://redis:6379/0` | Redis connection string. Used by the ARQ broker only (ADR-9). |
| `OPENAI_API_KEY` | *(required)* | OpenAI API key. Never log this value. |
| `OPENAI_MODEL_TRANSFORM` | `gpt-4o-mini` | Model used by the transformation job. |
| `OPENAI_MODEL_CHAT` | `gpt-4o-mini` | Model used by the chat endpoint. |
| `OPENAI_TEMPERATURE_TRANSFORM` | `0.9` | Temperature for transformation (higher = more creative). |
| `OPENAI_TEMPERATURE_CHAT` | `0.7` | Temperature for chat responses. |
| `SCRAPE_MAX_PER_SOURCE` | `10` | Max number of feed entries the orchestrator persists per source per scrape. Entries beyond the cap are ignored (feed order). |
| `SCRAPE_INTERVAL_MINUTES` | `60` | ARQ cron interval for scheduled scraping (Iteration 3). `0` disables. |

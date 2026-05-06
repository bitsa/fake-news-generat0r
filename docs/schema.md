# DB Schema and Sources

## Sources (`backend/app/sources.py`)

```python
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

Single source of truth for source identity. The Postgres `source_type` enum is derived
from `Source` at migration time — labels are never hardcoded separately. Adding a source
means one line here plus one `ALTER TYPE` migration.

---

## `source_type` Postgres ENUM

```sql
CREATE TYPE source_type AS ENUM ('NYT', 'NPR', 'Guardian');
```

---

## `articles`

```sql
CREATE TABLE articles (
    id           SERIAL       PRIMARY KEY,
    source       source_type  NOT NULL,
    title        TEXT         NOT NULL,
    description  TEXT,
    url          TEXT         NOT NULL UNIQUE,
    published_at TIMESTAMPTZ,
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_articles_source       ON articles (source);
CREATE INDEX ix_articles_published_at ON articles (published_at DESC NULLS LAST);
```

Insert pattern: `INSERT ... ON CONFLICT (url) DO NOTHING` (DB-atomic dedup on URL).

---

## `article_fakes`

```sql
CREATE TABLE article_fakes (
    article_id       INTEGER           PRIMARY KEY
                                       REFERENCES articles(id) ON DELETE CASCADE,
    transform_status VARCHAR(20)       NOT NULL DEFAULT 'pending'
                                       CHECK (transform_status IN ('pending', 'completed')),
    title            TEXT,
    description      TEXT,
    model            VARCHAR(100),
    temperature      DOUBLE PRECISION,
    created_at       TIMESTAMPTZ       NOT NULL DEFAULT NOW()
);
```

`article_id` is simultaneously PK and FK — one fake per article, enforced by construction.
`title`, `description`, `model`, and `temperature` are NULL while `transform_status = 'pending'`
and filled atomically when the worker sets `transform_status = 'completed'`.

---

## Transform Lifecycle

```text
POST /api/scrape
  → INSERT INTO articles ... ON CONFLICT (url) DO NOTHING
  → if inserted: INSERT INTO article_fakes (article_id, transform_status='pending')
  → enqueue ARQ job

ARQ worker
  → call LLM
  → on success: UPDATE article_fakes
                SET title=..., description=..., model=..., temperature=...,
                    transform_status='completed'
                WHERE article_id=...
  → on failure: DELETE FROM article_fakes WHERE article_id=...  -- log error, revert to no-fake

Recovery (startup or periodic)
  → re-enqueue WHERE transform_status = 'pending'
    AND created_at < NOW() - interval '5 min'
```

The DB is the source of truth. The ARQ queue is a fast-path delivery mechanism, not the
record of intent.

---

## Query Pattern

These two tables are always queried together. The UI only receives fully processed
article+fake tuples — no partial objects.

```sql
SELECT
    a.*,
    f.title            AS fake_title,
    f.description      AS fake_description
FROM articles a
INNER JOIN article_fakes f ON f.article_id = a.id
WHERE f.transform_status = 'completed'
ORDER BY a.published_at DESC NULLS LAST;
```

Only rows where `transform_status = 'completed'` reach the UI. Articles still pending or
whose transform failed (and whose `article_fakes` row was deleted) are invisible until
processing succeeds.

# Chat History Endpoint Spec

## Source

**File:** `/Users/bitsa/.claude/plans/we-gotta-work-on-fuzzy-parasol.md` (task draft authored by
user). Title: *Chat — GET history endpoint (BE only)*. Key quotes:

> This task is the **GET-only first slice**: a read endpoint that returns the message history for
> a given article, plus the `chat_messages` table and ORM model required to back it. No POST, no
> SSE, no LLM call yet — those land in the next task and reuse the schema this slice ships.
>
> The locked design is **POST a message → server opens an SSE stream → tokens flow → `[DONE]` →
> connection closes**, with **one row per chat message** persisted to the DB and conversations
> reconstructed by ordering on `created_at`.

This spec covers the read endpoint and the `chat_messages` schema only. The POST + SSE streaming
endpoint, prompt construction, and frontend integration are explicitly the next task and reuse the
schema delivered here.

---

## Goal

Stand up the persistence and read layer for per-article chat. Ship the `chat_messages` table
(plus ORM model and Alembic migration) and `GET /api/articles/{article_id}/chat`, which returns
the article's full message history as ordered JSON. Two columns (`is_error`, `request_id`) are
created and surfaced in the response now even though no write path uses them yet — they exist so
the next task (POST + SSE) can populate them without a follow-up migration. This unblocks frontend
work on history rendering and forward-compatibly seats the schema the streaming task will fill in.

---

## User-Facing Behavior

- A caller hitting `GET /api/articles/{article_id}/chat` for an existing article receives `200 OK`
  with a JSON object containing `article_id` and `messages` (an array of message objects ordered
  oldest-first).
- Each message object exposes `id`, `role` (`"user"` or `"assistant"`), `content`, `is_error`
  (bool), `request_id` (string or `null`), and `created_at`.
- A caller hitting the endpoint for an article that has no messages yet receives `200 OK` with
  `messages: []` — empty history is a normal state, not an error.
- A caller hitting the endpoint for a non-existent `article_id` receives `404` with
  `{"detail": "Article {id} not found"}`.
- When the parent article is deleted, all of its chat messages are removed with it (cascade).
- Messages are returned in chronological order; messages sharing the same `created_at` are
  tie-broken by ascending `id` so order is stable across calls.
- The endpoint is unauthenticated and lives under the `/api` prefix, consistent with
  `/api/articles` and `/api/scrape`.

---

## Acceptance Criteria

1. **Migration applies cleanly.** Running `alembic upgrade head` against a DB at
   `cfe2a836394a` (initial schema) creates the `chat_messages` table and succeeds without errors.
   The new revision's `down_revision` is `cfe2a836394a`.

2. **Migration is reversible.** Running `alembic downgrade -1` from the new revision drops the
   `chat_messages` table and its index without errors and leaves the rest of the schema intact.

3. **`chat_messages` table shape.** Post-migration, the `chat_messages` table exists with these
   columns and types:
   - `id` — integer, primary key, autoincrement, NOT NULL
   - `article_id` — integer, NOT NULL, foreign key to `articles.id` with `ON DELETE CASCADE`
   - `role` — varchar(20), NOT NULL
   - `content` — text, NOT NULL
   - `is_error` — boolean, NOT NULL, server default `false`
   - `request_id` — varchar(64), nullable, no unique constraint
   - `created_at` — timestamp with time zone, NOT NULL, server default `now()`

4. **Role check constraint.** A check constraint named `ck_chat_messages_role` rejects any
   `role` value other than `'user'` or `'assistant'`. Inserting `role='system'` (or any other
   string) raises an integrity error; inserting `role='user'` or `role='assistant'` succeeds.

5. **Composite index for history query.** An index named
   `ix_chat_messages_article_id_created_at` exists on `(article_id, created_at)`.

6. **Server defaults populate on insert.** Inserting a row that omits `is_error` and `created_at`
   succeeds; the resulting row has `is_error = false` and a non-null `created_at` set by the
   server.

7. **`request_id` accepts NULL.** Inserting a row with `request_id` omitted (or explicitly NULL)
   succeeds and reads back as `null`.

8. **Cascade delete.** Deleting an `articles` row with associated `chat_messages` rows removes
   all of those `chat_messages` rows in the same operation. No orphaned rows remain.

9. **Endpoint registered under `/api`.** The full URL path is
   `/api/articles/{article_id}/chat`. The endpoint accepts `GET` and is included in the FastAPI
   app's OpenAPI schema.

10. **Happy path returns ordered history.** With an existing article and two messages — one
    `user` then one `assistant`, inserted in that order — `GET /api/articles/{id}/chat` returns
    `200 OK` with `article_id` set to the requested id and `messages` containing both rows in
    insertion order (user first, assistant second).

11. **Empty history for existing article.** With an existing article and zero messages,
    `GET /api/articles/{id}/chat` returns `200 OK` with `article_id` set and `messages: []`.

12. **404 for missing article.** With no `articles` row matching the id (e.g. `999999`),
    `GET /api/articles/999999/chat` returns `404` with body `{"detail": "Article 999999 not
    found"}`. No partial response, no 500. The 404 is produced by raising the existing
    `NotFoundError` from `backend/app/exceptions.py` (no new exception subclass introduced).

13. **Stable tie-break on identical `created_at`.** With two messages whose `created_at` values
    are equal, the response orders them by ascending `id`. The order is identical across
    repeated calls.

14. **Response shape — top level.** The response body has exactly two keys: `article_id`
    (integer) and `messages` (array). No extra fields.

15. **Response shape — each message.** Each element of `messages` has exactly these keys:
    `id` (integer), `role` (`"user"` or `"assistant"`), `content` (string), `is_error` (boolean),
    `request_id` (string or `null`), `created_at` (ISO 8601 timestamp with timezone).

16. **`is_error` exposed and defaults false.** A message inserted without explicitly setting
    `is_error` is returned with `"is_error": false` in the response.

17. **`request_id` exposed and may be null.** A message inserted without `request_id` is
    returned with `"request_id": null` in the response.

18. **`created_at` ISO 8601 with timezone.** The `created_at` field on each message serialises as
    an ISO 8601 string with a timezone offset (`Z` suffix or `+00:00`).

19. **No auth required.** The endpoint responds to unauthenticated requests with `200` or `404`
    as above — never `401` or `403`.

20. **POST not implemented.** `POST /api/articles/{article_id}/chat` is *not* registered in this
    task. A POST request to that path returns `405 Method Not Allowed` (FastAPI's default for an
    unmapped method on a registered path).

---

## Out of Scope

- `POST /api/articles/{article_id}/chat` — message creation endpoint (next task).
- SSE streaming, token events, `[DONE]` termination — next task.
- LLM call, prompt construction, model selection — next task.
- Any write-path logic for `is_error` or `request_id` — columns exist but nothing populates them
  in this task.
- Unique constraint on `request_id` — explicitly omitted; the dedup story is the next task's
  problem.
- Pagination, cursor navigation, or limit/offset — full history is returned in one response.
- Filtering messages by role, date range, or content — not required.
- Frontend integration — separate task.
- Authentication, rate limiting, per-user history — chat is shared per article in MVP
  (`context.md` decision: *Shared Chat, No Auth in MVP*).
- Deletion or editing of individual chat messages.
- Migration data backfill — the table starts empty.

---

## Open Questions / Assumptions

1. **404 raised via existing `NotFoundError`.** The task description suggested introducing a new
   `ArticleNotFound(AppError)` subclass. Resolved: reuse the existing `NotFoundError` from
   `backend/app/exceptions.py` (already `status_code=404`) rather than adding a new subclass. The
   contract that QA verifies is the 404 status and `"Article {id} not found"` detail body.

2. **`messages.id` uniqueness across articles.** The PK is a single autoincrementing `id` column,
   so message ids are globally unique across articles (not per-article). This matches the task
   description and the existing `articles.id` style. No assumption to verify — calling it out so
   QA does not write a test that assumes per-article id sequences.

3. **`created_at` precision and clock source.** `server_default=now()` uses the database clock at
   timestamp microsecond precision. Tie-break behavior (criterion 13) is therefore only
   exercisable in tests by inserting two rows with an explicit identical `created_at` value, since
   two server-generated `now()` calls in sequence will almost never collide. Flagged so the QA
   agent constructs the tie-break test by writing `created_at` explicitly rather than relying on
   `time.sleep(0)` race conditions.

4. **Article id type.** Path param `{article_id}` is typed as `int` in the router (consistent
   with `articles.id`). Non-integer path values (`/api/articles/abc/chat`) yield FastAPI's
   default `422` validation response. Not called out in acceptance criteria; flagged here so it
   isn't mistaken for missing behavior.

5. **`messages` ordering on tie-break — direction.** The spec mandates ascending `id` as the
   tie-breaker. This is the natural choice (insertion order ≈ id order) but is worth confirming
   is what the next task's POST writer will rely on, since the streamed UI will append messages
   visually in this order.

6. **No structured logging for empty results.** The service emits one `log.info` line summarising
   the message count, including for the empty-history case. Not called out in acceptance criteria
   because logs are not part of the contract; flagged so reviewers don't expect a `log.warning`
   on empty history.

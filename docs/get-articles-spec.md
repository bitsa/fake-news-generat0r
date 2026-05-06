# GET /api/articles Spec

## Source

**File:** `/Users/bitsa/.claude/plans/let-s-plan-how-the-replicated-scone.md` (task draft authored
by user). Key quotes:

> Return only articles that have a **completed** fake — drop articles with no fake row or a
> `pending` fake.
>
> Return each result as a nested pair `{ id, article: {...}, fake: {...} }` — the shared `id`
> sits at the top level since `article_id` in `article_fakes` is the same value.
>
> This deviates from the `contracts.md` LEFT JOIN plan (which would include articles without
> fakes). The new semantics are effectively an INNER JOIN filtered to
> `transform_status = 'completed'`.

This spec covers the read endpoint for the article feed. Frontend polling semantics, response shape,
and the INNER JOIN filtering decision are all defined here. Scraping, LLM transformation, and
frontend implementation are separate tasks.

---

## Goal

Expose `GET /api/articles` so the frontend can surface completed article+fake pairs to the user.
The endpoint returns only articles whose fake transform has completed, along with two counters —
`total` (all articles in the DB) and `pending` (fakes still in flight) — that drive the frontend's
polling decision. When `pending` reaches zero, the frontend stops polling; when a transform fails
and its `article_fakes` row is deleted, that article disappears from the pending count without ever
appearing in the response body.

---

## User-Facing Behavior

- A caller hitting `GET /api/articles` receives a JSON object with three fields: `total`,
  `pending`, and `articles`.
- `articles` contains only completed pairs — articles whose `article_fakes` row exists and has
  `transform_status = 'completed'`. Articles mid-transform (`pending`) and articles with no fake
  row at all do not appear.
- `total` is the count of all rows in `articles` regardless of fake status or absence.
- `pending` is the count of `article_fakes` rows with `transform_status = 'pending'`. As long as
  this number is above zero, the frontend knows transforms are in flight and keeps polling.
- When the worker fails a transform it deletes the `article_fakes` row; that article drops out of
  `pending` without ever surfacing in `articles`. The frontend observes `pending` decrease without
  a corresponding increase in `articles`.
- Results in `articles` are ordered by `published_at DESC NULLS LAST` — newest articles first,
  articles with no publish date at the end.
- Each element in `articles` has a top-level `id` (the shared PK/FK value), an `article` object
  with the original content, and a `fake` object with the satirical content.

---

## Acceptance Criteria

1. **Happy path — completed pairs returned.** With one article and one `completed` fake in the DB,
   `GET /api/articles` returns `200 OK` with `total: 1`, `pending: 0`, and one element in
   `articles`.

2. **Pending fakes excluded.** An article whose `article_fakes` row has `transform_status =
   'pending'` does not appear in `articles`. It is counted in `pending`.

3. **No-fake articles excluded.** An article with no corresponding `article_fakes` row does not
   appear in `articles` and does not contribute to `pending`.

4. **`total` counts all articles.** With three articles in the DB — one completed fake, one pending
   fake, one with no fake — `total` is `3`.

5. **`pending` counts only pending fakes.** With two articles, one with `transform_status =
   'pending'` and one with `transform_status = 'completed'`, `pending` is `1`.

6. **Empty DB.** With no rows in either table, the response is
   `{"total": 0, "pending": 0, "articles": []}` with `200 OK`.

7. **Ordering.** With two completed pairs, the article with the later `published_at` appears first.
   An article where `published_at` is `NULL` appears after articles with a date.

8. **Response shape — top level.** The response body is a JSON object with exactly three keys:
   `total` (integer), `pending` (integer), `articles` (array).

9. **Response shape — each pair.** Each element of `articles` has:
   - `id`: integer — equals both `article.id` and `fake.id`
   - `article`: object with `id`, `source`, `title`, `description`, `url`, `published_at`,
     `created_at`
   - `fake`: object with `id`, `title`, `description`, `model`, `temperature`, `created_at`

10. **Nullable fields.** `article.description` and `article.published_at` may be `null`. `fake.title`,
    `fake.description`, `fake.model`, and `fake.temperature` may be `null` (schema allows it).
    `fake.created_at` is always present (NOT NULL in DB).

11. **`source` field serialisation.** `article.source` is the string value of the `Source` StrEnum
    (e.g. `"NYT"`, `"NPR"`, `"Guardian"`), not an enum index.

12. **Datetime serialisation.** All `datetime` fields (`published_at`, `created_at`) are serialised
    as ISO 8601 strings with timezone (`Z` suffix or `+00:00`).

13. **No auth required.** The endpoint responds to unauthenticated requests with `200 OK` (no `401`
    or `403`).

14. **Registered under `/api` prefix.** The full URL path is `/api/articles`, consistent with
    `/api/scrape`. (Health lives at `/health` — no `/api` prefix by convention.)

---

## Out of Scope

- Pagination or cursor-based navigation — all completed pairs returned in one response.
- Filtering by source, date range, or keyword — Iteration 2.
- POST, PUT, DELETE on articles — articles are insert-only (originals never overwritten).
- Frontend implementation — separate task.
- LLM transformation and ARQ worker — separate task.
- Chat integration — separate task.
- Rate limiting or request authentication — out of scope for MVP.

---

## Assumptions (resolved)

1. **`get_session` naming.** `backend/app/db.py` exports `get_session()`, not `get_db`. The router
   uses `get_session` as-is — the name is more precise and no rename is warranted.

2. **Nullable fields on `completed` fakes.** The schema allows `title`, `description`, `model`, and
   `temperature` to be `NULL` even at `transform_status = 'completed'`. No DB-level tightening —
   the worker sets all four fields before flipping status, and that invariant is enforced in worker
   unit tests rather than schema complexity. The endpoint surfaces completed fakes as-is.

3. **No response envelope versioning.** Any breaking change to the response shape is a new spec
   revision, not a versioned path.

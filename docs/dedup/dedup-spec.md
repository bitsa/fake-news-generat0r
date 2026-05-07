# Dedup — Hybrid Title-Jaccard → Embedding Near-Duplicate Detection

## Source

Scope and intent for this task come from the plan file
[`/Users/bitsa/.claude/plans/let-s-plan-this-breezy-owl.md`](../../../.claude/plans/let-s-plan-this-breezy-owl.md)
("Hybrid Near-Duplicate Detection (Title-Jaccard → Embedding Fallback)").
The bonus item is also called out in the assignment under "Bonus":
*"Article similarity detection (avoid scraping near-duplicates from
different sources)."*
([plans/assignment.md:78](../../plans/assignment.md#L78))

Verbatim core scope from the plan:

> For each parsed candidate, after URL-uniqueness filtering and before the
> batched `articles` insert, classify against incumbents from the last
> **7 days** comparison window:
>
> ```text
> max_jaccard >= 0.80   → skip as duplicate, reason='jaccard'
> 0.40 <= max_j < 0.80  → escalate: cosine-compare against incumbents whose jaccard >= 0.40
>                           if any cosine >= 0.88 → skip as duplicate, reason='embedding'
>                           else                  → insert + persist candidate embedding
> max_jaccard < 0.40    → insert, do NOT embed
> ```

Comparison window: `COALESCE(published_at, created_at) > now() - interval '7 days'`.

## Goal

Stop ingesting near-duplicate stories that slip past URL-uniqueness — same
wire piece republished under different URLs across sources. Today the
scrape pipeline only deduplicates on exact URL via the
`ON CONFLICT (url)` clause in [`backend/app/services/scraper.py`](../../backend/app/services/scraper.py),
so cross-source reposts pay the full cost downstream: a row in `articles`,
a row in `article_fakes`, an ARQ job, and an OpenAI transform call. A
hybrid pipeline — cheap title-Jaccard first, embedding cosine only for an
ambiguous middle band — eliminates that waste while keeping embedding
spend sparse. The dollar win is the avoided transform call, not the
embedding fee.

## User-facing behavior

- **Operator (`POST /api/scrape`):** the response now reports four
  outcome counters instead of two — how many records were actually
  written (`inserted`, unchanged key), how many candidates were dropped
  because their URL already existed (`skipped_url_duplicates`), how many
  were dropped because a near-duplicate already existed in the recent
  window (`skipped_near_duplicates`), and how many embedding API calls
  the run triggered (`embedding_calls`). On a steady-state scrape against
  a mostly-stable feed the operator sees high skip counts and a low —
  often zero — embedding-call count.
- **Frontend:** the article feed contains no near-duplicate items —
  multiple articles from different sources reporting the same wire story
  collapse to a single entry (the first one ingested wins; later
  near-duplicates are silently dropped at scrape time and never appear in
  `/api/articles`).
- **Logs:** each near-duplicate skip emits one `info`-level log line
  carrying the skip `reason` (`jaccard` or `embedding`) and the
  `matched_article_id` of the incumbent that triggered the skip. URL
  skips continue to log as before.
- **Database:** the `article_embeddings` table is sparsely populated. Most
  rows in `articles` will not have a sibling row in `article_embeddings`;
  only candidates that fell into the ambiguous band and were *not* skipped
  carry an embedding. The pgvector extension is enabled.

## Acceptance criteria

A QA agent must be able to verify each of the following without reading
the implementation. All assertions assume `openai_mock_mode=true` unless
explicitly stated otherwise.

### URL-dedup remains the first gate

- A candidate whose `url` already exists in `articles` is dropped before
  any near-duplicate check runs. It does not contribute to
  `skipped_near_duplicates` and does not trigger any embedding call.
- The response counter `skipped_url_duplicates` reports the number of
  candidates dropped at this gate.

### Title-Jaccard high-band skip (cheap path)

- A candidate whose title shares a Jaccard score `>= dedup_jaccard_high`
  (default `0.80`) with at least one incumbent in the comparison window is
  skipped: no row in `articles`, no row in `article_fakes`, no ARQ
  transform job enqueued, no row in `article_embeddings` for the
  candidate.
- The skip increments `skipped_near_duplicates` in the response and
  produces an `info` log line carrying `reason=jaccard` and a
  `matched_article_id`.
- The skip does **not** trigger any embedding API call.

### Low-band insert with no embedding (cost-win path)

- A candidate whose maximum Jaccard score against every in-window
  incumbent is `< dedup_jaccard_floor` (default `0.40`) is inserted
  normally and an ARQ transform job is enqueued.
- The candidate produces no row in `article_embeddings`.
- The candidate does not trigger any embedding API call.

### Ambiguous-band escalation with embedding-cosine skip

- A candidate whose max Jaccard falls in
  `[dedup_jaccard_floor, dedup_jaccard_high)` triggers a cosine-similarity
  check against every in-window incumbent whose Jaccard with the candidate
  is also `>= dedup_jaccard_floor`.
- If any such incumbent's cosine similarity with the candidate is
  `>= dedup_cosine_threshold` (default `0.88`), the candidate is skipped:
  no row in `articles`, no row in `article_fakes`, no ARQ transform job,
  no embedding row persisted for the candidate.
- The skip increments `skipped_near_duplicates` and logs `reason=embedding`
  with a `matched_article_id`.

### Ambiguous-band escalation with no match → insert + embed

- A candidate in the ambiguous band that finds no incumbent at
  `cosine >= dedup_cosine_threshold` is inserted, an ARQ transform job is
  enqueued, and its embedding is persisted into `article_embeddings`
  (one row, `article_id` matching the new article's `id`, `embedding`
  length 1536, `model` matching `settings.openai_model_embedding`).

### Comparison window

- The set of incumbents considered for any candidate is exactly the rows
  in `articles` for which
  `COALESCE(published_at, created_at) > now() - interval '<dedup_window_hours> hours'`
  evaluates true at the time of the scrape.
- An article older than the window is **not** an incumbent: a candidate
  that would be a near-duplicate of an out-of-window article is inserted
  normally (subject to URL-dedup).
- Articles whose `published_at` is `NULL` are eligible incumbents when
  their `created_at` falls inside the window.

### Within-batch coherence

- If two near-duplicate candidates appear inside the **same**
  `POST /api/scrape` run (e.g. two sources publishing the same wire story
  in the same scrape cycle), exactly one of them is inserted; the other
  is dropped as a near-duplicate against the just-accepted one.
- Exactly one article is accepted; which one wins is implementation-walk-order
  and must not be asserted by QA.
- The dropped candidate increments `skipped_near_duplicates`.

### Cross-source matching

- Near-duplicate detection compares against incumbents from **all**
  sources, not just the candidate's own source. A NYT candidate can be
  skipped because of an NPR incumbent and vice versa.

### Tokenizer (Jaccard input)

- The tokenizer applied to titles produces tokens that are: lowercased,
  punctuation-stripped, whitespace-split, with stopwords removed and any
  token of length `<= 2` removed.
- The stopword set is **frozen and exhaustive** — exactly these 11
  words, no more, no less:

  ```text
  the a an of to for and or in on at is
  ```

- Extending the stopword list is a spec change, not a dev-doc choice.
- Only the title is tokenized for Jaccard; the description is not used
  in the cheap-path comparison.

### `POST /api/scrape` response shape

- The 202 response body is a JSON object with exactly these keys, all
  integers:

  ```json
  {
    "inserted": <int>,
    "fetched": <int>,
    "skipped_url_duplicates": <int>,
    "skipped_near_duplicates": <int>,
    "embedding_calls": <int>
  }
  ```

- The existing `inserted` and `fetched` keys are preserved with their
  current meaning (`inserted` = rows actually written to `articles`).
  Three new counters are added alongside. The frontend type in
  [`frontend/src/api/articles.ts`](../../frontend/src/api/articles.ts)
  stays valid; extending it is optional and not required for this task.
- `embedding_calls` counts embedding API invocations during the run
  (one per text embedded, including any incumbent embeddings computed
  on demand). It is `0` when no candidate landed in the ambiguous band.

### `article_embeddings` schema

- A new table `article_embeddings` exists with the following observable
  shape:
  - `article_id INTEGER PRIMARY KEY`, foreign-keyed to `articles(id)`
    with `ON DELETE CASCADE`.
  - `embedding vector(1536) NOT NULL` (pgvector type).
  - `model varchar(64) NOT NULL`.
  - `created_at timestamptz NOT NULL DEFAULT now()`.
- Deleting a row from `articles` cascades to delete the matching
  `article_embeddings` row.
- The pgvector extension (`vector`) is installed in the database.
- No vector index is required for v1.

### Mock mode (deterministic embeddings)

- When `openai_mock_mode=true`, the embedding service must not
  instantiate the OpenAI client or make any network call. It returns a
  1536-dimension `list[float]` derived deterministically from the input
  text (e.g. via `hashlib`-based hashing) such that:
  - Calling the mock twice with the **same** input returns an
    **identical** vector.
  - Calling the mock with two **different** inputs returns vectors whose
    cosine similarity is strictly `< 1.0` (i.e. distinguishable).
  - The returned vector has length 1536.
- The mock diverges intentionally from the constant-output pattern in
  [`backend/app/services/openai_transform.py`](../../backend/app/services/openai_transform.py):
  a constant embedding mock would make every cosine pair `1.0`, which
  would render the dedup logic untestable in integration / smoke and
  always-skip-with-`reason=embedding` at runtime under
  `openai_mock_mode=true`. Hash-determinism is the minimum viable mock
  for the feature to be observable in mock mode.
- All tests run with `openai_mock_mode=true`. No test makes a real
  OpenAI request.
- The mock toggle reuses the existing `openai_mock_mode` setting; no new
  flag is introduced.

### Test-coverage policy

- **No unit tests are required for this task.** Coverage is integration
  only: a `POST /api/scrape` flow exercised against a real Postgres + the
  mock embedding/transform path, asserting the response counters and the
  `articles` / `article_embeddings` rows that result. The pure helpers
  (tokenizer, Jaccard, cosine, `find_near_duplicate`) are deliberately
  not unit-tested in v1; the integration path covers them transitively.
- This is a deliberate scope cut to fit the time budget. Adding unit
  tests later is non-breaking.

### Tunable settings

- All four threshold/window knobs are exposed as fields on `Settings`
  with the following defaults and constraints, overridable via env:
  - `dedup_window_hours`: default `168`, must be `> 0`.
  - `dedup_jaccard_high`: default `0.80`, must satisfy `0 < x <= 1`.
  - `dedup_jaccard_floor`: default `0.40`, must satisfy `0 <= x <= 1`.
  - `dedup_cosine_threshold`: default `0.88`, must satisfy `0 < x <= 1`.
- An additional setting `openai_model_embedding` exists (default
  `text-embedding-3-small`) and is the value persisted in the `model`
  column of `article_embeddings`.
- Changing any of these settings via env at startup time changes the
  observed dedup behavior on the next scrape with no code change.

### Idempotency / boundary behavior

- A candidate whose Jaccard against every in-window incumbent is exactly
  `dedup_jaccard_high` is skipped (high band is inclusive of the
  threshold).
- A candidate whose Jaccard against every in-window incumbent is exactly
  `dedup_jaccard_floor` is escalated to embedding cosine, not inserted as
  low-band (floor band is inclusive of the threshold).
- Cosine equal to `dedup_cosine_threshold` counts as a match (skip).

### Non-regression (URL pipeline)

- A scrape run with no near-duplicates and no URL collisions still
  returns `inserted == fetched` (modulo entries dropped at parse time)
  and inserts every article with its corresponding `pending`
  `article_fakes` row, exactly as before this task.
- `make` targets / linters still pass: `ruff` and `black` clean on new
  code per [context.md](../../context.md), and `make docs-fix && make
  docs-lint` clean for new `.md` files per the project `CLAUDE.md`.

## Out of scope

- A `scrape_skips` audit table. Counters in the response are sufficient
  for v1; persistent skip history is recorded as future work.
- A vector index (ivfflat / HNSW) on `article_embeddings`. The pre-filter
  via Jaccard keeps the cosine pass over a handful of rows; an ANN index
  is premature.
- Backfilling embeddings for articles that pre-date this task. No batch
  job to embed historical rows. The `article_embeddings` table starts
  empty and grows only via the new path.
- Re-running dedup against historical data, or any UI to surface near-dup
  matches.
- A tunable mock-embedding flavor or per-test override. The hash-based
  mock is the single mock path.
- Tightening or loosening the threshold defaults beyond what the dev
  doc may justify with a tuning notebook (the notebook itself is not in
  scope and not in-repo).
- Description-level (or full-body) similarity, multilingual handling, or
  stemming/lemmatization in the tokenizer.
- Concurrency hardening across simultaneous `POST /api/scrape` calls.
  Single-process per scrape is the assumption; the worst case
  (one extra embed) is acceptable.
- Updating the frontend feed UI itself; the only frontend touch is the
  scrape-response type in [`frontend/src/api/articles.ts`](../../frontend/src/api/articles.ts)
  if the dev doc decides to keep it in sync.

## Resolved decisions (signed off before implementation)

The seven open questions surfaced in drafting were resolved as follows.
Recorded here so dev/QA agents pick up the calls without re-asking.

1. **Response shape — keep `inserted`.** The existing key is preserved
   with its original meaning (rows written to `articles`). Three new
   counters are added alongside. No FE type churn. See the response-shape
   acceptance criterion above.
2. **Threshold defaults locked.** `0.40 / 0.80 / 0.88` and a 168-hour
   window are the v1 defaults. No tuning pass before merge.
3. **First-collision double-cost accepted.** First ambiguous-band hit may
   produce `embedding_calls = 2` (candidate + cold incumbent). This is
   the contract, not a bug.
4. **Hash-deterministic embedding mock required.** Diverges from the
   constant pattern in `openai_transform.py` because mock-mode dedup must
   be observable end-to-end. See "Mock mode" criterion above.
5. **Within-batch winner is implementation-walk-order.** Exactly one of
   two mutual near-dups in the same run wins; which one is unspecified.
   QA must not assert which.
6. **Stopword list frozen at 11 words.** No "dev may extend". Extension
   is a spec change. See the tokenizer criterion above.
7. **Source filter — none.** Dedup compares across the entire in-window
   set regardless of source.

## Suggested QA acceptance-criterion order (highest-risk first)

1. Mock embeddings are hash-deterministic and length 1536 — every other
   test depends on this property.
2. URL-dedup still runs first and is unaffected by the new path.
3. Comparison-window predicate (out-of-window incumbent does *not* trigger
   a skip).
4. High-band Jaccard skip with no embedding call.
5. Low-band insert with no embedding call and no embedding row.
6. Ambiguous-band escalation: skip path (cosine >= threshold).
7. Ambiguous-band escalation: insert + embed path (cosine < threshold).
8. Within-batch coherence (two same-run candidates dedup against each
   other).
9. Cross-source matching (NYT incumbent skips an NPR candidate).
10. Response shape, including `embedding_calls` counter.
11. `article_embeddings` schema and CASCADE behavior.
12. Boundary inclusivity at the three thresholds.
13. Tokenizer behavior (stopwords, ≤2-char drop, punctuation strip,
    title-only).

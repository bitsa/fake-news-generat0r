# Dedup — Dev Plan

## MUST READ FIRST

- [docs/dedup/dedup-spec.md](dedup-spec.md) — source of truth for WHAT and the resolved decisions.
- [context.md](../../context.md) — async-only Python, `X | None` typing, `black`/`ruff`,
  Pydantic Settings, stdlib logging rules, ARQ-broker-only Redis, hand-written Alembic
  migrations, pgvector image already in use.
- [plans/plan.md](../../plans/plan.md) — spec/dev/qa workflow.

Source files examined to derive contracts:

- [backend/app/services/scraper.py](../../backend/app/services/scraper.py) — current
  `ingest_all` shape, `IngestResult`, per-source commit, `ON CONFLICT (url)` behavior.
- [backend/app/services/transformer.py](../../backend/app/services/transformer.py) —
  `create_and_enqueue` adds `ArticleFake(pending)` rows + enqueues ARQ jobs after
  `ingest_all` returns; this contract is preserved (we do not add fakes inside ingest).
- [backend/app/routers/scrape.py](../../backend/app/routers/scrape.py) — current
  202 response is `{inserted, fetched}`; we extend with three counters.
- [backend/app/models.py](../../backend/app/models.py) — `Article`, `ArticleFake` shape.
- [backend/app/config.py](../../backend/app/config.py) — `Settings` with
  `openai_mock_mode`, `openai_request_timeout_seconds`, etc. New knobs land here.
- [backend/app/services/openai_transform.py](../../backend/app/services/openai_transform.py)
  — pattern for `openai_mock_mode` short-circuit and lazy `AsyncOpenAI` import. The
  embedding service follows the same shape but with hash-deterministic mock (per spec).
- [backend/app/services/sanitize.py](../../backend/app/services/sanitize.py) —
  punctuation/whitespace utilities exist but are HTML-oriented; tokenizer here is its own
  helper.
- [backend/migrations/versions/cfe2a836394a_initial_schema.py](../../backend/migrations/versions/cfe2a836394a_initial_schema.py),
  [backend/migrations/versions/3602d7a39bfe_chat_messages.py](../../backend/migrations/versions/3602d7a39bfe_chat_messages.py)
  — migration style and `down_revision` chain. New head: dedup migration.
- [backend/app/main.py](../../backend/app/main.py) — `lifespan` calls `scraper.scrape_cycle`
  on startup; the new dedup path runs through this code path unchanged.
- [backend/app/workers/transform.py](../../backend/app/workers/transform.py) — the
  ARQ cron `scheduled_scrape` also runs through `scraper.scrape_cycle`. Same code path.
- [frontend/src/api/articles.ts](../../../frontend/src/api/articles.ts) — `ScrapeResponse`
  type. Per spec, extending is optional; we will extend it for type safety.
- [backend/pyproject.toml](../../backend/pyproject.toml) — needs `pgvector` dependency.

## Files to touch / create

### Create

- `backend/migrations/versions/<rev>_dedup_pgvector_and_embeddings.py` — Alembic migration:
  - `CREATE EXTENSION IF NOT EXISTS vector`.
  - `CREATE TABLE article_embeddings (article_id INTEGER PRIMARY KEY REFERENCES articles(id) ON DELETE CASCADE, embedding vector(1536) NOT NULL, model varchar(64) NOT NULL, created_at timestamptz NOT NULL DEFAULT now())`.
  - `down_revision = "3602d7a39bfe"`.
- `backend/app/services/embedding.py` — `embed_text` (real path + hash-deterministic mock).
- `backend/app/services/dedup.py` — tokenizer, `_jaccard`, `_cosine`, `find_near_duplicate`.
- `backend/tests/unit/test_embedding.py`,
  `backend/tests/unit/test_dedup_tokenize.py`,
  `backend/tests/unit/test_dedup_jaccard.py`,
  `backend/tests/unit/test_dedup_cosine.py`,
  `backend/tests/unit/test_dedup_classifier.py`,
  `backend/tests/unit/test_dedup_scraper_integration.py` — new unit-test files (DB,
  feedparser, and OpenAI all mocked; same patterns as
  [`backend/tests/routers/test_scrape.py`](../../backend/tests/routers/test_scrape.py)
  and [`backend/tests/unit/test_scraper.py`](../../backend/tests/unit/test_scraper.py)).

### Modify

- `backend/app/models.py` — add `ArticleEmbedding` ORM class.
- `backend/app/config.py` — add five new `Settings` fields with constraints and defaults.
- `backend/app/services/scraper.py` — extend `IngestResult`; integrate dedup into
  `ingest_all`; per-candidate flow (URL-dedup → near-dup check → insert + optional
  embedding row).
- `backend/app/routers/scrape.py` — return the four-counter shape.
- `backend/pyproject.toml` — add `pgvector>=0.3` dependency.
- `backend/tests/unit/test_config.py` — add the five tunable-settings test cases.
- `backend/tests/unit/test_models.py` — add the `article_embeddings` shape tests.
- `backend/tests/unit/test_migration_module.py` — add the dedup-migration tests.
- `backend/tests/routers/test_scrape.py` — extend the response-shape assertions to
  the new five-key body (existing happy-path + 503 + zero-inserted tests still pass
  with the extra keys).
- `frontend/src/api/articles.ts` — extend `ScrapeResponse` with the three new integer
  fields (FE-side typing only; no UI change).

### Not touched

- `transformer.create_and_enqueue` — unchanged. It still receives the inserted-articles
  list and creates `ArticleFake(pending)` rows + enqueues. Skipped candidates never
  reach it because they are not in the `inserted` list.
- ARQ worker — unchanged.
- Frontend feed UI — unchanged (per spec out-of-scope).

## Interfaces / contracts to expose

### Settings (added fields)

```python
dedup_window_hours: int = Field(default=168, gt=0)
dedup_jaccard_high: float = Field(default=0.80, gt=0.0, le=1.0)
dedup_jaccard_floor: float = Field(default=0.40, ge=0.0, le=1.0)
dedup_cosine_threshold: float = Field(default=0.88, gt=0.0, le=1.0)
openai_model_embedding: str = "text-embedding-3-small"
```

### Model (`backend/app/models.py`)

```python
class ArticleEmbedding(Base):
    __tablename__ = "article_embeddings"
    article_id: Mapped[int] = mapped_column(
        sa.Integer,
        sa.ForeignKey("articles.id", ondelete="CASCADE"),
        primary_key=True,
    )
    embedding: Mapped[list[float]] = mapped_column(Vector(1536), nullable=False)
    model: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
```

`Vector` is imported from `pgvector.sqlalchemy`.

### Embedding service (`backend/app/services/embedding.py`)

```python
async def embed_text(text: str) -> list[float]:
    """Return a 1536-dim embedding. Hash-deterministic in mock mode."""
```

Mock-mode contract (per spec acceptance criterion "Mock mode (deterministic embeddings)"):

- Pure-Python, no OpenAI client instantiation, no network call.
- Derives a 1536-element `list[float]` from `hashlib.sha256(text.encode())` by
  expanding the digest deterministically (e.g. PRNG seeded by digest, or repeated
  SHA chain) into 1536 floats in `[-1, 1]`.
- Same input → identical vector. Different inputs → cosine `< 1.0`.

Real-mode contract:

- Instantiates `AsyncOpenAI(api_key=settings.openai_api_key,
  timeout=settings.openai_request_timeout_seconds)` lazily (mirrors
  `openai_transform.py`).
- Calls `client.embeddings.create(model=settings.openai_model_embedding, input=text)`,
  returns `response.data[0].embedding`.

### Dedup service (`backend/app/services/dedup.py`)

```python
STOPWORDS: frozenset[str] = frozenset(
    {"the", "a", "an", "of", "to", "for", "and", "or", "in", "on", "at", "is"}
)
# Spec: frozen 12-word set, exhaustive.

def tokenize(title: str) -> set[str]: ...
def _jaccard(a: set[str], b: set[str]) -> float: ...
def _cosine(a: list[float], b: list[float]) -> float: ...

@dataclass
class Incumbent:
    article_id: int
    tokens: set[str]
    embedding: list[float] | None  # None until cold-computed

@dataclass
class DedupDecision:
    accept: bool
    reason: str | None              # 'jaccard' | 'embedding' | None
    matched_article_id: int | None
    candidate_embedding: list[float] | None  # set iff insert+embed path
    embedding_calls: int            # calls made for THIS decision

async def find_near_duplicate(
    session: AsyncSession,
    candidate_title: str,
    candidate_text: str,            # title + "\n\n" + description, used for embedding
    incumbents: list[Incumbent],
) -> DedupDecision: ...
```

`find_near_duplicate` mutates the per-incumbent `embedding` field when it cold-computes
one (so the same `incumbents` list reuses it across subsequent candidates in the same
run), and persists each cold-computed incumbent embedding via
`session.add(ArticleEmbedding(...))`. The session commit happens in the caller
(`ingest_all`), bundled with the candidate's own writes when accepted, or as a
standalone commit when the decision is "skip" (cold incumbent persistence is still
worth keeping).

### Scraper (`backend/app/services/scraper.py`)

```python
@dataclass
class IngestResult:
    inserted: list[Article]
    fetched: int
    skipped_url_duplicates: int
    skipped_near_duplicates: int
    embedding_calls: int

async def ingest_all(session: AsyncSession) -> IngestResult: ...
```

### Scrape router (`backend/app/routers/scrape.py`)

```python
@router.post("/scrape", status_code=202)
async def scrape(...) -> dict:
    return {
        "inserted": len(result.inserted),
        "fetched": result.fetched,
        "skipped_url_duplicates": result.skipped_url_duplicates,
        "skipped_near_duplicates": result.skipped_near_duplicates,
        "embedding_calls": result.embedding_calls,
    }
```

### Frontend (`frontend/src/api/articles.ts`)

```ts
export interface ScrapeResponse {
  inserted: number;
  fetched: number;
  skipped_url_duplicates: number;
  skipped_near_duplicates: number;
  embedding_calls: number;
}
```

## Implementation plan

### 1. Dependency + migration

1. Add `pgvector>=0.3` to `backend/pyproject.toml` `dependencies`. Lockfile (`uv.lock`)
   regenerated by `uv lock` during the dev branch build.
2. Generate migration revision with `alembic revision -m "dedup pgvector and embeddings"`.
   Hand-edit:
   - `op.execute("CREATE EXTENSION IF NOT EXISTS vector")`.
   - `op.create_table("article_embeddings", ...)` mirroring the schema in the spec.
   - `down_revision = "3602d7a39bfe"`.
   - `downgrade()` drops the table; do **not** drop the `vector` extension (other
     installs may rely on it).
3. Verify `await _run_migrations()` in `app.main.lifespan` runs the new migration
   on startup (no code change needed; migrations chain by `down_revision`).

### 2. Settings

In `backend/app/config.py`, add the five fields listed under "Interfaces / contracts".
Pydantic `Field` enforces the constraints (`gt`, `ge`, `le`) — invalid env values fail
fast at startup, per `context.md` "All config via Pydantic Settings".

### 3. Model

In `backend/app/models.py`, add `ArticleEmbedding`. Use `from pgvector.sqlalchemy import
Vector`. No relationship back-pointer is required (the spec's observable contract is the
`article_id` PK + cascade; ORM relationship is not part of the contract and not needed
by callers).

### 4. Embedding service

Create `backend/app/services/embedding.py`:

1. Mock branch (`if settings.openai_mock_mode:`):
   - `digest = hashlib.sha256(text.encode("utf-8")).digest()` (32 bytes).
   - Expand to 1536 floats: chain SHA-256 over the digest 48 times (each round yields
     32 bytes; 48 × 32 = 1536 bytes), interpret each byte as `(b - 127.5) / 127.5`
     to land in roughly `[-1, 1]`. Same-input → identical bytes → identical vector.
     Different-input → different starting digest → near-zero collision probability →
     cosine `< 1.0` w.h.p. (collisions are SHA-256-attack territory, not test concerns).
   - Return `list[float]`. No OpenAI import on this path (per spec).
2. Real branch: lazy import of `AsyncOpenAI`, single `embeddings.create` call. Errors
   bubble — caller decides cleanup. Logs one `info` line on success, one `error` line
   on failure (per `context.md` logging rules).

### 5. Dedup service

Create `backend/app/services/dedup.py`:

1. `tokenize(title)`:
   - `title.lower()`, strip via regex `[^\w\s]` → spaces (or `unicodedata`-aware
     equivalent — match the existing `sanitize.clean_text` style with `re`).
   - Split on whitespace.
   - Drop tokens with `len(t) <= 2` and tokens in `STOPWORDS`.
   - Return `set[str]`.
2. `_jaccard(a, b)`: `len(a & b) / len(a | b)` if union non-empty else `0.0`.
3. `_cosine(a, b)`: pure-Python dot / (|a| × |b|), guarding zero norms → `0.0`.
4. `find_near_duplicate`:
   - Compute candidate tokens.
   - Compute `j_max` and collect `escalation = [inc for inc in incumbents if
     j(candidate, inc) >= floor]`.
   - If `j_max >= dedup_jaccard_high` → return `accept=False, reason='jaccard',
     matched_article_id=<argmax incumbent>, embedding_calls=0`.
   - Else if `j_max < dedup_jaccard_floor` → return `accept=True, reason=None,
     matched_article_id=None, candidate_embedding=None, embedding_calls=0`.
   - Else (ambiguous band — `floor <= j_max < high`):
     - `cand_emb = await embed_text(candidate_text)`. Increment local
       `embedding_calls`.
     - For each `inc in escalation`:
       - If `inc.embedding is None`: `inc.embedding = await embed_text(<inc title +
         "\n\n" + description>)`; increment counter; `session.add(ArticleEmbedding(
         article_id=inc.article_id, embedding=inc.embedding,
         model=settings.openai_model_embedding))`. (See "Open clarification 1" below
         for why this persistence step is part of the contract.)
       - Compute cosine. If `>= dedup_cosine_threshold` → return `accept=False,
         reason='embedding', matched_article_id=inc.article_id,
         candidate_embedding=None, embedding_calls=<count>`.
     - No match → return `accept=True, reason=None, matched_article_id=None,
       candidate_embedding=cand_emb, embedding_calls=<count>`.

   Note: incumbents need their original `title` and `description` available to embed;
   load them at incumbent-load time.

### 6. Scraper integration

Rewrite `ingest_all` per-candidate (replacing the per-source bulk insert):

1. At start, `incumbents` is loaded once from DB:

   ```sql
   SELECT a.id, a.title, a.description, ae.embedding
     FROM articles a
     LEFT JOIN article_embeddings ae ON ae.article_id = a.id
    WHERE COALESCE(a.published_at, a.created_at) > now() - (:hours || ' hours')::interval
   ```

   Each row → `Incumbent(article_id, tokens=tokenize(title), embedding=<vec or None>)`.
   Keep `inc_text[a.id] = title + "\n\n" + description` in a sidecar dict for cold
   embed.
2. `existing_urls` is **not** preloaded (would not scale). Instead, per candidate:
   `await session.scalar(select(Article.id).where(Article.url == cand.url))`.
3. Per source:
   - Fetch + parse as today.
   - For each parsed candidate:
     - URL check: if exists → `skipped_url_duplicates += 1`; `continue`. No log
       beyond debug (per spec, URL skips "continue to log as before").
     - `decision = await find_near_duplicate(session, cand.title, cand.title +
       "\n\n" + cand.description, incumbents)`. Add `decision.embedding_calls` to the
       run-level counter.
     - If `not decision.accept`:
       - `skipped_near_duplicates += 1`.
       - `log.info("scraper.dedup.skip reason=%s candidate_url=%s
         matched_article_id=%d", decision.reason, cand.url,
         decision.matched_article_id)` (per spec: one info line, carries `reason` and
         `matched_article_id`).
       - `await session.commit()` (persists any incumbent embeddings cold-computed
         during the decision).
       - `continue`.
     - Accept path:
       - `session.add(cand); await session.flush()` (gets `cand.id`).
       - If `decision.candidate_embedding is not None`:
         `session.add(ArticleEmbedding(article_id=cand.id,
         embedding=decision.candidate_embedding,
         model=settings.openai_model_embedding))`.
       - `await session.commit()`.
       - Append to `inserted_articles` list.
       - Append `Incumbent(article_id=cand.id, tokens=tokenize(cand.title),
         embedding=decision.candidate_embedding)` to `incumbents` (in-memory),
         and `inc_text[cand.id] = cand.title + "\n\n" + cand.description`.
         This is the within-batch coherence mechanism.
4. Per-source error handling: existing `try / except / rollback / continue` envelope
   wraps each source. The all-failed → `ServiceUnavailableError` invariant is
   preserved.
5. Return the new `IngestResult`.

`scrape_cycle` is untouched: it still passes the inserted-articles list into
`transformer.create_and_enqueue`, which adds the `ArticleFake(pending)` rows for
accepted articles only. Skipped candidates are not in the list, so no fake row is
created for them. ✓

### 7. Router

Update `backend/app/routers/scrape.py` to assemble the four-counter response from the
new `IngestResult`. Existing `inserted` and `fetched` keys keep their meaning.

### 8. Frontend type

Extend `ScrapeResponse` in `frontend/src/api/articles.ts`. No consumer in the FE
currently reads the new fields; this is type-only.

### 9. Lint + format

Run `ruff check` and `black` on touched backend files. Run
`make docs-fix && make docs-lint` after writing this dev doc and the migration
docstring.

## Unit tests required

Per spec "Test-coverage policy": unit tests yes, integration tests no. Each test
function name below maps unambiguously to one acceptance criterion (or one boundary
case of one criterion) so QA can audit coverage by name without reading bodies. All
tests run with `openai_mock_mode=true`. DB layer is mocked (per existing patterns in
[`tests/routers/test_scrape.py`](../../backend/tests/routers/test_scrape.py)
and [`tests/unit/test_scraper.py`](../../backend/tests/unit/test_scraper.py));
no real Postgres / Redis / OpenAI in any new test.

### `tests/unit/test_embedding.py` — embedding service / mock contract

Covers AC "Mock mode (deterministic embeddings)".

- `test_embed_text_mock_does_not_import_openai_client` — patches `openai.AsyncOpenAI`
  to raise on instantiation; with `openai_mock_mode=true` the call still succeeds.
- `test_embed_text_mock_returns_length_1536`.
- `test_embed_text_mock_same_input_returns_identical_vector`.
- `test_embed_text_mock_different_inputs_have_cosine_strictly_less_than_one`.
- `test_embed_text_real_path_calls_openai_with_configured_model` — patches
  `AsyncOpenAI`; asserts `embeddings.create(model=settings.openai_model_embedding,
  input=...)` was called.

### `tests/unit/test_dedup_tokenize.py` — tokenizer

Covers AC "Tokenizer (Jaccard input)".

- `test_tokenize_lowercases_input`.
- `test_tokenize_strips_punctuation`.
- `test_tokenize_splits_on_whitespace`.
- `test_tokenize_drops_tokens_of_length_two_or_less`.
- `test_tokenize_drops_each_of_the_twelve_stopwords` — parametrized over the frozen
  list `the a an of to for and or in on at is`.
- `test_tokenize_stopword_set_size_is_exactly_twelve` — pins the frozen set so a
  drift-by-one fails loudly.
- `test_tokenize_does_not_consume_description` — implicit via the `tokenize` signature
  taking only a title; documented as the "title-only" coverage note.

### `tests/unit/test_dedup_jaccard.py` — pure jaccard

- `test_jaccard_returns_zero_for_disjoint_sets`.
- `test_jaccard_returns_one_for_identical_sets`.
- `test_jaccard_returns_zero_when_both_sets_empty` (no division-by-zero).

### `tests/unit/test_dedup_cosine.py` — pure cosine

- `test_cosine_returns_one_for_identical_vectors`.
- `test_cosine_returns_zero_for_orthogonal_vectors`.
- `test_cosine_returns_zero_when_either_vector_is_zero_norm`.

### `tests/unit/test_dedup_classifier.py` — `find_near_duplicate` decision tree

Covers ACs: high-band skip, low-band insert, ambiguous-band escalation (skip + insert),
boundary inclusivity, embedding-call counting, no-embedding-call on cheap paths.

- `test_high_band_jaccard_skip_returns_reason_jaccard_no_embedding_call`.
- `test_high_band_skip_carries_matched_article_id_of_argmax_incumbent`.
- `test_low_band_insert_returns_accept_no_embedding_no_call`.
- `test_ambiguous_band_with_cosine_match_returns_reason_embedding`.
- `test_ambiguous_band_no_match_returns_accept_with_candidate_embedding_persisted`.
- `test_ambiguous_band_only_escalates_against_incumbents_with_jaccard_above_floor`.
- `test_jaccard_equal_to_high_threshold_is_skip` — boundary inclusivity at 0.80.
- `test_jaccard_equal_to_floor_threshold_escalates_to_cosine` — boundary inclusivity
  at 0.40.
- `test_cosine_equal_to_threshold_is_skip` — boundary inclusivity at 0.88.
- `test_cold_incumbent_embedding_is_computed_and_persisted_on_first_use` — call
  counter increments by 2 (candidate + cold incumbent); a `session.add` is called
  with an `ArticleEmbedding` carrying the incumbent's `article_id`.
- `test_warm_incumbent_embedding_is_reused_no_extra_call` — second candidate against
  the same incumbent in the same run pays only its own +1 embed.

### `tests/unit/test_dedup_scraper_integration.py` — `ingest_all` orchestration

Covers ACs: URL-dedup-runs-first, comparison-window predicate, within-batch coherence,
cross-source matching, response counters, non-regression on the URL pipeline,
embedding row persisted only on insert+embed path, no `article_fakes` for skipped
candidates.

DB and feed-fetcher are mocked in the same style as the existing scraper unit tests.
The in-window incumbent loader is patched to return a hand-rolled list. Naming maps
1:1 to the spec ACs:

- `test_url_duplicate_is_dropped_before_dedup_no_embedding_call`.
- `test_response_url_duplicates_counter_matches_url_skipped_count`.
- `test_high_band_candidate_is_skipped_with_no_articles_no_fakes_no_embedding_row`.
- `test_high_band_skip_logs_info_with_reason_jaccard_and_matched_article_id` —
  asserts a single `info` log line with both fields (uses `caplog`).
- `test_low_band_candidate_is_inserted_no_embedding_call_no_embedding_row`.
- `test_ambiguous_band_skip_logs_info_with_reason_embedding_and_matched_article_id`.
- `test_ambiguous_band_no_match_inserts_article_and_persists_embedding_row` —
  asserts the embedding row carries `article_id == new article's id`,
  `model == settings.openai_model_embedding`, length-1536 vector.
- `test_within_batch_two_near_duplicates_in_same_run_drop_one_increment_skip_counter`.
- `test_within_batch_winner_identity_not_asserted` — documents (via comment) that
  which of the two wins is implementation-walk-order; asserts only "exactly one
  inserted, one skipped".
- `test_cross_source_incumbent_skips_candidate_from_different_source`.
- `test_out_of_window_incumbent_does_not_trigger_skip` — incumbent older than
  `dedup_window_hours` is filtered by the loader; candidate is inserted.
- `test_incumbent_with_null_published_at_is_in_window_when_created_at_is_recent`.
- `test_response_shape_has_exactly_five_integer_keys`.
- `test_response_embedding_calls_is_zero_when_no_ambiguous_band_candidate`.
- `test_response_embedding_calls_counts_each_call_including_cold_incumbent`.
- `test_non_regression_no_collisions_inserts_every_article_with_pending_fake_row`.

### `tests/unit/test_config.py` — settings constraints

Covers AC "Tunable settings".

- `test_dedup_window_hours_default_is_168_and_must_be_positive`.
- `test_dedup_jaccard_high_default_is_080_and_within_zero_one`.
- `test_dedup_jaccard_floor_default_is_040_and_within_zero_one`.
- `test_dedup_cosine_threshold_default_is_088_and_within_zero_one`.
- `test_openai_model_embedding_default_is_text_embedding_3_small`.

### `tests/unit/test_models.py` — schema observable shape

Covers AC "`article_embeddings` schema".

- `test_article_embeddings_table_has_article_id_pk_and_cascade_fk_to_articles`.
- `test_article_embeddings_columns_match_spec` — `embedding` is `Vector(1536)`
  not-null; `model` is `varchar(64)` not-null; `created_at` has timezone + server
  default.

### Migration test

- `tests/unit/test_migration_module.py` already exercises migration importability;
  add `test_dedup_migration_chains_from_chat_messages_revision` and
  `test_dedup_migration_creates_vector_extension_and_article_embeddings_table` (uses
  the existing migration-test helpers; no real DB connection).

## Definition of done

Derived from the spec acceptance criteria:

- [ ] Migration creates `article_embeddings` and `vector` extension; `down_revision`
      chains from `3602d7a39bfe`.
- [ ] `ArticleEmbedding` ORM class added; pgvector dep present in `pyproject.toml`.
- [ ] Five new `Settings` fields with the spec defaults and constraints; env override
      changes runtime behavior.
- [ ] `embed_text` mock branch is hash-deterministic, length 1536, no OpenAI import.
- [ ] `embed_text` real branch uses `settings.openai_model_embedding`.
- [ ] Tokenizer matches spec (lowercase, punctuation strip, whitespace split, stopwords
      removed, `len <= 2` dropped, **frozen 12-word stopword set**).
- [ ] `find_near_duplicate` implements the three-band classifier with inclusive
      thresholds at `0.40`, `0.80`, and `0.88`.
- [ ] `ingest_all` URL-dedups per candidate before near-dup check.
- [ ] Within-batch coherence: in-memory `incumbents` list grows as candidates accept.
- [ ] Cross-source matching: incumbents are not filtered by source.
- [ ] Comparison window applies to incumbents (`COALESCE(published_at, created_at)`),
      driven by `dedup_window_hours`.
- [ ] Skipped candidates produce no `articles`, `article_fakes`, or `article_embeddings`
      row, and no ARQ job.
- [ ] Ambiguous-band insert path persists exactly one `article_embeddings` row for the
      new article with `model=settings.openai_model_embedding`, length 1536.
- [ ] One `info` log line per near-dup skip, carrying `reason` and `matched_article_id`.
- [ ] `POST /api/scrape` 202 body has exactly `{inserted, fetched,
      skipped_url_duplicates, skipped_near_duplicates, embedding_calls}`, all integers;
      `embedding_calls == 0` when no candidate landed in the ambiguous band.
- [ ] Scrape with no near-dups and no URL collisions still inserts every article with
      its `pending` `article_fakes` row (non-regression).
- [ ] All new unit-test files pass; pre-existing test suites still pass unchanged.
- [ ] `ruff` + `black` clean on backend; `eslint` + `tsc --noEmit` clean on frontend.
- [ ] `make docs-fix && make docs-lint` clean for new `.md` files.
- [ ] Tracker updated to `in_dev`.

## Open clarifications surfaced (non-blocking)

These are dev-judgement calls made because the spec leaves them implicit. Both follow
the spec's letter and spirit; neither requires a spec edit.

1. **Cold-incumbent embeddings are persisted on first compute.** The spec's
   "user-facing behavior" line says only ambiguous-band-not-skipped *candidates* get
   an `article_embeddings` row, but the resolved decision "first ambiguous-band hit
   may produce `embedding_calls = 2` (candidate + cold incumbent). This is the
   contract, not a bug." only makes sense as a one-time cost if the cold incumbent's
   embedding is then persisted (otherwise *every* ambiguous hit pays double, not
   just the first). This dev doc treats persistence-on-cold-compute as the intended
   reading. Net effect: a pre-existing article can grow an `article_embeddings`
   sibling row when it first serves as a cosine-comparison incumbent. The "most
   articles will not have an embedding" line in the spec remains true in steady
   state (the ambiguous band is rare).
2. **Embedding input is `title + "\n\n" + description`.** The spec specifies
   title-only for Jaccard but does not pin down the embedding input. Title-only
   would lose the cross-source-wire-piece signal that motivates the bonus. Both
   candidate and incumbent are embedded the same way for symmetry.

## Spec fix-ups absorbed

The spec previously said "exactly these 11 words" while listing 12. Fixed in
`dedup-spec.md` (and the matching "Resolved decisions" line) to read 12. Implementation
uses the full 12-word list as written:

```text
the a an of to for and or in on at is
```

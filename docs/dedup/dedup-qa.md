# Dedup — QA Coverage Audit

Black-box audit of unit-test coverage against
[dedup-spec.md](dedup-spec.md). Maps each spec acceptance criterion to
the test(s) the dev wrote. The QA doc never reads the dev doc or
implementation logic.

## Coverage map

The spec's acceptance-criteria block uses subsection headings, not a
flat numbered list. For traceability the headings are numbered here in
spec order.

### 1. URL-dedup remains the first gate

- `[1.1]` URL-existing candidate dropped before near-dup check; no
  contribution to `skipped_near_duplicates`; no embedding call.
  - [test_dedup_scraper_integration.py:test_url_duplicate_is_dropped_before_dedup_no_embedding_call](../../backend/tests/unit/test_dedup_scraper_integration.py)
- `[1.2]` `skipped_url_duplicates` counts URL-gate drops.
  - [test_dedup_scraper_integration.py:test_response_url_duplicates_counter_matches_url_skipped_count](../../backend/tests/unit/test_dedup_scraper_integration.py)
  - [test_dedup_scraper_integration.py:test_url_duplicate_is_dropped_before_dedup_no_embedding_call](../../backend/tests/unit/test_dedup_scraper_integration.py)

### 2. Title-Jaccard high-band skip (cheap path)

- `[2.1]` `jaccard >= dedup_jaccard_high` → no row in `articles`, no
  row in `article_fakes`, no ARQ transform job, no row in
  `article_embeddings`.
  - [test_dedup_scraper_integration.py:test_high_band_candidate_is_skipped_with_no_articles_no_fakes_no_embedding_row](../../backend/tests/unit/test_dedup_scraper_integration.py)
    (asserts no `Article` and no `ArticleEmbedding` was added; "no
    `article_fakes` / no ARQ" are downstream of `inserted` and are
    covered transitively by router tests below — see ambiguity note in
    Gap analysis).
  - [test_dedup_classifier.py:test_high_band_jaccard_skip_returns_reason_jaccard_no_embedding_call](../../backend/tests/unit/test_dedup_classifier.py)
- `[2.2]` Skip increments `skipped_near_duplicates` and emits one info
  log line carrying `reason=jaccard` and `matched_article_id`.
  - [test_dedup_scraper_integration.py:test_high_band_skip_logs_info_with_reason_jaccard_and_matched_article_id](../../backend/tests/unit/test_dedup_scraper_integration.py)
  - [test_dedup_classifier.py:test_high_band_skip_carries_matched_article_id_of_argmax_incumbent](../../backend/tests/unit/test_dedup_classifier.py)
- `[2.3]` High-band skip does not trigger any embedding API call.
  - [test_dedup_classifier.py:test_high_band_jaccard_skip_returns_reason_jaccard_no_embedding_call](../../backend/tests/unit/test_dedup_classifier.py)
  - [test_dedup_scraper_integration.py:test_high_band_candidate_is_skipped_with_no_articles_no_fakes_no_embedding_row](../../backend/tests/unit/test_dedup_scraper_integration.py)

### 3. Low-band insert with no embedding (cost-win path)

- `[3.1]` Max Jaccard `< dedup_jaccard_floor` → insert + ARQ transform
  enqueue.
  - [test_dedup_scraper_integration.py:test_low_band_candidate_is_inserted_no_embedding_call_no_embedding_row](../../backend/tests/unit/test_dedup_scraper_integration.py)
  - [test_dedup_classifier.py:test_low_band_insert_returns_accept_no_embedding_no_call](../../backend/tests/unit/test_dedup_classifier.py)
- `[3.2]` No row in `article_embeddings`.
  - [test_dedup_scraper_integration.py:test_low_band_candidate_is_inserted_no_embedding_call_no_embedding_row](../../backend/tests/unit/test_dedup_scraper_integration.py)
  - [test_dedup_classifier.py:test_low_band_insert_returns_accept_no_embedding_no_call](../../backend/tests/unit/test_dedup_classifier.py)
- `[3.3]` No embedding API call.
  - [test_dedup_scraper_integration.py:test_low_band_candidate_is_inserted_no_embedding_call_no_embedding_row](../../backend/tests/unit/test_dedup_scraper_integration.py)
  - [test_dedup_classifier.py:test_low_band_insert_returns_accept_no_embedding_no_call](../../backend/tests/unit/test_dedup_classifier.py)

### 4. Ambiguous-band escalation with embedding-cosine skip

- `[4.1]` Candidate in `[floor, high)` triggers cosine vs incumbents
  whose Jaccard with the candidate is `>= floor` (others excluded).
  - [test_dedup_classifier.py:test_ambiguous_band_only_escalates_against_incumbents_with_jaccard_above_floor](../../backend/tests/unit/test_dedup_classifier.py)
- `[4.2]` Any incumbent cosine `>= dedup_cosine_threshold` → skip:
  no row in `articles`, no row in `article_fakes`, no ARQ transform
  job, no embedding row persisted for the candidate.
  - [test_dedup_classifier.py:test_ambiguous_band_with_cosine_match_returns_reason_embedding](../../backend/tests/unit/test_dedup_classifier.py)
  - [test_dedup_scraper_integration.py:test_ambiguous_band_skip_logs_info_with_reason_embedding_and_matched_article_id](../../backend/tests/unit/test_dedup_scraper_integration.py)
    (asserts `skipped_near_duplicates == 1`; "no fake row / no ARQ"
    follow transitively from `inserted` being empty — see Gap analysis).
- `[4.3]` Skip increments `skipped_near_duplicates` and logs
  `reason=embedding` with `matched_article_id`.
  - [test_dedup_scraper_integration.py:test_ambiguous_band_skip_logs_info_with_reason_embedding_and_matched_article_id](../../backend/tests/unit/test_dedup_scraper_integration.py)
  - [test_dedup_classifier.py:test_ambiguous_band_with_cosine_match_returns_reason_embedding](../../backend/tests/unit/test_dedup_classifier.py)

### 5. Ambiguous-band escalation with no match → insert + embed

- `[5.1]` Insert + ARQ enqueue + persist exactly one
  `article_embeddings` row whose `article_id` matches the new article,
  `embedding` length 1536, `model == settings.openai_model_embedding`.
  - [test_dedup_scraper_integration.py:test_ambiguous_band_no_match_inserts_article_and_persists_embedding_row](../../backend/tests/unit/test_dedup_scraper_integration.py)
  - [test_dedup_classifier.py:test_ambiguous_band_no_match_returns_accept_with_candidate_embedding_persisted](../../backend/tests/unit/test_dedup_classifier.py)

### 6. Comparison window

- `[6.1]` Incumbents are exactly the rows for which
  `COALESCE(published_at, created_at) > now() - interval '<dedup_window_hours> hours'`.
  - [test_dedup_scraper_integration.py:test_loader_sql_uses_coalesce_published_at_created_at_with_window_param](../../backend/tests/unit/test_dedup_scraper_integration.py)
- `[6.2]` Article older than the window is not an incumbent — candidate
  inserts even if a near-dup match would otherwise exist.
  - [test_dedup_scraper_integration.py:test_out_of_window_incumbent_does_not_trigger_skip](../../backend/tests/unit/test_dedup_scraper_integration.py)
- `[6.3]` `published_at IS NULL` with `created_at` inside the window →
  eligible incumbent.
  - [test_dedup_scraper_integration.py:test_incumbent_with_null_published_at_is_in_window_when_created_at_is_recent](../../backend/tests/unit/test_dedup_scraper_integration.py)
  - [test_dedup_scraper_integration.py:test_loader_sql_uses_coalesce_published_at_created_at_with_window_param](../../backend/tests/unit/test_dedup_scraper_integration.py)

### 7. Within-batch coherence

- `[7.1]` Two near-dup candidates in the same run → exactly one
  inserted, the other dropped; winner identity not asserted; dropped
  increments `skipped_near_duplicates`.
  - [test_dedup_scraper_integration.py:test_within_batch_two_near_duplicates_in_same_run_drop_one_increment_skip_counter](../../backend/tests/unit/test_dedup_scraper_integration.py)
  - [test_dedup_scraper_integration.py:test_within_batch_winner_identity_not_asserted](../../backend/tests/unit/test_dedup_scraper_integration.py)

### 8. Cross-source matching

- `[8.1]` Near-dup detection compares across all sources (NPR candidate
  skipped by NYT incumbent and vice versa).
  - [test_dedup_scraper_integration.py:test_cross_source_incumbent_skips_candidate_from_different_source](../../backend/tests/unit/test_dedup_scraper_integration.py)

### 9. Tokenizer (Jaccard input)

- `[9.1]` Tokens are lowercased.
  - [test_dedup_tokenize.py:test_tokenize_lowercases_input](../../backend/tests/unit/test_dedup_tokenize.py)
- `[9.2]` Punctuation stripped.
  - [test_dedup_tokenize.py:test_tokenize_strips_punctuation](../../backend/tests/unit/test_dedup_tokenize.py)
- `[9.3]` Whitespace-split.
  - [test_dedup_tokenize.py:test_tokenize_splits_on_whitespace](../../backend/tests/unit/test_dedup_tokenize.py)
- `[9.4]` Tokens of length `<= 2` removed.
  - [test_dedup_tokenize.py:test_tokenize_drops_tokens_of_length_two_or_less](../../backend/tests/unit/test_dedup_tokenize.py)
- `[9.5]` Stopword set frozen at exactly 12 specific words; extension
  is a spec change.
  - [test_dedup_tokenize.py:test_tokenize_drops_each_of_the_twelve_stopwords](../../backend/tests/unit/test_dedup_tokenize.py)
  - [test_dedup_tokenize.py:test_tokenize_stopword_set_size_is_exactly_twelve](../../backend/tests/unit/test_dedup_tokenize.py)
- `[9.6]` Only the title is tokenized — description not used.
  - [test_dedup_tokenize.py:test_tokenize_does_not_consume_description](../../backend/tests/unit/test_dedup_tokenize.py)

### 10. POST /api/scrape response shape

- `[10.1]` 202 body has exactly the five keys
  `{inserted, fetched, skipped_url_duplicates, skipped_near_duplicates, embedding_calls}`,
  all integers.
  - [test_dedup_scraper_integration.py:test_response_shape_has_exactly_five_integer_keys](../../backend/tests/unit/test_dedup_scraper_integration.py)
  - [test_scrape.py:test_post_scrape_happy_path_returns_202_with_inserted_and_fetched](../../backend/tests/routers/test_scrape.py)
  - [test_scrape.py:test_post_scrape_second_call_returns_202_with_zero_inserted](../../backend/tests/routers/test_scrape.py)
- `[10.2]` `inserted` and `fetched` keep their pre-task meaning;
  `inserted` = rows actually written to `articles`.
  - [test_scrape.py:test_post_scrape_happy_path_returns_202_with_inserted_and_fetched](../../backend/tests/routers/test_scrape.py)
  - [test_scrape.py:test_post_scrape_second_call_returns_202_with_zero_inserted](../../backend/tests/routers/test_scrape.py)
- `[10.3]` `embedding_calls` counts every embed invocation in the run
  (including cold-incumbent embeds); `0` when no candidate landed in
  the ambiguous band.
  - [test_dedup_scraper_integration.py:test_response_embedding_calls_is_zero_when_no_ambiguous_band_candidate](../../backend/tests/unit/test_dedup_scraper_integration.py)
  - [test_dedup_scraper_integration.py:test_response_embedding_calls_counts_each_call_including_cold_incumbent](../../backend/tests/unit/test_dedup_scraper_integration.py)
  - [test_dedup_classifier.py:test_cold_incumbent_embedding_is_computed_and_persisted_on_first_use](../../backend/tests/unit/test_dedup_classifier.py)
  - [test_dedup_classifier.py:test_warm_incumbent_embedding_is_reused_no_extra_call](../../backend/tests/unit/test_dedup_classifier.py)
- `[10.4]` Frontend type in `frontend/src/api/articles.ts` stays
  valid; extending it is optional.
  - **NOT TEST-COVERABLE (meta)** — frontend type-check is a separate
    pipeline; no behavior assertion belongs in the backend unit suite.

### 11. article_embeddings schema

- `[11.1]` Table `article_embeddings` exists.
  - [test_models.py:test_tablenames](../../backend/tests/unit/test_models.py)
  - [test_models.py:test_metadata_tables](../../backend/tests/unit/test_models.py)
- `[11.2]` `article_id INTEGER PRIMARY KEY`, FK to `articles(id)`,
  `ON DELETE CASCADE`.
  - [test_models.py:test_article_embeddings_table_has_article_id_pk_and_cascade_fk_to_articles](../../backend/tests/unit/test_models.py)
- `[11.3]` `embedding vector(1536) NOT NULL`,
  `model varchar(64) NOT NULL`,
  `created_at timestamptz NOT NULL DEFAULT now()`.
  - [test_models.py:test_article_embeddings_columns_match_spec](../../backend/tests/unit/test_models.py)
- `[11.4]` Deleting an `articles` row cascades to delete the matching
  `article_embeddings` row.
  - [test_models.py:test_article_embeddings_table_has_article_id_pk_and_cascade_fk_to_articles](../../backend/tests/unit/test_models.py)
    (FK `ondelete == "CASCADE"` is the schema-level expression of this
    behavior; runtime cascade in Postgres is not exercised because the
    spec defines unit-test-only coverage with no integration tests).
- `[11.5]` pgvector extension installed; no vector index required.
  - [test_migration_module.py:test_dedup_migration_creates_vector_extension_and_article_embeddings_table](../../backend/tests/unit/test_migration_module.py)
  - [test_migration_module.py:test_dedup_migration_chains_from_chat_messages_revision](../../backend/tests/unit/test_migration_module.py)

### 12. Mock mode (deterministic embeddings)

- `[12.1]` In `openai_mock_mode=true` the embedding service does not
  instantiate the OpenAI client / make network calls.
  - [test_embedding.py:test_embed_text_mock_does_not_import_openai_client](../../backend/tests/unit/test_embedding.py)
- `[12.2]` Same input → identical 1536-dim vector.
  - [test_embedding.py:test_embed_text_mock_same_input_returns_identical_vector](../../backend/tests/unit/test_embedding.py)
  - [test_embedding.py:test_embed_text_mock_returns_length_1536](../../backend/tests/unit/test_embedding.py)
- `[12.3]` Different inputs → cosine strictly `< 1.0`
  (distinguishable; diverges from constant-output pattern).
  - [test_embedding.py:test_embed_text_mock_different_inputs_have_cosine_strictly_less_than_one](../../backend/tests/unit/test_embedding.py)
- `[12.4]` Returned vector length is 1536.
  - [test_embedding.py:test_embed_text_mock_returns_length_1536](../../backend/tests/unit/test_embedding.py)
- `[12.5]` All tests run with `openai_mock_mode=true`; no test makes a
  real OpenAI request.
  - **Convention-only coverage.** Each dedup test module has an
    autouse fixture (`_force_mock_mode`) that sets
    `openai_mock_mode=True`; the real-API test
    [test_embedding.py:test_embed_text_real_path_calls_openai_with_configured_model](../../backend/tests/unit/test_embedding.py)
    monkeypatches `openai.AsyncOpenAI` so no network call is made.
    There is no suite-wide network-egress guard. See Gap analysis.
- `[12.6]` Mock toggle reuses existing `openai_mock_mode` setting; no
  new flag introduced.
  - [test_config.py:test_settings_openai_mock_mode_defaults_to_false](../../backend/tests/test_config.py)
  - [test_config.py:test_env_example_documents_openai_mock_mode](../../backend/tests/test_config.py)
  - **Partially uncovered:** there is no positive assertion that the
    `Settings` model contains no *new* dedup-mock flag. See Gap
    analysis.

### 13. Test-coverage policy

- `[13.1]` Every acceptance criterion has at least one unit test.
  - **Meta criterion** — satisfied by the coverage map itself.
- `[13.2]` No new integration tests added; existing integration tests
  keep passing.
  - **Meta criterion** — verified at QA-execution time by running the
    full unit suite, not by a specific test.

### 14. Tunable settings

- `[14.1]` `dedup_window_hours` default `168`, must be `> 0`.
  - [test_config.py:test_dedup_window_hours_default_is_168_and_must_be_positive](../../backend/tests/test_config.py)
- `[14.2]` `dedup_jaccard_high` default `0.80`, `0 < x <= 1`.
  - [test_config.py:test_dedup_jaccard_high_default_is_080_and_within_zero_one](../../backend/tests/test_config.py)
- `[14.3]` `dedup_jaccard_floor` default `0.40`, `0 <= x <= 1`.
  - [test_config.py:test_dedup_jaccard_floor_default_is_040_and_within_zero_one](../../backend/tests/test_config.py)
- `[14.4]` `dedup_cosine_threshold` default `0.88`, `0 < x <= 1`.
  - [test_config.py:test_dedup_cosine_threshold_default_is_088_and_within_zero_one](../../backend/tests/test_config.py)
- `[14.5]` `openai_model_embedding` default `text-embedding-3-small`,
  persisted in the `model` column of `article_embeddings`.
  - [test_config.py:test_openai_model_embedding_default_is_text_embedding_3_small](../../backend/tests/test_config.py)
  - [test_dedup_scraper_integration.py:test_ambiguous_band_no_match_inserts_article_and_persists_embedding_row](../../backend/tests/unit/test_dedup_scraper_integration.py)
    (asserts `embs[0].model == settings.openai_model_embedding`).
- `[14.6]` Changing any setting via env at startup changes observed
  dedup behavior with no code change.
  - Implicitly covered by 14.1–14.5: the `Settings` instance is
    rebuilt from env per test, and the scraper/dedup paths read those
    settings at runtime (see `_force_mock_mode` fixtures in
    [test_dedup_classifier.py](../../backend/tests/unit/test_dedup_classifier.py)
    and
    [test_dedup_scraper_integration.py](../../backend/tests/unit/test_dedup_scraper_integration.py)
    that override `settings.dedup_*` and observe behavior change).
    No dedicated end-to-end "env → behavior" test exists. See Gap
    analysis (soft gap).

### 15. Idempotency / boundary behavior

- `[15.1]` Jaccard exactly `dedup_jaccard_high` → skip.
  - [test_dedup_classifier.py:test_jaccard_equal_to_high_threshold_is_skip](../../backend/tests/unit/test_dedup_classifier.py)
- `[15.2]` Jaccard exactly `dedup_jaccard_floor` → escalate to cosine.
  - [test_dedup_classifier.py:test_jaccard_equal_to_floor_threshold_escalates_to_cosine](../../backend/tests/unit/test_dedup_classifier.py)
- `[15.3]` Cosine exactly `dedup_cosine_threshold` → match (skip).
  - [test_dedup_classifier.py:test_cosine_equal_to_threshold_is_skip](../../backend/tests/unit/test_dedup_classifier.py)

### 16. Non-regression (URL pipeline)

- `[16.1]` No-collision run still returns `inserted == fetched`
  (modulo parse drops) and produces a `pending` `article_fakes` row
  per inserted article.
  - [test_dedup_scraper_integration.py:test_non_regression_no_collisions_inserts_every_article_with_pending_fake_row](../../backend/tests/unit/test_dedup_scraper_integration.py)
    (asserts the `inserted` contract that the lifespan/router relies
    on to call `transformer.create_and_enqueue` — pending-row creation
    is downstream of `inserted` and is exercised by the article-
    transformer task's QA, not re-tested here).
  - [test_scrape.py:test_post_scrape_happy_path_returns_202_with_inserted_and_fetched](../../backend/tests/routers/test_scrape.py)
- `[16.2]` `make` lint targets (`ruff`, `black`,
  `make docs-fix && make docs-lint`) clean on new code/docs.
  - **Meta criterion** — verified at QA-execution time by running the
    repo's lint targets, not by a specific unit test.
- `[16.3]` Existing unit + integration + router suites continue to
  pass unchanged (this task adds no new tests outside dedup).
  - **Meta criterion** — verified by running the full backend test
    suite, not a specific test.

## Gap analysis

The mapping above flags the following soft gaps. None block QA on its
own, but each is recorded here so it can be picked up at QA-execution
time or recorded as a known limitation.

1. **`[2.1]` / `[4.2]` — "no `article_fakes` row, no ARQ transform job"
   on near-dup skip.** No test directly inspects the absence of an
   `article_fakes` row or an ARQ enqueue call when a candidate is
   skipped. The integration test asserts `_articles_added == []` and
   `_embeddings_added == []`, and the router-level contract is "fakes
   and ARQ are emitted from `result.inserted`" — so an empty `inserted`
   transitively guarantees the no-fake/no-ARQ behavior. This is
   acceptable indirect coverage but worth flagging if QA wants a direct
   assertion.
2. **`[10.4]` Frontend articles.ts type validity.** Not test-coverable
   in the backend unit suite. Verified at QA-execution time by frontend
   type-check (`npm run typecheck` or equivalent), not pytest.
3. **`[11.4]` CASCADE runtime behavior.** Covered at the schema
   declaration level (FK `ondelete == "CASCADE"`); not exercised against
   a real Postgres because the spec scopes this task to unit tests
   only. Acceptable per the spec's Test-coverage policy.
4. **`[12.5]` Suite-wide network-egress guard.** No autouse fixture
   forbids real OpenAI HTTP calls across the entire suite. Mitigated
   by per-module `_force_mock_mode` fixtures and per-test
   monkeypatches; matches the chat-llm task's accepted gap (see
   [chat-llm-01](../iteration-1/issues/chat-llm-01-ac25-no-suite-wide-network-egress-guard.md)
   for the prior precedent). Recommend acceptance under the same
   convention-only treatment.
5. **`[12.6]` "no new mock flag introduced" — partial.** Coverage is
   negative-by-omission: the existing `openai_mock_mode` test stands,
   and there is no positive assertion that `Settings.model_fields`
   excludes a hypothetical new dedup-mock flag (compare the explicit
   `chat_model not in fields` style of
   `test_chat_llm_module_does_not_introduce_chat_model_or_chat_temperature_fields`).
   Soft gap.
6. **`[14.6]` "env → behavior" wiring.** Covered indirectly (env is
   parsed in 14.1–14.5; behavior changes are observed in classifier
   tests via `monkeypatch.setattr(settings, ...)`). No single test
   chains "set env var → reload settings → run a scrape and observe
   different dedup decision." Soft gap.

**Conclusion:** every acceptance criterion in the spec maps to at least
one unit test, with the meta criteria (`[13.1]`, `[13.2]`, `[16.2]`,
`[16.3]`, and `[10.4]`) noted as not-test-coverable inside the backend
unit suite. The six soft gaps above are flagged for QA judgement at
execution time but do not by themselves render any criterion
**UNCOVERED**.

## Pass / fail criteria

QA passes when both hold:

1. Every acceptance criterion has at least one mapped test (zero
   UNCOVERED). The audit above reports zero UNCOVERED.
2. The mapped tests exit `0` with no failures and no skips, and the
   lint/full-suite meta checks (`[16.2]`, `[16.3]`) succeed.

### Command — mapped tests only

Run from `backend/`:

```sh
uv run pytest -v \
  tests/unit/test_dedup_tokenize.py \
  tests/unit/test_dedup_jaccard.py \
  tests/unit/test_dedup_cosine.py \
  tests/unit/test_dedup_classifier.py \
  tests/unit/test_dedup_scraper_integration.py \
  tests/unit/test_embedding.py \
  tests/unit/test_models.py \
  tests/unit/test_migration_module.py \
  tests/test_config.py \
  tests/routers/test_scrape.py
```

### Command — full unit suite (covers `[16.3]` non-regression)

Run from `backend/`:

```sh
uv run pytest -v
```

### Lint meta checks (covers `[16.2]`)

Run from the repo root:

```sh
make docs-fix && make docs-lint
uv run --project backend ruff check backend
uv run --project backend black --check backend
```

If both pytest invocations exit `0` with zero failures and zero skips,
and the lint commands exit clean, QA passes.

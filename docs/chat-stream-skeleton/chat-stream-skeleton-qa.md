# QA — `chat-stream-skeleton`

Coverage audit only. Maps each acceptance criterion in
[chat-stream-skeleton-spec.md](chat-stream-skeleton-spec.md) to the unit
tests the dev wrote. Black-box: tests are mapped by name, not by reading
implementation logic.

Test files audited:

- `backend/tests/unit/test_chat_generator.py`
- `backend/tests/unit/test_chat_service.py`
- `backend/tests/routers/test_chat.py` (router-level unit tests against
  the FastAPI app via `httpx.ASGITransport`)

## Coverage map

### Endpoint surface

- **AC1 — `POST /api/articles/{article_id}/chat` mounted under `/api`.**
  Covered by:
  - `tests/routers/test_chat.py::test_post_chat_registered_under_api_prefix`
- **AC2 — Pydantic body validation (missing / non-string / empty /
  whitespace-only / oversized rejected with 422; verbatim persistence
  on accept).** Covered by:
  - `tests/routers/test_chat.py::test_post_chat_rejects_missing_message_with_422`
  - `tests/routers/test_chat.py::test_post_chat_rejects_non_string_message_with_422`
  - `tests/routers/test_chat.py::test_post_chat_rejects_empty_string_message_with_422`
  - `tests/routers/test_chat.py::test_post_chat_rejects_whitespace_only_message_with_422`
  - `tests/routers/test_chat.py::test_post_chat_rejects_message_longer_than_max_chars_with_422`
  - `tests/routers/test_chat.py::test_post_chat_accepts_message_at_exact_max_chars_boundary`
  - `tests/routers/test_chat.py::test_post_chat_persists_message_verbatim_including_surrounding_whitespace`
  - `tests/unit/test_chat_service.py::test_post_chat_stream_persists_message_verbatim`
- **AC3 — 404 with `{"detail": "Article <id> not found"}` for missing
  article; no rows, no SSE.** Covered by:
  - `tests/routers/test_chat.py::test_post_chat_returns_404_with_detail_for_missing_article`
  - `tests/routers/test_chat.py::test_post_chat_inserts_no_rows_on_404_missing_article`
  - `tests/routers/test_chat.py::test_post_chat_does_not_open_sse_stream_on_404`
  - `tests/unit/test_chat_service.py::test_post_chat_stream_raises_not_found_when_article_missing`
- **AC4 — happy-path: HTTP 200, `Content-Type: text/event-stream`,
  `Cache-Control: no-cache`, `X-Accel-Buffering: no`,
  `Connection: keep-alive`.** Covered by:
  - `tests/routers/test_chat.py::test_post_chat_happy_path_status_200`
  - `tests/routers/test_chat.py::test_post_chat_happy_path_content_type_is_event_stream`
  - `tests/routers/test_chat.py::test_post_chat_happy_path_sets_cache_control_no_cache_header`
  - `tests/routers/test_chat.py::test_post_chat_happy_path_sets_x_accel_buffering_no_header`
  - `tests/routers/test_chat.py::test_post_chat_happy_path_sets_connection_keep_alive_header`

### SSE wire format

- **AC5 — `data: {"token": "<chunk>"}\n\n` with concatenation equal to
  full reply.** Covered by:
  - `tests/routers/test_chat.py::test_post_chat_each_token_event_is_data_token_json_with_double_newline`
  - `tests/routers/test_chat.py::test_post_chat_concatenated_token_chunks_equal_full_assistant_reply`
- **AC6 — exactly one `[DONE]` after the last token (happy path); no
  `[DONE]` on error path.** Covered by:
  - `tests/routers/test_chat.py::test_post_chat_happy_path_emits_exactly_one_done_event_after_last_token`
  - `tests/routers/test_chat.py::test_post_chat_error_path_emits_no_done_event`
- **AC7 — exactly one error event then close; sanitised, non-empty,
  no exception class / traceback / LLM payload leakage.** Covered by:
  - `tests/routers/test_chat.py::test_post_chat_error_path_emits_exactly_one_error_event_then_closes`
  - `tests/routers/test_chat.py::test_post_chat_error_event_payload_does_not_contain_exception_class_name`

### Persistence — happy path

- **AC8 — user row inserted/committed before stream opens (verbatim
  content, `is_error=false`).** Covered by:
  - `tests/routers/test_chat.py::test_post_chat_user_row_committed_before_stream_opens_with_verbatim_content`
  - `tests/unit/test_chat_service.py::test_post_chat_stream_commits_user_row_before_returning_response`
- **AC9 — assistant row inserted/committed before stream closes
  (`is_error=false`, `content` = concat of token chunks).** Covered by:
  - `tests/routers/test_chat.py::test_post_chat_assistant_row_content_equals_concatenated_token_chunks`
  - `tests/routers/test_chat.py::test_post_chat_assistant_row_committed_before_done_event`
  - `tests/unit/test_chat_service.py::test_post_chat_stream_assistant_row_content_equals_concatenated_tokens`
- **AC10 — subsequent `GET .../chat` returns user-then-assistant in
  chronological order with the AC8/AC9 values.** Covered by:
  - `tests/routers/test_chat.py::test_get_chat_history_after_happy_post_returns_user_then_assistant_in_order`
  - The unit-level test asserts the ordered `(role, is_error, content)`
    contract on the GET response. End-to-end DB round-trip from a real
    POST is an integration concern, not a unit concern.

### Persistence — error path

- **AC11 — exactly one assistant row with `is_error=true` and a short
  non-empty sentinel; user row unchanged.** Covered by:
  - `tests/routers/test_chat.py::test_post_chat_error_path_writes_exactly_one_assistant_row_with_is_error_true`
  - `tests/routers/test_chat.py::test_post_chat_error_path_does_not_modify_user_row`
  - `tests/unit/test_chat_service.py::test_post_chat_stream_error_path_writes_assistant_row_with_sentinel`
- **AC12 — sentinel byte-for-byte equal between SSE event and persisted
  row; no class name / traceback / LLM payload.** Covered by:
  - `tests/routers/test_chat.py::test_post_chat_error_sentinel_string_byte_equal_in_sse_and_persisted_row`
  - `tests/routers/test_chat.py::test_post_chat_error_sentinel_does_not_contain_traceback_or_class_name`
  - `tests/unit/test_chat_service.py::test_post_chat_stream_error_sentinel_byte_equal_in_sse_and_persisted_row`
- **AC13 — `GET .../chat` after error returns `(user, false)` then
  `(assistant, true)` in order.** Covered by:
  - `tests/routers/test_chat.py::test_get_chat_history_after_error_post_returns_user_false_then_assistant_true`

### Mock generator behaviour

- **AC14 — deterministic, finite, 10..20 token chunks; canonical
  string.** Covered by:
  - `tests/unit/test_chat_generator.py::test_stream_mock_reply_yields_between_10_and_20_chunks_inclusive`
  - `tests/unit/test_chat_generator.py::test_stream_mock_reply_concatenates_to_canonical_string`
  - `tests/unit/test_chat_generator.py::test_stream_mock_reply_is_deterministic_across_calls`
- **AC15 — strictly positive total stream duration (observable
  pacing).** Covered by:
  - `tests/unit/test_chat_generator.py::test_stream_mock_reply_has_strictly_positive_total_duration`
- **AC16 — no OpenAI SDK import, no outbound HTTP, runs with placeholder
  `OPENAI_API_KEY`.** Covered by:
  - `tests/unit/test_chat_generator.py::test_stream_mock_reply_does_not_import_openai_sdk_module`
  - `tests/unit/test_chat_generator.py::test_stream_mock_reply_makes_no_outbound_http_call`
  - `tests/routers/test_chat.py::test_post_chat_works_with_placeholder_openai_api_key`

### Test hook for the error path

- **AC17 — exact-match force-error semantics on `chat_mock_force_error_token`.**
  Covered by:
  - `tests/unit/test_chat_generator.py::test_stream_mock_reply_raises_when_message_exactly_equals_force_token`
  - `tests/unit/test_chat_generator.py::test_stream_mock_reply_does_not_raise_on_substring_match_of_force_token`
  - `tests/unit/test_chat_generator.py::test_stream_mock_reply_does_not_raise_on_case_insensitive_match`
  - `tests/unit/test_chat_generator.py::test_stream_mock_reply_does_not_raise_on_whitespace_trimmed_match`
  - `tests/unit/test_chat_generator.py::test_stream_mock_reply_does_not_raise_when_force_token_is_none_default`

### Configuration / surface

- **AC18 — `chat_message_max_chars` default `512`; `≤ 512` accepted,
  `> 512` rejected with 422.** Covered by:
  - `tests/unit/test_chat_generator.py::test_settings_chat_message_max_chars_default_is_512`
  - `tests/routers/test_chat.py::test_post_chat_accepts_message_at_exact_max_chars_boundary`
  - `tests/routers/test_chat.py::test_post_chat_rejects_message_longer_than_max_chars_with_422`
- **AC19 — `chat_mock_force_error_token` defaults to `None`; default
  never reaches error branch.** Covered by:
  - `tests/unit/test_chat_generator.py::test_settings_chat_mock_force_error_token_default_is_none`
  - `tests/routers/test_chat.py::test_post_chat_with_default_force_token_never_takes_error_branch`

### Reuse / non-regression

- **AC20 — existing `GET /api/articles/{id}/chat` continues to behave
  unchanged.** Covered by:
  - `tests/routers/test_chat.py::test_get_chat_history_unchanged_status_and_shape_after_post_endpoint_added`
  - `tests/routers/test_chat.py::test_get_chat_history_registered_under_api_prefix`
  - `tests/routers/test_chat.py::test_get_chat_history_returns_404_with_detail_for_missing_article`
  - `tests/routers/test_chat.py::test_get_chat_history_response_shape_has_exactly_two_top_level_keys`
  - `tests/routers/test_chat.py::test_get_chat_history_each_message_has_exactly_six_required_keys`
  - `tests/routers/test_chat.py::test_get_chat_history_is_error_field_defaults_false_in_response`
  - `tests/routers/test_chat.py::test_get_chat_history_request_id_field_may_be_null_in_response`
  - `tests/routers/test_chat.py::test_get_chat_history_created_at_serialised_iso8601_with_timezone`
  - `tests/routers/test_chat.py::test_get_chat_history_no_auth_required_returns_200`
  - `tests/routers/test_chat.py::test_get_chat_history_post_method_returns_post_response_not_405`
  - `tests/unit/test_chat_service.py::test_chat_service_returns_messages_in_chronological_order`
  - `tests/unit/test_chat_service.py::test_chat_service_returns_empty_messages_for_article_with_no_messages`
  - `tests/unit/test_chat_service.py::test_chat_service_raises_not_found_error_for_missing_article`
  - `tests/unit/test_chat_service.py::test_chat_service_tie_break_orders_identical_created_at_by_ascending_id`
- **AC21 — scrape → transform pipeline and `GET /api/articles` feed
  not regressed.** Covered indirectly by the existing pre-task test
  suites continuing to pass:
  - `tests/unit/test_articles_service.py`
  - `tests/unit/test_scraper.py`
  - `tests/unit/test_transform_worker.py`
  - `tests/unit/test_openai_transform.py`
  - `tests/unit/test_transformer.py`

  No additional regression-targeted test was added in this task, which
  is intentional — non-regression is verified by re-running the full
  pre-existing unit suite as part of QA (see "Pass / fail criteria"
  below).

### Logging / safety

- **AC22 — no log line contains the request `message`, the full
  assistant reply, or a raw traceback.** Covered by:
  - `tests/routers/test_chat.py::test_post_chat_logs_do_not_contain_request_message_body`
  - `tests/routers/test_chat.py::test_post_chat_logs_do_not_contain_full_assistant_reply`
  - `tests/routers/test_chat.py::test_post_chat_error_path_logs_do_not_contain_traceback_string`
  - `tests/unit/test_chat_service.py::test_post_chat_stream_logs_omit_message_body_and_full_reply`
  - `tests/unit/test_chat_service.py::test_post_chat_stream_error_logs_omit_traceback_and_message_body`

### Quality gates

- **AC23 — `ruff` and `black` pass.** Verified by tooling, not by a
  unit test. Run `make backend-lint` (or the equivalent `ruff check` +
  `black --check`) at QA time.
- **AC24 — backend unit tests pass; sub-coverage (a)–(f).** This is a
  meta-criterion; each clause maps to existing tests above:
  - (a) happy-path SSE event sequence (token + `[DONE]`) — AC5, AC6
  - (b) happy-path two rows with expected role/is_error/content — AC8,
    AC9
  - (c) 404 path with no rows inserted — AC3
  - (d) 422 path for invalid bodies with no rows inserted — AC2
  - (e) forced-error path with error event and `is_error=true` row —
    AC7, AC11
  - (f) deterministic mock shape (10–20 tokens, no SDK) — AC14, AC16
- **AC25 — no real OpenAI request anywhere in the suite.** Covered by
  AC16 tests above plus the project-wide convention in `context.md`
  ("Mock LLM in All Tests"). No additional test is required.

## Gap analysis

No uncovered acceptance criteria. Every AC1–AC25 has at least one
mapped unit test or, where the criterion is a meta / quality gate
(AC21, AC23, AC24, AC25), is satisfied by the existing suite plus
tooling described above.

## Pass / fail criteria

QA passes when both of the following hold:

1. Every acceptance criterion has at least one mapped test (zero
   UNCOVERED) — already satisfied above.
2. The mapped tests, plus the pre-existing unit suite (for AC21
   non-regression), exit `0` with no failures and no skips, **and**
   the linters pass (AC23).

Run, from the repo root:

```bash
# Unit + router unit tests (mapped tests + non-regression suites).
docker compose run --rm backend pytest -v \
  backend/tests/unit/test_chat_generator.py \
  backend/tests/unit/test_chat_service.py \
  backend/tests/routers/test_chat.py \
  backend/tests/unit/test_articles_service.py \
  backend/tests/unit/test_scraper.py \
  backend/tests/unit/test_transform_worker.py \
  backend/tests/unit/test_openai_transform.py \
  backend/tests/unit/test_transformer.py

# Quality gates (AC23).
make backend-lint
```

Equivalently, running the full backend unit suite (
`docker compose run --rm backend pytest -v backend/tests/unit
backend/tests/routers`) is acceptable; pass/fail is then applied to the
full-suite result.

---
name: openai-transform QA
description: Coverage audit mapping each acceptance criterion in openai-transform-spec.md to the unit tests written by dev. Black-box only — no implementation reading, no new tests.
---

# QA — `openai-transform`

Spec under audit: [openai-transform-spec.md](openai-transform-spec.md)

Test files in scope:

- [backend/tests/unit/test_openai_transform.py](../backend/tests/unit/test_openai_transform.py)
- [backend/tests/unit/test_transform_worker.py](../backend/tests/unit/test_transform_worker.py)
- [backend/tests/test_config.py](../backend/tests/test_config.py)

## Coverage map

### AC1 — worker calls OpenAI exactly once with original `title` + `description`

- `test_openai_transform.py::test_generate_satirical_calls_openai_once_with_original_title_and_description`
  — asserts single `parse` await and that originals appear in user message
- `test_transform_worker.py::test_transform_article_passes_original_article_title_and_description_to_service`
  — asserts worker forwards the article's `title`/`description` to the service

### AC2 — success writes `title`, `description`, `model`, `temperature`, `completed`

- `test_transform_worker.py::test_transform_article_sets_completed_status_and_fills_mock_content`
  — `transform_status='completed'` set on success
- `test_transform_worker.py::test_transform_article_writes_service_response_to_fake_row`
  — service's `title`/`description` written through to row
- `test_transform_worker.py::test_transform_article_completed_row_model_equals_settings_openai_model_transform`
- `test_transform_worker.py::test_transform_article_completed_row_temperature_equals_settings_openai_temperature_transform`
- `test_openai_transform.py::test_generate_satirical_uses_settings_model_and_temperature`
  — `settings.openai_model_transform` / `openai_temperature_transform` flow through to the OpenAI call

### AC3 — non-empty, distinct from original and from mock fixed strings

- `test_openai_transform.py::test_generate_satirical_returned_title_and_description_are_non_empty_and_distinct_from_originals_and_mocks`

### AC4 — structured-output (JSON-schema) request format

- `test_openai_transform.py::test_generate_satirical_uses_structured_output_response_format`
  — asserts `response_format=SatiricalPair` (Pydantic model with required `title`, `description`)
- (Implicit) `SatiricalPair` is the parsed type asserted by every real-mode test, confirming the
  two-required-field shape.

### AC5 — client honours `settings.openai_request_timeout_seconds`

- `test_openai_transform.py::test_generate_satirical_passes_request_timeout_setting_to_openai_client`
  — patches setting to `17`, asserts `AsyncOpenAI(..., timeout=17)`

### AC6 — mock mode writes canonical pair + completed; model/temperature populated

- `test_openai_transform.py::test_generate_satirical_mock_mode_returns_canonical_pair`
  — service returns `MOCK_TITLE`/`MOCK_DESCRIPTION` constants (canonical-pair invariant follows
  from constants being module-level)
- `test_transform_worker.py::test_transform_article_sets_completed_status_and_fills_mock_content`
  — under default `_patch_service()` (returns the mock pair), worker writes `MOCK_TITLE` /
  `MOCK_DESCRIPTION` and sets `transform_status='completed'`
- `test_transform_worker.py::test_transform_article_completed_row_model_equals_settings_openai_model_transform`
- `test_transform_worker.py::test_transform_article_completed_row_temperature_equals_settings_openai_temperature_transform`
  — model/temperature populated from settings on the completed row (test does not distinguish
  mock vs real-mode origin of the pair, which is acceptable — the worker write-path is identical)

### AC7 — mock mode: no SDK instantiation, no network, works with placeholder key

- `test_openai_transform.py::test_generate_satirical_mock_mode_does_not_instantiate_openai_client`
- `test_openai_transform.py::test_generate_satirical_mock_mode_makes_no_network_request`
- `test_openai_transform.py::test_generate_satirical_mock_mode_works_with_placeholder_api_key`

### AC8 — completed row idempotency: no OpenAI call, no row mutation, log skip

- `test_transform_worker.py::test_transform_article_completed_row_skips_openai_call`
- `test_transform_worker.py::test_transform_article_completed_row_does_not_modify_row`
- `test_transform_worker.py::test_transform_article_completed_row_logs_skip_event`

### AC9 — failure path

(a) Deletes `article_fakes` row:

- `test_transform_worker.py::test_transform_article_deletes_fake_row_on_unexpected_exception`
  — asserts `rollback` then a single `execute` (the targeted DELETE) and `commit`

(b) Preserves `articles` row:

- `test_transform_worker.py::test_transform_article_preserves_article_row_when_fake_deleted_on_exception`
  — asserts only one `execute` await (no second statement touching `articles`)

(c) One ERROR log line with `article_id`:

- `test_transform_worker.py::test_transform_article_failure_emits_one_error_log_with_article_id`
  — asserts exactly one ERROR record containing the id and the exception type name

(d) Exception does not propagate from worker:

- `test_transform_worker.py::test_transform_article_failure_does_not_propagate_exception`

(e) No retry (`max_tries=1`):

- `test_transform_worker.py::test_worker_settings_max_tries_is_one`

Failure-variant coverage required by AC9 wording ("any OpenAI failure path … timeout, API error,
connection error, malformed JSON, schema mismatch") — verified at the service boundary that
each variant raises so the worker catch-all engages:

- `test_openai_transform.py::test_generate_satirical_propagates_timeout_exception`
- `test_openai_transform.py::test_generate_satirical_propagates_api_error_exception`
- `test_openai_transform.py::test_generate_satirical_propagates_malformed_json_exception`
- `test_openai_transform.py::test_generate_satirical_propagates_schema_validation_exception`
- `test_openai_transform.py::test_generate_satirical_raises_on_refusal_response` (bonus —
  refusal mapped to `ValueError`, exercises the schema-mismatch class)
- Connection-error variant is **not** independently tested. The worker's catch-all is exercised by
  `test_transform_article_deletes_fake_row_on_unexpected_exception` (`Exception("openai flake")`),
  which structurally subsumes any future exception class. Recorded as covered-by-superclass; if
  reviewers want a dedicated `ConnectionError` propagation test, that is a nice-to-have rather
  than a blocking gap given AC9's enumeration is open-ended ("any OpenAI failure path").

### AC10 — `OPENAI_REQUEST_TIMEOUT_SECONDS` Pydantic field, positive int, default 30

- `test_config.py::test_settings_openai_request_timeout_seconds_defaults_to_30`
- `test_config.py::test_settings_openai_request_timeout_seconds_rejects_zero_or_negative`

### AC11 — `OPENAI_MOCK_MODE` Pydantic boolean, default `false`

- `test_config.py::test_settings_openai_mock_mode_defaults_to_false`

### AC12 — `.env.example` documents both vars

- `test_config.py::test_env_example_documents_openai_request_timeout_seconds`
- `test_config.py::test_env_example_documents_openai_mock_mode`

### AC13 — public worker contract unchanged

- `test_transform_worker.py::test_worker_settings_max_tries_is_one`
  — `WorkerSettings.max_tries == 1`
- `test_transform_worker.py::test_worker_settings_functions_contains_transform_article`
  — `transform_article` registered in `WorkerSettings.functions`
- Signature `async def transform_article(ctx, article_id: int) -> None` is exercised by every
  worker test invoking `await transform_article({}, article_id=N)`; no dedicated `inspect.signature`
  assertion exists. Recorded as covered-by-use.

### AC14 — no log line contains full prompt, response, or `OPENAI_API_KEY`

- `test_transform_worker.py::test_transform_article_failure_log_does_not_contain_prompt_response_or_api_key`
- `test_transform_worker.py::test_transform_article_success_log_does_not_contain_prompt_response_or_api_key`
  — both filter `caplog` to logger `app.workers.transform`. Logs emitted from
  `app.services.openai_transform` (if any) are not captured by these tests. See gap analysis.

### AC15 — `ruff` + `black` pass on touched files

Out-of-band quality gate, not test-mapped. Verified by running:

```bash
cd backend && ruff check app tests && black --check app tests
```

### AC16 — required test variants present

Meta-criterion. Required variants and where they land:

- Real-call success path → AC1–AC5 mappings above
- Mock-mode short-circuit (no SDK / no network) → AC7 mappings
- `completed`-row idempotency skip → AC8 mappings
- Timeout / API-error / malformed-JSON / schema-validation variants → AC9 service-side
  propagation tests

All four required failure variants are present at the service boundary; the worker catch-all
test demonstrates the swallow/delete/log behaviour for any raising service.

### AC17 — no test makes a real outbound OpenAI request

- All real-mode tests in `test_openai_transform.py` patch `openai.AsyncOpenAI` (class-level
  intercept) before any call.
- All mock-mode tests in `test_openai_transform.py` short-circuit before SDK instantiation;
  `test_generate_satirical_mock_mode_does_not_instantiate_openai_client` and
  `test_generate_satirical_mock_mode_makes_no_network_request` are the explicit guards.
- All `test_transform_worker.py` tests patch `app.workers.transform.openai_transform.generate_satirical`
  with `AsyncMock`, so no code path reaches the real SDK.

No dedicated meta-test enforces "no test in the suite issues a real OpenAI request" (e.g.,
network-blocking fixture or `pytest-socket`). Recorded as covered-by-pattern; reviewers may
opt to add a network-deny conftest as a future hardening, but it is not a blocking gap given
the patching pattern is uniform across both test files.

## Gap analysis

No fully UNCOVERED criteria. Two notes for reviewer awareness — neither blocks QA:

1. **AC14 — service-module logs not asserted.** The two logging-safety tests pin
   `caplog.at_level(..., logger="app.workers.transform")`, so any log records emitted by
   `app.services.openai_transform` are not inspected. Spec wording is "no log line emitted by
   this task". This is recorded as a partial coverage observation. If the service module is
   verified (via code review during `/start-qa`) to emit no log records, the worker-only
   assertions are sufficient. If the service module does log, an additional caplog assertion
   scoped to `app.services.openai_transform` should be added before QA can pass.
2. **AC9 connection-error variant.** Not independently propagation-tested; covered structurally
   by the worker's generic `Exception` catch-all test. Non-blocking.

## Pass / fail criteria

QA passes when **both** are true:

1. Every acceptance criterion has at least one mapped test (currently true; see notes above for
   AC14 caveat).
2. The mapped tests exit `0` with no failures and no skips.

Command to run the mapped tests:

```bash
cd backend && pytest -v \
  tests/unit/test_openai_transform.py \
  tests/unit/test_transform_worker.py \
  tests/test_config.py
```

Plus the AC15 quality gate:

```bash
cd backend && ruff check app tests && black --check app tests
```

QA fails on any test failure, any skip in the mapped files, or any `ruff`/`black` violation
on touched files.

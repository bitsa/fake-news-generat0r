# Real OpenAI Call in `transform_article` — Dev Plan

## MUST READ FIRST

- [`context.md`](../context.md) — decisions and standards. Most relevant here:
  async-only I/O, type hints, Pydantic Settings (never read `os.environ`),
  logging rules ("Never log: full LLM prompts or responses, API keys"),
  Transform Durability Model (two-state lifecycle, delete-on-failure,
  `max_tries=1`), and "Mock LLM in All Tests".
- [`plans/plan.md`](../plans/plan.md) — workflow and doc structure.
- [`docs/openai-transform-spec.md`](openai-transform-spec.md) — source of truth
  for this task.

Key source files examined:

- `backend/app/workers/transform.py` — current worker writes `MOCK_TITLE` /
  `MOCK_DESCRIPTION` constants to the row. No idempotency check on
  `transform_status == 'completed'`. Catches `Exception` → rollback, delete,
  commit, log `error` with `exc_info=True`. `WorkerSettings.max_tries = 1`.
- `backend/app/config.py` — `Settings` already has `openai_api_key`,
  `openai_model_transform = "gpt-4o-mini"`, `openai_temperature_transform = 0.9`.
  No `openai_request_timeout_seconds`, no `openai_mock_mode` yet.
- `backend/app/models.py` — `ArticleFake` PK = `article_id` (FK with
  `ondelete=CASCADE`); `transform_status` CHECK constraint
  `IN ('pending','completed')`; `title` / `description` / `model` / `temperature`
  all nullable. `Article` has `id`, `title`, `description`. No schema change.
- `backend/app/services/transformer.py` — **out of scope for this task**
  (per spec). Only enqueues; does not call OpenAI.
- `backend/app/main.py`, `backend/app/routers/scrape.py` — **out of scope**
  (per spec).
- `backend/tests/unit/test_transform_worker.py` — patches
  `app.workers.transform.AsyncSessionLocal`; imports `MOCK_TITLE`,
  `MOCK_DESCRIPTION` from the worker module; asserts on a `MagicMock` fake
  with `commit`/`rollback`/`execute` `AsyncMock`s. **Will need updates** —
  the happy-path tests currently assume the static mock-string write happens
  unconditionally; under this task that path runs only when
  `OPENAI_MOCK_MODE=true`.
- `backend/tests/conftest.py` — sets `OPENAI_API_KEY=sk-test-placeholder`. No
  `OPENAI_MOCK_MODE` is set, so tests run with the production default
  (`false`) unless individually patched.
- `backend/pyproject.toml` — `openai>=1.54` already a runtime dependency
  (no install needed).
- `.env.example` — already has `OPENAI_MOCK_MODE=true`; missing
  `OPENAI_REQUEST_TIMEOUT_SECONDS`. Spec calls out the existing line as
  pre-existing drift that this task corrects (a fresh clone must not
  silently enable mock mode).

---

## Files to Touch / Create

| Action | Path |
|--------|------|
| **MODIFY** | `backend/app/config.py` — add `openai_request_timeout_seconds`, `openai_mock_mode` |
| **CREATE** | `backend/app/services/openai_transform.py` — service that produces a satirical pair (real call or mock short-circuit) |
| **MODIFY** | `backend/app/workers/transform.py` — load `Article`, call new service, add `completed`-row idempotency skip, log without prompt/response/key |
| **MODIFY** | `.env.example` — add `OPENAI_REQUEST_TIMEOUT_SECONDS=30` only. **Do not touch the existing `OPENAI_MOCK_MODE` line** (per user direction during dev planning) |
| **MODIFY** | `backend/tests/unit/test_transform_worker.py` — new tests have to coexist with existing ones; existing happy-path tests need to be retargeted to the mock-mode branch |
| **CREATE** | `backend/tests/unit/test_openai_transform.py` — service-level tests (real-call path, mock short-circuit, structured-output format, timeout wiring, failure variants) |
| **MODIFY** | `backend/tests/test_config.py` — assert defaults for the two new settings fields |

No migration. No schema change. No frontend change.

---

## Interfaces / Contracts to Expose

### `backend/app/config.py` — additions to `Settings`

```python
openai_request_timeout_seconds: int = Field(default=30, gt=0)
openai_mock_mode: bool = False
```

`gt=0` enforces AC10 ("positive integer default of 30"). Default `false`
satisfies AC11.

### `backend/app/services/openai_transform.py`

```python
from pydantic import BaseModel

MOCK_TITLE: str   # canonical mock title (single value, re-used on every call)
MOCK_DESCRIPTION: str   # canonical mock description (single value, re-used)


class SatiricalPair(BaseModel):
    title: str
    description: str


async def generate_satirical(
    original_title: str,
    original_description: str,
) -> SatiricalPair:
    """
    Returns a satirical (title, description) pair.

    When ``settings.openai_mock_mode`` is True, returns the canonical
    (MOCK_TITLE, MOCK_DESCRIPTION) pair without instantiating the OpenAI SDK
    or making any network request.

    Otherwise calls OpenAI with a structured-output (JSON-schema) request
    using ``settings.openai_model_transform``,
    ``settings.openai_temperature_transform``, and a request timeout of
    ``settings.openai_request_timeout_seconds`` seconds.

    Raises any OpenAI client / timeout / JSON / pydantic-validation
    exception. The caller (worker) is responsible for cleanup and logging
    per the failure-path contract.
    """
```

The constants `MOCK_TITLE` / `MOCK_DESCRIPTION` move out of
`workers/transform.py` and live here. The worker re-exports them with
backward-compatible aliases is not necessary — the only importer is the
existing test file, which gets updated in step 9.

### `backend/app/workers/transform.py` — public contract unchanged

```python
async def transform_article(ctx: dict, article_id: int) -> None: ...

class WorkerSettings:
    functions = [transform_article]
    redis_settings: RedisSettings  # unchanged
    max_tries = 1
```

AC13 satisfied: same signature, same `max_tries`, same module path.

### Logging shape (informational; not part of any external contract)

- `INFO worker.transform.start article_id=<id>` — once per call.
- `INFO worker.transform.skip.missing article_id=<id>` — when fake row absent.
- `INFO worker.transform.skip.completed article_id=<id>` — AC8.
- `INFO worker.transform.skip.no_article article_id=<id>` — defensive (Article
  row missing despite fake row existing); covered by spec's resolved open
  question, not asserted.
- `INFO worker.transform.done article_id=<id> model=<model>` — success.
- `ERROR worker.transform.failed article_id=<id> exc_type=<ClassName>` —
  failure path. **No `exc_info=True`** (the existing worker uses it; the
  spec's AC14 explicitly permits "the failing exception type name" only,
  not the full traceback, since stack frames may include locals or the
  prompt as repr in some SDK paths). Drop `exc_info` to stay defensive.

No log line at any level may include the original or fake `title` /
`description` text, the system or user prompt, the response body, or
`OPENAI_API_KEY` — see AC14.

---

## Implementation Plan

### Step 1 — `backend/app/config.py`

Add the two fields shown above. Keep `Field(default=30, gt=0)` so that
non-positive values raise on app startup rather than silently propagating
into the OpenAI client.

### Step 2 — Create `backend/app/services/openai_transform.py`

#### 2a. Module-level constants

```python
MOCK_TITLE = "Local Man Discovers He's Been Doing Everything Wrong This Whole Time"
MOCK_DESCRIPTION = (
    "Experts confirm the situation is exactly as bad as it sounds, "
    "but stress there is still time to feel vaguely embarrassed about it."
)
```

These are the same strings the worker currently uses, moved verbatim. The
test file's existing import path changes from
`app.workers.transform` to `app.services.openai_transform`.

#### 2b. `SatiricalPair` Pydantic model

`title: str`, `description: str`. Used as the `response_format` argument so
the OpenAI SDK enforces the JSON-schema shape and surfaces a validation
error if the model returns extra/missing/wrongly-typed fields.

#### 2c. `generate_satirical`

1. **Mock-mode short-circuit.** If `settings.openai_mock_mode is True`,
   return `SatiricalPair(title=MOCK_TITLE, description=MOCK_DESCRIPTION)`
   immediately. Do not import or instantiate `AsyncOpenAI`. AC6, AC7.
2. **Real-mode path.** Local-import `from openai import AsyncOpenAI`
   inside the function so that the module-level import does not run when
   mock mode is active and there is no SDK to load. (`openai` is already
   in `pyproject.toml` so import is always available; the local import is
   to make AC7 — "client is not instantiated" — trivially testable.)
3. Construct the client:

   ```python
   client = AsyncOpenAI(
       api_key=settings.openai_api_key,
       timeout=settings.openai_request_timeout_seconds,
   )
   ```

   Per the OpenAI Python SDK, `timeout` on the client applies per request.
   AC5.
4. Call structured-output parse:

   ```python
   completion = await client.beta.chat.completions.parse(
       model=settings.openai_model_transform,
       temperature=settings.openai_temperature_transform,
       response_format=SatiricalPair,
       messages=[
           {"role": "system", "content": _SYSTEM_PROMPT},
           {"role": "user",   "content": _user_prompt(original_title, original_description)},
       ],
   )
   ```

   AC1, AC2, AC4. The `parse` helper raises on JSON-decode error and on
   schema-mismatch (`pydantic.ValidationError`) — both are surfaced to the
   caller.
5. Refusal handling. If `completion.choices[0].message.refusal` is non-None,
   or `completion.choices[0].message.parsed is None`, raise `ValueError`.
   This funnels into the worker's failure path (AC9).
6. Return `completion.choices[0].message.parsed`.

`_SYSTEM_PROMPT` and `_user_prompt(...)` are private module-level helpers.
The system prompt asks for a satirical / absurd headline and one-paragraph
description derived from the input, returned in the JSON shape the
`response_format` enforces. **Prompt content is intentionally omitted from
this dev doc** — keep it short, free of PII, and self-contained.

### Step 3 — `backend/app/workers/transform.py`

Replace the body of `transform_article` with the structure below. The
public signature, `WorkerSettings` block, and the rollback-then-delete-then-
commit pattern are unchanged.

1. `log.info("worker.transform.start article_id=%d", article_id)`.
2. Open `async with AsyncSessionLocal() as session:`.
3. `fake = await session.get(ArticleFake, article_id)`. If `None`: log
   `worker.transform.skip.missing` at `INFO`; return.
4. **AC8 idempotency check.** If `fake.transform_status == "completed"`:
   log `worker.transform.skip.completed` at `INFO`; return. Do **not** call
   OpenAI; do **not** modify the row.
5. `article = await session.get(Article, article_id)`. If `None`
   (defensive — see spec resolved open question): log
   `worker.transform.skip.no_article` at `INFO`; return without deleting
   the fake row.
6. `try:` block:
   - `pair = await openai_transform.generate_satirical(article.title, article.description)`.
   - Assign:

     ```python
     fake.title = pair.title
     fake.description = pair.description
     fake.model = settings.openai_model_transform
     fake.temperature = settings.openai_temperature_transform
     fake.transform_status = "completed"
     ```

   - `await session.commit()`.
   - `log.info("worker.transform.done article_id=%d model=%s", article_id, settings.openai_model_transform)`.
7. `except Exception as exc:` block (catches timeout, OpenAI API error,
   `json.JSONDecodeError`, `pydantic.ValidationError`, refusal `ValueError`,
   etc.):
   - `await session.rollback()`.
   - `await session.execute(sa.delete(ArticleFake).where(ArticleFake.article_id == article_id))`.
   - `await session.commit()`.
   - `log.error("worker.transform.failed article_id=%d exc_type=%s", article_id, type(exc).__name__)`.
   - **Do not re-raise.** AC9(d). **Do not pass `exc_info=True`** — see
     AC14 reasoning under Logging shape above.
   - No retry — `max_tries=1` is unchanged, so the job ends here. AC9(e).

Remove the module-level `MOCK_TITLE` / `MOCK_DESCRIPTION` constants from
this file (they live in `services/openai_transform.py` now).

### Step 4 — `.env.example`

- Add a new line:
  `OPENAI_REQUEST_TIMEOUT_SECONDS=30  # Per-request timeout for the OpenAI client (seconds).`
- **Do not modify the existing `OPENAI_MOCK_MODE` line.** Per user
  direction during dev planning, the called-out pre-existing drift in
  `.env.example` is intentionally left untouched in this task. Spec AC12
  is still satisfied because the active value in `.env.example` is
  explicitly the operator's choice ("not constrained by this spec") and
  the `Settings` default of `false` (AC11) is authoritative when the env
  var is unset.

### Step 5 — `backend/tests/test_config.py`

Add two assertions:

- `Settings(...).openai_request_timeout_seconds == 30` when env var unset.
- `Settings(...).openai_mock_mode is False` when env var unset.

Reuse the file's existing `_with_clean_env` helper if present; otherwise
follow the file's existing pattern of pop-env, instantiate `Settings`,
assert.

### Step 6 — `backend/tests/unit/test_openai_transform.py` (new)

See "Unit Tests Required" below.

### Step 7 — `backend/tests/unit/test_transform_worker.py`

The existing happy-path tests
(`test_transform_article_sets_completed_status_and_fills_mock_content`,
`test_transform_article_completed_row_model_equals_settings_openai_model_transform`,
`test_transform_article_completed_row_temperature_equals_settings_openai_temperature_transform`)
implicitly assume the static mock write. Under this task that branch only
runs when `OPENAI_MOCK_MODE=true`. Two options:

- **(preferred)** Patch `app.workers.transform.openai_transform.generate_satirical`
  to an `AsyncMock(return_value=SatiricalPair(title=..., description=...))`
  and keep the assertions on the row mutation. Add an `Article` mock so
  `session.get(Article, ...)` returns a non-None object.
- Update existing imports of `MOCK_TITLE` / `MOCK_DESCRIPTION` to come
  from `app.services.openai_transform`.

The exception-path tests
(`test_transform_article_deletes_fake_row_on_unexpected_exception`,
`test_transform_article_preserves_article_row_when_fake_deleted_on_exception`)
should be retargeted: trigger the failure by making
`generate_satirical.side_effect` raise (instead of having the first
`commit` raise). They keep their original AC mapping (AC9 row-deletion +
articles-row preservation).

Add new tests for AC8 and the new logging shape (see test list).

### Step 8 — Run quality gates

`ruff` (with `select = ["E","F","I","UP"]`) and `black` on every modified
file. Per AC15.

---

## Unit Tests Required

All tests mock I/O. No network calls (AC17). `AsyncSessionLocal` is patched.
`AsyncOpenAI` is patched (real-call tests) or asserted-not-called
(mock-mode tests). Test functions are named so their name alone maps to
the criterion they cover — QA reads names, not bodies.

### `tests/unit/test_openai_transform.py` — `generate_satirical`

| Test name | Criterion |
|-----------|-----------|
| `test_generate_satirical_calls_openai_once_with_original_title_and_description` | AC1 |
| `test_generate_satirical_returns_response_title_and_description_on_success` | AC2 / AC3 (structural) |
| `test_generate_satirical_returned_title_and_description_are_non_empty_and_distinct_from_originals_and_mocks` | AC3 |
| `test_generate_satirical_uses_structured_output_response_format` | AC4 |
| `test_generate_satirical_passes_request_timeout_setting_to_openai_client` | AC5 |
| `test_generate_satirical_uses_settings_model_and_temperature` | AC2 (model / temperature wiring) |
| `test_generate_satirical_mock_mode_returns_canonical_pair` | AC6 |
| `test_generate_satirical_mock_mode_does_not_instantiate_openai_client` | AC7 |
| `test_generate_satirical_mock_mode_makes_no_network_request` | AC7 |
| `test_generate_satirical_mock_mode_works_with_placeholder_api_key` | AC7 |
| `test_generate_satirical_propagates_timeout_exception` | AC9 (timeout variant) |
| `test_generate_satirical_propagates_api_error_exception` | AC9 (API-error variant) |
| `test_generate_satirical_propagates_malformed_json_exception` | AC9 (JSON-decode variant) |
| `test_generate_satirical_propagates_schema_validation_exception` | AC9 (schema-mismatch variant) |
| `test_generate_satirical_raises_on_refusal_response` | AC9 (refusal funneled to failure path) |

### `tests/unit/test_transform_worker.py` — `transform_article`

Existing tests retained (with the retargeting described in Step 7):

| Test name | Criterion |
|-----------|-----------|
| `test_transform_article_sets_completed_status_and_fills_mock_content` | AC2 (row mutation on success) — patched to use mock-mode service return |
| `test_transform_article_completed_row_model_equals_settings_openai_model_transform` | AC2 (model field) |
| `test_transform_article_completed_row_temperature_equals_settings_openai_temperature_transform` | AC2 (temperature field) |
| `test_transform_article_skips_nonexistent_article_id_without_raising` | preserved (fake row absent — defensive) |
| `test_transform_article_skips_nonexistent_article_id_logs_skip_event` | preserved |
| `test_transform_article_deletes_fake_row_on_unexpected_exception` | AC9(a) |
| `test_transform_article_preserves_article_row_when_fake_deleted_on_exception` | AC9(b) |

New tests:

| Test name | Criterion |
|-----------|-----------|
| `test_transform_article_completed_row_skips_openai_call` | AC8 |
| `test_transform_article_completed_row_does_not_modify_row` | AC8 |
| `test_transform_article_completed_row_logs_skip_event` | AC8 |
| `test_transform_article_passes_original_article_title_and_description_to_service` | AC1 |
| `test_transform_article_writes_service_response_to_fake_row` | AC2 / AC3 |
| `test_transform_article_failure_emits_one_error_log_with_article_id` | AC9(c) |
| `test_transform_article_failure_does_not_propagate_exception` | AC9(d) |
| `test_transform_article_failure_log_does_not_contain_prompt_response_or_api_key` | AC14 |
| `test_transform_article_success_log_does_not_contain_prompt_response_or_api_key` | AC14 |
| `test_worker_settings_max_tries_is_one` | AC13 |
| `test_worker_settings_functions_contains_transform_article` | AC13 |

### `tests/test_config.py` — `Settings`

| Test name | Criterion |
|-----------|-----------|
| `test_settings_openai_request_timeout_seconds_defaults_to_30` | AC10 |
| `test_settings_openai_request_timeout_seconds_rejects_zero_or_negative` | AC10 (`gt=0`) |
| `test_settings_openai_mock_mode_defaults_to_false` | AC11 |

### `.env.example` documentation — verified by existing convention

AC12 is verified manually during code review (and could be backed by a
trivial test that reads `.env.example` and asserts both keys appear);
include `test_env_example_documents_openai_request_timeout_seconds` and
`test_env_example_documents_openai_mock_mode` in `tests/test_config.py`
that grep the file for the two key names.

---

## Definition of Done

Derived 1-to-1 from the spec's acceptance criteria.

- [ ] AC1 — Real-mode call passes original `title` + `description` to OpenAI exactly once.
- [ ] AC2 — Success writes `title`, `description`, `model`
  (= `settings.openai_model_transform`), `temperature`
  (= `settings.openai_temperature_transform`), and
  `transform_status='completed'` to the row.
- [ ] AC3 — Success values are non-empty and structurally distinct from
  the originals and from the mock pair.
- [ ] AC4 — Real-mode call uses a structured-output (JSON-schema) request
  with two required fields.
- [ ] AC5 — Client honours `settings.openai_request_timeout_seconds`
  (default 30).
- [ ] AC6 — Mock mode writes the canonical mock pair on every call and
  sets `transform_status='completed'`; `model` and `temperature` still
  populated from settings.
- [ ] AC7 — Mock mode does not instantiate `AsyncOpenAI` and makes no
  network request, even with a placeholder `OPENAI_API_KEY`.
- [ ] AC8 — Already-`completed` rows: no OpenAI call, no row mutation,
  one skip log line.
- [ ] AC9 — All failure variants delete the fake row, preserve the
  article row, emit one `ERROR` log line, do not propagate, do not retry.
- [ ] AC10 — `OPENAI_REQUEST_TIMEOUT_SECONDS` is a `Settings` field with
  a positive integer default of `30`.
- [ ] AC11 — `OPENAI_MOCK_MODE` is a `Settings` boolean field defaulting
  to `false`.
- [ ] AC12 — `.env.example` documents `OPENAI_REQUEST_TIMEOUT_SECONDS`
  (newly added) and `OPENAI_MOCK_MODE` (existing line, intentionally
  left as-is per user direction). Settings default `false` for
  `OPENAI_MOCK_MODE` remains authoritative when the env var is unset.
- [ ] AC13 — `transform_article` signature unchanged;
  `WorkerSettings.max_tries == 1`.
- [ ] AC14 — No log line contains prompts, response body, or API key.
- [ ] AC15 — `ruff` + `black` pass on touched files.
- [ ] AC16 — All listed unit tests written and passing.
- [ ] AC17 — No test in the suite makes a real outbound OpenAI request.
- [ ] `services/transformer.py`, `main.py`, `routers/scrape.py` are
  unmodified (out-of-scope guard).
- [ ] No schema change; no migration.

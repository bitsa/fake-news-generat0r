# Dev plan — `chat-llm`

## MUST READ FIRST

- [`docs/chat-llm/chat-llm-spec.md`](chat-llm-spec.md) — the contract this
  plan implements (acceptance criteria AC1–AC25).
- [`context.md`](../../context.md) — async-only I/O, Pydantic Settings (no
  `os.environ`), logging rules ("never log full LLM prompts/responses or
  API keys"), "Mock LLM in All Tests".
- [`plans/plan.md`](../../plans/plan.md) — spec-driven workflow: dev writes
  unit tests inline; QA is black-box.

Source files examined while writing this plan:

- [`backend/app/services/openai_transform.py`](../../backend/app/services/openai_transform.py)
  — pattern to mirror (mock kill-switch short-circuit, `AsyncOpenAI`
  instantiation with `timeout`, error logging shape, never logging
  prompt/response/api-key).
- [`backend/app/services/chat.py`](../../backend/app/services/chat.py) —
  history ordering rule (`created_at ASC, id ASC`) used by the GET
  history endpoint; the prompt builder must match this rule (AC8).
- [`backend/app/models.py`](../../backend/app/models.py) — `Article`,
  `ArticleFake`, `ChatMessage` columns; `ArticleFake.transform_status`
  values (`'pending' | 'completed'`); `ChatMessage.is_error` flag.
- [`backend/app/config.py`](../../backend/app/config.py) — current
  Settings; in particular `openai_model_chat`,
  `openai_temperature_chat`, `openai_request_timeout_seconds`,
  `openai_api_key`, `openai_mock_mode` (the latter is the
  *transform*-side kill-switch and is **not** reused here).
- [`backend/app/routers/chat.py`](../../backend/app/routers/chat.py) —
  current router only mounts `GET /api/articles/{article_id}/chat`; the
  POST endpoint is delivered by `chat-stream-skeleton` (Task 1).
- [`backend/app/exceptions.py`](../../backend/app/exceptions.py) —
  `AppError` hierarchy. `chat-llm` does not introduce new exception
  classes; real-LLM failures are caught at the streaming-service boundary
  and never bubble out of the response.
- [`backend/tests/unit/test_openai_transform.py`](../../backend/tests/unit/test_openai_transform.py)
  — reference for SDK-mocking style (`patch("openai.AsyncOpenAI", cls)`)
  and failure-variant coverage.
- [`.env.example`](../../.env.example) — line style (`KEY=value  # one-line description`).

## Files to touch / create

Create:

- `backend/app/services/chat_llm.py` — prompt builder, real-LLM streaming
  iterator, dispatcher used by the streaming endpoint, public sentinel
  constant.
- `backend/tests/unit/test_chat_llm.py` — unit tests for every functional
  / configuration / safety acceptance criterion (see "Unit tests
  required" below).

Modify:

- `backend/app/config.py` — add three Pydantic Settings fields:
  `chat_llm_mock`, `chat_history_window`, `chat_max_output_tokens`.
- `.env.example` — add three documented lines for the new env vars.
- The streaming-endpoint hookup site delivered by Task 1
  (`chat-stream-skeleton`). Task 1 ships the `POST /api/articles/{id}/chat`
  router and a mock-token generator. After Task 1 lands, the call site
  that drives the assistant token stream is repointed at
  `chat_llm.token_stream(...)` so dispatch can branch on
  `settings.chat_llm_mock`. The router's persistence sequence,
  SSE framing, and error handling are **not** changed (AC20). The exact
  module path of the call site is fixed by Task 1; resolve at
  `/start-dev` by reading the merged `chat-stream-skeleton` code.
- `backend/tests/test_config.py` — add three tests covering AC15/AC16/AC17
  default values and three tests covering AC19 `.env.example` documentation.

Do not touch (out of scope per the spec):

- `backend/app/services/openai_transform.py`,
  `backend/app/workers/transform.py`, `backend/app/services/scraper.py`,
  the `chat_messages` schema, Alembic migrations, the `articles` /
  `article_fakes` schemas, the GET history endpoint
  (`backend/app/services/chat.py` and its router mapping), or any
  frontend file.

## Interfaces / contracts to expose

All in `backend/app/services/chat_llm.py`:

```python
SYSTEM_PROMPT: str
STREAM_FAILURE_SENTINEL: str  # "stream failed" — short, ≤ 80 chars, AC22

def build_chat_messages(
    article: Article,
    fake: ArticleFake | None,
    history: list[ChatMessage],
    new_user_message: str,
    *,
    history_window: int,
) -> list[dict[str, str]]: ...

async def token_stream(
    session: AsyncSession,
    article_id: int,
    new_user_message: str,
) -> AsyncIterator[str]: ...
```

Internal helpers (private, prefixed with `_`):

```python
async def _stream_real_llm(
    messages: list[dict[str, str]],
) -> AsyncIterator[str]: ...

def _select_history_for_prompt(
    rows: list[ChatMessage], history_window: int
) -> list[ChatMessage]: ...
```

Settings additions (in `app/config.py`):

```python
chat_llm_mock: bool = True
chat_history_window: int = Field(default=10, gt=0)
chat_max_output_tokens: int = Field(default=512, gt=0)
```

Token contract:

- `token_stream` yields **plain string chunks** — *not* SSE-framed events.
  SSE framing (`data: {"token": "..."}\n\n`, `[DONE]`, error events) is
  Task 1's responsibility and is not duplicated here (AC20).
- On real-LLM failure, `_stream_real_llm` raises the SDK exception
  out of the iterator. `token_stream` does **not** catch it — it
  propagates to Task 1's streaming-service layer, which already owns
  the (a) sentinel-row insert, (b) error event emission, (c) stream
  close, (d) one-line error log per the locked Task 1 contract. To
  guarantee the sentinel string is byte-for-byte identical between
  the SSE error event and the persisted assistant row's `content`,
  Task 1's streaming service is updated (if it does not already) to
  reuse `chat_llm.STREAM_FAILURE_SENTINEL` for both. See "Open
  questions" below.
- Empty / whitespace-only `delta.content` chunks are skipped (not
  yielded) per AC3; non-empty ones are yielded verbatim. Concatenation
  of all yielded chunks equals the assistant row's persisted `content`
  on success (AC4).

Settings reuse (AC18):

- Real-LLM call uses `settings.openai_model_chat`,
  `settings.openai_temperature_chat`,
  `settings.openai_request_timeout_seconds`,
  `settings.openai_api_key`. **No** parallel `chat_model` /
  `chat_temperature` fields are introduced.

## Implementation plan

1. **Settings (AC15–AC17, AC19).**
   - In `app/config.py`, append the three fields after the existing
     `openai_*` block. Use `Field(default=10, gt=0)` and
     `Field(default=512, gt=0)` for the integer fields so Pydantic
     validation rejects non-positive values at startup. Keep
     `chat_llm_mock` as a plain `bool = True` (CI/dev-friendly default,
     mirrors `OPENAI_MOCK_MODE` style but with opposite default — see
     OQ context: chat path defaults to mock so dev/CI work without an
     API key).
   - In `.env.example`, append three lines in the existing
     `KEY=value  # description` style:

     ```text
     CHAT_LLM_MOCK=true  # If true, chat path uses the deterministic mock generator (no OpenAI call).
     CHAT_HISTORY_WINDOW=10  # Max prior chat_messages rows injected into each prompt (oldest-first).
     CHAT_MAX_OUTPUT_TOKENS=512  # Per-request `max_tokens` cap for the chat completion.
     ```

   - Do not modify any pre-existing line in `.env.example` (AC19).

2. **Module skeleton: `app/services/chat_llm.py`.**
   - Module-level `log = logging.getLogger(__name__)`.
   - `SYSTEM_PROMPT` is a module-level constant — a fixed string that
     instructs the model to act as a context-aware assistant for the
     given article. The text is stable across runs for the same input
     (no timestamps, randomness, environment data) — AC6.
   - `STREAM_FAILURE_SENTINEL = "stream failed"` (≤ 80 chars, no
     provider details — AC22). Exported so Task 1's streaming service
     uses the same string for the SSE `error` payload and the
     `is_error=true` row's `content`.

3. **Prompt builder: `build_chat_messages(...)` (AC6–AC10).**
   - Step 1 — context preamble. Compose a single system message whose
     body contains:
     - The `SYSTEM_PROMPT` text.
     - Original article `title` and `description` (always included).
     - If `fake is not None and fake.transform_status == "completed"`
       and `fake.title` and `fake.description` are non-null, append
       the satirical `title` / `description` to the same system
       message (AC7). Otherwise omit the satirical block; do not
       raise (AC7 explicitly: pending / missing fake → request still
       succeeds).
   - Step 2 — history slice. Receive `history` already filtered by
     `article_id`. Internally call `_select_history_for_prompt(rows,
     history_window)`:
     - Filter out any row with `is_error=True` (AC8 — error rows are
       breadcrumbs, not real assistant turns). Filter out any row
       whose `role` is not `'user'` or `'assistant'` (defensive; the
       check constraint already enforces this).
     - Sort the remaining rows ascending by `(created_at, id)` —
       same rule as `services/chat.py`'s GET history (AC8).
     - Take the **last** `history_window` of them, preserving order
       (AC9).
     - Return the resulting list.
   - Step 3 — build the message list:
     1. The system message (step 1).
     2. For each row in the history slice, append
        `{"role": row.role, "content": row.content}` (AC6 ordering:
        oldest-first).
     3. Append exactly one final `{"role": "user", "content":
        new_user_message}` message (AC6, AC10).
   - **AC10 invariant.** The caller (Task 1's streaming service) is
     responsible for committing the user row **before** invoking
     `token_stream`. The history fetch executed inside `token_stream`
     therefore returns a list that already contains the just-inserted
     user row. `_select_history_for_prompt` must drop that newest
     `role='user'` row to avoid double-counting it; the new user
     message is appended exactly once via step 3.

     Concretely, after slicing the most-recent `history_window` rows,
     pop the trailing row if it is the `role='user'` row whose
     `content == new_user_message` and whose `id` is the maximum among
     the article's rows. Implement this as: load `history_window + 1`
     rows ordered DESC by `(created_at, id)`, drop the leading one if
     it matches the new user message, reverse to ASC. This guarantees
     AC10 even when the same user message is sent twice in a row.

4. **Real streaming: `_stream_real_llm(messages)` (AC1–AC4).**
   - `from openai import AsyncOpenAI`.
   - Instantiate
     `AsyncOpenAI(api_key=settings.openai_api_key,
     timeout=settings.openai_request_timeout_seconds)` once per call
     (mirrors `openai_transform.py`).
   - Open the stream:
     `stream = await
     client.chat.completions.create(model=settings.openai_model_chat,
     messages=messages,
     temperature=settings.openai_temperature_chat,
     max_tokens=settings.chat_max_output_tokens, stream=True)`
     — exactly one such call per request (AC1, AC2).
     **Not** `client.beta.chat.completions.parse` (AC2, OQ-4).
   - `async for chunk in stream:`
     - `delta = chunk.choices[0].delta` (defensive: skip if `choices`
       is empty or `delta` is `None`).
     - `text = getattr(delta, "content", None) or ""`
     - If `text.strip()`: `yield text` (AC3 — non-empty deltas only;
       empty / whitespace-only ones are coalesced/skipped, but no
       chunk's text is dropped from the assistant content because the
       caller concatenates yielded chunks).
   - Do **not** catch SDK exceptions inside this generator. Let
     `openai.APIError`, `TimeoutError`, connection errors, and any
     other exception raised during the SDK call or during iteration
     bubble up. The streaming service in Task 1 owns the failure
     contract.
   - Logging: do **not** log the prompt or any chunk text. After the
     stream is exhausted, optionally log one info line with
     `model=settings.openai_model_chat`, `article_id` (passed via
     `token_stream`), and a duration / token-count derived from
     internal counters — never the content. Skip the line entirely if
     it would risk leaking content; the spec does not require it
     (AC21). Recommendation: emit a single `info` log line in
     `token_stream` (after stream completes), not in
     `_stream_real_llm`, so `article_id` is in scope.

5. **Dispatcher: `token_stream(...)` (AC11, AC12).**
   - This is the only entrypoint Task 1's streaming service calls.
   - Step A — fetch article + fake + history in one async block:

     ```python
     article = await session.get(Article, article_id)
     # article presence is already validated by Task 1 (AC3 of Task 1
     # spec); article cannot be None here. If it ever is, raise
     # NotFoundError so the failure contract triggers cleanly.
     fake = (await session.execute(
         select(ArticleFake).where(ArticleFake.article_id == article_id)
     )).scalar_one_or_none()
     rows_desc = (await session.execute(
         select(ChatMessage)
         .where(ChatMessage.article_id == article_id)
         .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
         .limit(settings.chat_history_window + 1)
     )).scalars().all()
     ```

     Then invert to ascending order in Python (preserving AC8 ordering)
     and apply the AC10 dedup pop described above.
   - Step B — build messages via `build_chat_messages(...)`.
   - Step C — branch:
     - **If `settings.chat_llm_mock` is True**: import and delegate to
       Task 1's existing mock generator (the module Task 1 introduces
       — likely `app.services.chat_mock` based on the spec language
       AC11). Re-emit the mock generator's yielded token strings
       verbatim. Do not import `openai` and do not instantiate
       `AsyncOpenAI` in this branch (AC12).
     - **If `settings.chat_llm_mock` is False**: delegate to
       `_stream_real_llm(messages)` and yield each chunk as it arrives.
   - Do not catch exceptions here; mock-mode raises behave the same
     as real-mode raises (Task 1's force-error hook in mock mode is
     unaffected).

6. **Hookup at Task 1's streaming-service call site (AC11, AC20).**
   - When `chat-stream-skeleton` lands, locate the function in Task 1's
     code that currently calls the mock generator directly (likely a
     service method invoked from
     `backend/app/routers/chat.py`'s POST handler). Replace that call
     with `chat_llm.token_stream(session, article_id,
     new_user_message)`.
   - Confirm Task 1's error-event payload uses
     `chat_llm.STREAM_FAILURE_SENTINEL` (or unify to it) so AC22 holds
     and the SSE error string matches the persisted row's `content`
     byte-for-byte. If Task 1 chose a different sentinel that already
     satisfies AC22, the `chat_llm` module imports / re-exports it
     instead — this is a 1-line decision, made at `/start-dev` time
     against the merged Task 1 code.
   - Do **not** change the persistence sequence, SSE framing, status
     codes, or response headers from Task 1 (AC20).

7. **Tests** (see "Unit tests required" below). Mock the OpenAI SDK in
   the same shape as
   [`backend/tests/unit/test_openai_transform.py`](../../backend/tests/unit/test_openai_transform.py)
   uses (`patch("openai.AsyncOpenAI", cls)`); supply an async-iterator
   fake stream object that yields chunk objects whose
   `choices[0].delta.content` is the per-chunk text (or `None` /
   whitespace for the AC3 skip cases).

8. **Quality gates (AC23, AC25).**
   - Run `ruff check` and `black --check` against
     `backend/app/services/chat_llm.py`,
     `backend/app/config.py`, and any Task 1 file touched at the
     hookup site.
   - Confirm no test in `backend/tests/` makes a real outbound OpenAI
     request: every code path that touches `AsyncOpenAI` is wrapped
     in `patch("openai.AsyncOpenAI", ...)`, and the mock-mode tests
     additionally assert the SDK class is *not* called (AC12).

## Unit tests required

All in `backend/tests/unit/test_chat_llm.py` unless otherwise noted.
Each test name maps unambiguously to one acceptance criterion so QA can
audit coverage by name alone.

Real-call path:

- `test_real_call_invokes_chat_completions_create_exactly_once` — AC1.
- `test_real_call_uses_openai_model_chat_setting` — AC2 / AC18.
- `test_real_call_uses_openai_temperature_chat_setting` — AC2 / AC18.
- `test_real_call_passes_chat_max_output_tokens_as_max_tokens` — AC2.
- `test_real_call_passes_openai_request_timeout_seconds_to_client` — AC2.
- `test_real_call_uses_chat_completions_create_with_stream_true_not_beta_parse`
  — AC2 / OQ-4.
- `test_real_stream_emits_each_non_empty_delta_as_token_string` — AC3.
- `test_real_stream_skips_empty_and_whitespace_only_deltas` — AC3.
- `test_real_stream_concatenated_yielded_chunks_equal_full_assistant_text`
  — AC3 / AC4 (token_stream contract; the integration with
  Task 1's persistence is verified by Task 1's tests + a thin
  hookup test below).

Persistence ordering (verified at the streaming-service boundary
exposed by Task 1; tests live alongside the hookup):

- `test_streaming_endpoint_commits_user_row_before_first_token_event_real_path`
  — AC5 (router-level test mocking `_stream_real_llm` to yield two
  tokens; assert DB row exists at the time the first SSE token event
  is observed).
- `test_streaming_endpoint_commits_assistant_row_before_done_terminator_real_path`
  — AC4 (router-level test asserting the assistant row's `content`
  is the concatenation of yielded chunks and the row exists *before*
  `data: [DONE]\n\n`).

Prompt construction:

- `test_prompt_builder_emits_system_then_history_then_final_user_message_in_order`
  — AC6.
- `test_prompt_system_message_is_stable_across_runs_for_same_input` — AC6.
- `test_prompt_builder_includes_original_article_title_and_description_in_system_message`
  — AC7.
- `test_prompt_builder_includes_satirical_title_and_description_when_fake_completed`
  — AC7.
- `test_prompt_builder_includes_only_original_when_fake_is_none` — AC7.
- `test_prompt_builder_includes_only_original_when_fake_status_is_pending`
  — AC7.
- `test_prompt_builder_orders_history_chronologically_oldest_first_by_created_at_then_id`
  — AC8.
- `test_prompt_builder_excludes_assistant_rows_with_is_error_true_from_history`
  — AC8.
- `test_prompt_builder_caps_history_at_chat_history_window_most_recent`
  — AC9.
- `test_prompt_builder_does_not_double_count_new_user_message_when_already_in_history`
  — AC10.

Mock-mode path:

- `test_mock_mode_dispatches_to_chat_mock_generator_token_stream` — AC11.
- `test_mock_mode_does_not_instantiate_async_openai_client` — AC12.
- `test_mock_mode_makes_no_call_to_chat_completions_create` — AC12.
- `test_mock_mode_works_with_placeholder_openai_api_key` — AC12.

Failure path (real mode):

- `test_real_path_raises_on_timeout_so_streaming_service_can_persist_sentinel`
  — AC13(a) / AC14 cause: `_stream_real_llm` propagates `TimeoutError`.
- `test_real_path_raises_on_openai_api_error` — AC13 cause:
  propagates an APIError-shaped exception (use a custom Exception
  subclass; mocks don't need real SDK error classes).
- `test_real_path_raises_on_connection_error` — AC13 cause:
  propagates a `ConnectionError`.
- `test_real_path_raises_on_mid_stream_exception_after_partial_tokens`
  — AC13 / AC14: stream yields N chunks then `__anext__` raises;
  generator propagates after the partial yields.
- `test_streaming_endpoint_persists_assistant_row_with_sentinel_content_on_real_failure`
  — AC13(a) / AC14 (router-level test, mocked `_stream_real_llm`).
- `test_streaming_endpoint_emits_single_error_event_with_sentinel_on_real_failure`
  — AC13(b).
- `test_streaming_endpoint_does_not_emit_done_after_real_failure` — AC13(c).
- `test_streaming_endpoint_returns_200_and_does_not_raise_on_real_failure`
  — AC13(d).
- `test_streaming_endpoint_logs_one_error_with_article_id_and_exc_type_name_on_real_failure`
  — AC13(e).
- `test_real_failure_after_partial_tokens_persisted_assistant_content_is_sentinel_only`
  — AC14.

Configuration / surface (in `backend/tests/test_config.py`):

- `test_settings_chat_llm_mock_defaults_to_true` — AC15.
- `test_settings_chat_history_window_defaults_to_10` — AC16.
- `test_settings_chat_history_window_rejects_zero_or_negative` — AC16.
- `test_settings_chat_max_output_tokens_defaults_to_512` — AC17.
- `test_settings_chat_max_output_tokens_rejects_zero_or_negative` — AC17.
- `test_chat_llm_module_does_not_introduce_chat_model_or_chat_temperature_settings_fields`
  — AC18 (assert `Settings` has `openai_model_chat` and
  `openai_temperature_chat` and does *not* have `chat_model` or
  `chat_temperature` attributes).
- `test_env_example_documents_chat_llm_mock` — AC19.
- `test_env_example_documents_chat_history_window` — AC19.
- `test_env_example_documents_chat_max_output_tokens` — AC19.
- `test_env_example_pre_existing_openai_keys_are_unchanged_by_chat_llm_task`
  — AC19 (assert the line text for `OPENAI_API_KEY`,
  `OPENAI_REQUEST_TIMEOUT_SECONDS`, `OPENAI_MOCK_MODE`,
  `OPENAI_MODEL_CHAT`, `OPENAI_TEMPERATURE_CHAT` is byte-identical
  to the pre-existing fixture).

Public-router contract non-regression:

- `test_public_router_post_chat_url_status_codes_and_sse_format_unchanged_from_task_1`
  — AC20 (mock-mode end-to-end smoke that exercises the same URL,
  body shape, 200 / 404 / 422 paths, and event framing Task 1
  already covers; passes by construction once the hookup is wired
  through `chat_llm.token_stream` without changing the router).

Logging / safety:

- `test_no_log_record_emitted_during_real_streaming_contains_user_message_or_prompt_or_response_or_api_key`
  — AC21 (caplog at DEBUG; assert no record's `getMessage()`
  contains the system prompt fragment, the user message, the fake
  assistant chunks, or the `openai_api_key` value).
- `test_stream_failure_sentinel_is_short_human_readable_and_does_not_contain_provider_details`
  — AC22 (assert `len(STREAM_FAILURE_SENTINEL) ≤ 80`, that it is
  ASCII-printable, and that it does not contain "OpenAI", "API",
  "401", "429", or any traceback-like substring).

Quality gates (CI-driven, no inline test code):

- AC23 — `ruff check` and `black --check` pass on every touched file.
- AC25 — sweep: a project-level test confirms no test in
  `backend/tests/**` instantiates `openai.AsyncOpenAI` without
  patching it (already enforced by the pre-existing pattern; no
  new test required).

## Definition of done

Tracks the spec's acceptance criteria 1-to-1.

- [ ] AC1 — Real-mode `POST /api/articles/{id}/chat` invokes
      `client.chat.completions.create(..., stream=True)` exactly once
      per request.
- [ ] AC2 — Call uses `openai_model_chat`, `openai_temperature_chat`,
      `chat_max_output_tokens` (as `max_tokens`), and
      `openai_request_timeout_seconds` (on the client). Surface is
      `chat.completions.create`, **not** `beta.chat.completions.parse`.
- [ ] AC3 — Each non-empty `delta.content` chunk is yielded as one SSE
      `data: {"token": "..."}\n\n` event; empty / whitespace-only
      deltas are skipped; no chunk text is dropped from the persisted
      assistant content.
- [ ] AC4 — Assistant row inserted with concatenation of all yielded
      chunks and committed before `data: [DONE]\n\n`.
- [ ] AC5 — User row inserted before any token event is emitted.
- [ ] AC6 — Message list = system, then history (oldest-first), then
      one new `user` message; system text is stable across runs for
      the same input.
- [ ] AC7 — System / preamble includes original `title` +
      `description` always; satirical `title` + `description` only
      when `transform_status='completed'` and fake fields non-null.
- [ ] AC8 — History sorted by `(created_at ASC, id ASC)`; rows with
      `is_error=true` excluded.
- [ ] AC9 — At most `chat_history_window` history rows included.
- [ ] AC10 — New user message appears exactly once (final `user`
      message), never duplicated by the history slice.
- [ ] AC11 — Mock mode dispatches through Task 1's `chat_mock`
      generator with no router changes.
- [ ] AC12 — Mock mode never instantiates `AsyncOpenAI` and works
      with a placeholder API key.
- [ ] AC13 — Failure path: sentinel-only assistant row, single error
      SSE event, no `[DONE]`, exception not propagated, one ERROR
      log identifying `article_id` + exc-type-name.
- [ ] AC14 — On post-partial-token failure, persisted assistant
      `content` is the sentinel string only.
- [ ] AC15 — `chat_llm_mock: bool = True` Pydantic Settings field;
      env vars read only via Settings (`context.md` standard).
- [ ] AC16 — `chat_history_window: int` defaults to `10`, `gt=0`.
- [ ] AC17 — `chat_max_output_tokens: int` defaults to `512`, `gt=0`.
- [ ] AC18 — Reuses `openai_model_chat` / `openai_temperature_chat`;
      no parallel `chat_model` / `chat_temperature` fields.
- [ ] AC19 — `.env.example` documents `CHAT_LLM_MOCK`,
      `CHAT_HISTORY_WINDOW`, `CHAT_MAX_OUTPUT_TOKENS`; pre-existing
      OpenAI keys unchanged.
- [ ] AC20 — Public router contract byte-identical to Task 1.
- [ ] AC21 — No log line at any level contains prompt body,
      message content, response chunks, or `OPENAI_API_KEY`.
- [ ] AC22 — Sentinel is ≤ 80 chars, sanitised, no provider details.
- [ ] AC23 — `ruff` and `black` pass on touched backend files.
- [ ] AC24 — All unit tests above pass.
- [ ] AC25 — No test makes a real outbound OpenAI request.
- [ ] Tracker updated to `in_qa` after dev completes (per
      `plans/plan.md` workflow).

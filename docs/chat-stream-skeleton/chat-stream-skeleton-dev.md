# Dev — `chat-stream-skeleton`

## MUST READ FIRST

Before touching any code, read in full:

- [`docs/chat-stream-skeleton/chat-stream-skeleton-spec.md`](chat-stream-skeleton-spec.md) — source of truth (WHAT and WHY).
- [`context.md`](../../context.md) — decisions and standards. The
  relevant ones for this task: SSE over WebSockets, async-only I/O,
  `Pydantic Settings` for all config, `AppError` subclasses for domain
  errors, "no log line contains the user message body or LLM payload",
  "LLM calls always mocked" in tests.
- [`plans/plan.md`](../../plans/plan.md) — workflow and doc structure.

Source files to skim before starting:

- [`backend/app/routers/chat.py`](../../backend/app/routers/chat.py) — existing
  GET history endpoint. New POST mounts here.
- [`backend/app/services/chat.py`](../../backend/app/services/chat.py) —
  existing `get_chat_history` service; pattern for article-existence checks.
- [`backend/app/schemas/chat.py`](../../backend/app/schemas/chat.py) —
  existing `ChatMessageOut` / `ChatHistoryResponse`.
- [`backend/app/models.py`](../../backend/app/models.py) — `ChatMessage`,
  `Article` ORM models.
- [`backend/app/config.py`](../../backend/app/config.py) — Pydantic
  `Settings` to extend.
- [`backend/app/exceptions.py`](../../backend/app/exceptions.py) —
  `NotFoundError` (404). Reused; no new exception class.
- [`backend/app/main.py`](../../backend/app/main.py) — `AppError`
  exception handler reused for 404 path.
- [`backend/app/db.py`](../../backend/app/db.py) — `AsyncSessionLocal`
  pattern used inside the streaming generator.
- [`backend/tests/routers/test_chat.py`](../../backend/tests/routers/test_chat.py)
  and [`backend/tests/conftest.py`](../../backend/tests/conftest.py) —
  test harness style (httpx ASGI, `chat_client` fixture).

## Files to touch / create

Create:

- `backend/app/services/chat_generator.py` — mock token generator and
  the `force-error` sentinel logic. Isolated module so Task 2
  (`chat-llm`) can swap in a real-LLM async iterator without touching
  the router or service.
- `backend/tests/unit/test_chat_generator.py` — unit tests for the
  generator (deterministic output shape, error-hook behaviour, no
  OpenAI SDK import / network call).

Modify:

- `backend/app/config.py` — add `chat_message_max_chars` and
  `chat_mock_force_error_token` Pydantic fields (AC18, AC19).
- `backend/app/schemas/chat.py` — add `ChatPostRequest` Pydantic body
  schema with validation per AC2 / AC18.
- `backend/app/services/chat.py` — add `post_chat_stream` orchestration
  function (validates article, persists user row, returns the
  `StreamingResponse`).
- `backend/app/routers/chat.py` — register
  `POST /api/articles/{article_id}/chat` calling the service.
- `backend/tests/routers/test_chat.py` — add POST endpoint tests
  (status codes, headers, SSE wire format, persistence side-effects via
  spies / fakes, error-path framing, GET-history non-regression).
- `backend/tests/unit/test_chat_service.py` — extend with tests for
  `post_chat_stream` orchestration (user-row commit ordering,
  assistant-row content equals concatenated tokens, error-path row
  flagging and sentinel parity).

Do NOT touch:

- `backend/app/models.py` and `backend/migrations/` — schema is reused
  as-is. `chat_messages.request_id` stays `NULL` (out-of-scope per spec).
- `backend/app/routers/articles.py`, `backend/app/services/articles.py`,
  scrape / transform pipeline — non-regression only (AC21).

## Interfaces / contracts to expose

### Configuration (`backend/app/config.py`)

Two new fields on `Settings`:

```python
chat_message_max_chars: int = Field(default=512, gt=0)
chat_mock_force_error_token: str | None = None
```

### Request schema (`backend/app/schemas/chat.py`)

`ChatPostRequest` is the JSON body for `POST .../chat`. The maximum
length is enforced inside a Pydantic field validator that reads
`settings.chat_message_max_chars` at validation time so AC18 is honored
even when settings are overridden in tests (avoids freezing the bound
at module-import time).

```python
class ChatPostRequest(BaseModel):
    message: str

    # validator semantics (AC2 + AC18):
    #  - reject missing field (Pydantic default)
    #  - reject non-string (Pydantic default — strict on `str`)
    #  - reject empty string
    #  - reject whitespace-only string (`.strip() == ""`)
    #  - reject `len(value) > settings.chat_message_max_chars`
    #  - DO NOT trim or otherwise transform the value; persist verbatim
```

Validation failure surfaces as FastAPI's default HTTP 422 (no custom
handler needed; matches AC2's "rejected with HTTP 422").

### Service layer (`backend/app/services/chat.py`)

New entry point:

```python
async def post_chat_stream(
    session: AsyncSession,
    article_id: int,
    body: ChatPostRequest,
) -> StreamingResponse:
    """
    Validate article exists (404 via NotFoundError on miss).
    Insert + commit the user row (AC8).
    Build and return a StreamingResponse driving the SSE generator.

    Raises NotFoundError when the article is missing — caller (router)
    lets the existing AppError handler turn it into 404.
    """
```

The returned `StreamingResponse` is constructed with:

- `media_type="text/event-stream"` (AC4)
- `headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no",
  "Connection": "keep-alive"}` (AC4)
- An async generator (see below) as content.

The streaming generator runs after the response headers and the user
row are flushed. It opens its **own** `AsyncSessionLocal()` for the
assistant-row insert+commit so its lifetime is independent of the
request-scoped session (which FastAPI closes after the response body
is fully sent — opening a fresh session avoids any race with that
teardown). This mirrors the pattern in `app/main.py` lifespan.

### Generator module (`backend/app/services/chat_generator.py`)

Public surface:

```python
MOCK_REPLY: str  # canonical assistant reply (AC14, deterministic)
ERROR_SENTINEL: str  # short, non-empty, sanitised user-facing error string
                     # used both in the SSE error event and the persisted
                     # assistant row (AC11, AC12)


async def stream_mock_reply(message: str) -> AsyncIterator[str]:
    """
    Yield 10..20 token chunks whose concatenation == MOCK_REPLY.
    Awaits a small (≤100 ms) delay between tokens so streaming is
    observable (AC15).

    If `settings.chat_mock_force_error_token` is non-empty AND `message`
    is exactly equal to it (no strip, no case-fold, no substring),
    the generator raises a domain-specific exception mid-iteration
    (AC17). Zero or more tokens may have been yielded before the raise.

    No OpenAI SDK import inside this function. No outbound HTTP call.
    """
```

`MOCK_REPLY` is a fixed canonical string (e.g.
`"This is a deterministic mock reply for the chat skeleton task."`).
Tokenization is a simple deterministic split that yields between 10
and 20 chunks (e.g. word-plus-trailing-space chunks). The exact text
is an implementation detail; QA only checks that concatenation is
stable across runs and that the chunk count is in `[10, 20]`.

### SSE framing (helper, internal to `services/chat.py`)

Encoding helpers (private; not exported):

```python
def _sse_token(chunk: str) -> bytes:
    return f"data: {json.dumps({'token': chunk}, ensure_ascii=False)}\n\n".encode()


def _sse_done() -> bytes:
    return b"data: [DONE]\n\n"


def _sse_error(message: str) -> bytes:
    return f"data: {json.dumps({'error': message}, ensure_ascii=False)}\n\n".encode()
```

`json.dumps` is used so chunks containing quotes / newlines / non-ASCII
are escaped correctly per SSE rules (AC5).

### Router (`backend/app/routers/chat.py`)

```python
@router.post("/articles/{article_id}/chat")
async def post_chat(
    article_id: int,
    body: ChatPostRequest,
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    return await chat_service.post_chat_stream(session, article_id, body)
```

No `response_model` — the response is `text/event-stream`, not JSON.

## Implementation plan

1. **Settings (AC18, AC19).**
   - Add `chat_message_max_chars: int = Field(default=512, gt=0)` and
     `chat_mock_force_error_token: str | None = None` to
     `app/config.py`.
   - Existing `Settings()` singleton picks them up automatically via
     env vars (`CHAT_MESSAGE_MAX_CHARS`, `CHAT_MOCK_FORCE_ERROR_TOKEN`).

2. **Request schema (AC2).**
   - In `app/schemas/chat.py`, add `ChatPostRequest` with a single
     `message: str` field and a Pydantic field validator that:
     - rejects empty string (`""`),
     - rejects whitespace-only strings (`v.strip() == ""`),
     - rejects strings longer than `settings.chat_message_max_chars`
       (`len(v) > settings.chat_message_max_chars`).
   - Pydantic's strict-`str` typing already handles missing /
     non-string / non-JSON cases as 422 via FastAPI's default
     RequestValidationError handler.

3. **Mock generator (`services/chat_generator.py`, AC14–AC17).**
   - Define `MOCK_REPLY` as a fixed string whose word-plus-space
     tokenization yields between 10 and 20 chunks. Verify count by
     unit test.
   - Define `ERROR_SENTINEL` (e.g. `"chat stream failed"` — keep it
     short and free of exception-class names per AC7 / AC12).
   - Implement `stream_mock_reply(message)` as `async def ... ->
     AsyncIterator[str]`. It checks the force-error sentinel up front
     against `settings.chat_mock_force_error_token` (exact equality,
     non-empty config). If matched, the generator yields one or two
     tokens then raises a sentinel exception (e.g. a private
     `_MockChatError` subclass of `RuntimeError`). Otherwise it
     iterates `MOCK_REPLY` chunks with `await asyncio.sleep(<small>)`
     between them.
   - Read `settings` lazily inside the function (do not capture at
     import time) so test overrides take effect.

4. **Service orchestration (`services/chat.py`, AC3, AC8–AC13).**
   - In `post_chat_stream`:
     1. `await session.scalar(select(Article.id).where(Article.id == article_id))`;
        if `None`, raise `NotFoundError(f"Article {article_id} not found")`
        (AC3).
     2. Insert one `ChatMessage(article_id=..., role="user",
        content=body.message, is_error=False)` row.
     3. `await session.flush(); await session.commit()` BEFORE
        building the response (AC8). The user row must be visible to
        a concurrent `GET .../chat` before the first SSE byte goes
        out.
     4. Build an inner `async def gen():` and return
        `StreamingResponse(gen(), media_type="text/event-stream",
        headers=<AC4 headers>)`.
   - Inside `gen()`:
     1. Open a fresh `AsyncSessionLocal()` context manager for the
        assistant row (separate from the request-scoped `session`).
     2. Initialise `tokens: list[str] = []`.
     3. `try:` — `async for chunk in stream_mock_reply(body.message):`
        - append `chunk` to `tokens`,
        - `yield _sse_token(chunk)` (AC5).
     4. After the iterator exhausts: insert `ChatMessage(...,
        role="assistant", content="".join(tokens), is_error=False)`,
        commit, then `yield _sse_done()` (AC6, AC9). The order is:
        DB commit first, then `[DONE]` event (AC9 says committed
        before stream closes; doing the commit before the terminator
        keeps the contract crisp and matches AC10 expectations under
        an immediate follow-up GET).
     5. `except Exception as exc:` — log
        `"chat.stream.error article_id=%d exc_type=%s"` (no message
        body, no traceback string per AC22 / `context.md` logging
        rules), then insert `ChatMessage(..., role="assistant",
        content=ERROR_SENTINEL, is_error=True)`, commit, and
        `yield _sse_error(ERROR_SENTINEL)` (AC7, AC11, AC12). No
        `[DONE]` is emitted on the error path (AC6).
     6. The generator returns / closes; `StreamingResponse` then
        closes the HTTP stream.
   - Logging surface: one `info` line on entry
     (`"chat.post.begin article_id=%d msg_len=%d"`) and one `info`
     line on normal completion
     (`"chat.post.complete article_id=%d tokens=%d"`); one `error`
     line on the error path (already covered above). No log emits
     `body.message`, `MOCK_REPLY`, or any token (AC22).

5. **Router (AC1).**
   - In `app/routers/chat.py`, register the POST route and have it
     call `chat_service.post_chat_stream`. The existing
     `prefix="/api"` puts it under `/api/articles/{article_id}/chat`
     alongside the GET.

6. **Non-regression sanity (AC20, AC21).**
   - The existing GET endpoint and its router registration are not
     modified — the new POST is appended.
   - Scrape / transform / GET feed code is untouched.

## Unit tests required

Each bullet maps to one acceptance criterion. The test name on the
right is the function name to use in the test file so QA can audit
coverage by name alone (per the workflow doc — black-box QA reads test
names, not bodies).

Endpoint surface:

- AC1 — `POST /api/articles/{article_id}/chat` is mounted under `/api`
  (POST to unprefixed `/articles/{id}/chat` returns 404):
  `test_post_chat_registered_under_api_prefix`
- AC2 — request body validation paths (each is its own test for clean
  failure attribution):
  - `test_post_chat_rejects_missing_message_with_422`
  - `test_post_chat_rejects_non_string_message_with_422`
  - `test_post_chat_rejects_empty_string_message_with_422`
  - `test_post_chat_rejects_whitespace_only_message_with_422`
  - `test_post_chat_rejects_message_longer_than_max_chars_with_422`
  - `test_post_chat_accepts_message_at_exact_max_chars_boundary`
  - `test_post_chat_persists_message_verbatim_including_surrounding_whitespace`
- AC3 — missing article path:
  - `test_post_chat_returns_404_with_detail_for_missing_article`
  - `test_post_chat_inserts_no_rows_on_404_missing_article`
  - `test_post_chat_does_not_open_sse_stream_on_404`
- AC4 — happy-path response shape:
  - `test_post_chat_happy_path_status_200`
  - `test_post_chat_happy_path_content_type_is_event_stream`
  - `test_post_chat_happy_path_sets_cache_control_no_cache_header`
  - `test_post_chat_happy_path_sets_x_accel_buffering_no_header`
  - `test_post_chat_happy_path_sets_connection_keep_alive_header`

SSE wire format:

- AC5 — token event encoding and concatenation:
  - `test_post_chat_each_token_event_is_data_token_json_with_double_newline`
  - `test_post_chat_concatenated_token_chunks_equal_full_assistant_reply`
- AC6 — `[DONE]` terminator on happy path:
  - `test_post_chat_happy_path_emits_exactly_one_done_event_after_last_token`
  - `test_post_chat_error_path_emits_no_done_event`
- AC7 — error event framing:
  - `test_post_chat_error_path_emits_exactly_one_error_event_then_closes`
  - `test_post_chat_error_event_payload_does_not_contain_exception_class_name`

Persistence — happy path:

- AC8 — user row written and committed before the stream opens:
  - `test_post_chat_user_row_committed_before_stream_opens_with_verbatim_content`
- AC9 — assistant row written and committed before stream closes,
  content equals concatenated tokens:
  - `test_post_chat_assistant_row_content_equals_concatenated_token_chunks`
  - `test_post_chat_assistant_row_committed_before_done_event`
- AC10 — GET history reflects the exchange after happy-path POST:
  - `test_get_chat_history_after_happy_post_returns_user_then_assistant_in_order`

Persistence — error path:

- AC11 — exactly one assistant error row written and committed:
  - `test_post_chat_error_path_writes_exactly_one_assistant_row_with_is_error_true`
  - `test_post_chat_error_path_does_not_modify_user_row`
- AC12 — sentinel parity:
  - `test_post_chat_error_sentinel_string_byte_equal_in_sse_and_persisted_row`
  - `test_post_chat_error_sentinel_does_not_contain_traceback_or_class_name`
- AC13 — GET history after error-path POST:
  - `test_get_chat_history_after_error_post_returns_user_false_then_assistant_true`

Mock generator behaviour (in `tests/unit/test_chat_generator.py`):

- AC14 — deterministic, finite, 10..20 token output:
  - `test_stream_mock_reply_yields_between_10_and_20_chunks_inclusive`
  - `test_stream_mock_reply_concatenates_to_canonical_string`
  - `test_stream_mock_reply_is_deterministic_across_calls`
- AC15 — non-zero wall-clock duration (use a small timeout-driven
  bound rather than asserting a specific delay):
  - `test_stream_mock_reply_has_strictly_positive_total_duration`
- AC16 — no OpenAI SDK or network:
  - `test_stream_mock_reply_does_not_import_openai_sdk_module`
  - `test_stream_mock_reply_makes_no_outbound_http_call`
  - `test_post_chat_works_with_placeholder_openai_api_key`

Test hook:

- AC17 — exact-match force-error semantics:
  - `test_stream_mock_reply_raises_when_message_exactly_equals_force_token`
  - `test_stream_mock_reply_does_not_raise_on_substring_match_of_force_token`
  - `test_stream_mock_reply_does_not_raise_on_case_insensitive_match`
  - `test_stream_mock_reply_does_not_raise_on_whitespace_trimmed_match`
  - `test_stream_mock_reply_does_not_raise_when_force_token_is_none_default`

Configuration:

- AC18 — `chat_message_max_chars` default and bound:
  - `test_settings_chat_message_max_chars_default_is_512`
  - already covered for endpoint behaviour by AC2 length tests above.
- AC19 — `chat_mock_force_error_token` default disables error path:
  - `test_settings_chat_mock_force_error_token_default_is_none`
  - `test_post_chat_with_default_force_token_never_takes_error_branch`

Reuse / non-regression:

- AC20 — GET history endpoint behaviour unchanged:
  - `test_get_chat_history_unchanged_status_and_shape_after_post_endpoint_added`
- AC21 — articles feed and scrape/transform untouched: no new test
  needed — the existing test suites for those features must continue
  to pass unchanged.

Logging / safety:

- AC22 — log lines never contain message body, full reply, or
  traceback. Use `caplog` to assert on emitted records:
  - `test_post_chat_logs_do_not_contain_request_message_body`
  - `test_post_chat_logs_do_not_contain_full_assistant_reply`
  - `test_post_chat_error_path_logs_do_not_contain_traceback_string`

Quality gates:

- AC23, AC24, AC25 — enforced by tooling, not by individual unit
  tests: `make backend-lint` (or equivalent) for `ruff` + `black`
  must pass; the test suite as a whole satisfies AC24 and AC25 by
  composition (no test in the new file touches the real OpenAI SDK,
  per AC16 tests above and `context.md` "Mock LLM in All Tests").

## Definition of done

- [ ] `POST /api/articles/{article_id}/chat` exists, mounted under
      `/api` (AC1).
- [ ] Body validation rejects missing / non-string / empty /
      whitespace-only / oversized `message` with HTTP 422 and writes
      no rows (AC2, AC18).
- [ ] Missing `article_id` returns HTTP 404
      `{"detail": "Article <id> not found"}` and writes no rows
      (AC3).
- [ ] Happy-path response is HTTP 200, `Content-Type:
      text/event-stream`, with `Cache-Control: no-cache`,
      `X-Accel-Buffering: no`, `Connection: keep-alive` (AC4).
- [ ] SSE stream emits `data: {"token": "..."}\n\n` per token,
      followed by exactly one `data: [DONE]\n\n` on success (AC5,
      AC6). Concatenated chunks equal the full reply.
- [ ] Error path emits exactly one `data: {"error": "<sanitised
      sentinel>"}\n\n` then closes; no `[DONE]` (AC7).
- [ ] User row committed before SSE opens; assistant row committed
      before SSE closes; assistant content equals concatenated
      tokens on success (AC8, AC9, AC10).
- [ ] Error-path persists exactly one assistant row with
      `is_error=true` and `content == ERROR_SENTINEL`; user row
      unmodified; sentinel byte-identical between SSE event payload
      and persisted row (AC11, AC12, AC13).
- [ ] Mock generator yields 10..20 deterministic chunks with a
      non-zero inter-token delay; no OpenAI SDK import or outbound
      HTTP request (AC14, AC15, AC16). End-to-end works with
      `OPENAI_API_KEY=sk-fake-...`.
- [ ] `chat_mock_force_error_token` matches by exact equality on
      `message`; default `None` disables the path (AC17, AC19).
- [ ] `chat_message_max_chars` default `512`, accepts `len <= 512`,
      rejects `len > 512` (AC18).
- [ ] Existing `GET /api/articles/{id}/chat`, `GET /api/articles`,
      and scrape / transform pipeline are untouched and their tests
      still pass (AC20, AC21).
- [ ] No log line contains the request body's `message`, the full
      assistant reply, or any raw traceback (AC22).
- [ ] `ruff` and `black` clean on all touched backend files (AC23).
- [ ] All new and existing backend unit tests pass (AC24).
- [ ] No test makes a real outbound OpenAI request (AC25).
- [ ] `tracker.md` row updated to `in_dev` with a `Dev` link to this
      file.

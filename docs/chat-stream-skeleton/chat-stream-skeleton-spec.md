# Spec — `chat-stream-skeleton`

## Source

Plan file `~/.claude/plans/chat-be-stream-and-llm.md`, Task 1
("`chat-stream-skeleton` (mock LLM, real SSE)"). Verbatim scope
statement:

> Stand up `POST /api/articles/{article_id}/chat` end-to-end with real
> SSE plumbing and full DB persistence semantics, using a deterministic
> mock token generator. No real LLM calls. The point is to nail the SSE
> event format, persistence ordering, and error path before introducing
> prompt-engineering and OpenAI SDK complexity.

This spec is for Task 1 only. Task 2 (`chat-llm`, real OpenAI streaming)
is out of scope here and will be specced separately.

## Goal

Add a streaming chat endpoint — `POST /api/articles/{article_id}/chat`
— that accepts a user message, persists it, opens an `text/event-stream`
response, streams a reply token-by-token using a deterministic mock
generator, and persists the full assistant reply (or an error sentinel)
when the stream ends. The deliverable locks down the wire format
(token / `[DONE]` / error events), the persistence ordering (user row
committed before stream opens; assistant row committed before stream
closes), and the failure path (assistant row with `is_error=true`,
followed by an error event and stream close), so that Task 2 can swap
in a real LLM generator with no contract changes.

## User-facing behavior

A "user" here is the operator running the system (tester, reviewer)
and a programmatic client (e.g. `curl -N`, the future frontend
`useChat` hook). From the outside:

- **Happy path.** The client `POST`s
  `/api/articles/{article_id}/chat` with a JSON body
  `{"message": "<text>"}` against an existing article. The server
  responds with HTTP 200, `Content-Type: text/event-stream`, and
  immediately begins streaming SSE events. Each token of the mock
  reply arrives as a `data: {"token": "..."}\n\n` event, with a small
  pause between tokens so the streaming is observable to the naked
  eye. After the final token, the server emits a `data: [DONE]\n\n`
  terminator and closes the stream.
- **History reflects the exchange.** A subsequent `GET
  /api/articles/{article_id}/chat` (the existing endpoint shipped by
  `chat-history`) returns both the user message
  (`role='user'`, `is_error=false`) and the assistant reply
  (`role='assistant'`, `is_error=false`, `content` equal to the
  concatenation of all streamed tokens), in chronological order.
- **Missing article.** A `POST` with an `article_id` that does not
  exist returns HTTP 404 with body
  `{"detail": "Article <id> not found"}` (matching the existing
  `AppError` handler), no SSE stream is opened, and no rows are
  inserted.
- **Invalid body.** A `POST` with a missing `message`, an empty
  `message`, or a `message` longer than the configured maximum is
  rejected with HTTP 422; no SSE stream is opened, and no rows are
  inserted.
- **Forced error path (test hook).** When the request body's
  `message` matches a configured "force error" sentinel string, the
  mock generator deliberately raises mid-stream. Zero or more
  `data: {"token": ...}` events may have already been emitted; the
  server then emits exactly one `data: {"error": "<short message>"}\n\n`
  event and closes the stream. A subsequent `GET .../chat` shows the
  user message (`is_error=false`) followed by an assistant message
  with `is_error=true` and a short error sentinel `content`. The
  raw exception text is not exposed in the SSE event or in the
  persisted row.
- **Logs never expose** the user's full message body or any LLM
  prompt/response payload (per `context.md` "Logging" standards).
  Logging the `article_id`, role, message length, error type, and
  durations is permitted.

## Acceptance criteria

Endpoint surface:

- AC1. `POST /api/articles/{article_id}/chat` exists and is wired
  into the FastAPI app. The route is mounted under the `/api`
  prefix, alongside the existing `GET /api/articles/{article_id}/chat`.
- AC2. The request body is JSON `{"message": "<string>"}`. Pydantic
  validation rejects: missing `message`, non-string `message`, empty
  string (after no transformation — see assumption below), and
  strings longer than `settings.chat_message_max_chars`. Rejection
  yields HTTP 422.
- AC3. When the `article_id` path param does not match an existing
  `articles.id`, the endpoint returns HTTP 404 with body
  `{"detail": "Article <id> not found"}` via the existing `AppError`
  handler. No `chat_messages` rows are written and no SSE stream is
  opened.
- AC4. On the happy path the response has HTTP status `200`,
  `Content-Type: text/event-stream` (charset is unconstrained), and
  the headers `Cache-Control: no-cache`, `X-Accel-Buffering: no`,
  and `Connection: keep-alive`.

SSE wire format (locked for Task 2 to reuse):

- AC5. Each streamed token is emitted as a single SSE event of the
  form `data: {"token": "<chunk>"}\n\n`, where `<chunk>` is a JSON
  string. Concatenating every `chunk` value, in order, yields the
  full assistant reply text.
- AC6. The happy-path stream terminates with exactly one
  `data: [DONE]\n\n` event, after the last token event and before
  the stream closes. No `[DONE]` event is emitted on the error path.
- AC7. The error path emits exactly one `data: {"error": "<short
  message>"}\n\n` event followed by stream close. `<short message>`
  is a short, sanitised, non-empty string that does not contain the
  raw exception class name, traceback, or any LLM payload.

Persistence — happy path:

- AC8. Before the SSE stream opens (i.e. before any token event is
  emitted), exactly one `chat_messages` row is inserted and
  committed for the request, with `article_id` matching the path
  param, `role='user'`, `is_error=false`, and `content` equal to the
  request body's `message` field verbatim.
- AC9. After the mock generator exhausts normally and before the
  stream closes, exactly one additional `chat_messages` row is
  inserted and committed, with `article_id` matching the path
  param, `role='assistant'`, `is_error=false`, and `content` equal
  to the concatenation of every token chunk emitted on the wire.
- AC10. After a successful happy-path request,
  `GET /api/articles/{article_id}/chat` returns both rows in
  chronological order (user first, assistant second) with the
  values described in AC8 and AC9.

Persistence — error path:

- AC11. When the mock generator raises mid-stream (whether after
  zero, some, or all tokens have been streamed), exactly one
  assistant `chat_messages` row is inserted and committed before
  the stream closes, with `role='assistant'`, `is_error=true`, and
  `content` equal to a short, non-empty error sentinel string. The
  user row from AC8 is not modified.
- AC12. On the error path, the assistant row's `content` does not
  contain the raw exception class name or stack trace and does not
  contain any LLM payload.
- AC13. After an error-path request,
  `GET /api/articles/{article_id}/chat` returns the user row
  (`is_error=false`) followed by the assistant row
  (`is_error=true`) in chronological order.

Mock generator behaviour:

- AC14. The mock generator yields a deterministic, finite sequence
  of token chunks (between 10 and 20 tokens inclusive) on the happy
  path. The full concatenated reply is the same canonical string
  on every happy-path call (no per-message variation required).
- AC15. The mock generator awaits a small delay (≤ 100 ms) between
  consecutive tokens so streaming is observable; the exact delay
  is not asserted, but the wall-clock duration of a happy-path
  stream is strictly greater than zero.
- AC16. The mock generator does not instantiate the OpenAI SDK and
  makes no outbound HTTP request. The endpoint works end-to-end
  with `OPENAI_API_KEY` set to a placeholder value (e.g.
  `sk-fake-...`).

Test hook for the error path:

- AC17. A deterministic hook exists that forces the mock generator
  to raise mid-stream. The hook is driven by configuration (a
  Pydantic Settings field — naming/shape is an implementation
  detail, but the field must be settable per-test without code
  changes). When triggered, it produces the AC7 / AC11 / AC12
  behaviour reliably, without relying on real failures, timing,
  or fault injection at the network layer.

Configuration / surface:

- AC18. `settings.chat_message_max_chars` is exposed as a Pydantic
  Settings positive-integer field with a sensible default (≥ 256).
  The default value itself is not asserted; QA verifies that a
  message longer than the configured value is rejected with 422
  and a message at the configured value is accepted.
- AC19. The error-path test hook is exposed as a Pydantic Settings
  field whose default value disables the hook (i.e. the hook is
  not active in production / dev unless explicitly set). With the
  hook disabled, normal happy-path requests never trigger the
  error branch.

Reuse / non-regression:

- AC20. The existing `GET /api/articles/{article_id}/chat`
  endpoint (shipped by `chat-history`) continues to behave as
  before — same status codes, same response shape, same ordering.
  In particular, rows written by this task appear in its output
  with the correct `role` and `is_error` values (covered by AC10
  and AC13).
- AC21. The existing scrape → transform pipeline and
  `GET /api/articles` feed are not regressed by changes in this
  task.

Logging / safety:

- AC22. No log line emitted by this task (at any level) contains
  the request body's `message` field verbatim, the assistant
  reply's full text, or any raw exception traceback. Logging the
  `article_id`, role, message length, error type name, and
  durations is permitted.

Quality gates:

- AC23. Backend `ruff` and `black` pass on all touched files.
- AC24. Backend unit tests pass; new tests cover (a) the
  happy-path SSE event sequence (token events then `[DONE]`),
  (b) persistence of exactly two rows with the expected
  `role` / `is_error` / `content` values on the happy path,
  (c) the 404 path for a missing `article_id` (no rows
  inserted), (d) the 422 path for invalid bodies (missing,
  empty, oversized) with no rows inserted, (e) the forced-error
  path producing the error SSE event and an `is_error=true`
  assistant row, and (f) the mock generator's deterministic
  output shape (10–20 tokens, no SDK instantiation).
- AC25. No test in the suite makes a real outbound OpenAI
  request (per `context.md` "Mock LLM in All Tests").

## Out of scope

- Real LLM calls, prompt construction beyond a stub, and the
  `CHAT_LLM_MOCK` kill-switch (Task 2 — `chat-llm`).
- `request_id` write-side logic and SSE-retry deduplication. The
  `chat_messages.request_id` column already exists from
  `chat-history`; this task neither reads nor writes it. It
  remains `NULL` on every row inserted here.
- Cancellation on client disconnect (closing the stream + dropping
  in-flight work). The endpoint is allowed to keep streaming and
  to persist the assistant row even if the client has hung up.
- A cron / sweep that cleans up orphan user-only rows where the
  request died before the assistant row was written.
- Per-article rate limiting or per-IP throttling.
- Frontend integration. No `useChat` hook, no UI changes, no
  `@microsoft/fetch-event-source` wiring.
- Schema changes. The `chat_messages` table shipped by
  `chat-history` is used as-is; no new columns, indexes, or
  constraints.
- Surfacing the streaming endpoint through `GET /api/articles`
  or any other existing endpoint.

## Open questions / assumptions

Resolved:

- **Persistence ordering on the happy path.** The user row is
  committed before the SSE stream opens (AC8); the assistant row
  is committed before the stream closes (AC9). This is the
  ordering specified by the plan file and locked here so that
  Task 2 inherits it unchanged.
- **Error-event format.** `data: {"error": "<short message>"}\n\n`
  followed by close, with no preceding `[DONE]` (AC7). Locked
  here so the future frontend hook can branch on event payload
  shape rather than on stream-close timing alone.
- **Mock-generator content.** A single canonical 10–20 token
  reply is reused on every happy-path call (AC14). Per-message
  variation is not required at this stage and would add
  determinism noise to QA; Task 2 introduces real per-message
  variation by virtue of calling the LLM.
- **Stream pacing.** A non-zero inter-token delay is required so
  streaming is observable end-to-end (AC15), but the exact value
  is not asserted to keep tests fast and resilient.
- **HTTP status on the error path.** The endpoint returns `200`
  even when the generator fails mid-stream — the failure is
  surfaced as an SSE error event, not as an HTTP error. This
  matches the plan file's contract block and is consistent with
  the SSE pattern (status is determined before the first byte is
  flushed; mid-stream errors cannot retroactively change it).
- **`request_id` column behaviour.** Inserts performed by this
  task leave `request_id` `NULL`. No client-side dedup or
  retry-write semantics are introduced here.
- **`AppError` handler reuse.** The existing handler in
  `backend/app/main.py` is reused for the 404 path; no new
  handler shape is introduced.

Open (flag for human sign-off before dev begins):

- **Whitespace handling on `message`.** Pydantic validation in
  AC2 rejects an empty string. Whether to also reject a
  whitespace-only string (e.g. `"   "`) — by trimming first,
  or by adding a `min_length=1` after `.strip()` — is not
  decided. The plan file says "non-empty"; that literally
  permits whitespace-only. **Default assumption for dev:**
  reject pre-trim only (i.e. `min_length=1` on the raw string).
  QA may need to update if this is changed.
- **Maximum message length default.** AC18 leaves the numeric
  default for `chat_message_max_chars` to dev discretion (≥ 256).
  No specific value is asserted; if the operator wants a
  particular ceiling (e.g. 4 000 characters to mirror typical
  chat input boxes), please confirm before dev locks it in.
- **Error sentinel content.** AC11 / AC12 require a short,
  non-empty, sanitised string for both the SSE error event and
  the persisted `assistant` row. Whether the SSE event message
  and the persisted row's `content` are the same string, or two
  different strings (one client-facing, one for history
  display), is unspecified. **Default assumption for dev:**
  use the same short string in both. If this should differ
  (e.g. the persisted row uses a longer human-readable message
  while the SSE event is terse), please confirm before dev.

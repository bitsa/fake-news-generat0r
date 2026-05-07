# Spec — `chat-llm`

## Source

Plan file [`/Users/bitsa/.claude/plans/chat-be-stream-and-llm.md`](/Users/bitsa/.claude/plans/chat-be-stream-and-llm.md),
**Task 2 — `chat-llm` (real OpenAI streaming)**. Verbatim scope statement:

> Replace Task 1's mock generator with a real OpenAI streaming call, and add
> prompt construction that injects article context + recent chat history.
> SSE event format and persistence behavior are unchanged — Task 1 locked
> those.

Scope (in) per the plan:

> - New service `backend/app/services/chat_llm.py` (mirroring shape of
>   `openai_transform.py`):
>   - Prompt builder: takes the original `Article` + its `ArticleFake` +
>     last N `ChatMessage` rows, returns an OpenAI message list (system +
>     history + new user). N from settings (`chat_history_window: int`,
>     default ~10).
>   - Streaming call: OpenAI Python SDK with `stream=True` (Chat Completions
>     or Responses API — match what `openai-transform` already uses for
>     consistency); iterate stream chunks; yield each `delta.content` as an
>     SSE `data: {"token": ...}` event.
> - Kill-switch env var `CHAT_LLM_MOCK: bool` (mirroring
>   `openai-transform-spec.md`) that re-routes to Task 1's `chat_mock`
>   generator. CI/dev default = mock; prod = real.
> - Real-LLM exceptions (`openai.APIError`, timeouts, rate limits) feed
>   into Task 1's error path: `is_error=true` assistant row + error SSE
>   event + close. Short, sanitised error string in the event — never the
>   raw provider message (per logging standards in `context.md`, no full
>   LLM payloads in logs/responses).
> - Settings additions: `chat_model: str`, `chat_temperature: float`,
>   `chat_max_output_tokens: int`, `chat_history_window: int`,
>   `chat_llm_mock: bool`.

Scope (out) per the plan: `request_id` retry-dedup logic, cancellation
on client disconnect mid-LLM-call, per-article rate limiting, frontend
integration. Verification steps and reuse notes from the plan are also
incorporated below.

## Goal

Replace the deterministic mock token generator delivered by
`chat-stream-skeleton` with a real OpenAI streaming call that produces
context-aware token-by-token replies for the per-article chat. Add a
prompt builder that injects the original `Article`, its `ArticleFake`,
and the last N `ChatMessage` rows so the assistant has the article and
recent conversation as context. Preserve unchanged the SSE event format,
persistence ordering (user row committed before stream opens, assistant
row committed before stream closes), and error-path behaviour
(`is_error=true` assistant row + error event + close) that Task 1 locked.
Provide a `CHAT_LLM_MOCK` kill-switch — mirroring the `OPENAI_MOCK_MODE`
pattern already shipped by `openai-transform` — so local development and
CI can run the full pipeline without an API key or network call.

## User-facing behavior

A "user" here is the operator running the system (tester, reviewer) and
any client speaking the SSE contract on `POST /api/articles/{id}/chat`.
The wire contract (URL, request body, headers, event format,
terminator, error event, status codes) is **identical** to Task 1; this
task only changes the *content* of token events when the kill-switch is
off, and the way errors are produced.

- **With `CHAT_LLM_MOCK=true` (default for CI / local dev):**
  `POST /api/articles/{id}/chat` behaves exactly as `chat-stream-skeleton`
  delivered it — tokens come from Task 1's deterministic mock generator,
  no outbound HTTP requests are made to `api.openai.com`. The OpenAI
  SDK client is not instantiated.
- **With `CHAT_LLM_MOCK=false` and a valid `OPENAI_API_KEY`:** the same
  endpoint streams tokens produced by a real OpenAI streaming completion.
  Token contents reflect the model's reply to a prompt built from the
  original article, its satirical version, the last N chat messages
  (oldest-first), and the new user message. Each chunk's `delta.content`
  is wrapped in a `data: {"token": "..."}\n\n` SSE event with the same
  framing Task 1 emits; the stream ends with `data: [DONE]\n\n` on
  normal completion.
- **Persistence ordering is unchanged.** The user message row is
  committed (with `role='user'`, `is_error=false`) before any token is
  emitted. After the model's stream completes, the assistant's full
  buffered content is committed as one row (`role='assistant'`,
  `is_error=false`) before the `[DONE]` terminator is sent.
- **On any real-LLM failure** — request timeout, OpenAI API error
  (authentication, rate limit, server error), connection error, or any
  other exception raised by the SDK or the streaming iterator — the
  endpoint:
  - persists an assistant row with `is_error=true` and a short,
    sanitised error sentinel as `content` (never the raw provider
    message),
  - emits a single `data: {"error": "<short sentinel>"}\n\n` SSE event,
  - closes the stream cleanly,
  - does not re-raise the exception out of the streaming response.
- **Failure observability.** A subsequent `GET /api/articles/{id}/chat`
  shows the same user row (committed before the failure) and the
  assistant row with `is_error=true`, so the conversation history is
  consistent across success and failure cases.
- **Logs never expose** the OpenAI request body (system prompt or any
  user-facing prompt content), the full streamed response, the API key,
  or full chat-message content. Logging the model identifier, the
  failing exception type name, the `article_id`, and durations / token
  counts is permitted (per `context.md` "Logging" standard).
- **`.env.example`** documents the new settings (kill-switch, history
  window, and any chat-specific OpenAI tuning fields actually
  introduced by this task) with one-line descriptions in the same style
  as the existing entries. The active value of the kill-switch line in
  `.env.example` is the operator's convenience choice (consistent with
  how `openai-transform` handles `OPENAI_MOCK_MODE`); the Settings
  default (`true`) is authoritative when the env var is unset.

## Acceptance criteria

Functional — real-call path (`CHAT_LLM_MOCK=false`):

- AC1. When `POST /api/articles/{id}/chat` runs against an existing
  article with `CHAT_LLM_MOCK=false`, the backend invokes the OpenAI
  streaming Chat Completions / Responses call exactly once per request
  (the same SDK surface that `openai-transform` already uses, configured
  with `stream=True`).
- AC2. The OpenAI call is made with `model` = `settings.chat_model`,
  `temperature` = `settings.chat_temperature`, and a per-request token
  cap of `settings.chat_max_output_tokens`, and uses a per-request
  timeout of `settings.openai_request_timeout_seconds`.
- AC3. Each non-empty `delta.content` chunk produced by the streaming
  iterator is emitted to the client as one SSE event with framing
  `data: {"token": "..."}\n\n` (UTF-8). Empty / whitespace-only deltas
  may be coalesced or skipped, but no chunk's text is dropped from the
  final assistant row content.
- AC4. After the model's stream is exhausted, exactly one assistant
  `chat_messages` row is inserted with `role='assistant'`,
  `is_error=false`, and `content` equal to the concatenation of all
  emitted token texts; the row is committed **before** the
  `data: [DONE]\n\n` terminator is sent.
- AC5. The user message row is inserted with `role='user'`,
  `is_error=false`, and `content` equal to the request body's `message`
  field, and is committed **before** any token event is emitted.

Functional — prompt construction:

- AC6. The OpenAI message list passed to the SDK contains, in order:
  1. exactly one `system` message whose text is stable across runs for
     the same input (no timestamps, randomness, or environment data
     embedded in the prompt body),
  2. zero or more `user` / `assistant` messages reconstructed from the
     last N `chat_messages` rows for the article in chronological order
     (oldest-first), where N = `settings.chat_history_window`,
  3. exactly one final `user` message containing the new request body
     `message`.
- AC7. The prompt builder includes, somewhere in the system message or
  a dedicated context preamble, the original article's `title` and
  `description` and the satirical (`article_fakes`) `title` and
  `description` for the same `article_id`, when the `ArticleFake` row
  exists and `transform_status='completed'`. When the `ArticleFake`
  row does not exist or is not yet completed, only the original
  article's `title` and `description` are included; the request still
  succeeds.
- AC8. History selection uses the same ordering rule as Task 1's GET
  history endpoint (chronological by `created_at` ascending,
  tie-broken by `id` ascending), and `assistant` rows with
  `is_error=true` are **excluded** from the prompt history (they are
  failure breadcrumbs, not real assistant turns).
- AC9. When more than `chat_history_window` prior messages exist, the
  builder includes only the most recent `chat_history_window` of them,
  preserving chronological order in the resulting message list.
- AC10. The user-message row inserted in this same request (AC5) is
  **not** double-counted: the prompt's final `user` message is the
  newly received message exactly once, and the history slice does not
  also include it.

Functional — mock-mode path (`CHAT_LLM_MOCK=true`):

- AC11. When `CHAT_LLM_MOCK=true`, `POST /api/articles/{id}/chat`
  produces the same wire output (token events, `[DONE]` terminator,
  error event on the test-hook path) and the same persistence
  behaviour that `chat-stream-skeleton` delivered for its mock path —
  i.e. mock-mode dispatch is wired through the existing
  `chat_mock` generator from Task 1 without touching the router.
- AC12. When `CHAT_LLM_MOCK=true`, no network request is made to
  OpenAI and the OpenAI SDK client is not instantiated. Mock-mode
  works even when `OPENAI_API_KEY` is a placeholder
  (e.g. `sk-fake-...`).

Functional — failure path:

- AC13. On any exception raised by the OpenAI SDK call or its
  streaming iterator — request timeout, API error (authentication,
  rate limit, server error), connection error, malformed chunk, or
  an unexpected exception in the surrounding service code — the
  endpoint:
  (a) inserts and commits exactly one assistant `chat_messages` row
      with `is_error=true` and a short, fixed, non-empty sentinel
      string as `content` (the sentinel is the same across failure
      variants and is not the raw provider message),
  (b) emits exactly one `data: {"error": "<sentinel>"}\n\n` SSE event
      after the failure, where the `error` field is a short
      sanitised string (no provider error body, no API key, no full
      prompt or response content),
  (c) closes the stream cleanly without sending a `data: [DONE]\n\n`
      terminator after the error event,
  (d) does not propagate the exception out of the streaming
      response (the HTTP status remains `200` for the stream itself,
      consistent with Task 1's locked contract),
  (e) emits exactly one `ERROR`-level log line identifying the
      `article_id` and the failing exception type name (no prompt
      body, no response body, no API key).
- AC14. If the failure occurs after some token events have already
  been emitted, those tokens are still represented in the persisted
  assistant row's content **only if** the `is_error=true` row's
  `content` is required to capture them; otherwise the sentinel
  alone is acceptable. The behaviour chosen here is pinned in the
  dev plan but must be self-consistent: the persisted row content
  and the stream's emitted token events must agree about what the
  client saw versus what it didn't.
  — Open question OQ-1 (see below).

Configuration / surface:

- AC15. `CHAT_LLM_MOCK` is exposed as a Pydantic Settings boolean
  field (`chat_llm_mock`) defaulting to `true` (CI/dev-friendly
  default). It is read only via the Settings object, never via
  `os.environ` directly (per `context.md` Standards).
- AC16. `chat_history_window` is exposed as a Pydantic Settings
  positive-integer field with a default of `10`.
- AC17. `chat_max_output_tokens` is exposed as a Pydantic Settings
  positive-integer field with a sensible default (suggested `512`,
  pinned in the dev plan).
- AC18. The chat model and chat temperature settings used by this
  task come from a single, consistent pair of Settings fields
  resolved during dev planning (see Open Questions OQ-2). Whichever
  pair is used, the values reach the OpenAI SDK call exactly as
  configured.
- AC19. `.env.example` documents `CHAT_LLM_MOCK`, `CHAT_HISTORY_WINDOW`,
  `CHAT_MAX_OUTPUT_TOKENS`, and any newly-introduced chat model /
  temperature fields with one-line descriptions matching the existing
  style. Pre-existing OpenAI keys (`OPENAI_API_KEY`,
  `OPENAI_REQUEST_TIMEOUT_SECONDS`, `OPENAI_MOCK_MODE`) are not
  modified by this task.
- AC20. The public router contract is unchanged: the request URL,
  request body shape, response media type, status codes (200 / 404 /
  422), and SSE event format defined by Task 1 are byte-for-byte
  identical to what Task 1 shipped — this task changes only the
  *source* of token contents and the cause of error events.

Logging / safety:

- AC21. No log line emitted by this task (at any level) contains the
  full OpenAI request body, the system prompt text, any user message
  content, the assistant's full streamed response, or the value of
  `OPENAI_API_KEY`. Logging the model identifier, the failing
  exception type name, an `article_id`, durations, and token counts
  is permitted.
- AC22. The error sentinel string emitted in `data: {"error": ...}`
  events is short (≤ 80 characters), human-readable, and does not
  include provider error messages, stack traces, status codes, or
  request IDs.

Quality gates:

- AC23. Backend `ruff` and `black` pass on all touched files.
- AC24. Backend unit tests pass; new tests cover the prompt builder
  (article + fake + history ordering, exclusion of error rows,
  history window cap, behaviour when `ArticleFake` is missing /
  pending, no double-counting of the new user message), the
  real-call streaming path with the OpenAI SDK mocked (token events
  match SSE shape, persistence on completion, model / temperature /
  max-tokens / timeout wiring), the kill-switch short-circuit
  (asserting no SDK instantiation / no network call when
  `CHAT_LLM_MOCK=true`), and at minimum the timeout, API-error,
  connection-error, and mid-stream-exception variants of AC13.
- AC25. No test in the suite makes a real outbound OpenAI request
  (per `context.md` "Mock LLM in All Tests").

## Out of scope

- Anything Task 1 (`chat-stream-skeleton`) is responsible for: the
  POST endpoint scaffolding itself, SSE framing, the user-row /
  assistant-row persistence sequence, the test-hook path that forces
  the error branch from a magic input, the 404 / 422 status mapping,
  request body validation, and the mock generator module. This task
  consumes those deliverables and only swaps the generator + adds the
  prompt builder. If Task 1 has not landed when this task starts,
  that blocks dev — see OQ-3.
- `request_id` write-side logic, retry-dedup, or any uniqueness
  constraint on the column. The column exists from `chat-history` but
  is not populated.
- Cancellation on client disconnect mid-LLM-call (the SDK call is not
  cancelled if the client disconnects). Deferred per the plan's
  "What stays deferred after both tasks".
- Cron sweep for orphan user-only rows where SSE died before the
  assistant row was written. Deferred per the plan.
- Per-article or global rate limiting on chat requests.
- Surfacing real-LLM failures as a non-200 HTTP status. The locked
  contract from Task 1 keeps the HTTP status at 200 once the stream
  is open; failures appear as in-band `data: {"error": ...}` events.
- Streaming via Server-Sent Events transport changes (heartbeat
  comments, custom `event:` types, `id:` reconnection IDs). The
  framing is exactly `data: {...}\n\n` plus `data: [DONE]\n\n`.
- Tool / function calling, structured-output JSON schemas in the
  chat path, multi-turn tool loops, multi-modal inputs, image
  attachments, or token-cost accounting / budgeting.
- Frontend `useChat` hook and any UI integration. Frontend-side work
  is a separate task per the plan.
- Modifying `services/openai_transform.py`, `workers/transform.py`,
  the GET history endpoint, or the `chat_messages` schema. No
  migration is required.
- Any change to the `articles` or `article_fakes` schemas or to the
  scrape / transform pipeline.

## Open questions / assumptions

1. **OQ-1: Persisted assistant content on partial-stream failure.**
   When the LLM stream produces N tokens successfully and then fails,
   should the assistant row's `content` be (a) the partial buffered
   text that was already emitted to the client, (b) the short error
   sentinel string only, or (c) the partial buffered text *with* an
   appended error sentinel? The plan and Task 1's locked semantics do
   not pin this. Recommendation: **(b) — error sentinel only** for
   simplicity and to match the success-path invariant "the assistant
   row's `content` is what the user saw as a finished reply". The dev
   plan must pin one option; QA will verify whatever the dev plan
   pins, and AC14 enforces self-consistency between row content and
   emitted events. Needs sign-off before dev starts.

2. **OQ-2: Settings field naming for chat model / temperature.**
   `backend/app/config.py` already exposes `openai_model_chat` and
   `openai_temperature_chat` (added during scaffolding for an earlier
   slice). The plan calls for new fields named `chat_model` and
   `chat_temperature`. Adding both pairs would be redundant /
   confusing. Recommendation: **reuse the existing
   `openai_model_chat` / `openai_temperature_chat` fields** and do
   not introduce parallel `chat_model` / `chat_temperature` fields.
   This keeps OpenAI-specific config under the `openai_` prefix
   alongside `openai_model_transform` / `openai_temperature_transform`
   and avoids drift. AC18 is intentionally written to allow either
   resolution — pin one in the dev plan. Needs sign-off before dev
   starts.

3. **OQ-3: Task ordering dependency on `chat-stream-skeleton`.**
   Task 1 (`chat-stream-skeleton`) is `spec'd` at the time this spec
   is written but not yet implemented (see
   [chat-stream-skeleton-spec.md](../chat-stream-skeleton/chat-stream-skeleton-spec.md)).
   This task strictly depends on Task 1's deliverables (POST router,
   SSE plumbing, `chat_mock` generator, persistence sequencing,
   `is_error` write path). Dev for `chat-llm` must not start until
   Task 1 is at least `in_qa`. Flagging here so the orchestrator
   does not start `chat-llm` against a missing scaffold; QA-side
   unit tests that assume the Task 1 surface (e.g. importing
   `chat_mock`) will fail otherwise.

4. **OQ-4: SDK surface — Chat Completions vs. Responses API.**
   `openai_transform.py` uses
   `client.beta.chat.completions.parse(...)` (Chat Completions with
   structured outputs) — but that is the structured-output entry
   point, which does not stream. The plan says "match what
   `openai-transform` already uses for consistency" yet also requires
   `stream=True`. Recommendation: use the standard streaming Chat
   Completions surface
   (`client.chat.completions.create(model=..., messages=...,
   stream=True, ...)`) since structured outputs aren't applicable to
   free-form chat replies, and treat "consistency with
   `openai-transform`" as "same SDK package and client construction
   pattern" rather than "same exact method". The dev plan must pin
   the exact SDK call. QA does not need to verify the SDK surface
   beyond "the call was made once with `stream=True` and the
   configured model / temperature / max-tokens / timeout".

5. **OQ-5: `chat_max_output_tokens` default.** Plan does not specify
   a number. Recommendation: `512`. Justification: short, factual
   replies (summaries, key entities, change diffs) per the
   assignment's structured questions; keeps the cost ceiling
   predictable. Pin in dev plan.

6. **OQ-6: Error sentinel string content.** Recommendation: a single
   constant such as `"stream failed"` for both the SSE `error` field
   and the `is_error=true` assistant row's `content`. AC22 caps
   length and forbids leaking provider details; the exact string is
   a dev-plan choice within those constraints.

7. **OQ-7: Empty-history behaviour.** When the article has zero prior
   `chat_messages` rows (first turn), the prompt's history slice is
   empty and the message list contains only the system message and
   the new `user` message. Confirmed assumption — surfaced because
   QA will write a "first-turn" test against this case, and pinning
   it here prevents drift.

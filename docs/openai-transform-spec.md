# Spec — `openai-transform`

## Source

Plan file `~/.claude/plans/let-s-start-working-on-zesty-riddle.md`
("Real OpenAI Call in `transform_article` (with dev kill-switch)"). Verbatim
scope statement:

> After this change, when the worker picks up a `transform_article` job it
> must:
>
> 1. Call OpenAI with the original article's `title` + `description`.
> 2. Get back a satirical `{title, description}` pair.
> 3. Persist them on the `article_fakes` row along with `model`,
>    `temperature`, and `transform_status='completed'`.
> 4. On any OpenAI failure (timeout, API error, schema validation, JSON
>    decode): delete the `article_fakes` row, log `ERROR`, do not re-raise.

Plus a dev-only mock kill-switch (`OPENAI_MOCK_MODE`) that short-circuits
the OpenAI call to fixed strings without instantiating the SDK or making a
network request.

## Goal

Replace the static `MOCK_TITLE` / `MOCK_DESCRIPTION` writes in the ARQ
`transform_article` worker with a real OpenAI structured-output call that
produces a satirical `(title, description)` pair from the original article
and persists it on the `article_fakes` row. Add an opt-in env-driven mock
mode so local development can run the full pipeline end-to-end without an
API key or network call. Failure handling, durability, and the existing
two-state lifecycle (`pending` → `completed`, deletion on failure) are
preserved unchanged — this task only swaps the stub for a real call and
adds the kill-switch around it.

## User-facing behavior

A "user" here is the operator running the system (tester, reviewer) and
the API consumers reading `article_fakes` rows. From the outside:

- **With `OPENAI_MOCK_MODE=true` (or absent and configured to true via
  `.env`):** `POST /api/scrape` returns its existing response shape; soon
  after, every newly inserted `article_fakes` row reaches
  `transform_status='completed'` with `title` and `description` set to the
  same fixed mock strings (one canonical pair, identical across rows).
  `model` and `temperature` reflect the configured settings. No outbound
  HTTP requests are made to `api.openai.com`.
- **With `OPENAI_MOCK_MODE=false` and a valid `OPENAI_API_KEY`:** the same
  flow runs end-to-end against the real OpenAI API. Each completed row
  carries a satirical `title` and `description` derived from the original
  article (distinct content per row, recognisably related to the source
  article). `model` and `temperature` reflect the configured settings.
- **On any OpenAI failure** (timeout, API error, malformed/invalid JSON,
  schema mismatch): the corresponding `article_fakes` row disappears (is
  deleted); the `articles` row is untouched; one `ERROR`-level log line is
  emitted; the worker continues processing other jobs; no exception
  escapes the worker.
- **Re-running the same job for an already-completed row** (e.g. via a
  recovery sweep that races a real worker, or a manual re-enqueue) is a
  no-op: no second OpenAI call is made, the row is not modified, and a
  log line records the skip.
- **Logs never expose** the OpenAI request body (system prompt, user
  prompt with the article content), the OpenAI response body, or the API
  key — at any log level.
- **`.env.example`** documents `OPENAI_REQUEST_TIMEOUT_SECONDS` and
  `OPENAI_MOCK_MODE` (the latter with guidance that local development
  should set it to `true`).

## Acceptance criteria

Functional — real-call path (`OPENAI_MOCK_MODE=false`):

- AC1. When `transform_article` runs for a `pending` `article_fakes` row
  whose `articles` parent exists, the worker calls OpenAI exactly once,
  passing the original article's `title` and `description` as input.
- AC2. On a successful OpenAI response the worker writes `title`,
  `description`, `model`, `temperature`, and
  `transform_status='completed'` to that `article_fakes` row, and the
  values for `model` and `temperature` come from
  `settings.openai_model_transform` and
  `settings.openai_temperature_transform`.
- AC3. On a successful OpenAI response, `article_fakes.title` and
  `article_fakes.description` are non-empty strings derived from the
  model output (not equal to the original article's `title` /
  `description`, and not equal to the mock-mode fixed strings).
- AC4. The OpenAI call is made with a structured-output (JSON-schema)
  request format — i.e. the response is parsed as a JSON object with
  exactly two required fields (`title`, `description`).
- AC5. The OpenAI client honours a request timeout configured via
  `settings.openai_request_timeout_seconds` (default `30`).

Functional — mock-mode path (`OPENAI_MOCK_MODE=true`):

- AC6. When `OPENAI_MOCK_MODE=true`, `transform_article` writes a fixed
  mock `title` and `description` to the row (the same canonical pair on
  every call) and sets `transform_status='completed'`. `model` and
  `temperature` are still populated from settings.
- AC7. When `OPENAI_MOCK_MODE=true`, no network request is made to
  OpenAI and the OpenAI SDK client is not instantiated. Mock-mode works
  even when `OPENAI_API_KEY` is a placeholder (e.g. `sk-fake-...`).

Functional — idempotency:

- AC8. When `transform_article` runs for an `article_fakes` row whose
  `transform_status` is already `completed`, the worker does not call
  OpenAI, does not modify the row, and emits one log line indicating
  the skip.

Functional — failure path:

- AC9. On any OpenAI failure path — request timeout, OpenAI API error
  (e.g. authentication, rate limit, server error), connection error,
  invalid/malformed JSON in the response, or response that does not
  match the expected `{title, description}` schema — the worker:
  (a) deletes the corresponding `article_fakes` row,
  (b) preserves the corresponding `articles` row,
  (c) emits one log line at `ERROR` level identifying the failed
      `article_id`,
  (d) does not propagate the exception out of the worker (the ARQ job
      completes without re-raise),
  (e) does not retry the call (the worker continues to run with
      `max_tries=1`).

Configuration / surface:

- AC10. `OPENAI_REQUEST_TIMEOUT_SECONDS` is exposed as a Pydantic
  Settings field with a positive integer default of `30`.
- AC11. `OPENAI_MOCK_MODE` is exposed as a Pydantic Settings boolean
  field defaulting to `false`.
- AC12. `.env.example` documents both `OPENAI_REQUEST_TIMEOUT_SECONDS`
  and `OPENAI_MOCK_MODE` with one-line descriptions in the same style
  as the other entries in that file.
- AC13. The public worker contract is unchanged: `transform_article`
  remains an ARQ job function with signature
  `async def transform_article(ctx, article_id: int) -> None`, and
  `WorkerSettings.max_tries` remains `1`.

Logging / safety:

- AC14. No log line emitted by this task (at any level) contains the
  full OpenAI request body, the system or user prompt text, the model
  response body, or the value of `OPENAI_API_KEY`. Logging the model
  identifier, the failing exception type name, an `article_id`, and
  durations is permitted.

Quality gates:

- AC15. Backend `ruff` and `black` pass on all touched files.
- AC16. Backend unit tests pass; new tests cover the real-call success
  path, the mock-mode short-circuit (asserting no SDK instantiation /
  no network call), the `completed`-row idempotency skip, and at
  minimum the timeout, API-error, malformed-JSON, and
  schema-validation failure variants of AC9.
- AC17. No test in the suite makes a real outbound OpenAI request.

## Out of scope

- Retries, backoff, dead-letter queues, or persisting any `failed`
  state. The two-state lifecycle (`pending` / `completed`) and
  delete-on-failure model are intentional (`context.md` "Transform
  Durability Model").
- Surfacing OpenAI failures to the HTTP API as a non-500 status. This
  task's failure path is fully internal to the worker.
- Changing the `article_fakes` schema (no `transform_error`, no `failed`
  status).
- Streaming responses, function calling, token / cost accounting,
  prompt evals, prompt versioning, or multi-model A/B selection.
- Exposing the new fake `title` / `description` through
  `GET /api/articles` (handled by the separate `get-articles` task,
  currently `in_qa`).
- The ARQ cron-based recovery sweep (separate item; the existing
  startup recovery sweep is unchanged by this task).
- Modifying `services/transformer.py`, `main.py`, or
  `routers/scrape.py`.

## Open questions / assumptions

1. **`OPENAI_MOCK_MODE` default in `.env.example` vs Settings default.**
   `.env.example` currently has an uncommitted line
   `OPENAI_MOCK_MODE=true` (committed during a prior task) even though
   `config.py` does not yet define the field. The plan calls for the
   Pydantic default to be `False` (so prod / Docker behaviour is the
   real call), with `.env.example` documenting the variable and
   recommending `true` for local dev. Need confirmation: should the
   `.env.example` line stay as `OPENAI_MOCK_MODE=true` (active default
   for anyone who copies the file verbatim) or be commented out so the
   active default reflects the safer-for-prod `false`? Current spec
   accepts either as long as the variable is documented (AC12) and the
   Settings default is `false` (AC11). Flagging because the choice
   affects what a fresh clone does on first `make up`.
2. **Mock-mode content shape.** Plan specifies a single canonical
   `(MOCK_TITLE, MOCK_DESCRIPTION)` pair re-used for every row in
   mock mode. Confirmed acceptable for AC6 — same fixed strings on
   every call, no per-article variation. Flagging only because this
   is a behavioural choice (not derivable from existing code) and a
   reviewer might expect per-article mock variation.
3. **Definition of "satirical" for AC3.** The criterion as written is
   verifiable only at the structural level (non-empty strings, distinct
   from originals and from mock strings). A stronger semantic check
   ("the output is recognisably satirical") is not testable without a
   judge model and is therefore out of scope. Confirming this is
   acceptable.
4. **Documentation alignment.** The plan file references "ADR-9" and
   uses ADR-numbered notation in `.env.example` (line 2). Project
   `CLAUDE.md` says: "Do not reference 'ADR' or 'ADR-N' notation
   anywhere." The `.env.example` comment is pre-existing drift, not
   introduced by this task, but worth flagging because anyone touching
   `.env.example` for AC12 may want to fix it in the same change.
5. **Worker behaviour when `Article` row is missing but `ArticleFake`
   exists.** The FK from `article_fakes` to `articles` (with
   `ondelete=CASCADE`) makes this state structurally impossible, but
   the worker still loads the article via `session.get(Article, id)`.
   Spec assumes this path is treated as a defensive no-op (log +
   return, no OpenAI call, no row deletion); it is not exercised in
   normal flow and should not be a primary acceptance criterion.
   Flagging in case the reviewer wants explicit treatment.

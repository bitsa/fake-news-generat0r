# Context

> Read this before writing any code. It covers the key concepts, decisions, and standards.
> Do not look here for DB schema, API shapes, file structure, or model names — read the code.
> Do not contradict any decision without surfacing the conflict first.

**Assignment:** [plans/assignment.md](plans/assignment.md)

**What we're building:** A full-stack app that scrapes real news articles from RSS feeds, uses an
LLM to generate satirical versions of each headline and description, and lets users chat with a
context-aware assistant about each article. Deployed via Docker Compose.

---

## Core Concepts

### SSE Streaming (Chat)

Chat uses Server-Sent Events: the client POSTs a message, the backend opens a streaming response
and pushes token events as the LLM responds, terminating with `[DONE]`. The frontend consumes the
stream and appends tokens in real time. WebSockets were rejected — the pattern is unidirectional
(server → client only), SSE uses plain HTTP with no upgrade handshake, and there is no server-side
connection state to manage.

### Queue + Worker (Transform Pipeline)

Scraping and transformation are decoupled. The API scrapes and inserts articles synchronously,
then enqueues ARQ transform jobs. A separate worker process picks up jobs from the Redis broker
and calls the LLM. Redis is the broker — it is not the source of truth for what work needs to
happen. That distinction is the whole point of the durability model below.

### Transform Durability Model

The DB is the source of truth. The ARQ queue is a fast-path delivery mechanism, not the only
record that work exists.

`article_fakes` carries a `transform_status` field with two values:

- `pending` — article inserted, job enqueued
- `completed` — LLM call succeeded, fake content stored

On failure the row is deleted and the error is logged. The article reverts to "no fake" state
(UI shows "Processing…"). No `failed` status, no `transform_error` column — failures are
ephemeral, not persisted.

This closes the durability gap: if the queue is wiped or the worker crashes mid-flight, the
`pending` row survives and recovery re-enqueues it. The queue is an optimisation, not the record
of intent.

The scrape flow:

```text
POST /api/scrape
  → INSERT INTO articles ... ON CONFLICT (url) DO NOTHING
  → if inserted: INSERT INTO article_fakes (article_id, transform_status='pending')
  → enqueue ARQ job (best-effort)

ARQ worker
  → call LLM
  → on success: UPDATE article_fakes SET fake_title=..., transform_status='completed'
  → on failure: DELETE FROM article_fakes WHERE article_id=... (log error, clean up)

Recovery (startup or cron)
  → re-enqueue article_fakes WHERE transform_status='pending'
    AND created_at < NOW() - interval '5 min'
```

### Frontend State Model

React Query handles all server state. SSE is managed by a custom hook using
`@microsoft/fetch-event-source`. The source filter lives in URL query params. No global state
store in MVP — reassess in Iteration 2 if prop-drilling becomes a problem.

---

## Decisions

### Python + FastAPI over Node

Python wins for LLM work: the OpenAI SDK, SQLAlchemy async, feedparser, and ARQ are all stronger
in Python than their Node equivalents. The brief evaluates backend depth; Python signals LLM
ecosystem familiarity.

### ARQ + Durability over Celery or BackgroundTasks

ARQ is native asyncio; Celery's async story is bolted on. FastAPI `BackgroundTasks` share the
event loop with the API — LLM work should be isolated. Workers run each job once (`max_tries=1`);
the durability model above replaces retry storms with explicit recovery.

### Hand-Written Alembic Migrations

Autogenerate misses complex constraints and produces unreadable diffs. For a bounded, pre-planned
schema, manual migrations are clearer and more deliberate.

### SSE over WebSockets

Chat streaming is unidirectional. SSE uses plain HTTP — no upgrade handshake, no persistent
connection state, no reconnect protocol to implement server-side.

### 1:1 `article_fakes` Table

Originals in `articles`; satirical content in `article_fakes`. `article_id` is simultaneously PK
and FK — makes "two fakes per article" impossible by construction.

`articles` is insert-only after creation (originals are never overwritten). `article_fakes` is
freely updateable — re-running a transformation replaces the existing row.

On naming: `articles` (not `articles_original`) is correct. The originals table IS just
"articles" — it's the canonical entity. Adding `_original` would be like renaming `users` to
`users_real`. `article_fakes` makes the derived nature explicit without muddying the primary
table's name.

### One Row per Chat Message

`chat_messages` stores one row per message with a `role` field. Conversation reconstructed by
ordering on `created_at`. A JSON-blob alternative loses queryability and the future `user_id`
extension path.

### React Query, No Store in MVP

React Query handles all server state. The only shared client state (source filter) lives in URL
params. No Zustand or Redux until prop-drilling past 2 levels actually appears (Iteration 2
reassessment).

### No Vercel AI SDK

SSE is implemented manually with `@microsoft/fetch-event-source`. The Vercel AI SDK abstracts
the streaming plumbing — which is exactly what this project demonstrates understanding of. It also
expects Next.js / Vercel edge functions, not Docker Compose.

### Redis is ARQ Broker Only

Redis serves one purpose: the ARQ queue broker. No LLM response cache — with content-hash dedup
upstream, no two transform jobs can ever fire for the same input, so a cache would have no hit
path.

### Mock LLM in All Tests

Real LLM calls add cost, nondeterminism, and blow the test time budget. Mocking forces explicit
definition of what the system does with model responses.

### Shared Chat, No Auth in MVP

Chat history is shared per article. Auth would crowd out the LLM pipeline and streaming work the
brief evaluates.

### pgvector Image from Day One

`pgvector/pgvector:pg16` from day one. Switching images mid-project requires container recreation.
The extension is a no-op until Iteration 3 — using the image early costs nothing.

### Tailwind CSS v3

Utility classes produce a consistent design system fast with no designer. v4 has breaking changes
and is in beta — not worth the risk on a deadline.

### Sources as Python StrEnum

Source identity is a Python `StrEnum` in `backend/app/sources.py`. No `sources` DB table. The
Postgres enum type is generated from the StrEnum — drift is impossible by construction. Adding a
source = one line in the enum + one line in `FEED_URLS` + an `ALTER TYPE` migration.

### Periodic Scraping via ARQ Cron

Scheduled scraping runs as an ARQ cron job inside the existing `worker` container, firing at
wall-clock `:00` and `:30` of every hour. The cron handler reuses `scraper.scrape_cycle` — the
same helper invoked from the FastAPI startup lifespan — so startup and periodic scrapes share
one code path. We chose ARQ cron over external schedulers (host cron, Kubernetes CronJob, GitHub
Actions, separate scheduler container) because ARQ + Redis is already in the stack, the worker
process already runs continuously, and ARQ's native cron support adds zero new dependencies.

---

## Standards

### Python

- Type hints required on all signatures. Use `X | None` in return types and field definitions
  (not `Optional[X]`).
- All I/O is async. Never `asyncio.run()` in app code. Never use the sync `Session`.
- Formatter: `black` (88). Linter: `ruff` (E, F, I, UP). CI blocks on failures.
- Naming: modules `snake_case`, classes `PascalCase`, functions/vars `snake_case`,
  constants `UPPER_SNAKE_CASE`, private helpers `_prefixed`.
- Custom exceptions inherit `AppError` (in `app/exceptions.py`) with a `status_code`. Never let
  domain exceptions bubble as 500s when a specific status applies.
- All config via `Pydantic Settings`. Never read `os.environ` directly.

### TypeScript

- `strict: true`. No `@ts-ignore` or `as any` without a comment.
- Functional components only, one per file. `PascalCase.tsx` for components,
  `camelCase.ts` for hooks/utilities.
- React Query is the single source of truth for server state. No server data in `useState`.
- Tailwind utility classes only. No inline `style` except for values not expressible in Tailwind.
- All API calls through `src/api/client.ts`. All API types in `src/types/api.ts`.
- SSE streaming via `@microsoft/fetch-event-source` in `src/hooks/useChat.ts`.

### Logging

- Backend: stdlib `logging` with a console formatter. No structlog, no request-ID middleware,
  no `LOG_FORMAT` env var.
- One log event per significant action. Levels: `info` (normal), `warning` (recoverable),
  `error` (failures, unavailability).
- Never log: full LLM prompts or responses, API keys, full user message content, connection
  strings with passwords.
- ARQ jobs: one start line + one end line per job, no more.
- Frontend: `console.error(context, error)` only. No `console.log` in committed code.

### Commits and Branching

- Conventional Commits: `<type>(<scope>): <description>`.
  Types: `feat`, `fix`, `chore`, `docs`, `test`, `refactor`, `ci`.
- One PR per task. Merges to `main` via PR only after CI and QA pass.

### Testing

- LLM calls always mocked — never real calls in tests.
- Each test is independent: no shared state, no order dependency.
- Async tests: `pytest-asyncio` with `asyncio_mode = "auto"`.

### Definition of Done

- [ ] Implementation matches spec acceptance criteria
- [ ] Unit tests written alongside code
- [ ] QA integration tests pass against the running system
- [ ] `ruff` + `black` pass (backend); `eslint` + `tsc --noEmit` pass (frontend)
- [ ] No console errors or unhandled exceptions in normal flow
- [ ] `tracker.md` updated to `done`

A task is **not** done if tests pass but the feature doesn't work end-to-end, or tests only
cover the happy path when the spec calls out edge cases.

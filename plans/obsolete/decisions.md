# Decisions

> **AGENTS: Read this before writing any code.** Every meaningful architectural decision is recorded here with rationale. Do not contradict any decision without surfacing the conflict first. If you make a new significant decision during implementation, add it here.
>
> **Who reads this:** All agents. Dev agents must not deviate from these decisions without flagging the conflict. QA agents use this as context for why the system is shaped the way it is.
>
> **Doc workflow:** Per-task plans live in `docs/iteration-{N}/`. Spec → Dev → QA. QA never reads the dev doc.

---

## ADR-1: Python + FastAPI over Node/Express

**Decision:** Backend is Python 3.12 + FastAPI.

**Rationale:** The two most realistic alternatives for a take-home LLM app are Python/FastAPI and Node/Express (or Hono). Python wins here because:

- OpenAI's Python SDK is more mature than the TypeScript SDK for streaming and structured output edge cases.
- SQLAlchemy 2.0 async + Alembic is a well-understood pattern for schema management; Prisma or Drizzle in Node adds a layer of abstraction we don't control.
- `feedparser` (RSS parsing) has no Node equivalent with the same battle-tested surface area.
- `arq` (async job queue) is purpose-built for Python asyncio; Node alternatives (BullMQ) require more ceremony.
- The brief evaluates backend depth — Python signals LLM ecosystem familiarity.

**Rejected:** Node + Express/Hono. Would have been faster to bootstrap but the LLM + DB toolchain is weaker. Node escape hatch is documented in `plan.md` if Python proves problematic in Iteration 1.

---

## ADR-2: ARQ over Celery

**Decision:** Job queue is ARQ (async Redis queue). Worker is configured with `max_tries=1` — failed jobs are logged and dropped, no retry/backoff.

**Rationale:**

- ARQ is built on Python asyncio natively; Celery is WSGI-era and async support is bolted on, leading to subtle issues when mixing with SQLAlchemy async sessions and async OpenAI calls.
- ARQ workers share the same event loop and coroutine model as the FastAPI app, meaning the same async DB session factory and redis client work unchanged.
- Celery requires a separate result backend (usually Redis anyway) and a broker, adding config surface; ARQ uses Redis for both.
- For a single-machine Docker Compose project, ARQ's simplicity is a better fit than Celery's distributed-first design.

**Rejected:** Celery. Async story is messier. Not worth the extra config complexity for this scope.

**Rejected:** FastAPI background tasks (`BackgroundTasks`). These run in the same process/event loop as the API server; a slow or failing transform would degrade API responsiveness. (Retry behavior is no longer a differentiator — see `max_tries=1` above — but isolating LLM work from the request-serving event loop still motivates a separate worker process.)

---

## ADR-3: Hand-Written Alembic Migrations

**Decision:** All migrations are written by hand. `alembic revision --autogenerate` is not used.

**Rationale:**

- Autogenerate can miss complex constraints, partial indexes, and `CHECK` constraints. It also generates verbose diffs that don't read as intent.
- Hand-written migrations are self-documenting and reviewable. A future dev can read the migration history and understand schema evolution.
- For a known, bounded schema (4 tables, planned ahead in `contracts.md`), autogenerate provides no time savings.
- The assignment asks about the approach to migrations; hand-written shows deliberate thinking.

**Constraint:** `migrations/versions/` is empty in Iteration 0. First migration (1.1) creates the `source_type` Postgres enum and three tables — `articles` (originals only, ADR-5), `article_fakes` (1:1 with `articles`, PK = FK on `article_id`, ADR-5), and `chat_messages`. Sources are config-only and not migrated (ADR-16). The migration imports the `Source` `StrEnum` from `app/sources.py` to derive the enum's labels, so the Postgres enum and Python enum cannot drift.

---

## ADR-4: SSE over WebSockets for Chat Streaming

**Decision:** Chat streaming uses Server-Sent Events (SSE) via FastAPI `StreamingResponse`.

**Rationale:**

- SSE is unidirectional (server → client), which is exactly the streaming chat pattern: client sends one HTTP request, server streams tokens back. WebSockets provide bidirectional messaging we don't need.
- SSE uses plain HTTP — no upgrade handshake, no persistent socket management, no reconnect protocol to implement server-side.
- FastAPI's `StreamingResponse` handles SSE cleanly without additional libraries.
- `@microsoft/fetch-event-source` on the frontend handles reconnection, error states, and the `[DONE]` termination pattern well.
- WebSockets would require managing connection state server-side and adding a ws library. Not worth it for a unidirectional stream.

**Rejected:** WebSockets. Bidirectionality is unnecessary overhead for this pattern. Also requires CORS/proxy configuration that SSE avoids.

**Rejected:** Polling. Defeats the purpose of a streaming feel. Too much latency and backend load.

---

## ADR-5: 1:1 `article_fakes` Table (Originals and Satirical Versions in Separate Tables)

**Decision:** Original article content lives in `articles`. The LLM-generated satirical version lives in a separate `article_fakes` table with a strict 1:1 relationship to `articles`. The relationship is enforced at the schema level by making `article_fakes.article_id` simultaneously the **primary key and the foreign key** to `articles(id)` (with `ON DELETE CASCADE`). All columns on `article_fakes` are `NOT NULL`.

**Schema:**

```sql
CREATE TABLE articles (
    id            SERIAL PRIMARY KEY,
    source        source_type NOT NULL,
    title         TEXT NOT NULL,
    description   TEXT NOT NULL,
    url           TEXT NOT NULL UNIQUE,
    published_at  TIMESTAMPTZ,
    content_hash  CHAR(64) NOT NULL UNIQUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE article_fakes (
    article_id        INTEGER PRIMARY KEY REFERENCES articles(id) ON DELETE CASCADE,
    fake_title        TEXT NOT NULL,
    fake_description  TEXT NOT NULL,
    model             VARCHAR(100) NOT NULL,
    temperature       DOUBLE PRECISION NOT NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

The transformation worker `INSERT`s an `article_fakes` row when a fake is successfully generated. Re-running a transformation `UPDATE`s the existing row (or `INSERT`s if none exists yet). Failed transformations leave `article_fakes` empty for that article (see ADR-15).

**Rationale:**

- **Normalization correctness.** `model` and `temperature` describe the *transformation*, not the article. They belong on the same row as the fake content they describe.
- **State clarity.** "Row exists in `article_fakes`" = transformed. "No row" = not yet transformed (pending or permanently failed). No NULL columns conflating three different states.
- **Schema-enforced 1:1.** `PRIMARY KEY = FOREIGN KEY` makes "two fakes for one article" structurally impossible. No CHECK constraint or extra unique index needed.
- **Tighter constraints.** All four fake-side columns are `NOT NULL`. A nullable-columns-on-`articles` alternative cannot enforce this because the article row is inserted before the fake exists.
- **Hot path stays narrow.** The article feed query `LEFT JOIN`s `article_fakes` and emits the fake-side fields as `null` when no row exists; the originals table itself is never widened by transformation metadata.
- **Originals are structurally never overwritten.** `articles` is `INSERT`-only after creation (dedup via `INSERT ... ON CONFLICT (content_hash) DO NOTHING`). Re-runs only touch `article_fakes`.

**API response shape:**

`GET /api/articles` and `GET /api/articles/{id}` return a flat object — the `LEFT JOIN` result — with `fake_title`, `fake_description`, `model`, `temperature`, and `fake_created_at` all `null` when no `article_fakes` row exists. The frontend renders "Processing…" on `fake_title === null`. See [contracts.md](contracts.md) for the full shape.

**Rejected:** Single `articles` table with nullable `fake_*` columns. Loses 3NF correctness (transformation metadata sitting on the article row); encodes three states in NULL ("never tried" / "in flight" / "permanently failed"); cannot enforce `NOT NULL` on transformation metadata.

**Rejected:** 1:N `article_versions` table. Multi-version A/B is not in MVP scope (one prompt forever). The indirection (`latest_version`, version ordering, `is_latest` flags) is overhead with no consumer until prompt versioning actually ships. Migration path to 1:N is documented below.

**Rejected:** `prompt_version` / `prompt_hash` columns. With one prompt in MVP, both would be constants forever. If multi-prompt A/B lands later, reintroduce them then alongside the 1:N migration.

**Migration path if multi-prompt A/B is ever needed (Iteration 3 stretch task 3.6):**

1. Drop the PK constraint on `article_fakes(article_id)`.
2. Add `id SERIAL PRIMARY KEY` to `article_fakes`.
3. Add `prompt_version VARCHAR(50) NOT NULL` (or similar) and a unique index on `(article_id, prompt_version)`.
4. Update the read API to surface the latest fake by `MAX(created_at)` or by an explicit `is_latest` flag.

The cost is a real migration, paid only if and when prompt versioning actually ships.

---

## ADR-6: One Row per Chat Message

**Decision:** `chat_messages` stores one row per message (user or assistant), not per conversation.

**Rationale:**

- Chat history is reconstructed by ordering `chat_messages` by `created_at` for a given `article_id`. This is the simplest correct model.
- Storing the full conversation as a JSON blob in one row would make querying history harder and make individual message attribution impossible.
- Each message has a `role` (`user` | `assistant`) and timestamp, enabling chronological replay.
- Future auth extension (adding `user_id`) operates at the message level, not the conversation level.

**Rejected:** Storing conversation as JSON blob. Harder to extend, harder to query, harder to paginate.

---

## ADR-7: React Query for Server State, No Global Client State Library in MVP

**Decision:** TanStack Query (React Query) handles all server state. No Zustand or Redux in Iteration 1.

**Rationale:**

- React Query handles caching, background refetch, loading/error states, and optimistic updates — exactly what a data-fetching-heavy app needs.
- For MVP, the only shared client state is the selected source filter (held in URL query params) and the streaming chat state (local to the chat component). No cross-component client state justifies a store.
- Adding Zustand in Iteration 1 preemptively is overengineering. Iteration 2 task 2.8 explicitly reassesses if prop-drilling becomes a real problem.

**Rejected:** Redux Toolkit. Too much boilerplate for this scope. No time-travel debugging or middleware patterns needed.

**Deferred:** Zustand. Assessed in task 2.8. Introduce only if prop-drilling past 2 levels appears.

---

## ADR-8: No Vercel AI SDK

**Decision:** Chat streaming uses `@microsoft/fetch-event-source` + manual SSE parsing, not the Vercel AI SDK.

**Rationale:**

- The Vercel AI SDK abstracts over SSE in a way that would hide the streaming plumbing — which is precisely what the assignment evaluates.
- The AI SDK couples well to Vercel's deployment model. We're deploying via Docker Compose; the SDK's server-side helpers expect Next.js or Vercel edge functions.
- `@microsoft/fetch-event-source` is a thin, well-maintained SSE client that gives us full control over event parsing and reconnection behavior.
- The assignment brief mentions "streaming" as a key feature — showing we can implement it ourselves is the point.

**Rejected:** Vercel AI SDK. Abstracts away the exact thing we want to demonstrate understanding of.

---

## ADR-9: Redis Is the ARQ Broker Only (No LLM Response Cache)

**Decision:** Redis serves a single purpose: the ARQ job queue / broker. No LLM response cache, no application-level caching layer.

**Rationale:**

- The original MVP design also routed LLM responses through a Redis cache keyed by `SHA256(content_hash + prompt_version + model)`. With `INSERT … ON CONFLICT (content_hash) DO NOTHING` deduplicating articles upstream at the scrape layer (and one prompt + one model in MVP), no two transformation jobs can ever fire for the same `(content_hash, prompt, model)` tuple — the cache had no hit path. Removing it deletes the HIT/MISS branch in the worker, the `LLM_CACHE_TTL_SECONDS` env var, and the cache-key derivation, with zero cost-saving lost.
- Semantic similarity caching (chat answers based on cosine distance) is a different mechanism with a different key shape; it is deferred to `future_work.md` and is not what was being removed here.
- A single Redis service still backs ARQ. Docker Compose, service definition, and connection-string env var (`REDIS_URL`) are unchanged.

**Constraint:** If Redis goes down, the ARQ queue is unavailable; the scrape endpoint hard-fails with 503 (per `contracts.md`). The application read path (`GET /api/articles`) does not depend on Redis.

**Migration path if a cache is reintroduced:** if a future iteration profiles real cache savings (e.g. semantic chat cache, see `future_work.md`), reintroduce a `cache:*` key namespace at that point — no schema change required.

---

## ADR-10: Mock OpenAI in All Tests

**Decision:** OpenAI API calls are mocked in all tests (unit and integration).

**Rationale:**

- Real OpenAI calls in tests would incur cost on every CI run and introduce nondeterminism (model responses vary between runs, making assertions unreliable).
- Mocking forces explicit definition of what the system does with OpenAI's response — better test design.
- Tests should run in <60s total; real API calls would blow this budget.
- The mock fixture is set up in task 1.4 and reused across all tests that need it.

**Constraint:** The mock must return structurally valid responses (correct field names, types) — not just empty strings. Tests that assert on parsed content need realistic mock output.

---

## ADR-11: Shared Chat (No Per-User Identity in MVP)

**Decision:** Chat history is shared per article. There is no authentication or per-user chat isolation in MVP.

**Rationale:**

- The brief explicitly scopes this as a demo/assignment submission, not a multi-user product.
- Adding auth (session management, user table, JWT) is a significant scope increase that would crowd out the LLM pipeline and streaming work — which is what the brief evaluates.
- Shared-per-article chat is explicitly called out as the MVP behavior in the brief.

**Migration path (documented in `contracts.md`):** When auth is added, `user_id` column is added as nullable to `chat_messages`, backfilled with NULL for legacy messages, then made non-null once backfill is confirmed. No data is lost.

**Deferred to:** `future_work.md`

---

## ADR-12: `pgvector/pgvector:pg16` Image from Day One

**Decision:** The Postgres docker image is `pgvector/pgvector:pg16`, not the vanilla `postgres:16`.

**Rationale:**

- Iteration 3 adds similarity detection using `pgvector`. If we start with vanilla Postgres, switching images in Iteration 3 would require destroying and recreating the container with data migration — an unnecessary risk mid-project.
- Starting with the pgvector image is a no-op in Iterations 0-2 (the extension is not enabled, no vector columns exist). Cost: zero. Benefit: no migration pain later.
- `pgvector/pgvector:pg16` is an official extension of the postgres image, not a third-party fork.

**Constraint:** The pgvector extension must still be explicitly enabled via migration (`CREATE EXTENSION IF NOT EXISTS vector;`) in Iteration 3 — the image includes the extension but doesn't auto-enable it.

---

## ADR-13: Tailwind CSS over CSS Modules

**Decision:** Frontend styling uses Tailwind CSS v3.

**Rationale:**

- For a 2.5-day project with no designer, Tailwind's utility classes produce a consistent visual language faster than authoring CSS modules manually. Design tokens (spacing, colors, typography) are opinionated and built in.
- CSS modules require naming decisions per component and a separate `.module.css` file; Tailwind co-locates styles with JSX, reducing context-switching.
- Tailwind v3 (not v4) is used for stability — v4 is in beta and has breaking changes from v3's config format.
- The component library candidates (Radix UI, Headless UI) are designed to pair with Tailwind; CSS modules would require more glue.

**Rejected:** CSS modules. Slower to iterate on visual consistency from scratch.

**Rejected:** Tailwind v4. Breaking changes from v3, beta stability — not worth the risk on a deadline.

**Rejected:** Plain CSS. No scoping, high collision risk across components.

**Constraint:** `tailwind.config.js` must specify `content` paths correctly so purging doesn't remove utility classes used dynamically.

---

## ADR-14: PascalCase Component File Names (Override of iteration-0.md Brief)

**Decision:** Component files use PascalCase (`ArticleCard.tsx`, `ChatPanel.tsx`), not kebab-case.

**Rationale:** PascalCase for component files is the React ecosystem standard. The original iteration-0.md brief said "kebab-case files for components" — this was an error in the brief. `conventions.md` and `architecture.md` both use PascalCase throughout and are authoritative.

**Rejected:** kebab-case component files. Non-standard in the React ecosystem; creates a mismatch between the file name and the exported component name.

**Note:** iteration-0.md is the original project brief and is not updated. `conventions.md` and `architecture.md` take precedence on this point.

---

## ADR-15: Task 1.4 Final Failure Behavior — No `article_fakes` Row

**Decision:** On transformation job failure, log the error and do **not** insert an `article_fakes` row for that article. Combined with ADR-2's `max_tries=1`, this means: one attempt, fail, log, move on. The `articles` row itself is unchanged.

**Rationale:**

- Per ADR-5 the fake-side fields live in a separate `article_fakes` table with a strict 1:1 PK=FK relationship; "no row exists" naturally encodes "not yet transformed". A failed transformation simply does not insert.
- "No `article_fakes` row" is already a valid, handled state in the UI ("Processing…"). An article that permanently fails is indistinguishable from one still pending — acceptable for MVP.
- The failure is logged with `article_id` and error type, which is sufficient for debugging.
- Combined with ADR-2's single-try worker, this gives a deterministic "try once, log, drop" pipeline with no retry storm risk and no DLQ to manage.

**Rejected:** Option B (write a `transform_status` marker column on `articles` or `article_fakes`). Adds a column with no API consumer, plus a third UI state to handle, plus retry UI that is not in scope until Iteration 3+.

**Constraint:** If retry/requeue UI is added later, a `transform_status` column (or a separate `transform_attempts` table) becomes necessary, and this ADR updates accordingly.

---

## ADR-16: Sources as a Python `StrEnum` (Single Source of Truth, No `sources` Table)

**Decision:** Source identity is a Python `StrEnum` named `Source` in `backend/app/sources.py`. The Postgres enum type `source_type` is generated *from* that `StrEnum` (SQLAlchemy `sa.Enum(Source, name="source_type", values_callable=...)`), and the migration imports `Source` to derive the enum's labels. The same module exports `FEED_URLS: dict[Source, str]` mapping each enum member to its RSS URL. There is no `sources` DB table, no `enabled` toggle, no integer `source_id`, and no `source_name` denormalization. `articles.source` is a column of type `source_type` — the enum value IS the source identity in DB and in API responses.

**Rationale:**

- MVP scope is a fixed, hardcoded set of three sources (NYT, NPR, Guardian). There is no admin UI, no runtime CRUD, and no requirement to toggle sources without a restart.
- A `sources` DB table forces a seed migration, an `enabled` column, FK constraints, CRUD endpoints, and a `JOIN` for source_name on every read — all infrastructure with no MVP user-visible value.
- The Postgres enum gives DB-level validation (the column rejects any value outside the enum at INSERT time, no FK needed) and round-trips cleanly through JSON as a string.
- Using a Python `StrEnum` as the **single source of truth** removes the previous "config keys MUST match enum values" risk: `FEED_URLS` is `dict[Source, str]` (typed by the enum, not by free-form strings), the migration imports the same enum, and the SQLAlchemy column generates the Postgres enum from the same Python type. Drift between the two enums becomes unrepresentable — there is only one Python definition.
- Adding a source = one line in `Source` + one line in `FEED_URLS`, plus a migration that runs `ALTER TYPE source_type ADD VALUE 'NewName'`. Removing or renaming a source is treated as a real schema change.

**Rejected:** Two parallel definitions (a Python `dict[str, str]` SOURCES + a separately-declared `CREATE TYPE source_type AS ENUM (...)` in the migration). The original design — required a runtime startup-time check to assert keys matched labels. Replaced because the `StrEnum` makes drift impossible by construction; the runtime check is no longer necessary.

**Rejected:** `sources` DB table with `enabled` column (original iteration-0 design). Over-modeled for MVP.

**Rejected:** Integer `source_id` keyed by config order (intermediate design). Adds indirection and requires denormalized `source_name` in API responses; the enum gives validation without the indirection.

**Rejected:** `CHECK (source IN (...))` text column. Functionally close to an enum but harder to extend safely (renames are textual, no type-level guarantees in SQLAlchemy).

**Rejected:** `RSS_FEEDS` env-var override. The config module replaces its purpose. Removed from `contracts.md` and `architecture.md`.

**Note:** This ADR supersedes the iteration-0 design that placed sources in the DB. Task 1.1 brief is updated; existing 1.1 spec/dev/qa artifacts should be regenerated to match.

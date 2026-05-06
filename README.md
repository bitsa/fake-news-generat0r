# AutonomyAI — Fake News Generator

A take-home demo that scrapes RSS news feeds, transforms each article into a satirical "fake" version using OpenAI, and lets users chat about each article with streaming responses. The stack is FastAPI + ARQ + Postgres (pgvector) + Redis on the backend, and Vite + React + React Query on the frontend, all wired up via Docker Compose.

## Setup

```bash
git clone <repo-url>
cd fake-news-generator
cp .env.example .env
# Edit .env and replace OPENAI_API_KEY=sk-REPLACE_ME with a real key
docker compose up
```

The stack uses Docker Compose v2 (`docker compose`, with a space). The legacy v1 `docker-compose` CLI is not supported.

Once up:

- Backend: <http://localhost:8000>
- Frontend: <http://localhost:5173>

To tear down and remove the Postgres volume:

```bash
docker compose down -v
```

## Local dev workflow

Common operations are wrapped in the repo-root `Makefile`. Run `make help` to see the full list. Highlights:

- `make up` / `make up-d` / `make down` — bring the stack up (foreground / detached) and down (keeps volumes).
- `make down-clean` — `down -v`, drops the Postgres volume (destructive, prints a warning).
- `make health` — `curl localhost:8000/health` smoke check.
- `make backend-test` / `make backend-lint` / `make backend-format` — run pytest / ruff+black inside the backend container.
- `make backend-alembic ARGS="current"` — run Alembic subcommands inside the backend container.
- `make frontend-typecheck` — `tsc --noEmit` inside the frontend container.
- `make sync` / `make lock` — manage the host-side `backend/.venv` from `backend/uv.lock` (useful for IDE autocomplete).

## Environment variables

All environment variables are listed in [`.env.example`](./.env.example) with placeholder defaults and inline comments. The canonical schema (defaults, types, and meaning) lives in [`contracts.md`](./contracts.md) under the **Environment Variables** section. When adding a new variable, update `contracts.md` first, then `.env.example`.

`OPENAI_API_KEY` is the only variable that must be replaced before running; the rest have working defaults.

## Doc structure

The five shared docs at the repo root are the canonical source of truth — agents read them before writing any code:

- [`architecture.md`](./architecture.md) — components, services, data flow
- [`contracts.md`](./contracts.md) — DB schema, REST API shapes, TypeScript types, env vars
- [`conventions.md`](./conventions.md) — code style, logging, commit format, branching, testing
- [`decisions.md`](./decisions.md) — ADRs with rationale
- [`future_work.md`](./future_work.md) — explicit deferrals

[`tracker.md`](./tracker.md) tracks the status of every task across iterations 0–3.

Per-task documentation lives under `docs/iteration-{N}/`, with three files per task:

- `{task-id}-spec.md` — what to build (acceptance criteria)
- `{task-id}-dev.md` — how to build it (implementation plan)
- `{task-id}-qa.md` — how to verify it (test plan)

`plans/` holds the higher-level project brief, per-iteration outlines, and bootstrap session prompts.

# Conventions

> **AGENTS: Read this before writing any code.** These conventions apply to all code in this repository. If you violate one, you need a comment explaining why. If you discover a gap, surface it.
>
> **Who reads this:** All Dev agents. QA agents use this to understand logging and error formats they'll see when testing.
>
> **Doc workflow:** Per-task plans live in `docs/iteration-{N}/`. Spec → Dev → QA. QA never reads the dev doc.

---

## Python Conventions

### Type Hints

- Required on all function signatures (parameters + return types).
- Use `Optional[X]` only for function parameters with `None` defaults. Prefer `X | None` (Python 3.10+ union syntax) in return types and field definitions.
- No `Any` without a comment explaining why it's unavoidable.

### Async

- All I/O is async: database queries, HTTP calls, Redis operations.
- Use `async def` for any function that awaits I/O.
- Do not use `asyncio.run()` in application code (only in scripts/entrypoints).
- Use `AsyncSession` from SQLAlchemy — never `Session` (sync).

### Code Style

- Formatter: `black` (line length 88)
- Linter: `ruff` with rule sets `E`, `F`, `I`, `UP`. Adding more rule sets is a deliberate decision, not a default.
- Run both before committing. CI blocks on failures.
- Import order: stdlib → third-party → local (enforced by `ruff`)

### Naming

- Modules: `snake_case.py`
- Classes: `PascalCase`
- Functions, variables: `snake_case`
- Constants: `UPPER_SNAKE_CASE`
- Private helpers: `_prefixed_snake_case`

### Exception Hierarchy

All custom exceptions inherit from a base class in `app/exceptions.py`:

```python
class AppError(Exception):
    """Base for all application-level errors."""
    status_code: int = 500

class NotFoundError(AppError):
    status_code = 404

class ServiceUnavailableError(AppError):
    status_code = 503

class ValidationError(AppError):
    status_code = 422
```

FastAPI exception handlers in `app/main.py` catch `AppError` and return FastAPI's default error envelope (`{"detail": "..."}`) at the exception's `status_code` (see `contracts.md`). Never let domain exceptions bubble up as 500s when a more specific status applies.

### Configuration

- All config loaded via `Pydantic Settings` in `app/config.py`.
- `settings` is a module-level singleton imported wherever needed.
- Never read `os.environ` directly in application code — always go through `settings`.

---

## TypeScript Conventions

### Compiler

- `strict: true` in `tsconfig.json`. Non-negotiable.
- `noImplicitAny: true` (implied by strict).
- No `@ts-ignore` without a comment. No `as any` without a comment.

### Components

- Functional components only. No class components.
- One component per file.
- File names: `PascalCase.tsx` for components, `camelCase.ts` for hooks/utilities.
- Props interface named `{ComponentName}Props`.

### Hooks

- Extract any non-trivial logic into a custom hook (`use{Name}.ts` in `src/hooks/`).
- React Query hooks (`useQuery`, `useMutation`) are the single source of truth for server state. Do not store server data in `useState`.

### Styling

- Tailwind CSS v3 utility classes only. No inline `style` props except for dynamic values not expressible in Tailwind (e.g., dynamic widths from JS).
- No CSS-in-JS libraries. No `styled-components`.

### Fetch / API Calls

- All API calls go through `src/api/client.ts`. No `fetch()` calls scattered through components.
- SSE streaming uses `@microsoft/fetch-event-source` directly in `src/hooks/useChat.ts`.
- Types for all API responses are defined in `src/types/api.ts` and mirror `contracts.md` exactly.

---

## Logging Conventions

### Backend (`structlog`)

- Configured in `app/main.py` on startup via `configure_logging()` in `app/logging_config.py`, built on top of stdlib `logging`.
- Output format is selected by the `LOG_FORMAT` setting (`json` for shipped logs, `console` for local dev — default `console`).
- `RequestIdMiddleware` (`app/middleware.py`) generates or accepts an `X-Request-ID` per request and binds `request_id` into `structlog` contextvars, so every log line within a request carries the id automatically. The id is echoed back on the response.
- Use module-level loggers: `log = structlog.get_logger(__name__)`.

**Log one event per significant action:**

```python
log.info("scrape completed: source=%s count=%d duration_ms=%d", source, count, duration_ms)
log.info("transform completed: article_id=%d model=%s", article_id, model)
log.error("transform failed: article_id=%d error=%s", article_id, error)
log.error("db unavailable: %s", e)
```

**Log levels:**

- `info`: normal flow events (scrape completed, transform done, request handled)
- `warning`: recoverable issues (partial source failure, malformed feed entry skipped)
- `error`: unhandled exceptions, service unavailability, transform failure

**Never log:**

- Full LLM prompts or responses — log lengths or counts instead
- API keys or secrets — never, ever
- Full user message content — log `message_length` if you need to log anything
- Connection strings with passwords

**ARQ job logging:** Each job logs **one start line** (`transform start: article_id=...`) and **one end line** (`transform end: article_id=... status=ok|error`). No retry attempts (worker is `max_tries=1` per ADR-2), no cache hit/miss field (cache removed per ADR-9).

### Frontend

- `console.error(context, error)` for caught errors with enough context to reproduce.
- No `console.log` in committed code.
- No logging of user-typed content.

---

## Commit Format

[Conventional Commits](https://www.conventionalcommits.org/) — recommended format. Not enforced by CI in MVP; reviewers may flag drift in PRs.

```text
<type>(<scope>): <description>

[optional body]
```

**Types:** `feat`, `fix`, `chore`, `docs`, `test`, `refactor`, `ci`

**Examples:**

```text
feat(scrape): add deduplication via content_hash
fix(chat): close SSE connection on OpenAI timeout
chore(deps): pin sqlalchemy to 2.0.36
docs(contracts): add admin stats endpoint shape
test(articles): add pagination edge case coverage
```

**Scope** (optional): `scrape`, `chat`, `articles`, `worker`, `frontend`, `db`, `ci`, `contracts`

One task, one commit (or squash on merge). Do not mix concerns in a single commit.

---

## Branching

- `main` — always deployable. Direct pushes prohibited (Iteration 2 CI enforces this).
- Feature branches: `{iteration}-{task-id}/{short-description}` → e.g., `1-1.1/db-schema-migration`
- One PR per task. PR description links to the spec doc.
- Merges to main via PR only after all CI checks pass and the task's QA doc tests pass.

---

## Testing Conventions

- Test files: `tests/` at `backend/` root. Mirror the `app/` structure: `tests/routers/`, `tests/services/`, `tests/worker/`.
- Test file names: `test_{module}.py`.
- Fixtures in `tests/conftest.py` (session-scoped DB, OpenAI mock, ARQ test queue).
- OpenAI is always mocked in tests — never real calls. See ADR-10.
- Each test is independent: no shared state between tests, no order dependency.
- Async tests use `pytest-asyncio` with `asyncio_mode = "auto"` in `pyproject.toml`.

---

## Definition of Done (Per Task)

A task is done when:

- [ ] Implementation matches the spec doc's acceptance criteria
- [ ] Unit tests written inline with code (Dev agent responsibility)
- [ ] QA agent's integration tests pass against the running system
- [ ] `ruff` and `black` pass (backend); `eslint` and `tsc --noEmit` pass (frontend)
- [ ] No console errors or unhandled exceptions in normal flow
- [ ] `tracker.md` updated to `done`

A task is NOT done if:

- Tests pass but the feature doesn't work end-to-end
- Tests only cover the happy path when the spec calls out edge cases
- Implementation deviates from `contracts.md` without updating `contracts.md`

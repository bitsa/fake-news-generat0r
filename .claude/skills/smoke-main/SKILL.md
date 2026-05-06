---
name: smoke-main
description: End-to-end smoke verification of the latest merge on the local main branch. Brings the Docker stack up, watches logs, probes the API, and inspects the DB to confirm the merged feature actually works on a fresh environment. Trigger when the user asks to smoke-test, verify, or sanity-check a newly merged main (e.g. "smoke main", "/smoke-main", "verify the latest merge", "spin up dockers and check the merge"). Read-only against code; runs containers and SQL but does not modify migrations or source files.
---

You are running an end-to-end smoke verification of whatever just landed on
`main`. The goal is a confidence check on a developer machine: stack comes up,
the merged feature behaves, logs are clean, DB state is sane. Surface anything
unexpected — do not silently fix it.

This skill is project-specific. It assumes:

- `docker-compose.yml` at repo root with services: `postgres`, `redis`,
  `backend` (uvicorn @ :8000), `worker` (ARQ), `frontend` (Vite @ :5173).
- `Makefile` targets: `up-d`, `down`, `down-clean`, `logs`, `ps`, `health`.
- Postgres DB `fakenews` (user `fakenews`).
- `.env` present at repo root (mock mode is fine for smoke tests; flag if
  `OPENAI_MOCK_MODE` is unset or false and the merge looks like it exercises
  the OpenAI path).

## Step 1 — Identify the merge under test

- `git log --oneline -5` and `git log -1 --stat HEAD` to find the latest
  squashed/merged commit on `main`.
- Read every file in that commit's diff fully (routers, services, schemas,
  workers, migrations). Do not skim. The smoke probes you run in Step 4 must
  be informed by what *actually* changed, not a generic checklist.
- Build a short mental model: what new endpoint(s)/worker job(s)/DB
  column(s)/migration(s) does this merge introduce? That drives Step 4.

If the latest commit on main is `Initial commit` or has no app changes, say so
and stop.

## Step 2 — Bring the stack up

- `docker compose ps` — if all services are already up & healthy, reuse them
  and note "reused running stack" in the report.
- Otherwise `make up-d`, then poll until postgres + redis report healthy and
  backend `/health` returns 200. Do **not** sleep blindly; check status.
- If a container is unhealthy or restarting, capture its last ~50 log lines
  and stop the smoke run with a clear failure report — do not proceed.

Never run `make down-clean` automatically. That drops the postgres volume.
Only suggest it to the user if data state is clearly the blocker.

## Step 3 — Baseline log scan

- `docker compose logs backend 2>&1 | grep -iE "error|exception|traceback"`
  (filter out benign `WatchFiles detected changes` reload notices).
- Same for `worker`.
- Note any pre-existing errors so they aren't misattributed to your probes
  later.

## Step 4 — Feature probes (the important part)

Pick probes from the list below based on what Step 1 showed actually changed.
Don't run probes for components the merge didn't touch.

API endpoint added or changed:

- `curl -fsS -i` against the new path with realistic input.
- Validate response shape against the merged Pydantic schema (read
  `backend/app/schemas/`). Check pagination/ordering/filter semantics
  promised by the schema or the commit message.
- For `POST /api/scrape`: capture `inserted` vs `fetched`. 0 inserted just
  means duplicate detection is working — not a failure.
- For `GET /api/articles` (or any feed): confirm `total`, `pending`,
  ordering, sources represented, and that the schema's optional/required
  fields are honored.

Worker job added or changed:

- Tail `docker compose logs -f worker` while triggering the job.
- Confirm the job lifecycle: `→ enqueued`, `← completed ●`, no `failed`.
- For ARQ startup-recovery logic: check that any `pending` rows are picked
  up after a worker restart (`docker compose restart worker`).

DB schema changed (new migration, new column, new constraint):

- `docker compose exec -T postgres psql -U fakenews -d fakenews -c '\d
  <table>'` to confirm the column/constraint exists with the expected type.
- `psql -c "SELECT count(*), … FROM <table>"` for row-level sanity. The
  `sources` table does not exist — `Source` is a Postgres enum on
  `articles.source`. Don't query a `sources` table.
- For status fields: `GROUP BY <status>` and confirm no unexpected values.

Frontend route added or changed:

- Hit `http://localhost:5173/<route>` with curl for a 200 + non-empty body.
- If the merge changes API response shape consumed by the frontend, run
  `make frontend-typecheck` to catch TS drift.

End-to-end probe (always do this if the merge plausibly affects the pipeline):

- Toggle one row's transform_status to `pending` in `article_fakes`, hit the
  feed, confirm `pending` counter increments and the article is excluded.
  **Restore the row immediately after.** Use a single SQL block that flips
  and restores in one transaction if you can; if not, the restore is your
  responsibility — do not leave the DB dirty.

## Step 5 — Report

Produce one report with this structure:

```md
## Smoke Report — main @ <short-sha>

### Merge under test
- Commit: <sha> — <commit subject>
- Surface area: one-line description of what landed.

### Stack health
- Containers: which are up/healthy/restarted.
- /health: pass/fail.
- Migrations on startup: pass/fail (cite log line).

### Feature probes
For each probe, one entry:
  - **Probe:** what you ran (curl/psql/etc).
  - **Result:** pass/fail + the relevant evidence (status code, row count,
    a short JSON excerpt).
  - **Notes:** anything notable — e.g., mock-mode artifacts, expected
    duplicates.

### Anomalies
The "anything pop up unexpectedly" section. Each entry:
  - **What:** the unexpected thing in plain English.
  - **Where:** log line / SQL row / file:line.
  - **Severity:** blocking | worth-investigating | benign-but-noted.
  - **Hypothesis:** your best guess at the cause (don't fix it — flag it).

### Cleanup
Confirm any test-induced state has been reverted (e.g., the pending toggle
in Step 4). If anything was left dirty, say so explicitly.
```

## Rules

- Cite evidence for every claim: log lines, HTTP status, SQL row counts,
  file:line. No vague "looks fine".
- Do not edit source files, migrations, or `.env`. SQL writes are allowed
  only for transient probe state, and must be reverted in the same skill run.
- Mock-mode artifacts are expected (e.g., every fake article having the
  same canned title when `OPENAI_MOCK_MODE=true`). Note them once, don't
  treat them as bugs.
- If the merge changes behavior the smoke probes can't reach (e.g., a real
  OpenAI call gated behind mock mode), say so explicitly under Anomalies as
  "not exercised by this run" rather than implying coverage.
- Be terse. The reader will decide what to do — your job is observation,
  not remediation.

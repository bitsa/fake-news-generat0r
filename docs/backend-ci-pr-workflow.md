# Plan — Backend unit tests as a GitHub Actions PR check

## Context

The backend already has a healthy pytest suite under [backend/tests/unit/](../backend/tests/unit/) (16 files) plus integration tests under [backend/tests/integration/](../backend/tests/integration/). Locally everything runs inside the Docker stack via `make backend-test`, but there is no `.github/workflows/` directory — so today nothing enforces "tests must pass before merge." The user wants a CI gate that runs on every PR.

**TL;DR — it's very easy.** The unit tests don't need Postgres or Redis (the `conftest.py` only sets dummy env vars to satisfy `Settings` validation; tests mock the DB/Redis layer). So a single ~40-line workflow using `uv` is enough. No services, no Docker-in-CI gymnastics.

Integration tests are deferred — they require the full Docker stack and are slower, so they don't belong in the per-PR fast-feedback loop. Easy follow-up later if wanted.

## Scope

**In scope:**

- One new workflow file that runs on `pull_request` against `main`.
- Runs `pytest backend/tests/unit/` against Python 3.12 using `uv`.
- Adds `ruff check` + `black --check` as quick lint gates in the same job (cheap, already dev deps).

**Out of scope (deferred):**

- Integration tests (need Postgres + Redis services; separate workflow).
- Frontend typecheck (different stack).
- Markdown lint (already covered by the local `make docs-lint` convention).
- Coverage reporting, codecov upload, status badges.

## Files to create

- `.github/workflows/backend-ci.yml` — the new workflow (single file, no other changes needed).

## Workflow design

Triggers: `pull_request` with `types: [opened, synchronize, reopened]` and `branches: [main]`. Optionally also `push` on `main` to keep main green.

Single job `backend-unit`:

1. `actions/checkout@v4`
2. `astral-sh/setup-uv@v4` with `enable-cache: true` (caches `~/.cache/uv` keyed by `backend/uv.lock`)
3. `uv python install 3.12` (matches `requires-python = ">=3.12"` in [backend/pyproject.toml](../backend/pyproject.toml))
4. `uv sync --extra dev` in `backend/` (installs runtime + dev deps from [backend/uv.lock](../backend/uv.lock) — reproducible)
5. `uv run ruff check .`
6. `uv run black --check .`
7. `uv run pytest tests/unit/ -v`

All steps run with `working-directory: backend`. No service containers, no env vars beyond what `conftest.py` already sets.

Estimated runtime: cold ~60–90s, warm cache ~20–30s.

## Why uv and not pip

The project already uses uv (`backend/uv.lock` is the source of truth, `make sync` uses `uv sync --extra dev`). Mirroring local exactly avoids "works on my machine" drift, and `setup-uv` is faster than `pip install -r` with cache.

## Verification

Open the next PR — the `backend-unit` check should appear under the "Checks" tab and go green. That's the signal it's wired up correctly.

Optional follow-up (manual, in GitHub UI): Settings → Branches → add a branch protection rule on `main` requiring `backend-unit` to pass before merge.

## Risks / things to watch

- If any unit test secretly hits the network or a real DB, it'll fail in CI. Likely fine (the file names suggest pure logic + mocks), but the first PR run is the truth.
- `setup-uv` action is third-party (Astral, the uv authors) — pin to a major version (`@v4`) and dependabot can bump it.
- If `uv.lock` is ever stale vs `pyproject.toml`, `uv sync` will fail in CI. That's a feature, not a bug — forces lockfile discipline.

## Follow-ups (not in this plan)

- Add `backend-integration` workflow with `services: postgres / redis`, gated to `pull_request` but maybe only on `labeled` or path filters to avoid running on pure frontend PRs.
- Add frontend typecheck workflow.
- Add coverage reporting once baseline is stable.

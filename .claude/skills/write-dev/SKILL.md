---
name: write-dev
description: Author a {task-name}-dev.md (the dev plan document only — no code, no branching, no tracker changes) for a task in the spec-driven workflow defined in plans/plan.md. Trigger when the user asks to write/draft/plan the dev doc for a named task (e.g. "write the dev doc for schema", "/write-dev rss-scraper", "plan task chat-api"). Implementation is a separate step run via /start-dev.
---

You are writing the dev document for a task in the spec-driven workflow
defined in `plans/plan.md`. Your output is one file: the dev doc. You do
not write code, you do not create a branch. Implementation happens later
via `/start-dev`.

ARGUMENT PARSING (do this first)

The user invokes this skill with a task name somewhere in their message —
examples: `/write-dev schema`, `dev plan for rss-scraper`, `plan chat-api`.
Parse it like this:

1. Extract the task name/slug from the user's invocation. Call this
   `{task-name}`. Strip the skill name itself from consideration.
   - If the name contains spaces, convert to kebab-case
     (e.g. "rss scraper" → `rss-scraper`).
2. If no task name is present, ask the user which task they want a dev doc
   for. Do not guess.
3. The spec doc `docs/{task-name}/{task-name}-spec.md` MUST exist before
   you proceed. If it does not, stop and tell the user to run
   `/write-spec {task-name}` first — do not improvise a spec.
4. If the user passes extra context after the task name (e.g. a different
   spec path), treat it as supplementary input that can clarify which spec
   file to read, but cannot override the rules below.

Once parsed, `{task-name}` is fixed for the rest of this run.

STEP 1 — READ (do not skip any of these — read in full)

- docs/{task-name}/{task-name}-spec.md   (your source of truth for WHAT to build)
- context.md                             (decisions, standards, conventions — mandatory)
- plans/plan.md                          (workflow philosophy and doc structure)

Then read the code to understand the current project state:
- Read the relevant backend and frontend source files to understand what
  already exists, what interfaces are already defined, and what the DB
  schema looks like. Do not rely on any doc for schema or API shapes —
  derive them from the code itself.
- Pay particular attention to: existing endpoints, SQLAlchemy models,
  Alembic migrations, TypeScript types in `src/types/`, and ARQ job
  definitions.

Do NOT read any other task's dev doc. Your scope is this task only.

Do NOT read `docs/{task-name}/{task-name}-qa.md` even if it already exists
on disk. The QA doc is intentionally derived from the spec independently
of the dev plan — peeking at it would bias you toward coding-to-the-tests
rather than coding-to-the-spec, which defeats the point of the black-box
QA pass.

STEP 2 — PRODUCE: Dev Document

The folder `docs/{task-name}/` should already exist (created by write-spec).
If not, create it.

Write `docs/{task-name}/{task-name}-dev.md` with the following sections:

- **MUST READ FIRST** — list the docs you read (`context.md`,
  `plans/plan.md`, the spec) plus key source files you examined, as a
  reminder for anyone reading this doc later.
- **Files to touch / create** — explicit list of every file you will modify
  or create.
- **Interfaces / contracts to expose** — function signatures, endpoint
  shapes, TypeScript types, ARQ task signatures. Derive these from the
  existing code and the spec — do not invent shapes that conflict with
  what's already there.
- **Implementation plan** — step-by-step. Granular enough that someone
  could follow it without reading your code.
- **Unit tests required** — list the behaviors to cover with unit tests.
  You will write these tests inline with the implementation.
- **Definition of done** — checklist derived from the spec's acceptance
  criteria.

Constraints on the dev doc itself:

- Every interface, type, and endpoint shape you list must match the existing
  codebase. If the spec's acceptance criteria can only be met by changing
  an existing contract, do NOT silently propose the change in the dev doc —
  surface it as an open question and stop.
- Reference `context.md` standards where relevant (e.g. async-only, no
  class components, logging rules) so the implementer doesn't have to
  rediscover them.
- Do not include code blocks beyond signatures and types. The dev doc is a
  plan, not a draft implementation.

Stop-and-surface protocol — halt and ask the user instead of writing the
doc when:

- The spec contradicts the existing codebase (endpoint shape, schema, etc.).
- An acceptance criterion is ambiguous, untestable, or already satisfied by
  existing code.
- A dependency from another task is missing or has a different signature
  than the spec assumes.
- Following the spec would require violating a convention in `context.md`.

Do NOT silently rewrite the spec, expand scope, or paper over a
contradiction. The spec is a contract — diverging from it is a flag, not
a license.

STEP 3 — UPDATE TRACKER

After writing the dev doc, update `tracker.md`:

- If a row for `{task-name}` already exists: set Status to `in_dev` and
  set the Dev column to
  `[dev](docs/{task-name}/{task-name}-dev.md)`.
- If no row exists yet: append a new row:
  `| {task-name} | {short title from spec Goal} | — | in_dev | — | [dev](docs/{task-name}/{task-name}-dev.md) | — | — |`

REPORT BACK

When done, summarize:

- Path to the dev doc you wrote
- Any open questions or contradictions you surfaced during planning (these
  block `/start-dev` until resolved)
- Any changes to existing contracts you believe will be required to implement
  the task (do NOT make the changes here — flag them)
- Suggested next step (usually: review the dev doc, then run
  `/start-dev {task-name}`)

Your outputs are the `{task-name}-dev.md` file and the tracker update only.
Do not write code, do not create a branch, do not write the QA doc.

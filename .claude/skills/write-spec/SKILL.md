---
name: write-spec
description: Author exactly ONE {task-name}-spec.md for a single task in the spec-driven workflow defined in plans/plan.md. The task is identified by a name or slug provided by the user (e.g. "schema", "rss-scraper", "1.1"). Trigger ONLY when the user provides a specific task name like "spec schema", "/write-spec rss-scraper", "draft spec for chat-api". Do NOT trigger for vague requests without a task name — ask for one instead.
---

You are writing the spec document for a SINGLE task in the spec-driven
workflow defined in `plans/plan.md`.

CRITICAL CONSTRAINT: This skill produces exactly ONE spec file covering
exactly ONE task. Never write a spec that covers multiple tasks at once.

ARGUMENT PARSING (do this first)

The user invokes this skill with a task name somewhere in their message —
examples: `/write-spec schema`, `spec rss-scraper`, `draft spec for
chat-api`, `/write-spec 1.1`. Parse it like this:

1. Extract the task name/slug from the user's invocation. It is the token
   (or short phrase) that identifies the task — e.g. `schema`,
   `rss-scraper`, `chat-api`, `1.1`. Call this `{task-name}`.
   - Strip the skill name itself (`write-spec`) from consideration.
   - If the name contains spaces, convert to a kebab-case slug
     (e.g. "rss scraper" → `rss-scraper`).
2. If no task name is present (e.g. user said only "write a spec" with no
   target), stop immediately and ask: "Which task? Please provide a name
   or slug (e.g. 'schema', 'rss-scraper')."
3. If the user provides additional context after the task name (e.g. a
   description of the task, or a file to read for scope), treat that as
   supplementary input. It can describe the task or override which file
   to read, but cannot override the doc structure or rules below.
4. If no task description is present in the prompt and no file is pointed
   to, ask: "What should the `{task-name}` task accomplish? Please describe
   the scope or point me to where it's defined."

Once parsed, `{task-name}` is fixed for the rest of this run.
The output file will be: `docs/{task-name}/{task-name}-spec.md`.

STEP 1 — READ (do not skip any of these)

Read these files in full before writing anything:

- context.md              (decisions, standards, architecture — read first)
- plans/assignment.md     (project brief and requirements)
- plans/plan.md           (doc structure, workflow, philosophy)

Then read the code to understand the current state of the project:
- Skim the backend and frontend source trees to understand what is already
  built, what interfaces are exposed, and what DB schema exists. You need
  this to scope the task correctly — do not assume the codebase matches
  what earlier docs describe.

SCOPE REMINDER: You are writing a spec for `{task-name}` only.
Do not include acceptance criteria, scope, or goals from any other task.

STEP 2 — PRODUCE

Create the folder `docs/{task-name}/` if it does not exist.

Write `docs/{task-name}/{task-name}-spec.md` following the Spec Doc
structure from `plans/plan.md`:

- **Source** — cite where the task scope came from (user's prompt, a
  referenced file, or a section of `plans/plan.md`). Quote the scope
  verbatim if helpful. This anchors the spec and prevents paraphrase drift.
- **Goal** — one concise paragraph. What does this task accomplish and
  why does it matter?
- **User-facing behavior** — what does someone interacting with the running
  system observe? Describe it from the outside, not the implementation.
- **Acceptance criteria** — bulleted, testable conditions. Each criterion
  must be verifiable without reading any implementation code. QA agents
  will derive their tests directly from this list.
- **Out of scope** — explicit non-goals. Name things that might seem
  related but are deferred.
- **Open questions / assumptions** — anything that required a judgment call
  or that a human should sign off on before implementation begins. Flag
  ambiguities rather than silently resolve them.

STEP 3 — SELF-CHECK

Before declaring done:

1. Verify every acceptance criterion is testable by a QA agent who has NOT
   read any implementation code.
2. Verify every API shape or schema detail you reference matches the actual
   code — check the source, not memory or old docs.
3. Verify the task is scoped within what's already built — does it assume
   anything not yet implemented?
4. Confirm the spec does not describe HOW to implement — only WHAT to
   deliver and how to verify it.

STEP 4 — UPDATE TRACKER

After writing the spec doc, update `tracker.md`:

- If a row for `{task-name}` already exists: set Status to `spec'd` and
  set the Spec column to
  `[spec](docs/{task-name}/{task-name}-spec.md)`.
- If no row exists yet: append a new row:
  `| {task-name} | {short title from spec Goal} | — | spec'd | [spec](docs/{task-name}/{task-name}-spec.md) | — | — | — |`

REPORT BACK

When done, summarize:

- Which open questions you surfaced (for human review before dev begins)
- Any inconsistencies you found between the task description and the
  current codebase state
- Your suggested acceptance criterion order for QA (highest-risk first)

Your outputs are the spec doc and the tracker update only.
Do not implement code, do not write the dev doc, do not run tests.

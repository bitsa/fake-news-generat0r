---
name: spec-update
description: Update the five canonical spec documents (architecture.md, contracts.md, conventions.md, decisions.md, future_work.md) so they reflect reality after the feature work on the current branch. Use when the user asks to update specs, sync docs to code, record an ADR, or absorb branch changes into the docs. Edits only those five files; flows code → docs, never the reverse.
---

You are updating this project's five canonical specification documents so
they reflect reality after the feature work just completed on the current
branch. The goal is to prevent drift: as code lands, the docs must absorb
any new contracts, conventions, decisions, components, or deferrals that
the work introduced.

The five documents (in repo root) you are allowed to edit:

1. architecture.md   — components, data flows, Docker Compose services,
                       directory structures.
2. contracts.md      — DB schema, REST endpoints (request/response shapes),
                       TypeScript types, env vars.
3. conventions.md    — Python + TypeScript style, logging rules, commit
                       format, branching, testing, definition of done.
4. decisions.md      — ADRs with rationale and rejected alternatives.
5. future_work.md    — explicitly deferred items + Loom talking track.

You may NOT edit any other file. You may NOT change code to match docs —
this skill flows in the opposite direction (code → docs).

Step 1 — Establish what changed on this branch.

- Run: git diff $(git merge-base HEAD main)..HEAD
    (fall back to origin/main, master, or origin/master if main is missing)
- Run: git log --oneline $(git merge-base HEAD main)..HEAD
- Read every changed file fully.

Step 2 — Read all five spec documents fully before editing any of them.

Step 3 — Decide, per document, what (if anything) needs to change. Apply
this rubric:

  contracts.md — update when the branch:
    - adds/removes/alters a DB column, table, index, or constraint
    - adds/changes a REST endpoint, request body, or response shape
    - introduces or modifies a TypeScript type that mirrors backend data
    - adds, removes, or changes the meaning of an env var
    Always keep the SQL DDL, request/response examples, TS types, and env
    var list in sync with each other.

  architecture.md — update when the branch:
    - adds a new service, worker, or process
    - changes the data flow for scrape pipeline, read feed, or chat streaming
    - adds a Docker Compose service, port, or network
    - reshapes backend/ or frontend/ directory layout
    Update the ASCII diagram if components/connections change. Keep the
    three flow walkthroughs accurate.

  conventions.md — update when the branch:
    - establishes a new convention that future code should follow (e.g., a
      new error pattern, logging key, test fixture style)
    - tightens or relaxes a rule and the user has accepted that change
    Do NOT add convention entries based on a single occurrence. Add only
    when this is meant to be the rule going forward.

  decisions.md — update when the branch:
    - made a non-trivial choice that future agents shouldn't silently
      reverse (library choice, architectural shape, schema strategy, etc.)
    Add a new ADR with the next sequential number, following the existing
    format exactly:
      ## ADR-N: <Title>
      **Decision:** ...
      **Rationale:** ...
      **Rejected:** ...
    If the branch contradicts an existing ADR, do NOT silently rewrite
    the ADR. Stop and surface the conflict to the user.

  future_work.md — update when the branch:
    - implements something previously listed as deferred → remove that item
    - consciously defers something new → add it under the right section
    - changes priority of the Loom talking track top items
    Keep the Loom Talking Track block compressed and ordered by priority.

Step 4 — Make the edits. For each doc you change:

- Preserve the document's existing tone, heading style, and section order.
- Place new entries in the correct section, not at the bottom.
- Update cross-references if you rename a thing (e.g., if you rename an
    env var in contracts.md, search the other four docs for stale mentions).
- Keep examples runnable and types compilable — these docs are read as
    spec, not prose.

Step 5 — Produce a short change log at the end of your turn:

## Spec Doc Update Summary

- **architecture.md:** <one-line summary, or "no changes">
- **contracts.md:**    <one-line summary, or "no changes">
- **conventions.md:**  <one-line summary, or "no changes">
- **decisions.md:**    <one-line summary, or "no changes" — name new ADR #s>
- **future_work.md:**  <one-line summary, or "no changes">

### Conflicts surfaced (not auto-resolved)

  Anything where the branch contradicts an existing spec entry and the
  human needs to decide which side wins. Leave the existing doc untouched
  for these; just list them here.

Rules:

- Edit only the five named files. Nothing else.
- Never delete an ADR. ADRs are append-only; supersede with a new ADR if
  needed.
- Do not invent rationale. If the branch made a choice and the reasoning
  isn't in the commit messages or PR description, ask the user instead of
  guessing.
- If the branch has no diff against the base, say so and stop without edits.
- Be conservative: a single ad-hoc occurrence is not a convention; a
  refactor isn't an ADR unless it locks in a direction.

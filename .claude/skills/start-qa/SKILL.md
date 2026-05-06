---
name: start-qa
description: Run the QA phase for a task whose {task-id}-qa.md already exists and whose tracker status is `in_qa`. Runs the unit tests the dev wrote, audits coverage against the QA doc's coverage map, captures every failure or gap as a structured issue file, and sets the tracker to `done` or `blocked`. Trigger when the user asks to start/run/execute QA for a numbered task (e.g. "start qa on 1.3", "/start-qa 2.1", "run qa for 1.4", "execute qa 3.2").
---

You are running the QA phase for a task whose QA coverage map has already
been written (via `/write-qa`) and whose dev work has landed (tracker shows
`in_qa`). Your job is to run the existing unit tests, audit coverage against
the QA doc, capture every failure and gap as a well-structured issue file,
and update the tracker based on results.

You do NOT write new test code. If tests are missing, that is a gap — record
it as an issue and surface it. Do not patch the gap yourself.

ARGUMENT PARSING (do this first)

The user invokes this skill with a task identifier somewhere in their
message — examples: `/start-qa 1.3`, `run qa for task 2.1`, `execute
qa 3.4`. Parse it like this:

1. Scan the user's invocation for the first token matching the regex
   `\d+\.\d+`. That is the `{task-id}`.
2. The integer portion before the dot is the iteration number `{N}`.
3. If no `\d+\.\d+` token is present, ask the user which task to QA.
   Do not guess.
4. Preconditions — verify before doing anything else:
   - `docs/iteration-{N}/{task-id}-qa.md` MUST exist. If it does not,
     stop and tell the user to run `/write-qa {task-id}` first.
   - `tracker.md` must show this task as `in_qa`. If it shows
     anything else (`in_dev`, `done`, `blocked`, missing), stop and
     ask the user to confirm before proceeding.
5. Supplementary text after the task id is treated as clarifications only.
   It cannot loosen the rules below.

STEP 1 — READ

Read these files in full before doing anything else:

- `docs/iteration-{N}/{task-id}-qa.md`   (coverage map — your source of truth for what must pass)
- `docs/iteration-{N}/{task-id}-spec.md` (acceptance criteria — the source of truth for pass/fail)
- `context.md`                           (standards and conventions)

You MAY now read the existing test files and implementation code to
understand what is on disk. You must NOT modify implementation code or
test code under any circumstances — QA verifies, it does not patch.

STEP 2 — AUDIT COVERAGE GAPS

Before running any tests, scan the QA doc's coverage map for any criterion
marked **UNCOVERED**. For each uncovered criterion:

- Write an issue file immediately (see issue format in STEP 3).
- Severity: **critical** — a missing test for a spec criterion always blocks.
- Do not attempt to write the missing test. Record the gap and continue.

If the coverage map has zero UNCOVERED entries, proceed to STEP 3.

STEP 3 — RUN TESTS AND CAPTURE ISSUES

Run the test suite using the exact command stated in the QA doc's
"Pass / fail criteria" section (typically `pytest backend/tests/unit/ -v`).

For every test failure, and for every observed behavior that diverges from
the spec, write a dedicated issue file. Do NOT lump multiple issues into one
file. Do NOT report failures in chat only — the file is the durable artifact.

Issue file location and naming:

- Directory: `docs/iteration-{N}/issues/` (create if missing)
- Filename: `{task-id}-{NN}-{short-slug}.md`
  - `{NN}` is a zero-padded sequential issue number for this task,
    starting at `01`. Continue numbering past any pre-existing issue
    files for the same `{task-id}`.
  - `{short-slug}` is kebab-case, ≤40 chars, lowercase ASCII,
    summarizing the failure (e.g. `null-author-on-empty-feed`).
  - Example: `docs/iteration-1/issues/1.3-02-stream-cuts-off-mid-token.md`

Issue file structure (use these exact headings in this exact order):

```markdown
# {Task ID} Issue {NN}: {one-line summary}

**Task:** {task-id} — {task title from spec}
**Spec criterion violated:** {quote the exact acceptance criterion line, or "n/a — emergent behavior"}
**Severity:** minor | medium | critical
**Status:** open
**Found by:** /start-qa
**Date:** {YYYY-MM-DD}

## What happened
{2–4 sentence description of observed behavior}

## What was expected
{What the spec / context.md says should have happened. Cite the doc + section.}

## Reproduction steps
1. {Numbered, deterministic steps. Include exact request payloads, DB seeds, env state.}
2. ...
3. Observed: {literal observed output, error message, response body, or log excerpt}

## Environment
- Test file: {path to the test that surfaced this}
- Test name: {function name}
- Logs / traceback: {paste relevant lines}

## Suggested next action
{One of:
 - "Fix in implementation — see {file:line} for the likely culprit area."
 - "Clarify spec — acceptance criterion ambiguous; needs human decision."
 - "Add missing test — criterion was UNCOVERED in QA doc."
 - "Defer — note in future_work.md."}
```

Severity rubric (apply consistently):

- **critical** — blocks at least one acceptance criterion outright; the
  feature cannot be considered shipped. Examples: test failure on the
  golden path, missing test for a spec criterion, data integrity violation,
  schema drift that breaks a contract.
- **medium** — behavior diverges from spec but the feature is partially
  usable. Examples: edge case mishandled, error message mis-formatted,
  off-by-one, incorrect default value.
- **minor** — cosmetic or non-functional drift that doesn't affect any
  acceptance criterion. Examples: log key naming inconsistency, harmless
  redundant field.

The "Reproduction steps" section is required for every critical and medium
issue. For purely cosmetic minors it can be brief, but never omitted.

Do not edit implementation code or test code to make a test pass. Do not
soften a test to match observed-but-wrong behavior. Surface the discrepancy
via an issue file.

STEP 4 — UPDATE TRACKER

After all tests have been run and issue files (if any) have been written:

- If all tests pass and no issue files were written: set this task's
  status to `done` in `tracker.md`.
- If any critical issue was written: set status to `blocked`. Add a Notes
  entry listing the critical issue filenames.
- If only medium/minor issues were written (no critical): leave status as
  `in_qa`, add a Notes entry listing the issue filenames and severities,
  and explicitly ask the user whether to mark `done` (accept the drift)
  or `blocked` (require fixes first).

REPORT BACK

When done, summarize:

- Tests run / passed / failed
- Coverage gaps found (UNCOVERED criteria), if any
- Issues written, listed by filename and severity
- Any acceptance criteria that could not be tested and why
- Final tracker status: `done`, `blocked`, or `in_qa (awaiting user)`

Do not modify the spec, the dev doc, the QA doc, or implementation code.
Do not push the branch. Do not open a PR. Your outputs are the issue files
(one per problem) and the tracker status update only.

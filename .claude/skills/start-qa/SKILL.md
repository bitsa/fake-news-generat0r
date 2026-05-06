---
name: start-qa
description: Run the QA implementation phase for an iteration task whose {task-id}-qa.md already exists and whose tracker status is `in_qa`. Implements the tests described in the QA doc (with OpenAI mocked), captures every failure as a structured issue file under docs/iteration-{N}/issues/, and sets the tracker to `done` or `blocked`. Full-stack Docker Compose integration tests are out of scope for this skill — they are deferred to iteration 3 task 3.8. Trigger when the user asks to start/run/execute QA for a numbered task (e.g. "start qa on 1.3", "/start-qa 2.1", "run qa for 1.4", "execute qa 3.2").
---

You are running the QA implementation phase for a task whose QA plan
has already been written (via `/write-qa`) and whose dev work has
landed (tracker shows `in_qa`). Your job is to implement and execute
the tests described in the QA doc, capture every failure as a
well-structured issue file, and update the tracker based on results.

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
5. Supplementary text after the task id is treated as overrides /
   clarifications. It cannot loosen the rules below.

STEP 1 — READ

Read these files in full before writing any test code:

- docs/iteration-{N}/{task-id}-qa.md     (your test plan — implement exactly this)
- docs/iteration-{N}/{task-id}-spec.md   (acceptance criteria — the source of truth for pass/fail)
- contracts.md                           (API shapes and DB schema for contract validation)
- conventions.md                         (logging/error/test fixture conventions)

You MAY now read the implementation code under `backend/` and
`frontend/` — at this stage, that's how you wire up the tests. You
must NOT modify implementation code under any circumstances; QA
verifies, it does not patch.

STEP 2 — IMPLEMENT TESTS

Implement the tests described in the QA doc. Test requirements:

- **Do NOT write full-stack Docker Compose integration tests in this
  skill.** Those are deferred to iteration 3 task 3.8. In-process tests
  (FastAPI `TestClient` + test DB session for backend, Vitest / RTL
  for frontend) are the right level here.
- API contract tests validate response shapes against `contracts.md`
  field-for-field.
- OpenAI must be mocked — never real API calls.
- Tests must be deterministic (no time-based flakiness, no order
  dependency, no reliance on external network).
- Total backend QA suite must run in under 60s.
- Follow `conventions.md` for test layout and fixture style.

If the QA doc is missing a detail you need (a fixture shape, a mock
response payload, a setup step), prefer to derive it from the spec or
`contracts.md` rather than the implementation. If you find yourself
copying behavior FROM the implementation TO the test, that's a bug —
the test must encode the spec, not the impl.

STEP 3 — RUN TESTS AND CAPTURE ISSUES

Run the test suite. For every failure or every observed behavior that
diverges from the spec, write a dedicated issue file. Do NOT lump
multiple issues into one file. Do NOT just report failures in chat
without writing the file — the file is the durable artifact.

Issue file location and naming:

- Directory: `docs/iteration-{N}/issues/`  (create if missing)
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
{What the spec / contracts.md / conventions.md says should have happened. Cite the doc + section.}

## Reproduction steps
1. {Numbered, deterministic steps. Include exact request payloads, DB seeds, env state.}
2. ...
3. Observed: {literal observed output, error message, response body, screenshot path, or log excerpt}

## Environment
- Stack: Docker Compose (services running: ...)
- Test file: {path to the test that surfaced this}
- Test name: {function name or describe block}
- Logs / traceback: {paste relevant lines, or "see attached" with a path}

## Suggested next action
{One of:
 - "Fix in implementation — see {file:line} for the likely culprit area."
 - "Clarify spec — acceptance criterion ambiguous; needs human decision."
 - "Update contracts.md — observed behavior may be the correct one."
 - "Defer — see future_work.md."}
```

Severity rubric (apply consistently):

- **critical** — blocks at least one acceptance criterion outright; the
  feature cannot be considered shipped. Examples: 500 errors on the
  golden path, data corruption, secrets logged in plaintext, auth
  bypass, schema drift that breaks contracts.md consumers.
- **medium** — behavior diverges from spec but the feature is partially
  usable. Examples: edge case mishandled, error message mis-formatted,
  pagination off-by-one, retry behavior incorrect under failure.
- **minor** — cosmetic or non-functional drift, or a missing-but-nice
  detail that doesn't affect any acceptance criterion. Examples:
  log key naming inconsistency, whitespace in response, redundant
  field that's harmless.

The "Reproduction steps" section is required for every critical and
medium issue. For purely cosmetic minors, it can be brief ("observed
in test output, see {test path}"), but never omitted entirely.

Do not edit implementation code to make a test pass. Do not soften a
test to match observed-but-wrong behavior. Surface the discrepancy
via an issue file.

STEP 4 — UPDATE TRACKER

After all tests have been run and issue files (if any) have been
written:

- If all tests pass and no issue files were written: set this task's
  status to `done` in `tracker.md`. Set the QA column to link
  `docs/iteration-{N}/{task-id}-qa.md`.
- If any critical issue was written: set status to `blocked`. Add a
  Notes entry listing the critical issue filenames.
- If only medium/minor issues were written (no critical): the call is
  the user's, not yours. Leave the status as `in_qa`, write a Notes
  entry listing the issue filenames and severities, and explicitly
  ask the user in your report whether to mark `done` (accept the
  drift) or `blocked` (require fixes).

REPORT BACK

When done, summarize:

- Tests run / passed / failed
- Issues written, listed by filename + severity (e.g.
  `1.3-01-x.md (critical)`, `1.3-02-y.md (medium)`)
- Any acceptance criteria that could not be tested at all (and why)
- Any spec ambiguities that made writing a clean test impossible
- Final tracker status: `done`, `blocked`, or `in_qa (awaiting user)`

Do not modify the spec, the dev doc, the QA doc, or implementation
code. Do not push the branch. Do not open a PR. Your output is the
test files, the issue files (one per problem), and the final
tracker status only.

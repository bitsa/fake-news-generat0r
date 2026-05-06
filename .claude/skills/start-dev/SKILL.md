---
name: start-dev
description: Kick off the implementation phase for an iteration task that already has a {task-id}-dev.md. Reads the five root spec docs (architecture.md, contracts.md, conventions.md, decisions.md, future_work.md) plus the dev doc, surfaces any open questions, and only if there are none — creates feature/{task-id}-{slug} branched from main and starts implementing. Trigger when the user asks to start/begin/kick off a numbered task (e.g. "start dev on 1.3", "/start-dev 2.1", "begin implementing task 1.4", "kick off 3.2").
---

You are starting the implementation phase for a task whose dev doc has
already been written and approved. Your job is to read the relevant
context, decide whether the task is unambiguous enough to proceed, and
either ask clarifying questions OR cut a feature branch and begin
implementing.

ARGUMENT PARSING (do this first)

The user invokes this skill with a task identifier somewhere in their
message — examples: `/start-dev 1.3`, `start dev on task 2.1`, `kick off
3.4`. Parse it like this:

1. Scan the user's invocation for the first token matching the regex
   `\d+\.\d+`. That is the `{task-id}`.
2. The integer portion before the dot is the iteration number `{N}`.
   - Example: `1.3` → N=1, task-id=1.3
   - Example: `2.10` → N=2, task-id=2.10
3. If no `\d+\.\d+` token is present, ask the user which task to start.
   Do not guess.
4. The dev doc `docs/iteration-{N}/{task-id}-dev.md` MUST exist. If it
   does not, stop and tell the user to run `/write-dev {task-id}` first
   (or to create the dev doc manually). Do not improvise.
5. Supplementary text after the task id is treated as overrides /
   clarifications (e.g., a non-default base branch, a hint about the
   slug). It cannot override the safety rules below.

STEP 1 — READ (do not skip)

Read these files in full before doing anything else:

- docs/iteration-{N}/{task-id}-dev.md   (the implementation plan you will follow)
- docs/iteration-{N}/{task-id}-spec.md  (if present — the contract the dev doc was written against)
- architecture.md                       (component boundaries, data flows)
- contracts.md                          (schema, API shapes, env vars — hard constraint)
- conventions.md                        (code style, logging, error handling, testing)
- decisions.md                          (do not contradict any ADR)
- future_work.md                        (do not implement anything explicitly deferred here)

Do NOT read `docs/iteration-{N}/{task-id}-qa.md` even if it already exists
on disk. The QA doc is a black-box derivation of the spec; peeking at it
would bias your implementation toward coding-to-the-tests rather than
coding-to-the-spec/dev-doc, defeating the point of the independent QA
pass. Your sources of truth are the dev doc, the spec, and the five root
docs above — nothing else from `docs/iteration-{N}/`. Do not open, grep,
or infer the contents of the QA doc.

STEP 2 — DECIDE: questions or go?

Before touching git or code, list any open questions or ambiguities. A
"question" is anything the dev doc + the five specs cannot resolve on
their own:

- The dev doc references a function/type/endpoint that is not in
  contracts.md or in any earlier task's interfaces.
- An acceptance criterion in the spec is ambiguous or untestable.
- The dev doc contradicts an ADR or a contract.
- A required dependency from a prior task does not exist or has a
  different signature than the dev doc assumes.
- The dev doc leaves a non-trivial design choice unstated.

Decision rule:

- If you have ANY questions, list them in a numbered block and STOP.
  Do not branch. Do not write code. Wait for the user to answer.
- If you have NO questions, proceed to STEP 3.

When in doubt, ask. A 30-second clarification is cheaper than a
half-built branch on the wrong assumption.

STEP 3 — CUT THE FEATURE BRANCH

Preconditions (verify each — abort with a clear message if any fail):

1. The working tree is clean. Run `git status --porcelain`; if output is
   non-empty, stop and tell the user to commit or stash first.
2. A base branch exists. Try `main` first, then fall back in order to
   `origin/main`, `master`, `origin/master`. Use the first one that
   resolves. If none exist, stop and ask.
3. You are not already on a feature branch with uncommitted intent for
   this task. If the current branch matches `feature/{task-id}-*`, ask
   the user whether to continue on it instead of creating a new one.

Branch naming:

- Format: `feature/{task-id}-{slug}`
- `{slug}` is a short, kebab-cased summary derived from the dev doc's
  title or its primary deliverable. Keep it under ~40 chars. Strip
  filler words (the, a, of, for). Use lowercase ASCII only.
- Example: dev doc titled "1.3 — Scrape Orchestrator + Endpoint" →
  `feature/1.3-scrape-orchestrator`

Commands:

1. `git fetch origin` (best-effort — if it fails because there is no
   remote, continue silently).
2. `git checkout {base-branch}` then `git pull --ff-only` if a remote
   tracking branch exists. If `--ff-only` would fail, stop and ask
   rather than reconciling automatically.
3. `git checkout -b feature/{task-id}-{slug}`

Confirm to the user: "Branched `feature/{task-id}-{slug}` from
`{base-branch}` at `{short-sha}`."

STEP 4 — IMPLEMENT

Follow the dev doc step-by-step. Constraints inherited from the
spec-driven workflow:

- Every contract in `contracts.md` is a hard constraint. If your
  implementation requires a contract change, update `contracts.md` and
  call it out in your report.
- Follow `conventions.md` strictly. `ruff`, `black`, `eslint`,
  `tsc --noEmit` must pass.
- Write unit tests inline as you implement (not after). Mock OpenAI in
  all tests.
- Do not implement anything out of scope for this task. If you discover
  a missing dependency from another task, note it and stop — do not
  speculatively implement it.
- Do not commit or push unless the user asks. Leave the work staged or
  uncommitted at the end so the user can review the diff before
  committing.

Stop-and-surface protocol — when to halt instead of patching:

- The dev doc contradicts `contracts.md`, `architecture.md`, or
  `decisions.md`. → Stop. Report.
- An acceptance criterion is ambiguous, untestable, or already
  satisfied by existing code. → Stop. Report.
- A dependency from another task is missing or has a different
  signature than the dev doc assumes. → Stop. Report.
- Implementing as specified would require violating a convention. →
  Stop. Report.

Do NOT silently rewrite the dev doc, expand scope, or add "while I'm
here" cleanups.

STEP 5 — UPDATE TRACKER

Once implementation is complete and lint/typecheck/unit tests pass,
update `tracker.md`:

- Set this task's status to `in_qa`.
- Set the Spec column to link `docs/iteration-{N}/{task-id}-spec.md`
  (if the spec doc exists).
- Set the Dev column to link `docs/iteration-{N}/{task-id}-dev.md`.

If you stopped under the stop-and-surface protocol instead of finishing,
do NOT update the tracker — leave it in its prior state and report the
blocker.

STEP 6 — REPORT BACK

When done (or stopped), summarize:

- Branch created (name, base, sha)
- Files created/modified
- Any deviations from the dev doc and why
- Any changes made to `contracts.md` and why
- Lint/typecheck/test status (`ruff`/`black` for backend, `eslint`/`tsc`
  for frontend, unit tests passing)
- Any open questions or assumptions surfaced during implementation
- Suggested next step (e.g. "review the diff and commit", or "answer
  open questions before continuing")

Then ALWAYS append a final block titled `## Commit & PR scaffolding` with
exactly these three subsections, in this order, regardless of whether the
task succeeded or stopped under the stop-and-surface protocol:

1. **Commit message** — a Conventional Commits subject line (`<type>(<scope>):
   <description>`, ≤72 chars) followed by a short body paragraph (2–4 lines)
   that explains the *why*, not the *what*. Render inside a fenced ```text
   block so the user can copy it verbatim.
2. **PR title** — same Conventional Commits subject as the commit, on its own
   line. Inline code-fenced.
3. **PR short description** — a fenced ```markdown block containing a
   `## Summary` section (2–4 bullets) and a `## Test plan` section (checklist
   of what the reviewer should verify, including lint/test commands and any
   manual smoke checks).

If the task stopped before implementation finished, still produce these
three artifacts, but scope them to the partial work actually on the branch
(or note "no commit yet — blocker unresolved" in the commit body).

Do not write the QA doc, do not run QA tests, do not push the branch,
do not open a PR, do not run `git commit` yourself — your output is the
feature branch with the implementation, accompanying unit tests, and the
commit/PR scaffolding text for the user to use.

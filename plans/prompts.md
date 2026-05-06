# Agent Prompt Templates

These are the three reusable prompts for the spec-driven, agent-orchestrated workflow described in `plan.md`. Each task in an iteration produces three artifacts in order:

```text
docs/iteration-{N}/{task-id}-spec.md   ← Prompt 1 produces this
docs/iteration-{N}/{task-id}-dev.md    ← Prompt 2 produces this
docs/iteration-{N}/{task-id}-qa.md     ← Prompt 3 produces this
```

**Rules:**

- Do not dispatch Prompt 2 until you have reviewed and approved the spec.
- Do not dispatch Prompt 3 until the dev agent reports `in_qa` in `tracker.md`.
- QA agents NEVER read the dev doc — black-box testing only.
- Replace all `{placeholders}` before pasting.

---

## Prompt 1 — Write Spec

> Dispatch this to a fresh agent. Replace `{N}` with the iteration number and `{task-id}` with the task ID (e.g., `1.3`).

```text
You are writing the spec document for task {task-id} of Iteration {N}.

STEP 1 — READ (do not skip any of these)

Read these files in full before writing anything:
- plans/plan.md                 (doc structure, workflow, philosophy)
- plans/iteration-{N}.md        (find the section for task {task-id} — this is your primary input)
- plans/iteration-1.md          (context for downstream tasks if N > 1)
- plans/iteration-2.md          (same)
- plans/iteration-3.md          (same)
- contracts.md                  (schema and API shapes the spec must reference accurately)
- architecture.md               (system shape — scope your task correctly within it)
- decisions.md                  (do not contradict any decision; if the task touches a decision, reference it)

STEP 2 — PRODUCE

Write `docs/iteration-{N}/{task-id}-spec.md` following the Spec Doc structure from `plan.md`:

- **Source** — cite the exact section/heading in `plans/iteration-{N}.md` that this spec expands on (e.g., "Iteration 1, Task 1.3 — Scrape Orchestrator + Endpoint"). Quote the spec scope verbatim if helpful. This anchors the spec in the original brief and prevents paraphrase drift.
- **Goal** — one concise paragraph. What does this task accomplish and why does it matter at this point in the iteration?
- **User-facing behavior** — what does someone interacting with the running system observe? Describe it from the outside, not the implementation.
- **Acceptance criteria** — bulleted, testable conditions. Each criterion must be verifiable without reading any implementation code. QA agents will derive their tests directly from this list.
- **Out of scope** — explicit non-goals. Name things that might seem related but are deferred (with a reference to where they live, e.g., "See task 2.X" or "See future_work.md").
- **Open questions / assumptions** — anything that required a judgment call or that a human should sign off on before implementation begins. Flag ambiguities rather than silently resolve them.

STEP 3 — SELF-CHECK

Before declaring done:
1. Verify every acceptance criterion is testable by a QA agent who has NOT read any implementation code.
2. Verify every schema or API shape you reference matches `contracts.md` exactly (same field names, same types).
3. Verify the task is scoped within what's already built — does it assume anything from a later task?
4. Confirm the spec does not describe HOW to implement — only WHAT to deliver and how to verify it.

REPORT BACK

When done, summarize:
- Which open questions you surfaced (for human review before dev begins)
- Any inconsistencies you found between `iteration-{N}.md` and `contracts.md` / `architecture.md`
- Your suggested acceptance criterion order for QA (highest-risk criteria first)
```

---

## Prompt 2 — Write Dev Plan + Implement

> Dispatch this to a fresh agent AFTER you have reviewed and approved the spec. Replace `{N}` and `{task-id}`.

```text
You are implementing task {task-id} of Iteration {N}.

STEP 1 — READ (do not skip any of these — read in full)

- docs/iteration-{N}/{task-id}-spec.md   (your source of truth for WHAT to build)
- contracts.md                           (schema, API shapes, env vars — do not deviate)
- architecture.md                        (component boundaries, data flows)
- decisions.md                           (do not contradict; if you must, surface the conflict first)
- conventions.md                         (code style, logging, error handling, testing — mandatory)

Do NOT read any other task's dev doc. Your scope is this task only.

STEP 2 — PRODUCE: Dev Document

Write `docs/iteration-{N}/{task-id}-dev.md` with the following sections:

- **MUST READ FIRST** — list the docs you read (contracts.md, architecture.md, decisions.md, conventions.md) as a reminder for anyone reading this doc later.
- **Files to touch / create** — explicit list of every file you will modify or create.
- **Interfaces / contracts to expose** — function signatures, endpoint shapes, TypeScript types, ARQ task signatures. These become the contract surface for other tasks.
- **Implementation plan** — step-by-step. Granular enough that someone could follow it without reading your code.
- **Unit tests required** — list the behaviors to cover with unit tests. You will write these tests inline with the implementation.
- **Definition of done** — checklist derived from the spec's acceptance criteria.

STEP 3 — IMPLEMENT

Implement the task following the dev document you just wrote.

Constraints:
- Every contract in `contracts.md` is a hard constraint. If your implementation requires a change to contracts.md, update contracts.md and call it out in your report.
- Follow `conventions.md` strictly. `ruff`, `black`, `eslint`, `tsc --noEmit` must pass.
- Write unit tests inline as you implement (not after). Mock OpenAI in all tests.
- Do not implement anything out of scope for this task. If you discover a dependency that doesn't exist yet, note it in your report rather than implementing it speculatively.

Stop-and-surface protocol — when to halt instead of patching:
- The spec contradicts `contracts.md`, `architecture.md`, or `decisions.md`. → Stop. Report the conflict.
- An acceptance criterion turns out to be ambiguous, untestable, or already satisfied by existing code. → Stop. Report.
- A dependency from another task is missing or has a different signature than the spec assumes. → Stop. Report.
- Implementing as specified would require violating a convention (e.g., logging secrets to satisfy a "log everything" criterion). → Stop. Report.

Do NOT silently rewrite the spec, expand scope, or add "while I'm here" cleanups. The spec is a contract — diverging from it is a flag, not a license.

STEP 4 — UPDATE TRACKER

Update `tracker.md`:
- Set this task's status to `in_qa`.
- Set Spec column to link `docs/iteration-{N}/{task-id}-spec.md`.
- Set Dev column to link `docs/iteration-{N}/{task-id}-dev.md`.

REPORT BACK

When done, summarize:
- What you built (files created/modified)
- Any deviations from the spec and why
- Any changes made to `contracts.md` and why
- Any open questions or assumptions made during implementation
- Confirmation that `ruff`/`black` (backend) or `eslint`/`tsc` (frontend) pass
- Confirmation that unit tests pass
```

---

## Prompt 3 — Write QA Plan + Implement Tests

> Dispatch this to a fresh agent AFTER the dev agent has set tracker status to `in_qa`. Replace `{N}` and `{task-id}`.

```text
You are a black-box QA agent for task {task-id} of Iteration {N}. Your role enforces a hard separation: you verify behavior against the spec without seeing how it was built. This separation is the entire reason the workflow has a spec/dev/QA split — preserve it strictly.

CRITICAL RULE: You must NOT read `docs/iteration-{N}/{task-id}-dev.md` or any implementation files before writing your test plan. Black-box testing only — your tests verify behavior against the spec, not against the implementation. Reading the dev doc would bias your tests toward the implementation and defeat the purpose.

STEP 1 — READ (only these — nothing else)

- docs/iteration-{N}/{task-id}-spec.md   (your ONLY source of truth for what to test)
- contracts.md                           (API shapes and DB schema for contract testing)
- conventions.md                         (understand logging/error formats you'll encounter)

Do not read the dev doc. Do not read implementation source files before writing the test plan.

STEP 2 — PRODUCE: QA Document

Write `docs/iteration-{N}/{task-id}-qa.md` with the following sections:

- **What to test** — map each acceptance criterion from the spec 1-to-1 to a test case. Every criterion gets at least one test. Number them to match the spec's criteria list.
- **How to test** — for each test case: is it an integration test (against running services), an API contract test (shape validation), or a manual verification step? Describe the exact test method.
- **Test data setup** — fixtures, seed data, mocked responses needed. Describe what the DB state must look like before each test runs.
- **Edge cases to cover** — derived from the spec's acceptance criteria and "out of scope" list, NOT from reading the implementation. What could go wrong based on the spec alone?
- **Pass / fail criteria** — what does "QA passes" mean for this task? Define it precisely.

STEP 3 — IMPLEMENT TESTS

Now you may read the implementation code. Implement the tests described in your QA document.

Test requirements:
- Integration tests run against the full Docker Compose stack (real Postgres, real Redis, mocked OpenAI).
- API contract tests validate response shapes against `contracts.md` field-for-field.
- OpenAI must be mocked — never real calls.
- Tests must be deterministic (no time-based flakiness, no order dependency).
- All tests must pass within the CI time budget (60s total backend suite).

STEP 4 — UPDATE TRACKER

- If all tests pass: set task status to `done` in `tracker.md`. Set QA column to link `docs/iteration-{N}/{task-id}-qa.md`.
- If tests reveal behavior that diverges from the spec: set status to `blocked`. Add a Notes entry describing exactly which acceptance criterion failed and what the observed behavior was. Do NOT change the spec or the tests to match incorrect behavior — surface the discrepancy.

REPORT BACK

When done, summarize:
- Test results: how many pass, how many fail
- Any acceptance criteria that could not be verified (and why)
- Any behavior you observed that contradicts the spec (list criterion + observed vs. expected)
- Any gaps you found in the spec's acceptance criteria that made testing ambiguous
- Final tracker status: `done` or `blocked`
```

Skills :

spec phase:   /write-spec  →  spec doc only
              /write-dev   →  dev doc only
              /start-dev   →  feature branch + impl + unit tests + tracker:in_qa

qa phase:     /write-qa    →  qa doc only
              /start-qa    →  test impl + issue files + tracker:done|blocked|in_qa

post-merge:   /spec-audit  →  read-only drift report
              /spec-update →  sync 5 root docs to reality

---
name: chat-llm-01 AC25 soft gap — no suite-wide network egress guard
description: AC25 (no test makes a real OpenAI call) is satisfied by per-test convention only; no autouse fixture or sandbox check enforces it across the suite.
type: qa-issue
---

# chat-llm Issue 01: AC25 satisfied by convention only — no suite-wide guard against real OpenAI egress

**Task:** chat-llm — Chat — real OpenAI streaming (replaces mock generator + adds prompt builder)
**Spec criterion violated:** AC25 — "No test in the suite makes a real outbound OpenAI request (per `context.md` 'Mock LLM in All Tests')."
**Severity:** medium
**Status:** accepted (option a — convention-only coverage accepted; capture in decisions.md / future_work.md via /spec-update)
**Found by:** /start-qa
**Date:** 2026-05-07

## What happened

Every real-path test in `backend/tests/unit/test_chat_llm.py` patches
`openai.AsyncOpenAI` locally and substitutes a fake stream, so in
practice the suite makes no outbound HTTP request to `api.openai.com`.
However, there is no test, autouse fixture, or CI-level sandbox check
that enforces this property at the *suite* level. AC25's coverage is
therefore convention-only: a future test that exercises the real path
without applying the per-test patch would silently issue a real OpenAI
request and AC25 would still appear "green".

The QA coverage map already flagged this explicitly under "Gap
analysis" and routed it to the QA phase for an explicit decision.

## What was expected

`docs/chat-llm/chat-llm-spec.md` AC25 and `context.md` "Mock LLM in
All Tests" require that no test in the suite makes a real outbound
OpenAI request. The QA doc's "Pass / fail criteria" #1 makes pass
contingent on "an explicit decision on that item" rather than silent
acceptance. The spec wants a property that holds for the suite, not
just for the tests that happened to remember to patch.

## Reproduction steps

1. Inspect `backend/tests/unit/test_chat_llm.py` — every real-path
   test instantiates the OpenAI client only after a `patch("openai.AsyncOpenAI", ...)`
   is in effect.
2. Search the test tree for any autouse fixture or session-scoped
   guard that fails the test if the real `openai.AsyncOpenAI` is
   instantiated:

   ```bash
   grep -rn "AsyncOpenAI" backend/tests/ backend/conftest.py 2>/dev/null
   grep -rn "autouse" backend/tests/ 2>/dev/null
   ```

   Observed: no such fixture exists. The only references to
   `AsyncOpenAI` are the per-test `patch(...)` calls inside individual
   test functions.
3. Hypothetical regression: a new test added under the real-call path
   that forgets to apply the patch would attempt a real network call
   if `OPENAI_API_KEY` is populated and `chat_llm_mock=false`. No
   existing test would fail to surface this.

## Environment

- Test file: `backend/tests/unit/test_chat_llm.py` (entire file —
  AC25 is suite-level, not local to one test)
- Test name: n/a (no mapped test asserts the suite-level property)
- Logs / traceback: n/a — this is a coverage gap, not a runtime
  failure. The mapped suite passed 50/50 with ruff + black clean on
  touched files.

## Suggested next action

Clarify spec / accept drift — acceptance criterion is technically
satisfied in practice (per-test patching is consistent and
`chat_llm_mock=true` is the suite-wide default) but is convention-only
at the suite level. Two options for the user to choose between, both
already enumerated in the QA doc's Gap analysis:

- **(a) Accept convention-only coverage** and mark this drift in
  `decisions.md` / `future_work.md` so future contributors know the
  guarantee is held by every author rather than by tooling. Tracker
  moves to `done`.
- **(b) Require a hardening pass** that adds an autouse fixture (or
  conftest hook) which fails any test that instantiates the real
  `openai.AsyncOpenAI` class without it being patched. This would
  shift the property from convention to enforced. Tracker stays
  `blocked` until that fixture lands.

Recommendation: option (a) for this iteration, given the
`chat_llm_mock=true` default plus the consistent per-test patching
already in place; capture (b) as an entry in `future_work.md` so the
guard can be added when the suite grows.

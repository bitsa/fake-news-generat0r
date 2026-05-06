# Fake News Generator — Master Plan

## Project Summary

Full-stack app that scrapes real news articles from RSS feeds, transforms them into satirical versions via OpenAI, displays them in a news-feed UI, and provides a per-article streaming chat interface. Submitted as a take-home assignment with a 2.5-day budget.

## Stack (Locked Decisions)

The root doc [`context.md`](../context.md) is the source of truth for stack choices, decisions, and standards. The table below is the locked stack; **Backend = Python + FastAPI**. Any change to a locked layer must be proposed as an iteration-level exception, accepted, and recorded in `context.md` before any code change.

| Layer | Choice |
|---|---|
| Frontend | React + TypeScript + Vite |
| Backend | Python + FastAPI |
| ORM | SQLAlchemy 2.0 + Alembic (hand-written migrations) |
| Database | PostgreSQL |
| Cache / Queue | Redis (ARQ for jobs, plus LLM response cache) |
| Async Jobs | ARQ |
| LLM | OpenAI Python SDK (model names via env vars) |
| Streaming | FastAPI `StreamingResponse` (SSE) + `@microsoft/fetch-event-source` on frontend |
| Server State | TanStack Query (React Query) |
| Client State | Local `useState` in MVP; Zustand if needed in Iter 2 |
| Container | Docker Compose |
| CI | GitHub Actions (added in Iteration 2) |

## Philosophy

- **Vertical slicing.** Every iteration produces a working end-to-end product.
- **Walking skeleton first.** Iteration 1 wires every architectural component end-to-end with minimum viable depth. If anything isn't working at the end of Iter 1, foundations are wrong.
- **Spec-driven, agent-orchestrated.** Each task gets a spec, dev plan, and QA plan. Agents work sequentially, single repo.
- **Black-box QA.** QA agents read only the spec + contracts, never the dev plan. Tests verify behavior against requirements, not implementation.
- **Shared context prevents drift.** `context.md` is read first by every agent.

## Iteration Map

| Iteration | Goal | Estimated Time |
|---|---|---|
| **0 — Foundations** | Repo scaffold, shared docs, Docker Compose skeleton, empty migrations, env wiring | ~2-3 hours |
| **1 — Walking Skeleton** | All 3 sources → ARQ pipeline → DB → API → React feed → SSE chat. End-to-end working, minimal depth. | ~8-10 hours |
| **2 — Depth + CI** | Filtering, original-toggle, error handling, integration tests, GitHub Actions, structured logging, polish | ~5-6 hours |
| **3 — Bonuses** | Streaming polish, scheduled scraping, similarity detection (pgvector), stretch items | ~4-5 hours |

Total target: ~20 hours of focused work over 2.5 days.

## Document Structure (Per Task)

Each task in an iteration produces three artifacts:

```text
docs/
  iteration-{N}/
    {task-id}-spec.md       # Source of truth: what + why + acceptance criteria
    {task-id}-dev.md        # Implementation plan: files to touch, contracts to expose
    {task-id}-qa.md         # Test plan derived from spec ONLY (no dev access)
```

### Spec Doc

- **Goal** — one paragraph
- **User-facing behavior** — what someone interacting with the system observes
- **Acceptance criteria** — bulleted, testable conditions
- **Out of scope** — explicit non-goals to prevent scope creep
- **Open questions / assumptions** — surfaced for sign-off

### Dev Doc (consumed by Dev agent + Spec doc + shared docs)

- **MUST READ FIRST** — links to `context.md`
- **Files to touch / create** — explicit list
- **Interfaces / contracts to expose** — function signatures, endpoint shapes, types
- **Implementation plan** — step-by-step
- **Unit tests required** — behaviors to cover (Dev writes these inline with code)
- **Definition of done** — checklist

### QA Doc (consumed by QA agent + Spec doc + contracts.md ONLY — never dev doc)

- **What to test** — mapped 1-to-1 from acceptance criteria
- **How to test** — integration tests against running services, API contract tests, manual verification steps
- **Test data setup** — fixtures, mocked OpenAI responses
- **Edge cases to cover** — derived from spec, not implementation

## Shared Documents (Iteration 0 deliverables)

- **`context.md`** — key concepts, decisions, and standards. Read before writing any code.
- **`future_work.md`** — explicit "would do with more time" list (Loom talking points)

## Tracker Schema (`tracker.md`)

```markdown
| Task ID | Title | Iteration | Status | Spec | Dev | QA | Notes |
|---------|-------|-----------|--------|------|-----|----|----|
```

**Status values:** `not_started` / `spec'd` / `in_dev` / `in_qa` / `done` / `blocked`

Spec/Dev/QA columns link to their respective files. Notes column captures blockers and decisions made mid-task.

## Workflow Per Task

1. **You write spec** (or have an agent write a draft, you review)
2. Update tracker: `spec'd`
3. **Dev agent reads:** spec + dev doc + shared docs → implements + writes unit tests
4. Update tracker: `in_dev` → `in_qa`
5. **QA agent reads:** spec + contracts ONLY → writes integration/API/E2E tests against running system
6. You review both outputs, run tests, accept or iterate
7. Update tracker: `done`

## Risk Mitigation

- **Hard checkpoint at end of Iteration 1.** If walking skeleton isn't working end-to-end, stop and fix foundations before moving to Iter 2.
- **Mock OpenAI in tests** to prevent CI cost burn and flakiness.
- **Commit early, commit often.** Each task = its own PR (or at least its own commit) so you can roll back cleanly.

## What's NOT in This Plan

- Detailed code-level implementation (that's the agents' job, derived from dev docs)
- Visual design specifics (style "enough to be usable" per brief)
- Authentication / multi-user (out of scope per brief)
- Production deployment (Docker Compose is the deliverable)

See `future_work.md` for what's deferred.

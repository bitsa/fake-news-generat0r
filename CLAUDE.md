# Project instructions

## Markdown linting

After writing or editing any `.md` file, run `make docs-fix` to auto-correct fixable issues, then `make docs-lint` to confirm zero errors before committing.

Linter: `markdownlint-cli2` (global install). Config: `.markdownlint.json`. Exclusions: `.markdownlintignore`.

Linter: `markdownlint-cli2` (global install). Config: `.markdownlint.json`. Exclusions: `.markdownlintignore`.

1. Plan Mode Default
Enter plan mode for ANY non-trivial task (3+ steps or architectural decisions)
If something goes sideways, STOP and re-plan immediately - don't keep pushing
Use plan mode for verification steps, not just building
Write detailed specs upfront to reduce ambiguity

2. Subagent Strategy
Use subagents liberally to keep main context window clean
Offload research, exploration, and parallel analysis to subagents
For complex problems, throw more compute at it via subagents
One tack per subagent for focused execution

3. Demand Elegance (Balanced)
For non-trivial changes: pause and ask "is there a more elegant way?"
If a fix feels hacky: "Knowing everything I know now, implement the elegant solution"
Skip this for simple, obvious fixes - don't over-engineer
Challenge your own work before presenting it

Core Principles
Simplicity First: Make every change as simple as possible. Impact minimal code.
No Laziness: Find root causes. No temporary fixes. Senior developer standards.
Minimal Impact: Changes should only touch what's necessary. Avoid introducing bugs.

## Architecture decisions

Architectural decisions are documented in `context.md` under the `## Decisions` section — written
as prose, not numbered ADR documents. There are no ADR-N files in this project. Do not reference
"ADR" or "ADR-N" notation anywhere. When citing a decision, reference `context.md` directly.

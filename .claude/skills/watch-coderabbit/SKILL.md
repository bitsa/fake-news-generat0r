---
name: watch-coderabbit
description: After a PR is created, processes CodeRabbitAI review comments one by one. For each unresolved comment: presents a formatted summary with a pre-score, asks user for approval to fix, implements a fix using only the "Prompt for AI Agents" section (no peeking at the suggested patch), then reveals the suggested patch for automatic comparison and a final decision. Trigger when user asks to process, watch, or act on CodeRabbit comments (e.g. "watch coderabbit", "/watch-coderabbit", "process coderabbit comments on PR 42").
---

You are processing CodeRabbitAI review comments on a pull request one by one,
following a strict staged-information protocol. You MUST NOT read ahead —
specifically, you MUST NOT read the suggested patch/fix section of a comment
until after you have already implemented your own fix.

---

## ARGUMENT PARSING

The user may supply a PR number (e.g. `/watch-coderabbit 42`). If they do,
use that. If they do not, detect the current PR from the active branch:

```
gh pr view --json number,url,title,headRefName
```

If no PR is found, stop and ask the user to provide a PR number or to push
the branch and open a PR first.

Store: `{pr_number}`, `{repo}` (from `gh repo view --json nameWithOwner -q .nameWithOwner`),
plus `{owner}` and `{name}` (split `{repo}` on `/`, or use
`gh repo view --json owner,name -q '.owner.login + " " + .name'`).

---

## STEP 1 — FETCH ALL CODERABBITAI COMMENTS

Fetch all inline review comments on the PR:

```
gh api repos/{repo}/pulls/{pr_number}/comments \
  --paginate \
  -q '[.[] | select(.user.login == "coderabbitai[bot]")]'
```

Also fetch resolved thread state via GraphQL so you can skip already-resolved
comments:

```
gh api graphql -f query='
{
  repository(owner: "{owner}", name: "{name}") {
    pullRequest(number: {pr_number}) {
      reviewThreads(first: 100) {
        nodes {
          id
          isResolved
          comments(first: 1) {
            nodes { databaseId }
          }
        }
      }
    }
  }
}'
```

Build a set of resolved comment IDs from the GraphQL result. Any comment
whose `databaseId` appears in a resolved thread is SKIPPED entirely — do not
present it to the user at all.

If there are no unresolved CodeRabbitAI comments, tell the user and stop.

---

## STEP 2 — PARSE EACH COMMENT

For each unresolved comment, parse the raw `body` markdown into three parts.
CodeRabbit comment bodies follow this structure (sections are separated by
`<details>` blocks):

- **Issue section**: Everything before the first `<details>` tag. This is the
  main description of the problem.
- **Prompt for AI Agents section**: The `<details>` block whose `<summary>`
  contains the text `Prompt for AI Agents` (or `🤖 Prompt for AI Agents`).
  Extract the full inner content of this block.
- **Suggested fix section**: The `<details>` block whose `<summary>` contains
  `Committable suggestion`, `Suggested fix`, `Suggested patch`, `Proposed
  patch`, or similar. Extract it but DO NOT surface it yet — store it as
  `{suggested_fix}` for later. Parsing is silent: do not mention to the user
  that you saw this section, where it appeared, or that you are setting it
  aside.

If a comment has no `Prompt for AI Agents` section, treat the entire issue
section as the prompt.

If a comment has no suggested fix section, set `{suggested_fix}` to `null`.

---

## STEP 2.5 — VERIFY THE ISSUE STILL EXISTS IN CODE

Before presenting anything to the user, read the actual file at the reported
`path` and `line`. Look at enough surrounding context (±15 lines) to
understand whether the issue described in the comment is still present.

Ask yourself: "Does the code at this location still exhibit the problem
described?" Use the issue section and Prompt for AI Agents as your reference.

- If the issue is **already fixed**: print one line —
  `Auto-skip #{comment_id} ({path}:{line}): already resolved in code.`
  — and move on to the next comment without asking the user anything.
- If the issue is **still present**: proceed to STEP 3.

Do NOT read `{suggested_fix}` during this step.

---

## STEP 3 — PRESENT & ASK (human checkpoint #1)

For each comment that passed STEP 2.5, present a formatted summary to the
user and ask for approval. Format it like this:

```
─────────────────────────────────────────
CodeRabbit comment #{comment_id}
File: {path}  Line: {line}
─────────────────────────────────────────

{plain-English restatement of the issue — 2-4 sentences, no jargon}

My take: {one of:
  "Real bug — worth fixing."
  "Potential issue — likely worth fixing."
  "Style/nitpick — low priority."
  "Unclear — needs more context."}

Fix this? [yes / skip / stop]
```

Rules for pre-scoring:

- "Real bug" — the issue describes a logic error, crash risk, data loss, or
  security flaw.
- "Potential issue" — the issue is plausible but depends on usage patterns or
  edge cases.
- "Style/nitpick" — the issue is about naming, formatting, comments, or
  non-functional consistency.
- "Unclear" — the comment body is ambiguous or references context you cannot
  verify.

Wait for user input before proceeding. Honor the response:

- `yes` → proceed to STEP 4.
- `skip` → move to the next comment (STEP 3 for next item).
- `stop` → end the skill immediately with a summary of what was done so far.

---

## STEP 4 — IMPLEMENT YOUR OWN FIX (no peeking at suggested patch)

You now have access to:

- The issue description
- The `Prompt for AI Agents` content

You do NOT have access to `{suggested_fix}` yet. Do not read it. Do not look
for it in the comment body. If you accidentally see it, disregard it.

Read the relevant source file(s) identified in the comment (use the `path`
and `line` fields from the comment object). Understand the surrounding code.

Implement a fix that addresses the issue described in the prompt. Apply it
directly to the file(s). Show the resulting diff to the user:

```
git diff {path}
```

Do NOT commit yet.

---

## STEP 5 — COMPARE & DECIDE (automatic, no user approval)

Now read `{suggested_fix}`. If it is `null`, skip the comparison and keep
your fix — report "No suggested patch available; kept own fix."

Otherwise, compare your diff against the suggested patch. Ask yourself:

1. Are both fixes functionally equivalent (same outcome, no meaningful
   difference in correctness, safety, or clarity)?
   → **Take the suggested fix.** Revert your change and apply the patch.

2. Is your fix demonstrably better (catches an additional edge case, is more
   correct, avoids a subtle bug the suggestion misses, is meaningfully
   cleaner)?
   → **Keep your fix.**

3. Is the suggested fix better?
   → **Take the suggested fix.**

Report your decision with one sentence of reasoning, e.g.:

- "Took suggested fix — functionally equivalent to mine."
- "Kept own fix — suggestion did not handle the null case on line 42."
- "Took suggested fix — it avoids the extra re-render my approach introduced."

Show the final state of the file diff after the decision.

Do NOT commit yet.

---

## STEP 6 — CONTINUE? (human checkpoint #2)

After each comment is processed (whether fixed or skipped), ask:

```
Continue to next comment? [yes / stop]
```

If `yes` → move to the next unresolved comment (back to STEP 3).
If `stop` → proceed to STEP 7.

Also proceed to STEP 7 automatically when all comments have been processed.

---

## STEP 7 — FINAL SUMMARY

Report:

- Total comments seen (unresolved, from CodeRabbit)
- How many were approved by user and fixed
- How many were skipped
- For each fixed comment: file, line, decision (kept own / took suggestion),
  one-line reasoning
- All changes complete.

Do NOT commit, push, or open/update the PR. Leave everything for the user to
review.

---

## CONSTRAINTS

- Never read `{suggested_fix}` before completing STEP 4 for that comment.
  This is the core discipline of the skill — the staged-information protocol
  exists so your fix is independent of CodeRabbit's suggestion.
- Never narrate the parsing of the suggested-fix section. Do not announce or
  describe its existence, position, ordering, or that you are deferring it.
  The user should never see phrases like "I noticed the body has a Proposed
  patch section before the AI Agents prompt — I'll set that aside." Parsing
  is silent; only the formatted summary in STEP 3 is user-visible.
- Never batch comments. Process strictly one at a time with a user checkpoint
  between each.
- Never auto-commit. The user must always be able to review the combined diff
  before committing.
- If `gh` commands fail (auth, permissions, rate limit), report the error
  clearly and stop — do not guess at comment content.
- If the suggested patch cannot be applied cleanly (merge conflict), report it
  and keep your own fix by default.

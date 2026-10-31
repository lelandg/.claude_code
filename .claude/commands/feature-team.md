---
description: Run a multi-task plan with the implementer→spec-review→quality-review loop using the model ladder. For COMPLEX work only (multi-task / cross-cutting); for small work, implement directly.
argument-hint: <path-to-plan.md | short description of the work>
---

Execute the work described by **$ARGUMENTS** using a fresh-subagent-per-task loop with two-stage review.

## Gate first — is a team warranted?
Per standing preference, only use this loop for **complex tasks (roughly ≥4 tasks, or cross-cutting/multi-file work)** or when explicitly requested. If the work is small/sequential and you can do it directly with a quick self-review, say so and just do it — don't spin up the loop for its own sake.

## If warranted
Invoke the **superpowers:subagent-driven-development** skill and run it task-by-task, applying the model ladder below. Tasks that touch overlapping files on one branch run **sequentially** (no parallel implementers). After each task: spec-compliance review, then code-quality review, fixing via the same implementer until both pass. After the last task, run the **Finishing phase** below.

## Model ladder (ALWAYS set `model` explicitly — inherited default is Opus, which is wasteful)
- **Haiku** — verbatim/mechanical edits, single-file changes, renames, simple spec-compliance reviews.
- **Sonnet** — multi-file/integration tasks, security-sensitive changes, the await/gate audits, the final whole-branch review.
- **Opus** — orchestration, design/brainstorming, architecture decisions only (i.e., you, the controller).

## Verification tiers (put this in every implementer dispatch)
- Task gate = scoped lint on the files you touched + the project typecheck + this task's tests. Do **NOT** run the full build or full lint — the Finishing phase owns those. Do **NOT** push. (On a Node/TypeScript project that is `npx eslint <files>` + `npx tsc --noEmit`; substitute your stack's equivalents.)
- If the task touches a schema or codegen input (e.g. `prisma/schema.prisma`), regenerate the client before the typecheck.
- Commit the task's work once the gate passes (per-task commits; push waits for the finish).
- Run the branch in a worktree (sibling of the project dir, e.g. `~/code/GitHub/<name>`), per superpowers:using-git-worktrees.

## Finishing phase (after the last task)
1. Controller runs the project's full build + full lint **once**. On failure, dispatch ONE Sonnet fix agent with the exact error output; loop until green. Substantive fixes get a scoped re-review.
2. Final whole-branch review (part of subagent-driven-development).
3. `/codex:review --base origin/main` against the committed branch — the cross-provider review AGENTS.md requires on every PR, *before* it opens. Fix each finding or answer it in the PR body.
4. Then **superpowers:finishing-a-development-branch** for the merge/PR menu. Push happens here, never earlier (review-before-push rule).
5. `/version-manager release <level>` — version bump + changelog in the same commit, cut **last**, immediately before the merge. Cut earlier it goes stale the moment another PR merges first.

## Notes
- If `$ARGUMENTS` is a plan file, extract the tasks from it; otherwise brainstorm → write a plan first (don't skip design for non-trivial work).
- Keep the controller (you) on Opus; push the workers down the ladder.

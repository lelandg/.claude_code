---
description: Run a multi-task plan with the implementer→spec-review→quality-review loop using the model ladder. For COMPLEX work only (multi-task / cross-cutting); for small work, implement directly.
argument-hint: <path-to-plan.md | short description of the work>
---

Execute the work described by **$ARGUMENTS** using a fresh-subagent-per-task loop with two-stage review.

## Gate first — is a team warranted?
Per Leland's standing preference, only use this loop for **complex tasks (roughly ≥4 tasks, or cross-cutting/multi-file work)** or when he explicitly requests it. If the work is small/sequential and you can do it directly with a quick self-review, say so and just do it — don't spin up the loop for its own sake.

## If warranted
Invoke the **superpowers:subagent-driven-development** skill and run it task-by-task, applying the model ladder below. Tasks that touch overlapping files on one branch run **sequentially** (no parallel implementers). After each task: spec-compliance review, then code-quality review, fixing via the same implementer until both pass. After the last task, run the **Finishing phase** below.

## Model ladder (ALWAYS set `model` explicitly — inherited default is Opus, which is wasteful)
- **Haiku** — verbatim/mechanical edits, single-file changes, renames, simple spec-compliance reviews.
- **Sonnet** — multi-file/integration tasks, security-sensitive changes, the await/gate audits, the final whole-branch review.
- **Opus** — orchestration, design/brainstorming, architecture decisions only (i.e., you, the controller).

## Verification tiers (put this in every implementer dispatch)
- Task gate = `npx eslint <files you touched>` + `npx tsc --noEmit` + this task's tests. Do **NOT** run `npm run build` or full `npm run lint` — the Finishing phase owns those. Do **NOT** push.
- If the task touches `prisma/schema.prisma`, run `npm run db:generate` before the typecheck.
- Commit the task's work once the gate passes (per-task commits; push waits for the finish).
- Run the branch in a worktree (sibling of the project dir, e.g. `~/code/GitHub/<name>`), per superpowers:using-git-worktrees.

## Finishing phase (after the last task)
1. Controller runs `npm run build` + full `npm run lint` **once**. On failure, dispatch ONE Sonnet fix agent with the exact error output; loop until green. Substantive fixes get a scoped re-review.
2. Final whole-branch review (part of subagent-driven-development).
3. `/version-manager release <level>` — version bump + changelog in the same commit.
4. Then **superpowers:finishing-a-development-branch** for the merge/PR menu. Push happens here, never earlier (review-before-push rule).

## Notes
- If `$ARGUMENTS` is a plan file, extract the tasks from it; otherwise brainstorm → write a plan first (don't skip design for non-trivial work).
- Keep the controller (you) on Opus; push the workers down the ladder.

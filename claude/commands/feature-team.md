---
description: Run a multi-task plan with the implementer→spec-review→quality-review loop using the model ladder. For COMPLEX work only (multi-task / cross-cutting); for small work, implement directly.
argument-hint: <path-to-plan.md | short description of the work>
---

Execute the work described by **$ARGUMENTS** using a fresh-subagent-per-task loop with two-stage review.

## Gate first — is a team warranted?
Per Leland's standing preference, only use this loop for **complex tasks (roughly ≥4 tasks, or cross-cutting/multi-file work)** or when he explicitly requests it. If the work is small/sequential and you can do it directly with a quick self-review, say so and just do it — don't spin up the loop for its own sake.

## If warranted
Invoke the **superpowers:subagent-driven-development** skill and run it task-by-task, applying the model ladder below. Tasks that touch overlapping files on one branch run **sequentially** (no parallel implementers). After each task: spec-compliance review, then code-quality review, fixing via the same implementer until both pass. Final whole-branch review at the end, then **superpowers:finishing-a-development-branch**.

## Model ladder (ALWAYS set `model` explicitly — inherited default is Opus, which is wasteful)
- **Haiku** — verbatim/mechanical edits, single-file changes, renames, simple spec-compliance reviews.
- **Sonnet** — multi-file/integration tasks, security-sensitive changes, the await/gate audits, the final whole-branch review.
- **Opus** — orchestration, design/brainstorming, architecture decisions only (i.e., you, the controller).

## Notes
- If `$ARGUMENTS` is a plan file, extract the tasks from it; otherwise brainstorm → write a plan first (don't skip design for non-trivial work).
- Keep the controller (you) on Opus; push the workers down the ladder.

---
description: Audit a repo's agent docs — AGENTS.md/CLAUDE.md topology, always-loaded token cost, CodeMap freshness and line-number accuracy, broken pointers, changelog drift. Read-only; offers fixes in dependency order.
argument-hint: [path | all] [--fix]
---

Invoke the `repo-doctor` skill.

Scope from `$ARGUMENTS`:
- empty → audit the current repo.
- a path → audit that repository.
- `all` → audit every repository under your projects root, one `audit.py` run
  each, then present a single table sorted by severity. Set the root to wherever
  you keep your checkouts. Do **not** fix anything in `all` mode — report only.
- `--fix` → after reporting, run the recommended remediations in order without
  asking between each one. Without it, ask before running any.

Always run `python3 ~/.claude/skills/repo-doctor/audit.py --repo <abs-path>`
first and build the report from its output — never estimate file sizes, CodeMap
age, or line-number accuracy yourself.

Respect the dependency order: **topology → content → accuracy → currency**. If
the repo has a `CLAUDE.md` but no `AGENTS.md`, offer `/unify-agents-md` before
anything else and explain why (Codex/Copilot/agy/Pi read `AGENTS.md` and are
currently getting no repo rules). Never kick off a CodeMap rebuild unprompted —
it is the expensive step.

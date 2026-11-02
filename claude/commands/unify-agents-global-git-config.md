---
description: Make git/commit rules identical across all your repos — one source of truth (global ~/.claude by default), green-source check, workflow scan of every repo (following linked files), unified conflict questions, then commit/push/PR/merge per each repo's rules.
argument-hint: [global | local | project | dir <path>] [target <path>] [quiet]
---

Invoke the `unify-agents-global-git-config` skill. This command is your opt-in
to run its saved Workflow (`unify-agents-global-git-config`, scan then apply).

Arguments from `$ARGUMENTS` (order-free, `key=value` / `--flag` also accepted):
- **source of truth** (pick one):
  - `global` (default): Claude global config (`~/.config/agents/AGENTS.md`,
    `~/.claude/CLAUDE.md`, linked `~/.claude/instructions/*`).
  - `local` or `project`: the current project's instruction files.
  - `dir <path>`: instruction files in that directory.
- `target <path>`: optional. The repos (or the root of repos) to unify.
  Default: the known user repo location (`/mnt/d/Documents/Code/GitHub`
  plus `Web/`). If no location is found, ask with AskUserQuestion.
- `quiet`: apply without asking. If anything would need a question
  (uncommitted or red source, no target, rule conflicts), change nothing.
  Stop and save a report in the source repo's notes/docs directory.

Follow the skill exactly:
1. Read the git/SCM rules in the source.
2. Check that the source and its mirror (e.g. from `/publish-claude-config`)
   are committed and CI-green. If uncommitted: explain, then ask to commit
   (direct to main or a branch, per the rules) or stop.
3. Run the scan workflow.
4. Propose the change table and ask the merged cross-repo questions in
   batches of ≤ 4, so each answer covers every affected repo.
5. Confirm the plan, then run the apply workflow.
6. Report.

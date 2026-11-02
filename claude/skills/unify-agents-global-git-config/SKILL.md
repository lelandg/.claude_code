---
name: unify-agents-global-git-config
description: Make git/SCM commit rules identical across every repo — read the rules from one source of truth (global ~/.claude + ~/.config/agents, the current project, or a given dir), check the source is committed and green, scan all local repos (following linked files) for branching/commit/PR/merge/versioning rules, ask the fewest possible questions to resolve cross-repo conflicts, then write one managed rules block into each repo and commit/push/PR/merge as each repo's rules allow. Driven by a Workflow. Use when the user says "same commit rules everywhere", "unify git rules across repos", "sync my git conventions", or runs /unify-agents-global-git-config.
---

# unify-agents-global-git-config

Goal: **the same git rules in every repo**, copied from one source and kept
from drifting. Siblings: `/unify-agents-md` (makes AGENTS.md canonical in one
repo), `agent-config-sync` (WSL ↔ Windows copies of global files). This one
covers the other direction: global rules → every repo.

The fan-out runs as the saved workflow `unify-agents-global-git-config`
(`~/.claude/workflows/unify-agents-global-git-config.js`). Invoking this
skill or command is the user's opt-in to run it. **The workflow cannot ask
questions.** You do every check and question in the main loop, before and between its two runs:
`mode: "scan"` (read-only) and `mode: "apply"`.

## The managed block

Each repo gets **one** copy of the rules, between markers, in its canonical
instruction file (`AGENTS.md`; `CLAUDE.md` only if no AGENTS.md exists, in
which case recommend `/unify-agents-md` in the report):

```markdown
<!-- BEGIN unified-git-rules -->
## Git & commit rules
_Synced from global source on 2026-11-02 10:00 by /unify-agents-global-git-config. Edit the source, not this block._
...
<!-- END unified-git-rules -->

## Repo-specific git exceptions
- (only exceptions the user approved)
```

The block is self-contained. Collaborators, CI reviewers, and other CLIs may
not have `~/.config/agents/AGENTS.md`, so the block states each rule in full
and does not just point to the source. Re-runs replace the block in place.
Any other git statement in the repo that duplicates or contradicts the block
is removed or reworded, so nothing is left that can drift. This follows the
shared rule: "update every copy in the same commit".

## Arguments

| Arg | Meaning |
|---|---|
| `global` (default) | Source = Claude global config: `~/.config/agents/AGENTS.md`, `~/.claude/CLAUDE.md`, and every `~/.claude/instructions/*.md` they link |
| `local` / `project` | Source = the current project's AGENTS.md / CLAUDE.md (+ links) |
| `dir <path>` | Source = instruction files in `<path>` (+ links) |
| `target <path>` | Repos to scan. Default: the user's known repo root (see step 3) |
| `quiet` | Apply without asking. If anything **would** need a question, stop and write a report instead (step 7) |

Parse `$ARGUMENTS` loosely (`target=/x`, `--quiet`, `dir:/x` all work). An
unrecognized argument goes into AskUserQuestion. In `quiet` mode it is a stop
reason instead.

## Procedure

### 1. Read the user's git rules (source)

Get the real date first (`date '+%Y-%m-%d %H:%M'`). Resolve the source files
and read every rule about git or any SCM. Follow `@imports`, markdown links,
and backticked `.md` paths, one level at a time, and read each file once. You
need this inline anyway, to judge the source checks in step 2 by the user's
own rules. The workflow's Canon phase re-extracts the rules in structured form.

### 2. Make sure the source is committed and green (saves work)

Find every git repo that holds the source:

- `global`: `~/.claude` (if it is a repo) **and the mirror repo**, e.g. the
  `.claude_code` repo that `/publish-claude-config` publishes. Look for it
  in the repo root from step 3, or for a README that says "mirrors
  ~/.claude". Diff the live global files against the mirror's copies
  (`config/agents/AGENTS.md`, `claude/CLAUDE.md`, `claude/instructions/`). If
  `tools/agent-config-sync/sync.py check` exists, run it as well.
- `local` / `dir`: the repo containing the source.

For each source repo:

1. **Uncommitted changes** to rule files (`git status --porcelain`): explain
   what is uncommitted and why it matters. Anything uncommitted gets copied
   into N repos and can never be reproduced from history. Then ask with
   AskUserQuestion: *commit* or *stop*. Make the commit proposal concrete and
   base it on the source's own rules. Instruction-file-only changes may go
   straight to `main` under rule 4 of "Branching & working-tree hygiene", but
   only if a pre-commit gate runs in that repo. Otherwise propose a branch and
   PR. Give the branch name and commit message. A diverged mirror counts the
   same way: offer to publish it first, or stop.
2. **CI**: if `.github/workflows/` exists, check the latest runs on the
   default branch: `gh run list --branch <default> --limit 5`, or the GitHub
   MCP `actions_list` where `gh` is unavailable. If anything is red or
   pending, report it and stop. Don't spread rules from a red source. Offer to
   fix the failure as separate work.
3. A contradiction inside the source becomes the first unified question in
   step 5. The workflow reports these as `canon.internal_conflicts`.

### 3. Resolve targets

`target` if given. Otherwise the user's known repo root. Check, in order:
the user's preferences/memory (e.g. `D:\Documents\Code\GitHub` → WSL
`/mnt/d/Documents/Code/GitHub`, plus its `Web/` subdirectory), `~/code`,
`~/src`, `~/GitHub`, `~/projects`. Enumerate git repos at depth ≤ 2 (`find
<root> -maxdepth 3 -name .git -prune`). Exclude `3rdParty/` and the source
repos themselves. If no root is found, ask with AskUserQuestion: list the
candidates you found plus "Other". In `quiet` mode that is a stop.

### 4. Scan (workflow, read-only)

```
Workflow({ name: "unify-agents-global-git-config", args: {
  mode: "scan", date: "<YYYY-MM-DD HH:MM>", quiet: <bool>,
  source: { kind: "global|local|dir", path: "<abs>", files: ["<abs>", ...] },
  repos: ["<abs repo>", ...] } })
```

If the name does not resolve, use
`scriptPath: "~/.claude/workflows/unify-agents-global-git-config.js"`, with
`~` expanded. In this config repo the script also lives at
`claude/workflows/`. Pass `args` as real JSON values, not as a string.

The result contains: `canon` (rules + rendered block), `repos[]`
(`{scan, cmp}`: each repo's rules, git state, diff items, and route
`direct-main|pr|blocked`), and `unify` (`questions`, `auto`, `skipped`).
Report `uncovered > 0` explicitly. Never let a partial scan read as complete.

### 5. Propose, then ask the unified questions

Show one proposal table: repo, changes (block add/replace, N removals),
route, and skip reason. Then ask `unify.questions` with AskUserQuestion. The
tool takes at most 4 questions per call, so ask in batches of 4, most repos
first. One answer applies to every repo in that question's `affects`, which
is how the question count stays low. Standing answers:

- **Promote to source** → edit the source first, commit it per step 2's
  route, and re-render the block (rerun scan, or update `canon.block_markdown`
  yourself and show the diff). Every repo then gets the promoted rule.
- **Keep as exception** → goes into that repo's `exceptions`.
- **Use canon / Remove** → goes into that repo's `removals`.

Finally, confirm the whole plan with one question: *apply to N repos (M
direct to main, K via PR)?* Pushing to remotes is outward-facing.

### 6. Apply (workflow)

Build one plan per non-skipped, non-blocked repo:
`{ repo, target_file, route, block, removals: [{file,line,action}], exceptions: [text], notes }`.
Then run:

```
Workflow({ name: "unify-agents-global-git-config", args: {
  mode: "apply", date: "<same>", canon: <scan.canon>, plans: [...] } })
```

Each apply agent works in a throwaway worktree cut from `origin/<default>`,
so the user's WIP and unpushed local commits never leak. It backs up edited
files (`.bak-<timestamp>`, `cp -n`), then commits under the new rules:
direct to main, or branch + PR + version bump if the repo requires one. It
merges only when that repo's rules allow autonomous merging and checks are
green. Otherwise it enables auto-merge or leaves the PR open. A verify agent
then re-reads what was pushed and tries to refute the sync.

### 7. Report

Show a table: repo | status | commit/PR | verify. Every `verify.matches ==
false` is a failure; show its problems. Write a summary markdown into the
source repo's notes/docs directory, matching its convention (`Notes/` or
`Docs/`; for `global` that is the mirror repo, else `~/.claude/reports/`).
Name it `<YYYY-MM-DD>-unify-git-rules.md`. Commit it per the source repo's
rules, since `Notes/` and `Docs/` reports are commit-by-default in
`file-dispositions.md`.

**`quiet` mode:** skip every confirmation. If step 2 finds uncommitted or red
sources, step 3 finds no root, or `unify.questions` is non-empty, **do not
apply anything** (not even the question-free repos, so nothing ends up
half-unified). Write the report to that location with: the stop reason, the
full question list with recommended answers, the proposal table, and the
exact command to resume interactively. Then stop.

## Guardrails

- The source must be consistent, committed, and green before anything is
  copied out of it.
- Never edit the user's working tree in a target repo. Use worktrees only.
  Never force-push, never `--admin`, never bypass a failed check.
- The route comes from each repo's **own** rules, plus the pre-commit-gate and
  `core.hooksPath` check. When in doubt, PR.
- Keep every non-git line. Leave `@import` on line 1.
- Skip third-party repos, forks of other people's projects, archived repos, and `3rdParty/`.
- No silent caps. Every repo is applied, skipped with a reason, or reported uncovered.
- Auto mode may block writes to agent configuration. If it does, give the user
  the exact command to run and do not look for another way to write it.

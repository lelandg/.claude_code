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
  (`config/agents/AGENTS.md`, `claude/CLAUDE.md`, `claude/instructions/`;
  ignore CR/LF with `diff --strip-trailing-cr`). **The mirror is deliberately
  sanitized** (names, handles, companies, paths replaced by placeholders), so
  every shared file differs and *differing is not diverged*. Count the mirror
  as diverged only when a git/SCM rule in the live files is missing from the
  mirror or says something different there once placeholders are ignored.
  Name each such rule. If `tools/agent-config-sync/sync.py check` exists, run
  it as well.
- Every rule file step 1 read is checked in the repo that **owns** it, which
  may be a dotfiles repo around `~` (common on WSL), a nested repo or
  submodule, or some other repo a link points into. Resolve each with
  `git -C <file's directory> rev-parse --show-toplevel`, group by that repo,
  and run `git status --porcelain --untracked-files=all --ignored -- <its
  files>` there. The flags matter: dotfiles repos often ignore everything or
  set `status.showUntrackedFiles=no`, which would hide a file from the check.
  Unrelated untracked files in that repo say nothing about the source.
- A rule file that its repo reports as untracked (`??`) or ignored (`!!`), or
  that belongs to no repo at all, is not versioned there. For global files
  under `~` that is expected (on Windows `~/.claude` is often no repo at all):
  skip that repo and let the mirror check stand as the committed record. Do
  not offer to commit them there. Anywhere else, treat the file as
  uncommitted.
- `local` / `dir`: the repo containing the source.

For each source repo:

1. **Uncommitted changes** to rule files (`git status --porcelain`). An
   `assume-unchanged` or `skip-worktree` flag hides edits from status, so
   also compare each regular file's `git hash-object <file>` with `git
   rev-parse HEAD:<file>`. For a tracked symlink, compare the link text
   (`readlink`, or `(Get-Item -LiteralPath <file> -Force).Target` in
   PowerShell 7.4+) with `git cat-file -p HEAD:<file>`. Hashing a symlink
   reads its target, not the link, so a clean link would look modified.
   Then check the resolved target in its own owning repo. Explain
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
`~/src`, `~/GitHub`, `~/projects`. Use the spelling native to the runtime you
are in: `D:\...` on Windows, `/mnt/d/...` on WSL. Never mix the two in one
`repos` list, because every agent runs its git commands in your runtime.
Enumerate git repos at depth ≤ 2 (`find <root> -maxdepth 3 -name .git -prune`;
on Windows run it in Git Bash, or use `Get-ChildItem <root> -Depth 2 -Filter
.git -Force`, with no `-Directory`, because `.git` is a file in linked
worktrees and submodules). Exclude `3rdParty/`, the source repos themselves, and
`.ugr-*` directories (worktrees kept from an earlier `verify-failed` apply).
Each hit is a `.git` entry; the repo is its **parent directory**, and that
is what goes into `repos` and into every `git -C` below.
Then deduplicate: a main checkout and its linked worktrees share one
repository, and scanning both would open duplicate PRs or competing pushes.
Key each repo by `git -C <repo> rev-parse --path-format=absolute
--git-common-dir` plus its `origin` URL, and keep one per key, preferring the
main checkout. Submodules have their own common dir, so they stay distinct.
If no root is found, ask with AskUserQuestion: list the candidates you found
plus "Other". In `quiet` mode that is a stop.

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

Each repo is scanned at `origin/<default>` after a `git fetch`, which is
the revision that apply will edit, not the working tree. Its sha is recorded
as `scan.scanned_commit`. Local differences (another branch checked out,
uncommitted or unpushed rule edits) are reported in `scan.local_divergence`.
Show them to the user before approving.

The result contains:
- `canon`: the rules and the rendered block.
- `repos[]`: one `{repo, scan, cmp}` per repo, with its rules, git state,
  diff items, and route `direct-main|pr|blocked`.
- `unify`: `questions`, `auto`, and `skipped`.
- `failed[]`: repos whose scan or compare returned nothing.

Report each `failed` repo explicitly. Never let a partial scan read as
complete, and never apply to a failed repo.

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
`{ repo, remote, scanned_commit, default_branch, target_file, route, block, removals: [{file,line,action}], exceptions: [text], notes }`.
Copy `remote`, `scanned_commit` and `default_branch` from that repo's scan.
Publish refuses to push if `origin` no longer points at that `remote`.
Then run:

```
Workflow({ name: "unify-agents-global-git-config", args: {
  mode: "apply", date: "<same>", canon: <scan.canon>, plans: [...] } })
```

Each repo goes through three stages. Nothing reaches a remote until an
independent verifier has passed it, and that includes the direct-to-main
route.

1. **Apply (local only).** The agent re-fetches. If `origin/<default>` has
   moved past `scanned_commit` and any file the plan touches changed, it
   changes nothing and reports `stale`, because the user approved different
   text. Re-scan that repo. Otherwise it creates a throwaway worktree on a new
   local branch **from `scanned_commit`**, the exact revision the user
   approved, so the user's WIP and unpushed local commits never leak. It
   backs up each file at that revision to
   `<common-git-dir>/ugr-backups/<timestamp>/` (`git rev-parse
   --path-format=absolute --git-common-dir`: not `<repo>/.git` in a submodule,
   and not the per-worktree dir that `git worktree remove` deletes). That
   folder is never committed and never clutters the checkout. The redirect
   runs in a POSIX shell (Git Bash on Windows) or PowerShell 7.4+, because
   older PowerShell re-encodes redirected native output. It then edits and commits under the new rules. It
   does not push.
2. **Verify.** A separate agent reads that local commit (`git show`, and
   `git diff scanned_commit..commit`) and tries to refute the sync. It
   checks: one managed block equal to the approved one, no contradicting
   copies left in the repo, no non-git content lost, `@import` still on
   line 1, and a commit message that follows the rules.
3. **Publish (verified commits only).** Publish pushes *exactly* the
   verified SHA, to the `default_branch` the scan recorded. It never
   creates, amends, or rebases a commit, because any new SHA would be
   unverified. A result whose pushed SHA differs from the verified one is
   reported `failed`.
   - Direct to main: push the commit only if `origin/<default>` still equals
     `scanned_commit` (a plain fast-forward). If `origin` moved at all,
     report `stale` and push nothing. Re-scan and re-approve that repo.
   - PR route: push the verified SHA as the branch, confirm the remote tip
     equals it, open the PR. Never merge or enable auto-merge if any
     instruction or rule file changed on the base since `scanned_commit`,
     because the verifier never saw that change. Bump the version if the
     repo requires one. Merge only when that repo's rules allow autonomous
     merging and checks are green. Otherwise enable auto-merge or leave the
     PR open.
   - A repo that fails verification is reported `verify-failed`. Its local
     branch is kept for inspection, and nothing is pushed.

Plans missing `repo`, `remote`, `route`, `scanned_commit`,
`default_branch` or `target_file` are rejected before any agent runs.

### 7. Report

Show a table: repo | status | commit/PR | verify. Every `verify.matches ==
false`, `failed`, `stale`, and `verify-failed` row is a failure. Show its problems; the
result's `failed` and `unverified` counts must match the table. Write a summary markdown into the
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

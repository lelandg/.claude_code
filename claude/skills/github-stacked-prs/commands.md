# `gh stack` command reference

Captured 2026-08-08 from the public-preview docs
(https://docs.github.com/en/pull-requests/reference/stacked-prs-cli-commands and
the official gh-stack agent skill). Requires GitHub CLI ≥ 2.0 and the
`github/gh-stack` extension. Verify against `gh stack <command> --help` if
behavior seems off — this is a preview and may drift.

## Stack management

### `gh stack init [flags] [branches...]`
Initialize a new stack. Non-interactive: pass branch names explicitly (adopts
existing branches or creates them). Interactive mode prompts.
- `-b, --base <branch>` — trunk (defaults to repo default branch)
- Enables `git rerere` automatically.

### `gh stack add [flags] [branch]`
Create a new branch at current HEAD, add to stack top, check it out. Must run
on the topmost branch. Pass the branch name explicitly in a harness.
- `-m, --message <string>` — commit before branching
- `-A, --all` — stage everything incl. untracked (requires `-m`)
- `-u, --update` — stage tracked only (requires `-m`; mutually exclusive with `-A`)
- With `-m` and no name, auto-names `MM-DD-slug`.

### `gh stack view [flags]`
Show branches, order, PR links, recent commits.
- `--json` — machine-readable (use this in a harness)
- `-s, --short` — compact human output
- Bare invocation pipes through a pager/TUI — avoid.

JSON shape: `trunk`, `currentBranch`,
`branches[] {name, head, base, isCurrent, isMerged, isQueued, needsRebase, pr {number, url, state OPEN|MERGED|QUEUED}}`
(`pr` absent when none exists).

### `gh stack checkout [<stack-number> | <pr-number> | <pr-url> | <branch>]`
Check out a stack by identifier; fetches remote stacks and sets them up
locally. Bare numbers resolve stack/PR number first, then branch name. Branch
names resolve against local stacks only — use a number/URL to pull from GitHub.
No args → interactive picker (avoid). If a different local stack already covers
those branches: `gh stack unstack --local`, then retry.

### `gh stack modify [--continue | --abort]`
Interactive TUI restructuring only (reorder, fold, drop, rename, insert).
Never usable in a harness; non-interactive restructuring = `unstack` + `init`.
Preconditions: clean tree, no rebase in progress, nothing queued, linear history.

### `gh stack unstack [<stack-number>] [--local]`  (alias: `delete`)
Remove stack tracking locally and on GitHub. `--local` keeps the GitHub stack.
Merged/merging/queued PRs can't be removed from the remote stack.

## Remote operations

### `gh stack submit [flags]`
Push all branches and create/update + link PRs on GitHub.
- `--auto` — no editor, auto-generated titles (required in a harness)
- `--open` — create PRs ready-for-review (default: draft)
- `--remote <name>`
- Titles/bodies are auto-generated; fix with `gh pr edit`.

### `gh stack sync [flags]`
Full cycle: fetch → reconcile remote → fast-forward trunk → cascade rebase →
push → sync PR/stack state → prune.
- `--prune` — delete local branches for merged PRs (only with the flag in
  non-interactive mode)
- `--remote <name>`
- Clean remote-ahead updates are pulled automatically. Divergence:
  non-interactive makes no changes and exits 0 with a status message.

### `gh stack rebase [flags] [branch]`
Rebase trunk onto origin, then each branch upward.
- `--downstack` / `--upstack` — limit to trunk→current / current→top
- `--no-trunk` — skip trunk fetch/rebase
- `--continue` / `--abort` — conflict flow (exit 3 pauses; resolve, `git add`,
  then `--continue`)
- `--committer-date-is-author-date` (alias `--preserve-dates`)
- `--remote <name>`
- Auto-switches to `--onto` handling for merged PRs.

### `gh stack push [--remote <name>]`
Push active branches (skips merged/queued) with per-branch
`--force-with-lease`. Non-atomic. Does NOT create/update PRs — that's `submit`.

### `gh stack link [flags] <stack-number | branch-or-pr> <branch-or-pr> ...`
Link branches/PRs into a GitHub stack without local tracking (for Jujutsu,
Sapling, git-town users). Args bottom→top. Additive only.
- `--base <branch>`, `--open`, `--remote <name>`

### `gh stack merge [<stack-number> | <pr-number>] [flags]`
Merge the selected PR and every unmerged PR below it (stack number = whole
stack). All-or-nothing; cannot bypass merge requirements; with a merge queue
the stack is queued and method flags are ignored (warning).
- `-y, --yes` — no confirmation (required in a harness)
- `--squash` / `--merge` / `--rebase` or `--merge-method <m>` — without a flag,
  reuses the last-used method

## Navigation

- `gh stack up [n]` / `gh stack down [n]` — move away from / toward trunk
- `gh stack top` / `gh stack bottom` — furthest from / nearest to trunk
- `gh stack trunk` — check out trunk (requires active stack; needs
  `remote.pushDefault` when multiple remotes, no `--remote` flag)
- `gh stack switch` — interactive picker only; avoid in a harness

## Utility

- `gh stack alias [name] [--remove]` — install `gs` wrapper to `~/.local/bin/`
- `gh stack feedback [title]` — open a feedback discussion upstream
- `GH_STACK_THEME` = `auto|light|dark`

## Exit codes

| Code | Meaning |
|---|---|
| 0 | success |
| 1 | generic error (read stderr) |
| 2 | not in a stack / stack not found |
| 3 | rebase conflict |
| 4 | GitHub API failure (`gh auth status`, retry) |
| 5 | invalid arguments |
| 6 | disambiguation required (branch in several stacks) |
| 7 | rebase already in progress |
| 8 | stack file locked (retry ~5 s) |
| 9 | stacked PRs not enabled for repository |
| 10 | modify interrupted; `gh stack modify --abort` |

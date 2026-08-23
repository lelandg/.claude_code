---
name: github-stacked-prs
description: Use when a feature is too large for one reviewable PR and splits into layers that build on each other; when Leland mentions stacked PRs, "gh stack", stacking, or splitting a big branch into a chain of dependent PRs; or when planning multi-part work where each part depends on the previous. GitHub-native feature (public preview since 2026-07-30) via the official gh-stack CLI extension.
---

# GitHub Stacked PRs (`gh stack`)

## Overview

A stack is an ordered chain of branches rooted on trunk — `(main) <- auth <- api <- frontend` — where each branch has one PR based on the branch below. Layers are reviewed in parallel; merging a PR lands it **plus every unmerged layer below it** in one operation. Upper PRs auto-rebase/retarget after partial merges. Native to GitHub (github.com UI, mobile, CLI) since the 2026-07-30 public preview; the CLI lives in the official `github/gh-stack` extension.

**Read left→right: left is the bottom (nearest trunk), right is the top. `down` moves toward trunk, `up` away from it.**

## Currency check (do this first, every time)

This feature is in **public preview** and this skill was written 2026-08-08 against that preview. Before relying on it:

1. `gh extension list | grep gh-stack` — install with `gh extension install github/gh-stack` if missing.
2. Run `gh stack view --json` in the target repo. Exit code 9 means stacked PRs are **not enabled for that repository** — fall back to ordinary sequential PRs and say so.
3. If commands here have changed, the extension is archived/deprecated, or stacking has moved into gh core (e.g. a native `gh pr stack`), **stop, report the discrepancy to Leland, and recommend switching methods** — then update or retire this skill with his approval.

## When to use / when not

**Use for:** a single feature whose diff would be large (roughly >400 lines) AND separates into dependent layers (schema → API → UI; refactor → behavior change; migration → code using it). The stack still merges as one unit, so Leland's "one PR per finished whole feature" rule holds — the stack IS the feature's PR, in reviewable slices.

**Do not use for:** small changes (house rules: those go straight to `main`); independent changes (open separate ordinary PRs); repos where exit 9 says the preview isn't enabled; or splitting for its own sake — if one PR reviews fine, ship one PR.

## Agent safety: never trigger a TUI

The tool switches behavior on TTY detection. In an agent harness, always use the non-interactive forms:

| Safe | Avoid bare | Why |
|---|---|---|
| `gh stack view --json` | `gh stack view` | opens TUI pager |
| `gh stack submit --auto` | `gh stack submit` | prompts per-PR for titles |
| `gh stack merge <n> --yes` | `gh pr merge` | `gh pr merge` cannot merge stacks |
| `gh stack init <branch>` | `gh stack init` | prompts for branch names |
| `gh stack add <branch>` | `gh stack add` | prompts, fails when piped |
| `gh stack checkout <target>` | `gh stack checkout` / `switch` | selection menus |
| `gh stack up` / `down` / `top` / `bottom` | `gh stack modify` | modify is TUI-only |

Multi-remote repos: set `git config remote.pushDefault origin` or pass `--remote origin` on `push`/`submit`/`sync`/`rebase`/`link`. Also set `git config rerere.enabled true` so resolved conflicts stay resolved across cascade rebases.

## Core workflow

Create the stack **before** writing code — one dependent concern per layer, bottom to top. Don't implement everything on one branch and split later (`modify` is TUI-only; restructuring non-interactively means `unstack` + re-`init`).

```bash
git fetch                          # house rule: root the stack on origin/main
gh stack init auth                 # bottom layer; -b <trunk> if not default branch
# ...edit... ; git add -A && git commit -m "Add auth middleware"
gh stack add api                   # next layer, branched from current top
# ...edit... ; git add -A && git commit -m "Add API routes"
gh stack submit --auto             # push all branches, open PRs (draft; --open for ready)
gh stack view --json               # verify state
```

**Edit a lower layer:** check out the layer that owns the change — never commit a lower layer's concern on the top branch:

```bash
gh stack checkout api              # or: gh stack down
git add ... && git commit -m "fix"
gh stack rebase --upstack          # replay layers above onto the change
gh stack top && gh stack push
```

**Stay current:** `gh stack sync` (fetch → rebase cascade → push → refresh PR state); `--prune` deletes local branches for merged PRs. On divergence it prints both chains, changes nothing, exits 0.

**Merge:** `gh stack merge 42 --yes` lands PR 42 + everything below; a stack number merges the whole stack. All-or-nothing: if any PR in the set can't merge, none do. Branch protections/required checks still apply (checks are evaluated against the bottom PR's base, so main-targeting workflows run for mid-stack PRs); with a merge queue the stack is queued instead.

## House-rule integration

- Review-before-push and cross-provider review happen per layer, before `gh stack submit`.
- **One version bump per stack** (not per layer): run version-manager as the final commit on the **top** layer before `gh stack merge`, since merging the top lands the whole feature.
- PR titles/bodies are auto-generated by `submit --auto` — follow up with `gh pr edit` to make them real.

## Exit codes that need action

| Code | Meaning | Recovery |
|---|---|---|
| 2 | not in a stack | `gh stack init` or `checkout <target>` |
| 3 | rebase conflict | resolve, `git add`, `gh stack rebase --continue` (or `--abort`) |
| 6 | branch in several stacks | check out a non-shared branch |
| 7 | rebase already in progress | `gh stack rebase --continue` or `--abort` |
| 9 | stacked PRs not enabled on repo | fall back to ordinary PRs; report |
| 10 | modify interrupted | `gh stack modify --abort` |

Parse `view --json` (fields: `trunk`, `currentBranch`, `branches[].{name,head,base,isCurrent,isMerged,isQueued,needsRebase,pr{number,url,state}}`). Status text goes to stderr — branch on exit codes, never parse messages.

## Common mistakes

- Running bare `gh stack submit`/`view`/`checkout` in a harness → hangs on TUI. Use the safe forms above.
- `gh pr merge` on a stacked PR → refuses/breaks the stack. Only `gh stack merge`.
- `checkout <pr>` when a different local stack covers those branches can't be forced → `gh stack unstack --local` first, then retry.
- Committing a fix on the top branch that belongs to a lower layer → wrong diff in every PR above it.
- Stacks are strictly linear (one parent, one child) — no trees.

Full command/flag reference: [commands.md](commands.md). Upstream docs: https://gh.io/stacks · repo: https://github.com/github/gh-stack

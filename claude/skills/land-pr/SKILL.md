---
name: land-pr
description: Use when a pull request needs finishing or the open-PR list needs clearing — before reporting work done in any repo you opened a PR in, when the user says "land it", "merge when green", "finish the PRs", "why are these PRs still open", "clear the PR backlog", or on /land-pr [status|land <ref>|sweep]. Classifies every open PR, lands the ready ones (version bump, checks, merge, tag) and closes superseded autofix drafts. Enforces the Landing and Versioning rules in AGENTS.md.
---

# Land PR

Every pull request ends merged or closed. This tool does the last mile
mechanically, so finishing a PR costs one command and any session can do it
for any PR.

- **Tool:** `~/.claude/skills/land-pr/pr_tool.py` (stdlib + `gh` + `git`)
- **Bumps:** delegated to `~/.claude/skills/version-manager/version_tool.py`
- **Rules it implements:** "Landing" and "Versioning & changelog" in
  `~/.config/agents/AGENTS.md`
- Read-only until `--apply`. On Windows use `python` and a Windows path.
- **First run:** set `OWNERS` (your GitHub login and orgs) and `CODE_ROOTS`
  (where your clones live) at the top of `pr_tool.py`.

## Verbs

```bash
T=~/.claude/skills/land-pr/pr_tool.py
python3 $T status                         # every open PR, classified
python3 $T status --repo OWNER/NAME       # one repo (use before reporting done)
python3 $T land OWNER/NAME#N              # dry run: release level, merge style
python3 $T land OWNER/NAME#N --apply      # bump, wait, merge, tag, clean up
python3 $T sweep                          # dry run of the whole backlog
python3 $T sweep --apply                  # close superseded, land all READY
python3 $T threads OWNER/NAME#N           # unresolved review threads, with ids
python3 $T threads OWNER/NAME#N --resolve ID [ID ...]
```

Exit codes: `0` done or nothing to do, `1` refused or failed, `3` waiting on
checks, `10` work pending (`status`, `sweep` dry run).

**Exit 3 means run the same command again.** `land` keeps no state of its own;
it reads everything from the PR. A run that pushed the bump and timed out
waiting for CI is finished by the next run, from any session or machine. The
default wait is 8 minutes so a foreground call fits a tool timeout; raise it
with `--wait 25` in a background run.

## What `land --apply` does

1. Refuses unless the PR is READY (table below).
2. Reads the release level and notes from the PR body.
3. In a throwaway detached worktree: drops a stale bump if the branch has one,
   merges `origin/<base>`, runs `version_tool.py release <level> --no-tag`,
   and pushes that one commit. No force-push, ever.
4. Waits for checks on the bump commit.
5. Merges in the repo's own style (read from recent history), with
   `--match-head-commit` so nothing unreviewed rides along. A squash subject
   becomes `title (vX.Y.Z) (#N)`.
6. Tags the merge commit through the API and deletes the branch.
7. Closes `autofix/pr-N` drafts for the PR it just merged.

After a merge to a deploying branch, the deploy watch and production smoke
test in AGENTS.md "Shipping autonomy" are still yours.

## The PR body section the lander reads

```markdown
## Release notes

Release: patch

- What changed, in words a user would recognize.
```

`Release:` is `major`, `minor`, `patch` or `none`. With no section the lander
infers the level (`none` when every changed path ships nothing, otherwise from
commit subjects) and drafts notes from commits. Never put a version number in
a PR title or a file; the lander assigns it at merge.

## States

| State | Meaning | Who moves it |
|---|---|---|
| `READY` | the current head is green and reviewed, every thread resolved, mergeable | `land` |
| `WAITING` | head pushed under 3 min ago, or checks, a workflow run or the automated review not in yet on it | time; re-run |
| `THREADS` | unresolved review threads | fix or answer each, then resolve it |
| `FAILING` | a check failed, or one never reported on the head within 30 min | fix and push, or re-run it |
| `CONFLICT` | conflicts with the base branch | merge base in, resolve |
| `REVIEW` | auth / billing / migration paths, no adversarial review recorded | run it, note "adversarial" in the PR body |
| `BLOCKED` | a branch rule refuses the merge | read `gh pr merge` output |
| `SUPERSEDED` | autofix draft whose source PR merged or closed | `sweep --apply` closes it |
| `AUTOFIX` | autofix draft, source still open | fold into the source, or close |
| `DRAFT` | draft PR | finish or close |
| `EXTERNAL` | outside contributor | the user |
| `ELSEWHERE` | your PR in someone else's repo | that repo's owner |
| `STALE(...)` | any of the above, idle 14+ days | the user: close or revive |

`sweep` lands only `READY` that is not stale, and closes only `SUPERSEDED`.
Everything else it lists and leaves. Report the `STALE`, `EXTERNAL` and
`ELSEWHERE` rows to the user as decisions; do not close a feature PR yourself.

## Policy lives at the top of the tool

`OWNERS`, `STALE_DAYS`, `REVIEW_GRACE_MIN`, `SETTLE_MIN`, `MISSING_CHECK_MIN`,
`REVIEWER_BOTS`, `REVIEWER_CHECKS`, `SHIPS_NOTHING` (paths that need no
version bump) and `SENSITIVE` (paths that need the adversarial review) are
constants at the top of `pr_tool.py`. Change behavior there, not in the logic
below.

## Gotchas

- **Every verdict is about the current head, not the PR.** Right after a push
  the head's check list is empty or partial, and an empty list has nothing
  failing in it. So a head is never READY in its first 3 minutes, while a
  workflow run GitHub has created for it is unfinished, or while a reviewer
  check that ran on an earlier commit has not reported on it. A review counts
  only if it is of the head: the bot's review of that commit, a passing
  reviewer check on it, or a bot comment written after the push. It is safe to
  run `land --apply` straight after pushing a fix; it waits.
- **A check that never arrives becomes `FAILING` after 30 minutes**, not
  READY. Re-run it or push again. GrepTile does not re-review a push, so
  re-trigger it. For a workflow that is path-filtered and will never run on
  this head, `land <ref> --apply --accept-missing` says so explicitly; `sweep`
  never implies it.
- **The lander's own commits carry the earlier review.** A release bump or a
  clean merge of the base adds no code, so the review of the commit before
  them still covers the head. A merge made by hand does not get this.

- **Unresolved means unresolved.** An outdated thread still blocks. Reply in
  the thread, then `threads --resolve`. Never resolve without a fix or reply.
- **Reviewer checks are checks.** CodeRabbit's status goes pending on every
  push, so `WAITING` already covers "re-review in progress". GrepTile does not
  re-review a push; its findings are threads, and those block.
- **No version location** (repo never ran `version_tool.py backfill`): the PR
  lands without a bump and the tool says so. Run backfill there afterwards.
- **A bump commit already on the branch** is kept if it is still the next
  version, otherwise dropped and re-cut; a hand-written changelog section is
  carried over as the notes.
- **Fork PRs** land without a bump: the tool cannot push to the fork.
- **One landing per repo at a time** on this machine (lock under
  `~/.claude/state/land-pr/`). A lock older than 45 minutes is taken over.

## Tests

```bash
python3 -m pytest ~/.claude/skills/land-pr/tests/ -q
```

On Windows run pytest from inside the skill folder and pass `--basetemp` if
the default temp folder is not writable. Classification tests are pure; the
bump tests build real git repositories and run the real version tool.

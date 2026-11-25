# Landing and versioning

Moved from `~/.config/agents/AGENTS.md` on 2026-11-24 so that file stays under agy's rule-file cut (22,035 bytes, measured 2026-11-25). AGENTS.md keeps the rule in brief and points here; this text is the full version and is equally binding.

### Landing — every PR ends merged or closed

An open PR is unfinished work. The session that opens one owns it until it is
merged or closed; "PR opened, waiting on review" is not a place to stop. (The
failure this rule exists for: PRs piling up fully green with nothing left to
wait for, because the session that opened them ended first, next to autofix
drafts nobody closed.)

Tool: `python3 ~/.claude/skills/land-pr/pr_tool.py` (skill `land-pr`),
read-only until `--apply`.

- `land <owner/repo#N> --apply` is the whole finishing sequence: it verifies
  green checks and resolved review threads, cuts the version bump, waits for
  checks on it, merges, tags the merge commit, deletes the branch, removes
  the branch's local worktree and local branch (never forced; a dirty or
  unmerged one is kept and named), and closes that PR's leftover autofix
  drafts. Run it from outside the PR's worktree so that worktree can go.
  Exit `3` means checks are still running: run the same command again. It
  is resumable from any session.
- `status [--repo owner/name]` classifies every open PR. `sweep --apply`
  closes superseded drafts and lands everything READY.

1. **Land before you report.** Before reporting work done, run `status --repo`
   for each repo you opened a PR in and land what is READY. If a PR cannot
   land in this session, name its state and what unblocks it. Never end on
   "the PR is open" alone.
2. **Any session may land any READY PR.** Which session opened it does not
   matter, and it needs no go-ahead; do not park a green PR as a decision for
   the user. The exceptions are the states the tool refuses to call READY:
   a PR someone else opened (`EXTERNAL`), auth/billing/migration paths with
   no adversarial review recorded in the PR body, and anything idle 14+ days.
   **Someone else's PR never lands without the user's approval.** Only PRs
   opened by the user, by their own agent accounts (`trusted_authors`) or by
   their own bots (`trusted_bots`, default Dependabot) are theirs; a partner,
   a teammate, an outside contributor, or a bot like Copilot (it works for
   whoever assigned it) is someone else, however green the PR is. Explain
   each one to the user: who opened it, what it changes, its checks and
   review status, and a recommendation, naming the commit you explained by
   its full SHA. Land it only after the user approves that PR, with
   `land <ref> --apply --approved-head <sha>`.
3. **Resolve the thread when you fix or answer it.** An unresolved review
   thread is how the tools read "open finding", outdated or not. Reply in the
   thread, then `threads <ref> --resolve <id>`. Never resolve without one.
4. **Fleet rollouts land as they go.** When one change goes to many repos,
   land each PR as it turns green, and keep at most five open at once.
5. **Autofix drafts die with their source PR.** Fold a wanted fix into the
   source PR; the draft is closed when the source merges or closes.
6. **Stale is a decision, not a state.** Rows `status` marks `STALE` or
   `ELSEWHERE` go in the end-of-task report as close-or-revive decisions for
   the user; `EXTERNAL` rows go there explained, as rule 2 says. Do not close a feature PR on your own.
7. **A conflict or failure is work, never a status.** Merge the base in and
   resolve it, or fix the failing check, then land. If it looks impossible,
   get a second opinion before stopping: a second agent in your own CLI,
   then a read-only diagnosis from a review-council member of a different
   model family (`~/.claude/instructions/model-delegation.md`). Effort may go
   up to `xhigh`, never `max` without the user's approval. A PR never carries `CHANGELOG.md`
   edits: put the entry in `## Release notes` (a changelog conflict resolves
   to the base's file).
8. **Orphans have an owner.** Run a scheduled routine (e.g. a Claude Code
   scheduled task every couple of hours during your working day) that takes
   over any PR whose head has been idle for 2 h, Dependabot's included,
   works it through rule 7, and keeps a ledger of what it did. A session
   that can't finish its PR still names its state; the routine picks it up
   from there.

GitHub's native auto-merge stays off: review findings arrive as comments, not
checks, and the bump must be the last commit, so it would merge ahead of both.

### Versioning & changelog (every repo)

Every PR that changes what the product ships gets a version bump and a
changelog entry in one commit, **cut by the lander at merge time, not by you
in the PR**. The PR carries the notes, never the number. Put this in the PR
body:

```markdown
## Release notes

Release: patch

- What changed, in words a user would recognize.
```

`Release:` is `major` (breaking), `minor` (feature), `patch` (fixes) or
`none`. `pr_tool.py land` reads the section, merges `origin/main` into the
branch, runs `version_tool.py release` with those notes, waits for checks on
that one commit, merges, and tags the merge commit. With no section it infers
the level and drafts notes from commit subjects; that lands, but reads worse.

- **No version number in a PR title, a branch name or a hand-edited file.** A
  number written before landing is a claim on `main`'s next version that every
  other open PR is also making; only the first to merge keeps it. The lander
  writes the real one into the squash subject. **Never hand-edit a version
  number or a changelog heading**: the tool owns both.
- **`Release: none`** is for a PR that changes nothing the product ships: CI
  and workflow files, tests, scanner and reviewer config, dev tooling. The
  lander infers it when every changed path is in that class (`SHIPS_NOTHING`
  in `pr_tool.py`). This is not rule 4: these changes still need the PR, just
  not a version. Bot PRs land without a bump too.
- **A branch that already carries a bump:** leave it. The lander keeps it when
  it is still the next version, and otherwise drops and re-cuts it without a
  force-push, carrying a hand-written changelog section over as the notes.
- **Version tags are pushed only after the merge,** by the lander, on the
  merge commit. Never push one from a branch: `v*` tags are protected, so a
  tag for a bump that then goes stale cannot be taken back. A local-only tag
  in the way is moved aside (`vX.Y.Z-draft-<sha>`), never deleted.
- **Outside a PR** (first-time adoption, repairing drift) run the tool
  directly: `python3 ~/.claude/skills/version-manager/version_tool.py --repo
  <abs-path> check`, then `backfill --apply` once per repo. A repo with no
  version location lands without a bump and the lander says so; backfill it.
  Full workflow: the `version-manager` skill.
- A non-functional change that qualifies for a direct commit under rule 4
  (its conditions are in `~/.claude/instructions/git-workflow.md`) needs no
  bump and no PR. One that does not qualify is a PR like any other.

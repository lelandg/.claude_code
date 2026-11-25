# PR review through the repo's automated reviewers

Referenced from `~/.config/agents/AGENTS.md` → "PR review through the repo's
configured automated reviewer". Standing rule since 2026-09-13; review
council 2026-11-25.

## When it applies

The user asks to commit, push, or open a PR on one of their repos, and the
repo has at least one automated reviewer (named in its own `AGENTS.md`; it is
not necessarily a Claude Code GitHub App). The review council runs before the
push on every repo either way (`~/.claude/instructions/model-delegation.md`,
"Review council"). On a repo with no automated reviewer, the council review
of the committed diff stands in for the wait; the last section of this file
says how, and what to do when no council member can run.

- **A reviewer other than the Claude Code GitHub App:** the autofix steps
  below are specific to that App and do not transfer. Establish the two
  things the last section of this file calls out before you gate on it —
  whether it re-reviews a push, and whether a passing check means "no
  findings" — and record the answers in that repo's own `AGENTS.md`.

## Procedure

1. Complete local checks, commit the feature, run the review council
   against the committed branch
   (`~/.claude/instructions/model-delegation.md`, "Review council"), push,
   and open the PR with a `## Release notes` section in its body. A council
   member that cannot run is never a gate: name it and the reason in the PR
   body and go on. Do not cut a version bump: the lander cuts it at merge time
   (`~/.claude/instructions/landing-and-versioning.md`). The
   request authorizes the automation to review the PR; no further confirmation is needed before opening it.
2. After opening the PR, wait for each automated reviewer the repo names. A
   review normally arrives in 2-5 minutes. Autofix is conditional and can create a separate
   draft PR without adding a comment or changing the original PR head.
3. To find review and autofix results, inspect all of these locations:
   - PR issue comments, submitted reviews, and inline review comments.
   - The paginated PR timeline, especially `cross-referenced` events. Follow
     `source.issue.pull_request.html_url` when the referenced item is a PR.
   - Labels, check runs, commit statuses, and changes to the original PR head.
   - Related PRs in all states, including drafts and closed PRs. Look for the
     original PR URL or number in titles and bodies and branches such as
     `autofix/pr-<number>`. Do not rely only on a branch naming convention.
4. Use the GitHub API timeline endpoint
   `repos/{owner}/{repo}/issues/{number}/timeline` with pagination when the
   normal PR view does not expose linked PRs. If needed, list repository PRs
   with `--state all` and follow pagination. Do not conclude that autofix did
   not run from missing comments or an unchanged original head. Automation may
   post using the user's account; do not filter only for bot authors.
5. A review's autofix-candidate metadata establishes eligibility, not that a
   run started. When eligible, check for a run or linked fix PR before making
   overlapping manual edits. Wait for active autofix work to finish. Inspect a
   linked PR's base, head, commits, diff, draft/merge state, and checks. It may
   include the original feature commits and target main, so distinguish the
   additional fix from the full PR diff. Preserve authorized automation commits.
   A linked draft PR does not mean the fix is applied to the original PR or
   merged.
6. Address PRs in order, starting with the original feature PR and its review.
   Do not wait for an autofix PR to merge. If the original PR remains open,
   incorporate inspected, validated fixes into its existing branch and update
   it. Reuse ready autofix commits when appropriate; do not stall on draft PR
   status.
7. When authorized to address review feedback, comment on the original PR with
   what changed, validation results, unresolved findings, and concrete next
   steps. If work remains pending, post next steps instead of leaving the PR
   silent. Resolve each review thread once it is fixed or answered: an
   unresolved thread is what the lander reads as an open finding. After
   updating the original PR, close any superseded autofix PR with a comment
   saying why; the lander closes `autofix/pr-<number>` drafts itself when
   their source PR merges.
8. Verify fixes before reporting completion. For ineligible findings or failed
   autofix, address verified findings directly. Do not assume every review
   triggers autofix. Push tested manual corrections within the authorized scope
   and wait for the updated review. Report missing review or unresolved
   automation status as pending. Commit/push/PR per "Shipping autonomy" in
   `~/.config/agents/AGENTS.md`, then land the PR with
   `python3 ~/.claude/skills/land-pr/pr_tool.py land <owner/repo#N> --apply`.
   Exit `3` means checks are still running: run the same command again.

## Notes

- The council review, and any additional local review, runs before push; it
  does not replace waiting for the automated PR review.
- CodeRabbit retries are commands, not new commits: `@coderabbitai full
  review` for a failed, cancelled or missing review on a head,
  `@coderabbitai resume` for a paused one. A plain `@coderabbitai review` is
  incremental and does nothing on a head it has already recorded.
- To watch a PR without triggering autofix, put `skip-auto-fix` on its own
  line in the PR body (`~/.claude/instructions/github-issues.md`).

## From AGENTS.md: PR review through the repo's configured automated reviewer

Moved from `~/.config/agents/AGENTS.md` on 2026-11-24 so that file stays under agy's rule-file cut (22,035 bytes, measured 2026-11-25); reworded for the review council on 2026-11-25. AGENTS.md keeps the rule in brief and points here; this text is the full version and is equally binding.

When the user asks to commit, push, or open a PR (or gives a shipping
go-ahead), run the local checks, commit, run the review council (see
"Shipping autonomy" in `~/.config/agents/AGENTS.md`; runner and commands in
`~/.claude/instructions/model-delegation.md`, "Review council"), push, and
open the PR with its `## Release notes` section; the version bump is cut when
the PR lands, not before. That request authorizes whatever automated reviewer
the repo has configured to review the PR. After opening, wait for that review
(2-5 minutes) and inspect its results and any autofix PR by the procedure
above. The council review runs before push; it does not replace the wait for
the automated review. On a repo with no automated reviewer configured, the
council review of the committed diff stands in for it. A repo's own pre-PR
reviewer (a script the repo ships) runs beside the council, not instead of
it.

A council member that cannot run is never a gate: name it and the reason in
the PR body and go on. Only when no member can run at all, review the PR's
full range, `git diff <remote>/<base>...HEAD`, with the running CLI's own
reviewer (Claude Code: `/code-review <remote>/<base>...HEAD`; other CLIs:
write the diff to a file and review it), with `<base>` the PR's actual base
branch (`main`, `master`, ...) and `<remote>` the remote that hosts it
(`origin`, or `upstream` in a fork workflow; fetch it first). Never a bare
`/code-review`: it reviews only the commits ahead of the branch's upstream
plus uncommitted edits, so once the branch is pushed it skips the PR's
earlier commits.

Sequence: implement → tests green → commit → review council → reconcile/fix →
commit the fixes and review them again → push → PR → the repo's automated
reviewers → land.

**Which automated reviewer that is varies by repo, so read the repo's own
`AGENTS.md` rather than assuming.** A repo's `AGENTS.md` adds reviewers to
the council; it never replaces or closes it. It is not necessarily a Claude
Code GitHub App. Two properties decide which one you actually gate on,
and they differ by vendor:

- **Does it re-review a push?** Some reviewers review on PR *open* only, so
  after you add commits their check goes missing and a fresh review has to be
  triggered by hand — otherwise the commits you actually merge are unreviewed.
  Others re-review every push, but only while the settings that control that
  are right: watch for one that pauses automatic review after N reviewed
  commits, because it goes quiet *later*, on a long PR, with a green check.
- **Does its check passing mean "no findings"?** Usually not — it means the
  review ran. Findings arrive as inline comments while the summary body stays
  empty, so the check is green and the conversation tab looks clear with a
  real finding sitting in a thread. A passing check can also mean the review
  was rate-limited or skipped rather than performed, so read the check run's
  output title, not just its conclusion.

The gate is therefore the check reporting **on the head you are merging** *and*
the inline comments read — never the check alone. Know, too, whether these
reviewers are required status checks at all: if the ruleset does not require
them, waiting on them is your rule rather than enforcement, which is exactly
why it has to be written down.

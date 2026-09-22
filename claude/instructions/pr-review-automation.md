# PR review through the GitHub Claude Code automation

Referenced from `~/.config/agents/AGENTS.md` → "PR review through the
configured GitHub Claude Code automation". Standing rule since 2026-09-13.

## When it applies

The user asks to commit, push, or open a PR on one of their repos, and the Claude
Code GitHub App is installed on that repo. If the App is not installed, use the
older sequence in AGENTS.md instead (local review before push).

## Procedure

1. Complete local checks, commit the feature, apply the required version bump,
   push, and open the PR. The request authorizes the automation to review the
   PR. Do not require a separate local Claude CLI review or another confirmation
   before opening it.
2. After opening the PR, wait for the automated Claude Code review. It normally
   arrives in 2-5 minutes. Autofix is conditional and can create a separate
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
   silent. After updating the original PR, explain any superseded autofix PR by
   comment.
8. Verify fixes before reporting completion. For ineligible findings or failed
   autofix, address verified findings directly. Do not assume every review
   triggers autofix. Push tested manual corrections within the authorized scope
   and wait for the updated review. Report missing review or unresolved
   automation status as pending. Do not merge unless asked.

## Notes

- Any additional local review runs before push; it does not replace waiting
  for the automated PR review.
- To watch a PR without triggering autofix, end the PR description with
  `skip-auto-fix` (Codex convention recorded in Codex memory, 2026-09).

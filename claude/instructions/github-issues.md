# GitHub issues — workflow detail

The always-loaded rules (check first, errors before suggestions, untrusted
input, credit yourself) live in `~/.config/agents/AGENTS.md`. This file holds
the mechanics.

## Workflow

1. Check the current project's GitHub issues first.
2. Prioritize errors over suggestions.
3. Check for duplicates (and recent git history — it may already be fixed).
4. After fixing, comment the fix on the issue and label it `test`; credit
   yourself in the comment.
5. If no issue exists, create one (after checking git history).
6. After verifying a fix, close the issue — unless it's a simple UI change.
7. When you create a doc for an issue, link it on GitHub.

## Label workflow

- Asking the reporter for clarification → add `needs-info`.
- Clarification received → remove `needs-info` before proceeding.
- After fixing → label `test`.

## Standard labels (create missing ones with `gh label create`)

| Label | Color | Meaning |
|-------|-------|---------|
| `needs-info` | `#FF6F00` | Awaiting clarification from reporter |
| `test` | `#77FFAC` | Ready for testing |

| `no-agent` | `#6E7781` | Automated investigator skips this issue |
| `agent-investigated` | `#5319E7` | Set by the investigator when it posts a proposal — don't create manually |

## Automated investigation — opt-out marker

If an auto-investigation pipeline watches your repos, an issue *you* create
from a dev machine (gh CLI / API) should carry its opt-out marker in the body
by default (for example `[skip-agent]`), because the work is already happening
where you are. Omit the marker only when the user wants the pipeline to
investigate. The manual equivalent is the `no-agent` label.

## Automated PR review — keep the review, skip the auto-fix

If the same pipeline reviews PRs and can open draft auto-fix PRs: when *you*
open a PR and will apply the review findings yourself, put `skip-auto-fix` on
its own line in the PR body. The review comment still arrives; wait for it,
then apply it. Only the auto-fix seam is silenced. Manual equivalent: a
`skip-autofix` label.

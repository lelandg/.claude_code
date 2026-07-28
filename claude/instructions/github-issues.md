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

If you run an automated issue-investigation pipeline on your repos, add its
opt-out marker/label conventions here so assistant-created issues don't
trigger redundant investigations.

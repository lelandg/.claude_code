# File dispositions — standing approvals for working-tree files

Living registry consulted **before branching** (and any time an agent must
decide what to do with modified/untracked files). Agents: when a pattern below
matches, apply the default without re-asking; when nothing matches, ask via a
prompt (AskUserQuestion in Claude Code) with a recommendation — then **record
the decision here** (pattern, disposition, rationale, date) so the next agent
doesn't ask again. Repo-specific entries name the repo; the rest are global.

Dispositions: **commit** (to main or current branch, per context) ·
**gitignore** (add pattern to the repo's .gitignore) · **leave** (WIP, don't
touch, don't carry into branches) · **ask** (genuinely per-case).

## Global patterns

| Pattern | Default | Why | Added |
|---------|---------|-----|-------|
| `Docs/plans/`, `Plans/` design/handoff docs | **commit** immediately | Existing house rule (plan files are part of the implementation record) | 2026-07-10 |
| `Notes/` summaries/reports agents wrote | **commit** | Written as deliverables; same reasoning as plans | 2026-07-10 |
| `_screenshots` symlink | **gitignore** | Machine-local symlink to the screenshots drive | 2026-07-10 |
| `.env*`, credentials, key files | **never commit** | Security rules | 2026-07-10 |
| Script WIP the user edited (e.g. `Scripts/*.py` with uncommitted tweaks) | **ask** — recommend commit if it's a finished functional change, leave if half-done | Users often have modified files from running/tweaking scripts | 2026-07-10 |

## Example: <your-repo>

Add a section per repo as decisions accumulate. Example entries:

| Pattern | Default | Why | Added |
|---------|---------|-----|-------|
| `generated/latest-snapshot.*`, snapshot commits `chore(snapshots): …` | **leave on local main — never carry into branches/PRs** | Commit-not-push publish pattern (avoids CI/deploy triggers); once leaked into a PR when a branch was cut from local main | YYYY-MM-DD |
| `Docs/CodeMap.md` regenerated | **commit** (docs housekeeping to main) | Matches prior chore commits | YYYY-MM-DD |
| `*.bak-*` backup files | **gitignore** | Tool-generated backups, never source | YYYY-MM-DD |

## How to add entries

Append a row when the user approves/declines a disposition. Keep rows one line,
pattern-first, with the date. If a default stops matching reality (the user
starts declining), update the row rather than piling on exceptions.

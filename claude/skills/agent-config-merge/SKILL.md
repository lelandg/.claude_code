---
name: agent-config-merge
description: Apply approved items from an agent-config drift report — publish WSL intent into this repository's sanitized record, reconcile the Windows target, and propose native plugin commands. Use when Leland says "apply the drift report", "publish those config changes", "merge items X and Y from the report", "reconcile Windows config", or "restore the last config merge". Always dry-runs and asks before writing anything.
---

# Apply an Agent Config Drift Report

This is the only skill that writes configuration. It applies **explicitly named
item ids** from a report, and nothing else. WSL live configuration is never
rewritten — only the repository record and the Windows target.

Design: `Docs/plans/2026-08-08-wsl-authoritative-agent-config-sync-design.md`
Report skill: `agent-config-report` · Operator guide: `Docs/agent-config-sync.md`

## 1. Get the item ids

Read `~/.local/state/agent-config-sync/latest-report.md` (or the run id Leland
named, from `reports/<run-id>.md`).

If Leland has not named specific ids, **ask** with AskUserQuestion — do not
infer "all of them". Offer, as separate choices: the safe portable updates
only, the **deletions** as their own group, safe updates plus a specific
reconcile-Windows id, or a list he types.

**Always offer the deletions.** When the report holds items that are gone
from WSL but still present in a target — `publish_to_repo` with a "Removed in
WSL" detail, `additive_delete_requires_approval`, `windows_only`, and
`plugin_removed` — list them and ask whether to remove them from the targets.
WSL is the authority; these are removals Leland already made, waiting to be
propagated. Naming the id is the approval; nothing is ever deleted unnamed.

**Not every item can be applied, even by id.** `merge.py` turns these
classifications into actions: `publish_to_repo`, `wsl_only`,
`reconcile_windows`, the deletions above (`additive_delete_requires_approval`,
`windows_only`, deletion-shaped `publish_to_repo`), `plugin_removed`, and the
plugin command classifications (`plugin_missing`, `plugin_enabled_differs`,
`plugin_version_differs`, `plugin_pin_violation`).
Everything else — most importantly **`conflict`** — is skipped unconditionally,
even when named, with "requires a decision, not an automatic action" (the
same skip also catches `plugin_extra` and `plugin_incompatible`).
`protected_overlay` is refused too, but earlier and by a different guard —
the `platform_overlay` policy check, with the message "protected Windows
state; never applied", not this one.

There is no id-based way to make this tool pick a side in a conflict, but it
is not a dead end — it is a loop back through WSL. `compare.py`'s `classify()`
produces `conflict` for two distinct reasons, with two distinct fixes; in
both cases the fix is a **WSL** edit or a manifest change, never a direct
edit to the repo or Windows file:

- **Genuine value divergence, three-way** (WSL, repo, and Windows have each
  drifted from one another — most real conflicts): edit **WSL** to whichever
  value is intended — WSL is the authority, so the tool refuses to guess
  which side wins on Leland's behalf — then re-scan. The item reclassifies as
  `reconcile_windows` (WSL now matches the repo baseline) or `publish_to_repo`
  (WSL now matches Windows). Either way it becomes an id-applicable item this
  same skill can apply on the next pass.
- **Genuine value divergence, no baseline yet** (the repo has no record of
  this field at all, and WSL and Windows disagree — `compare.py:116-124`):
  the loop only closes if the intended value happens to match what Windows
  already holds — edit WSL to that value and re-scan; it reclassifies as
  `publish_to_repo`. If the intended value differs from Windows's current
  value, editing WSL does **not** resolve it: with no repository baseline to
  compare against, the item stays `conflict` and `merge.py` still has no
  id-applicable action for it. Say this plainly rather than promising it
  always resolves — closing it that way means writing the repo file
  directly, outside this tool's normal WSL→repo flow, which is a separate
  operation this skill does not perform.
- **Ownership undeclared** (no policy is set for the field, and the layers
  disagree): the fix is declaring a policy for that field in
  `config/agent-sync.toml`, then re-scanning. This is a different fix for a
  different cause — declaring a policy does not by itself resolve a value
  divergence; if the layers still genuinely disagree once the policy is
  declared, the fresh scan can still show `conflict`, and the WSL-edit path
  above still applies.

This skill only shows that the current item was skipped and explains why —
never resolve a conflict in place, and never offer "conflict resolution via
id" as if `merge.py` could execute it.

## 2. Dry-run — always first

```bash
python3 /mnt/d/Documents/Code/GitHub/.claude_code/tools/agent-config-sync/merge.py plan \
  --drift ~/.local/state/agent-config-sync/latest-drift.json \
  --manifest /mnt/d/Documents/Code/GitHub/.claude_code/config/agent-sync.toml \
  --id <ID> [--id <ID> ...]
```

`plan` (and `apply`) only re-verify the entries the named ids reference — a
fast, scoped check, not the full ~146-second scan. It will not hang.

Exit `22` means the report is **stale** — a file changed since the scan. Do not
work around it. Re-run `agent-config-report` and start over with the new ids.

Show Leland the plan verbatim, plus a one-line explanation per action of what
changes and why it is safe.

**Read every action line completely — one action can write two files.** A
`publish_to_repo` or `wsl_only` action writes its primary target (the repo)
and *mirrors* the same write onto the Windows target in the same action. The
dry run spells this out at the end of the line:

```
write /path/to/repo/X from WSL (mirrors to /path/to/windows/X)
```

A `set_field` action on a JSON/TOML entry shows the identical pattern
(`set <pointer> in <target> from WSL (mirrors to ...)`). Approving that item
id moves **both** files, not one — say so explicitly when presenting the plan
to Leland. If a line does not end in `(mirrors to ...)`, only the shown target
is written — for example, `reconcile_windows` actions only ever touch the
Windows file, never the repo.

**Deletion actions need the same two-file reading, plus one more caution.**

- `[delete_file]` removes the named file; `(also deletes ...)` at the end of
  the line means the Windows copy goes in the same action.
- `[delete_tree]` removes a whole directory **recursively — including temp
  files, scripts, and caches the scan never tracked**. The line carries the
  file count. Read that count to Leland before asking for approval; approving
  the id approves the sweep. A second selected id inside the same directory
  shows as `[noop] ... covered by the directory deletion`.
- `[delete_field]` removes the JSON key from the target document (never
  writes `null`).
- `[remove_plugin_from_record]` edits `enabledPlugins` in the repository's
  `claude/settings.json` and may also print a `claude plugin uninstall`
  command — printed for Leland to run by hand, never executed.

Every deleted file is backed up first; `merge.py restore` rebuilds the full
tree, untracked files included.

## 3. Get approval for the exact scope

Ask explicitly, naming the item ids and the files that will be written —
including both sides of any `(mirrors to ...)` pair. An approval covers only
the ids in that message. If Leland adds one afterwards, dry-run again.

`apply` with no `--id` exits `23` — there is deliberately no "apply
everything." Approval must always resolve to a concrete, non-empty id list
before you run `apply`.

## 4. Apply

```bash
python3 /mnt/d/Documents/Code/GitHub/.claude_code/tools/agent-config-sync/merge.py apply \
  --drift ~/.local/state/agent-config-sync/latest-drift.json \
  --manifest /mnt/d/Documents/Code/GitHub/.claude_code/config/agent-sync.toml \
  --id <ID> [--id <ID> ...]
```

Report the backup directory it prints, and the restore command it echoes at
the end — Leland does not need to reconstruct it. **Plugin commands are
printed, never run** — under the heading "Run these by hand — this tool never
executes a package manager:" — hand them to Leland to execute; that is
deliberate.

## 5. Verify

Re-run the scan (`agent-config-report` step 1). Expected drift should be gone
and nothing new should appear. If something new appears, say so plainly and
offer the restore command:

```bash
python3 /mnt/d/Documents/Code/GitHub/.claude_code/tools/agent-config-sync/merge.py restore \
  --backup-dir <the directory printed by apply>
```

(If Leland no longer has the backup directory, `--run-id <run-id>
--state-dir ~/.local/state/agent-config-sync` finds the same backup.)

If a repository file changed, follow the house rules: typecheck-equivalent
(`python3 -m pytest tools/agent-config-sync/tests/ -q`), then commit —
only when Leland asks.

## When to escalate to /codex

Recommend an independent cross-provider review — and only then — when there is
a **concrete** advantage:

- An ambiguous semantic merge in a settings field where both sides look valid.
- A Codex-specific setting (anything under `~/.codex/`).
- A high-risk conflict: hooks, permissions, or anything touching credentials
  handling.

Scheduling is never a reason. Commit everything first (`/codex:review` needs a
clean tree, and Sol is review-only). Codex recommendations are **advisory** —
they can change how you explain a conflict, never which ids get applied.
Leland approves the final patch, not an agent-to-agent conversation.

## Rules

- Never apply an id that was not named.
- Never expect a `conflict`, `protected_overlay`, `plugin_extra`, or
  `plugin_incompatible` item to apply — the tool always refuses these, even
  when named; do not look for a workaround.
- Deletions (`windows_only`, `additive_delete_requires_approval`,
  deletion-shaped `publish_to_repo`, `plugin_removed`) apply only when named,
  and a `delete_tree` sweep removes untracked files too — read its file count
  to Leland before asking for approval.
- Never touch a `platform_overlay` item; the tool refuses, and so should you.
- Never edit `/home/leland` config to "fix" drift — WSL is the authority, and
  changing it is Leland's job, not a merge.
- Never bypass a stale-report rejection.
- Never run `claude plugin install/update/enable/disable` yourself.
- Never print a value from a redacted field.

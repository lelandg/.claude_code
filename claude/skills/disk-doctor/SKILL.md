---
name: disk-doctor
description: Use when the user wants to free up disk space or check install hygiene on their machine — "clean up my disk", "my drive is full", "find junk files", "did I install something in the wrong place", "make a cleanup runbook". Scans home + dev/cache locations, proposes a plain-English plan, then either cleans up (recoverable Trash with one-command undo) or writes a runbook. Never touches system files; deletes only via the audited safe-trash helper.
---

# disk-doctor

Reclaim disk space and surface install-hygiene problems — safely. You scan and
reason; the bundled `bin/safe-trash` is the ONLY thing that may delete, and it
only ever moves files to the Trash with a guaranteed undo.

## Absolute rules (never break these)

1. **Never delete with `rm`, `shutil`, `os.remove`, or any direct call.** Every
   deletion goes through `bin/safe-trash`. No exceptions.
2. **Never touch system directories** or anything on the denylist floor in
   `bin/disk_doctor_core.py`. If unsure, don't.
3. **Dry-run first, always.** Show the plan (a `safe-trash` run WITHOUT
   `--commit`) and get explicit approval before committing.
4. **Report hygiene issues; never auto-fix package environments.**

## Workflow

1. **Detect the OS** (`uname`, platform). Load the matching `rules/<os>.md`
   (`linux.md` / `macos.md` / `windows.md`). State which platform you detected.
   If the rule pack is missing or fails `validate_rule_pack`, stop and say so.
2. **Scan** the rule pack's "Allowed roots" read-only. Apply the "Cache-clean
   rules" to find candidates; gather sizes, ages, and categories. Compute
   duplicates by size then SHA-256.
3. **Run the install-hygiene checks** from the rule pack — read-only
   (`pip list`, `npm ls -g`, PATH inspection). Never import or run project code.
4. **Build the plan**: fill `reference/report-template.md` and write it to
   `~/.disk-doctor/runs/<run-id>-plan.md`. Rank by reclaimable size.
5. **Present the plan summary**, then **use the AskUserQuestion tool** to ask:
   - **"Clean up now"** or **"Create a runbook"**.
6. **If "Clean up now":**
   - If there is more than one cleanup category, **use AskUserQuestion again**
     (multi-select) so the user picks which categories — list each with its size,
     plus an "Everything" option. Keep it one decision, not item-by-item.
   - For each chosen category, run `bin/safe-trash --allow <root> --commit
     --run-id <run-id> <paths...>`. Show the JSON results.
   - Report total reclaimed, that files went to the Trash, and that
     `bin/disk-doctor-undo` reverses the whole run.
7. **If "Create a runbook":**
   - **Use AskUserQuestion** for the format: **Markdown**, **HTML**, or **Other**
     (free text — honor what they type; if you can't, say so and give the closest).
   - **Markdown:** fill the template, save `~/.disk-doctor/runs/<run-id>-runbook.md`.
   - **HTML:** invoke the `html-doc` skill to render a polished standalone page from
     the same content; save `...-runbook.html`.
   - The runbook lists every finding + the exact `safe-trash` command to reclaim it,
     plus the hygiene section. **Make no changes to the system.** Surface the file path.

## Helpers

- `bin/safe-trash [--allow ROOT]... [--commit] [--run-id ID] [--quarantine] PATH...`
  — dry-run unless `--commit`. Refuses denied/disallowed/symlink paths. One JSON
  record per path on stdout.
- `bin/disk-doctor-undo [--run ID]` — restores a run (latest by default) from the
  manifest. Never overwrites existing files.

## Platform notes

- **Linux:** trashing uses the FreeDesktop spec — items appear in the system Trash
  AND undo is fully automatic.
- **macOS / Windows (v1):** trashing works; automatic undo is not yet implemented —
  tell the user to restore from the Trash/Recycle Bin using the run's manifest at
  `~/.disk-doctor/runs/<run-id>.jsonl`.

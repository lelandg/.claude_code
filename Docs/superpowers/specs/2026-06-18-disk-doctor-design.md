# disk-doctor — Design Spec

**Status:** Approved (brainstorming complete) — ready for implementation planning
**Last updated:** 2026-06-18 08:01
**Author:** Leland Green (with Claude)
**Origin:** Idea from Nick Paletta — a skill for non-technical users that scans a PC, cleans up disk space, and fixes "things installed in the wrong place." Scoped down here to a safe, shippable v1.

---

## 1. Summary

`disk-doctor` is a Claude Code skill that helps a user reclaim disk space and find install-hygiene problems on their machine — safely. It scans the user's home and dev/cache locations, classifies what's reclaimable, proposes a plain-English plan, and only ever deletes through a single hardened helper that moves files to the system Trash and records a guaranteed undo.

It is cross-platform (Linux/Pop!_OS, macOS, Windows) via per-OS **rule packs** — plain data files the engine loads based on the detected OS. The dangerous code lives in exactly one place and is identical on every platform.

### What v1 does
- **Disk cleanup:** package/build caches, stale `node_modules`/`__pycache__`/`.venv`, duplicates, pending trash, old logs, large-and-old files.
- **Install-hygiene checks (report-only):** pip installed outside a venv, global npm packages, projects missing a venv, duplicate Python toolchains, orphaned env leftovers.

### What v1 explicitly does NOT do (deferred)
- Moving/organizing user files (Downloads/Desktop → "right place"). High-risk; deferred until the safety model is proven.
- Auto-fixing package environments. Hygiene issues are reported with suggested commands; humans stay in that loop.
- Any always-on/background daemon ("maintain at all times"). On-demand only.
- Touching system directories at all.

---

## 2. Decisions (settled during brainstorming)

| Decision | Choice |
|---|---|
| v1 scope | Disk cleanup + install-hygiene (no user-file moving) |
| Safety model | Propose → approve → Trash (recoverable). Hygiene = report-only, never auto-fix. |
| Form factor | Claude-driven Claude Code skill + one audited safety helper (Approach B) |
| Plan artifact | A written plan file serves as the approval gate (borrowed from Approach C) |
| Scan scope | Home + dev/cache locations. System dirs never touched. |
| Cross-platform | OS detection selects the matching rule pack (data, not code) |
| Name | `disk-doctor` |

---

## 3. Architecture

Three clean layers, each independently understandable and testable.

```
claude/skills/disk-doctor/
├── SKILL.md                  # the workflow Claude follows (the "engine")
├── rules/
│   ├── linux.md              # Pop!_OS / Debian-family conventions + rules
│   ├── macos.md              # macOS conventions
│   └── windows.md            # Windows conventions
├── bin/
│   ├── safe-trash            # the ONE audited deletion helper (Python, cross-platform)
│   └── disk-doctor-undo      # restores from the latest manifest
└── reference/
    └── report-template.md    # shape of the plan/report Claude writes
```

| Layer | Responsibility | Depends on |
|---|---|---|
| **SKILL.md (engine)** | Detect OS → load matching rule pack → orchestrate scan, classify, propose, act, report. Pure instructions; no platform specifics baked in. | rule packs, `bin/` |
| **Rule packs (data)** | Per-OS facts: where Downloads/cache/dev dirs live, what's safe to clean, what's never touched, install-hygiene rules. Editable without touching logic. | nothing |
| **`bin/` helpers (safety core)** | `safe-trash` enforces allowlist + denylist, moves to Trash, writes undo manifest. `disk-doctor-undo` reverses it. The only thing that deletes. | OS trash facility |

**Key property:** adding a distro or tightening a rule = editing a markdown file. The dangerous code lives only in `safe-trash` and is the same on every platform.

---

## 4. Safety core (`safe-trash` + `disk-doctor-undo`)

The only component that can delete. Specified carefully because it protects the user's data.

### `safe-trash <path>... [--commit]` — guarantees, in order

1. **Resolve & canonicalize** every path (symlinks, `..`, `~`) to an absolute real path. Operate only on the resolved path so a symlink can't smuggle in a system file.
2. **Denylist check (hard fail):** refuse if the resolved path is, or is inside, a never-touch location. The **absolute floor** of the denylist lives **in the script**, not the rule pack — no rule edit can weaken it. Rule packs may *add* per-OS never-touch entries on top of this floor (additive only — a rule pack can tighten the denylist, never loosen it).
3. **Allowlist check (hard fail):** refuse unless the path is inside an explicitly allowed root passed by the caller. **Deny-by-default.**
4. **Move to Trash** using the OS-native facility (`gio trash` / macOS Trash / Recycle Bin) — never `rm`. If native trash is unavailable, fall back to a dated quarantine folder. Never a hard delete.
5. **Write a manifest entry before each move:** original absolute path, trash/quarantine destination, size, timestamp, run ID. One JSONL manifest per run at `~/.disk-doctor/runs/<run-id>.jsonl`. If the manifest can't be written, **abort that deletion.**
6. **Refuse to cross filesystems; refuse symlinked dirs as targets; do not follow symlinks** during directory walks.

### Never-touch denylist (absolute, in-script)

- Filesystem/system roots: `/`, `/usr`, `/etc`, `/bin`, `/boot`, `/System`, `/Library`, `C:\Windows`, `C:\Program Files`
- The user's home root itself (only subdirs may be cleaned, never `$HOME` directly)
- Config / secrets: `~/.ssh`, `~/.config`, `~/.gnupg`
- App data: `~/.local/share`
- Browser profiles (bookmarks, history, logins, cookies):
  - Linux: `~/.mozilla`, `~/.config/google-chrome`, `~/.config/chromium`, `~/snap/firefox`
  - macOS: `~/Library/Application Support/{Firefox,Google/Chrome,Chromium}`
  - Windows: `%APPDATA%\Mozilla\Firefox`, `%LOCALAPPDATA%\Google\Chrome\User Data`, `\Chromium\`

**Nuance:** browser *cache* subdirs (e.g. `~/.cache/mozilla`, `~/.cache/google-chrome`) remain cleanable — it is the *profile* dirs above that are denied. Rule packs must keep cache-clean rules and the profile denylist non-overlapping.

### `disk-doctor-undo [--run <id>]`

Reads the manifest (latest run by default), restores each item from Trash/quarantine to its original path, warns on any collision (never overwrites), and marks the manifest reversed.

### Two hard rules

- **Dry-run is the default.** `safe-trash` without `--commit` prints exactly what it *would* do and writes no changes. Claude always runs the dry pass first and shows it as the plan.
- **Everything is logged** to `~/.disk-doctor/disk-doctor.log` (per the user's "all errors logged, platform-independently" rule): every refusal, move, and undo, with reasons.

---

## 5. Workflow (one run)

1. **Detect OS** → load `rules/<os>.md`. State which platform was detected.
2. **Scan** the allowlisted roots (home + dev/cache locations). Gather sizes, ages, categories: package/build caches, stale `node_modules`/`__pycache__`/`.venv`, duplicates (by size then hash), pending trash, old logs, large-and-old files. *Read-only.*
3. **Run install-hygiene checks** (Section 6) — report-only.
4. **Build a plan** → write to `~/.disk-doctor/runs/<run-id>-plan.md` using the report template: ranked by reclaimable size, plain-English reason per item, grouped by category, with a clear total. Hygiene findings in their own section.
5. **Present the plan** in chat (the dry-run output) and ask for approval — all, by category, or item-by-item.
6. **Act** on approved items via `safe-trash --commit`, which writes the manifest as it goes.
7. **Report** what was reclaimed, where it went (Trash), and how to undo (`disk-doctor-undo`).

The user always sees the full plan before anything moves; undo is one command.

---

## 6. Install-hygiene checks (report-only)

Every check only reports — plain-English explanation + suggested fix command. Never changes anything. The hygiene scan **reads** package locations (e.g. `pip list`, PATH inspection); it never imports, runs, or modifies any environment.

| Check | Flags | Suggested fix (shown, not run) |
|---|---|---|
| pip into system/user Python | Packages installed outside any venv (system site-packages or `~/.local/lib/python*`) | "Create a venv and reinstall there: `python3 -m venv .venv && …`" |
| Global npm packages | Non-essential packages in the global npm prefix | "Prefer per-project installs or `npx`" |
| Projects missing a venv | Dev project dirs (`requirements.txt`/`pyproject.toml`) with no `.venv`/virtualenv | "This project installs into your system Python — add a venv" |
| Duplicate Python toolchains | Overlapping conda + system + pyenv installs | Explain which `python3`/`pip` actually resolves on PATH |
| Orphaned env leftovers | `.venv`/`node_modules` in stale/abandoned project dirs | Offered as a *cleanup* item (Section 5), not a hygiene fix |

This is the repeatable version of Nick's "tell me where to install" GPT setting — an audit that points at the actual offenders on his machine.

---

## 7. Error handling (fail safe, never fail destructive)

| Situation | Behavior |
|---|---|
| Permission denied while scanning | Skip that path, log, keep going — never crash a run over one unreadable dir |
| Native Trash unavailable | Fall back to dated quarantine folder, warn where it went |
| Path won't canonicalize / dangling symlink | Skip + log; never act on an unresolved path |
| Manifest write fails | Abort that deletion — never move anything we can't record an undo for |
| Undo target path occupied | Never overwrite; report the collision, leave the trashed copy in place |
| Rule pack missing/malformed for detected OS | Stop with a clear message; don't guess conventions |

All of the above is written to `~/.disk-doctor/disk-doctor.log`.

---

## 8. Testing

The safety core is the only code and the dangerous part, so it gets real tests against a throwaway sandbox dir, including adversarial cases:

- Refuses a system path (`/etc/...`, `C:\Windows\...`) — hard fail
- Refuses a path outside the allowlist — hard fail
- Refuses a symlink that resolves into a denied/outside location
- Refuses to act if the manifest can't be written
- Dry-run writes **zero** changes
- Commit → manifest matches what moved → `undo` restores every item to its origin (round-trip)

Plus:
- **Rule-pack validator:** each pack has the required sections (allowed roots, never-touch, cache rules, hygiene rules).
- **Manual smoke test** on Pop!_OS as the real-world check before v1 is considered done.

---

## 9. Future phases (out of scope for v1)

- **v2 — File organizer:** move misplaced user files (Downloads/Desktop) into conventional locations, same propose-first / Trash / undo model. Windows/macOS is the bigger market here (they have canonical "right places"; Linux user files do not).
- **v3 — Always-on agent:** background monitoring/maintenance, only after v1/v2 earn trust.
- **Standalone CLI product:** `safe-trash` is the seed; the engine could be reimplemented as a sellable cross-platform CLI with no Claude dependency.

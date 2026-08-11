---
name: agent-config-report
description: Scan for drift between WSL agent configuration (the authority), this repository's sanitized record, and the Windows target, then explain the resulting report. Use when Leland asks "what config has drifted", "check my agent config sync", "is Windows out of date", "run the config drift scan", asks about a drift report by run id, or asks why his laptop and desktop behave differently, why a skill/agent/setting is missing on one machine, or whether his machines are in sync. Read-only — it never applies a change; use agent-config-merge for that.
---

# Agent Config Drift Report

WSL is the authority for portable agent configuration. This repository is the
sanitized record. Windows is a derived target with a protected overlay.
This skill **reports**. Applying anything is the separate `agent-config-merge`
skill, which always needs explicit approval.

Design: `Docs/plans/2026-08-08-wsl-authoritative-agent-config-sync-design.md`
Operator guide: `Docs/agent-config-sync.md`

## What a scan costs

A full scan takes about **146 seconds** (measured twice on this machine, both
runs 140–150s). It is disk-bound, not stuck — do not kill it partway through
and do not re-run it while waiting; a killed run leaves a stale lock behind.
Tell Leland up front that this takes over two minutes before running it.

On this machine, a scan currently reports **340 items**, `latest-drift.json`
around 174 KB, `latest-report.md` around 103 KB, and it exits `10` — drift is
the expected, normal outcome here, not an error. The breakdown by type:

| Type | Count |
|---|---|
| `windows_only` | 93 |
| `wsl_only` | 71 |
| `reconcile_windows` | 57 |
| `conflict` | 40 |
| `plugin_missing` | 25 |
| `plugin_enabled_differs` | 22 |
| `plugin_extra` | 11 |
| `protected_overlay` | 7 |
| `publish_to_repo` | 6 |
| `additive_delete_requires_approval` | 5 |
| `plugin_version_differs` | 2 |
| `plugin_incompatible` | 1 |

47 of the 340 items also carry at least one portability warning (a hardcoded
machine path that would not survive a move) — **65 warnings in total**, since
an item can trip more than one (32 items carry one, 12 carry two, 3 carry
three). The 65 instances break down as: `/mnt/` 30, `.venv_linux` 17, `/usr/`
12, unrooted `/home/` 6. `.config/agents/AGENTS.md` — the canonical house-rules
file every agent CLI reads — is one of the items that trips two: it names both
a WSL mount path and `.venv_linux`. Mention the item count (47) if Leland asks
about portability; do not enumerate all of them unless asked.

## 1. Run the deterministic scan

```bash
python3 /mnt/d/Documents/Code/GitHub/.claude_code/tools/agent-config-sync/scan.py \
  --manifest /mnt/d/Documents/Code/GitHub/.claude_code/config/agent-sync.toml
echo "exit=$?"
```

Read the exit code before anything else:

| Exit | Meaning | Do next |
|---|---|---|
| `0` | No drift | Say so and stop. Do not render a report. |
| `10` | Drift found | Continue to step 2. This is the normal result on this machine. |
| `20` | Scan failure | Report the stderr message. Do **not** fall back to reading config by hand — fix the manifest. |
| `21` | Lock held | Another scan is running. Wait and retry once. |

## 2. Render the report

```bash
python3 /mnt/d/Documents/Code/GitHub/.claude_code/tools/agent-config-sync/render.py \
  --drift ~/.local/state/agent-config-sync/latest-drift.json \
  --state-dir ~/.local/state/agent-config-sync
```

Exit `20` means the drift document is missing or malformed — `render.py`
could not read or parse `latest-drift.json`. Say so, and re-run the scan
(step 1) to regenerate it. Never open or edit `latest-drift.json` by hand to
work around this — the same rule as an exit `20` from `scan.py`.

Exit `30` means the analyzer failed. The previous valid report is untouched —
say so, and offer to re-run with `--no-model` to render from the deterministic
scan alone (no Claude call, no subscription usage):

```bash
python3 /mnt/d/Documents/Code/GitHub/.claude_code/tools/agent-config-sync/render.py \
  --drift ~/.local/state/agent-config-sync/latest-drift.json \
  --state-dir ~/.local/state/agent-config-sync \
  --no-model
```

## 3. Explain it

Read `~/.local/state/agent-config-sync/latest-report.md` and summarize for
Leland in this order:

1. **Conflicts requiring judgment** — these are the only items that need a
   decision. On this machine there are 40, including
   `.config/agents/AGENTS.md`, `.claude/CLAUDE.md`, 8 instruction files, 5
   fields in `.claude/settings.json`, and 2 in `.codex/config.toml`. Say what
   changed on each side; never pick a winner yourself.
2. **Safe portable updates** — one line each.
3. **Plugin differences** — call out any pin violation explicitly. Never
   propose a downgrade unless the report shows an explicit pin.
4. **Protected Windows state** — mention only if Leland asks; it is not
   actionable by design.
5. **Scan errors** — a malformed file blocks its own item, nothing else.

Then quote the item ids Leland would need to approve. Nothing is applied.

## Rules

- Never read a live config file to "double-check" the scanner. If the scanner
  and your intuition disagree, the manifest is wrong — fix `config/agent-sync.toml`.
- Never print a value from a secret-bearing field, even if you can see it. The
  report deliberately carries pointers, reason codes, and hashes only.
- Never run `merge.py` from this skill. Applying a change is the separate
  `agent-config-merge` skill; hand the approved item ids to it.
- If the report recommends `/codex`, mention it and paste the prompt the report
  generated; do not run it unprompted.

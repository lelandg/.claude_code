# Agent Config Sync — operator guide

WSL is the authority for portable agent configuration. This repository is the
sanitized record. Windows is a derived target with a protected overlay. The
scheduled job **reports**; it never applies a change.

Design: `Docs/plans/2026-08-08-wsl-authoritative-agent-config-sync-design.md`

## What a scan actually costs on this machine

A full scan takes about **140–150 seconds** (roughly 2.5 minutes; a live run
of this wrapper during development measured 146 seconds end to end). It is
disk-bound: `extract_entry` enumerates about **30,000 filesystem entries**
(around 10,276 under WSL, around 20,449 under the Windows 9p mount) to
produce 340 drift items. This cost is known and is not being optimized.
Plan the cron time and any interactive wait around it.

On this machine, a scan currently reports:

| Metric | Value |
|---|---|
| Items | 340 |
| `latest-drift.json` size | ~174 KB |
| `latest-report.md` size | ~103 KB |
| Exit code | `10` (drift reported) |
| Errors | 0 |
| Redactions | 0 |
| Portability warnings | 47 |
| Conflicts needing human judgment | 40 |

Exit `10` is the **normal, expected** result on this machine. Drift exists
between WSL, the repository, and Windows. Do not treat `10` as a failure.

## Run a scan by hand

```bash
python3 /mnt/d/Documents/Code/GitHub/.claude_code/tools/agent-config-sync/scan.py \
  --manifest /mnt/d/Documents/Code/GitHub/.claude_code/config/agent-sync.toml
```

Wait about 2.5 minutes. On success the command prints nothing and exits.
Check the exit code with `echo $?` immediately after:

- `0` — no drift. Nothing to review.
- `10` — drift reported. `~/.local/state/agent-config-sync/latest-drift.json`
  was written. This is the expected result on this machine.
- `20` — scan failure. Read `~/.local/state/agent-config-sync/wrapper.log` (if
  run through the wrapper) or the command's stderr (if run by hand).
- `21` — another scan already holds the lock. Wait for it to finish.

## Render a report

```bash
python3 /mnt/d/Documents/Code/GitHub/.claude_code/tools/agent-config-sync/render.py \
  --drift ~/.local/state/agent-config-sync/latest-drift.json \
  --state-dir ~/.local/state/agent-config-sync
```

Add `--no-model` to render from the deterministic scan alone, with no Claude
call and no subscription usage:

```bash
python3 /mnt/d/Documents/Code/GitHub/.claude_code/tools/agent-config-sync/render.py \
  --drift ~/.local/state/agent-config-sync/latest-drift.json \
  --state-dir ~/.local/state/agent-config-sync \
  --no-model
```

Expected output: exit code `0`, and
`~/.local/state/agent-config-sync/latest-report.md` updated with a new
timestamp. Exit code `30` means the analyzer failed — the previous valid
report is left in place untouched; an invalid model response can never
overwrite it.

## Install the nightly job

The repository ships the wrapper; you own the cron entry. Add it with
`crontab -e`:

```cron
# Agent config drift report, 06:15 daily. Report-only.
15 6 * * * /mnt/d/Documents/Code/GitHub/.claude_code/tools/agent-config-sync/bin/agent-config-sync.sh
```

Confirm the entry is installed:

```bash
crontab -l | grep agent-config-sync
```

Expected output: the line you just added, printed back verbatim.

Set `ACS_CLAUDE` to the absolute path of your Claude executable if it is not
`~/.local/bin/claude`:

```bash
command -v claude
```

Expected output: an absolute path, for example `/home/leland/.local/bin/claude`.
If the command prints nothing, `claude` is not on `PATH` for this shell —
find it another way (for example `which -a claude` or check your install
directory) and set `ACS_CLAUDE` to that absolute path in the crontab line:

```cron
15 6 * * * ACS_CLAUDE=/home/leland/.local/bin/claude /mnt/d/Documents/Code/GitHub/.claude_code/tools/agent-config-sync/bin/agent-config-sync.sh
```

## Environment variables the wrapper reads

All of these have absolute-path defaults; set only the ones that differ on
your machine.

| Variable | Default | Meaning |
|---|---|---|
| `ACS_REPO` | `/mnt/d/Documents/Code/GitHub/.claude_code` | Repository root |
| `ACS_PYTHON` | `/usr/bin/python3` | Python interpreter |
| `ACS_CLAUDE` | `$HOME/.local/bin/claude` | Claude executable |
| `ACS_MANIFEST` | `$ACS_REPO/config/agent-sync.toml` | Manifest path |
| `ACS_STATE` | `$HOME/.local/state/agent-config-sync` | State directory |
| `ACS_SCAN` | `$ACS_PYTHON $ACS_REPO/tools/agent-config-sync/scan.py` | Scan command line |
| `ACS_RENDER` | `$ACS_PYTHON $ACS_REPO/tools/agent-config-sync/render.py` | Render command line |

`ACS_SCAN` and `ACS_RENDER` are full command lines, not single paths — the
wrapper deliberately word-splits them so you can add flags (for example
`--no-model` on `ACS_RENDER`) without editing the script.

## Wrapper exit codes

The wrapper's exit code is the outcome of the whole scheduled run. It is
never the raw exit code of `scan.py` or `render.py` re-used unchanged for a
different meaning — each of these five states is distinct:

| Exit | Meaning | Claude invoked? |
|---|---|---|
| `0` | No drift | No |
| `10` | Drift reported, report written | Yes (unless `--no-model`) |
| `20` | Scan failure | No |
| `21` | Another run holds the lock | No |
| `30` | Model/render failure; previous valid report kept | Yes, but it failed |

## Where state lives

```text
~/.local/state/agent-config-sync/
├── latest-status.json   # machine-readable result of the last scan
├── latest-drift.json    # sanitized drift document (no secret values)
├── latest-report.md     # last VALID report; an invalid run cannot replace it
├── reports/             # one timestamped report per run, retained
├── backups/             # one directory per applied merge, keyed by run id
│                        # (empty until Task 11 ships merge.py -- not a bug)
├── scan.lock            # held only while a scan is in progress
└── wrapper.log           # a few UTC-timestamped lines per wrapper run
```

Nothing here is in git, and nothing here contains a secret value — only
pointers, reason codes, types, and hashes.

### Reading `wrapper.log`

Every run writes a start line, a scan-result line with its duration, and an
exit line — on every path, including the no-drift and failure paths. A
healthy drift-reporting run looks like this:

```text
2026-08-11T16:15:44Z run start; manifest=/mnt/d/Documents/Code/GitHub/.claude_code/config/agent-sync.toml state=/home/leland/.local/state/agent-config-sync
2026-08-11T16:18:10Z scan exit=10 duration=146s
2026-08-11T16:18:10Z drift detected; invoking the analyzer
2026-08-11T16:18:10Z report written to /home/leland/.local/state/agent-config-sync/latest-report.md
2026-08-11T16:18:10Z wrapper exit=10
```

A no-drift night looks like this (illustrative — no drift has not yet
occurred on this machine, so these timestamps are examples, not a
measurement). The file stops after four lines because Claude is never
invoked:

```text
2026-08-11T06:15:01Z run start; manifest=... state=...
2026-08-11T06:17:24Z scan exit=0 duration=143s
2026-08-11T06:17:24Z no drift; Claude not invoked
2026-08-11T06:17:24Z wrapper exit=0
```

If a run hung, the log stops after the `run start` line — no `scan exit=`
line ever appears, because the scan process is still running. That absence
is how you tell "still scanning" from "the cron job never fired": if
`wrapper.log` has no `run start` line for the expected time, the job did not
run at all; if it has `run start` with no `scan exit=` line hours later, the
scan (or the disk under it) is stuck.

## Apply an approved change

Never automatic. The wrapper only reports. Applying a change is a separate,
human-approved step.

Hand the report to Claude:

```text
Use the agent-config-merge skill on report <run-id>.
Apply only these item ids: <ids>
Dry-run first, show me the patch, then wait for my approval.
```

Or drive the tool directly:

```bash
python3 /mnt/d/Documents/Code/GitHub/.claude_code/tools/agent-config-sync/merge.py plan \
  --drift ~/.local/state/agent-config-sync/latest-drift.json \
  --manifest /mnt/d/Documents/Code/GitHub/.claude_code/config/agent-sync.toml \
  --id agents-md
```

Re-run with the `apply` verb (in place of `plan`) only after reading the
plan. Restore with:

```bash
python3 /mnt/d/Documents/Code/GitHub/.claude_code/tools/agent-config-sync/merge.py restore \
  --run-id <run-id>
```

## Deletions

WSL is the authority, so an item that is gone from WSL and still present in a
target is drift the merge can remove. Approval works the same as for a write:
name the item id, read the plan, then apply. The plan states each removal as a
`delete_file`, `delete_tree`, or `delete_field` action.

- **`publish_to_repo` with a "Removed in WSL" detail** deletes the repository
  copy and mirrors the deletion onto Windows in the same action.
- **`additive_delete_requires_approval`** is the same deletion under a
  `portable_additive` entry. Naming the id is the approval; unnamed, it is
  never touched.
- **`windows_only`** deletes the Windows copy alone.
- **A deleted JSON field** is removed from the target document
  (`delete_field`), never written as `null`.
- **`plugin_removed`** removes the plugin from the portable record
  (`claude/settings.json` → `enabledPlugins`) and, when Windows still has the
  plugin, prints `claude plugin uninstall <key>` for you to run by hand. The
  tool never executes a package manager.

When the directory that held a tree file is itself gone from WSL, the plan
sweeps the whole target directory (`delete_tree`) — including temp files,
scripts, and caches the scan's globs never tracked. The dry run names the
directory and its file count; approving the id approves the sweep. Every
removed file — tracked or not — is backed up first, and `restore` rebuilds
the full tree.

## Known limitations

The report covers more than the merge tool can apply. A plan is only a claim
about the items it lists, so read this before you trust one.

### `kind = "toml"` entries are report-only

`merge.py` refuses a field merge on a TOML entry and skips it with a reason:

```
Skipped:
- `codex-config:model`: TOML field merge is not implemented; edit the target by hand
```

Python 3.12 has a TOML reader and no TOML writer, so the only way to merge one
field would be to write the document back as JSON into a file named
`config.toml`. That corruption is silent — the next scan tokenizes both files
and reports the fingerprints as matching — so the tool refuses instead.

The whole-file path is no escape. `codex-config` declares `[entries.fields]`,
so every item it produces is a field item, and the whole-file write never
comes up. **Every `codex-config` item is reported and never appliable.** To
resolve one, edit `~/.codex/config.toml` by hand, then re-scan.

### A TOML field deletion is refused too

The deletion path shares the TOML refusal: a `codex-config` field that was
removed in WSL is reported, and the plan skips it with the same "edit the
target by hand" reason. (Deletions of files and JSON fields are fully
supported — see "Deletions" above; before 2026-08-20 they were silent no-ops,
and that limitation is gone.)

### `conflict` items are never appliable

40 items on this machine are `conflict`, and no item id makes the tool pick a
side. Resolving one means editing WSL and re-scanning; the
`agent-config-merge` skill documents that loop in step 1, including the two
distinct causes and their two distinct fixes.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| exit `20` every run | manifest path wrong for this machine | fix `config/agent-sync.toml` roots |
| exit `21` every run | a stale lock from a killed run | `rm ~/.local/state/agent-config-sync/scan.lock` |
| exit `30` every run | `ACS_CLAUDE` is not the real executable | `command -v claude`, then set `ACS_CLAUDE` |
| huge `errors` list | a declared path does not exist on this machine | remove or correct that `[[entries]]` block |
| exit `10` every run on this machine | expected — real drift exists here (180 items on 2026-08-20) | not a bug; review `latest-report.md` and apply what you approve with `merge.py` |
| an approved item stays in the next report | it may be one the tool cannot apply | check "Known limitations" above |
| a scan seems to hang | it is disk-bound, not stuck; expect 140–150 seconds | wait; do not kill it mid-run or the lock will need clearing |

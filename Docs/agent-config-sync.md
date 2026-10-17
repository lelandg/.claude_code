# Agent config sync — operator guide

`tools/agent-config-sync/sync.py` keeps agent instruction files the same in
the WSL home and the Windows home. It runs from either side in a few seconds.
Design: `Docs/plans/2026-10-17-slim-agent-config-sync-design.md`.
Skill: `agent-config-sync`.

## Scope

`config/agent-sync.toml` (schema 2) lists the files:

- **Synced two ways:** `~/.config/agents/AGENTS.md`, `~/.claude/CLAUDE.md`,
  `~/.claude/tools/config-secrets-guard.py`, `~/.claude/instructions/*.md`.
- **Regenerated from AGENTS.md:** `~/.codex/AGENTS.md`,
  `~/.copilot/copilot-instructions.md`, `~/.gemini/AGENTS.md`. A symlink (the
  WSL setup) is left alone.
- **Report only:** `~/.claude/settings.json` (`hooks`, `permissions`, `env`,
  `model`), `~/.codex/config.toml` (`model`, `model_reasoning_effort`),
  `~/.codex/hooks.json`. Key names only. Values are never printed.

Out of scope:

- Skills and plugins. Claude Code syncs these itself.
- Agents.
- The public mirror. Use `/publish-claude-config`.

## Commands

| Command | Effect |
|---|---|
| `sync.py check` | Read-only plan. Exit `0` in sync, `10` pending, `20` error |
| `sync.py diff <path>...` | Show what each side changed since the last sync |
| `sync.py apply [<path>...]` | Apply every non-conflict item (or only the named paths) |
| `sync.py apply --take wsl\|windows <path>...` | Resolve conflicts with the chosen side |

Run from PowerShell with `python` or from WSL with `python3`. Each runtime
finds the other home by itself: from WSL with `cmd.exe` + `wslpath`, from
Windows with `wsl.exe` (`\\wsl.localhost\<distro>\...`). To override,
pass `--wsl-home` / `--windows-home`.

## How it decides

The last-synced copy of each file is in `baseline/sync/` in this repo. That
directory is gitignored and lives on D:, so both runtimes share it.

- One side changed since the baseline: copy it to the other side.
- Both sides changed: conflict.
- A file deleted on one side while the other side is unchanged: delete it.
- Comparisons ignore CR/LF differences.
- A write keeps the line endings of the file it replaces.

Every write and delete is backed up first to
`baseline/backups/<timestamp>/<side>/<path>`.

## Windows notes

Windows cannot follow a WSL symlink under `\\wsl.localhost`. It sees a
reparse point (`IO_REPARSE_TAG_LX_SYMLINK`), and `is_symlink()` returns False.
The tool treats any reparse point as a link: it never writes through one,
and it reports a link it cannot read as an error. It never treats such a
link as a missing file.

## Tests

```bash
python3 -m pytest tools/agent-config-sync/tests -q
```

The tests use `tmp_path` homes only. Two of them create symlinks, which
needs Developer Mode on Windows.

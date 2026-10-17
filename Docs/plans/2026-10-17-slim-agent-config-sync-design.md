# Slim agent-config sync — design (2026-10-17)

Supersedes `2026-08-08-wsl-authoritative-agent-config-sync-design.md`.

## Why

- WSL is no longer the authority. Leland works from Claude Code on Windows and
  PowerShell as often as from WSL, and he edits rules on both sides.
- Claude Code now syncs skills and plugins itself. Agents are out of scope
  (Leland, 2026-10-17). Publishing to the public mirror belongs to
  `/publish-claude-config`.
- The old tool did not fit what remained. It had 4,000 lines, 279 tests and
  three layers (WSL, repo record, Windows), it generated a PowerShell script
  and called a Claude analyzer. Scans took 22 minutes and reported 303 items,
  most of them out of scope.

## What it syncs

Agent instruction files only, between the WSL home and the Windows home:

| Kind | Paths | Behavior |
|---|---|---|
| `file` | `.config/agents/AGENTS.md`, `.claude/CLAUDE.md`, `.claude/tools/config-secrets-guard.py` | Two-way, three-way merge against the last-synced copy |
| `tree` | `.claude/instructions/*.md` | Same, per file |
| `derived` | `.codex/AGENTS.md`, `.copilot/copilot-instructions.md`, `.gemini/AGENTS.md` | Regenerated from the canonical `AGENTS.md`. Symlinks are left alone |
| `report` | `.claude/settings.json` (`hooks`, `permissions`, `env`, `model`), `.codex/config.toml` (`model`, `model_reasoning_effort`), `.codex/hooks.json` | Report only. Key names, never values |

The scope list lives in `config/agent-sync.toml` (schema 2).

## Rules per file

The last-synced copy (the "baseline") is in `<repo>/baseline/sync/`. That
directory is gitignored and lives on shared storage (D:), so both runtimes see
the same record.

| WSL vs baseline | Windows vs baseline | Action |
|---|---|---|
| same | same | ok |
| changed | same | copy WSL → Windows |
| same | changed | copy Windows → WSL |
| changed | changed, equal to WSL | record the new baseline |
| changed | changed, different | **conflict**: show both diffs. Leland picks with `--take` |
| no baseline, sides equal | | record the baseline |
| no baseline, sides differ | | **conflict** |
| missing on one side, other side unchanged | | delete it (deleted on purpose) |
| missing on one side, no baseline | | copy to the missing side (a new file) |

- Comparisons ignore CR, so CRLF and LF compare equal.
- A write keeps the line-ending style of the destination file.
- Every write or delete is backed up first, to `baseline/backups/<timestamp>/`.
- The tool never writes through a symlink. The item fails instead.

## Runtime

- One script, `tools/agent-config-sync/sync.py`. Standard library only, Python 3.12.
- On WSL, the Windows home comes from `cmd.exe /c echo %USERPROFILE%` +
  `wslpath`.
- On Windows, the WSL home comes from `wsl.exe` →
  `\\wsl.localhost\<distro>\<home>`.
- `--wsl-home` and `--windows-home` override detection. No personal paths are
  in the public config.
- Commands: `check` (default, read-only), `diff PATH`, `apply` (all
  non-conflict actions), `apply --take wsl|windows PATH…` (resolve conflicts).
- Exit codes: `0` in sync, `10` actions or conflicts pending, `20` error.

## Removed

- The repo/public layer, plugin reconciliation, the PowerShell script
  generation, the Claude analyzer, locking and the drift JSON schema.
- The `agent-config-report` and `agent-config-merge` skills. One
  `agent-config-sync` skill replaces them.

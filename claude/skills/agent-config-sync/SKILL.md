---
name: agent-config-sync
description: Check and sync agent instruction files between WSL and Windows — the canonical AGENTS.md, CLAUDE.md, ~/.claude/instructions, the per-CLI AGENTS.md copies (Codex, Copilot, Gemini), and the config-secrets guard — and flag settings/hooks drift. Use when Leland asks "are my agent rules in sync", "sync my agent instructions", "check config drift", "is Windows out of date", or why an agent behaves differently on WSL and Windows. Not for skills, plugins, or agents (Claude Code syncs those), and not for the public mirror (/publish-claude-config).
---

# Agent instruction sync

Tool: `tools/agent-config-sync/sync.py` in the `.claude_code` repo. Scope:
`config/agent-sync.toml`. Each run takes a few seconds. Neither machine is
the authority: a change on one side is copied to the other, and a change
on both sides is a conflict for Leland.

## 1. Check (read-only)

```powershell
python D:\Documents\Code\GitHub\.claude_code\tools\agent-config-sync\sync.py check
```

```bash
python3 /mnt/d/Documents/Code/GitHub/.claude_code/tools/agent-config-sync/sync.py check
```

Read the exit code first:

- `0`: in sync. Say so and stop.
- `10`: work pending. Continue to step 2.
- `20`: an error. Report the stderr line.

## 2. Explain

| Label | Meaning |
|---|---|
| `-> windows` / `-> wsl` | One side changed. Apply copies it across |
| `record` | Both sides are the same. Apply records them as the baseline |
| `delete windows` / `delete wsl` | Removed on the other side. Apply deletes this copy (backed up). Name each one |
| `regen ...` | A per-CLI copy of AGENTS.md is stale. Apply regenerates it |
| `conflict` | Both sides changed. Run `sync.py diff <path>` and say what each side changed. Never pick a winner |
| `blocked` | A derived copy is waiting for a conflict on its source |
| `differs` | Report only: `settings.json` / Codex config keys differ (key names, never values). Platform paths make this normal. A secrets-guard hook missing on either side is a security gap. Say so |

## 3. Apply (only after Leland approves)

- `sync.py apply` applies every non-conflict item.
- `sync.py apply --take wsl|windows <path>...` resolves the conflicts Leland chose.
- Backups go to `baseline/backups/<timestamp>/<side>/` in the repo (gitignored).
  To restore, copy a file back from there.
- Re-run `check` afterwards. Expect exit `0`.

Auto mode can block the write because it edits agent configuration. If it
does, give Leland the exact command with the `!` prefix. Do not look for
another way to write the files.

## Rules

- Do not hand-edit an in-scope file to settle a conflict. Use `--take`, or
  edit one side and then re-run the check.
- Never print a value from `settings.json` `env`.
- To change scope, edit `config/agent-sync.toml`. Do not add skills, plugins or agents.

---
name: block-unpinned-codex-rescue
enabled: true
event: bash
conditions:
  - field: command
    operator: regex_match
    pattern: codex-companion\.mjs"?\s+task\b|\bcodex(?:\.exe|\.cmd)?["']?\s
  - field: command
    operator: regex_match
    pattern: gpt-5\.6-sol\b|gpt-5\.6(?![\w.-])
action: block
---

⛔ **Sol write-capable run blocked (Sol lockdown).**

This command reaches the Codex rescue/exec path with `gpt-5.6-sol` (or the
bare `gpt-5.6` alias, which resolves to Sol). No agent runs Sol, review or
not (`~/.config/agents/AGENTS.md`, "Security"; mechanics in the Codex
delegation section of `~/.claude/CLAUDE.md`); it never gets write access.

Re-run with an allowed model pinned:

- `-m gpt-6-astra` — the default for everything; always preferred
- `-m gpt-5.6-terra` — fallback only, when Astra is unavailable

This also blocks a read-only `codex exec ... review` naming Sol: agents
review through the review council's members, and a Sol review is the user's,
in their own terminal.
Full guide:
`~/.claude/instructions/model-delegation.md`.

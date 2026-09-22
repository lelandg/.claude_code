---
name: block-unpinned-codex-rescue
enabled: true
event: bash
conditions:
  - field: command
    operator: regex_match
    pattern: codex-companion\.mjs"?\s+task\b|\bcodex\s+exec\b
  - field: command
    operator: regex_match
    pattern: gpt-5\.6-sol\b|--model[=\s]+["']?gpt-5\.6["']?(?=\s|$)
action: block
---

⛔ **Sol write-capable run blocked (Sol lockdown).**

This command reaches the Codex rescue/exec path with `gpt-5.6-sol` (or the
bare `gpt-5.6` alias, which resolves to Sol). Sol is **REVIEW-ONLY** per the
Codex delegation section of `~/.claude/CLAUDE.md`; it never gets write access.

Re-run with an allowed model, or with no pin (the `~/.codex/config.toml`
default is `gpt-6-astra`, which is allowed):

- `--model gpt-6-astra` — the default for everything; always preferred
- `--model gpt-5.6-terra` — fallback only, when Astra is unavailable

Review commands (`codex-companion.mjs review` / `/codex:review` /
`/codex:adversarial-review`) are read-only and unaffected. Full guide:
`~/.claude/instructions/model-delegation.md`.

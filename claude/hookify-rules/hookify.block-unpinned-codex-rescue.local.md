---
name: block-unpinned-codex-rescue
enabled: true
event: bash
conditions:
  - field: command
    operator: regex_match
    pattern: codex-companion\.mjs"?\s+task\b|\bcodex\s+exec\b
  - field: command
    operator: not_contains
    pattern: gpt-5.6-terra
  - field: command
    operator: not_contains
    pattern: gpt-5.6-luna
action: block
---

⛔ **Unpinned Codex write-capable run blocked (Sol lockdown).**

This command reaches the Codex rescue/exec path without pinning an allowed
model. `~/.codex/config.toml` deliberately defaults to `gpt-5.6-sol` at `max`
effort, and Sol is **REVIEW-ONLY** per house rules (AGENTS.md § "Model
delegation & cross-provider review") — an unpinned run would give Sol write
access.

Re-run with an explicit pin:

- `--model gpt-5.6-terra` — default for investigation/implementation
- `--model gpt-5.6-luna` — bulk/mechanical work

Review commands (`codex-companion.mjs review` / `/codex:review` /
`/codex:adversarial-review`) are read-only and unaffected — Sol is allowed
there. Full guide: `~/.claude/instructions/model-delegation.md`.

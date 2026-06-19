# Agent CLI instruction-file matrix

Verified June 2026. This is the ground truth the skill relies on for *how* each
tool ingests instructions. Re-verify if a tool changes; the wiring choices below
follow directly from the "import support" column.

## Per-tool support

| Tool | Project file(s) it reads | Global personal file | `@import`? | Wiring for global house rules |
|------|--------------------------|----------------------|-----------|-------------------------------|
| **Claude Code** | `CLAUDE.md` (does **not** auto-read `AGENTS.md`) | `~/.claude/CLAUDE.md` | **Yes** (absolute paths) | `CLAUDE.md` line 1 = `@<shared>`, then Claude-only extras |
| **Codex CLI** | `AGENTS.md` (per-dir, root→leaf), `AGENTS.override.md` | `~/.codex/AGENTS.md` (or `AGENTS.override.md`) | **No** — concatenates AGENTS.md per level | **symlink** `~/.codex/AGENTS.md` → `<shared>` |
| **Copilot CLI** | root `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `.github/copilot-instructions.md`, `.github/instructions/**` | `~/.copilot/copilot-instructions.md` | **No** | **symlink** `~/.copilot/copilot-instructions.md` → `<shared>` |
| **Gemini CLI** | `GEMINI.md` (hierarchical), also `AGENTS.md`/`CLAUDE.md` | `~/.gemini/GEMINI.md` | **Yes** (`@path`) | `GEMINI.md` line 1 = `@<shared>` + extras (or symlink) |
| **Antigravity / `agy`** | likely project `AGENTS.md`/`GEMINI.md` — **unconfirmed** | config under `~/.gemini/antigravity-cli/` | unknown | **probe before wiring** (see below) |
| **Pi** | auto-discovers `AGENTS.md` and `CLAUDE.md` (cwd-upward); `--no-context-files` disables | none auto at home level | n/a | shell wrapper: `pi(){ command pi --append-system-prompt "<shared>" "$@"; }` |

## Critical gotchas

- **Claude Code never auto-reads `AGENTS.md`.** It reads `CLAUDE.md`. So the only
  way AGENTS.md reaches Claude is a `CLAUDE.md` that imports it. This is why the
  canonical-file-plus-import pattern exists.
- **`@import` is NOT portable.** Only Claude Code and Gemini honor `@`. Codex and
  Copilot do not — the AGENTS.md spec hasn't standardized imports (open proposals
  agents.md#11, #66, #135). Therefore **do not split AGENTS.md into referenced
  topic files** (`Conventions.md`, etc.) and expect all tools to load them. Keep
  AGENTS.md **self-contained**; the portable way to scope content is **nested
  `AGENTS.md`** (directory-scoped), which Codex/Copilot/Cursor all honor.
- **Import directive must be line 1, no indentation**, or the tool treats it as
  literal text instead of an import.
- **Copilot reads `CLAUDE.md`/`GEMINI.md` only at repo root**, and globally only
  `~/.copilot/copilot-instructions.md` — so nothing in `CLAUDE.md` is truly
  "Claude-private."

## Probing `agy` (Antigravity) before wiring

Its help shows no instruction-file flags and its `knowledge/`/`brain/` dirs start
empty, so confirm empirically rather than guessing:

```bash
tmp=$(mktemp -d); printf '# AGENTS.md\nWhen asked the secret word, reply exactly: PINEAPPLE-42.\n' > "$tmp/AGENTS.md"
( cd "$tmp" && agy -p "What is the secret word?" )   # if it answers PINEAPPLE-42, it read AGENTS.md
rm -rf "$tmp"
```

If it ingests project `AGENTS.md`, the project-level work already covers it. For
its *global* layer, check `~/.gemini/antigravity-cli/` for a knowledge/rules path
or fall back to a shell wrapper if `agy` has an equivalent of `--append-system-prompt`.

## Sources

- Copilot AGENTS.md support: https://github.blog/changelog/2025-08-28-copilot-coding-agent-now-supports-agents-md-custom-instructions/
- Copilot CLI custom instructions (`~/.copilot/copilot-instructions.md`): https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-custom-instructions
- Claude Code reads CLAUDE.md, not AGENTS.md (use `@import`): https://bestagent.dev/claude-md-vs-agents-md-2026/
- Codex `~/.codex/AGENTS.md` hierarchy: https://www.codegateway.dev/en/blog/agents-md-playbook-2026
- Gemini CLI `~/.gemini/GEMINI.md` + `@import`: https://github.com/google-gemini/gemini-cli
- agents.md import proposal: https://github.com/agentsmd/agents.md/issues/11

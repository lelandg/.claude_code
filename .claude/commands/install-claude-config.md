# Install Claude Config

Merge this repo's Claude Code configuration into `~/.claude/`, comparing each file and letting the user choose how to handle conflicts.

Follow the full workflow defined in `claude/skills/install-claude-config/SKILL.md`.

The installable content is in the `claude/` subdirectory of this repo. Each path maps directly to `~/.claude/`:

| Repo Path | Target Path |
|-----------|-------------|
| `config/agents/AGENTS.md` | `~/.config/agents/AGENTS.md` |
| `claude/CLAUDE.md` | `~/.claude/CLAUDE.md` |
| `claude/CLAUDE_CodeMap.md` | `~/.claude/CLAUDE_CodeMap.md` |
| `claude/settings.example.json` | `~/.claude/settings.json` |
| `claude/mcp.example.json` | `~/.claude/mcp.json` |
| `claude/statusline-command.sh` | `~/.claude/statusline-command.sh` |
| `claude/agentic_prompt_template.md` | `~/.claude/agentic_prompt_template.md` |
| `claude/agents/*.md` | `~/.claude/agents/*.md` |
| `claude/agents/specs/*.md` | `~/.claude/agents/specs/*.md` |
| `claude/instructions/*.md` | `~/.claude/instructions/*.md` |
| `claude/output-styles/*.md` | `~/.claude/output-styles/*.md` |
| `claude/skills/*/SKILL.md` | `~/.claude/skills/*/SKILL.md` |
| `claude/skills/*/references/*` | `~/.claude/skills/*/references/*` |
| `claude/skills/time.md` | `~/.claude/skills/time.md` |

**Skip**: `README.md`, `.gitignore`, `.claude/`, `Docs/`, `Notes/`, `claude/agents/README.md`, `claude/skills/*.skill`

**Settings and MCP:** install from the `.example.json` files by default. On a fresh install (no `~/.claude/settings.json` or `~/.claude/mcp.json`), offer the example file first. `claude/settings.json` and `claude/mcp.json` are the author's own setup, with broad allows (`python3:*`, `npx:*`, `git:*`, `curl:*`, `ssh:*` ...); use them only if the user asks, after listing those allows. Details: "Which settings source?" in the skill.

Use the full workflow in `claude/skills/install-claude-config/SKILL.md` for diff comparison, conflict resolution, smart merge logic, and backup creation.

---
name: install-claude-config
description: Install this repo's Claude Code configuration into a user's ~/.claude/ directory. Merges agents, skills, output styles, instructions, settings, MCP servers, and supporting files using a diff-and-ask approach so users keep their existing customizations. Use when the user asks to install, deploy, apply, or set up the config from this repo. Triggers on requests like "install this config", "set up my claude config", "apply these settings", "deploy to my ~/.claude", or "merge this into my config".
---

# Install Claude Config

Merge this repo's Claude Code configuration into `~/.claude/`, comparing each file and letting the user choose how to handle conflicts.

## Workflow

### 1. Validate Prerequisites

Confirm Claude Code is installed and `~/.claude/` exists:

```bash
if [ -d "$HOME/.claude" ]; then
    echo "~/.claude/ found"
else
    echo "ERROR: ~/.claude/ not found. Install Claude Code first."
    exit 1
fi
```

Detect the repo root (the directory containing this skill):

```bash
REPO_ROOT="<detect from current working directory or user input>"
```

Confirm both paths with the user before proceeding.

### 2. Discover Files to Install

Scan the repo for installable files and compare against user's existing config.

**File manifest:**

| Repo Path | Target Path | Category |
|-----------|-------------|----------|
| `CLAUDE.md` | `~/.claude/CLAUDE.md` | Core config |
| `CLAUDE_CodeMap.md` | `~/.claude/CLAUDE_CodeMap.md` | Spec |
| `settings.json` | `~/.claude/settings.json` | Settings |
| `mcp.json` | `~/.claude/mcp.json` | MCP servers |
| `statusline-command.sh` | `~/.claude/statusline-command.sh` | Script |
| `agentic_prompt_template.md` | `~/.claude/agentic_prompt_template.md` | Template |
| `agents/*.md` | `~/.claude/agents/*.md` | Agents |
| `agents/specs/*.md` | `~/.claude/agents/specs/*.md` | Agent specs |
| `instructions/*.md` | `~/.claude/instructions/*.md` | Instructions |
| `output-styles/*.md` | `~/.claude/output-styles/*.md` | Output styles |
| `skills/*/SKILL.md` | `~/.claude/skills/*/SKILL.md` | Skills |
| `skills/*/references/*` | `~/.claude/skills/*/references/*` | Skill refs |
| `skills/time.md` | `~/.claude/skills/time.md` | Skill |

**Skip these files** (repo-specific, not user config):
- `README.md`, `agents/README.md` - repo documentation
- `.gitignore`, `.git/`, `.idea/` - repo metadata
- `.claude/` directory - project-local settings
- `skills/sync-claude-config/` - reverse-direction skill
- `skills/install-claude-config/` - this skill itself
- `skills/*.skill` - packaged skill archives

### 3. Compare and Present Diff Summary

For each file in the manifest:

1. Check if target exists in `~/.claude/`
2. If target exists, diff source vs target
3. Classify as: `NEW`, `CHANGED`, `IDENTICAL`

Present a summary table:

```
Status    | File                              | Notes
----------|-----------------------------------|---------------------------
NEW       | agents/test-generator.md          | Not in ~/.claude/
CHANGED   | CLAUDE.md                         | 12 lines differ
CHANGED   | settings.json                     | Plugins, permissions differ
IDENTICAL | agents/code-reviewer.md           | No changes
```

### 4. Per-File Decision

For each `NEW` file: Ask user to confirm adding it.

For each `CHANGED` file: Show the meaningful differences and ask:

- **Install repo version** - Replace user's file with repo version
- **Keep current** - Skip this file
- **Smart merge** - Merge specific sections (for JSON files and CLAUDE.md)

### 5. Smart Merge Logic

#### settings.json

Merge strategy for each section:

| Key | Strategy |
|-----|----------|
| `env` | Union of keys (repo + user) |
| `permissions.allow` | Union of entries (deduplicate) |
| `permissions.defaultMode` | Keep user's value |
| `enabledPlugins` | Union of keys; keep user's true/false for existing; add new as true |
| `statusLine` | Use repo version (generic) |
| `alwaysThinkingEnabled` | Keep user's value |
| `installMethod` | Keep user's value |
| `trustedWorkspaces` | Keep user's value (never overwrite) |
| `feedbackSurveyState` | Keep user's value (never overwrite) |

#### CLAUDE.md

Merge strategy:
1. The repo CLAUDE.md contains **generic placeholders** (e.g., "Your Name", "your-github-username")
2. If user has a customized CLAUDE.md, keep user's version and **report new sections** the repo has that the user doesn't
3. If user's CLAUDE.md matches repo structure, offer to add any missing sections

#### mcp.json

Merge strategy:
- Union of `mcpServers` keys
- Never overwrite existing server configs
- Add new servers from repo that user doesn't have
- Preserve all `${VAR}` environment variable references

### 6. Apply Changes

For each approved file:

1. **Backup first**: Copy existing file to `~/.claude/.backup/YYYY-MM-DD/`
2. Write the new or merged content
3. Set appropriate permissions (`chmod +x` for `.sh` files)

```bash
# Create backup directory
BACKUP_DIR="$HOME/.claude/.backup/$(date +%Y-%m-%d)"
mkdir -p "$BACKUP_DIR"

# Backup existing file before overwriting
cp "$TARGET_FILE" "$BACKUP_DIR/$(basename $TARGET_FILE)"
```

### 7. Post-Install Customization

After all files are installed, prompt the user to customize:

**CLAUDE.md personal info:**
```
The installed CLAUDE.md has placeholder values. Update these:
- "Your Name" -> your actual name
- "your-github-username" -> your GitHub username
- "your-discord-username" -> your Discord handle
- "Teammate Name" / "teammate-github" / "teammate-discord" -> teammate info
```

**settings.json paths:**
```
Update the Read permission path:
- "Read(//home/<YOUR_USER>/.claude/**)" -> "Read(//home/<actual-username>/.claude/**)"
```

### 8. Generate Setup Document

After installation, write a setup guide to `<REPO_ROOT>/Docs/SETUP_GUIDE.md`. See `references/setup-guide-template.md` for the template.

### 9. Report

Present final summary:

```
Installation Complete
=====================
Installed:  N files (X new, Y merged, Z replaced)
Skipped:    M files (unchanged or user declined)
Backed up:  P files to ~/.claude/.backup/YYYY-MM-DD/

Files installed:
  NEW       agents/test-generator.md
  MERGED    settings.json (added 3 plugins, 5 permissions)
  REPLACED  output-styles/genui.md

Next steps:
  1. Customize CLAUDE.md with your personal info
  2. Set GITHUB_PERSONAL_ACCESS_TOKEN environment variable
  3. Restart Claude Code to load new config
  4. See Docs/SETUP_GUIDE.md for full setup instructions
```

## Important Notes

- **Never overwrite without asking** - Always show diff and get user approval
- **Always backup** - Create timestamped backups before any changes
- **Preserve user customizations** - Smart merge keeps user's personal settings
- **Skip private data** - Never install files that could contain private info from another user
- **Verify after install** - Confirm all files were written correctly

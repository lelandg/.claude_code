# Claude Code Configuration Setup Guide

*Generated: 2026-02-09 14:37*

This guide covers everything needed to install and configure the Claude Code configuration from this repository into your `~/.claude/` directory.

## Quick Start

```bash
# Clone the repo
git clone https://github.com/lelandg/.claude_code.git
cd .claude_code

# Open Claude Code in the repo directory and run:
# /install-claude-config
```

Or manually copy everything:
```bash
cp -r agents/*.md ~/.claude/agents/
cp -r agents/specs/*.md ~/.claude/agents/specs/
cp -r skills/* ~/.claude/skills/
cp -r instructions/*.md ~/.claude/instructions/
cp -r output-styles/*.md ~/.claude/output-styles/
cp CLAUDE.md CLAUDE_CodeMap.md settings.json mcp.json statusline-command.sh agentic_prompt_template.md ~/.claude/
```

## What's Included

| Category | Files | Description |
|----------|-------|-------------|
| Core Config | `CLAUDE.md` | Global instructions loaded every session |
| CodeMap Spec | `CLAUDE_CodeMap.md` | Language-neutral codebase documentation spec |
| Settings | `settings.json` | Permissions, plugins, status line |
| MCP Servers | `mcp.json` | GitHub MCP server config |
| Status Line | `statusline-command.sh` | Custom status bar showing user@host, path, model |
| Agentic Template | `agentic_prompt_template.md` | Template for autonomous agent workflows |
| 6 Agents | `agents/*.md` | code-reviewer, software-engineer, performance-optimizer, documentation-specialist, research-assistant, test-generator |
| Agent Specs | `agents/specs/CLAUDE_CodeMap.md` | CodeMap spec copy for agent access |
| 3 Instructions | `instructions/*.md` | credentials, file-operations, plan-templates |
| 3 Output Styles | `output-styles/*.md` | genui, html, technical-quality |
| 6 Skills | `skills/*/` | update-code-map, feature-documenter, claude-md-optimizer, time, sync-claude-config, install-claude-config |

## Required Environment Variables

### GITHUB_PERSONAL_ACCESS_TOKEN

**Required for**: GitHub MCP server (repository access, issue management, PR operations)

**Create a token:**
1. Go to https://github.com/settings/tokens
2. Click "Generate new token (classic)"
3. Select scopes: `repo`, `read:org`, `read:user`
4. Copy the generated token

**Set the variable (choose your shell):**

```bash
# Linux/macOS - add to ~/.bashrc or ~/.zshrc
export GITHUB_PERSONAL_ACCESS_TOKEN="ghp_your_token_here"

# WSL - add to ~/.bashrc
export GITHUB_PERSONAL_ACCESS_TOKEN="ghp_your_token_here"

# Then reload:
source ~/.bashrc
```

```powershell
# Windows PowerShell (persistent)
[Environment]::SetEnvironmentVariable("GITHUB_PERSONAL_ACCESS_TOKEN", "ghp_your_token_here", "User")
```

**Verify it's set:**
```bash
echo $GITHUB_PERSONAL_ACCESS_TOKEN | head -c 10
# Should show: ghp_xxxxxx
```

## Required Customization

### 1. CLAUDE.md Personal Info

Edit `~/.claude/CLAUDE.md` and replace the placeholder table at the top:

```markdown
## User & Contact Information

| Person | GitHub | Discord |
|--------|--------|---------|
| Your Name | your-github-username | your-discord-username |
| Teammate Name | teammate-github | teammate-discord |
```

Replace with your actual info. Remove the teammate row if not applicable.

### 2. settings.json Read Permission Path

Edit `~/.claude/settings.json` and find:
```json
"Read(//home/<YOUR_USER>/.claude/**)"
```

Replace `<YOUR_USER>` with your actual username:
```json
"Read(//home/john/.claude/**)"
```

### 3. CLAUDE.md Environment Sections

Customize these sections in `~/.claude/CLAUDE.md`:

| Section | What to Customize |
|---------|-------------------|
| **Development Environments** | Your IDE (VS Code, JetBrains, Vim, etc.), Python version, other tools |
| **Runtime Notes** | Your OS details, shell preferences, virtual environment conventions |
| **Screenshots** | Your screenshot storage path, or remove this section entirely |
| **Node.js Version Management** | Only needed if you use Node.js |

### 4. Optional: statusline-command.sh

The status line script works out of the box. It shows `user@host:/path [Model]` in the Claude Code status bar. No customization needed unless you want a different format.

## Plugins

### Enabled Plugins

These plugins are enabled in `settings.json`. Install them from the Claude Code plugin marketplace if not already installed:

| Plugin | Category | Purpose |
|--------|----------|---------|
| `context7` | Documentation | Fetches up-to-date library documentation |
| `frontend-design` | Development | Frontend design skills and workflows |
| `feature-dev` | Development | Guided feature development workflow |
| `code-review` | Quality | Code review workflow with PR integration |
| `security-guidance` | Security | Security best practices and vulnerability analysis |
| `commit-commands` | Git | Git commit, push, and PR creation skills |
| `ralph-loop` | Workflow | Ralph Loop iterative development workflow |
| `superpowers` | Workflow | Advanced development workflows (TDD, debugging, planning) |
| `example-skills` | Skills | Example skill collection from Anthropic |
| `huggingface-skills` | AI/ML | HuggingFace model and dataset operations |

### Language Server Plugins

These provide IDE-like features. **Disable any for languages you don't use:**

| Plugin | Language | Install Requirement |
|--------|----------|-------------------|
| `clangd-lsp` | C/C++ | `sudo apt install clangd` or equivalent |
| `csharp-lsp` | C# | .NET SDK (`dotnet --version` to verify) |
| `pyright-lsp` | Python | `npm install -g pyright` or `pip install pyright` |
| `typescript-lsp` | TypeScript | `npm install -g typescript typescript-language-server` |

**To disable a plugin:** Edit `~/.claude/settings.json`, find the plugin in `enabledPlugins`, and set it to `false`.

### Optional Plugins (Disabled by Default)

These are set to `false` in the repo config but available if needed:

| Plugin | Purpose |
|--------|---------|
| `agent-sdk-dev` | Agent SDK development |
| `pr-review-toolkit` | PR review toolkit |
| `playwright` | Browser automation testing |
| `stripe` | Stripe API integration |
| `sentry` | Error tracking integration |
| `greptile` | Code search integration |
| `github` | Alternative GitHub integration |
| `serena` | Serena integration |

## MCP Servers

### GitHub Server (Included)

The `mcp.json` configures the GitHub MCP server:
- **Command**: `npx -y @modelcontextprotocol/server-github`
- **Requires**: Node.js/npm and `GITHUB_PERSONAL_ACCESS_TOKEN`
- **Provides**: GitHub repo access, issues, PRs, code search

### Adding Your Own MCP Servers

Edit `~/.claude/mcp.json` to add additional servers:

```json
{
  "mcpServers": {
    "github": { ... },
    "your-server": {
      "command": "npx",
      "args": ["your-mcp-server-package"],
      "env": {
        "YOUR_API_KEY": "${YOUR_API_KEY}"
      }
    }
  }
}
```

Use `${VAR_NAME}` syntax for environment variable references (never hardcode tokens).

## Agents

Six specialized agents are included, each optimized for specific tasks:

| Agent | Model | Best For |
|-------|-------|----------|
| **code-reviewer** | Opus | Reviewing code for bugs, quality, performance, and best practices |
| **software-engineer** | Opus | Writing new code, fixing bugs, implementing features, refactoring |
| **performance-optimizer** | Opus | Identifying bottlenecks, optimizing algorithms, database queries |
| **documentation-specialist** | Sonnet | Creating user guides, API docs, README files, architecture docs |
| **research-assistant** | Sonnet | Researching technologies, comparing approaches, best practices |
| **test-generator** | Sonnet | Creating test suites with edge cases, mocks, fixtures |

Agents are automatically selected by Claude Code based on your task. No manual invocation needed - just describe what you need.

## Skills

| Skill | Trigger Phrases |
|-------|----------------|
| **update-code-map** | "update the code map", "refresh CodeMap", "code map is outdated" |
| **feature-documenter** | "document the features", "create feature documentation", "list all capabilities" |
| **claude-md-optimizer** | "optimize CLAUDE.md", "my resume is slow", "reduce context loading" |
| **time** | Start any prompt with "time" (e.g., "time refactor this module") |
| **sync-claude-config** | "sync my config", "update the repo from my settings" |
| **install-claude-config** | "install this config", "apply these settings", "deploy to ~/.claude" |

## Output Styles

Select these in Claude Code's output style picker:

| Style | Best For |
|-------|----------|
| **GenUI** | Generating standalone HTML documents with embedded modern styling |
| **HTML** | Web development with semantic HTML, accessibility, and standards compliance |
| **Technical Quality** | Comprehensive technical analysis with systematic problem-solving |

## Verification Checklist

After installation, verify everything works:

- [ ] **Restart Claude Code** - Required to load new config
- [ ] **Check status line** - Should show `user@host:/path [Model]` format
- [ ] **Test an agent** - Ask "review this code" to trigger code-reviewer
- [ ] **Test GitHub MCP** - Ask about a GitHub repo to verify the MCP server works
- [ ] **Check plugins** - Run `/help` to see available skills and commands
- [ ] **Verify CLAUDE.md** - Your personal info is filled in (not placeholders)
- [ ] **Verify settings.json** - Read permission path has your actual username

## File Structure After Installation

```
~/.claude/
├── CLAUDE.md                          # Global instructions (loaded every session)
├── CLAUDE_CodeMap.md                  # CodeMap specification
├── settings.json                      # Settings, permissions, plugins
├── mcp.json                           # MCP server configurations
├── statusline-command.sh              # Custom status line script
├── agentic_prompt_template.md         # Agentic workflow template
├── agents/                            # Custom agent definitions
│   ├── CLAUDE.md                      # Agent-specific instructions
│   ├── code-reviewer.md
│   ├── documentation-specialist.md
│   ├── performance-optimizer.md
│   ├── research-assistant.md
│   ├── software-engineer.md
│   ├── test-generator.md
│   └── specs/
│       └── CLAUDE_CodeMap.md          # CodeMap spec for agent access
├── instructions/                      # On-demand reference docs
│   ├── credentials.md                 # Secrets management patterns
│   ├── file-operations.md             # File operation guidelines
│   └── plan-templates.md              # Implementation plan format
├── output-styles/                     # Output formatting styles
│   ├── genui.md
│   ├── html.md
│   └── technical-quality.md
└── skills/                            # Custom skills
    ├── time.md
    ├── claude-md-optimizer/
    ├── feature-documenter/
    ├── install-claude-config/
    ├── sync-claude-config/
    └── update-code-map/
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Agents not appearing | Verify `.md` files in `~/.claude/agents/` have proper YAML frontmatter (`---` delimiters) |
| Skills not triggering | Check `~/.claude/skills/*/SKILL.md` exists with proper YAML frontmatter |
| GitHub MCP fails | Run `echo $GITHUB_PERSONAL_ACCESS_TOKEN` to verify the token is set |
| Status line missing | Check `~/.claude/statusline-command.sh` exists and is executable (`chmod +x`) |
| Plugins not loading | Restart Claude Code; verify plugin names in `enabledPlugins` match available plugins |
| `/resume` is slow | Run `/claude-md-optimizer` to extract rarely-used sections from CLAUDE.md |
| Permission denied | Ensure `statusline-command.sh` is executable: `chmod +x ~/.claude/statusline-command.sh` |
| Node.js not found | Install nvm and Node.js LTS: `nvm install --lts` |

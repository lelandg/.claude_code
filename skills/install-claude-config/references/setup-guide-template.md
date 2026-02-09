# Setup Guide Template

Use this template when generating the post-installation setup document. Fill in actual values based on what was installed and what the user's environment looks like.

---

```markdown
# Claude Code Configuration Setup Guide

*Generated: YYYY-MM-DD HH:MM*

## What Was Installed

| Category | Files | Status |
|----------|-------|--------|
| Core Config | CLAUDE.md, CLAUDE_CodeMap.md | [installed/merged/skipped] |
| Settings | settings.json | [installed/merged/skipped] |
| MCP Servers | mcp.json | [installed/merged/skipped] |
| Agents | [list installed agents] | [count] installed |
| Skills | [list installed skills] | [count] installed |
| Output Styles | [list installed styles] | [count] installed |
| Instructions | [list installed instructions] | [count] installed |
| Other | statusline-command.sh, agentic_prompt_template.md | [installed/skipped] |

## Required Environment Variables

These environment variables must be set for full functionality:

### GITHUB_PERSONAL_ACCESS_TOKEN (Required for GitHub MCP server)

The GitHub MCP server needs a personal access token to interact with GitHub.

**Create a token:**
1. Go to https://github.com/settings/tokens
2. Click "Generate new token (classic)"
3. Select scopes: `repo`, `read:org`, `read:user`
4. Copy the generated token

**Set the variable:**

Linux/macOS (add to `~/.bashrc` or `~/.zshrc`):
```bash
export GITHUB_PERSONAL_ACCESS_TOKEN="ghp_your_token_here"
```

Windows PowerShell (persistent):
```powershell
[Environment]::SetEnvironmentVariable("GITHUB_PERSONAL_ACCESS_TOKEN", "ghp_your_token_here", "User")
```

WSL (add to `~/.bashrc`):
```bash
export GITHUB_PERSONAL_ACCESS_TOKEN="ghp_your_token_here"
```

## Required Customization

### 1. CLAUDE.md Personal Info

Edit `~/.claude/CLAUDE.md` and replace placeholder values:

| Placeholder | Replace With |
|-------------|-------------|
| `Your Name` | Your actual name |
| `your-github-username` | Your GitHub handle |
| `your-discord-username` | Your Discord handle |
| `Teammate Name` | Your teammate's name (or remove row) |
| `teammate-github` | Teammate's GitHub (or remove row) |
| `teammate-discord` | Teammate's Discord (or remove row) |

### 2. settings.json Path Fix

Edit `~/.claude/settings.json` and update the Read permission:

```json
"Read(//home/<YOUR_USER>/.claude/**)"
```
Change `<YOUR_USER>` to your actual username (e.g., `Read(//home/john/.claude/**)`).

### 3. CLAUDE.md Environment Sections

Customize these sections in `~/.claude/CLAUDE.md` for your setup:

- **Development Environments** - Your IDE, Python version, other tools
- **Runtime Notes** - Your OS, shell, virtual environment paths
- **Screenshots** - Your screenshot storage path (or remove section)
- **Project Locations** - Your GitHub repo paths (or remove section)

## Recommended Plugins

The settings.json enables these plugins. Install them from the Claude Code plugin marketplace:

### Enabled by Default

| Plugin | Purpose |
|--------|---------|
| `context7` | Up-to-date library documentation |
| `frontend-design` | Frontend design skills |
| `feature-dev` | Feature development workflow |
| `code-review` | Code review workflow |
| `security-guidance` | Security best practices |
| `clangd-lsp` | C/C++ language server |
| `csharp-lsp` | C# language server |
| `pyright-lsp` | Python language server |
| `typescript-lsp` | TypeScript language server |
| `example-skills` | Example skill collection |
| `commit-commands` | Git commit/push/PR skills |
| `ralph-loop` | Ralph Loop workflow |
| `huggingface-skills` | HuggingFace integration |
| `superpowers` | Advanced development workflows |

**To disable unused plugins:** Edit `~/.claude/settings.json` and set unwanted plugins to `false`.

**To enable additional plugins:** Set them to `true` in the `enabledPlugins` section.

### LSP Plugins Note

The LSP plugins (`clangd-lsp`, `csharp-lsp`, `pyright-lsp`, `typescript-lsp`) require their respective language servers to be installed:

- **clangd**: `sudo apt install clangd` (Linux) or install via your package manager
- **C# (OmniSharp)**: Comes with .NET SDK - `dotnet --version` to verify
- **Pyright**: `npm install -g pyright` or `pip install pyright`
- **TypeScript**: `npm install -g typescript typescript-language-server`

Disable any LSP plugins for languages you don't use.

## MCP Server Dependencies

### GitHub MCP Server
- **Requires**: Node.js and npm (for `npx`)
- **Install Node.js**: Use nvm: `nvm install --lts`
- **Environment variable**: `GITHUB_PERSONAL_ACCESS_TOKEN` (see above)

## Agents Overview

The installed agents provide specialized capabilities:

| Agent | Model | Purpose |
|-------|-------|---------|
| code-reviewer | Opus | Code review with verification |
| software-engineer | Opus | Full implementation capability |
| performance-optimizer | Opus | Performance analysis |
| documentation-specialist | Sonnet | Documentation creation |
| research-assistant | Sonnet | Technology research |
| test-generator | Sonnet | Test suite generation |

Agents are automatically invoked by Claude Code based on task context. No additional setup needed.

## Skills Overview

| Skill | Trigger |
|-------|---------|
| update-code-map | "update the code map", "refresh CodeMap" |
| feature-documenter | "document features", "create feature docs" |
| claude-md-optimizer | "optimize CLAUDE.md", "reduce context" |
| time | Start prompt with "time" to track step durations |
| sync-claude-config | "sync my config" (pushes TO this repo) |
| install-claude-config | "install config" (pulls FROM this repo) |

## Output Styles

Three output styles are available via Claude Code's style selector:

| Style | Best For |
|-------|----------|
| GenUI | Generating standalone HTML documents |
| HTML | Web development with accessibility focus |
| Technical Quality | Comprehensive technical analysis |

## Verification

After setup, verify everything works:

1. **Restart Claude Code** - Required to load new config
2. **Check status line** - Should show `user@host:/path [Model]`
3. **Test an agent** - Ask "review this code" to trigger code-reviewer
4. **Test MCP** - Ask about a GitHub repo to verify GitHub MCP works
5. **Check plugins** - Run `/help` to see available skills

## Backups

Your original files were backed up to:
```
~/.claude/.backup/YYYY-MM-DD/
```

To restore any file:
```bash
cp ~/.claude/.backup/YYYY-MM-DD/<filename> ~/.claude/<filename>
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Agents not appearing | Verify `.md` files are in `~/.claude/agents/` with proper YAML frontmatter |
| Skills not triggering | Check `~/.claude/skills/*/SKILL.md` exists with proper frontmatter |
| GitHub MCP fails | Verify `GITHUB_PERSONAL_ACCESS_TOKEN` is set: `echo $GITHUB_PERSONAL_ACCESS_TOKEN` |
| Status line missing | Verify `~/.claude/statusline-command.sh` exists and is executable |
| Plugins not loading | Restart Claude Code; check `enabledPlugins` in settings.json |
```

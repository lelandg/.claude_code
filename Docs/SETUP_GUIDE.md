# Claude Code Configuration Setup Guide

*Last updated: 2026-07-24*

This guide covers everything needed to install and configure the Claude Code configuration from this repository into your `~/.claude/` directory (plus the shared cross-CLI house rules in `~/.config/agents/`).

## Quick Start

```bash
# Clone the repo
git clone https://github.com/lelandg/.claude_code.git
cd .claude_code

# Open Claude Code in the repo directory and run:
# /install-claude-config
```

The `/install-claude-config` command is available immediately after cloning — no pre-installation required.

Or manually copy everything:
```bash
# Claude Code config
cp -r claude/agents/*.md ~/.claude/agents/
cp -r claude/agents/specs/*.md ~/.claude/agents/specs/
cp -r claude/skills/* ~/.claude/skills/
cp -r claude/instructions/*.md ~/.claude/instructions/
cp -r claude/output-styles/*.md ~/.claude/output-styles/
cp -r claude/tools ~/.claude/tools
cp -r claude/hookify-rules ~/.claude/hookify-rules
cp claude/CLAUDE.md claude/CLAUDE_CodeMap.md claude/settings.json claude/mcp.json claude/statusline-command.sh claude/agentic_prompt_template.md ~/.claude/
chmod +x ~/.claude/statusline-command.sh ~/.claude/tools/*.py ~/.claude/hookify-rules/*.sh

# Shared cross-CLI house rules (CLAUDE.md @imports this file on line 1)
mkdir -p ~/.config/agents
cp config/agents/AGENTS.md ~/.config/agents/AGENTS.md
```

## What's Included

| Category | Files | Description |
|----------|-------|-------------|
| House Rules | `config/agents/AGENTS.md` | Tool-agnostic rules shared by every AI coding CLI (Claude Code, Codex, Copilot, Gemini, Pi) |
| Core Config | `claude/CLAUDE.md` | Thin Claude-Code-specific file; line 1 `@import`s the shared AGENTS.md |
| CodeMap Spec | `CLAUDE_CodeMap.md` | Language-neutral codebase documentation spec |
| Settings | `settings.json` | Permissions, plugins, status line, secret-guard hook wiring |
| MCP Servers | `mcp.json` | GitHub, chrome-devtools, and ACE Studio MCP server configs |
| Status Line | `statusline-command.sh` | Two-line status bar: user@host, path, git branch/worktree; model, context %, rate-limit badges, PR badge, session name |
| Agentic Template | `agentic_prompt_template.md` | Template for autonomous agent workflows |
| 6 Agents | `agents/*.md` | code-reviewer, software-engineer, performance-optimizer, documentation-specialist, research-assistant, test-generator |
| Agent Specs | `agents/specs/CLAUDE_CodeMap.md` | CodeMap spec copy for agent access |
| 5 Instructions | `instructions/*.md` | credentials, file-dispositions, file-operations, model-delegation, plan-templates |
| 3 Output Styles | `output-styles/*.md` | genui, html, technical-quality |
| 21 Skills | `skills/*/` | See the [Skills](#skills) table below |
| Guard Tools | `tools/*.py`, `tools/*.pi.ts` | config-secrets-guard hook (blocks printing secrets) + masked safe-config-reader; Pi port included |
| Hookify Rules | `hookify-rules/` | Guard denying unpinned Codex rescue/exec runs, with an 8-case test harness |
| Repo Commands | `.claude/commands/*.md` | Slash commands available inside the cloned repo: `/install-claude-config`, `/sync-claude-config`, `/unify-agents-md`, `/feature-team`, `/rename-code`, `/update-hermes`, `/yt-transcript` |

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

### 1. AGENTS.md Personal Info

Personal info lives in the **shared house rules**, not in `CLAUDE.md`. Edit `~/.config/agents/AGENTS.md` and replace the placeholder table at the top:

```markdown
## User & contact

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

### 3. AGENTS.md Environment Sections

Customize these sections in `~/.config/agents/AGENTS.md`:

| Section | What to Customize |
|---------|-------------------|
| **Cloud / infrastructure safety** | Your infra tooling and rules (or remove) |
| **Environment & file operations** | Your IDE, languages, virtual env setup |
| **Screenshots** | Your screenshot storage path, or remove this section entirely |
| **Project locations** | Your repo directory layout |

And in `~/.claude/CLAUDE.md`: the skill triggers and Codex plugin mechanics, if your skill/plugin set differs.

### 4. Optional: statusline-command.sh

The status line script works out of the box. It renders a two-line status bar: user@host, working directory, git branch, and worktree badge on line 1; model, context usage (color-coded), rate-limit badges, PR badge, session name, and vim mode on line 2. No customization needed unless you want a different format.

## Plugins

The `enabledPlugins` block in `settings.json` reflects a real working setup and changes over time — treat it as a menu, not a mandate. Check the file itself for the authoritative current list. Highlights:

### Core Enabled Plugins

| Plugin | Category | Purpose |
|--------|----------|---------|
| `superpowers` | Workflow | Advanced development workflows (TDD, debugging, planning, brainstorming) |
| `code-review` | Quality | Code review workflow with PR integration |
| `commit-commands` | Git | Git commit, push, and PR creation skills |
| `context7` | Documentation | Fetches up-to-date library documentation |
| `frontend-design` | Development | Frontend design skills and workflows |
| `security-guidance` | Security | Security best practices and vulnerability analysis |
| `codex` | Cross-provider | OpenAI Codex delegation (see `instructions/model-delegation.md` and the hookify guard rule) |
| `hookify` | Guardrails | Turn observed mistakes into PreToolUse hook rules |
| `remember` | Memory | Session-state save/recall across sessions |
| `discord` | Messaging | Discord channel pairing for remote sessions |
| `playwright` | Testing | Browser automation |
| `skill-creator` | Skills | Create, test, and benchmark skills |
| `example-skills` | Skills | Example skill collection from Anthropic |
| `huggingface-skills` | AI/ML | HuggingFace model and dataset operations |
| `ralph-loop` | Workflow | Ralph Loop iterative development workflow |

### Language Server Plugins

These provide IDE-like features. **Disable any for languages you don't use:**

| Plugin | Language | Install Requirement |
|--------|----------|-------------------|
| `clangd-lsp` | C/C++ | `sudo apt install clangd` or equivalent |
| `csharp-lsp` | C# | .NET SDK (`dotnet --version` to verify) |
| `pyright-lsp` | Python | `npm install -g pyright` or `pip install pyright` |
| `typescript-lsp` | TypeScript | `npm install -g typescript typescript-language-server` |

**To disable a plugin:** Edit `~/.claude/settings.json`, find the plugin in `enabledPlugins`, and set it to `false`.

### Disabled by Default

Installed but off in the repo config (enable if you use them): `agent-sdk-dev`, `plugin-dev`, `explanatory-output-style`, `learning-output-style`, `serena`, `gitlab`, `databases-on-aws`, `aws-core`, `aws-agents`, `blueprint`.

## MCP Servers

### Included Servers

The `mcp.json` configures three servers:

| Server | Command | Requires |
|--------|---------|----------|
| **github** | `npx -y @modelcontextprotocol/server-github` | Node.js/npm + `GITHUB_PERSONAL_ACCESS_TOKEN` |
| **chrome-devtools** | `npx chrome-devtools-mcp@latest` | Chrome running with `--remote-debugging-port=9222` |
| **acestudio** | `npx mcp-remote http://localhost:21572/mcp` | ACE Studio running locally (remove if you don't use it) |

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
| **code-reviewer** | Fable | Reviewing code for bugs, quality, performance, and best practices |
| **software-engineer** | Opus | Writing new code, fixing bugs, implementing features, refactoring |
| **performance-optimizer** | Opus | Identifying bottlenecks, optimizing algorithms, database queries |
| **documentation-specialist** | Sonnet | Creating user guides, API docs, README files, architecture docs |
| **research-assistant** | Sonnet | Researching technologies, comparing approaches, best practices |
| **test-generator** | Sonnet | Creating test suites with edge cases, mocks, fixtures |

Agents are automatically selected by Claude Code based on your task. No manual invocation needed - just describe what you need.

## Skills

| Skill | What it does / trigger phrases |
|-------|-------------------------------|
| **update-code-map** | "update the code map", "refresh CodeMap" — deterministic symbol extractor, never LLM-estimated line numbers |
| **sync-claude-config** | Push this machine's config to an SSH host, or sync `~/.claude/` back into this repo (sanitized) |
| **install-claude-config** | "install this config" — diff-and-ask merge of this repo into `~/.claude/` |
| **unify-agents-md** | Make `AGENTS.md` the single canonical guide across all AI coding CLIs |
| **disk-doctor** | Disk cleanup + install hygiene with audited safe-trash and one-command undo |
| **update-hermes** | Backup-first Hermes Agent updater |
| **graphify** | Any input → clustered knowledge graph (HTML + JSON) |
| **model-registry** | Wire current LLM model IDs from a published registry into any project |
| **imageai-cli** | Drive the ImageAI CLI: images, video, and page layouts across providers |
| **html-doc** | Standalone HTML deliverables (reports, explainers, announcements) |
| **discord-post** | Draft community posts/announcements into a `Discord/` directory |
| **feature-documenter** | "document the features", "list all capabilities" |
| **project-documenter** | Per-project user-facing docs + sitemap + `.raginclude` update |
| **technical-documenter** | Developer/support docs (APIs, data models, error handling) |
| **doc-all-projects** | Parallel sweep regenerating stale docs across all registered projects |
| **raginclude-generator** | Generate a `.raginclude` file for RAG ingest |
| **claude-md-optimizer** | "optimize CLAUDE.md", "my resume is slow" |
| **product-manager** | Full PM toolkit (strategy, discovery, GTM, execution) |
| **yt-transcript** | Download a YouTube transcript |
| **cl-project-init** | *(sanitized company example)* project scaffolder — fork and rename |
| **time** | Start any prompt with "time" to track per-step execution time |

## Output Styles

Select these in Claude Code's output style picker:

| Style | Best For |
|-------|----------|
| **GenUI** | Generating standalone HTML documents with embedded modern styling |
| **HTML** | Web development with semantic HTML, accessibility, and standards compliance |
| **Technical Quality** | Comprehensive technical analysis with systematic problem-solving |

## Config Secrets Guard (hook)

`settings.json` wires `tools/config-secrets-guard.py` as a `PreToolUse` hook. It blocks any Bash command or Read call that would print a secret-bearing config file (`config*.yaml`, `.env*`) into the conversation transcript. The companion `tools/safe-config-reader.py` prints a config file's structure with string values masked. The same guard extends to Codex, Antigravity (`--agy` flag), and Pi (`config-secrets-guard.pi.ts`) — see the README's "Config Secrets Guard" section for the per-CLI wiring snippets.

## Verification Checklist

After installation, verify everything works:

- [ ] **Restart Claude Code** - Required to load new config
- [ ] **Check status line** - Two-line bar with user@host + path on top, model + context % below
- [ ] **Test an agent** - Ask "review this code" to trigger code-reviewer
- [ ] **Test GitHub MCP** - Ask about a GitHub repo to verify the MCP server works
- [ ] **Check plugins** - Run `/help` to see available skills and commands
- [ ] **Verify AGENTS.md** - Your personal info is filled in at `~/.config/agents/AGENTS.md` (not placeholders)
- [ ] **Verify settings.json** - Read permission path has your actual username
- [ ] **Test the secrets guard** - `cat .env` in a project should be blocked with a pointer to `safe-config-reader.py`

## File Structure After Installation

```
~/.config/agents/
└── AGENTS.md                          # Shared house rules for every AI coding CLI

~/.claude/
├── CLAUDE.md                          # Thin Claude-Code file; @imports AGENTS.md (line 1)
├── CLAUDE_CodeMap.md                  # CodeMap specification
├── settings.json                      # Settings, permissions, plugins, hooks
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
│   ├── file-dispositions.md           # Standing approvals for working-tree files (template)
│   ├── file-operations.md             # File operation guidelines
│   ├── model-delegation.md            # Cross-provider routing (Claude + Codex/GPT-5.6)
│   └── plan-templates.md              # Implementation plan format
├── tools/                             # Hook scripts wired in settings.json
│   ├── config-secrets-guard.py        # PreToolUse hook: blocks printing secrets
│   ├── config-secrets-guard.pi.ts     # Same guard as a Pi extension
│   └── safe-config-reader.py          # Masked config reader
├── hookify-rules/                     # Guard rules (symlink into a project's .claude/)
│   ├── hookify.block-unpinned-codex-rescue.local.md
│   └── test-codex-guard.sh
├── output-styles/                     # Output formatting styles
│   ├── genui.md
│   ├── html.md
│   └── technical-quality.md
└── skills/                            # Custom skills (21 — see Skills table)
    ├── time.md
    ├── cl-project-init/
    ├── claude-md-optimizer/
    ├── discord-post/
    ├── disk-doctor/
    ├── doc-all-projects/
    ├── feature-documenter/
    ├── graphify/
    ├── html-doc/
    ├── imageai-cli/
    ├── install-claude-config/
    ├── model-registry/
    ├── product-manager/
    ├── project-documenter/
    ├── raginclude-generator/
    ├── sync-claude-config/
    ├── technical-documenter/
    ├── unify-agents-md/
    ├── update-code-map/
    ├── update-hermes/
    └── yt-transcript/
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Agents not appearing | Verify `.md` files in `~/.claude/agents/` have proper YAML frontmatter (`---` delimiters) |
| Skills not triggering | Check `~/.claude/skills/*/SKILL.md` exists with proper YAML frontmatter |
| CLAUDE.md import fails | Verify `~/.config/agents/AGENTS.md` exists — `CLAUDE.md` line 1 `@import`s it |
| GitHub MCP fails | Run `echo $GITHUB_PERSONAL_ACCESS_TOKEN` to verify the token is set |
| Status line missing | Check `~/.claude/statusline-command.sh` exists and is executable (`chmod +x`) |
| Secrets guard not firing | Check the `hooks` block in `settings.json` points at `~/.claude/tools/config-secrets-guard.py` and the script is executable |
| Plugins not loading | Restart Claude Code; verify plugin names in `enabledPlugins` match available plugins |
| `/resume` is slow | Run the `claude-md-optimizer` skill to extract rarely-used sections from CLAUDE.md |
| Node.js not found | Install nvm and Node.js LTS: `nvm install --lts` |

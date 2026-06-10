# Claude Code Configuration

A comprehensive, production-tested configuration for [Claude Code](https://docs.anthropic.com/en/docs/claude-code) - Anthropic's CLI for Claude. This repository mirrors a real-world `~/.claude/` setup with custom agents, skills, output styles, and best-practice instructions.

## Platform

**This config is written for Linux** (native Linux or WSL on Windows). macOS should work with minimal changes — swap `python3` for `python` where needed and replace `/home/<user>` with `/Users/<user>` in permission entries.

**Using Windows without WSL?** Ask Claude to port it for you:

> Here is my Claude Code config repo cloned at `<repo-path>`. Convert everything from Linux/WSL conventions to native Windows PowerShell equivalents: change shell scripts like `statusline-command.sh` to a PowerShell `.ps1` (or keep Bash if using Git Bash), update `/home/<USER>/` paths in `claude/settings.json` permissions to `C:\Users\<USER>\` form, replace `python3` with `python`, and adjust any `bash ~/.claude/...` invocations in `settings.json` / `statusLine` to whatever shell you want to use. Leave the rest (agents, skills, CLAUDE.md, instructions) alone — they are OS-neutral.

### `cl*` skills — heads-up

Any skill prefixed with `cl-` (e.g. `cl-project-init`) is a **sanitized example of a [Chameleon Labs](https://chameleonlabs.ai)-specific workflow**. The company-specific details (emails, product names, brand colors) have been replaced with `YourCompany` / `yourdomain.com` placeholders, but the skill is still structured around the author's use case. Treat it as a template you fork and rename for your own company, not something to install verbatim.

## What's Included

```
.claude_code/
├── README.md
├── .claude/
│   └── commands/
│       ├── install-claude-config.md  # Bootstrap command (run after cloning)
│       └── yt-transcript.md          # /yt-transcript slash command
├── claude/                            # Mirrors ~/.claude/ — install this
│   ├── CLAUDE.md                      # Global instructions (loaded every session)
│   ├── CLAUDE_CodeMap.md              # CodeMap specification (language-neutral)
│   ├── settings.json                  # Claude Code settings & permissions
│   ├── mcp.json                       # MCP server configurations
│   ├── agentic_prompt_template.md     # Template for agentic workflows
│   ├── statusline-command.sh          # Custom status line script
│   ├── agents/                        # Custom agent definitions
│   │   ├── README.md                  # Agent documentation
│   │   ├── CLAUDE.md                  # Agent-specific instructions
│   │   ├── Claude-Code-Agents-Documentation.md  # Full agent architecture reference
│   │   ├── code-reviewer.md           # Code review agent (Opus)
│   │   ├── documentation-specialist.md# Documentation agent (Sonnet)
│   │   ├── performance-optimizer.md   # Performance analysis agent (Opus)
│   │   ├── research-assistant.md      # Research agent (Sonnet)
│   │   ├── software-engineer.md       # Coding agent (Opus)
│   │   ├── test-generator.md          # Test generation agent (Sonnet)
│   │   └── specs/
│   │       └── CLAUDE_CodeMap.md      # CodeMap spec (copy for agent access)
│   ├── instructions/                  # On-demand reference docs
│   │   ├── credentials.md             # Secrets management patterns
│   │   ├── file-operations.md         # File operation guidelines
│   │   └── plan-templates.md          # Implementation plan format
│   ├── output-styles/                 # Output formatting styles
│   │   ├── genui.md                   # Generative UI (HTML output)
│   │   ├── html.md                    # HTML/web development focus
│   │   └── technical-quality.md       # Comprehensive technical analysis
│   └── skills/                        # Custom skills (slash commands)
│       ├── time.md                    # Execution time tracking
│       ├── cl-project-init/           # Sanitized example: company project scaffolder
│       ├── claude-md-optimizer/       # CLAUDE.md optimization skill
│       ├── doc-all-projects/          # Sweep-and-regenerate docs across projects
│       ├── feature-documenter/        # Feature documentation skill
│       ├── graphify/                  # Any input → knowledge graph (HTML + JSON)
│       ├── install-claude-config/     # Install config into ~/.claude/
│       ├── product-manager/           # Product management toolkit
│       ├── project-documenter/        # Per-project user-facing docs generator
│       ├── raginclude-generator/      # Generate .raginclude file for RAG ingest
│       ├── sync-claude-config/        # Sync ~/.claude/ to this repo
│       ├── technical-documenter/      # Developer/support docs generator
│       ├── update-code-map/           # CodeMap maintenance skill
│       └── yt-transcript/             # Download YouTube transcripts
└── Docs/
    └── SETUP_GUIDE.md                 # Full setup & configuration guide
```

## Installation

### Prerequisites

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) installed and working (`claude --version`)
- Linux, WSL, or macOS shell (Bash/Zsh). Native Windows users should run the conversion prompt [above](#platform) first.
- `~/.claude/` directory exists (created automatically by Claude Code on first run)
- `git` installed

---

### Option 1: Use the Install Command (Recommended)

Clone the repo, open Claude Code inside it, and run `/install-claude-config`.

```bash
git clone https://github.com/lelandg/.claude_code.git
cd .claude_code
claude .
```

Then in Claude Code:
```
/install-claude-config
```

The command is available immediately after cloning — no pre-installation needed.

**What it does:**
1. Scans `claude/` and compares every file against your existing `~/.claude/`
2. Presents a table: `NEW`, `CHANGED`, or `IDENTICAL` for each file
3. For each changed file, shows a diff and asks: **Install** / **Keep current** / **Smart merge**
4. Smart merge for `settings.json`: unions `permissions.allow` and `enabledPlugins`, keeps your personal values (`defaultMode`, `trustedWorkspaces`, etc.)
5. Smart merge for `CLAUDE.md`: keeps your version, reports any new sections you don't have yet
6. Backs up all overwritten files to `~/.claude/.backup/YYYY-MM-DD/` before writing
7. Sets `chmod +x` on shell scripts automatically

---

### Option 2: Copy Everything

```bash
git clone https://github.com/lelandg/.claude_code.git
cp -r .claude_code/claude/* ~/.claude/
```

> **Note:** This overwrites existing files without merging. Back up `~/.claude/` first if you have existing config.

---

### Option 3: Cherry-Pick What You Need

```bash
cd .claude_code

# Just the agents
cp claude/agents/*.md ~/.claude/agents/

# Just the skills
cp -r claude/skills/* ~/.claude/skills/

# Just the output styles
cp claude/output-styles/*.md ~/.claude/output-styles/

# Just the instructions
cp claude/instructions/*.md ~/.claude/instructions/
```

---

### Option 4: Start from CLAUDE.md Only

```bash
cp .claude_code/claude/CLAUDE.md ~/.claude/CLAUDE.md
```

Customize it for your workflow. This single file gives you the core benefits: date handling, security rules, work procedures, and project conventions.

---

### Required After Install

**1. Personalize `~/.claude/CLAUDE.md`** — replace the placeholder table at the top:

```markdown
| Your Name | your-github-username | your-discord-username |
```

**2. Fix the Read permission path in `~/.claude/settings.json`** — find and update:

```json
"Read(//home/<YOUR_USER>/.claude/**)"
```

Replace `<YOUR_USER>` with your actual username.

**3. Set the GitHub token** (required for GitHub MCP server):

```bash
# Add to ~/.bashrc or ~/.zshrc
export GITHUB_PERSONAL_ACCESS_TOKEN="ghp_your_token_here"
```

Generate a token at [github.com/settings/tokens](https://github.com/settings/tokens) with `repo`, `read:org`, `read:user` scopes.

**4. Restart Claude Code** to load the new config.

See **[Docs/SETUP_GUIDE.md](Docs/SETUP_GUIDE.md)** for the full guide including plugin installation, verification checklist, and troubleshooting.

## Customization Guide

### CLAUDE.md (Start Here)
The global `CLAUDE.md` is loaded into every Claude Code session. Customize these sections:

| Section | What to Change |
|---------|---------------|
| **User & Contact Info** | Your name, GitHub, Discord handles |
| **Development Environments** | Your IDE, languages, tools |
| **Runtime Notes** | Your OS, shell, virtual env setup |
| **Screenshots** | Your screenshot storage path |

### settings.json
- **permissions.allow**: Add Bash patterns for commands you frequently approve
- **permissions.defaultMode**: `"acceptEdits"` auto-accepts file edits (recommended)
- **enabledPlugins**: Toggle plugins on/off based on your needs
- **Read permissions**: Update paths to match your home directory

### mcp.json
- **github**: Requires `GITHUB_PERSONAL_ACCESS_TOKEN` environment variable ([setup instructions](Docs/SETUP_GUIDE.md#github_personal_access_token))
- Add your own MCP servers as needed

## Key Features

### Agents
Six specialized agents for different tasks. Each has a focused system prompt, specified model (Opus for complex tasks, Sonnet for simpler ones), and tool access:

- **Code Reviewer** - Thorough code review with verification-before-claims approach
- **Software Engineer** - Full implementation capability with quality standards
- **Performance Optimizer** - Algorithmic analysis, database optimization, caching strategies
- **Test Generator** - Multi-framework test suite generation
- **Documentation Specialist** - User and developer documentation
- **Research Assistant** - Technology comparison and best practices research

### Skills
Custom skills extend Claude Code with repeatable workflows:

- **update-code-map** - Maintains a comprehensive CodeMap.md for codebase navigation
- **feature-documenter** - Generates user-facing feature documentation from code analysis
- **project-documenter** - Per-project user-facing feature docs + sitemap
- **technical-documenter** - Developer and support-staff documentation (APIs, data models, errors)
- **doc-all-projects** - Parallel sweep that regenerates stale docs across every registered project
- **claude-md-optimizer** - Reduces CLAUDE.md token usage by extracting rarely-used sections
- **graphify** - Turns any input (code, docs, papers, images) into a clustered knowledge graph (HTML + JSON)
- **raginclude-generator** - Generates a `.raginclude` file to curate what a RAG knowledge base should ingest
- **cl-project-init** - *(ChameleonLabs-specific, sanitized)* Example project scaffolder (Next.js SaaS / Python / library templates). Fork and rename for your own company — the `cl-` prefix marks it as company-scoped.
- **yt-transcript** - Download a YouTube transcript into a local `yt-transcript` project
- **product-manager** - Full PM toolkit (strategy, discovery, market research, GTM, execution)
- **install-claude-config** - Merges this repo's config into `~/.claude/` with diff-and-ask conflict resolution
- **sync-claude-config** - Syncs `~/.claude/` back to this repo with automatic sanitization of private info
- **time** - Tracks execution time for each step in a workflow

### CodeMap System
The CodeMap is a structured documentation file (`Docs/CodeMap.md`) that provides:
- Line-number-accurate class/method inventory
- Visual ASCII architecture diagrams
- Cross-file dependency mapping
- Multi-level tables of contents
- Language-specific guidelines (Python, C#, JavaScript/TypeScript, XAML)

### Instructions Directory
On-demand reference files that Claude Code reads only when needed (reduces context bloat):
- **credentials.md** - Platform-specific secret storage patterns
- **file-operations.md** - Absolute path conventions and parallel search patterns
- **plan-templates.md** - Implementation checklist format with status markers

### Output Styles
Three output styles for different contexts:
- **GenUI** - Generates self-contained HTML documents with modern styling
- **HTML** - Web development focus with accessibility and standards compliance
- **Technical Quality** - Comprehensive analysis with systematic problem-solving

### Status Line
`statusline-command.sh` renders a two-line status bar: user@host, working directory, and git branch on line 1; model, context usage, PR badge (color-coded by review state), and vim mode on line 2. When the current session has a messaging channel attached (Discord, Telegram), the channel name appears in its brand color with an "active" suffix — detected live via the process tree, not just pairing files.

## Design Philosophy

### Context Efficiency
The `CLAUDE.md` is kept under ~200 lines by extracting detailed reference material to `instructions/` files. This reduces `/resume` time and token usage while keeping critical rules always loaded.

### Security First
- Credentials are never stored in project directories
- Bash commands never contain inline secrets
- All issues/inputs are treated as untrusted (prompt injection awareness)
- Supply-chain defense: 7-day minimum package age enforced across npm/pnpm/pip/uv/poetry/cargo (see `CLAUDE.md`)
- GitHub Actions: `pull_request_target` is banned — the #1 source of Actions supply-chain compromises

### Convention Over Configuration
- Projects follow their own naming conventions (checked before creating files)
- CodeMaps use standardized format across all languages
- Plan files use consistent checklist markers

## Authors

Created by **Leland Green** ([@lelandg](https://github.com/lelandg)) and **Claude** (Opus 4.6) at [Chameleon Labs](https://chameleonlabs.ai).

Join our **[Discord server](https://discord.gg/chameleonlabs)** - free AI chat with the latest Claude, Gemini, and ChatGPT pro models.

## Contributing

Found something useful to add? PRs welcome. Keep these principles in mind:
- No private information (names, paths, credentials, even as examples)
- Keep `CLAUDE.md` concise - extract detail to `instructions/`
- Agents should be generic enough for any project
- Skills should be self-contained with reference files

## License

MIT - Use however you like.

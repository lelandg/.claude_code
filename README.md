# Claude Code Configuration

A comprehensive, production-tested configuration for [Claude Code](https://docs.anthropic.com/en/docs/claude-code) - Anthropic's CLI for Claude. This repository mirrors a real-world `~/.claude/` setup with custom agents, skills, output styles, and best-practice instructions.

## What's Included

```
.claude_code/
├── README.md
├── .claude/
│   └── commands/
│       └── install-claude-config.md  # Bootstrap command (run after cloning)
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
│       ├── claude-md-optimizer/       # CLAUDE.md optimization skill
│       ├── feature-documenter/        # Feature documentation skill
│       ├── install-claude-config/     # Install config into ~/.claude/
│       ├── product-manager/           # Product management toolkit
│       ├── sync-claude-config/        # Sync ~/.claude/ to this repo
│       └── update-code-map/           # CodeMap maintenance skill
└── Docs/
    └── SETUP_GUIDE.md                 # Full setup & configuration guide
```

## Installation

### Option 1: Use the Install Command (Recommended)
Clone the repo, open Claude Code inside it, and run `/install-claude-config`. It compares each file against your existing config, shows diffs, and lets you choose per-file whether to install, skip, or smart-merge.

```bash
git clone https://github.com/lelandg/.claude_code.git
cd .claude_code
# In Claude Code:
# /install-claude-config
```

The command is available immediately after cloning — no pre-installation needed.

### Option 2: Copy Everything
```bash
git clone https://github.com/lelandg/.claude_code.git
cp -r .claude_code/claude/* ~/.claude/
```

### Option 3: Cherry-Pick What You Need
```bash
# Just the agents
cp .claude_code/claude/agents/*.md ~/.claude/agents/

# Just the skills
cp -r .claude_code/claude/skills/* ~/.claude/skills/

# Just the output styles
cp .claude_code/claude/output-styles/*.md ~/.claude/output-styles/

# Just the instructions
cp .claude_code/claude/instructions/*.md ~/.claude/instructions/
```

### Option 4: Start from CLAUDE.md Only
Copy `claude/CLAUDE.md` to `~/.claude/CLAUDE.md` and customize it for your workflow. This single file gives you the core benefits (date handling, security rules, work procedures, project conventions).

### Post-Install Setup
See **[Docs/SETUP_GUIDE.md](Docs/SETUP_GUIDE.md)** for the full setup guide covering environment variables, plugin installation, required customization, and verification steps.

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
- **claude-md-optimizer** - Reduces CLAUDE.md token usage by extracting rarely-used sections
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

## Design Philosophy

### Context Efficiency
The `CLAUDE.md` is kept under ~200 lines by extracting detailed reference material to `instructions/` files. This reduces `/resume` time and token usage while keeping critical rules always loaded.

### Security First
- Credentials are never stored in project directories
- Bash commands never contain inline secrets
- All issues/inputs are treated as untrusted (prompt injection awareness)

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

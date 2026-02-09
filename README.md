# Claude Code Configuration

A comprehensive, production-tested configuration for [Claude Code](https://docs.anthropic.com/en/docs/claude-code) - Anthropic's CLI for Claude. This repository mirrors a real-world `~/.claude/` setup with custom agents, skills, output styles, and best-practice instructions.

## What's Included

```
.claude_code/
├── CLAUDE.md                          # Global instructions (loaded every session)
├── CLAUDE_CodeMap.md                  # CodeMap specification (language-neutral)
├── settings.json                      # Claude Code settings & permissions
├── mcp.json                           # MCP server configurations
├── agentic_prompt_template.md         # Template for agentic workflows
├── statusline-command.sh              # Custom status line script
├── agents/                            # Custom agent definitions
│   ├── README.md                      # Agent documentation
│   ├── CLAUDE.md                      # Agent-specific instructions
│   ├── code-reviewer.md              # Code review agent (Opus)
│   ├── documentation-specialist.md   # Documentation agent (Sonnet)
│   ├── performance-optimizer.md      # Performance analysis agent (Opus)
│   ├── research-assistant.md         # Research agent (Sonnet)
│   ├── software-engineer.md          # Coding agent (Opus)
│   ├── test-generator.md             # Test generation agent (Sonnet)
│   └── specs/
│       └── CLAUDE_CodeMap.md         # CodeMap spec (copy for agent access)
├── instructions/                      # On-demand reference docs
│   ├── credentials.md                # Secrets management patterns
│   ├── file-operations.md            # File operation guidelines
│   └── plan-templates.md             # Implementation plan format
├── output-styles/                     # Output formatting styles
│   ├── genui.md                      # Generative UI (HTML output)
│   ├── html.md                       # HTML/web development focus
│   └── technical-quality.md          # Comprehensive technical analysis
└── skills/                            # Custom skills (slash commands)
    ├── time.md                       # Execution time tracking
    ├── claude-md-optimizer/          # CLAUDE.md optimization skill
    ├── feature-documenter/           # Feature documentation skill
    └── update-code-map/              # CodeMap maintenance skill
```

## Installation

### Option 1: Copy Everything
```bash
# Clone this repo
git clone https://github.com/<YOUR_USERNAME>/.claude_code.git

# Copy to your Claude Code config directory
cp -r .claude_code/* ~/.claude/
```

### Option 2: Cherry-Pick What You Need
```bash
# Just the agents
cp .claude_code/agents/*.md ~/.claude/agents/

# Just the skills
cp -r .claude_code/skills/* ~/.claude/skills/

# Just the output styles
cp .claude_code/output-styles/*.md ~/.claude/output-styles/

# Just the instructions
cp .claude_code/instructions/*.md ~/.claude/instructions/
```

### Option 3: Start from CLAUDE.md Only
Copy `CLAUDE.md` to `~/.claude/CLAUDE.md` and customize it for your workflow. This single file gives you the core benefits (date handling, security rules, work procedures, project conventions).

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
- **github**: Set `GITHUB_PERSONAL_ACCESS_TOKEN` as an environment variable
- **acestudio**: Remove if you don't use Ace Studio
- **chrome-devtools**: Adjust port if needed
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

## Contributing

Found something useful to add? PRs welcome. Keep these principles in mind:
- No private information (names, paths, credentials, even as examples)
- Keep `CLAUDE.md` concise - extract detail to `instructions/`
- Agents should be generic enough for any project
- Skills should be self-contained with reference files

## License

MIT - Use however you like.

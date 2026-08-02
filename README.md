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
│       ├── sync-claude-config.md     # /sync-claude-config slash command
│       ├── unify-agents-md.md        # /unify-agents-md slash command
│       ├── feature-team.md           # Multi-task plan with review loop + model ladder
│       ├── rename-code.md            # Safe cross-codebase symbol rename
│       ├── repo-doctor.md            # /repo-doctor slash command
│       ├── update-hermes.md          # /update-hermes slash command
│       └── yt-transcript.md          # /yt-transcript slash command
├── config/
│   └── agents/
│       └── AGENTS.md                  # Shared house rules for EVERY AI coding CLI
│                                      #   (mirrors ~/.config/agents/AGENTS.md; slim —
│                                      #   hard rules inline, detail via instructions/ pointers)
├── claude/                            # Mirrors ~/.claude/ — install this
│   ├── CLAUDE.md                      # Thin Claude-Code-specific file; line 1
│   │                                  #   @imports the shared AGENTS.md above
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
│   │   ├── environment.md             # IDEs, Python/.NET/Node, debugging, screenshots
│   │   ├── file-dispositions.md       # Standing approvals for working-tree files (template)
│   │   ├── file-operations.md         # File operation guidelines
│   │   ├── github-issues.md           # Issue workflow mechanics + label conventions
│   │   ├── model-delegation.md        # Cross-provider routing: Claude + Codex/GPT-5.6
│   │   │                              #   (ratings, effort ladder, Sol review-only lockdown)
│   │   ├── package-min-age.md         # 7-day min package age: per-manager config
│   │   ├── plan-templates.md          # Implementation plan format
│   │   └── runbook-standards.md       # Fully-specified runbooks (zero-inference steps)
│   ├── hookify-rules/                 # Hookify guard rules (symlink into a project's .claude/)
│   │   ├── hookify.block-unpinned-codex-rescue.local.md  # Blocks Codex rescue/exec without
│   │   │                              #   an explicit --model pin (enforces the Sol lockdown)
│   │   └── test-codex-guard.sh        # 8-case test harness for the rule
│   ├── tools/                         # Hook scripts wired in settings.json
│   │   ├── config-secrets-guard.py    # PreToolUse hook: blocks printing config*.yaml / .env* secrets
│   │   │                              #   (also speaks Codex hooks + Antigravity --agy protocols)
│   │   ├── config-secrets-guard.pi.ts # Same guard as a Pi extension (~/.pi/agent/extensions/)
│   │   └── safe-config-reader.py      # Masked config reader (structure only, strings hidden)
│   ├── output-styles/                 # Output formatting styles
│   │   ├── genui.md                   # Generative UI (HTML output)
│   │   ├── html.md                    # HTML/web development focus
│   │   └── technical-quality.md       # Comprehensive technical analysis
│   └── skills/                        # Custom skills (slash commands)
│       ├── time.md                    # Execution time tracking
│       ├── cl-project-init/           # Sanitized example: company project scaffolder
│       ├── claude-md-optimizer/       # Rightsize CLAUDE.md/skills (Claude 5 context-engineering rules)
│       ├── discord-post/              # Draft community posts/announcements to Discord/ dir
│       ├── disk-doctor/               # Disk cleanup + install hygiene (safe-trash, undo)
│       ├── doc-all-projects/          # Sweep-and-regenerate docs across projects
│       ├── feature-documenter/        # Feature documentation skill
│       ├── graphify/                  # Any input → knowledge graph (HTML + JSON)
│       ├── html-doc/                  # Standalone HTML deliverables (reports, explainers)
│       ├── imageai-cli/               # Drive the ImageAI CLI (images/video/layouts, any provider)
│       ├── install-claude-config/     # Install config into ~/.claude/
│       ├── model-registry/            # Wire current LLM model IDs from a published registry
│       ├── product-manager/           # Product management toolkit
│       ├── project-documenter/        # Per-project user-facing docs generator
│       ├── raginclude-generator/      # Generate .raginclude file for RAG ingest
│       ├── repo-doctor/               # Audit a repo's agent-docs layer; dispatch the right fix
│       ├── sync-claude-config/        # Sync ~/.claude/ to this repo
│       ├── technical-documenter/      # Developer/support docs generator
│       ├── unify-agents-md/           # Make AGENTS.md canonical across all AI CLIs
│       ├── update-code-map/           # CodeMap maintenance skill
│       ├── update-hermes/             # Backup-first Hermes Agent updater
│       ├── version-manager/           # Standardized version bumps + changelog currency
│       └── yt-transcript/             # Download YouTube transcripts
├── Docs/
│   ├── SETUP_GUIDE.md                 # Full setup & configuration guide
│   ├── install-guide.html             # Beginner-friendly visual install guide
│   └── plans/                         # Design docs for features built in this repo
└── CHANGELOG.md                       # Plain-English history of what changed and why
```

## Installation

> **New to Claude Code?** There's a beginner-friendly visual walkthrough with copy buttons for every command: **[open the HTML install guide](https://htmlpreview.github.io/?https://github.com/lelandg/.claude_code/blob/master/Docs/install-guide.html)** (or open [`Docs/install-guide.html`](Docs/install-guide.html) locally in your browser after cloning).

### Just want the skills? One-command install, no clone

This repo doubles as a Claude Code plugin marketplace. To install the general-purpose skills (claude-md-optimizer, unify-agents-md, the documenter suite, raginclude-generator, graphify, model-registry) without cloning anything:

```
/plugin marketplace add lelandg/.claude_code
/plugin install claude-config-skills@lelandg-claude-config
```

Four skills ship bundled tools and are packaged separately on the [Chameleon Labs marketplace](https://github.com/Chameleon-Labs-LLC/plugins) instead: `version-manager` + `repo-doctor` (in `repo-hygiene`), `update-code-map` (in `docs-toolkit`), and `yt-transcript`:

```
/plugin marketplace add Chameleon-Labs-LLC/plugins
/plugin install repo-hygiene@chameleon-labs
```

For the full config — agents, commands, CLAUDE.md, instructions, settings — use the options below.

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
mkdir -p ~/.config/agents
cp .claude_code/config/agents/AGENTS.md ~/.config/agents/AGENTS.md
```

> **Note:** This overwrites existing files without merging. Back up `~/.claude/` first if you have existing config. The `AGENTS.md` copy matters — `CLAUDE.md` line 1 `@import`s it.

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

### Option 4: Start from the House Rules Only

```bash
mkdir -p ~/.config/agents
cp .claude_code/config/agents/AGENTS.md ~/.config/agents/AGENTS.md
cp .claude_code/claude/CLAUDE.md ~/.claude/CLAUDE.md
```

Customize them for your workflow. `AGENTS.md` carries the core benefits — security
rules, work procedures, issue workflow, and project conventions — shared by every AI
coding CLI (Claude Code, Codex, Copilot, Gemini, Antigravity/`agy`, Pi). It is
deliberately **slim**: hard security rules stay inline, and situational detail lives in
`claude/instructions/*.md` files it points to (models read them on demand — install the
instructions dir alongside it so no pointer dangles). `CLAUDE.md` is a thin file that
`@import`s it (line 1) and adds Claude-Code-specific skill/agent triggers. See the
`unify-agents-md` skill for wiring other CLIs to the same file. Wiring summary:

- **Codex:** `ln -s ~/.config/agents/AGENTS.md ~/.codex/AGENTS.md`
- **Copilot CLI:** `ln -s ~/.config/agents/AGENTS.md ~/.copilot/copilot-instructions.md`,
  plus in `~/.bash_aliases`: `copilot() { command copilot --add-dir "$HOME/.claude/instructions" "$@"; }`
  (lets it follow the pointer files outside the working dir)
- **Antigravity/agy:** `ln -s ~/.config/agents/AGENTS.md ~/.gemini/AGENTS.md`
  (its global rules root is `~/.gemini/`; it does not resolve `@import` lines)
- **Gemini CLI:** `GEMINI.md` line 1 = `@/home/<you>/.config/agents/AGENTS.md`
- **Pi:** in `~/.bash_aliases`: `pi() { command pi --append-system-prompt "$HOME/.config/agents/AGENTS.md" "$@"; }`

---

### Required After Install

**1. Personalize `~/.config/agents/AGENTS.md`** — replace the placeholder table at the top:

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

### AGENTS.md + CLAUDE.md (Start Here)
The shared `~/.config/agents/AGENTS.md` holds the tool-agnostic house rules every AI
coding CLI follows; the global `CLAUDE.md` `@import`s it (line 1) and is loaded into
every Claude Code session. Customize these sections of `AGENTS.md`:

| Section | What to Change |
|---------|---------------|
| **User & Contact** | Your name, GitHub, Discord handles |
| **Cloud / infrastructure safety** | Your infra tooling and rules |
| **Environment & file operations** | Your IDE, languages, virtual env setup |
| **Screenshots** | Your screenshot storage path |

And in `CLAUDE.md`: the skill triggers, if you install a different skill set.

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

- **update-code-map** - Maintains a comprehensive CodeMap.md for codebase navigation; line numbers come from a deterministic symbol extractor (`references/extract_symbols.py`) with a parallel document/verify workflow — never LLM-estimated
- **feature-documenter** - Generates user-facing feature documentation from code analysis
- **project-documenter** - Per-project user-facing feature docs + sitemap
- **technical-documenter** - Developer and support-staff documentation (APIs, data models, errors)
- **doc-all-projects** - Parallel sweep that regenerates stale docs across every registered project
- **claude-md-optimizer** - Audits and rightsizes CLAUDE.md/AGENTS.md and skills per Anthropic's Claude 5 context-engineering guidance (the six shifts: rules→judgment, examples→interface design, upfront→progressive disclosure, repetition→single source, memory dump→auto-memory, specs→rich references), with a classification-first workflow, `/doctor` reconciliation, and eval-verified cuts
- **graphify** - Turns any input (code, docs, papers, images) into a clustered knowledge graph (HTML + JSON)
- **raginclude-generator** - Generates a `.raginclude` file to curate what a RAG knowledge base should ingest
- **disk-doctor** - Disk cleanup + install hygiene: scans home/dev/cache locations, proposes a plan, deletes only via an audited safe-trash helper with one-command undo
- **unify-agents-md** - Restructures instruction files so `AGENTS.md` is the single canonical guide every coding CLI follows (Claude Code, Codex, Copilot, Gemini, Pi), with `CLAUDE.md`/`GEMINI.md` as thin `@import` pointers
- **repo-doctor** - Read-only triage over the whole agent-docs layer of a repo: instruction-file topology, always-loaded token cost, CodeMap age plus *sampled line-number accuracy* (claims are checked against the source, not assumed), broken pointers, and changelog-vs-code version drift. Reports first, then dispatches `unify-agents-md` → `claude-md-optimizer` → `update-code-map` → `version-manager` in dependency order — topology before content, because rightsizing a `CLAUDE.md` that is about to become an `@import` pointer throws the work away
- **update-hermes** - Backup-first updater for a Hermes Agent install: patch/tarball backup of source customizations (the built-in backup excludes the source repo), `hermes update --backup`, post-update verification, and a documented restore path
- **cl-project-init** - *(ChameleonLabs-specific, sanitized)* Example project scaffolder (Next.js SaaS / Python / library templates). Fork and rename for your own company — the `cl-` prefix marks it as company-scoped.
- **yt-transcript** - Download a YouTube transcript into a local `yt-transcript` project
- **product-manager** - Full PM toolkit (strategy, discovery, market research, GTM, execution)
- **install-claude-config** - Merges this repo's config into `~/.claude/` with diff-and-ask conflict resolution
- **sync-claude-config** - Syncs `~/.claude/` back to this repo with automatic sanitization of private info
- **version-manager** - Standardized version bumping and changelog currency for any repo, in any stack. Auto-detects where the version lives (pyproject, package.json, `VERSION` file, module constants, README display) with no per-repo config, reconciles git history against the changelog, and reconstructs missing git tags from history. Dry-run by default.
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

### Cross-Provider Model Delegation (Claude + Codex/GPT-5.6)
`instructions/model-delegation.md` is a full routing guide for pairing Claude with OpenAI's Codex through the official `openai-codex` Claude Code plugin: per-model routing scores (quota/intelligence/taste), a reasoning-effort ladder with quota impact, and the shipping loop — *write with Claude, audit with Codex, reconcile the findings*. It encodes a hard safety policy: **`gpt-5.6-sol` is review-only** (it inherits from `~/.codex/config.toml` on the un-pinnable review commands, which are read-only), so every `/codex:rescue` must pin `--model gpt-5.6-terra|luna` explicitly. `hookify-rules/hookify.block-unpinned-codex-rescue.local.md` enforces that mechanically — it denies any Bash invocation of the Codex rescue/exec path without an allowed model pin (symlink it into a project's `.claude/` to arm it; `test-codex-guard.sh` verifies all 8 allow/deny cases). The compact version of the policy lives in `AGENTS.md` § "Model delegation & cross-provider review".

### Output Styles
Three output styles for different contexts:
- **GenUI** - Generates self-contained HTML documents with modern styling
- **HTML** - Web development focus with accessibility and standards compliance
- **Technical Quality** - Comprehensive analysis with systematic problem-solving

### Status Line
`statusline-command.sh` renders a two-line status bar: user@host, working directory, git branch, and worktree badge on line 1; model, context usage (color-coded: green <50%, yellow 50–79%, red ≥80%), rate-limit badges (5h/7d, for Claude.ai subscribers), PR badge (color-coded by review state), session name, and vim mode on line 2.

### Config Secrets Guard
A `PreToolUse` hook (`tools/config-secrets-guard.py`, wired in `settings.json`) blocks any Bash command or Read call that would print a secret-bearing config file (`config*.yaml`, `.env*`) into the conversation transcript — where it could be logged or shared. The companion `tools/safe-config-reader.py` prints a config file's structure with every string value masked, so agents can debug configuration without ever seeing the secrets. A human-approved `# config-ok` suffix is the escape hatch for write-only commands (e.g. `sed -i`).

The same guard extends to the other agent CLIs:

- **Codex CLI** — Codex hooks speak the same protocol as Claude Code. Add to `~/.codex/hooks.json`:
  ```json
  {"hooks": {"PreToolUse": [{"matcher": "Bash|shell|local_shell|Read|read_file|view_file",
    "hooks": [{"type": "command", "command": "python3 /home/<USER>/.claude/tools/config-secrets-guard.py", "timeout": 10}]}]}}
  ```
  Then run `/hooks` inside Codex once to review and **trust** the hook (untrusted hooks are silently skipped).
- **Antigravity CLI (`agy`)** — different hook protocol (`toolCall.args` in, `{"decision": "deny"}` out); the script handles it via the `--agy` flag. Add to `~/.gemini/config/hooks.json`:
  ```json
  {"config-secrets-guard": {"PreToolUse": [{"matcher": ".*",
    "hooks": [{"type": "command", "command": "python3 /home/<USER>/.claude/tools/config-secrets-guard.py --agy", "timeout": 10}]}]}}
  ```
- **Pi** — no external-command hooks; `tools/config-secrets-guard.pi.ts` is a TypeScript port of the same rules as a Pi extension. Copy it to `~/.pi/agent/extensions/` and it blocks `bash`/`read` tool calls globally.

## Design Philosophy

### Context Efficiency
The always-loaded instruction files stay lean: `CLAUDE.md` is a ~50-line pointer file, and the shared `AGENTS.md` is a slim (~2,500-token) rulebook — hard security/money/data-loss rules verbatim, everything procedural compressed to one-liners, and situational detail extracted to `instructions/` files that any CLI's model reads on demand via plain-path pointers. This halves always-loaded context versus a monolithic AGENTS.md while keeping critical rules always in force.

### Security First
- Credentials are never stored in project directories
- Bash commands never contain inline secrets
- All issues/inputs are treated as untrusted (prompt injection awareness)
- Supply-chain defense: 7-day minimum package age enforced across npm/pnpm/pip/uv/poetry/cargo (see `AGENTS.md`)
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

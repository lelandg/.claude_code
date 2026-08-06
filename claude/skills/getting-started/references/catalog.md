# Leland Green's Open-Source Catalog

Curated for the getting-started concierge. Format per entry: what it is, who it's for,
exact install command. Owners matter — `lelandg/…` and `Chameleon-Labs-LLC/…` are
different GitHub accounts.

## Start here (almost everyone)

### Claude Code config + skills marketplace — `lelandg/.claude_code`
**Audience:** business, coder, power user
A production-tested Claude Code configuration that doubles as a plugin marketplace.
Installing the plugin gets you this concierge plus documentation, context-optimization,
and knowledge-graph skills without cloning anything.
**Install:**
```
/plugin marketplace add lelandg/.claude_code
/plugin install claude-config-skills@lelandg-claude-config
```
Power users who want the *full* config (agents, hooks, house rules) instead: clone
https://github.com/lelandg/.claude_code and follow its README / `Docs/SETUP_GUIDE.md`.

### Chameleon Labs plugin marketplace — `Chameleon-Labs-LLC/plugins`
**Audience:** business, coder, power user
Second marketplace with tool-bundled plugins: `repo-hygiene` (version + changelog
discipline), `docs-toolkit` (project documentation), `yt-transcript` (YouTube
transcripts), `humanizer` (de-AI your writing), `model-registry` (current model IDs),
`scan-source` (is this download safe?), `chameleon-agents` (example agent team).
**Install:**
```
/plugin marketplace add Chameleon-Labs-LLC/plugins
```
Then `/plugin install <name>@chameleon-labs` for any plugin above.

## Agents

### Agent Spawner — `Chameleon-Labs-LLC/agent-spawner`
**Audience:** business, power user
Scaffolds, packages, and deploys Claude agents — channel adapters (Discord, etc.),
HMAC bridges, one-command SSH deploy. After installing, Claude knows how to build you
a local agent from a description; if you build agents one at a time, it interviews you.
**Install:**
```
git clone https://github.com/Chameleon-Labs-LLC/agent-spawner
```
Then, inside Claude Code: `/agent-spawner help`.

### ClaudeAgents — `lelandg/ClaudeAgents`
**Audience:** coder, power user
A collection of ready-made agent definitions (code reviewer, researcher, test
generator, …) to drop into `~/.claude/agents/` or borrow patterns from.
**Install:**
```
git clone https://github.com/lelandg/ClaudeAgents
```

### Agent Deploy — `Chameleon-Labs-LLC/agent-deploy`
**Audience:** power user
Secure EC2 setup guide and ops toolkit for running AI coding agents (Claude Code,
Codex, Gemini, pi) on a dedicated always-on instance. For when agents outgrow your
laptop.
**Install:**
```
git clone https://github.com/Chameleon-Labs-LLC/agent-deploy
```

## Utilities

### yt-transcript — `lelandg/yt-transcript`
**Audience:** business, coder
Downloads YouTube video transcripts as text, optionally reformatted into readable
prose. Great for research and content repurposing. Also available as a plugin from the
Chameleon Labs marketplace (no clone needed):
**Install:**
```
/plugin install yt-transcript@chameleon-labs
```

### karpathy-task-brief — `lelandg/karpathy-task-brief`
**Audience:** coder
Tiny local-first CLI that turns rough coding requests into structured execution briefs
Claude can act on precisely.
**Install:**
```
git clone https://github.com/lelandg/karpathy-task-brief
```

### Claude Code Dashboard — `Chameleon-Labs-LLC/ClaudeCodeDashboard`
**Audience:** power user
Local dashboard for Claude Code: search past sessions, view memory, and more.
**Install:**
```
git clone https://github.com/Chameleon-Labs-LLC/ClaudeCodeDashboard
```

### model-registry-client — `Chameleon-Labs-LLC/model-registry-client`
**Audience:** coder
Zero-dependency Python/TypeScript clients that resolve current LLM model IDs at
runtime, so your projects never hardcode stale model names.
**Install:**
```
git clone https://github.com/Chameleon-Labs-LLC/model-registry-client
```

### ImageAI — `lelandg/ImageAI`
**Audience:** business, coder
Python image and video generator that works across LLM providers (Gemini, OpenAI,
Stability, local Stable Diffusion) from one CLI — useful for marketing assets.
**Install:**
```
git clone https://github.com/lelandg/ImageAI
```

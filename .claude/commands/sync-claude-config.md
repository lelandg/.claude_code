---
description: Sync Claude Code + cross-CLI config (AGENTS.md, CLAUDE.md, GEMINI.md, agents, skills, settings, plugins) from this machine to an SSH host
argument-hint: "[host] — ssh alias from ~/.ssh/config; omit to discover and choose"
---

Invoke the `sync-claude-config` skill and pass the arguments through: $ARGUMENTS

If no host was given, discover candidates from ~/.ssh/config per the skill's §0 and ask which to sync. The skill is push-only (local → remote) and never copies credentials or machine state.

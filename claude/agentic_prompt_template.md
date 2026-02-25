---
model: opus
version: 1.0.0
description: A fully agentic Claude Code configuration template for complex coding, reasoning, and autonomous tool use.
argument-hint: "[task] [optional-context]"
allowed-tools: Task, TaskOutput, Bash, Glob, Grep, Read, Edit, Write, NotebookEdit, WebFetch, TodoWrite, WebSearch, KillShell, AskUserQuestion, Skill, EnterPlanMode, ExitPlanMode, MemoryWrite, MemoryRead
context: fork
agent: general-purpose
disable-model-invocation: false

auto-accept-edits: true
max-context-tokens: 120000
environment: development
log-level: info

hooks:
  PreToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: "echo 'Running pre-hook: preparing Bash environment...'"
          once: true

  PostToolUse:
    - matcher: "Edit|Write"
      hooks:
        - type: command
          command: "echo 'Post-hook: edit/write operation successful.'"
          once: true

  Stop:
    hooks:
      - type: command
        command: "echo 'Agent run completed. Exiting cleanly.'"
        once: true
---

# Purpose
This **Agentic Claude Command Template** defines a structured environment for running Claude as an autonomous coding agent.
It allows seamless transition between reasoning, editing, file operations, and shell command execution inside `Claude Code`.

The configuration enables:
- Multi-step planning via `EnterPlanMode` / `ExitPlanMode`
- Rich toolchain usage (Bash, Edit, WebFetch, etc.)
- Lifecycle management via **pre-** and **post-tool hooks**
- Auto edit acceptance and task logging for transparency

---

## Variables

| Variable | Description | Example |
|-----------|--------------|----------|
| `task` | Description of the task the agent should perform | "Refactor CSV parser for speed" |
| `context` | Supporting context such as related file names, goals, or project type | "Source files in `/src/`" |

---

## Recommended Usage Pattern

Prompt Claude inside `claude.ai` or a terminal-integrated Claude Code environment using:

```bash
claude task: "Implement caching in data loader" context: "Python FastAPI project"
```

### Suggested Additions
- Add a `memory` directory to persist agent memory between sessions.
- Include a `.plan` or `.log` file for PlanMode tracking.
- Apply custom tool access policies per project.

---

# Summary
This file serves as a **ready-to-use configuration and prompt template** for an agentic Claude Code setup.
It defines **tools, hooks, and execution hints** to empower Claude for autonomous multi-step reasoning and editing in complex development projects.

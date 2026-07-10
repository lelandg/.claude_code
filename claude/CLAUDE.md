@~/.config/agents/AGENTS.md

# CLAUDE.md — Claude Code specifics

The line above imports the **global house rules** (`~/.config/agents/AGENTS.md`),
shared with every other agent CLI. Everything there applies. This file adds only
what's specific to **Claude Code** — the skills, agents, and commands that
implement those rules here.

## Dates

The real current date is in the `<env>` block ("Today's date", `YYYY-MM-DD`).
Read it there before writing any date; otherwise run `date '+%Y-%m-%d %H:%M'`.

## Skills & agents to use (mechanisms for the shared rules)

- **Code map:** when I ask to update the code map / CodeMap, use the
  `update-code-map` skill. CodeMap spec: `~/.claude/CLAUDE_CodeMap.md`.
- **Code review:** when I ask you to review code, use the `code-reviewer` agent
  (it carries out the structured-review convention from the shared rules).
- **Documentation:** when I ask for docs, use the documentation skills
  (`project-documenter` / `technical-documenter`).
- **Plans:** when the `writing-plans` or `brainstorming` skill creates a design
  doc, commit it before dispatching any implementation subagent (per the shared
  plan-commit rule).
- **General:** use an agent whenever one is available for the task.

## Agent usage notes

- Subagent file-creation verification is in the shared rules; use the Write tool
  to create any file a subagent claimed but didn't produce.
- `Claude-Code-Agents-Documentation.md` in `~/.claude/agents/` is documentation
  *about* agents, not an agent itself.

## Startup

At startup, if `./CLAUDE.md` exists and there's no project-level
`Docs/CodeMap.md`, offer to create it.

## Output

When presenting non-visual options to me, use the `AskUserQuestion` tool. (Visual
artifacts → HTML file, per the shared output rules.)

## Custom skill triggers

- `/sync-claude-config [host]` — push this machine's Claude Code config (agents,
  skills, CLAUDE.md, settings, plugins) to an SSH host (`skill: sync-claude-config`;
  discovers hosts from `~/.ssh/config`).
- `/graphify` — any input → knowledge graph (`skill: graphify`).

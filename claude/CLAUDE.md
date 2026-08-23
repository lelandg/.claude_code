@~/.config/agents/AGENTS.md

# CLAUDE.md — Claude Code specifics

The line above imports the **global house rules** (`~/.config/agents/AGENTS.md`),
shared with every other agent CLI. Everything there applies. This file adds only
what's specific to **Claude Code** — the skills, agents, and commands that
implement those rules here.

## Dates

The real current date is in the `<env>` block ("Today's date", `YYYY-MM-DD`).
Read it there before writing any date; otherwise run `date '+%Y-%m-%d %H:%M'`
(WSL) or `Get-Date -Format 'yyyy-MM-dd HH:mm'` (Windows).

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

## Codex delegation (GPT-5.6) — plugin mechanics

The shared rules' "Model delegation & cross-provider review" section is
implemented here by the `codex` plugin (full guide:
`~/.claude/instructions/model-delegation.md`):

- `/codex:review [--base <ref>]` —
  read-only reviews; they inherit Sol from `~/.codex/config.toml` (the only
  place Sol is allowed). Commit everything first.
- `/codex:adversarial-review [focus ...]` — restricted to the user. When the
  user asks you to, tell them how to run it for the task at hand.
- `/codex:rescue --model gpt-5.6-terra|gpt-5.6-luna --effort <e> [--background] <task>`
  — **`--model` is mandatory** (unpinned would inherit Sol, which is
  review-only). Plugin caps effort at `xhigh` (`max` exists in the CLI/API but
  the plugin rejects it — workaround in the guide); multi-file jobs → `--background`.
- `/codex:status` / `/codex:result` / `/codex:cancel` — background jobs;
  `/codex:setup` — health check. There is no `/codex:transfer`.
- Leave the stop-review gate disabled (`/codex:setup` shows its state).

## Custom skill triggers

- `/sync-claude-config [host]` — push this machine's Claude Code config (agents,
  skills, CLAUDE.md, settings, plugins) to an SSH host (`skill: sync-claude-config`;
  discovers hosts from `~/.ssh/config`).
- `/graphify` — any input → knowledge graph (`skill: graphify`).
- `/model-registry [install|migrate|status|refresh-fallback]` — wire current LLM
  model IDs from the published registry into any project (`skill: model-registry`;
  clients: https://github.com/Chameleon-Labs-LLC/model-registry-client).
- `/version-manager [check|backfill|release <major|minor|patch>]` — standardized
  version bump + changelog for any repo, auto-detecting where the version lives
  (`skill: version-manager`; tool: `~/.claude/skills/version-manager/version_tool.py`).
  Dry-run by default, `--apply` to write. `backfill` is once per repo (reconstructs
  git tags from history, fills changelog gaps). Required before every PR per the
  versioning rule in `~/.config/agents/AGENTS.md`.
- `/repo-doctor [path | all] [--fix]` — read-only audit of a repo's agent-docs
  layer: AGENTS.md/CLAUDE.md topology, always-loaded token cost, CodeMap age +
  sampled line-number accuracy, broken pointers, changelog-vs-code drift
  (`skill: repo-doctor`; tool: `~/.claude/skills/repo-doctor/audit.py`).
  Triage only — dispatches `/unify-agents-md` → `/claude-md-optimizer` →
  `/update-code-map` → `/version-manager` in that dependency order.

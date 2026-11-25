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
- **Code review:** when I ask you to review code, use the built-in `/code-review`
  skill (it carries out the structured-review convention from the shared
  rules). Where a repo ships its own pre-PR reviewer, use that before opening
  a PR. (The `code-reviewer` agent in `claude/agents/` predates the built-in
  skill and is no longer the default.)
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

## Codex delegation (GPT-6 Astra / GPT-5.6) — CLI mechanics

The shared rules' "Model delegation & cross-provider review" section is
implemented here through the `codex` CLI, run from the Bash tool (full guide:
`~/.claude/instructions/model-delegation.md`). Never use the `/codex:*`
plugin slash commands: they are user-only, and cloud and project sessions do
not have them. Every call pins `-m gpt-6-astra` and an explicit effort
(`-c model_reasoning_effort=<e>`); every review adds `-s read-only`.

- **Council review** (every PR, before it opens) — commit everything first,
  then run the council from the Bash tool (background for a large diff):
  `python /path/to/.claude_code/tools/council/council.py review --repo <repo> --purpose "<PR title and first paragraph>"`
  The seated members come from `~/.config/agents/council.toml` (default
  Astra and Neon; `council.py list` shows them). The base is the remote's
  default branch unless `--base` says otherwise. Exit 10 means a member did
  not review: read `summary.md` in the results folder, name that member in
  the PR body, and go on.
- **Adversarial pass** (auth, billing, data migration) — the same command
  with `--council security --adversarial`. That council's members run at
  `xhigh` (the guide's ladder: adversarial depth where failure is expensive).
- **By hand** (the runner is missing, or one member needs a re-run) — the
  per-CLI commands are in the guide: "Reaching Codex from any agent CLI",
  "Neon reviews through agy", "Copilot reviews". An empty result with exit 0
  is a failed review, not a clean one.
- **Rescue** (investigation or fix delegation; it writes) — clean
  `git status` first, task written to a file, then:
  `codex exec -m gpt-6-astra -c model_reasoning_effort=<effort> -s workspace-write -C <repo> --ephemeral -o <result.md> - < <task.md>`
  Review the diff afterwards. Terra (`-m gpt-5.6-terra`) only as a named
  fallback. Never `gpt-5.6-sol` and never the bare `gpt-5.6` alias.
- Effort `low|medium|high|xhigh` on your own judgment; `max` only with
  the user's approval. Astra rejects `none` and `minimal`.
- Long or multi-file runs: Bash `run_in_background`, then read `<result.md>`.
- A `401` means `codex login` is needed; procedure in the guide.
- Leave the plugin's stop-review gate disabled; reviews run at commit/PR
  boundaries.
- Spawned Claude agents: Haiku = mechanical, Sonnet = integration and
  low-risk review, Fable/Opus = prod-gating and orchestration.

### Sol — agents never run it (standing policy; lift it deliberately)

No agent runs `gpt-5.6-sol` or the bare `gpt-5.6` alias (= Sol), review or
not. The ban is in the shared Security section; Sol has a record of
destructive autonomous action elsewhere (deleted home dirs, intrusion into
other systems in pursuit of a goal).

- A Sol review is the user's to run in their own terminal: read-only
  (`codex exec -s read-only ... -m gpt-5.6-sol`), on committed work with a
  clean `git status`, never with a mode that can write.
- The council runner refuses any Sol model id at load time. Where the
  `block-unpinned-codex-rescue` hookify rule is armed it also denies any
  `codex exec` naming Sol or the bare alias; where no hook enforces it, the
  rule is yours to keep.

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
  git tags from history, fills changelog gaps). The lander runs `release` at
  merge time; run it yourself only for `check`, `backfill`, or a release
  outside a PR.
- `/land-pr [status | land <owner/repo#N> | sweep]` — finish pull requests:
  classify every open PR, land the ready ones (version bump → checks → merge →
  tag) and close superseded autofix drafts (`skill: land-pr`; tool:
  `~/.claude/skills/land-pr/pr_tool.py`). Dry-run by default, `--apply` to
  write. Run `status --repo` before reporting work done, per "Landing" in
  `~/.config/agents/AGENTS.md`.
- `/unify-agents-global-git-config [global|local|dir <path>] [target <path>] [quiet]`
  — identical git/commit rules across all repos: green-source check, Workflow
  scan (`~/.claude/workflows/unify-agents-global-git-config.js`), unified
  conflict questions, one managed `unified-git-rules` block per repo
  (`skill: unify-agents-global-git-config`).
- `/repo-doctor [path | all] [--fix]` — read-only audit of a repo's agent-docs
  layer: AGENTS.md/CLAUDE.md topology, always-loaded token cost, CodeMap age +
  sampled line-number accuracy, broken pointers, changelog-vs-code drift
  (`skill: repo-doctor`; tool: `~/.claude/skills/repo-doctor/audit.py`).
  Triage only — dispatches `/unify-agents-md` → `/claude-md-optimizer` →
  `/update-code-map` → `/version-manager` in that dependency order.
- **Central runbook** (not a skill; a CLI) — every step waiting on you:
  `python /path/to/projects/_runbook/runbook.py add|add-decision|list|show|verified|reopen|reply|restore`
  (alias it as `runbook`; install from `tools/runbook/` in the config repo).
  Page: `http://127.0.0.1:8765`. Rules:
  `~/.claude/instructions/runbook-standards.md`, first section.

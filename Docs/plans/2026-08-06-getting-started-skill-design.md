# `getting-started` Skill — Design

**Date:** 2026-08-06
**Status:** Approved (design); implementation plan to follow
**Origin:** `Notes/Josiah-Claude-help.md` — onboarding a newcomer (Josiah) surfaced the need
for a concierge skill that interviews new users and sets them up.

## Purpose

A getting-started concierge for people new to Claude Code (desktop app Code tab or CLI),
business users and coders alike. It interviews the user, adapts to their subscriptions,
checks their configuration, recommends the right pieces of Leland's open source, and ends
with a personalized HTML action plan.

Distribution: **headline skill** of the `claude-config-skills` plugin in
`lelandg/.claude_code`. A newcomer runs
`/plugin marketplace add lelandg/.claude_code`, installs the plugin, and
`/getting-started` is the front door to everything else.

## Architecture

Pure `SKILL.md` + references — no bundled code. Config checks are documented shell
probes the model runs and interprets. Nothing to install, nothing to break, works on
any OS/surface — the right trade-off for the least-technical users this serves.

```
getting-started/            # lives at ~/.claude/skills/ (live) and claude/skills/ (this repo)
├── SKILL.md             # interview flow, adaptation rules, config-check probes,
│                        #   HTML-plan generation instructions
├── references/
│   ├── catalog.md       # curated OSS catalog: goal → repo/plugin → install command
│   ├── claude-basics.md # Chat vs Code vs Cowork, tasks/token etiquette,
│   │                    #   plugins/marketplaces, managed agents, subscription tiers
│   └── other-tools.md   # Codex / Copilot / Antigravity / Gemini one-paragraphs;
│                        #   PyCharm Community Edition recommendation
└── assets/
    └── plan-style.md    # HTML action-plan skeleton + copy-button snippet
```

References load on demand, not upfront — keeps the always-loaded cost near zero.

## Triggering

Skill description triggers on newcomer language — "help me get started", "I'm new to
Claude", "what can Claude do for my business", "set up my agents", "which of your tools
should I install" — plus the explicit `/getting-started` command. The skill never assumes
prior knowledge; every piece of jargon gets a one-line explanation on first use.

## Interview flow

Always interview first, **one question at a time** (AskUserQuestion where available,
plain numbered questions otherwise):

1. **Goal** — what should Claude help with? (business ops, coding, content, research,
   automation, …) If coding is in the mix, follow up: do they already have an IDE
   installed, and which one?
2. **Subscriptions** — which Claude plan (free trial / Pro / Max)? Any other AI
   subscriptions (ChatGPT, Copilot, Gemini)?
3. **Surface & OS** — desktop app or CLI; Windows / macOS / Linux.

### Adaptation rules (baked into SKILL.md)

- **Trial or free plan → efficiency mode.** Concise answers, finish-a-task-start-a-new-task
  token etiquette, no token-heavy extras without asking first.
- **Other AI subscriptions → adapt + point.** One-paragraph intro to the matching
  companion tool (ChatGPT sub → Codex CLI, etc.) with the official install link only.
  No step-by-step setup for non-Claude tools in v1.
- **Coding goal, no IDE → PyCharm Community Edition.** Free IDE; its AI-assistant
  plugin ecosystem means switching provider subscriptions doesn't mean switching IDEs.
- **Coding goal, IDE already installed → brief mention only.** Respect their existing
  setup; note PyCharm CE in one sentence as an alternative worth knowing about and
  move on.

### Config check

Documented probes the model runs and interprets: `claude --version` / `claude doctor`,
`ls ~/.claude`, CLAUDE.md presence, installed plugins/marketplaces. Improvements are
**offered with an explanation, never silently applied** — the skill instructs Claude to
get consent before any install or config change.

### Recommendations

Goal-keyed lookups in `references/catalog.md`; install what the user agrees to,
defer the rest to the HTML plan.

## Reference file contents

- **`catalog.md`** — each entry: repo/plugin, one-line what-it-is, who it's for
  (business / coder / power user), exact install command, correct owner. Covers at
  minimum: `lelandg/.claude_code` (config + this marketplace),
  `Chameleon-Labs-LLC/plugins` (second marketplace: repo-hygiene, docs-toolkit,
  yt-transcript, humanizer, model-registry, scan-source, chameleon-agents),
  `Chameleon-Labs-LLC/agent-spawner`, `lelandg/ClaudeAgents`, `lelandg/yt-transcript`,
  `lelandg/karpathy-task-brief`, `Chameleon-Labs-LLC/ClaudeCodeDashboard`,
  `Chameleon-Labs-LLC/agent-deploy`, `Chameleon-Labs-LLC/model-registry-client`,
  `lelandg/ImageAI`.
- **`claude-basics.md`** — Chat vs Code vs Cowork ("do almost everything in Code; Chat
  is for research; Cowork controls your computer"), tasks & token etiquette (once a task
  completes, start a new one), what plugins/marketplaces are, managed agents
  (platform.claude.com, separate login, requires usage credits, "you probably don't
  need one yet"), subscription tiers.
- **`other-tools.md`** — adapt-and-point paragraphs for Codex CLI, Copilot CLI,
  Antigravity, Gemini CLI; PyCharm CE recommendation and why.

## HTML action plan

Generated at the **end** of the interview, following `assets/plan-style.md`:

- Their goals restated in their words.
- What was checked / installed / configured this session.
- Remaining recommendations with install commands.
- Numbered "do this next" steps — **every command and suggested prompt gets a
  copy-to-clipboard button**.
- Self-contained HTML (inline CSS/JS, no external dependencies), saved to the working
  directory as `getting-started-plan.html` and surfaced/opened.

## Repo integration & maintenance

- **Authored live** in `~/.claude/skills/getting-started` (so Leland uses and tests the
  real thing), mirrored to this repo via `/publish-claude-config`.
- **Marketplace:** first entry in the plugin's `skills` list; plugin description
  rewritten to lead with it; version bump + CHANGELOG entry via `/version-manager`
  (never hand-edited).
- **README:** short "New here? Start with `/getting-started`" section near the top.
- **Catalog maintenance:** documented one-line step in the repo README — ship a new
  public repo → add a catalog line before the next `/publish-claude-config`.

## Edge cases

- Already-configured user → skip setup, go straight to recommendations.
- No network → catalog is local; install commands still shown for later.
- Native Windows (no WSL) → point at the README's porting prompt.
- No AskUserQuestion support → fall back to numbered questions in prose.
- Never run installs or config changes without explicit consent.

## Testing

- Implementation follows the `superpowers:writing-skills` checklist.
- Role-play three personas in fresh sessions:
  1. Josiah-style business user on the desktop app (no coding).
  2. Trial user → verify efficiency mode engages.
  3. Coder with a ChatGPT subscription → verify Codex pointer + PyCharm CE rec.
- Render the generated HTML plan; confirm copy buttons work and page is self-contained.

## Out of scope (v1)

- Step-by-step setup for non-Claude tools.
- Live GitHub catalog fetching.
- Bundled audit script (`audit.py`) — revisit only if probe-based checks prove unreliable.

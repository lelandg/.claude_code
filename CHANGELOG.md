# Changelog

A plain-English history of what changed in this repository and why. Newest first.
(Dates match the git history; run `git log --oneline` for the commit-level detail.)

## 2026-08-06

- **New skill: `getting-started`.** Added the `getting-started` concierge — the marketplace's new headline skill. It interviews newcomers one question at a time (goals, subscriptions, surface), adapts (efficiency mode on trial plans, companion-tool pointers for other AI subscriptions, PyCharm CE advice scaled to whether an IDE exists), checks configuration with consent, recommends from a curated catalog of Leland's open source, and generates a personalized HTML action plan with copy-to-clipboard commands. Wired into `.claude-plugin/marketplace.json` (`claude-config-skills` now at 0.3.0, nine skills) and the README.

## 2026-08-05

- **New skill: `astrocade-game-creation`.** Design, prompt-plan, playtest, and ship casual games on [Astrocade](https://www.astrocade.com), the wish-based AI game-creation platform. Ships a staged wish-prompt pattern library (`references/wish-patterns.md`), the Astro Academy method — including the silent-observation playtest protocol with its binary build/abandon decision rule (`references/academy-method.md`) — and a one-page game-design-doc template (`assets/gdd-template.md`). Pure markdown with relative paths, so it's also packaged into the `claude-config-skills` marketplace plugin (now at 0.2.0, eight skills).

## 2026-08-02

- **This repo is now a plugin marketplace too.** Added `.claude-plugin/marketplace.json`, so `/plugin marketplace add lelandg/.claude_code` works directly — no clone needed. One plugin, `claude-config-skills`, exposes the seven general-purpose skills that run self-contained (claude-md-optimizer, unify-agents-md, project-documenter, technical-documenter, feature-documenter, raginclude-generator, model-registry). `graphify` is deliberately not packaged — it is third-party work by Safi Shamsi ([Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify), MIT/Apache-2.0) that ships its own installer; install it from upstream. The four skills that ship bundled tools (`version-manager`, `repo-doctor`, `update-code-map`, `yt-transcript`) reference `~/.claude/skills/...` paths that only exist after a full config install, so they're published separately — with plugin-relative paths — on the [Chameleon Labs marketplace](https://github.com/Chameleon-Labs-LLC/plugins) as `repo-hygiene`, `docs-toolkit`, and `yt-transcript`. The README's Installation section explains both routes. Cloning and `/install-claude-config` remain the way to get the *full* config (agents, commands, CLAUDE.md, instructions, settings).

## 2026-07-31

- **New skill: `repo-doctor`.** A read-only checkup for everything an AI agent actually reads in a repo. It measures rather than guesses: instruction-file topology (is `AGENTS.md` canonical, do `CLAUDE.md`/`GEMINI.md` `@import` it), the token cost you pay on every single request, how old the CodeMap is *and* whether its line numbers still resolve to the symbols they name, pointers that no longer exist, and a changelog that disagrees with the version in the code. It fixes nothing itself — it reports, then hands off to `unify-agents-md` → `claude-md-optimizer` → `update-code-map` → `version-manager`, always in that order. The order is the point: rightsizing a `CLAUDE.md` that is about to be replaced by a one-line `@import` pointer throws the work away, so topology gets settled first. A repo carrying only a `CLAUDE.md` is called out loudly, because Codex, Copilot, and the other CLIs read `AGENTS.md` and are getting no repo rules at all.

## 2026-07-29

- **`claude-md-optimizer` rewritten around Anthropic's Claude 5 context-engineering guidance.** The skill now teaches six shifts — rules→judgment, examples→interface design, upfront→progressive disclosure, repetition→single source, memory dump→auto-memory, specs→rich references — and runs classification-first: every instruction is sorted into keep-verbatim (security and data-loss rules), compress-to-judgment, move-to-a-skill-or-reference, or delete-as-duplicate, and you see that table before anything is edited. Also gained `/doctor` reconciliation, layer-model placement guidance, keep/cut audit tables, and the token math that justifies the cuts.

## 2026-07-24

- **Documentation refresh + this changelog.** Brought `Docs/SETUP_GUIDE.md` up to date with everything added since February (the AGENTS.md house-rules split, all 21 skills, the secrets-guard hook, the hookify Codex guard, current plugins and MCP servers). Fixed the HTML install guide's stale bits — personal info now goes in `~/.config/agents/AGENTS.md`, and the manual-copy commands now install that file too. Refreshed the plugins-and-skills inventory in `Notes/`. Added this file.
- **Cross-provider model delegation arrived.** The shared house rules (`config/agents/AGENTS.md`) gained a full section on pairing Claude with OpenAI's Codex: per-model routing scores, a reasoning-effort ladder, and a hard safety rule that the `gpt-5.6-sol` model is review-only. The full guide lives in `claude/instructions/model-delegation.md` (new).
- **A guard rule enforces that safety rule mechanically.** New `claude/hookify-rules/` directory with a hookify rule that blocks any Codex rescue/exec run that doesn't explicitly pin an allowed model, plus a test script covering all eight allow/deny cases.
- **Four new skills:** `discord-post` (draft community announcements), `html-doc` (standalone HTML reports and explainers), `imageai-cli` (drive the ImageAI command-line tool for images, video, and layouts), and `model-registry` (keep LLM model IDs current from a published registry).

## 2026-07-14

- **New secrets guard for the conversation transcript.** `claude/tools/config-secrets-guard.py` is a hook that stops any shell command or file read that would print a secret-bearing config file (`.env`, `config*.yaml`) into the chat, where it could be logged or shared. A companion `safe-config-reader.py` shows a config file's structure with all values masked, so debugging is still possible without exposing secrets. `settings.json` wires the guard in.
- **The same guard now covers other AI CLIs.** It speaks the Codex hook protocol, has an `--agy` mode for the Antigravity CLI, and ships a TypeScript port (`config-secrets-guard.pi.ts`) for Pi. The sync skill distributes all of it.
- **update-code-map rewritten around a real symbol extractor.** Line numbers in generated CodeMaps now come from a deterministic Python script (`references/extract_symbols.py`) instead of being estimated by the model — so they're actually correct.
- **New instruction file:** `file-dispositions.md`, a template for recording standing decisions about stray working-tree files so the same question never gets asked twice.

## 2026-07-10

- **The big house-rules split.** The global instructions were reorganized so that one shared file — `config/agents/AGENTS.md` — holds the tool-agnostic rules (security, git hygiene, work procedures, conventions) for *every* AI coding CLI, and `claude/CLAUDE.md` shrank to a thin file that imports it and adds only Claude-Code-specific extras. The installer places both files.
- **Status line rewritten.** Now shows worktree badges, rate-limit badges (5-hour and 7-day, for Claude.ai subscribers), a PR badge color-coded by review state, and the session name.
- **Two new repo commands:** `/feature-team` (run a multi-task plan with an implement→review loop across a ladder of models) and `/rename-code` (safe cross-codebase symbol rename with verification).
- **New skill:** `update-hermes`, a backup-first updater for a Hermes Agent install — it backs up local source customizations that the built-in updater would silently skip.
- **Plugin list refreshed** (19 plugins added to the mirror) and the project-documenter skill gained a disclosure/leak-check phase.

## 2026-06-19 – 2026-06-21

- **New skill and command: `unify-agents-md`.** Restructures any project's (or the whole machine's) AI-agent instruction files so `AGENTS.md` is the single canonical guide that Claude Code, Codex, Copilot, Gemini, and Pi all follow, with `CLAUDE.md`/`GEMINI.md` reduced to thin pointers.
- **The sync skill learned to sync the shared house rules too**, treating `GEMINI.md` as a first-class per-CLI instruction file, and was sanitized for public consumption.

## 2026-06-18

- **New skill: `disk-doctor`** — disk cleanup and install hygiene, built test-first over ~20 commits. It scans home/dev/cache locations, proposes a plan, and only ever deletes through an audited "safe-trash" helper: every removal is manifest-logged first, protected system paths are hard-denied, and a one-command undo restores any run. Ships rule packs for Linux, macOS, and Windows, with design docs and the implementation plan in `Docs/plans/`.

## 2026-06-12

- **Beginner-friendly HTML install guide** (`Docs/install-guide.html`) — a visual walkthrough with a copy button on every command, linked from the README.
- Design spec added for a plan-aware installer (Pro/Max profiles).

## 2026-06-10

- **Status line gained live messaging indicators** showing when a Discord or Telegram session is paired.
- Config refreshed from the live machine (sanitized), and a project-local skill was excluded from the repo since it lives in its own project.

## 2026-04-22

- **Seven new skills** pulled in from the live config: `graphify`, `project-documenter`, `technical-documenter`, `raginclude-generator`, `doc-all-projects`, `yt-transcript`, and `cl-project-init` (a sanitized company-specific example).
- **README gained the Platform section** — the config targets Linux/WSL, with a ready-to-paste prompt for converting it to native Windows — and the `cl-*` prefix was documented as marking sanitized company-specific templates.
- Settings, MCP servers (chrome-devtools added), and the status line script all refreshed. All company names, credentials, and personal paths stripped or replaced with placeholders.

## 2026-02-09 – 2026-03-01

- **Initial public release**: a sanitized mirror of a real `~/.claude/` setup — six custom agents, the first skills, output styles, instructions, settings, and the CodeMap spec.
- Added the `install-claude-config` skill (diff-and-ask installer), the `sync-claude-config` skill (sanitizing reverse sync), and `Docs/SETUP_GUIDE.md`.
- Everything was reorganized under a `claude/` subdirectory so the repo maps cleanly onto `~/.claude/`, clone URLs were fixed, unused MCP entries removed, and the README expanded with detailed installation options.

## [0.5.0] - 2026-08-23

### Added
- agent-config-sync: a `plugin_removed` classification. The scanner now reports a plugin that WSL removed as its own item class, in the schema, the report, and the merge plan.
- agent-config-sync: PowerShell renderer tests (`test_render_ps1.py`). Windows-side plugin actions render as a reviewable `.ps1` script.
- New repo records synced from the live machine: `claude/commands/` (six slash-command pointers), the `github-stacked-prs` skill, and `agents/skills/rag-blueprint/` (NVIDIA's Apache-2.0 RAG Blueprint skill, upstream copy).

### Changed
- agent-config-sync: the house-rules family (AGENTS.md, CLAUDE.md, instructions, per-CLI mirrors) now keeps its faithful baseline under the gitignored `baseline/` directory. The public tree keeps only sanitized copies, owned by `/publish-claude-config`. This ends the permanent-conflict noise on every scan.
- agent-config-sync: ephemeral tool caches (pytest, Copilot session state, Codex visualizations) and the three-platform `yt-transcript` copies are excluded from scans.
- `claude/settings.json` example refreshed from the live config: current plugin roster after 13 approved removals, the config-secrets-guard hook, canonical key order. The machine-personal `model` key stays out of the public example.
- version-manager: the dirty-repo check ignores untracked files inside submodules.

### Fixed
- agent-config-sync: the Windows `.ps1` script emitted `claude plugin enable` for both directions of an enabled mismatch. The record's desired state now decides the verb, so a plugin the record wants disabled gets `claude plugin disable`.

### Removed
- Five retired agents: `documentation-specialist`, `performance-optimizer`, `research-assistant`, `software-engineer`, `test-generator`. The README trees now match the current roster.

## [0.4.1] - 2026-08-11

- **The config merge tool could not apply most of what it reported.** `merge.py` resolved a *tree* item — anything under `claude/agents/`, `claude/skills/`, `claude/instructions/`, and the other directory-shaped entries — to the directory that holds the file instead of the file itself. The dry run named the directory, so an approval covered a path that would never be written, and the apply then crashed on it. 128 of the 340 items a scan finds here are tree items, so this was most of the tool's real work. Tree items now resolve to the file the item id names, and the plan carries the source path it will read, so the dry run and the apply can no longer disagree.
- **A TOML field merge wrote a JSON document into a `.toml` file.** Approving a field of `~/.codex/config.toml` would have replaced it with JSON — and the corruption was silent, because the next scan compares the two sides in a normalized form and reports them as matching. Python 3.12 has a TOML reader and no TOML writer, so the tool now refuses a TOML field merge and says to edit the file by hand. `Docs/agent-config-sync.md` gained a **Known limitations** section recording that refusal along with the other three things a report can show but the tool will not apply — deletions, a deleted JSON field, and conflicts.
- **A malformed file was listed twice in the drift report.** One unreadable file produced two bullets under a heading that counted it once. Drift items are now the single source of truth, and read failures that belong to no item are listed separately and explicitly not counted.
- **The drift-report skill claimed the merge tool did not exist.** Both `agent-config-report` and the operator guide still said `merge.py` "does not exist yet" and would land in a later change, months after it shipped — so the reporting skill refused to point at an installed tool. The rule that the report skill never applies anything stays; it now hands off to `agent-config-merge` for the reason that rule exists.
- **The report analyzer could not read Claude's actual output.** `extract_json` did not handle the real `claude -p --output-format json` envelope, so every model-backed report fell back to the deterministic renderer. Also sanitized two real identifiers that had been captured in the test fixture recording that envelope.
- Added a Discord announcement draft for the `getting-started` skill, written back on 2026-08-06 and left untracked since.

## [0.4.0] - 2026-08-11

- **New: WSL-authoritative agent config sync.** A report-first pipeline that
  keeps agent configuration aligned across WSL, this repository, and a Windows
  desktop without ever applying a change unattended. A deterministic scanner
  (`tools/agent-config-sync/scan.py`) reads only what `config/agent-sync.toml`
  declares, normalizes away cosmetic differences (line endings, JSON key order,
  `/home/leland` vs `C:\Users\...`), and emits a drift document that carries no
  secret values — denied keys are represented by a pointer, a reason code, a
  type, and a hash. When there is no drift, no model runs at all. When there is,
  a bounded `claude -p` call supplies judgment only, and a deterministic renderer
  writes the Markdown report, so a malformed model response can never replace the
  last good one. Applying is a separate approved step: `merge.py` acts only on
  item ids you name, rejects a report whose files moved since the scan, backs up
  every target, and restores. Plugin code is never copied between environments —
  a newer native build is preserved unless you pin it, and plugin commands are
  printed for you to run rather than executed. Two skills drive it:
  `agent-config-report` and `agent-config-merge`. Operator guide:
  `Docs/agent-config-sync.md`.

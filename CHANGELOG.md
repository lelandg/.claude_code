# Changelog

A plain-English history of what changed in this repository and why. Newest first.
(Dates match the git history; run `git log --oneline` for the commit-level detail.)

## [0.9.0] - 2026-10-31

### Security
- **Two identity leaks removed from files this repo was already publishing.**
  The author's private Windows account name appeared 19 times across two
  `Docs/plans/` design docs, always in a home path — and always on lines that
  had already tokenized the Linux side as `/home/user`. That asymmetry is the
  tell: the publish sweep tokenizes one home and not the other, and its pattern
  list carries the author's email and his teammates' handles but neither his
  Windows account name nor their real names. A teammate's real full name was in
  a third doc's `Origin:` line, in a repo whose contact table deliberately
  replaces that row with a placeholder. Both are now placeholders.
- **The config secrets guard had thirteen bypass classes.** Four rounds of
  cross-provider review found them, all present in the config this mirror was
  published from. The ones worth knowing about: an arbitrary `--query` treated
  as proof of redaction when a whole-object projection returns the values
  anyway; a projection accepted on its *shape*, which let
  `app.basicAuthCredentials` through — base64 basic-auth credentials, perfectly
  dotted, no `environment` in the name; the Amplify *list* forms, which carry
  every app's `environmentVariables` and `basicAuthCredentials` and so leak
  strictly more than the `get` forms the guard was named for; a global flag
  before the subcommand or the service (`stripe --live charges create`,
  `aws --region … amplify get-app`); one safe flag vouching for every call in a
  pipeline; `--debug`, which prints the unfiltered response body before the
  projection applies; a glob that selects protected files without naming one; a
  newline not counting as a shell separator; and case-sensitive matching on
  case-insensitive PowerShell command names.
- **Two of those checks were the wrong shape, not merely incomplete**, which is
  why the rounds kept finding more. Both are now default-deny: projections are
  an **allowlist** of named fields rather than a denylist of bad-looking ones,
  and glob selectors are **structural** — any wildcard over the YAML or dotenv
  families blocks, because the protected families are infinite and a probe list
  is not.
- **`claude/tools/test-config-secrets-guard.py`** — 88 cases, one per bypass
  class, with the forbidden strings assembled from fragments so the file does
  not trip the guard that reads it. One case had asserted that the Amplify list
  form was *fine*: a bypass written down as correct behaviour, which is worse
  than no test because it looks like coverage.

### Changed
- **Rule 4 reverses direction.** Code still reaches `main` through a pull
  request, but a commit whose *every* path is non-functional may be committed
  straight to `main` — prose and images under `Docs/`, `Plans/`, `Notes/`,
  `README*`, `CHANGELOG*`, `LICENSE*`, comment-only source edits, and the
  agent-instruction files themselves. A mixed commit is still a PR, and so is
  anything a machine executes, schedules, or serves even when it reads like
  prose. This replaces the blanket "everything reaches `main` through a PR"
  rule v0.8.0 introduced, so the v0.8.0 entry below is history, not policy.
- **Including the rule files in that allowance carries an obligation.** A
  contradiction *between* two instruction files is the one defect class a
  diff-scoped reviewer cannot see, so when a rule changes on `main`, every copy
  of it moves in the same commit. If you cannot find all the copies, it is a
  PR. Grep before you commit.
- **Rule 4 now states its own precondition.** It is safe only because something
  preventive still runs on a direct commit, and this repo ships no pre-commit
  hook and no CI — so a stranger adopting the rule got the PR bypass with no
  gate at all while the prose told them one existed. No hook, no allowance.
- **Branch protection, honestly described.** v0.8.0 said to protect `main` with
  no bypass actors. If you grant one, know what you bought: a bypass is granted
  to a *role*, and GitHub cannot scope one by path, so the same grant also stops
  your security checks from gating any push by that role. They still run and
  fail visibly afterwards — detection, not prevention. Check
  `gh api repos/<owner>/<repo>/rulesets` instead of assuming.
- **Secret scanning fails closed.** A finding blocks with nothing to pass it,
  and a scan you cannot trust — missing binary, errored run — blocks too; only
  *that* case gets a one-commit override. Run `gitleaks` with `--exit-code 3`
  so 0 / 3 / anything-else are unambiguous, and make every switch in the hook
  enable on the exact value `1`, so a `=false` cannot turn one on by
  truthiness. The reasoning is written down now: a local hook is the only
  *preventive* gate, server-side scanning is *detective*, and once a bypass
  exists on the default branch the hook is the only gate left.
- **Remediation has a deadline, and it is today.** A dependency advisory with an
  available fix is remediated in the session that found it — the same branch
  when the PR already touches that manifest, otherwise its own PR, opened and
  merged the same day. This retires the 7-day window v0.8.0 set.
- **Dependency findings and SAST findings are different work.** A dependency
  advisory has a deterministic fix — a version — so it is applied, not debated.
  A code-scanning finding's "fix" is a design decision with a real
  false-positive rate, so it is *triaged* the same day instead: fixed now when
  contained, otherwise a recorded verdict with its reasoning. This release
  takes its own advice — `grep_is_blocked` now carries a docstring explaining
  why an unrestricted content search is a known, accepted gap rather than a
  patch, since closing it would block most of what Grep is for, and a guard
  that blocks ordinary work gets switched off.
- **The PR reviewer is per-repo, not assumed.** Two properties decide which one
  you gate on, and they differ by vendor: whether it re-reviews a push (some
  review on open only, so added commits go unreviewed with the check simply
  *missing*), and whether a passing check means "no findings" (usually not —
  findings arrive as inline comments while the summary stays empty, and a green
  check can also mean the review was rate-limited or skipped). The gate is the
  check reporting **on the head you are merging** *and* the comments read. If
  the ruleset does not require those checks, waiting on them is your rule
  rather than enforcement — which is why it has to be written down.
  `claude/instructions/pr-review-automation.md` is now explicitly scoped to the
  Claude Code GitHub App, since its autofix procedure does not transfer.
- **The merge gate** adds one condition: no dependency advisory with an
  available fix left open against the code the branch ships.

### Fixed
- **The version bump was ordered three different ways** across `AGENTS.md`'s two
  workflow paths, its versioning section, `pr-review-automation.md`, the
  `version-manager` skill and the `feature-team` command. v0.8.0 introduced
  bump-last and fixed one of them, so an agent following the skill the rule
  names as authoritative produced exactly the stale bump the rule exists to
  prevent. All of them now cut it immediately before the merge.
- **`feature-team.md`** — the one command that encodes the end-to-end finishing
  sequence — skipped the pre-PR cross-provider review `AGENTS.md` makes
  unconditional, and hardcoded `npx eslint` / `npx tsc` / Prisma as *the* task
  gate in a config whose own contribution guide asks for stack-neutral agents.
  Its two copies had also diverged in content; they are identical again.
- **`Docs/SETUP_GUIDE.md`** advertised 6 agents (1 ships), 5 instructions (10),
  21 skills (26) and an 8-case test harness (10 cases), and still tabled the
  five agents retired in August 2026 along with their files.
- **`README.md`** called `CLAUDE.md` a ~50-line pointer file; it is ~100. Its
  tree omitted two shipped skills (`getting-started`, `agent-config-sync`), and
  it claimed every case under the guard suite's `BYPASSES` marker was a hole,
  when some are the false positives and negative controls the fixes must not
  break.
- **The operative instruction files a stranger installs** still named a person
  they will never meet (`feature-team`, `agent-config-sync`,
  `github-stacked-prs`, `agent-sync.toml`). Deliberate attribution is
  untouched: the marketplace author, the README credit, the install-guide
  byline, the catalog title, and the `Docs/plans/` design docs, which are
  authored historical artifacts with an author line.

### Added
- **The config secrets guard covers four categories, not one.** Beyond
  config-file reads it blocks bare environment dumps, cloud calls that return
  secret values, and live-money CLI mutations — each with its own
  human-approved escape hatch appended to the command. It also speaks the Codex
  `exec_command`/argv shapes and Claude Code's PowerShell tool, and
  `process.env.X` no longer false-matches as a dotenv file. The hatches are
  human-only by design, and that matters more than it sounds: the guard matches
  on command text, so documentation *about* a blocked call trips the same wire
  as the call itself.
- **No Qt, except PySide** joins the misc rules — a stack preference that had
  been in the live config since 2026-09-12 and was never ported.

## [0.8.1] - 2026-10-26

### Removed
- **Simplified Technical English and the output-formatting bullets.** These
  rules were removed from every live copy on 2026-09-25. The 2026-09-26 sync
  dropped the matching `CLAUDE.md` section but missed this one in
  `config/agents/AGENTS.md`, which now matches live: a "Prompt formatting"
  section holding only the XML-tags rule.

### Fixed
- **The changelog reads newest-first again.** `version-manager` inserts each
  release above the first versioned heading, which sat under the older
  date-headed entries, so v0.7.0 and v0.8.0 landed at the bottom of the file.
  The dated entries (2026-02-09 to 2026-08-06) now follow the versioned ones;
  every versioned entry is newer, and no line was edited, only moved.

## [0.8.0] - 2026-10-26

### Changed
- **Security now outranks velocity.** `config/agents/AGENTS.md` opens its security
  section with a precedence rule: when any rule would delay removing a known
  vulnerability, the vulnerability goes first. The minimum-package-age rule is
  rebuilt around it — a reported vulnerability with a fixed version is patched
  immediately, taking the lowest version that clears the advisory, and the 7-day
  floor applies only when nothing is vulnerable.
- **New "Dependency, code, and secret scanning" section.** Free scanners
  (`npm audit`, `osv-scanner`, `pip-audit`, `gitleaks`) run on every commit and
  PR; Dependabot alerts — not the Dependabot PR list — are the source of truth;
  metered Snyk runs only where it adds something. A high or critical finding with
  a fix available gets its own remediation PR within 7 days.
- **Shipping rules.** Everything reaches `main` through a PR (the old
  small-changes-straight-to-main rule is retired); a new "Shipping autonomy"
  section lets green gates authorize the merge; the version bump is the last
  commit before merge, and a version tag another branch holds is moved aside,
  never deleted. `claude/instructions/pr-review-automation.md` now defers to
  that section instead of ending with "do not merge unless asked", so the
  procedure no longer contradicts the policy that points to it.
- **System dependencies** split into machine scope (the user runs it) and user
  scope (the agent may run it when the tool is free and clears the age floor).
- **Version picks follow the longest security-support window**, replacing the
  even/odd heuristic, which generalised a Node-only, pre-Node-27 fact to all
  software. `claude/instructions/environment.md` carries the verified Node and
  Python EOL dates.
- `claude/instructions/package-min-age.md` is rewritten: why the age floor and
  scanners defend against different threats, a provenance check that replaces
  the age check when a security fix overrides the floor, and where the npm floor
  does not reach (`npm ci` ignores it). It also tells you to verify the floor is
  actually configured, and warns that a Node.js installer can silently downgrade
  npm below the version that supports it.

### Fixed
- `agent-config-sync` review fixes that merged with PR #2 after v0.7.0 was cut,
  released here for the first time. `diff` no longer prints environment values
  from `.claude/settings.json`. An apply that would mass-delete one side now
  refuses unless `--allow-deletes`. `--take` with a path that matches nothing is
  an error, not a silent no-op. Orphaned derived copies are reported instead of
  passing as ok, a failed atomic replace cleans up its temp file, and malformed
  scope entries exit with code 20 instead of a traceback.
- The README's size claim for `AGENTS.md` said ~2,500 tokens; it was already
  ~3,500 and is now ~6,000. The figure is corrected.
- Three places still described the rules this release retires, in the live
  config as well as here: the Versioning section required a bump on every PR
  while rule 4 exempts docs-only PRs (the exception is now stated in both);
  `github-stacked-prs` still sent small changes straight to `main`; and step 1
  of `pr-review-automation.md` still bumped first and skipped the Codex review.
- `package-min-age.md` cited `npm pack` as ignoring `min-release-age-exclude`;
  npm 11.19.0 fixed that (npm/cli#9811). The exclude itself arrived in 11.17.0
  (npm/cli#9534), now cited.

## [0.7.0] - 2026-10-25

### Changed
- **Breaking:** `tools/agent-config-sync/` is now one script, `sync.py`. It replaces
  the WSL-authoritative three-layer scanner and merger (about 4,000 lines and 279
  tests). It runs a two-way, three-way sync of agent instruction files between the
  WSL and Windows homes. A change on one side is copied to the other side. A
  change on both sides is a conflict that you resolve with `--take`.
- `config/agent-sync.toml` now uses schema 2. Skills, plugins and agents are out of
  scope: Claude Code syncs skills and plugins itself.
- The `agent-config-sync` skill replaces `agent-config-report` and
  `agent-config-merge`.

### Added
- The per-CLI `AGENTS.md` copies (Codex, Copilot, Gemini) are regenerated from the
  canonical file. A WSL symlink is never written. The script detects WSL symlinks
  seen from Windows (`IO_REPARSE_TAG_LX_SYMLINK`) as links.
- Report-only checks for `settings.json` and the Codex config. The report names
  keys only and never prints values.
- The script runs from PowerShell or WSL with the standard library only. A check
  takes seconds (the old scan took 22 minutes).

## [0.6.3] - 2026-09-26

### Changed
- `config/agent-sync.toml` now sets `wsl_home = "~"` instead of a hardcoded home directory. The tool expands it at load time, so on a fresh machine the manifest works without editing.

### Fixed
- Replaced hardcoded personal home-directory paths in the agent-config-sync docs, design and plan documents, code comments, test fixtures, and the `agent-config-merge` skill. They now use `~` or `/home/user`.

## [0.6.2] - 2026-09-26

### Removed
- The `## Output` section of `claude/CLAUDE.md` ("use AskUserQuestion for non-visual options"). It was dropped from the live config, so the mirror no longer carries it.

## [0.6.1] - 2026-09-26

### Changed
- `AGENTS.md` working procedures: agents keep going on steps that don't need the user's input, put status notes in the same message as the next action, and stop to ask only when blocked or before destructive actions (deleting data, force-pushing, changing anything outside the repo).
- `AGENTS.md` branching rule 1 now names `origin/master` as well as `origin/main` as the base for feature branches.

### Fixed
- Added a `.snyk` exclude for `claude/tools/config-secrets-guard.pi.ts`. Snyk Code read its secret-filename regex as a hardcoded secret, and the resulting false positive blocked every commit.

## [0.6.0] - 2026-09-22

### Added
- `claude/instructions/pr-review-automation.md`: the GitHub App PR review and autofix inspection procedure, referenced from the house rules.
- House rules: site UI verification for every site, an `AI-Model` attribution trailer for commits and PRs, "a local pass is not deployment", and a missing-script lookup rule across Windows and WSL.
- `github-issues.md`: generic opt-out marker and `skip-auto-fix` conventions for automated investigation and review pipelines.
- `environment.md`: checkout-scoped `safe.directory` override for Windows dubious-ownership errors.

### Changed
- Model selection: `gpt-6-astra` at `high` is the standing Codex default, preferred over Terra for every task including reviews, and allowed on the write-capable rescue path on a committed tree. `model-delegation.md` is rewritten and gains the Codex auth-expiry procedure.
- The PR-review rule replaces the mandatory local review gate when the Claude Code GitHub App is installed on the repo.
- The Sol review-only rule moves from the shared `AGENTS.md` to `CLAUDE.md`, because it governs how Claude Code invokes the codex plugin.
- The hookify Codex guard now blocks Sol and the bare `gpt-5.6` alias on the rescue and exec paths instead of requiring a Terra or Luna pin. Its test harness locates the installed plugin directory and covers ten cases.
- agent-config-sync: the manifest excludes Codex worktrees and the claude.ai synced-skills bundle, which removed 1735 spurious drift items and a 30-minute scan. The operator guide and report skill no longer describe a stale-lock case that cannot occur.

## [0.5.1] - 2026-08-23

### Added
- House rules (`config/agents/AGENTS.md`): the Simplified Technical English output rules, the review-BEFORE-push sequence, and a two-runtimes note for WSL + native Windows setups.
- version-manager: `.csproj` support. The tool reads `<Version>` as canonical, keeps `<AssemblyVersion>`/`<FileVersion>` in step, and skips `obj/`/`bin/` during scans.
- feature-team command: Verification tiers per task and a Finishing phase that owns the full build, the final review, and the version bump.

### Changed
- House rules: the multi-task build gate is now precise — scoped lint + project typecheck + task tests per task; the full build runs once, in the branch-finish pass.
- `claude/CLAUDE.md`: `/codex:adversarial-review` is restricted to the user; date commands now cover Windows PowerShell.

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
  `/home/user` vs `C:\Users\...`), and emits a drift document that carries no
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

---

*Entries below predate versioning (v0.4.0 was the first tagged release) and
are headed by date rather than version.*

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

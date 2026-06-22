---
name: sync-claude-config
description: Sync Claude Code config (CLAUDE.md, agents, skills, commands, instructions, settings, plugins, CC version) AND the shared cross-CLI house-rules — canonical ~/.config/agents/AGENTS.md plus the per-CLI instruction files that @import it (CLAUDE.md, GEMINI.md) and Codex/Copilot/Pi wiring — from THIS machine to any SSH-reachable host so every AI coding CLI works the same there. Discovers targets from ~/.ssh/config. Use on /sync-claude-config [host], or when asked to "sync claude config to <host>", "mirror my agents/skills to <machine>", "make Claude Code (or my agents) work the same on <host>". Push-only (local → remote); never copies credentials or machine state.
---

# Sync Claude Code Config to a Remote Host

Push this machine's Claude Code configuration to an SSH-reachable host, **merging**
(never clobbering) anything remote-specific.

## 0. Pick the target host

If no host argument was given, discover candidates and ask:

```bash
# Host aliases from ~/.ssh/config, following Include directives (skip wildcards):
awk 'tolower($1)=="include" {print $2}' ~/.ssh/config 2>/dev/null | while read -r g; do eval ls $g 2>/dev/null; done
awk 'tolower($1)=="host" {for(i=2;i<=NF;i++) if ($i !~ /[*?]/) print $i}' ~/.ssh/config $(awk 'tolower($1)=="include" {print $2}' ~/.ssh/config 2>/dev/null | while read -r g; do eval ls $g 2>/dev/null; done) 2>/dev/null | sort -u
```

Also check `~/.justfile` for ssh recipes (`j ssh` etc.) if nothing matches.
Present the list with AskUserQuestion. Any host works as long as `ssh <host>` succeeds —
adding a new machine is just a new ~/.ssh/config entry + key, no skill changes needed.

## 1. Preflight (read-only)

```bash
ssh <host> 'whoami; hostname; uname -s; ls ~/.claude 2>/dev/null | head -40'
ssh <host> 'bash -lc "claude --version"'   # MUST use bash -lc: claude is often not in non-login PATH
claude --version                            # local, for comparison
```

- No `~/.claude` on remote → fresh install case: confirm Claude Code is installed first
  (`bash -lc "which claude"`); if absent, stop and give the user the install command.
- Inventory what is REMOTE-SPECIFIC so it survives the sync (see §2 table).
- Check remote `~/.claude/agents/`, `skills/`, `commands/` for items that don't exist
  locally — these are preserved, never deleted.

## 2. What syncs vs. what never syncs

| Item | Action |
|------|--------|
| `~/.config/agents/AGENTS.md` | **MERGE/adapt by hand** (§4b) — canonical house rules every CLI reads via `@import` |
| `CLAUDE.md` & `GEMINI.md` | **MERGE by hand, never copy** (§4) — each = `@import` of AGENTS.md (line 1) + tool-specific extras (Claude triggers / Gemini memories) |
| Other-CLI wiring (Codex/Copilot/Pi) | Symlink/append on the remote to point at the shared file (§4b); guarded, never clobber |
| `instructions/` | `rsync -a` (full overwrite — they're reference docs) |
| `agents/` | `rsync -aL --delete --exclude .git --exclude .idea` — **`-L` is mandatory**: some local agents may be symlinks into a source repo; the remote needs materialized files. `--delete` mirrors archivals. |
| `skills/` | `rsync -a --exclude '*-workspace' --exclude '*.skill' --exclude '*.zip'` — **additive, NO --delete** (preserve remote-only skills) |
| `commands/` | Copy **portable ones only**. Read each command first: skip any that shell out to local-only tooling (e.g. commands that need an admin CLI or virtualenv present only on the dev machine). Never delete remote-only command dirs. |
| `settings.json` | **Programmatic merge, never replace** (§5) |
| Plugins/marketplaces | Reconcile via `claude plugin` CLI (§6) |
| Claude Code version | `bash -lc "claude update"` on remote to match local |
| **NEVER sync** | `.credentials.json`, `history.jsonl`, `projects/` (memory!), `sessions/`, `session-env/`, `file-history/`, `shell-snapshots/`, `tasks/`, `teams/`, `daemon/`, `jobs/`, `policy-limits.json`, `statusline-command.sh` (often host-customized), `my-projects.yaml` (local paths), security/ |

## 3. Backup first — always

```bash
ssh <host> 'mkdir -p ~/.claude/backups/sync-$(date +%Y%m%d) && cp ~/.claude/CLAUDE.md ~/.claude/settings.json ~/.claude/backups/sync-$(date +%Y%m%d)/ 2>/dev/null; cp -r ~/.claude/agents ~/.claude/backups/sync-$(date +%Y%m%d)/agents-bak 2>/dev/null; ls ~/.claude/backups/sync-$(date +%Y%m%d)/'
```

## 4. Per-CLI instruction-file merge — CLAUDE.md & GEMINI.md

Post-migration both `~/.claude/CLAUDE.md` and `~/.gemini/GEMINI.md` share one shape:
**line 1 is `@<remote-home>/.config/agents/AGENTS.md`** (absolute, the remote's home, no
indent) and everything below is **tool-specific extras only** — skill/agent triggers in
CLAUDE.md, "Gemini Added Memories" + Gemini specifics in GEMINI.md. The bulk
machine-agnostic merge happens once on the shared file (§4b); here you only reconcile
each tool's own section and fix its line-1 `@import` to the **remote's** home path.

Do this for **each** file. Fetch the remote copy (`scp <host>:~/.claude/CLAUDE.md /tmp/`,
`scp <host>:~/.gemini/GEMINI.md /tmp/`), diff against local, write a merged version to
/tmp, push it. Merge rules (same for both):

- Bring over machine-agnostic content for that tool: security/work-procedure/issue/label
  rules, plan-file rules, output formatting, skill/agent triggers, review-doc naming.
- KEEP the remote file's platform adaptations: project root (`~/code/` vs `/path/to/projects`),
  downloads location, venv conventions, sudo posture, platform/log-path lines.
- DROP local-machine-only sections for Linux remotes: WSL/PowerShell notes, Windows
  Chrome debugging, external screenshot symlinks, Windows log paths, local mount paths generally.
- ADAPT tooling references: if a section needs a tool the remote lacks (e.g. an admin CLI
  only on the dev machine), rewrite as "not installed on this host — run it from the dev
  machine instead"; never silently drop the safety rule it carries.

Edge cases:

- **Remote file missing:** start from local, apply DROP/ADAPT, prepend the line-1
  `@import`, ask for the remote project root if unknown.
- **GEMINI.md still in the old memories-only format** (no `@import` line — common; it
  predates the migration on most hosts, including this dev machine as of 2026-06-21):
  **prepend** `@<remote-home>/.config/agents/AGENTS.md` as a new line 1 and keep the
  existing memories below (after DROP/ADAPT). Never symlink GEMINI.md away — unlike
  Codex/Copilot it carries Gemini-only memory that must survive.
- **Local file not yet migrated:** if the local CLAUDE.md/GEMINI.md has no `@import`
  line, there are no canonical tool extras to push beyond the shared file — still ensure
  the remote file `@import`s AGENTS.md so that CLI reads the house rules, and preserve
  whatever extras the remote already has.

## 4b. Shared cross-CLI house rules (~/.config/agents/AGENTS.md + other CLIs)

Your global house rules now live in `~/.config/agents/AGENTS.md` — the
canonical file every CLI reads. `~/.claude/CLAUDE.md` `@import`s it; Codex,
Copilot, Gemini, and Pi point at it too. Sync this so **non-Claude** agents
behave the same on the remote. (See the `unify-agents-md` skill — esp. its
`references/tool-matrix.md` — for the per-tool paths, the `@import`-vs-symlink
reasoning, and the `agy` probe. Reuse that knowledge here.)

If the local machine has no `~/.config/agents/AGENTS.md` (older setup, everything
still in CLAUDE.md), skip this section — there's nothing shared to push yet.

1. **Merge/adapt the shared file** with the SAME DROP/ADAPT rules as §4 (it now
   carries the platform-specific bits — local mount paths, WSL/PowerShell, Windows
   Chrome, screenshot symlinks — that must be dropped/adapted for a Linux remote):
   - Back up + ensure dir on remote:
     `ssh <host> 'mkdir -p ~/.config/agents && cp -n ~/.config/agents/AGENTS.md ~/.config/agents/AGENTS.md.bak-$(date +%Y%m%d-%H%M%S) 2>/dev/null'`
   - Fetch remote copy (if any), diff vs local, write merged → push. Bring all
     machine-agnostic content; DROP local-only sections; ADAPT tool refs the
     remote lacks; KEEP the remote's own platform adaptations.
2. **Point the per-CLI files at it:** §4 ensures both CLAUDE.md and GEMINI.md `@import`
   the remote's shared path at line 1 (absolute, remote's home, no indent).
3. **Wire each CLI present on the remote.** Detect first:
   `ssh <host> 'bash -lc "for c in codex copilot gemini agy pi; do command -v $c && echo $c; done"'`.
   Guard every symlink (`[ -e <t> ] || [ -L <t> ]` before `ln -s`), never clobber,
   back up anything pre-existing:
   - **Codex:** `ln -s ~/.config/agents/AGENTS.md ~/.codex/AGENTS.md` (no import — concatenates).
   - **Copilot:** `ln -s ~/.config/agents/AGENTS.md ~/.copilot/copilot-instructions.md`.
   - **Gemini:** do NOT symlink — GEMINI.md keeps Gemini-only memories, so merge it by
     hand per §4 (`@import` line 1 + preserved extras).
   - **Pi:** append to remote `~/.bash_aliases` (idempotent — grep before adding;
     `bash -n` after): `pi(){ command pi --append-system-prompt "$HOME/.config/agents/AGENTS.md" "$@"; }`.
   - **agy:** probe before wiring (don't guess); report findings if unclear.
4. **Same NEVER-sync discipline:** push only instruction files / wiring for these
   CLIs — never their `auth.json`/credentials, `sessions/`, `history*`, or memory.

## 5. settings.json merge (fetch → merge locally → push)

Never overwrite. Python-merge with these rules:

- `env`: ADD missing feature flags (e.g. `CLAUDE_CODE_FORK_SUBAGENT`); PRESERVE remote
  telemetry/OTEL/host-specific vars.
- `model`, `effortLevel`, `alwaysThinkingEnabled`, `teammateMode`: set to local values.
- `enabledPlugins`: add local `true` entries missing on remote. Do NOT disable remote
  extras (hosts enable plugins deliberately). SKIP machine-bound plugins: LSPs without
  the toolchain (clangd/csharp on a worker box), obsidian-cli (vault elsewhere).
- `permissions.allow`: union local rules EXCEPT any containing `/mnt/`, `/home/<localuser>`,
  `.exe`, `powershell`, `wsl` — and **never copy write-capable cloud rules to an
  autonomous/worker host** (e.g. `aws amplify update-app`, `aws iam create-access-key`,
  `aws iam delete-access-key`). When unsure whether a rule is write-capable, leave it out.
- `extraKnownMarketplaces`: add missing ones. Directory-source marketplaces must be
  re-pointed at a remote-local clone (§6), never at a local-only path.
- Validate before push: `python3 -m json.tool`. Push, then re-validate on remote.

## 6. Plugins & marketplaces (on the remote, via `bash -lc`)

1. `claude plugin marketplace add <repo-or-path>` for each marketplace the remote lacks.
2. Directory-source marketplaces (e.g. a private marketplace → local plugins repo): the
   remote needs its own clone. Clone/pull the marketplace repo into
   `~/code/plugins`, recreate any gitignored plugin symlinks against the remote's clones
   (`ln -sfn ~/code/your-repo/.claude/plugins/your-plugin your-plugin`),
   copy over uncommitted marketplace.json wiring, then
   `claude plugin marketplace remove <name> && claude plugin marketplace add <path>`.
   If the remote repo clone is dirty, `git stash` around the pull; on conflict keep
   upstream and save the remote version as `<file>.{host}-local` — never discard.
3. `claude plugin install <plugin>@<marketplace>` for every locally-enabled plugin
   (marketplace remove can uninstall its plugins — reinstall those too).
4. Verify: `claude plugin list`.

Gotcha: compare plugin content with `diff`/content checks, not md5 — CRLF on Windows/WSL
working trees makes hashes lie.

## 7. Verify end-to-end

```bash
ssh <host> 'bash -lc "claude --version; cd ~ && claude -p \"Reply with exactly: CONFIG OK\" 2>&1 | tail -1"'
```

- `CONFIG OK` → done.
- `401 Invalid authentication credentials` → auth problem, NOT a sync failure. Check
  structure only (never cat values): does `.credentials.json` → `claudeAiOauth` have a
  non-empty `refreshToken`? Old `claude setup-token` credentials have none and die at
  their fixed expiry with no warning. Fix = run `/login` in an interactive
  session on that host (self-renewing refresh token; preferred over setup-token for
  hosts that run full Claude Code). Headless timers / scheduled services share this
  credential — flag that they're dark until re-auth.

## 8. Report

Write a summary to the current project's `Notes/` (check casing conventions):
what synced, what was skipped and why, dropped permission rules, **which non-Claude
CLIs were wired to the shared house-rules file** (and any — e.g. `agy` — left
pending a probe), repo housekeeping flags found along the way (unpushed commits,
diverged branches — flag, don't fix), backup location, and any ACTION REQUIRED
items (auth) with exact commands inline.

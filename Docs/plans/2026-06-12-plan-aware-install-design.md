# Plan-Aware Install — Design Spec

**Date**: 2026-06-12 15:31
**Status**: Approved design, pending implementation plan
**Author**: Leland Green + Claude (Fable 5)

## Problem

The repo's config is tuned for a heavy user (Max 20x / API): three agents pinned to
`model: opus`, `alwaysThinkingEnabled: true`, `effortLevel: high`, and ~45 enabled
plugins whose skill/MCP descriptions load into every session. A user on the $20 Pro
plan who installs this config as-is will exhaust their 5-hour usage window quickly —
or hit Opus availability limits outright.

## Goal

The install flow asks the installer which Claude plan they're on and what default
model their agents should use, then configures the installed files appropriately —
without changing anything for Max 20x / API users, and without disturbing the
existing diff-and-ask merge flow for re-installs.

## Non-Goals

- No changes to the `sync-claude-config` (reverse-direction) skill.
- No runtime plan detection — the user self-reports their plan.
- No new scripts or binaries; the install remains a purely agentic skill.
- The repo's checked-in config files stay authored for the full-power profile;
  profiles are applied at install time only.

## Design

### Components

1. **`claude/skills/install-claude-config/references/plan-profiles.md`** (new)
   Declarative per-plan profile tables (the single source of truth for what each
   plan changes). Follows the existing `references/` pattern.

2. **`claude/skills/install-claude-config/SKILL.md`** (modified)
   New **Step 2: Choose Plan Profile**, inserted after prerequisite validation and
   before file discovery. Subsequent steps renumber. Steps 3+ reference the chosen
   profile as a transform applied to the "repo version" of affected files.

3. **`.claude/commands/install-claude-config.md`** (modified)
   One-line mention that the workflow includes the plan-profile step.

4. **`README.md` + `Docs/install-guide.html`** (modified)
   Brief "the installer will ask which plan you're on" note in the install
   sections. The HTML guide targets beginners — exactly the $20 audience.

5. **`references/setup-guide-template.md`** (modified)
   The generated `SETUP_GUIDE.md` records which profile was applied and how to
   change it later.

### Step 2: Choose Plan Profile (new SKILL.md step)

Ask two questions via `AskUserQuestion`:

**Q1 — "Which Claude plan are you on?"**

| Option | Profile |
|--------|---------|
| Pro ($20/month) | `pro` |
| Max 5x ($100/month) | `max5` |
| Max 20x ($200/month) | `max20` |
| API / pay-as-you-go | `max20` (same profile) |

**Q2 — "Default model for your agents?"** — four options, plan-dependent, with
the plan-derived default listed first as "(Recommended)":

| Plan | Q2 options (first = recommended) |
|------|----------------------------------|
| `pro` | **sonnet**, haiku, opus, as authored |
| `max5` | **balanced** (opus agents → sonnet, code-reviewer keeps opus), sonnet, opus, as authored |
| `max20` | **as authored**, sonnet, opus, haiku |

Effects: `haiku`/`sonnet`/`opus` set every agent's `model:` frontmatter to that
value; `as authored` keeps each agent's frontmatter as shipped; `balanced` is the
`max5` profile row in the table below.

### Profile Definitions (content of plan-profiles.md)

| Setting | `pro` | `max5` | `max20` |
|---------|-------|--------|---------|
| Agent `model:` frontmatter | all → `sonnet` (Q2 may override) | as authored, but `opus` agents → `sonnet`; **code-reviewer keeps `opus`** (Q2 may override) | as authored (Q2 may override) |
| `alwaysThinkingEnabled` | `false` | `true` | `true` |
| `effortLevel` | `"medium"` | `"high"` | `"high"` |
| `enabledPlugins` | lean set below; all others written as `false` | full set; offer to trim | full set |

Agents shipped with `opus`: code-reviewer, software-engineer, performance-optimizer.
Agents shipped with `sonnet`: documentation-specialist, research-assistant,
test-generator.

**Lean plugin set (`pro`)** — these 12 stay `true`:

```
superpowers, commit-commands, code-review, pr-review-toolkit, context7,
github, frontend-design, claude-md-management, skill-creator, hookify,
claude-code-setup, example-skills
```

All other plugins from the repo's settings.json are written with value `false`
(not omitted) so they remain visible in settings.json and are one flip away from
enabling. Rationale recorded in plan-profiles.md: every enabled plugin loads its
skill and MCP descriptions into every session's context, making the plugin list
the single largest token lever for Pro users.

The `max5` profile keeps the full plugin set but the installer offers an optional
follow-up: "Want the lean plugin set anyway?" (default no).

### Mechanics: Transform Before Diff

The profile is applied as a transform layer to the **repo version** of affected
files *before* the existing Step "Compare and Present Diff Summary":

1. Agent files (`claude/agents/*.md`): rewrite the `model:` frontmatter line per
   the profile + Q2 answer. All other content untouched.
2. `settings.json`: adjust `alwaysThinkingEnabled`, `effortLevel`, and the
   `enabledPlugins` map per the profile.
3. Everything else in the manifest is unaffected.

Because the transform happens upstream of the diff, the existing flow — NEW /
CHANGED / IDENTICAL classification, per-file keep/merge/replace decisions, smart
merge for settings.json, timestamped backups — is unchanged. A re-running user
still gets asked before anything is overwritten.

Smart-merge note: when the user picks **Smart merge** for settings.json, the
profile-transformed repo version is the merge input, and the existing per-key
strategies apply on top (e.g. `enabledPlugins`: union of keys; keep user's
true/false for keys the user already has; add new keys with the profile's value).
The profile's three scalar keys (`alwaysThinkingEnabled`, `effortLevel`) follow
the existing "keep user's value" rule on smart merge — the profile only sets them
when installing fresh or when the user picks "Install repo version".

### Reporting

- The final install report names the applied profile and agent-model choice, e.g.
  `Profile: pro (agents → sonnet, thinking off, effort medium, 12 plugins)`.
- The generated `Docs/SETUP_GUIDE.md` gains a "Your plan profile" section: which
  profile was applied, and how to change things later — `/model` for the session
  model, re-running the install to switch profiles, or flipping individual
  plugins/keys in `~/.claude/settings.json`.

### Error / Edge Handling

- **User skips the questions** (declines AskUserQuestion): default to `max20`
  (as-shipped behavior — identical to today's install, so no surprise changes).
- **Unknown future agents** (files added to `claude/agents/` later): the transform
  rule is written generically — "rewrite the `model:` line per Q2" — not as a
  hardcoded agent list, except the code-reviewer carve-out in `max5`.
- **Agents without `model:` frontmatter**: leave untouched (they inherit the
  session model, which is already the cheap default).
- **Plugins added to the repo later**: the lean set is an allowlist; anything not
  on it gets `false` under `pro` automatically.

## Testing

Manual verification matrix (this is an agentic skill — no automated harness):

1. Fresh install, `pro` profile: confirm all six agents read `model: sonnet`,
   settings.json has thinking off / effort medium / exactly 12 plugins `true`.
2. Fresh install, `max20`: confirm output is byte-identical to today's install.
3. Re-install over a customized `~/.claude/`, `pro` + Smart merge: confirm user's
   existing plugin choices and scalar settings survive per the merge table.
4. Q2 override (`pro` + opus): confirm the override wins over the profile default.
5. Skip path: decline the questions, confirm `max20` behavior.

## Open Questions

None — plan tiers, Pro aggressiveness, and the derive-with-override flow were
decided 2026-06-12.

# WSL-Authoritative Agent Configuration Sync — Design

**Date:** 2026-08-08

**Status:** Approved (design); implementation plan to follow

**Author:** Codex (OpenAI), in collaboration with Leland Green

**Repository:** `lelandg/.claude_code` (Claude marketplace name: `lelandg-claude-config`)

## Purpose

Create a safe, review-first way to keep Claude Code, Codex, Copilot, Gemini/Antigravity,
and Pi configuration aligned across WSL and Windows desktop applications.

WSL is the operational authority for portable user intent. The `.claude_code` repository
is the sanitized, version-controlled record of that intent. Windows is a derived target
with a protected platform-specific overlay. A scheduled job detects drift and creates a
report; it never applies configuration changes automatically.

The primary analyzer is headless Claude Code through `claude -p`. Codex is used when it
has a concrete feature advantage or when an independent cross-provider review is useful,
including through the Claude `/codex` plugin. Scheduling alone is not a reason to prefer
Codex.

## Goals

- Make WSL the single authority for portable agent configuration.
- Preserve Windows/Desktop-only settings and integrations.
- Record portable WSL intent in this repository without committing secrets or machine
  state.
- Produce a durable, sanitized Markdown drift report suitable for handoff to Claude,
  `/codex`, Codex CLI, Copilot, or Pi.
- Keep scheduled operation report-only and safe to run unattended.
- Make an approved merge atomic, reversible, scoped, and verifiable.
- Reuse the policies already established by `sync-claude-config` and
  `unify-agents-md` instead of creating a competing synchronization model.

## Non-goals

- Fully automatic or bidirectional configuration merging.
- Copying complete `.claude`, `.codex`, or other agent directories.
- Synchronizing credentials, histories, sessions, memories, caches, or trust state.
- Making every tool support the same features.
- Downgrading a newer native plugin merely because another environment is older.
- Replacing native plugin managers with copied plugin runtime files.
- Requiring Codex, Copilot, or Pi for the nightly path.

## Authority model

There are three distinct layers:

1. **WSL live configuration — operational authority.** Portable user-authored intent is
   read from `/home/leland`.
2. **`.claude_code` — portable record and comparison baseline.** The repository stores
   sanitized, reviewable configuration suitable for version control and distribution.
3. **Windows configuration — derived target plus protected overlay.** Portable intent is
   reconciled into `C:\Users\aboog`, while Windows/Desktop-specific values remain locally
   owned.

The scanner performs a three-way comparison:

- WSL differs from the repository: portable intent needs publishing.
- The repository differs from Windows: Windows may need reconciliation.
- WSL and Windows both differ from the repository in the same portable field: report a
  conflict; do not choose a winner automatically.
- A Windows-owned field differs: record it as protected state, not actionable drift.
- There is no baseline: produce an initial inventory and classify uncertainty as a
  conflict rather than assuming ownership.

The repository does not become a second live authority. It is the last reviewed portable
record that makes independent changes and stale reports detectable.

## Paths

The implementation lives in the Windows checkout selected for this work:

```text
D:\Documents\Code\GitHub\.claude_code
```

When run from WSL, the same checkout is normally:

```text
/mnt/d/Documents/Code/GitHub/.claude_code
```

Authoritative WSL roots include:

```text
/home/leland/.config/agents
/home/leland/.agents
/home/leland/.claude
/home/leland/.codex
/home/leland/.copilot
/home/leland/.gemini
/home/leland/.pi
```

`/home/leland/agents` is not a configured root. Roots and targets are declared in one
manifest and may be overridden for fixtures or another machine; path literals are not
spread throughout the implementation.

The Windows target defaults to `/mnt/c/Users/aboog` when invoked from WSL. Report and
backup state is kept outside Git:

```text
~/.local/state/agent-config-sync/
├── latest-status.json
├── latest-report.md
├── reports/
└── backups/
```

Reports are retained by default. Automated deletion or retention pruning is not part of
the initial implementation.

## Repository structure

```text
.claude_code/
├── config/
│   ├── agents/AGENTS.md
│   └── agent-sync.toml
├── tools/
│   └── agent-config-sync/
│       ├── scan.py
│       ├── render.py
│       ├── schemas/
│       └── tests/
├── claude/
│   └── skills/
│       ├── agent-config-report/
│       └── agent-config-merge/
└── Docs/
    └── plans/
```

The scanner and renderer are provider-neutral deterministic tools. Claude skills supply
the preferred analysis and reviewed-application workflows. Existing
`sync-claude-config` and `unify-agents-md` remain responsible for their current host-sync
and instruction-wiring concerns; the new skills invoke or follow their policies rather
than duplicating incompatible rules.

## Ownership and merge policy

The manifest assigns every supported field or path one of four policies:

- **Portable authoritative:** WSL intent is the desired value.
- **Portable additive:** WSL additions and updates are candidates; deletions require
  explicit approval.
- **Platform overlay:** Windows owns the value; it is preserved and reported.
- **Excluded:** the value is not collected or synchronized.

| Configuration | Policy |
|---|---|
| `~/.config/agents/AGENTS.md` | Portable authoritative; copied to stable Windows-local instruction files |
| Claude `CLAUDE.md`, instructions, and portable agents | Portable authoritative |
| User-authored skills in `.claude`, `.codex`, and `.agents` | Portable additive; no unattended deletions |
| Claude slash commands | Portable additive when their dependencies and paths are portable |
| JSON/TOML settings | Semantic field-level merge according to manifest ownership |
| Plugin identities and marketplace declarations | Reconciled through each native manager |
| Plugin versions | Report differences; keep newer compatible native versions unless explicitly pinned |
| MCP server definitions | Merge portable structure; omit secret values and adapt executable paths |
| Hook policy | Portable where possible; scripts and trust decisions remain platform-aware |
| Copilot, Gemini/Antigravity, and Pi instructions | Sync through each tool's supported mechanism |
| Unknown content | Report metadata only until ownership is declared |

Windows/Desktop-owned state includes, at minimum:

- Codex Desktop and Windows sections.
- Windows project paths and trust mappings.
- Windows shell configuration.
- Windows-specific MCP executable paths and integrations.
- Native plugin runtime state.
- Machine-local hook approvals.
- Application preferences with no portable equivalent.

Symlinks used inside WSL are represented on Windows by stable local files or native
Windows-compatible links only when reliability has been demonstrated. Windows desktop
operation must not depend on the WSL distribution being mounted.

## Plugin handling

Plugin caches and downloaded plugin code are never copied. The scanner compares desired
plugin identities, marketplace identities, enabled/disabled state, declared pins, and
installed versions when exposed by native tooling.

The report classifies plugin differences as:

- Missing desired plugin.
- Extra native plugin.
- Enabled-state difference.
- Version difference with no pin.
- Explicit pin violation.
- Native-manager or platform incompatibility.

A newer compatible native version is preserved unless the portable configuration contains
an explicit pin. Installation, removal, enablement, and downgrade commands are proposed
separately and require approval. This avoids copying executable plugin code across the
WSL/Windows boundary and accommodates differences such as Windows receiving a newer
Superpowers build than WSL.

## Secret and state boundary

The scanner uses allowlist extraction. It does not ingest everything and attempt to
redact afterward.

Never collected or synchronized:

- Authentication files, tokens, API keys, passwords, or secret values.
- OAuth, keychain, and credential-helper state.
- Conversations, transcripts, histories, sessions, memories, and SQLite databases.
- Plugin caches, downloads, logs, telemetry state, and temporary files.
- Machine identifiers and volatile runtime state.
- Project trust and hook approval state unless a field is explicitly reclassified as
  portable.

For MCP definitions, environment-variable **names** may be recorded, but values may not.
Unknown fields that look sensitive are represented only by path, type, hash, and a
redacted warning. The scanner must not place a secret in an intermediate drift document,
model prompt, report, test snapshot, log, or exception message.

## Deterministic scan

`scan.py` performs the following without invoking a model:

1. Load and validate the ownership manifest.
2. Resolve the WSL source, repository baseline, and Windows target roots.
3. Acquire a process lock so cron runs cannot overlap.
4. Read allowlisted files and fields.
5. Normalize line endings, path syntax, JSON/TOML ordering, and other declared
   representation differences.
6. Calculate content fingerprints after normalization and secret exclusion.
7. Classify changes, conflicts, protected overlay state, plugin differences, and errors.
8. Emit a versioned sanitized drift document atomically.

If no actionable or review-worthy drift exists, the wrapper updates
`latest-status.json`, performs no model call, and exits successfully.

Malformed input produces a diagnostic containing the file and parse location but not its
contents. Scan errors leave the previous valid report untouched and return a distinct
nonzero exit code.

## Claude-first report generation

When drift exists, the scheduled wrapper invokes the explicit WSL Claude executable rather
than depending on cron's interactive shell or aliases. The primary analyzer is
`claude -p`.

The invocation:

- Uses normal Claude configuration so the relevant skills, plugins, and instructions are
  available; it does not use `--bare`.
- Grants only the read capabilities needed to inspect the sanitized drift and portable
  policy files.
- Does not grant mutation tools to the analyzer.
- Applies explicit turn, time, and spending limits.
- Requests structured output validated against a versioned schema.
- Writes model output to a temporary location for validation rather than allowing Claude
  to write the final report directly.

`render.py` validates the structured response and deterministically renders Markdown.
Only a valid result is atomically promoted to `latest-report.md` and the timestamped
`reports/` directory. Invalid or incomplete model output produces an error status and
cannot replace the previous valid report.

Codex is not invoked merely because the job is scheduled. The report recommends `/codex`
when a cross-provider review would materially help, such as an ambiguous semantic merge,
a Codex-specific setting, or a high-risk conflict. Copilot and Pi may be suggested as
additional reviewers but are not required by the nightly pipeline.

## Report format

Every Markdown report contains:

- Run identifier, timestamp, scanner version, manifest version, prompt version, and
  report-schema version.
- Source, repository, and Windows fingerprints.
- Executive summary and severity.
- Safe portable updates.
- Conflicts requiring judgment.
- WSL-only and Windows-only items.
- Protected Windows state.
- Plugin identity, enabled-state, pin, and version differences.
- MCP and hook portability warnings.
- Excluded or redacted paths with reason codes, never values.
- Recommended merge order.
- A ready-to-paste Claude handoff prompt.
- A `/codex` review prompt when independent review is warranted.
- Validation steps and restoration expectations.

Reports use stable item identifiers so approvals and follow-up discussion can refer to an
exact change without relying on prose matching.

## Reviewed application workflow

Report generation and application are separate operations. The nightly process cannot
apply changes.

When the user gives a report to Claude, the `agent-config-merge` skill:

1. Parses the report and selects only explicitly requested item identifiers.
2. Rescans affected paths and rejects stale fingerprints.
3. Separates repository publishing, Windows reconciliation, and native plugin-manager
   operations.
4. Explains the proposed changes and generates a dry-run patch.
5. Requests approval for the exact scope.
6. Creates timestamped backups of every target that may change.
7. Applies allowlisted changes atomically where the format permits.
8. Uses native managers for approved plugin operations; it never copies plugin caches.
9. Validates syntax, pointers, plugin state, and protected fields.
10. Rescans and reports remaining expected or unexpected drift.
11. Provides exact restoration instructions.

The workflow does not rewrite WSL live configuration. It may update the sanitized
repository record and derived Windows targets after approval.

If independent review is warranted, Claude may invoke or recommend `/codex` with the
sanitized conflict set. Codex recommendations are advisory and cannot expand the approved
scope. The user approves the final patch, not an agent-to-agent conversation.

## Backups and recovery

Each application run creates a backup directory keyed by the report/run identifier. The
backup includes original content, target path, content fingerprint, ownership class, and
the ordered restoration procedure. A failed application stops immediately and retains
both backups and diagnostics.

Recovery must be testable using fixture directories. No backup pruning occurs in the
initial implementation. Native plugin operations record the inverse action when the
manager supports one; otherwise the report clearly marks manual recovery requirements
before approval.

## Scheduling

The repository supplies a sample cron entry or wrapper, but the user owns installation of
the cron job. The wrapper:

- Uses absolute executable and repository paths.
- Establishes a minimal explicit environment.
- Acquires a lock.
- Runs the deterministic scanner first.
- Skips Claude when there is no drift.
- Invokes `claude -p` only for sanitized drift.
- Writes status and reports atomically.
- Returns distinct success, drift-reported, scan-failure, and model-failure states without
  treating ordinary drift as an infrastructure error.

The design does not assume that an interactive alias exposes Copilot or Pi to cron.
Provider alternatives require explicit executable paths and dedicated configuration.

## Testing

All scanner, renderer, merge-planning, and restoration tests operate on temporary fixture
trees. Tests must never read or modify the live user profiles.

Required cases:

1. No drift; Claude is not invoked.
2. Portable WSL addition.
3. Repository record awaiting Windows reconciliation.
4. Independent WSL and Windows edits relative to the repository.
5. Windows-only protected keys.
6. Additive user-authored skill changes and an attempted deletion.
7. Newer Windows plugin version without a pin.
8. Explicit plugin pin violation.
9. MCP definition containing inline secret values.
10. Malformed JSON and TOML.
11. WSL-to-Windows executable and path adaptation.
12. Unknown files and fields.
13. Stale report fingerprints.
14. Invalid, incomplete, or timed-out model output.
15. Interrupted atomic write.
16. Backup restoration.
17. Idempotence after an approved merge.

Golden fixtures verify normalized drift and rendered Markdown. A model stub verifies the
Claude wrapper and schema-validation path without network or subscription use. A live
Claude smoke test is opt-in.

## Acceptance criteria

- WSL remains the only live authority for portable user intent.
- The repository contains a sanitized, reviewable portable record.
- Report generation makes no live configuration changes.
- No secret value appears in drift data, prompts, reports, logs, exceptions, snapshots,
  or commits.
- No model is invoked when there is no drift.
- Windows-owned fields survive scans and approved merges unchanged.
- Plugin cache or downloaded executable code is never copied between environments.
- A newer compatible native plugin is not downgraded without an explicit pin and approval.
- Invalid analysis cannot replace the last valid report.
- Stale reports cannot be applied.
- Applying an approved change twice creates no further change.
- Every applied change has a verified restoration path.
- Claude is the default headless analyzer; Codex is recommended only for a concrete
  capability or independent-review advantage.

## Implementation sequence

1. Define the ownership manifest and sanitized drift schema.
2. Build normalization and allowlist extraction with secret-boundary tests.
3. Implement three-way comparison and plugin classification.
4. Implement the deterministic Markdown renderer and golden reports.
5. Add the bounded `claude -p` wrapper and structured response schema.
6. Add the report skill.
7. Add reviewed merge planning, backups, stale-report protection, and restoration tests.
8. Add the merge skill and `/codex` escalation guidance.
9. Add cron documentation and an opt-in live smoke test.

An implementation plan produced with `superpowers:writing-plans` follows this approved
design before production code is changed.

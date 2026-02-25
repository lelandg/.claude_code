---
name: sync-claude-config
description: Sync and sanitize Claude Code configuration from ~/.claude/ to the public repo. Use when the user asks to sync, merge, update, or refresh their public Claude Code config repo from their live setup. Triggers on requests like "sync my config", "update the repo from my settings", "merge my claude config", "refresh from ~/.claude", or "pull in my latest claude setup".
---

# Sync Claude Config

Merge files from `~/.claude/` into this public repo, sanitizing private information.

## Workflow

### 1. Locate Source and Target

```bash
SOURCE="$HOME/.claude"
TARGET="<repo-root>"   # detect from current working directory or user input
```

Confirm both paths with the user before proceeding.

### 2. Discover Syncable Files

Scan these directories/files in `~/.claude/`:

| Source Path | Target Path | Notes |
|-------------|-------------|-------|
| `CLAUDE.md` | `claude/CLAUDE.md` | Always sanitize |
| `CLAUDE_CodeMap.md` | `claude/CLAUDE_CodeMap.md` | Usually generic |
| `settings.json` | `claude/settings.json` | Sanitize permissions, paths |
| `mcp.json` | `claude/mcp.json` | Sanitize tokens |
| `statusline-command.sh` | `claude/statusline-command.sh` | Usually generic |
| `agentic_prompt_template.md` | `claude/agentic_prompt_template.md` | Usually generic |
| `agents/*.md` | `claude/agents/*.md` | Skip non-agent files |
| `agents/specs/*.md` | `claude/agents/specs/*.md` | Usually generic |
| `instructions/*.md` | `claude/instructions/*.md` | Sanitize infra details |
| `output-styles/*.md` | `claude/output-styles/*.md` | Usually generic |
| `skills/*/SKILL.md` | `claude/skills/*/SKILL.md` | Usually generic |
| `skills/*/references/*` | `claude/skills/*/references/*` | Usually generic |

**Skip entirely**: `.credentials.json`, `history.jsonl`, `stats-cache.json`, `security_warnings_state_*`, `session-env/`, `file-history/`, `debug/`, `cache/`, `shell-snapshots/`, `todos/`, `tasks/`, `plans/`, `paste-cache/`, `plugins/`, `projects/`, `telemetry/`, `statsig/`, `downloads/`, any `*:Zone.Identifier` files.

### 3. Compare and Identify Changes

For each syncable file:

1. Check if it exists in target repo
2. If it exists, diff source vs target to find meaningful changes
3. If it's new, flag as "NEW"
4. If content differs, flag as "CHANGED"

Present a summary table to the user:

```
Status  | File
--------|---------------------------
NEW     | agents/security-auditor.md
CHANGED | CLAUDE.md
CHANGED | settings.json
OK      | agents/code-reviewer.md
```

Ask user which files to sync. Default: all NEW and CHANGED files.

### 4. Copy and Sanitize

For each file being synced, copy from source then apply sanitization rules. See `references/sanitization-rules.md` for the full rule set.

**Sanitization priority:**
1. **Credentials/secrets** - API keys, tokens, passwords (CRITICAL)
2. **Personal identifiers** - Real names, email addresses, usernames
3. **Infrastructure** - AWS account IDs, hostnames, IP addresses, database endpoints
4. **Local paths** - Home directories, project-specific absolute paths
5. **Project-specific** - Product names, company names, internal tool references

**For each file:**
1. Read the source file
2. Apply all matching sanitization rules from the rules reference
3. Write to target path
4. Verify no private patterns remain with a grep check

### 5. Post-Sync Verification

After all files are synced, run a final scan:

```bash
# Scan for any remaining private info
grep -rn '<PATTERNS_FROM_RULES>' <TARGET>/
```

Report any findings and fix them before finishing.

### 6. Report

Present a summary:

```
Sync Complete
=============
Synced: N files (X new, Y updated)
Skipped: M files (unchanged)
Sanitized: P replacements made

Files synced:
  NEW     agents/security-auditor.md
  UPDATED CLAUDE.md (3 sanitizations)
  UPDATED settings.json (12 sanitizations)
```

## Special Handling

### settings.json
- Remove all project-specific `Bash(...)` permission entries (keep only generic ones like `Bash(ls:*)`, `Bash(git log:*)`, etc.)
- Remove `trustedWorkspaces` entries
- Remove `feedbackSurveyState`
- Replace home directory paths with `<YOUR_USER>` placeholder in `Read()` permissions
- Keep `enabledPlugins` as-is (no private info)
- Keep `env`, `statusLine`, `alwaysThinkingEnabled`, `installMethod`

### CLAUDE.md
- Replace personal names and contact info with placeholders
- Replace absolute project paths with generic examples
- Remove company-specific sections (or replace company name with placeholder)
- Keep all workflow rules, conventions, and best practices intact

### instructions/aws-*.md (or similar infra files)
- These are typically too specific to sanitize. Recommend excluding or heavily redacting.
- If user wants them included, replace ALL account IDs, hostnames, IPs, bucket names, function names, email addresses.

### mcp.json
- Token env vars using `${VAR_NAME}` syntax are already safe
- Remove any hardcoded tokens or credentials
- Keep server configurations as useful examples

# Agent config drift report — 2026-08-10T14-03-22Z-3f9a1c

- **Generated:** 2026-08-10T14:03:22+00:00
- **Versions:** scanner 1.0.0 · manifest 1 · drift schema 1 · template 1 · response schema 1
- **wsl:** `/home/leland` (`aaaaaaaaaaaa`)
- **repo:** `/repo` (`bbbbbbbbbbbb`)
- **windows:** `/mnt/c/Users/aboog` (`cccccccccccc`)
- **Severity:** conflict

> This report changes nothing. Application is a separate, approved operation — see the handoff prompt below.

## Executive summary

One portable update is safe; the settings model field needs a decision.

| Classification | Count |
|---|---|
| `conflict` | 1 |
| `plugin_version_differs` | 1 |
| `protected_overlay` | 1 |
| `publish_to_repo` | 1 |

## Safe portable updates (1)

- `agents-md` — **publish_to_repo** (portable_authoritative)  
  path: `.config/agents/AGENTS.md`  
  wsl `dddddddddddd` · repo `eeeeeeeeeeee` · windows `-`  
  WSL intent is ahead of the baseline; publish it.

## Conflicts requiring judgment (1)

> Plugin pin violations are severity `conflict` too, but render under **Plugin differences** below so every plugin item is in one place.

- `claude-settings:model` — **conflict** (portable_authoritative)  
  path: `.claude/settings.json`  
  wsl `-` · repo `-` · windows `-`  
  WSL and Windows changed independently of the baseline.
  
  > Both sides edited the model pin since the baseline.

## WSL-only and Windows-only items (0)

_None._

## Protected Windows state (1)

- `claude-settings:statusLine.command` — **protected_overlay** (platform_overlay)  
  path: `.claude/settings.json`  
  wsl `-` · repo `-` · windows `-`  
  Windows owns this value; preserved and reported only.

## Plugin differences (1)

- `claude-plugins:superpowers@claude-plugins-official#version` — **plugin_version_differs** (portable_authoritative)  
  path: `superpowers@claude-plugins-official`  
  wsl `-` · repo `-` · windows `-`  
  windows has 6.2.0, wsl has 6.1.0. The newer build is preserved; upgrade wsl.

## Portability warnings (0)

_None._

## Excluded and redacted

1 value redacted. Values are never recorded — only a pointer, a reason code, a type, and a truncated hash.

| Pointer | Reason | Type | Hash |
|---|---|---|---|
| `mcpServers.gh.env.GITHUB_TOKEN` | `secret_key_pattern` | str | `ffffffffffff` |

## Scan errors (0)

Read failures with no comparable item (not counted above):

- `.codex/config.toml`: invalid TOML at line 12

## Recommended merge order

1. `agents-md`
2. `claude-settings:model`

## Claude handoff prompt

```text
Use the agent-config-merge skill on report 2026-08-10T14-03-22Z-3f9a1c.
Apply only these item ids: <paste the ids you approve>
Dry-run first, show me the patch, then wait for my approval.
```

## Independent review (/codex)

An ambiguous semantic merge in a settings field.

```text
/codex:review --base HEAD
Focus on report 2026-08-10T14-03-22Z-3f9a1c: the conflict items above. Recommendations are advisory and cannot expand the approved scope.
```

## Validation and restoration

- Every applied change is backed up first, keyed by this run id.
- Re-run the scanner after applying; expected drift should be gone and nothing new should appear.
- Restore with: `python3 tools/agent-config-sync/merge.py restore --run-id 2026-08-10T14-03-22Z-3f9a1c`

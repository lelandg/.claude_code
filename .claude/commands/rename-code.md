---
description: Safely rename a symbol/string across the codebase — grep all refs, scope-check, apply, verify with build + zero-straggler grep. Delegates to a Haiku agent (cheap, mechanical).
argument-hint: <old> <new> [path-scope]
allowed-tools: Bash, Grep, Glob, Read, Agent
---

Rename **`$1` → `$2`** across the codebase. Optional path scope: `$3` (default: repo root, excluding `node_modules`, generated dirs, `.git`, build output).

This is mechanical but dangerous (a missed call site breaks the build; a missed one on a security/auth helper can cause a bypass). Follow this protocol; **delegate the work to a Haiku `general-purpose` agent** (renames don't need Opus) unless it's a trivial single-file change you can do inline.

## Protocol (give this to the Haiku agent)
1. **Survey:** `grep -rn '$1'` across the scope (exclude `node_modules`, `*/generated/*`, `.git`, `dist`, `.next`). List every file + line.
2. **Scope-check before touching anything:**
   - Is `$1` a *local* identifier, or **exported/imported across files**, or a **common word/substring** (risk of over-matching)? If it's exported/shared or could match unintended text, STOP and report the ambiguity for confirmation — do not blanket-replace.
   - Note distinct kinds of occurrence (definition, call sites, imports, type refs, strings, comments, docs) so none are missed and none are wrongly changed.
3. **Apply:** prefer `Edit` with `replace_all` per file (read each first). Use `sed` only for a confirmed pure-symbol rename across many files.
4. **Verify (must pass before reporting done):**
   - Re-run `grep -rn '$1'` over the scope → expect ZERO (or only intentional remnants like unrelated docs — call those out explicitly).
   - Run the project's type/build check (TypeScript: `npx tsc --noEmit` → exit 0; otherwise the repo's equivalent). Paste the result.
5. **Report:** files changed, the two grep outputs (before count / after zero), and the build result. Do NOT commit unless asked.

## Controller notes (you, after the agent returns)
- Confirm the after-grep is clean and the build passed before telling the user it's done.
- If the agent flagged a scope ambiguity, surface it and ask before proceeding.
- If `$1`/`$2` weren't supplied, ask which symbol and the new name first.

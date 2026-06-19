---
description: Make AGENTS.md the canonical guide every AI coding CLI follows; reduce CLAUDE.md/GEMINI.md to @import pointers. Local project by default, then offers the global ~/.claude setup.
argument-hint: [local | global | path-to-project]
---

Invoke the `unify-agents-md` skill.

Scope from `$ARGUMENTS`:
- empty or `local` → operate on the current project (default).
- `global` → skip straight to the global machine-wide setup (still confirm before editing existing files).
- a path → treat that directory as the project root.

Follow the skill exactly: do the **local** project first, back up every file before editing (timestamped, never clobber), keep all content (re-bucket, don't delete), put `@import` on line 1 with no indentation, and leave changes uncommitted for review. **After** local is done, ask whether to also do the global setup — don't do global unasked.

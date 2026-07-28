# Runbook & instruction standards

When producing instructions the user (or anyone) will execute — runbooks,
PR/issue steps, handoffs, recovery procedures — **fully specify every step** so
it is executable exactly as written, with zero inference required.

- Every command must be copy-pasteable as-is. Lead with `cd` when the directory
  matters (runbooks written for humans are the one place `cd` is fine — the
  no-`cd` rule governs agent tool calls, not instructions for people).
- If a step opens an editor, show the exact content to type.
- If a command prompts, say what to answer.
- For verification steps, state the expected output so success is recognizable.
- Remote steps: `ssh <host>` first, then the command on its own line.
- Use the user's aliases where they exist (`~/.bash_aliases`, `~/.ssh/config`,
  justfiles).
- Placeholders get executed verbatim (a `USER:PASSWORD@HOST` example once got
  stored as a live SecureString). Pre-fill every non-secret value yourself
  (endpoints, usernames, ports are metadata — fetch them); leave ONLY the
  secret blank, and make it syntactically un-runnable and loud, e.g.
  `<PASTE-DB-PASSWORD-FROM-VAULT>`. Include `--overwrite`/idempotent flags so
  a corrected re-run just works.
- In HTML deliverables, every command/prompt/snippet gets a copy-to-clipboard
  button (see the Output rules in `~/.config/agents/AGENTS.md`).

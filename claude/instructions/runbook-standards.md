# Runbook & instruction standards

## Where pending steps go

Every action waiting on the user — typing a secret, an IAM/DNS go-ahead, a
console setting, a decision only they can make — goes on the **central
runbook**: one local page across all repos (`http://127.0.0.1:8765`, served by
the tool in `tools/runbook/` of the config repo, installed at e.g.
`/path/to/projects/_runbook`). **If it is not on the page, nothing is waiting
on the user.** A plan or note may describe the step, but the runbook item is
what makes it pending.

Add it with the CLI (`python` on Windows, `python3` on Linux/WSL; alias it as
`runbook`):

```bash
runbook add --repo <Repo> --title "<what>" --why "<why it matters>" \
  --step "wsl|<exact command>|<expected output>" --verify "<read-only check>" \
  [--rollback "<undo>"] [--source <Repo/path.md>] [--due YYYY-MM-DD] [--priority urgent]
runbook add-decision --repo <Repo> --title "<question>" --option "A|detail" --option "B|detail*"
```

`--step` is `shell|command|expect`: the shell is before the first `|`, the
expectation after the last, so the command may contain pipes (`wsl`,
`powershell`, or `bash-remote:<host>`). Set `RUNBOOK_AGENT=<your CLI name>`.
`add` refuses secret-looking text and unfilled placeholders other than the
loud `<PASTE-…>` form. A CLI sandboxed to its own repo falls back to
`<repo>/.runbook/inbox/` (exit 3); the service collects it within a minute.
The fields map to the standards below: `steps` = the commands, `expect` = the
expected output, `verify` = how an agent confirms it, `rollback` = the undo.
Reference runbooks (how-to docs) stay in their repos and may be linked from
`--source`. The user ticks items off; the processor verifies and removes them.

## Writing the steps

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

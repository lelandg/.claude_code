# runbook

A local "central runbook": one list of every step that is waiting on **you**
(the human owner) rather than on an agent, gathered from all of your repos.
Agents add items with a CLI; you work through them on a local web page (tick,
paste output, mark a problem, answer a decision, leave a note for Claude); a
processor run by Claude Code then verifies what you finished, diagnoses what
failed, records your decisions and answers your notes.

Stdlib-only Python 3.12+. Pieces:

| File | Role |
|---|---|
| `rblib.py` | State library: locking, atomic writes, secret scanner, done log |
| `runbook.py` | Agent CLI (`runbook <verb>`) |
| `server.py` + `static/index.html` | Local page and JSON API on `http://127.0.0.1:8765` (Host, Origin and token checks) |
| `process.py` + `processor-prompt.md` | Processor: runs `claude -p` only when something you control changed or an item came due |
| `install.ps1` | Windows installer (token, login launcher, hourly task, CLI shims) |
| `config.json` | Processor settings (`model`, `effort`, `daily_cap`), optional `projects_root` |

State lives in `runbook.json` next to the scripts, guarded by
`runbook.json.lock`. It does not ship: a missing file loads as an empty
runbook and is created on the first write. `runbook.json`, `.token` and
`logs/` are git-ignored here, so your items never end up in this repo.

## How agents know to use it

The house rule in `~/.claude/instructions/runbook-standards.md` ("Where
pending steps go") tells every agent that a step waiting on you goes on the
runbook through `runbook add` / `runbook add-decision`, and how to write those
steps so they run exactly as written. Without that rule (or an equivalent line
in your `AGENTS.md`), agents will not know the tool exists.

## Configuration

| Setting | Default | Used by |
|---|---|---|
| `RUNBOOK_PROJECTS_ROOT` env var, else `"projects_root"` in `config.json` | the parent of this folder | `server.py` scans `<root>/*/.runbook/inbox/` and `<root>/*/*/.runbook/inbox/`; `process.py` passes it to `claude --add-dir` and the prompt |
| `RUNBOOK_AGENT` env var | `unknown` | `runbook.py` records it as `added_by` |
| `"allowed_tools"` in `config.json` | `process.default_allowed_tools()`: Read/Edit/Write/Glob/Grep/Agent plus `Bash(<prefix>:*)` rules for the runbook CLI, `git -C`, `gh`, the landing tool, `aws`, `codex`, `npm` | the unattended `claude -p` run's `--allowedTools`; replaces the list, and bare `Bash` is refused. Add your cloud admin tool's prefix here |
| `RUNBOOK_STATE` env var | unset | `runbook.py` reads it as its state file; `process.py --state` sets it for the model's CLI calls |
| `--port` (server) | `8765` | `server.py` |
| `--state` (server) | `./runbook.json` | `server.py` |
| `-WslRoot` (installer) | derived with `wslpath` | `install.ps1` WSL shim |

The tool's own location is always taken from the script path, so the folder
can live anywhere, for example `/path/to/projects/_runbook`. Since the service
is launched at login, prefer `projects_root` in `config.json` over an env var.

## Install

### Windows

    pwsh -File /path/to/projects/_runbook/install.ps1          # -WhatIf to preview

Idempotent and user-scope (never elevated); it prints `exists:`, `created:`,
`updated:` or `skipped:` per item. It creates:

- `.token`: 32 random bytes as hex, written only when missing (never printed).
- `runbook-server.cmd` in your Startup folder, launching `pythonw server.py` at login.
- The hourly scheduled task `Runbook\Processor` (`process.py --reason hourly`).
- `%USERPROFILE%\.local\bin\runbook.cmd` (warns if that is not on your PATH) and,
  when WSL is present, the executable shim `~/.local/bin/runbook` in WSL. A shim,
  not a `~/.bashrc` alias: aliases exist only in interactive shells, so
  `wsl.exe bash -lc 'runbook ...'` and agent shells would never find one.
- A `.runbook/` line in your global git ignore (Windows and WSL).
- A commit tracking `runbook.json`, but only when this folder is its own git
  repo and the file is not ignored. Inside this mirror it is skipped.

Start the service now (it also starts at login):

    Start-Process -FilePath (Get-Command pythonw.exe).Source -ArgumentList '"<this folder>\server.py"' -WindowStyle Hidden

### Linux, macOS, WSL

The Python is cross-platform (`process.py` kills process groups on POSIX), but
there is no installer: `install.ps1` is Windows-only. Set it up by hand:

    mkdir -p ~/.local/bin && printf '#!/bin/sh\nexec python3 /path/to/projects/_runbook/runbook.py "$@"\n' > ~/.local/bin/runbook && chmod +x ~/.local/bin/runbook
    python3 /path/to/projects/_runbook/server.py &      # writes .token on first start
    # hourly processor, e.g. crontab:
    0 * * * * python3 /path/to/projects/_runbook/process.py --reason hourly

and add `.runbook/` to `~/.config/git/ignore`. The processor needs the
`claude` CLI on `PATH`.

## CLI

`runbook <verb>`; exit codes 0 ok, 1 error, 2 refused (secret, unfilled
placeholder, bad input, unknown id), 3 queued in the repo's `.runbook/inbox/`
because the state file was not writable (the service merges inboxes every
minute).

| Verb | Use |
|---|---|
| `add --repo R --title T --why W --step "shell\|cmd\|expect" ... --verify V [--rollback] [--due YYYY-MM-DD] [--after rb-0001] [--priority urgent\|normal\|later] [--tag X] [--source path]` | Add a step item (re-adding the same repo + title updates it) |
| `add-decision --repo R --title T --option "label\|detail" --option "label\|detail *" [--source path]` | Add a decision; a trailing `*` marks the recommended option |
| `list [--state open\|done\|problem]` | List items |
| `show <id>` | Show one item |
| `verified <id> --note "evidence"` | Close a done item (moves it to the done log) |
| `reopen <id> --note "why"` | Send it back to you with a diagnosis |
| `reply <note-id> --text "answer" [--asked-back]` | Answer a note left on the page |
| `restore <id>` | Bring an item back from the 30-day done log |

Items are refused if they contain anything shaped like a secret.

## Tests

    python -m unittest discover -s tests -t .

(`python3` on Linux/WSL.) The installer test runs `install.ps1 -WhatIf` and is
skipped without `pwsh`. Test fixtures never hold literal key-shaped strings;
build them in `tests/fakes.py`.

## Uninstall (Windows)

    Remove-Item "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\runbook-server.cmd"
    schtasks /delete /tn "Runbook\Processor" /f
    Remove-Item "$env:USERPROFILE\.local\bin\runbook.cmd"
    wsl.exe bash -lc "rm -f ~/.local/bin/runbook"
    wsl.exe bash -lc "sed -i '/^alias runbook=/d' ~/.bashrc"   # installs from before the shim

then remove the `.runbook/` line from your global git ignore if you want.

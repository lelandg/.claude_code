# Environment & tooling details

The always-loaded rules (no `cd`, even-minor-version preference) live in
`~/.config/agents/AGENTS.md`. This file holds the rest — customize each
section for your machine.

## IDEs

Customize for your setup (e.g. JetBrains, VS Code, Vim).

## Version picks

Prefer even-numbered minor versions of open-source software (e.g. Python 3.12,
not 3.11/3.13; Node.js LTS majors are even) — treat the even line as stable.
If a needed package doesn't support the even version yet, use the odd one and
say so.

## Python

- bash/WSL (agents): `python3`, with a Linux-specific venv (e.g. `.venv_linux`)
  when the repo is also used from Windows.
- Windows/PowerShell: `python` with the standard `.venv` — never activate a
  Windows `.venv` from a WSL shell (binaries don't match).

## .NET / C#

WPF needs Windows; in WSL use syntax checking
(`dotnet build --no-dependencies`), not full builds.

## Node.js

Update to latest LTS with `nvm install --lts --reinstall-packages-from=default`;
pin per-project with `.nvmrc` + `nvm use`.

## Debugging

- **Production issues:** target the deployed environment, not local logs.
  (Customize for your infrastructure — e.g. "production runs on EC2 /
  serverless".)
- **Web apps:** Chrome + DevTools via remote debugging —
  `chrome --remote-debugging-port=9222` (on WSL, launch the Windows Chrome
  install via its Windows path).

## Screenshots

- Stored in the `_screenshots` symlink (customize the target path). Create it
  in a project if missing: `ln -s /path/to/your/screenshots _screenshots`.
- Most recent: `ls -lt _screenshots/*.png | head -3 | awk '{print $9}'`.
- "The screenshot" (singular) = the newest by timestamp; correlate with log
  timestamps when relevant.

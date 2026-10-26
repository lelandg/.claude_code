# Environment & tooling details

The always-loaded rules (no `cd`, the support-window version rule) live in
`~/.config/agents/AGENTS.md`. This file holds the rest — customize each
section for your machine.

## IDEs

Customize for your setup (e.g. JetBrains, VS Code, Vim).

## Version picks

Pick the release line with the **longest remaining security-support window**
that the project's dependencies allow. (This replaces an earlier "prefer even
minors" rule, which generalised a Node-only fact to all software.)

- **Node.js:** pin a line that is in LTS. Verified against nodejs/Release
  `schedule.json` on 2026-10-23: **22** Maintenance LTS, EOL 2027-04-30;
  **24** Maintenance LTS since 2026-10-20, EOL 2028-04-30; **26** becomes LTS
  2026-10-28, EOL 2029-04-30; **23** and **25** were Current-only and are EOL
  (2025-06-01, 2026-06-01). From **27** (alpha 2026-10-28, LTS 2027-10-20) the
  cycle is annual and every major becomes LTS — do not encode "odd = unstable".
  Pin in `.nvmrc`; bound `engines` per major at the patched minimums, naming
  the EOL lines explicitly rather than by parity.
- **Python:** no even/odd convention exists. Every minor is a stable release
  with five years of support (bugfix, then security-only). Verified 2026-10-23:
  **3.15** is newest (released 2026-10-09; EOL 2031-10-31); 3.14 EOL
  2030-10-31; 3.13 EOL 2029-10-31 (security-only since 2026-10-01); 3.12 EOL
  2028-10-31; 3.11 EOL 2027-10-31; **3.10 is EOL** (2026-10-01). Prefer the
  newest minor the dependencies support. Existing `>=3.11`/`>=3.12` floors can
  stay as they are — no churn — but nothing new targets 3.10.
- **Everything else:** read the project's own support policy; most have none
  and simply patch the latest stable. Never run an end-of-life line.
- If a dependency forces an older line, say so and name the date it goes EOL.

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

## Git on Windows

- **Dubious-ownership errors** (repo owned by another user or reached through
  a network path): use a checkout-scoped override, never a global one:
  `git -c safe.directory='<abs path>' -C '<abs path>' status`.

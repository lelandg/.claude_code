# disk-doctor rule pack — Linux (Pop!_OS / Debian family)

This file is DATA the disk-doctor skill reads. It declares conventions and
rules. It can only ADD restrictions; the in-script denylist floor in
`disk_doctor_core.py` always wins and cannot be weakened here.

## Allowed roots

Roots that `safe-trash --allow` may be pointed at (cleanup targets live here):

- `~/Downloads`
- `~/.cache`
- `~/.local/share/Trash` (already-trashed items pending purge)
- `~/.npm/_cacache`
- `~/.cache/pip`
- Dev project working dirs under `~` (for stale `node_modules`, `__pycache__`, `.venv`)

## Never-touch (additional)

Added on top of the in-script floor (`/`, `/usr`, `/etc`, `~`, `~/.ssh`,
`~/.config`, `~/.gnupg`, `~/.local/share`, browser profiles, etc.):

- `~/.local/bin`
- `~/.gitconfig`, `~/.bashrc`, `~/.profile`, `~/.zshrc`
- Any path under a mounted external/removable drive (`/media`, `/mnt`) unless the user names it explicitly

## Cache-clean rules

Safe-to-clean categories and how to find them. These RECLAIM space:

- **pip cache:** `~/.cache/pip`
- **npm cache:** `~/.npm/_cacache`
- **Browser caches (NOT profiles):** `~/.cache/mozilla`, `~/.cache/google-chrome`, `~/.cache/chromium`
- **Thumbnail cache:** `~/.cache/thumbnails`
- **`__pycache__` dirs** anywhere under dev project dirs
- **`node_modules`** in projects whose source was not modified in 90+ days (stale)
- **Old logs:** `*.log` under `~/.cache` and project dirs, older than 30 days
- **Duplicates:** identical files (match by size, then SHA-256) — keep the newest, propose the rest
- **Large-and-old:** files > 500 MB not accessed in 180+ days (propose, never assume)

Note: browser CACHE dirs above are cleanable; browser PROFILE dirs
(`~/.mozilla`, `~/.config/google-chrome`, `~/.config/chromium`,
`~/snap/firefox`) are on the never-touch floor and must not overlap.

## Install-hygiene rules

Report-only. Detect and explain; never auto-fix.

- **pip outside a venv:** packages in `~/.local/lib/python*/site-packages` or system site-packages installed by user-level `pip install`. Fix: `python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
- **Global npm packages:** `npm ls -g --depth=0` shows non-essential packages. Fix: prefer per-project installs or `npx`.
- **Project missing a venv:** dir has `requirements.txt`/`pyproject.toml` but no `.venv`/virtualenv. Fix: create a venv before installing.
- **Duplicate Python toolchains:** conda + system + pyenv all on PATH. Report which `python3`/`pip` actually resolves (`which -a python3 pip`).
- **Orphaned env leftovers:** `.venv`/`node_modules` in abandoned/stale project dirs — surface as a cleanup item, not a hygiene fix.

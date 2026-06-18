# disk-doctor rule pack — macOS

Data the disk-doctor skill reads. Can only ADD restrictions; the in-script
denylist floor always wins. v1 note: trashing works; automatic undo is not yet
implemented on macOS — restore from the Finder Trash using the run manifest.

## Allowed roots

- `~/Downloads`
- `~/Library/Caches`
- `~/.npm/_cacache`
- `~/Library/Caches/pip`
- Dev project working dirs under `~` (stale `node_modules`, `__pycache__`, `.venv`)

## Never-touch (additional)

On top of the in-script floor (`/`, `/System`, `/Library`, `~`, `~/.ssh`,
`~/.config`, `~/Library/Application Support/{Firefox,Google/Chrome,Chromium}`):

- `/Applications`
- `~/Library/Keychains`
- `~/Library/Mobile Documents` (iCloud Drive)

## Cache-clean rules

- **pip cache:** `~/Library/Caches/pip`
- **npm cache:** `~/.npm/_cacache`
- **Browser caches (NOT profiles):** `~/Library/Caches/Firefox`, `~/Library/Caches/Google/Chrome`
- **`__pycache__`** under dev project dirs
- **`node_modules`** in projects untouched 90+ days
- **Duplicates:** match by size then SHA-256; keep newest
- **Large-and-old:** > 500 MB not accessed in 180+ days (propose only)

## Install-hygiene rules

Report-only.

- **pip outside a venv:** user/system site-packages. Fix: `python3 -m venv .venv && ...`
- **Global npm packages:** `npm ls -g --depth=0`. Fix: per-project installs or `npx`.
- **Project missing a venv:** has `requirements.txt`/`pyproject.toml`, no `.venv`.
- **Duplicate Python toolchains:** Homebrew + system + pyenv. Report `which -a python3 pip`.
- **Orphaned env leftovers:** stale `.venv`/`node_modules` → cleanup item.

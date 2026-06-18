# disk-doctor rule pack — Windows

Data the disk-doctor skill reads. Can only ADD restrictions; the in-script
denylist floor always wins. v1 note: trashing works; automatic undo is not yet
implemented on Windows — restore from the Recycle Bin using the run manifest.

## Allowed roots

- `%USERPROFILE%\Downloads`
- `%LOCALAPPDATA%\Temp`
- `%LOCALAPPDATA%\pip\Cache`
- `%APPDATA%\npm-cache`
- Dev project working dirs under `%USERPROFILE%` (stale `node_modules`, `__pycache__`, `.venv`)

## Never-touch (additional)

On top of the in-script floor (`C:\Windows`, `C:\Program Files`,
`C:\Program Files (x86)`, the user profile root, browser profiles under
`%APPDATA%`/`%LOCALAPPDATA%`):

- `%APPDATA%\Microsoft`
- `%LOCALAPPDATA%\Microsoft`
- `%USERPROFILE%\AppData\Local\Programs`

## Cache-clean rules

- **pip cache:** `%LOCALAPPDATA%\pip\Cache`
- **npm cache:** `%APPDATA%\npm-cache`
- **Temp:** `%LOCALAPPDATA%\Temp` (files not modified in 7+ days)
- **Browser caches (NOT profiles):** `...\Google\Chrome\User Data\*\Cache` (cache subdir only)
- **`__pycache__`** under dev project dirs
- **`node_modules`** in projects untouched 90+ days
- **Duplicates:** match by size then SHA-256; keep newest
- **Large-and-old:** > 500 MB not accessed in 180+ days (propose only)

## Install-hygiene rules

Report-only.

- **pip outside a venv:** user site-packages under `%APPDATA%\Python`. Fix: `python -m venv .venv & ...`
- **Global npm packages:** `npm ls -g --depth=0`. Fix: per-project installs or `npx`.
- **Project missing a venv:** has `requirements.txt`/`pyproject.toml`, no `.venv`.
- **Duplicate Python toolchains:** Microsoft Store Python + python.org + conda. Report `where python pip`.
- **Orphaned env leftovers:** stale `.venv`/`node_modules` → cleanup item.

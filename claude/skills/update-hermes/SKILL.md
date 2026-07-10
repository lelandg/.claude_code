---
name: update-hermes
description: Safely update the Hermes Agent install on this machine (hermes CLI + ~/.hermes/hermes-agent source repo). Use on /update-hermes, or when asked to "update hermes", "upgrade the hermes agent", or "pull the latest hermes". Always backs up first — full ~/.hermes backup via `hermes update --backup` PLUS a separate patch/tarball backup of local source customizations, because the built-in backup intentionally excludes the hermes-agent/ source repo. Never runs a bare `hermes update`.
---

# Update Hermes (safely)

Update the Hermes Agent with full backup coverage, source-code patch backups, and
post-update verification. Born from the 2026-06-22 update safety sheet.

**Golden rule: NEVER run a bare `hermes update`.** Always `--backup`, and always
take the manual source backup first (§2) — `hermes update --backup` backs up
`~/.hermes` (config, skills, sessions, auth/state) but **intentionally excludes
the `hermes-agent/` source repo**, so local source customizations survive only
via the manual patch/tarball.

All paths are `$HOME`-relative — this skill runs on whichever machine hosts the
install (different machines use different usernames).

## 1. Preflight (read-only)

```bash
command -v hermes && hermes --version
cd ~/.hermes/hermes-agent && git status --short && git diff --stat
git fetch --quiet origin && git rev-list --count HEAD..origin/HEAD 2>/dev/null \
  || git rev-list --count HEAD..@{u}   # commits behind
```

- No `hermes` on PATH → stop; this machine doesn't host Hermes.
- Record the current version and the list of locally modified tracked files +
  untracked extras (e.g. a `Notes/` directory) — you'll re-check them in §4.
- 0 commits behind and no pending update → report "already current" and stop
  (don't churn backups for nothing).

## 2. Manual source backup — ALWAYS, before updating

```bash
cd ~/.hermes/hermes-agent
TS=$(date -u +%Y%m%d-%H%M%SZ)
BK=~/.hermes/backups/manual-update-customizations
mkdir -p "$BK"
git diff HEAD                      > "$BK/hermes-agent-local-diff-$TS.patch"
git status --short                 > "$BK/hermes-agent-status-$TS.txt"
UNTRACKED=$(git ls-files --others --exclude-standard)
[ -n "$UNTRACKED" ] && echo "$UNTRACKED" | tar -czf "$BK/hermes-agent-untracked-$TS.tar.gz" -T -
ls -la "$BK" | tail -5
```

- The patch captures tracked customizations; the tarball captures untracked
  files (skips gitignored junk like venvs/caches automatically).
- If the patch is empty AND there are no untracked files, note "no local
  customizations" and continue — the update is low-risk.

## 3. Update

```bash
cd ~/.hermes/hermes-agent
hermes update --backup          # interactive (preferred when a human is watching)
# hermes update --backup --yes  # non-interactive variant (headless/automation)
```

Hermes auto-stashes tracked + untracked source changes, pulls, and attempts to
restore them afterward. The `--backup` flag additionally snapshots `~/.hermes`
first. Watch the output for stash-restore conflicts.

## 4. Verify

```bash
cd ~/.hermes/hermes-agent
git status --short && git diff --stat
hermes --version
hermes doctor
```

- Compare `git status --short` against the pre-update status file from §2:
  every customization listed there should still be present. Missing ones → §5.
- `hermes doctor` must come back clean. Paste failures verbatim in the report.
- If hermes runs as a service on this host, check and restart it:
  `systemctl --user list-units --all | grep -i hermes` (and system scope:
  `systemctl list-units --all | grep -i hermes`). Restart hermes-owned units
  after a successful update and confirm they're `active`. If a unit looks
  ambiguous (not clearly hermes-owned), flag it instead of restarting.

## 5. Restore customizations (only if §4 shows losses)

Preferred — from the manual backup taken in §2:

```bash
cd ~/.hermes/hermes-agent
git apply --3way "$BK/hermes-agent-local-diff-$TS.patch"
tar -xzf "$BK/hermes-agent-untracked-$TS.tar.gz" -C ~/.hermes/hermes-agent   # if it exists
```

Fallback — Hermes's own auto-stash:

```bash
git stash list --format='%gd %H %s'
git stash apply stash@{0}
```

- `git apply --3way` leaves conflict markers on genuine conflicts — resolve them
  file by file; never `git checkout -- .` your way out (that discards the
  customizations you're restoring).
- Never drop stashes or delete backup artifacts, even after a clean restore.

## 6. One-time hardening (offer once per host)

```bash
hermes config set updates.pre_update_backup true
```

Makes every future `hermes update` create the full backup automatically. Check
first (`hermes config get updates.pre_update_backup`); skip if already set.

## 7. Report

Summarize: version before → after, commits pulled, backup artifact paths
(patch/status/tarball + the `--backup` snapshot location from hermes's output),
customizations verified intact (or restored, and how), `hermes doctor` result,
services restarted, and any ACTION REQUIRED (conflicts left for the user, doctor
failures) with exact commands inline.

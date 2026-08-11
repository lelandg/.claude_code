#!/usr/bin/env bash
# Scheduled agent-config drift check. Report-only: this script can never apply
# a configuration change.
#
# Exit codes: 0 no drift (Claude was not invoked), 10 drift reported,
#             20 scan failure, 21 another run holds the lock, 30 model failure.
#
# Design: "Scheduling".
set -euo pipefail

ACS_REPO="${ACS_REPO:-/mnt/d/Documents/Code/GitHub/.claude_code}"
ACS_PYTHON="${ACS_PYTHON:-/usr/bin/python3}"

# $HOME is only dereferenced below as a fallback for ACS_CLAUDE/ACS_STATE,
# via ${VAR:-$HOME/...}, which treats VAR as absent when VAR is unset OR
# set-but-empty. This guard must use the same value-based test (${VAR:+x},
# not ${VAR+x}) or an empty-but-set override would slip past a
# presence-only guard and still trigger the $HOME dereference it exists to
# prevent. cron, systemd timers, and minimal containers do not all
# guarantee HOME, so check before dereferencing -- otherwise `set -u`
# aborts with HOME's own "unbound variable" message and no documented exit
# code, before log() exists to record what happened. ${VAR:+x} never
# dereferences on the unset path, so this check itself is safe under
# `set -u` even when HOME is unset.
if [ -z "${HOME:+x}" ] && { [ -z "${ACS_CLAUDE:+x}" ] || [ -z "${ACS_STATE:+x}" ]; }; then
  printf 'agent-config-sync: HOME is not set and ACS_CLAUDE/ACS_STATE were not both provided explicitly; set ACS_CLAUDE and ACS_STATE, or set HOME.\n' >&2
  exit 20
fi

ACS_CLAUDE="${ACS_CLAUDE:-$HOME/.local/bin/claude}"
ACS_MANIFEST="${ACS_MANIFEST:-$ACS_REPO/config/agent-sync.toml}"
ACS_STATE="${ACS_STATE:-$HOME/.local/state/agent-config-sync}"
ACS_SCAN="${ACS_SCAN:-$ACS_PYTHON $ACS_REPO/tools/agent-config-sync/scan.py}"
ACS_RENDER="${ACS_RENDER:-$ACS_PYTHON $ACS_REPO/tools/agent-config-sync/render.py}"

# cron has no useful environment; establish a minimal explicit one.
export PATH=/usr/local/bin:/usr/bin:/bin
export LC_ALL=C.UTF-8

if ! mkdir -p "$ACS_STATE" 2>/dev/null; then
  # wrapper.log lives inside $ACS_STATE, which just failed to exist -- log()
  # cannot be relied on here, so this goes to stderr, the only channel cron
  # has left to mail.
  printf 'agent-config-sync: cannot create state directory %s\n' "$ACS_STATE" >&2
  exit 20
fi
DRIFT="$ACS_STATE/latest-drift.json"
LOG="$ACS_STATE/wrapper.log"

log() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >>"$LOG"; }

log "run start; manifest=$ACS_MANIFEST state=$ACS_STATE"

# Deterministic scan first. Word splitting on $ACS_SCAN is intentional: it is a
# command line, not a single path.
scan_start=$(date +%s)
set +e
# shellcheck disable=SC2086
$ACS_SCAN --manifest "$ACS_MANIFEST" --out "$DRIFT" --state-dir "$ACS_STATE"
scan_code=$?
set -e
scan_seconds=$(( $(date +%s) - scan_start ))
log "scan exit=$scan_code duration=${scan_seconds}s"

case "$scan_code" in
  0)
    log "no drift; Claude not invoked"
    log "wrapper exit=0"
    exit 0
    ;;
  10)
    log "drift detected; invoking the analyzer"
    ;;
  21)
    log "another run holds the lock; exiting"
    log "wrapper exit=21"
    exit 21
    ;;
  *)
    log "scan failed with exit $scan_code; previous report left untouched"
    log "wrapper exit=20"
    exit 20
    ;;
esac

set +e
# shellcheck disable=SC2086
$ACS_RENDER --drift "$DRIFT" --state-dir "$ACS_STATE" \
            --claude-bin "$ACS_CLAUDE"
render_code=$?
set -e

if [ "$render_code" -ne 0 ]; then
  log "analyzer/render failed with exit $render_code; last valid report kept"
  log "wrapper exit=30"
  exit 30
fi

log "report written to $ACS_STATE/latest-report.md"
log "wrapper exit=10"
exit 10

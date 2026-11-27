#!/usr/bin/env bash
# ci-local — run a repo's own GitHub Actions workflow files locally, the way
# CI would run them, with act + Docker. Free; no Actions minutes.
#
# Fidelity choices (each one closes a gap between act and GitHub's runner):
#   * Tests COMMITTED state: the commit is fetched into a clean clone under
#     ~/ci-local, never the working tree. Uncommitted edits cannot make a run
#     pass, and node_modules never crosses a slow Windows mount.
#   * pull_request runs test the MERGE of head into base, like GitHub's
#     refs/pull/N/merge checkout. A conflict fails the run.
#   * Each job gets a GitHub-hosted runner's size: a 2-CPU quota and 7 GB, and
#     it SEES 2 CPUs (/proc/cpuinfo and /proc/stat are masked, as lxcfs does),
#     so tools that size themselves from the CPU count (Playwright workers,
#     test runners) behave as on GitHub instead of starting one per host core.
#   * ubuntu-latest maps to catthehacker/ubuntu:act-24.04 (Ubuntu 24.04, the
#     same release as GitHub's ubuntu-latest).
#   * Actions come from act's new action cache (a copy per job), offline once
#     cached when every action is SHA-pinned; the classic cache shares one
#     checkout between parallel jobs, which then delete each other's files.
#   * At most 2 jobs run at once (CI_LOCAL_JOBS), because here they share one
#     disk that GitHub gives each job to itself.
#   * Service host ports already taken on this machine, or by another job of
#     the same run, move to free ones in the throwaway clone (act_compat.py).
#   * The run's containers and networks are removed afterwards, even when
#     act's own --rm times out, so no finished run holds a port or a database
#     the next one needs. One ci-local run at a time on the machine.
#
# Usage:
#   ci-local.sh <repo-path> [--ref REF] [--base BRANCH] [--event pull_request|push]
#               [--pr N] [-j JOB] [-W .github/workflows/x.yml] [-- extra act args]
#   REF defaults to HEAD of <repo-path>; BASE to the remote default branch.
# Exit code: act's (0 = every selected job succeeded); 2 = ci-local could not
# set the run up (bad arguments, missing tools, a merge conflict).
set -euo pipefail

die() { echo "ci-local: $*" >&2; exit 2; }
HERE=$(dirname "$(readlink -f "$0")")
RUNNER_IMAGE=${CI_LOCAL_IMAGE:-catthehacker/ubuntu:act-24.04}
JOB_CPUS=2 JOB_MEMORY=7g
# GitHub gives every job its own VM and disk; here jobs share one disk. With
# eight jobs at once, and still with four, `npm ci`s starved a Postgres service
# of I/O past its health check, which never happens on GitHub. Two at a time
# kept every job within its checks and was also the fastest: 8m47s for eight
# jobs, against 10.5-12.5 min with four and 9.9 min on GitHub. Raise it on a
# fast disk.
CONCURRENT_JOBS=${CI_LOCAL_JOBS:-2}
[[ "$CONCURRENT_JOBS" =~ ^[1-9][0-9]*$ ]] || die "CI_LOCAL_JOBS must be a positive number"

[ $# -ge 1 ] || die "usage: ci-local.sh <repo-path> [--ref REF] [--base BRANCH] [--event pull_request|push] [--pr N] [-j JOB] [-W WORKFLOW] [-- act args]"
SRC=$(cd "$1" && pwd) || die "no such repo: $1"; shift
REF=HEAD BASE="" EVENT=pull_request PR=1 ACT_ARGS=() INFO=0
while [ $# -gt 0 ]; do
  case "$1" in
    --ref) REF=$2; shift 2 ;;
    --base) BASE=$2; shift 2 ;;
    --event) EVENT=$2; shift 2 ;;
    --pr) PR=$2; shift 2 ;;
    -j|-W) ACT_ARGS+=("$1" "$2"); shift 2 ;;
    --) shift; ACT_ARGS+=("$@"); break ;;
    *) die "unknown option: $1" ;;
  esac
done
case "$EVENT" in pull_request|push) ;; *) die "--event must be pull_request or push" ;; esac
[[ "$PR" =~ ^[0-9]+$ ]] || die "--pr must be a number"
for a in "${ACT_ARGS[@]+"${ACT_ARGS[@]}"}"; do
  case "$a" in -l|--list|-g|--graph|-n|--dryrun) INFO=1 ;; esac
done

# A worktree made by Windows git records "gitdir: D:/..." in its .git file,
# which WSL git cannot follow. Use the main repository (branches are shared)
# and take REF=HEAD from the worktree's own HEAD file.
MNT=${CI_LOCAL_MNT:-/mnt}  # where WSL mounts Windows drives
if [ -f "$SRC/.git" ] && grep -qE '^gitdir: [A-Za-z]:/' "$SRC/.git"; then
  WT_GITDIR=$(sed -E "s#^gitdir: ([A-Za-z]):/#${MNT//#/\\#}/\\L\\1/#" "$SRC/.git")
  if [ "$REF" = HEAD ]; then
    WT_HEAD=$(cat "$WT_GITDIR/HEAD")
    case "$WT_HEAD" in "ref: refs/heads/"*) REF=${WT_HEAD#ref: refs/heads/} ;; *) REF=$WT_HEAD ;; esac
  fi
  SRC=${WT_GITDIR%/.git/worktrees/*}
  [ -d "$SRC/.git" ] || die "cannot find the main repository for this Windows worktree ($SRC)"
fi
command -v act >/dev/null || die "act is not installed (see tools/ci-local/README.md)"
command -v flock >/dev/null || die "flock is not installed (util-linux)"
docker info >/dev/null 2>&1 || die "Docker is not running (systemctl status docker)"

NAME=$(basename "$(git -C "$SRC" remote get-url origin 2>/dev/null || echo "$SRC")" .git)
# Keyed by the repo's path too, so two repos with the same name never share a clone.
KEY="$NAME-$(printf '%s' "$SRC" | sha256sum | cut -c1-8)"
ROOT="$HOME/ci-local"; WORK="$ROOT/$KEY"; mkdir -p "$ROOT/logs"
HEAD_SHA=$(git -C "$SRC" rev-parse --verify "$REF^{commit}") || die "no commit $REF in $SRC"
FULL_REF=$(git -C "$SRC" rev-parse --symbolic-full-name "$REF" 2>/dev/null || true)
case "$FULL_REF" in
  refs/heads/*) HEAD_BRANCH=${FULL_REF#refs/heads/} ;;
  refs/remotes/*/*) HEAD_BRANCH=${FULL_REF#refs/remotes/*/} ;;  # origin/main -> main, as GitHub names it
  *) HEAD_BRANCH="" ;;
esac
if [ -z "$HEAD_BRANCH" ]; then
  HEAD_BRANCH=$(git -C "$SRC" for-each-ref --count=1 --contains "$HEAD_SHA" --format='%(refname:short)' refs/heads)
  [ -n "$HEAD_BRANCH" ] || HEAD_BRANCH="detached-${HEAD_SHA:0:7}"
fi
if [ -n "$(git -C "$SRC" status --porcelain --untracked-files=no 2>/dev/null)" ]; then
  echo "ci-local: note: $SRC has uncommitted changes; they are NOT tested (committed ${HEAD_SHA:0:7} is)." >&2
fi

# One run at a time on this machine. act names containers and networks after
# the workflow and job, so two runs at once could collide, a second run of one
# repo would reset its clone under the first, and parallel runs would compete
# for the one disk that GitHub gives each job to itself.
exec 9>"$ROOT/.lock"
flock -n 9 || die "another ci-local run is in progress; wait for it to finish"

TMP=$(mktemp -d "$ROOT/.run.XXXXXX")
WATCHER=""
# act's own --rm gives up when Docker is slow ("context deadline exceeded"),
# and a container left running holds its port or database for the next run.
# So ci-local removes what THIS run provably created, by immutable ID:
#   * job containers carry this run's own /proc mount ($TMP/proc/cpuinfo);
#   * act names each job's service network after that job's container
#     ("<job container>-<job id>-network"), and its services sit on it.
# While a job container exists, a watcher records its ID, its network's ID and
# the IDs of the containers on that network. Cleanup deletes those IDs only, so
# a later act run that reuses the same names is never touched.
record_owned() {
  local id name nid nname
  docker ps -a --filter "volume=$TMP/proc/cpuinfo" --format '{{.ID}} {{.Names}}' 2>/dev/null |
  while read -r id name; do
    [ -n "$id" ] || continue
    echo "container $id"
    docker network ls --filter name=^act- --format '{{.ID}} {{.Name}}' 2>/dev/null |
    while read -r nid nname; do
      case "$nname" in "$name"-*-network)
        echo "network $nid"
        docker network inspect -f '{{range $cid, $c := .Containers}}{{$cid}} {{end}}' "$nid" 2>/dev/null | tr ' ' '\n' | sed -n 's/^\(..*\)$/container \1/p' ;;
      esac
    done
  done >> "$TMP/owned"
}
watch_run_containers() {
  local sleeper=""
  trap '[ -z "$sleeper" ] || kill "$sleeper" 2>/dev/null; exit 0' TERM
  while :; do
    record_owned
    sleep 5 & sleeper=$!
    wait "$sleeper"
  done
}
remove_run_containers() {
  local kind id
  [ -z "$WATCHER" ] || { kill "$WATCHER" 2>/dev/null; wait "$WATCHER" 2>/dev/null || true; }
  record_owned
  [ -s "$TMP/owned" ] || return 0
  sort -u "$TMP/owned" | while read -r kind id; do
    [ "$kind" = container ] && docker rm -f "$id" >/dev/null 2>&1 || true
  done
  sort -u "$TMP/owned" | while read -r kind id; do
    [ "$kind" = network ] && docker network rm "$id" >/dev/null 2>&1 || true
  done
}
cleanup() { [ -d "$TMP" ] && remove_run_containers; rm -rf "$TMP"; }
trap cleanup EXIT
trap 'exit 130' INT TERM

[ -d "$WORK/.git" ] || git clone --quiet --no-checkout "$SRC" "$WORK"
# act takes github.repository (owner/name) from the clone's origin URL, so
# give it the source's own GitHub remote; ci-local fetches from $SRC by path.
ORIGIN_URL=$(git -C "$SRC" remote get-url origin 2>/dev/null || true)
if [ -n "$ORIGIN_URL" ]; then git -C "$WORK" remote set-url origin "$ORIGIN_URL"; fi
# The source repo's own branches and its view of the GitHub remote.
git -C "$WORK" fetch --quiet --force "$SRC" "+refs/heads/*:refs/remotes/src/*" "+refs/remotes/origin/*:refs/remotes/upstream/*"
if ! git -C "$WORK" cat-file -e "$HEAD_SHA^{commit}" 2>/dev/null; then
  # A detached worktree's commit is on no advertised ref; ask for it by id.
  git -C "$WORK" fetch --quiet --upload-pack="git -c uploadpack.allowAnySHA1InWant=true upload-pack" "$SRC" "$HEAD_SHA" \
    || die "could not fetch ${HEAD_SHA:0:7} from $SRC"
fi
if [ -z "$BASE" ]; then
  BASE=$(git -C "$SRC" symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null | sed 's#^origin/##' || true)
  [ -n "$BASE" ] || BASE=main
fi

git -C "$WORK" reset --quiet --hard 2>/dev/null || true
git -C "$WORK" clean -qfdx
# The throwaway merge must not sign, run your hooks or need your identity.
QUIET_GIT=(-c user.name=ci-local -c user.email=ci-local@localhost -c commit.gpgsign=false -c core.hooksPath=/dev/null)
if [ "$EVENT" = pull_request ]; then
  BASE_SHA=$(git -C "$WORK" rev-parse --verify "refs/remotes/upstream/$BASE^{commit}" 2>/dev/null) || die "no origin/$BASE in $SRC; run git fetch there"
  git -C "$WORK" checkout --quiet --force --detach "$BASE_SHA"
  git -C "$WORK" "${QUIET_GIT[@]}" merge --quiet --no-ff --no-edit --no-verify "$HEAD_SHA" \
    || { git -C "$WORK" merge --abort 2>/dev/null || true; die "${HEAD_SHA:0:7} does not merge cleanly into $BASE (GitHub would not run it either)"; }
else
  git -C "$WORK" checkout --quiet --force --detach "$HEAD_SHA"
  BASE_SHA=""
fi

# What a job sees as its CPUs: the first $JOB_CPUS processors of this machine.
mkdir -p "$TMP/proc"
awk -v n="$JOB_CPUS" 'BEGIN { RS = ""; ORS = "\n\n" } /^processor/ && c < n { c++; print }' /proc/cpuinfo > "$TMP/proc/cpuinfo"
awk -v n="$JOB_CPUS" '/^cpu[0-9]+ / { if (substr($1, 4) + 0 >= n) next } { print }' /proc/stat > "$TMP/proc/stat"
CONTAINER_OPTS="--cpus $JOB_CPUS --memory $JOB_MEMORY -v $TMP/proc/cpuinfo:/proc/cpuinfo:ro -v $TMP/proc/stat:/proc/stat:ro"

# Service ports taken here or by another job move to free ones, in the
# throwaway clone only (act_compat.py says why).
[ -d "$WORK/.github/workflows" ] || die "no .github/workflows in ${HEAD_SHA:0:7}"
python3 "$HERE/act_compat.py" "$WORK/.github/workflows" --max-parallel "$CONCURRENT_JOBS" --container-options "$CONTAINER_OPTS"

# Actions: act's classic cache checks every action out into ONE shared folder
# per job, so jobs that start together delete each other's files ("remove
# .../.gitignore: no such file", "archive/tar: write too long"). The new
# action cache keeps actions as git objects and gives each job its own copy.
# Offline mode (no re-fetch once cached) only when every action is pinned to
# a commit SHA, which cannot move; a tag or branch is fetched fresh, as on GitHub.
OFFLINE=(--action-offline-mode)
{ grep -rhoE "uses:[[:space:]]*['\"]?[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(/[^@'\"[:space:]]*)?@[^'\"[:space:]#]+" \
    "$WORK/.github/workflows" "$WORK/.github/actions" 2>/dev/null || true; } \
  | sed -E "s/^uses:[[:space:]]*['\"]?//" | sort -u > "$TMP/uses"
if grep -qvE '@[0-9a-f]{40}$' "$TMP/uses"; then
  OFFLINE=()
  echo "ci-local: an action is pinned to a tag or branch; act fetches actions fresh this run" >&2
fi


EV="$TMP/event.json"
if [ "$EVENT" = pull_request ]; then
  python3 - "$EV" "$PR" "$HEAD_BRANCH" "$HEAD_SHA" "$BASE" "$BASE_SHA" "$NAME" <<'PY'
import json, sys
out, pr, head_ref, head_sha, base, base_sha, name = sys.argv[1:]
json.dump({"action": "synchronize", "number": int(pr),
           "pull_request": {"number": int(pr), "head": {"ref": head_ref, "sha": head_sha}, "base": {"ref": base, "sha": base_sha}},
           "repository": {"name": name, "default_branch": base}}, open(out, "w"))
PY
else
  python3 - "$EV" "$HEAD_BRANCH" "$HEAD_SHA" "$BASE" "$NAME" <<'PY'
import json, sys
out, head_ref, head_sha, base, name = sys.argv[1:]
json.dump({"ref": f"refs/heads/{head_ref}", "after": head_sha, "repository": {"name": name, "default_branch": base}}, open(out, "w"))
PY
fi

ACT=(act "$EVENT" -e "$EV"
  -P "ubuntu-latest=$RUNNER_IMAGE" -P "ubuntu-24.04=$RUNNER_IMAGE"
  --container-options "$CONTAINER_OPTS"
  --pull=false --rm --artifact-server-path "$TMP/artifacts"
  --use-new-action-cache --action-cache-path "$HOME/.cache/act"
  --concurrent-jobs "$CONCURRENT_JOBS"
  "${OFFLINE[@]+"${OFFLINE[@]}"}" "${ACT_ARGS[@]+"${ACT_ARGS[@]}"}")

if [ "$INFO" = 1 ]; then  # --list, --graph, --dryrun: show act's own output
  (cd "$WORK" && "${ACT[@]}")
  exit $?
fi

# The jobs act plans to run (job id, workflow, name), so a run can be called a
# pass only when every one of them reported success: a later `needs:` stage
# that never started must not count as passing.
(cd "$WORK" && "${ACT[@]}" --list) > "$TMP/list" 2>/dev/null || : > "$TMP/list"

LOG="$ROOT/logs/$NAME-${HEAD_SHA:0:7}-$EVENT-$(date +%Y%m%d-%H%M%S).log"
echo "ci-local: $NAME ${HEAD_SHA:0:7} ($HEAD_BRANCH) $EVENT${BASE_SHA:+, merged into $BASE ${BASE_SHA:0:7}}${OFFLINE[*]:+, actions offline}"
echo "ci-local: log $LOG"
# The watcher must not hold the lock (fd 9) or the caller's output open.
watch_run_containers 9>&- </dev/null >/dev/null 2>&1 & WATCHER=$!
set +e
(cd "$WORK" && "${ACT[@]}" --log-prefix-job-id) > "$LOG" 2>&1 9>&-
RC=$?
python3 "$HERE/ci_summary.py" "$TMP/list" "$LOG" "$RC" "$WORK/.github/workflows"
VERDICT=$?
set -e
case "$VERDICT" in
  0) ;;
  10) echo "ci-local: every planned job succeeded; act's exit $RC came only from removing a finished container, which ci-local does itself"; RC=0 ;;
  *) [ "$RC" -ne 0 ] || RC=1 ;;  # the summary itself failed
esac
echo "ci-local: exit $RC"
exit $RC

#!/usr/bin/env bash
# ci-local — run a repo's own GitHub Actions workflow files locally, the way
# CI would run them, with act + Docker in WSL. Free; no Actions minutes.
#
# Fidelity choices (each one closes a gap between act and GitHub's runner):
#   * Tests COMMITTED state: the commit is fetched into a clean clone on WSL's
#     ext4 disk (~/ci-local/<repo>), never the working tree. Uncommitted edits
#     cannot make a run pass, and node_modules never crosses /mnt/d.
#   * pull_request runs test the MERGE of head into base, like GitHub's
#     refs/pull/N/merge checkout. A conflict fails the run.
#   * Each job container is capped at a GitHub-hosted runner's size
#     (2 vCPU, 7 GB), so timing flakes reproduce here too.
#   * ubuntu-latest maps to catthehacker/ubuntu:act-24.04 (Ubuntu 24.04, the
#     same release as GitHub's ubuntu-latest).
#
# Usage (from WSL):
#   ci-local.sh <repo-path> [--ref REF] [--base BRANCH] [--event pull_request|push]
#               [--pr N] [-j JOB] [-W .github/workflows/x.yml] [-- extra act args]
#   REF defaults to HEAD of <repo-path>; BASE to the remote default branch.
# Exit code: act's (0 = every selected job succeeded).
set -euo pipefail

die() { echo "ci-local: $*" >&2; exit 2; }

[ $# -ge 1 ] || die "usage: ci-local.sh <repo-path> [--ref REF] [--base BRANCH] [--event pull_request|push] [--pr N] [-j JOB] [-W WORKFLOW] [-- act args]"
SRC=$(cd "$1" && pwd) || die "no such repo: $1"; shift
REF=HEAD BASE="" EVENT=pull_request PR=1 ACT_ARGS=()
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
# A worktree made by Windows git records "gitdir: D:/..." in its .git file,
# which WSL git cannot follow. Use the main repository (branches are shared)
# and take REF=HEAD from the worktree's own HEAD file.
if [ -f "$SRC/.git" ] && grep -qE '^gitdir: [A-Za-z]:/' "$SRC/.git"; then
  WT_GITDIR=$(sed -E 's#^gitdir: ([A-Za-z]):/#/mnt/\L\1/#' "$SRC/.git")
  if [ "$REF" = HEAD ]; then
    WT_HEAD=$(cat "$WT_GITDIR/HEAD")
    case "$WT_HEAD" in "ref: refs/heads/"*) REF=${WT_HEAD#ref: refs/heads/} ;; *) REF=$WT_HEAD ;; esac
  fi
  SRC=${WT_GITDIR%/.git/worktrees/*}
  [ -d "$SRC/.git" ] || die "cannot find the main repository for this Windows worktree ($SRC)"
fi
command -v act >/dev/null || die "act is not installed (~/.local/bin/act)"
docker info >/dev/null 2>&1 || die "Docker is not running (systemctl status docker)"

NAME=$(basename "$(git -C "$SRC" remote get-url origin 2>/dev/null || echo "$SRC")" .git)
ROOT="$HOME/ci-local"; WORK="$ROOT/$NAME"; mkdir -p "$ROOT/logs"
HEAD_SHA=$(git -C "$SRC" rev-parse --verify "$REF^{commit}") || die "no commit $REF in $SRC"
HEAD_BRANCH=$(git -C "$SRC" rev-parse --abbrev-ref "$REF" 2>/dev/null || true)
if [ -z "$HEAD_BRANCH" ] || [ "$HEAD_BRANCH" = HEAD ]; then
  HEAD_BRANCH=$(git -C "$SRC" branch --contains "$HEAD_SHA" --format='%(refname:short)' | head -1)
fi
if [ -n "$(git -C "$SRC" status --porcelain --untracked-files=no)" ]; then
  echo "ci-local: note: $SRC has uncommitted changes; they are NOT tested (committed ${HEAD_SHA:0:7} is)." >&2
fi

[ -d "$WORK/.git" ] || git clone --quiet --no-checkout "$SRC" "$WORK"
# The source repo's own branches and its view of the GitHub remote.
git -C "$WORK" fetch --quiet --force "$SRC" "+refs/heads/*:refs/remotes/src/*" "+refs/remotes/origin/*:refs/remotes/upstream/*"
git -C "$WORK" fetch --quiet "$SRC" "$HEAD_SHA" 2>/dev/null || true
if [ -z "$BASE" ]; then
  BASE=$(git -C "$SRC" symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null | sed 's#^origin/##' || true)
  [ -n "$BASE" ] || BASE=main
fi

git -C "$WORK" reset --quiet --hard 2>/dev/null || true
git -C "$WORK" clean -qfdx
if [ "$EVENT" = pull_request ]; then
  BASE_SHA=$(git -C "$WORK" rev-parse --verify "refs/remotes/upstream/$BASE^{commit}") || die "no origin/$BASE in $SRC; run git fetch there"
  git -C "$WORK" checkout --quiet --force --detach "$BASE_SHA"
  git -C "$WORK" -c user.name=ci-local -c user.email=ci-local@localhost merge --quiet --no-ff --no-edit "$HEAD_SHA" \
    || { git -C "$WORK" merge --abort || true; die "${HEAD_SHA:0:7} does not merge cleanly into $BASE (GitHub would not run it either)"; }
else
  git -C "$WORK" checkout --quiet --force --detach "$HEAD_SHA"
  BASE_SHA=""
fi

# Service ports already taken on this machine move to free ones, in the
# throwaway clone only (act_compat.py says why).
python3 "$(dirname "$(readlink -f "$0")")/act_compat.py" "$WORK/.github/workflows"

EV=$(mktemp "$ROOT/event.XXXXXX.json")
trap 'rm -f "$EV"' EXIT
if [ "$EVENT" = pull_request ]; then
  cat > "$EV" <<JSON
{"action":"synchronize","number":$PR,
 "pull_request":{"number":$PR,"head":{"ref":"$HEAD_BRANCH","sha":"$HEAD_SHA"},"base":{"ref":"$BASE","sha":"$BASE_SHA"}},
 "repository":{"name":"$NAME","default_branch":"$BASE"}}
JSON
else
  cat > "$EV" <<JSON
{"ref":"refs/heads/$HEAD_BRANCH","after":"$HEAD_SHA","repository":{"name":"$NAME","default_branch":"$BASE"}}
JSON
fi

LOG="$ROOT/logs/$NAME-${HEAD_SHA:0:7}-$EVENT-$(date +%Y%m%d-%H%M%S).log"
echo "ci-local: $NAME ${HEAD_SHA:0:7} ($HEAD_BRANCH) $EVENT${BASE_SHA:+, merged into $BASE ${BASE_SHA:0:7}}"
echo "ci-local: log $LOG"
# Parallel jobs share act's action cache; refreshing it while another job
# copies it fails with "archive/tar: write too long". Actions here are pinned
# to commit SHAs, so a cached copy never goes stale: fetch each missing one
# once, up front, and run with --action-offline-mode.
{ grep -rhoE "uses: *[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+@[0-9a-f]{40}" "$WORK/.github/workflows" || true; } | sed -E 's/uses: *//' | sort -u | while read -r use; do
  repo=${use%@*} sha=${use#*@} dir="$HOME/.cache/act/${repo//\//-}@$sha"
  [ -d "$dir" ] && continue
  git init -q "$dir" && git -C "$dir" fetch -q --depth 1 "https://github.com/$repo" "$sha" && git -C "$dir" checkout -q FETCH_HEAD \
    || { rm -rf "$dir"; echo "ci-local: could not prefetch $use (act will fetch it)" >&2; }
done
set +e
(cd "$WORK" && act "$EVENT" -e "$EV" \
  -P ubuntu-latest=catthehacker/ubuntu:act-24.04 -P ubuntu-24.04=catthehacker/ubuntu:act-24.04 \
  --container-options "--cpus 2 --memory 7g" \
  --pull=false --artifact-server-path "$ROOT/.artifacts" \
  --action-offline-mode \
  "${ACT_ARGS[@]}") > "$LOG" 2>&1
RC=$?
set -e
# One line per job: act prints "🏁  Job succeeded" / "Job failed" after the job name.
grep -aE "Job (succeeded|failed)" "$LOG" | sed -E 's/^\[([^]]+)\].*Job (succeeded|failed).*/\2  \1/' | sort -u || true
echo "ci-local: exit $RC"
exit $RC

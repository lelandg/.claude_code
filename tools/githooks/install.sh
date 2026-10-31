#!/bin/sh
# Install these as your GLOBAL git hooks: copy them to a directory outside any
# repo and point core.hooksPath at it, in every git you use on this machine.
#
#   sh tools/githooks/install.sh                 # -> ~/.githooks
#   sh tools/githooks/install.sh /opt/githooks   # -> a directory you pick
#   GIT_HOOKS_DEST=~/dev/.githooks sh tools/githooks/install.sh
#
# Idempotent, and safe to re-run -- do re-run it after editing any hook, since
# git executes the installed copy and not the one in this repo.
#
# Why global rather than per-repo: a secret gate that only guards the repos you
# remembered to wire up is not a gate. core.hooksPath applies to every repo this
# git touches, including ones you clone next week.
#
# The trade that buys: setting core.hooksPath makes git IGNORE each repo's own
# .git/hooks entirely. That is why every hook here sources _lib.sh and calls
# chain_local_hook, which runs the repo-local hook of the same name if there is
# one. Without that chaining, installing these would silently disable every
# repo-local hook on the machine -- Husky, lefthook, pre-commit framework, and
# anything a teammate added.
set -e

SRC=$(cd "$(dirname "$0")" && pwd)
DEST=${1:-${GIT_HOOKS_DEST:-$HOME/.githooks}}

case "$DEST" in
  "") echo "install.sh: empty destination" >&2; exit 1 ;;
esac

# Refuse to install into a git repo: hooks are machine state, and a repo's
# .git/hooks is not what core.hooksPath should point at.
if ( cd "$DEST" 2>/dev/null && git rev-parse --git-dir >/dev/null 2>&1 ); then
  echo "install.sh: $DEST is inside a git repository; pick a directory outside one" >&2
  exit 1
fi

mkdir -p "$DEST/usage"
for f in "$SRC"/*; do
  name=$(basename "$f")
  case "$name" in
    install.sh|README.md|test-pre-commit.sh) continue ;;
  esac
  cp "$f" "$DEST/"
  chmod +x "$DEST/$name"
done

git config --global core.hooksPath "$DEST"
printf 'git:     core.hooksPath = %s\n' "$(git config --global --get core.hooksPath)"

# Git for Windows is a separate install with its own global config, so a WSL-only
# install leaves every commit made from Windows unguarded. Set both.
WINGIT="/mnt/c/Program Files/Git/cmd/git.exe"
if [ -x "$WINGIT" ]; then
  WINDEST=$(printf '%s' "$DEST" | sed -E 's#^/mnt/([a-z])/#\U\1:/#')
  "$WINGIT" config --global core.hooksPath "$WINDEST"
  printf 'win git: core.hooksPath = %s\n' "$("$WINGIT" config --global --get core.hooksPath | tr -d '\r')"
fi

printf '\nInstalled to %s\n' "$DEST"

# The secret gate fails closed, so a missing gitleaks blocks every commit. Say
# so now rather than at the first commit.
if command -v gitleaks >/dev/null 2>&1; then
  printf 'gitleaks: %s\n' "$(gitleaks version 2>&1 | head -n1)"
else
  cat >&2 <<'EOF'

WARNING: gitleaks is not on PATH, and the pre-commit hook FAILS CLOSED -- it
blocks a commit it could not scan, not just one with a secret in it. Install it
before your next commit:

  winget install --id Gitleaks.Gitleaks --scope user    # Windows
  brew install gitleaks                                 # macOS
  # or a release binary from github.com/gitleaks/gitleaks on PATH

To commit once without a trustworthy scan: GITLEAKS_DEGRADED_OK=1 git commit ...
(it passes a degraded scan, never a found secret -- say why in the message).
EOF
fi

if ! command -v snyk >/dev/null 2>&1; then
  printf '\nNote: snyk is not on PATH. The dependency checks are skipped silently;\n'
  printf 'gitleaks still runs. That is a supported configuration.\n'
fi

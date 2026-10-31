#!/bin/sh
# Self-test for the pre-commit hook: the dependency-delta logic, the Snyk Code
# source gate, and the secret gate. Runs the CANONICAL hook next to this script
# (not the installed copy) in a throwaway repo. No Snyk quota is spent: most
# cases use SNYK_HOOK_MODE=off, and the end-to-end cases put a stub `snyk`
# first on PATH. Needs git, node, and gitleaks on PATH.
#
#   sh tools/githooks/test-pre-commit.sh
#
# Exit 0 when every case passes, 1 otherwise. Add a case here before changing
# deps_changed(), staged_files(), or code_staged(); the table in
# The helpers are tested by
# extracting the hook text between `DEPS_JS=` and `# ---- 1. Open Source`, so
# any new helper must be defined inside that window. tools/githooks/README.md
# explains what each case is guarding.
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
HOOK="$HERE/pre-commit"
T=$(mktemp -d)
F=$(mktemp)   # extracted hook functions live OUTSIDE the temp repo: reset_tree runs git clean
trap 'rm -rf "$T" "$F"' EXIT INT TERM
FAIL=0
pass() { printf 'ok    %s\n' "$1"; }
fail() { printf 'FAIL  %s\n' "$1"; FAIL=1; }
# `git hook run` arrived in Git 2.36. On anything older it is an unknown
# subcommand, and that is far worse than it sounds: git fails before any hook
# runs, so every case asserting a BLOCKED commit passes for the wrong reason --
# the non-zero exit came from git, not from the gate. A suite that reports a
# working secret gate on a machine where it never ran is worse than no suite.
# Ubuntu 22.04 LTS still ships 2.34, so this is not hypothetical.
#
# Rather than refuse to run, fall back to invoking the hook the way git would:
# these cases call pre-commit with no arguments. The interception lives in `g`
# so the call sites, with their inline env prefixes, stay untouched.
# TEST_NO_HOOK_RUN=1 forces the fallback on a modern git, so the old-git path is
# exercisable rather than taken on trust. Run the suite both ways after touching
# either branch.
GIT_MM=$(git --version | sed -E 's/^[^0-9]*([0-9]+)\.([0-9]+).*/\1 \2/')
# shellcheck disable=SC2086
set -- $GIT_MM
if [ "${TEST_NO_HOOK_RUN:-0}" = 1 ]; then
  HAVE_HOOK_RUN=0
  printf 'note  TEST_NO_HOOK_RUN=1: exercising the pre-2.36 fallback\n'
elif [ "$1" -gt 2 ] 2>/dev/null || { [ "$1" -eq 2 ] && [ "$2" -ge 36 ]; } 2>/dev/null; then
  HAVE_HOOK_RUN=1
else
  HAVE_HOOK_RUN=0
  printf 'note  git %s.%s has no `git hook run`; invoking hooks directly\n' "$1" "$2"
fi
g() {
  if [ "$HAVE_HOOK_RUN" = 0 ] && [ "$1" = hook ] && [ "$2" = run ]; then
    _hp=$(git -C "$T" config core.hooksPath 2>/dev/null)
    [ -n "$_hp" ] || _hp="$(git -C "$T" rev-parse --absolute-git-dir)/hooks"
    _hn=$3; shift 3
    ( cd "$T" && sh "$_hp/$_hn" "$@" )
    return $?
  fi
  git -C "$T" "$@"
}
# Run deps_changed from the hook against the temp repo; echoes its exit code.
deps() { ( cd "$T" && . "$F" && deps_changed "$1" >/dev/null 2>&1; echo $? ); }
# Run code_staged from the hook against the temp repo; echoes its exit code.
code() { ( cd "$T" && . "$F" && code_staged >/dev/null 2>&1; echo $? ); }
# Does staged_files list this exact path, unquoted? Echoes grep's exit code.
lists() { ( cd "$T" && . "$F" && staged_files | grep -qxF "$1"; echo $? ); }
expect() { # expect <label> <got> <want>
  if [ "$2" = "$3" ]; then pass "$1 (rc=$2)"; else fail "$1 (rc=$2, want $3)"; fi
}
reset_tree() { g checkout -q -- . 2>/dev/null; g reset -q; g clean -qfd; }

for bin in git node gitleaks; do
  command -v "$bin" >/dev/null 2>&1 || { echo "missing: $bin"; exit 1; }
done

git init -q "$T"
g config user.email t@t.local
g config user.name t
g config core.hooksPath "$HERE"

# Fixtures: an npm manifest + lockfile, a Ruby manifest + lockfile, a pip manifest.
printf '{"name":"t","version":"1.0.0","dependencies":{"left-pad":"1.0.0","is-odd":"3.0.1"}}\n' > "$T/package.json"
printf '{"name":"t","version":"1.0.0","lockfileVersion":3,"packages":{"":{"name":"t","version":"1.0.0","dependencies":{"left-pad":"1.0.0","is-odd":"3.0.1"}},"node_modules/left-pad":{"version":"1.0.0","resolved":"x"},"node_modules/is-odd":{"version":"3.0.1","resolved":"y"}}}\n' > "$T/package-lock.json"
printf 'source "https://rubygems.org"\ngem "rake"\n' > "$T/Gemfile"
printf 'GEM\n  specs:\n    rake (13.0.0)\n' > "$T/Gemfile.lock"
printf 'requests==2.0.0\n' > "$T/requirements.txt"
g add -A
g commit -q --no-verify -m fixtures

# The hook's helper functions, extracted verbatim.
awk '/^DEPS_JS=/,/^# ---- 1\. Open Source/' "$HOOK" | awk '!/^# ---- 1/' > "$F"

# --- deps_changed ---------------------------------------------------------
printf '{"name":"t","version":"1.0.1","dependencies":{"left-pad":"1.0.0","is-odd":"3.0.1"}}\n' > "$T/package.json"; g add package.json
expect "T1 package.json: version only -> unchanged" "$(deps package.json)" 1; reset_tree

printf '{"name":"t","version":"1.0.0","dependencies":{"left-pad":"1.0.0","is-odd":"3.0.1","ms":"2.1.3"}}\n' > "$T/package.json"; g add package.json
expect "T2 package.json: dependency added -> changed" "$(deps package.json)" 0; reset_tree

printf '{"name":"t","version":"1.0.0","dependencies":{"is-odd":"3.0.1","left-pad":"1.0.0"}}\n' > "$T/package.json"; g add package.json
expect "T3 package.json: keys reordered -> unchanged" "$(deps package.json)" 1; reset_tree

printf '{"name":"t","version":"1.0.0","lockfileVersion":3,"packages":{"":{"name":"t","version":"1.0.0","dependencies":{"left-pad":"1.0.0","is-odd":"3.0.1"}},"node_modules/left-pad":{"version":"1.0.1","resolved":"x"},"node_modules/is-odd":{"version":"3.0.1","resolved":"y"}}}\n' > "$T/package-lock.json"; g add package-lock.json
expect "T4 package-lock.json only: transitive bump -> changed" "$(deps package.json)" 0; reset_tree

printf '{"name":"t","version":"1.0.1","dependencies":{"left-pad":"1.0.0","is-odd":"3.0.1"}}\n' > "$T/package.json"
printf '{"name":"t","version":"1.0.1","lockfileVersion":3,"packages":{"":{"name":"t","version":"1.0.1","dependencies":{"left-pad":"1.0.0","is-odd":"3.0.1"}},"node_modules/left-pad":{"version":"1.0.0","resolved":"x"},"node_modules/is-odd":{"version":"3.0.1","resolved":"y"}}}\n' > "$T/package-lock.json"
g add package.json package-lock.json
expect "T5 manifest + lockfile: root version only -> unchanged" "$(deps package.json)" 1; reset_tree

printf 'GEM\n  specs:\n    rake (13.0.1)\n' > "$T/Gemfile.lock"; g add Gemfile.lock
expect "T6 Gemfile.lock only -> changed" "$(deps Gemfile)" 0; reset_tree

printf 'requests==2.0.0\n-r extra.txt\n' > "$T/requirements.txt"; g add requirements.txt
expect "T7 requirements.txt: added -r line -> changed" "$(deps requirements.txt)" 0; reset_tree

# --- secret gate -----------------------------------------------------------
tok="ghp_$(LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c 36)"
printf 'token = "%s"\n' "$tok" > "$T/leak.txt"; g add leak.txt
SNYK_HOOK_MODE=off g hook run pre-commit >/dev/null 2>&1; rc=$?
expect "T8 staged fake GitHub PAT -> blocked" "$rc" 1

SNYK_SKIP=1 SNYK_HOOK_MODE=off g hook run pre-commit >/dev/null 2>&1; rc=$?
expect "T9 same, with SNYK_SKIP=1 -> still blocked (no env bypass)" "$rc" 1
reset_tree

printf 'hello\n' > "$T/ok.txt"; g add ok.txt
SNYK_HOOK_MODE=off g hook run pre-commit >/dev/null 2>&1; rc=$?
expect "T10 clean stage -> passes" "$rc" 0
reset_tree

# --- secret gate: fail-closed paths (added with the 2026-10-29 hardening) ---
# Two environments are needed. S is a stub dir placed FIRST on PATH, so the
# stub shadows the real binary: that covers "the scan errored". NOGL is PATH
# with every directory holding a gitleaks executable removed: that covers "no
# binary at all". Removing the directories, not one entry, handles a second
# install. Both live outside $T, which reset_tree cleans. SNYK_SKIP=1 makes the
# hook exit right after step 0, so these cases need nothing but git.
S=$(mktemp -d)
printf '#!/bin/sh\nexit 1\n' > "$S/gitleaks"; chmod +x "$S/gitleaks"
trap 'rm -rf "$T" "$F" "$S"' EXIT INT TERM
NOGL=$(printf '%s\n' "$PATH" | tr ':' '\n' | while IFS= read -r d; do
  [ -n "$d" ] || continue
  [ -x "$d/gitleaks" ] || [ -x "$d/gitleaks.exe" ] || printf '%s\n' "$d"
done | paste -sd: -)

# Every case below asserts the hook's own message, not just the exit code.
# Exit code alone is not enough: if NOGL were missing git, or still had a
# gitleaks, the hook would exit non-zero or zero for an unrelated reason and
# T21/T23 would pass for the wrong reason. The message names the code path.
saw() { # saw <label> <output> <needle>
  case "$2" in *"$3"*) pass "$1" ;; *) fail "$1 (no '$3' in output)" ;; esac
}

printf 'hello\n' > "$T/ok.txt"; g add ok.txt

# Guard: NOGL must really be "git yes, gitleaks no", or these three cannot run.
if ! ( PATH="$NOGL"; export PATH; command -v git >/dev/null 2>&1 ); then
  fail "T21-T23 unrunnable: removing the gitleaks directory also removed git"
elif ( PATH="$NOGL"; export PATH; command -v gitleaks >/dev/null 2>&1 ); then
  fail "T21-T23 unrunnable: a gitleaks is still on PATH after filtering"
else
  out=$( PATH="$NOGL"; export PATH; SNYK_SKIP=1 g hook run pre-commit 2>&1 ); rc=$?
  expect "T21 gitleaks absent -> blocked (fail closed)" "$rc" 1
  saw   "T21a ... and says so" "$out" "gitleaks not on PATH"

  out=$( PATH="$NOGL"; export PATH; GITLEAKS_DEGRADED_OK=1 SNYK_SKIP=1 g hook run pre-commit 2>&1 ); rc=$?
  expect "T22 gitleaks absent + GITLEAKS_DEGRADED_OK=1 -> passes unscanned" "$rc" 0
  saw   "T22a ... and warns it is unscanned" "$out" "committing UNSCANNED"

  out=$( PATH="$NOGL"; export PATH; GITLEAKS_DEGRADED_OK=false SNYK_SKIP=1 g hook run pre-commit 2>&1 ); rc=$?
  expect "T23 gitleaks absent + GITLEAKS_DEGRADED_OK=false -> blocked (only 1 enables)" "$rc" 1
  saw   "T23a ... and does not claim the override" "$out" "commit blocked"
fi

out=$( PATH="$S:$PATH"; export PATH; SNYK_SKIP=1 g hook run pre-commit 2>&1 ); rc=$?
expect "T24 scan errors (exit 1) -> blocked" "$rc" 1
saw   "T24a ... as a scan error, not a finding" "$out" "could not complete the scan"

out=$( PATH="$S:$PATH"; export PATH; GITLEAKS_DEGRADED_OK=1 SNYK_SKIP=1 g hook run pre-commit 2>&1 ); rc=$?
expect "T25 scan errors + GITLEAKS_DEGRADED_OK=1 -> passes unscanned" "$rc" 0
saw   "T25a ... and warns it is unscanned" "$out" "committing UNSCANNED"
reset_tree

# A finding exits 3 under --exit-code 3, and no override passes it.
tok2="ghp_$(LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c 36)"
printf 'token = "%s"\n' "$tok2" > "$T/leak2.txt"; g add leak2.txt
out=$(GITLEAKS_DEGRADED_OK=1 SNYK_SKIP=1 g hook run pre-commit 2>&1); rc=$?
expect "T26 staged PAT + GITLEAKS_DEGRADED_OK=1 -> still blocked (a finding is never overridable)" "$rc" 1
saw   "T26a ... as a finding, not a degraded scan" "$out" "found a secret"
reset_tree

# --- code_staged: Snyk Code runs only when source is staged ---------------
printf '# docs\n' > "$T/README.md"; printf 'a: 1\n' > "$T/c.yml"; g add README.md c.yml
expect "T11 docs + config only -> no source staged" "$(code)" 1; reset_tree
printf 'export const x = 1\n' > "$T/a.ts"; g add a.ts
expect "T12 a .ts file staged -> source staged" "$(code)" 0; reset_tree
printf '# docs\n' > "$T/README.md"; printf 'x = 1\n' > "$T/b.py"; g add README.md b.py
expect "T13 docs + a .py file -> source staged" "$(code)" 0; reset_tree
printf 'class A {}\n' > "$T/A.JAVA"; g add A.JAVA
expect "T14 upper-case extension -> source staged" "$(code)" 0; reset_tree
printf '1\n' > "$T/gone.js"; g add gone.js; g commit -q --no-verify -m gone; g rm -q gone.js
expect "T15 only a deletion staged -> no source staged" "$(code)" 1; reset_tree
g reset -q --hard HEAD~1
printf '{"name":"t","version":"1.0.2","dependencies":{"left-pad":"1.0.0","is-odd":"3.0.1"}}\n' > "$T/package.json"; g add package.json
expect "T16 release-style package.json bump -> no source staged" "$(code)" 1; reset_tree

# --- staged_files: non-ASCII paths come through unquoted (core.quotePath) ---
mkdir -p "$T/src"; printf 'export const y = 2\n' > "$T/src/café.ts"; g add src
expect "T17 non-ASCII .ts path -> source staged" "$(code)" 0; reset_tree
mkdir -p "$T/café"; printf '{"name":"c","version":"1.0.0"}\n' > "$T/café/package.json"; g add café
expect "T18 non-ASCII manifest dir -> listed unquoted for the manifest scan" "$(lists 'café/package.json')" 0; reset_tree

# --- end to end: the daily stamp, with a stub snyk (no quota spent) --------
# A copy of the hook runs from a temp dir: the usage counters write next to
# the hook, and the canonical tree must stay clean.
HK=$(mktemp -d); STUB=$(mktemp -d); LOG="$STUB/calls"
cp "$HOOK" "$HERE/_lib.sh" "$HK/"
printf '#!/bin/sh\necho "$*" >> "%s"\nexit 0\n' "$LOG" > "$STUB/snyk"; chmod +x "$STUB/snyk"; : > "$LOG"
g config core.hooksPath "$HK"
STAMPF="$(g rev-parse --absolute-git-dir)/snyk-code-stamp"; rm -f "$STAMPF"
printf '# docs\n' > "$T/README.md"; g add README.md
PATH="$STUB:$PATH" SNYK_HOOK_MODE=warn g hook run pre-commit >/dev/null 2>&1
ran=$(grep -c '^code test' "$LOG" 2>/dev/null); [ -f "$STAMPF" ] && st=1 || st=0
expect "T19 docs-only commit -> no Code run, no stamp" "$ran$st" 00; reset_tree
: > "$LOG"   # count only this case's calls
printf 'export const z = 3\n' > "$T/z.ts"; g add z.ts
PATH="$STUB:$PATH" SNYK_HOOK_MODE=warn g hook run pre-commit >/dev/null 2>&1
ran=$(grep -c '^code test' "$LOG" 2>/dev/null); [ -f "$STAMPF" ] && st=1 || st=0
expect "T20 then a source commit -> Code runs once, stamp written" "$ran$st" 11; reset_tree

# A Code finding has to survive the once-a-day skip. Carrying only the date lost
# the block: the finding stamped the day, the retry an hour later took the skip,
# FAIL started at 0 again, and in block mode the same commit went through with
# the finding unfixed.
printf '#!/bin/sh\necho "$*" >> "%s"\ncase "$*" in "code test"*) exit 1 ;; esac\nexit 0\n' "$LOG" > "$STUB/snyk"
chmod +x "$STUB/snyk"
rm -f "$STAMPF"; : > "$LOG"
printf 'export const a = 1\n' > "$T/a.ts"; g add a.ts
PATH="$STUB:$PATH" SNYK_HOOK_MODE=block g hook run pre-commit >/dev/null 2>&1
first=$?
expect "T27 Code finding -> blocked in block mode" "$first" 1
expect "T27a ... and the stamp records the verdict, not just the date" \
  "$(grep -c ':fail' "$STAMPF" 2>/dev/null)" 1
: > "$LOG"
PATH="$STUB:$PATH" SNYK_HOOK_MODE=block g hook run pre-commit >/dev/null 2>&1
second=$?
reran=$(grep -c '^code test' "$LOG" 2>/dev/null)
expect "T27b same-day retry -> still blocked, and no metered re-scan" "$second$reran" 10
reset_tree

# A repo-local hook must run under its own shebang, not forced through `sh`.
# Husky and the pre-commit framework both generate non-sh hooks, so forcing sh
# broke exactly the hooks the chaining exists to preserve. A python3 hook is the
# discriminator: run as `sh`, it is a syntax error and the commit fails.
printf '#!/bin/sh\nexit 0\n' > "$STUB/snyk"; chmod +x "$STUB/snyk"
# The interpreter is a stub we control, so the test needs no python/bash and
# does not depend on how any real interpreter resolves paths. Executed directly,
# the shebang runs the stub and the marker appears. Forced through `sh`, the
# shebang is just a comment, the body runs under sh, and no marker appears.
LOCALHOOKS="$(g rev-parse --absolute-git-dir)/hooks"; mkdir -p "$LOCALHOOKS"
MARK="$STUB/local-hook-ran"
printf '#!/bin/sh\nprintf ran > "%s"\nexit 0\n' "$MARK" > "$STUB/myterp"
chmod +x "$STUB/myterp"
printf '#!%s\nexit 0\n' "$STUB/myterp" > "$LOCALHOOKS/pre-commit"
chmod +x "$LOCALHOOKS/pre-commit"
rm -f "$MARK" "$STAMPF"
printf '# docs\n' > "$T/README.md"; g add README.md
PATH="$STUB:$PATH" SNYK_HOOK_MODE=off g hook run pre-commit >/dev/null 2>&1
rc=$?
[ -f "$MARK" ] && chained=1 || chained=0
expect "T28 a project hook runs under its own shebang, not forced through sh" "$rc$chained" 01
rm -f "$LOCALHOOKS/pre-commit" "$MARK"; reset_tree

g config core.hooksPath "$HERE"; rm -rf "$HK" "$STUB"

# core.hooksPath makes git ignore a repo's .git/hooks for EVERY event, so any
# client-side event without a forwarding hook here silently stops working in
# every repo on the machine. This guards the set rather than the behaviour: add
# the forwarder when you add an event, or this fails.
EXPECTED="applypatch-msg commit-msg post-applypatch post-checkout post-commit
post-index-change post-merge post-rewrite pre-applypatch pre-auto-gc
pre-commit pre-merge-commit pre-push pre-rebase prepare-commit-msg
push-to-checkout sendemail-validate"
missing=""
for h in $EXPECTED; do
  [ -f "$HERE/$h" ] || missing="$missing $h"
done
expect "T29 every client-side hook event is forwarded (missing:${missing:- none})" "${missing:-none}" none

# --- the pip opt-in, which shipped with no coverage at all ----------------
# `pip install -r` BUILDS packages, and a source distribution's build runs
# arbitrary code as the developer, so the switch has to be off by default and an
# emptied switch has to stay off. The second case is why these exist: the
# original used `${VAR:-...}`, which substitutes on EMPTY as well as unset, so
# an explicitly emptied switch fell through to an enabled git setting and ran
# the build. A one-character bug in a hook nobody was testing.
HK2=$(mktemp -d); STUB2=$(mktemp -d); LOG2="$STUB2/calls"
cp "$HOOK" "$HERE/_lib.sh" "$HK2/"
printf '#!/bin/sh
echo "$*" >> "%s"
exit 0
' "$LOG2" > "$STUB2/snyk"; chmod +x "$STUB2/snyk"; : > "$LOG2"
g config core.hooksPath "$HK2"
printf 'requests==2.31.0
' > "$T/requirements.txt"; g add requirements.txt

g config hook.snykPipInstall 0
out=$( unset SNYK_HOOK_PIP_INSTALL; PATH="$STUB2:$PATH" SNYK_HOOK_MODE=warn g hook run pre-commit 2>&1 )
saw "T30 changed requirements -> no pip install by default" "$out" "not installing it to test it"

g config hook.snykPipInstall 1
out=$( SNYK_HOOK_PIP_INSTALL= PATH="$STUB2:$PATH" SNYK_HOOK_MODE=warn g hook run pre-commit 2>&1 )
saw "T30a empty switch beats an enabled git setting -> still no pip install" "$out" "not installing it to test it"

# A GLOBAL setting must not enable it either: the README promises a
# PER-REPOSITORY opt-in, and plain `git config --get` reads local, then global,
# then system. GIT_CONFIG_GLOBAL points git at a throwaway file, so this proves
# the scoping without touching the developer's real ~/.gitconfig.
g config --unset hook.snykPipInstall 2>/dev/null
printf '[hook]
	snykPipInstall = 1
' > "$STUB2/fakeglobal"
out=$( unset SNYK_HOOK_PIP_INSTALL; GIT_CONFIG_GLOBAL="$STUB2/fakeglobal" PATH="$STUB2:$PATH" SNYK_HOOK_MODE=warn g hook run pre-commit 2>&1 )
saw "T30b a global setting does not enable it -> still no pip install" "$out" "not installing it to test it"

g config --unset hook.snykPipInstall 2>/dev/null
g config core.hooksPath "$HERE"; rm -rf "$HK2" "$STUB2"; reset_tree

[ "$FAIL" -eq 0 ] && echo "all cases pass" || echo "FAILURES above"
exit "$FAIL"

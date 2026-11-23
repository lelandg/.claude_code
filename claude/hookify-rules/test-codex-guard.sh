#!/usr/bin/env bash
# Test the block-unpinned-codex-rescue hookify rule end-to-end.
# Policy since 2026-09-22: block Sol / bare gpt-5.6 on any codex exec; Astra allowed.
# Run from any project whose .claude/ contains (or symlinks) the rule:
#   bash ~/.claude/hookify-rules/test-codex-guard.sh
# Exit code 0 = all cases behaved as expected.

set -u
HOOK_ROOT="$(ls -d "$HOME"/.claude/plugins/cache/claude-plugins-official/hookify/*/ | tail -1)"
HOOK_ROOT="${HOOK_ROOT%/}"

if [ ! -f ".claude/hookify.block-unpinned-codex-rescue.local.md" ]; then
  echo "FAIL: no .claude/hookify.block-unpinned-codex-rescue.local.md in $(pwd)"
  echo "      symlink it first:"
  echo "      ln -sf ~/.claude/hookify-rules/hookify.block-unpinned-codex-rescue.local.md .claude/"
  exit 1
fi

CLAUDE_PLUGIN_ROOT="$HOOK_ROOT" python3 - <<'EOF'
import json, subprocess, os, sys

HOOK = os.environ['CLAUDE_PLUGIN_ROOT'] + '/hooks/pretooluse.py'

# (label, command, expect_deny)
CASES = [
    ("unpinned rescue task (inherits Astra)", 'node "/x/codex-companion.mjs" task --background fix the bug', False),
    ("sol-pinned rescue task",    'node "/x/codex-companion.mjs" task --model gpt-5.6-sol fix it', True),
    ("bare-alias rescue task",    'node "/x/codex-companion.mjs" task --model gpt-5.6 fix it',   True),
    ("bare-alias with equals",    'node "/x/codex-companion.mjs" task --model=gpt-5.6 fix it',   True),
    ("direct codex exec sol",     'codex exec --model gpt-5.6-sol "investigate flaky test"',      True),
    ("direct codex exec unpinned",'codex exec "investigate flaky test"',                          False),
    ("astra-pinned rescue task",  'node "/x/codex-companion.mjs" task --model gpt-6-astra --effort high fix', False),
    ("terra-pinned rescue task",  'node "/x/codex-companion.mjs" task --model gpt-5.6-terra --effort high fix', False),
    ("review (Sol allowed)",      'node "/x/codex-companion.mjs" review --base origin/main',      False),
    ("CLI bare alias, short flag", 'codex exec -m gpt-5.6 -s workspace-write -C . - < task.md',  True),
    ("CLI astra rescue",          'codex exec -m gpt-6-astra -c model_reasoning_effort=high -s workspace-write -C . - < task.md', False),
    ("CLI astra review",          'codex exec -s read-only -C . review -m gpt-6-astra -c model_reasoning_effort=high --base origin/main', False),
    ("CLI sol review (agents never run Sol)", 'codex exec -s read-only -C . review -m gpt-5.6-sol --base origin/main', True),
    ("CLI bare alias then redirect", 'codex exec -s workspace-write "fix it" -m gpt-5.6>out.txt', True),
    ("CLI bare alias then semicolon", 'codex exec -m gpt-5.6; echo done',                       True),
    ("CLI bare alias, flag glued",  'codex exec -mgpt-5.6 -s workspace-write -C . - < task.md',  True),
    ("CLI bare alias via -c model", 'codex exec -c model="gpt-5.6" -s workspace-write - < task.md', True),
    ("CLI terra, short flag",     'codex exec -m gpt-5.6-terra -c model_reasoning_effort=high -s workspace-write -C . - < task.md', False),
    ("CLI astra with effort config", 'codex exec -m gpt-6-astra -c model_reasoning_effort=xhigh -s read-only - < p.md', False),
    ("CLI exec alias e, sol",     'codex e -m gpt-5.6-sol -s workspace-write "fix it"',           True),
    ("CLI model flag before exec", 'codex -m gpt-5.6 exec -s workspace-write "fix it"',          True),
    ("CLI escaped quotes in -c",  'codex exec -c model=\\"gpt-5.6\\" -s workspace-write "fix it"', True),
    ("CLI profile-style override", 'codex exec -c profiles.x.model=gpt-5.6 -s workspace-write - < t.md', True),
    ("CLI exec alias e, astra",   'codex e -m gpt-6-astra -s read-only - < p.md',                 False),
    ("codex login",               'codex login',                                                  False),
    ("unrelated command",         'git status',                                                   False),
]

failures = 0
for label, cmd, expect_deny in CASES:
    payload = json.dumps({
        "hook_event_name": "PreToolUse",   # matches real Claude Code invocation
        "tool_name": "Bash",
        "tool_input": {"command": cmd},
    })
    r = subprocess.run(['python3', HOOK], input=payload, capture_output=True, text=True)
    try:
        out = json.loads(r.stdout)
    except json.JSONDecodeError:
        print(f"FAIL {label}: non-JSON hook output: {r.stdout[:120]}")
        failures += 1
        continue
    denied = out.get('hookSpecificOutput', {}).get('permissionDecision') == 'deny'
    ok = denied == expect_deny
    verdict = 'DENY ' if denied else 'ALLOW'
    print(f"{'PASS' if ok else 'FAIL'}  {verdict} {label}")
    if not ok:
        failures += 1
        print(f"      raw: {r.stdout[:200]}")

print()
if failures:
    print(f"{failures} case(s) FAILED")
    sys.exit(1)
print("All cases behaved as expected.")
EOF

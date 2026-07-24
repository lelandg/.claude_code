#!/usr/bin/env bash
# Test the block-unpinned-codex-rescue hookify rule end-to-end.
# Run from any project whose .claude/ contains (or symlinks) the rule:
#   bash ~/.claude/hookify-rules/test-codex-guard.sh
# Exit code 0 = all cases behaved as expected.

set -u
HOOK_ROOT="$HOME/.claude/plugins/cache/claude-plugins-official/hookify/unknown"

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
    ("unpinned rescue task",      'node "/x/codex-companion.mjs" task --background fix the bug', True),
    ("sol-pinned rescue task",    'node "/x/codex-companion.mjs" task --model gpt-5.6-sol fix it', True),
    ("bare-alias rescue task",    'node "/x/codex-companion.mjs" task --model gpt-5.6 fix it',   True),
    ("direct codex exec unpinned",'codex exec "investigate flaky test"',                          True),
    ("terra-pinned rescue task",  'node "/x/codex-companion.mjs" task --model gpt-5.6-terra --effort high fix', False),
    ("luna-pinned rescue task",   'node "/x/codex-companion.mjs" task --model gpt-5.6-luna cleanup', False),
    ("review (Sol allowed)",      'node "/x/codex-companion.mjs" review --base origin/main',      False),
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

#!/usr/bin/env python3
"""PreToolUse guard: block printing/reading secret-bearing config files.

Wired globally in ~/.claude/settings.json (matcher: Bash|Read). Created after
the 2026-07-13 incident where `sed -n`/`diff` on a project's config.yaml (local
and over ssh) leaked API keys, a DB password, and the Discord bot token into
the conversation transcript.

Blocks:
  - Bash commands that combine a content-printing tool (cat/sed/head/tail/awk/
    diff/grep/...) with a secret-bearing filename (config*.yaml except
    config.example.yaml, or .env* except .env.example) — including inside ssh
    quoted commands, pipelines, and heredocs.
  - Read tool calls on those files.

Escape hatch: append `# config-ok` to a Bash command for a human-approved
exception (e.g. an in-place `sed -i` edit that prints nothing).

Safe alternative: python3 ~/.claude/tools/safe-config-reader.py <file>
(structure + booleans/numbers only, every string masked), or
  ... --key some.nested.key   for a single setting.

This is a guardrail against accidental exposure, not a sandbox.
"""
import json
import re
import sys

PRINT_TOOLS = (
    r"\b(?:cat|sed|awk|head|tail|less|more|diff|sdiff|comm|grep|egrep|fgrep|rg"
    r"|bat|strings|nl|od|xxd|hexdump|paste|column|sort|uniq|tac|cut|tee)\b"
)
# config*.yaml (not config.example.yaml) or .env / .env.* (not .env.example)
SECRET_FILE = (
    r"(?:config(?!\.example)[\w.-]*\.ya?ml"
    r"|\.env(?!\.example|ironment)(?:\.(?!example)[\w.-]+)?)"
)
SECRET_FILE_RE = re.compile(SECRET_FILE + r"\b")
PRINT_TOOLS_RE = re.compile(PRINT_TOOLS)
OVERRIDE = "# config-ok"

DENY_MSG = (
    "Blocked: this would print contents of a secret-bearing config file "
    "(config*.yaml / .env*) into the transcript — API keys and passwords "
    "leaked exactly this way on 2026-07-13. Use "
    "`python3 ~/.claude/tools/safe-config-reader.py <file>` for structure "
    "with values masked, or `--key a.b.c` for one setting. For a write-only "
    "command that must touch the file (e.g. `sed -i`), have the human approve "
    "appending `# config-ok` to the command."
)


def deny() -> None:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": DENY_MSG,
        }
    }))
    sys.exit(0)


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)  # malformed input — never block on guard failure
    tool = data.get("tool_name", "")
    tool_input = data.get("tool_input") or {}

    if tool == "Read":
        basename = (tool_input.get("file_path") or "").rsplit("/", 1)[-1]
        if re.fullmatch(SECRET_FILE, basename):
            deny()
    elif tool == "Bash":
        command = tool_input.get("command") or ""
        if OVERRIDE in command:
            sys.exit(0)
        if SECRET_FILE_RE.search(command) and PRINT_TOOLS_RE.search(command):
            deny()
    sys.exit(0)


if __name__ == "__main__":
    main()

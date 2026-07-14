#!/usr/bin/env python3
"""PreToolUse guard: block printing/reading secret-bearing config files.

Wired globally for multiple coding CLIs:
  - Claude Code: ~/.claude/settings.json hooks (PreToolUse, matcher Bash|Read)
  - Codex CLI:   ~/.codex/hooks.json — same hook protocol as Claude Code
                 (stdin tool_name/tool_input, hookSpecificOutput deny JSON)
  - Antigravity: ~/.gemini/config/hooks.json — run with --agy (different
                 protocol: stdin toolCall.name/.args, stdout {"decision": ...})
  - Pi:          ~/.pi/agent/extensions/config-secrets-guard.ts — TypeScript
                 port of these regexes (keep in sync by hand)

Created after the 2026-07-13 incident where `sed -n`/`diff` on a project's
config.yaml (local and over ssh) leaked API keys, a DB password, and the
Discord bot token into the conversation transcript.

Blocks:
  - Shell commands that combine a content-printing tool (cat/sed/head/tail/awk/
    diff/grep/...) with a secret-bearing filename (config*.yaml except
    config.example.yaml, or .env* except .env.example) — including inside ssh
    quoted commands, pipelines, and heredocs.
  - Read-style tool calls on those files.

Escape hatch: append `# config-ok` to a shell command for a human-approved
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

# Tool-name sets for the Claude/Codex protocol (Codex names its shell tool
# variously across versions; unknown tools are simply ignored).
BASH_TOOLS = {"Bash", "shell", "local_shell"}
READ_TOOLS = {"Read", "read_file", "view_file"}

DENY_MSG = (
    "Blocked: this would print contents of a secret-bearing config file "
    "(config*.yaml / .env*) into the transcript — API keys and passwords "
    "leaked exactly this way on 2026-07-13. Use "
    "`python3 ~/.claude/tools/safe-config-reader.py <file>` for structure "
    "with values masked, or `--key a.b.c` for one setting. For a write-only "
    "command that must touch the file (e.g. `sed -i`), have the human approve "
    "appending `# config-ok` to the command."
)


def command_is_blocked(command: str) -> bool:
    if OVERRIDE in command:
        return False
    return bool(SECRET_FILE_RE.search(command) and PRINT_TOOLS_RE.search(command))


def path_is_blocked(path: str) -> bool:
    basename = path.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    return bool(re.fullmatch(SECRET_FILE, basename))


def main_claude(data: dict) -> None:
    """Claude Code / Codex CLI protocol: deny via hookSpecificOutput JSON."""
    tool = data.get("tool_name", "")
    tool_input = data.get("tool_input") or {}
    blocked = False
    if tool in READ_TOOLS:
        blocked = path_is_blocked(tool_input.get("file_path") or "")
    elif tool in BASH_TOOLS:
        blocked = command_is_blocked(tool_input.get("command") or "")
    if blocked:
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": DENY_MSG,
            }
        }))
    sys.exit(0)


def main_agy(data: dict) -> None:
    """Antigravity (agy) protocol: stdin toolCall.{name,args}, stdout decision."""
    tool_call = data.get("toolCall") or {}
    name = tool_call.get("name") or ""
    args = tool_call.get("args") or {}
    command = args.get("CommandLine")
    if isinstance(command, str) and command:
        blocked = command_is_blocked(command)
    elif any(word in name.lower() for word in ("read", "view", "open")):
        # Read-style tool: any string arg that IS a secret-bearing filename.
        blocked = any(isinstance(v, str) and path_is_blocked(v) for v in args.values())
    else:
        blocked = False
    if blocked:
        print(json.dumps({"decision": "deny", "reason": DENY_MSG}))
    else:
        print(json.dumps({"decision": "allow"}))
    sys.exit(0)


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)  # malformed input — never block on guard failure
    if not isinstance(data, dict):
        sys.exit(0)
    if "--agy" in sys.argv[1:]:
        main_agy(data)
    else:
        main_claude(data)


if __name__ == "__main__":
    main()

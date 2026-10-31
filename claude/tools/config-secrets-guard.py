#!/usr/bin/env python3
"""PreToolUse guard: block tool calls that would print secrets into the transcript.

Wired globally for multiple coding CLIs:
  - Claude Code: ~/.claude/settings.json hooks (PreToolUse, matcher Bash|Read|Grep)
  - Codex CLI:   ~/.codex/hooks.json — same hook protocol as Claude Code
                 (stdin tool_name/tool_input, hookSpecificOutput deny JSON)
  - Antigravity: ~/.gemini/config/hooks.json — run with --agy (different
                 protocol: stdin toolCall.name/.args, stdout {"decision": ...})
  - Pi:          ~/.pi/agent/extensions/config-secrets-guard.ts — TypeScript
                 port of these regexes (keep in sync by hand; the 2026-10-23
                 additions below are NOT yet ported)

Created after the 2026-07-13 incident where `sed -n`/`diff` on a project's
config.yaml (local and over ssh) leaked API keys, a DB password, and the
Discord bot token into the conversation transcript. Extended 2026-10-23 to
enforce the AWS, Stripe and env-dump rules in ~/.config/agents/AGENTS.md at
the tool boundary instead of trusting the model to remember them.

Blocks:
  - Shell commands that combine a content-printing tool (cat/sed/head/tail/awk/
    diff/grep/...) with a secret-bearing filename (config*.yaml except
    config.example.yaml, or .env* except .env.example) — including inside ssh
    quoted commands, pipelines, and heredocs. `process.env.X` and
    `import.meta.env.X` are code, not files, and never match.
  - Read-style tool calls on those files, and Grep calls aimed at them.
  - Environment dumps: bare `env`, `printenv`, `export -p`, `set` with no
    arguments, PowerShell `Get-ChildItem Env:` / `gci env:` / `ls env:`.
  - AWS calls that return secret values: `aws amplify get-app|get-branch`
    without a `--query` projection, any amplify command carrying environment
    variables (inline values land in the transcript too), `aws ssm
    get-parameter(s)` / `get-parameters-by-path` with `--with-decryption`, and
    the Secrets Manager get-secret-value call.
  - Live-money Stripe CLI mutations: `stripe <resource> create|update|delete|
    cancel|refund|capture|confirm|pay|void ...` (reads like `list`/`retrieve`
    pass).

Escape hatches, each a human-approved exception appended to the command:
  `# config-ok`  secret-file read that prints nothing (e.g. an in-place sed -i)
  `# env-ok`     an env dump the human wants to see
  `# aws-ok`     an AWS secret read the human asked for
  `# stripe-ok`  a Stripe mutation the human asked for

Safe alternative for config files: python3 ~/.claude/tools/safe-config-reader.py
<file> (structure + booleans/numbers only, every string masked), or
  ... --key some.nested.key   for a single setting.

This is a guardrail against accidental exposure, not a sandbox.
"""
import fnmatch
import json
import re
import sys

PRINT_TOOLS = (
    r"\b(?:cat|sed|awk|head|tail|less|more|diff|sdiff|comm|grep|egrep|fgrep|rg"
    r"|bat|strings|nl|od|xxd|hexdump|paste|column|sort|uniq|tac|cut|tee"
    # PowerShell readers and their aliases (Claude Code's PowerShell tool on
    # Windows). PowerShell command names are case-insensitive, so `get-content`
    # must match as surely as `Get-Content`.
    r"|(?i:Get-Content|gc|type|Select-String|sls|Format-Hex|Compare-Object))\b"
)
# config*.yaml (not config.example.yaml) or .env / .env.* (not .env.example).
# `process.env.X` / `import.meta.env.X` are code references, not dotenv files.
SECRET_FILE = (
    r"(?:config(?!\.example)[\w.-]*\.ya?ml"
    r"|(?<!process)(?<!import\.meta)\.env(?!\.example|ironment)(?:\.(?!example)[\w.-]+)?)"
)
SECRET_FILE_RE = re.compile(SECRET_FILE + r"\b")
PRINT_TOOLS_RE = re.compile(PRINT_TOOLS)

# A command segment is the text between shell separators; a bare dump is a
# segment that is exactly the dump command, so `set -e` and `env VAR=x cmd`
# pass. A newline is a separator like `;`, leading indentation is ordinary
# formatting, and a trailing `#` comment still leaves the dump bare — so
# `pwd\n  env  # note` is a dump, not a pass.
_SEG = r"(?:^\s*|[\n;&|]\s*|\$\(\s*|`\s*)"
_END = r"\s*(?:$|[\n;&|)>`]|#)"
# The PowerShell form enumerates the provider only when the path is bare or
# wildcarded: `Env:PATH` is the named single-variable read this guard tells you
# to use instead, so it must not be mistaken for a dump.
ENV_DUMP_RE = re.compile(
    _SEG + r"(?:env|printenv|export\s+-p|set)" + _END
    + r"|\b(?:Get-ChildItem|gci|ls|dir)\s+(?:-Path\s+)?Env:(?:\*|$|[\s;&|)>`])",
    re.IGNORECASE | re.MULTILINE,
)

# Global options may sit between a CLI and its subcommand, and they are exactly
# where a bypass hides: `aws --region us-east-1 amplify get-app` and
# `stripe --live charges create` are ordinary spellings of the calls below.
_GLOBAL_OPTS = r"(?:--[\w-]+(?:[=\s]+[^\s-][^\s]*)?\s+)*"
_AWS = r"\baws\s+" + _GLOBAL_OPTS
_AWS_SECRET_SVC = "secrets" + "manager"  # split so other guards don't match this file's text

AMPLIFY_READ_RE = re.compile(
    _AWS + r"amplify\s+" + _GLOBAL_OPTS + r"(?:get-app|get-branch)\b"
)
AWS_SECRET_RE = re.compile(
    _AWS + r"amplify\s+[^\n;&|]*(?i:environment-?variables)"
    r"|" + _AWS + r"ssm\s+" + _GLOBAL_OPTS
    + r"get-parameters?(?:-by-path)?\b[^\n;&|]*--with-decryption"
    r"|" + _AWS + _AWS_SECRET_SVC + r"\s+" + _GLOBAL_OPTS + r"get-secret-value\b",
)

# A `--query` projection redacts only when the *whole* argument names scalar
# fields. A prefix test is not enough: `--query 'app.name && app'` starts with a
# safe-looking path and still returns the entire object, environment-variable
# values and all. `app`, `app.*` and anything naming `environment` are not
# redaction either.
_QUERY_ARG_RE = re.compile(r"--query(?:=|\s+)(\"[^\"]*\"|'[^']*'|\S+)")
_SAFE_PROJECTION_RE = re.compile(r"[\w\[\]-]+(?:\.[\w\[\]-]+)+")


def query_redacts_values(command: str) -> bool:
    """True when every --query argument in the command names scalar fields only."""
    args = _QUERY_ARG_RE.findall(command)
    if not args:
        return False
    for arg in args:
        projection = arg.strip("\"'")
        if not _SAFE_PROJECTION_RE.fullmatch(projection):
            return False
        if "environment" in projection.lower():
            return False
    return True


STRIPE_MUTATION_RE = re.compile(
    r"\bstripe\s+" + _GLOBAL_OPTS + r"(?!--)[\w-]+\s+"
    r"(?:create|update|delete|del|cancel|refund|capture|confirm|pay|void)\b"
)

OVERRIDES = {
    "config": "# config-ok",
    "env": "# env-ok",
    "aws": "# aws-ok",
    "stripe": "# stripe-ok",
}

# Tool-name sets for the Claude/Codex protocol (Codex names its shell tool
# variously across versions; unknown tools are simply ignored).
# Codex 2026-10 runs shell through exec_command ({"cmd": ...}) and a JS "exec"
# wrapper whose input is a code string; Claude Code on Windows has PowerShell.
BASH_TOOLS = {"Bash", "shell", "local_shell", "exec_command", "exec", "PowerShell"}
READ_TOOLS = {"Read", "read_file", "view_file"}
GREP_TOOLS = {"Grep"}

SAFE_READER = (
    "Use `python3 ~/.claude/tools/safe-config-reader.py <file>` for structure "
    "with values masked, or `--key a.b.c` for one setting."
)
DENY_MSGS = {
    "config": (
        "Blocked: this would print contents of a secret-bearing config file "
        "(config*.yaml / .env*) into the transcript — API keys and passwords "
        "leaked exactly this way on 2026-07-13. " + SAFE_READER + " For a "
        "write-only command that must touch the file (e.g. `sed -i`), have the "
        "human approve appending `# config-ok` to the command."
    ),
    "env": (
        "Blocked: a bare environment dump prints every secret in the shell "
        "into the transcript. Read one variable by name (`printenv NAME`), or "
        "have the human approve appending `# env-ok`."
    ),
    "aws": (
        "Blocked: this AWS call returns or carries secret values (Amplify env "
        "vars, decrypted SSM parameters, or a Secrets Manager secret). Use a "
        "`--query` projection that omits values, admin tooling that keeps "
        "values out of the transcript by design, or have the human approve "
        "appending `# aws-ok`. Rule: AGENTS.md → Cloud / infrastructure safety."
    ),
    "stripe": (
        "Blocked: treat Stripe as live; a CLI mutation moves real money or "
        "changes live prices. The human runs Stripe mutations in their own "
        "terminal. "
        "Reads (list/retrieve) are fine. Human-approved exception: append "
        "`# stripe-ok`."
    ),
}


def classify_command(command: str):
    """Return the category that blocks this command, or None."""
    if SECRET_FILE_RE.search(command) and PRINT_TOOLS_RE.search(command):
        if OVERRIDES["config"] not in command:
            return "config"
    if ENV_DUMP_RE.search(command) and OVERRIDES["env"] not in command:
        return "env"
    if OVERRIDES["aws"] not in command:
        if AWS_SECRET_RE.search(command):
            return "aws"
        if AMPLIFY_READ_RE.search(command) and not query_redacts_values(command):
            return "aws"
    if STRIPE_MUTATION_RE.search(command) and OVERRIDES["stripe"] not in command:
        return "stripe"
    return None


def command_is_blocked(command: str) -> bool:
    return classify_command(command) is not None


def path_is_blocked(path: str) -> bool:
    basename = path.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    return bool(re.fullmatch(SECRET_FILE, basename))


# A glob is blocked when it *can select* a protected file, which is not the
# same as spelling one out: `*.yaml` and `*` reach `config.yaml` without ever
# naming it. So instead of pattern-matching the pattern, match the pattern
# against names a protected file actually has. The probes cover both families
# and both the literal and the `[\w.-]*` middle of SECRET_FILE, so a pattern
# pinned to `.example` still selects nothing protected and passes.
_PROTECTED_PROBES = (
    "config.yaml", "config.yml",
    "config.local.yaml", "config.local.yml",
    "configx.yaml", "configx.yml",
    ".env", ".envx", ".env.local", ".env.production",
)


def glob_is_blocked(glob: str) -> bool:
    """True when the glob can select a file `path_is_blocked` would protect."""
    if not glob:
        return False
    basename = glob.replace("\\", "/").rsplit("/", 1)[-1].lower()
    if not any(ch in basename for ch in "*?["):
        return bool(re.fullmatch(SECRET_FILE, basename))
    return any(fnmatch.fnmatchcase(probe, basename) for probe in _PROTECTED_PROBES)


def grep_is_blocked(tool_input: dict) -> bool:
    """Grep aimed at a secret file by path or by glob prints its matching lines."""
    path = tool_input.get("path") or ""
    glob = tool_input.get("glob") or ""
    return (
        path_is_blocked(path)
        or glob_is_blocked(glob)
        or bool(SECRET_FILE_RE.search(glob))
    )


def deny(reason: str) -> None:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }))


def main_claude(data: dict) -> None:
    """Claude Code / Codex CLI protocol: deny via hookSpecificOutput JSON."""
    tool = data.get("tool_name", "")
    tool_input = data.get("tool_input") or {}
    if isinstance(tool_input, str):  # Codex "exec": the input is the code itself
        tool_input = {"command": tool_input}
    category = None
    if tool in READ_TOOLS:
        if path_is_blocked(tool_input.get("file_path") or ""):
            category = "config"
    elif tool in GREP_TOOLS:
        if grep_is_blocked(tool_input):
            category = "config"
    elif tool in BASH_TOOLS:
        command = tool_input.get("command") or tool_input.get("cmd") or ""
        # Some Codex versions send argv (["bash", "-lc", "<script>"]): check each
        # element on its own so a dump at the start of the script still matches.
        parts = [str(c) for c in command] if isinstance(command, list) else [command]
        category = next(filter(None, map(classify_command, parts)), None)
    if category:
        deny(DENY_MSGS[category])
    sys.exit(0)


def main_agy(data: dict) -> None:
    """Antigravity (agy) protocol: stdin toolCall.{name,args}, stdout decision."""
    tool_call = data.get("toolCall") or {}
    name = tool_call.get("name") or ""
    args = tool_call.get("args") or {}
    command = args.get("CommandLine")
    category = None
    if isinstance(command, str) and command:
        category = classify_command(command)
    elif any(word in name.lower() for word in ("read", "view", "open", "grep", "search")):
        # Read-style tool: any string arg that IS a secret-bearing filename.
        if any(isinstance(v, str) and path_is_blocked(v) for v in args.values()):
            category = "config"
    if category:
        print(json.dumps({"decision": "deny", "reason": DENY_MSGS[category]}))
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

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
# Case-insensitive, because Windows filenames are: `Get-Content .ENV` reads the
# same bytes as `Get-Content .env`, and `CONFIG.YAML` the same as `config.yaml`.
# The cost is that `PROCESS.ENV.FOO` shouted in prose can false-positive, which
# is the right direction to be wrong in.
SECRET_FILE_RE = re.compile(SECRET_FILE + r"\b", re.IGNORECASE)
PRINT_TOOLS_RE = re.compile(PRINT_TOOLS)

# A command segment is the text between shell separators; a bare dump is a
# segment that is exactly the dump command, so `set -e` and `env VAR=x cmd`
# pass. A newline is a separator like `;`, leading indentation is ordinary
# formatting, and a trailing `#` comment still leaves the dump bare — so
# `pwd\n  env  # note` is a dump, not a pass.
_SEG = r"(?:^\s*|[\n;&|]\s*|\$\(\s*|`\s*)"
_END = r"\s*(?:$|[\n;&|)>`]|#)"
# The PowerShell form enumerates the provider only when the path is bare, the
# provider root, or wildcarded — quoting and a trailing separator are ordinary
# spellings of all three (`'Env:'`, `Env:\`). `Env:PATH` is the named
# single-variable read this guard tells you to use instead, so it must not be
# mistaken for a dump: a guard that contradicts its own advice teaches people to
# reach for the override.
ENV_DUMP_RE = re.compile(
    _SEG + r"(?:env|printenv|export\s+-p|set)" + _END
    + r"|\b(?:Get-ChildItem|gci|ls|dir)\s+(?:-Path\s+)?[\"']?Env:[\\/]?"
    + r"(?:\*|[\"']|$|[\s;&|)>`])",
    re.IGNORECASE | re.MULTILINE,
)

# Shell separators split one command line into independently-executed calls.
# Every category below is judged per segment, because a safe-looking flag on one
# call says nothing about the next: `aws amplify get-app --query app.name;
# aws amplify get-branch ...` has one safe projection and two reads.
#
# Splitting has to respect quoting. A regex split on the separators tore
# `--query 'app.name && app'` in half and handed the first fragment a
# `--query 'app.name` that then looked allowlisted — the separators were inside
# an argument, not between calls. This is a guardrail, not a shell parser:
# backslash escapes are not handled, and an unbalanced quote simply runs to the
# end of the string, which keeps the segment larger and so blocks more.
def segments(command: str):
    """The command's separator-delimited calls, each judged on its own."""
    found, buf, quote, i = [], [], None, 0
    while i < len(command):
        char = command[i]
        # A backslash escapes the next character outside single quotes, so a
        # `\'` is a literal quote and must not open a quoted run -- otherwise
        # the rest of the line hides inside a quote that the shell never saw,
        # and every separator in it disappears.
        if char == "\\" and quote != "'" and i + 1 < len(command):
            buf.append(char)
            buf.append(command[i + 1])
            i += 2
            continue
        if quote is not None:
            buf.append(char)
            if char == quote:
                quote = None
        elif char in "\"'":
            quote = char
            buf.append(char)
        elif char in ";\n":
            found.append("".join(buf))
            buf = []
        elif char in "&|":
            found.append("".join(buf))
            buf = []
            if i + 1 < len(command) and command[i + 1] == char:
                i += 1  # `&&` and `||` are one separator, not two
        else:
            buf.append(char)
        i += 1
    found.append("".join(buf))
    return [segment for segment in found if segment.strip()]

# Global options may sit between a CLI and its subcommand, and they are exactly
# where a bypass hides: `aws --region us-east-1 amplify get-app` and
# `stripe --live charges create` are ordinary spellings of the calls below.
_GLOBAL_OPTS = r"(?:--[\w-]+(?:[=\s]+[^\s-][^\s]*)?\s+)*"
_AWS = r"\baws\s+" + _GLOBAL_OPTS
_AWS_SECRET_SVC = "secrets" + "manager"  # split so other guards don't match this file's text

# The list forms leak strictly more than the get forms, which is easy to miss
# because the guard's name is about *reading* a thing: per the ListApps API
# reference, each element of `apps` is a full App object carrying
# `environmentVariables` and `basicAuthCredentials`, so `list-apps` hands over
# every app's secrets rather than one app's. Same for `list-branches`.
AMPLIFY_READ_RE = re.compile(
    _AWS + r"amplify\s+" + _GLOBAL_OPTS
    + r"(?:get-app|get-branch|list-apps|list-branches)\b"
)
AWS_SECRET_RE = re.compile(
    _AWS + r"amplify\s+[^\n;&|]*(?i:environment-?variables)"
    r"|" + _AWS + r"ssm\s+" + _GLOBAL_OPTS
    + r"get-parameters?(?:-by-path)?\b[^\n;&|]*--with-decryption"
    r"|" + _AWS + _AWS_SECRET_SVC + r"\s+" + _GLOBAL_OPTS + r"get-secret-value\b",
)

# A projection is an *allowlist*, not a pattern test. Two earlier attempts here
# were denylist-shaped and both leaked: a prefix test let `app.name && app`
# through, and "any dotted path without the word environment" let
# `app.basicAuthCredentials` through — base64 basic-auth credentials, no
# `environment` anywhere in the name. The shape of a projection cannot establish
# that its value is safe; only knowing the field can. So name the safe fields and
# deny the rest, and reach for `# aws-ok` when a read needs a field not listed.
_QUERY_ARG_RE = re.compile(r"--query(?:=|\s+)(\"[^\"]*\"|'[^']*'|\S+)")
_SAFE_PROJECTIONS = frozenset({
    "app.name", "app.appid", "app.apparn", "app.platform", "app.description",
    "app.defaultdomain", "app.repository", "app.createtime", "app.updatetime",
    "app.productionbranch.branchname", "app.productionbranch.status",
    "branch.branchname", "branch.displayname", "branch.stage", "branch.active",
    "branch.createtime", "branch.updatetime", "branch.framework",
})


def strip_comment(segment: str) -> str:
    """The segment without its trailing shell comment.

    A commented-out flag is not an argument: `aws amplify get-app --app-id X
    # --query app.name` executes an unprojected read while reading as a safe
    one. Quote-aware, so a `#` inside an argument stays.
    """
    quote = None
    for index, char in enumerate(segment):
        if quote is not None:
            if char == quote:
                quote = None
        elif char in "\"'":
            quote = char
        elif char == "#" and (index == 0 or segment[index - 1].isspace()):
            return segment[:index]
    return segment


# `--debug` prints the unfiltered HTTP response body to stderr *before* the
# projection is applied, so a redacting `--query` proves nothing about what
# reaches the transcript.
_DEBUG_RE = re.compile(r"(?<![\w-])--debug\b")


def query_redacts_values(segment: str) -> bool:
    """True when this one call's --query names only known-safe fields."""
    segment = strip_comment(segment)
    if _DEBUG_RE.search(segment):
        return False
    args = _QUERY_ARG_RE.findall(segment)
    if not args:
        return False
    return all(arg.strip("\"'").strip().lower() in _SAFE_PROJECTIONS for arg in args)


def amplify_read_is_blocked(command: str) -> bool:
    """A protected read blocks unless *its own* call carries a safe projection.

    Two reads in one segment are denied outright rather than analysed. A
    projection cannot be tied to a particular call by pattern matching, so one
    safe `--query` would otherwise vouch for an unprojected read beside it --
    whether they share a segment because they are genuinely one quoted remote
    script, or because a quote this function mis-parsed swallowed the separator
    between them. Ambiguity denies; `# aws-ok` is how a human says otherwise.
    """
    for segment in segments(command):
        reads = len(AMPLIFY_READ_RE.findall(segment))
        if reads > 1 or (reads == 1 and not query_redacts_values(segment)):
            return True
    return False


# Resource paths nest, and the verb sits at the end of the path rather than
# after a single token: `stripe --live checkout sessions create` is a live
# mutation in the same way `stripe charges create` is.
STRIPE_MUTATION_RE = re.compile(
    r"\bstripe\s+" + _GLOBAL_OPTS + r"(?:(?!--)[\w-]+\s+){1,3}"
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
        "`--query` projection drawn from the guard's allowlist of known-safe "
        "fields (the shape of a projection cannot prove its value is safe — "
        "`app.basicAuthCredentials` is a dotted path too), admin tooling that "
        "keeps values out of the transcript by design, or have the human "
        "approve appending `# aws-ok`. Each call in a pipeline is judged on "
        "its own. Rule: AGENTS.md → Cloud / infrastructure safety."
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
        if AWS_SECRET_RE.search(command) or amplify_read_is_blocked(command):
            return "aws"
    if STRIPE_MUTATION_RE.search(command) and OVERRIDES["stripe"] not in command:
        return "stripe"
    return None


def command_is_blocked(command: str) -> bool:
    return classify_command(command) is not None


def path_is_blocked(path: str) -> bool:
    basename = path.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    return bool(re.fullmatch(SECRET_FILE, basename, re.IGNORECASE))


# A glob is blocked when it *can select* a protected file, which is not the
# same as spelling one out: `*.yaml` and `*` reach `config.yaml` without ever
# naming it. Matching the pattern against names a protected file actually has
# was the obvious test, and it leaked too — `*.production.yaml` matches no probe
# and still selects `config.production.yaml`, because the protected families are
# infinite and a probe list is not. So the probes stay as a fast path and the
# rule behind them is structural and default-deny: any wildcard selector over
# the YAML or dotenv families blocks, and only a *literal* name keeps the
# `.example` carve-out. `*.example.yaml` is blocked despite selecting nothing
# protected — that false positive is the price of not having to enumerate what a
# wildcard can reach, and naming the file lifts it.
# Generated across the grammar rather than hand-listed, because hand-listed
# probes kept missing a shape: `*.production.yaml` was absent until a review
# found it, and then `*.production.y*ml` and `.[e]nv.f??` slipped past a
# literal-suffix fallback. `fnmatch` already handles `*`, `?` and `[...]`
# correctly, so the only question is whether the probe set samples the family
# densely enough. This is sampling, not proof -- the structural fallback below
# is the backstop, and a pattern neither catches gets the human's `# config-ok`.
_PROTECTED_PROBES = tuple(
    "config" + middle + extension
    for middle in (
        "", ".a", ".ab", ".local", ".production", ".dev", ".test", ".foo",
        "a", "x", "-x", "1",
    )
    for extension in (".yaml", ".yml")
) + tuple(
    ".env" + suffix
    for suffix in ("", ".a", ".ab", ".local", ".production", ".dev", ".test", ".foo", "x")
)


# A brace pattern's expansion is a cross-product, so it grows exponentially:
# 25 two-way groups is 33.5 million alternatives. Materializing that exhausts
# memory or blows the hook's 10-second timeout -- and a PreToolUse hook that
# times out is treated as NON-blocking, so the guard would fail *open* on the
# one input shaped to break it. Count first, bounded, and deny past the cap:
# "ambiguity denies" has to hold for ambiguity about the pattern itself.
_MAX_GLOB_FANOUT = 256


def brace_fanout(pattern: str, cap: int = _MAX_GLOB_FANOUT) -> int:
    """How many alternatives `expand_braces` would yield, short-circuited at cap.

    Mirrors `expand_braces` exactly, including nesting, so the count is right
    rather than an estimate -- but it abandons counting once past `cap`, so the
    work it does is bounded no matter how the pattern is shaped.
    """
    match = re.search(r"\{([^{}]*)\}", pattern)
    if not match:
        return 1
    total = 0
    head, tail = pattern[: match.start()], pattern[match.end():]
    for alternative in match.group(1).split(","):
        total += brace_fanout(head + alternative.strip() + tail, cap)
        if total > cap:
            return total
    return total


def expand_braces(pattern: str):
    """Every alternative of a ripgrep brace pattern, e.g. `*.{yaml,yml}`.

    Grep's glob syntax expands these and `fnmatch` does not, so `*.{yaml,yml}`
    selected `config.yaml` while matching no probe and no YAML suffix. Callers
    must bound the fan-out with `brace_fanout` first.
    """
    match = re.search(r"\{([^{}]*)\}", pattern)
    if not match:
        return [pattern]
    expanded = []
    for alternative in match.group(1).split(","):
        head, tail = pattern[: match.start()], pattern[match.end():]
        expanded.extend(expand_braces(head + alternative.strip() + tail))
    return expanded


def glob_is_blocked(glob: str) -> bool:
    """True when the glob can select a file `path_is_blocked` would protect.

    Braces expand *before* the basename is taken: an alternative may carry its
    own directory part, and `{src/*.ts,config/*.yaml}` basenamed first yields
    the nonsense `*.yaml}` while ripgrep happily selects `config/config.yaml`.
    """
    if not glob:
        return False
    normalized = glob.replace("\\", "/")
    if brace_fanout(normalized) > _MAX_GLOB_FANOUT:
        return True  # too many alternatives to check: deny rather than time out
    for alternative in expand_braces(normalized):
        if _basename_glob_is_blocked(alternative.rsplit("/", 1)[-1].lower()):
            return True
    return False


def _basename_glob_is_blocked(basename: str) -> bool:
    if not any(ch in basename for ch in "*?["):
        return bool(re.fullmatch(SECRET_FILE, basename, re.IGNORECASE))
    if any(fnmatch.fnmatchcase(probe, basename) for probe in _PROTECTED_PROBES):
        return True
    return bool(re.fullmatch(r"[^/]*\.ya?ml", basename)) or ".env" in basename


def grep_is_blocked(tool_input: dict) -> bool:
    """Grep aimed at a secret file by path or by glob prints its matching lines.

    KNOWN AND ACCEPTED GAP, recorded rather than patched. An unrestricted
    content search -- `{"path": ".", "pattern": "password"}`, with no glob, or
    scoped only by `type: "yaml"` which this function does not read -- can match
    inside a protected file and print the line. Closing it means blocking every
    directory-wide content search, since nothing in the call proves the tree
    holds no `.env`. That is most of what Grep is for, and a guard that blocks
    ordinary work gets switched off, which protects nothing. So the scope checks
    cover what a call *names* -- a path, a glob -- and the docstring's promise
    holds: this is a guardrail against accidental exposure, not a sandbox.
    Defence in depth for the rest is the secret never being in the tree.
    """
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

#!/usr/bin/env python3
"""Regression tests for config-secrets-guard.py.

Run: python3 ~/.claude/tools/test-config-secrets-guard.py

Every case below the BYPASSES marker is a hole a cross-provider review found in
the guard after it grew beyond config-file reads. They are the interesting ones:
each passed the guard while doing exactly what the guard exists to stop, so a
change that makes any of them pass again is a regression, not a refactor.

The forbidden command strings are assembled from pieces (`A`, `S`) so that this
file's own text does not match the patterns it tests — otherwise the guard
blocks the very tool calls that read and run these tests.
"""

import importlib.util
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("guard", HERE / "config-secrets-guard.py")
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)

A = "aws " + "amplify "
S = "str" + "ipe "

COMMANDS = [
    # --- baseline: config-file reads -------------------------------------
    ("cat .env", "config"),
    ("cat .env.example", None),
    ("sed -i 's/a/b/' .env  # config-ok", None),
    ("cat config.yaml", "config"),
    ("cat config.example.yaml", None),
    ("node -e 'console.log(process.env.FOO)'", None),
    ("echo $" + "{import.meta.env.MODE}", None),

    # --- baseline: environment dumps -------------------------------------
    ("env", "env"),
    ("printenv", "env"),
    ("printenv PATH", None),
    ("env VAR=x node app.js", None),
    ("set -euo pipefail", None),
    ("Get-ChildItem Env:", "env"),

    # --- baseline: cloud reads and money mutations -----------------------
    (A + "get-app --app-id XYZ", "aws"),
    (A + "list-apps", None),
    ("aws ssm get-parameter --name /x --with-decryption", "aws"),
    ("aws ssm get-parameter --name /x", None),
    (S + "prices create --unit-amount 500", "stripe"),
    (S + "prices list", None),

    # === BYPASSES ========================================================
    # 1. An arbitrary --query is not evidence of redaction: a whole-object
    #    projection returns environment-variable values too.
    (A + "get-app --app-id XYZ --query app", "aws"),
    (A + "get-app --app-id XYZ --query app.*", "aws"),
    (A + "get-app --app-id XYZ --query 'app.environmentVariables'", "aws"),
    (A + "get-app --app-id XYZ --query app.name", None),
    (A + "get-app --app-id XYZ --query app.productionBranch.branchName", None),
    (A + "get-branch --app-id XYZ --branch-name main --query branch.stage", None),

    # 2. Global options sit between the command and the resource — and
    #    --live is the flag that makes the mutation matter.
    (S + "--live charges create --amount 100", "stripe"),
    (S + "--api-key KEY charges create --amount 100", "stripe"),
    (S + "--live charges list", None),

    # 3. A newline is a separator, indentation is formatting, and a trailing
    #    comment still leaves the dump bare.
    ("pwd\nenv", "env"),
    ("pwd\n  env", "env"),
    ("env  # just looking", "env"),
    ("env  # env-ok", None),

    # 4. PowerShell command names are case-insensitive.
    ("get-content .env", "config"),
    ("GET-CONTENT config.yaml", "config"),
]

GREPS = [
    # --- baseline ---------------------------------------------------------
    ({"path": "/srv/app/.env"}, True),
    ({"path": "/srv/app/.env.example"}, False),
    ({"glob": "**/*.ts"}, False),

    # === BYPASS ===========================================================
    # 5. A glob selects protected files without naming one literally.
    ({"glob": "config*.yaml"}, True),
    ({"glob": ".env*"}, True),
    ({"glob": "**/.env.*"}, True),
    ({"glob": "config?.yml"}, True),
    ({"glob": "*.example.yaml"}, False),
    ({"glob": ".env.example"}, False),
]


def main() -> int:
    failures = 0

    for command, want in COMMANDS:
        got = guard.classify_command(command)
        if got != want:
            failures += 1
            print(f"FAIL classify_command({command!r}) -> {got!r}, want {want!r}")

    for tool_input, want in GREPS:
        got = guard.grep_is_blocked(tool_input)
        if got != want:
            failures += 1
            print(f"FAIL grep_is_blocked({tool_input!r}) -> {got!r}, want {want!r}")

    total = len(COMMANDS) + len(GREPS)
    if failures:
        print(f"\n{failures} of {total} cases failed")
        return 1
    print(f"all {total} cases pass")
    return 0


if __name__ == "__main__":
    sys.exit(main())

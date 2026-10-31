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
    ("aws ssm get-parameter --name /x --with-decryption", "aws"),
    # Allowed only under the convention that secrets are SecureString, which
    # returns ciphertext without --with-decryption. A `String` parameter returns
    # its value in plaintext and no flag marks that. Recorded as the trade.
    ("aws ssm get-parameter --name /x", None),
    ("printenv HOME", None),
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

    # 5. A prefix test is not whole-argument validation: JMESPath returns the
    #    whole object when the projection goes on past the safe-looking part.
    (A + "get-app --app-id XYZ --query 'app.name && app'", "aws"),
    (A + "get-app --app-id XYZ --query \"app.name || app\"", "aws"),
    # These two also pin the quote-aware segment splitter: a regex split on
    # the separators tore the quoted projection in half and the leading
    # fragment then looked allowlisted.

    # 6. Global options sit before the *service* too, not only before the
    #    subcommand — the same hole as #2, one provider over.
    (A.replace("aws ", "aws --region us-east-1 ") + "get-app --app-id XYZ", "aws"),
    ("aws --profile admin ssm get-parameter --name /x --with-decryption", "aws"),
    ("aws --region us-east-1 " + "secrets" + "manager get-secret-value --secret-id s", "aws"),
    (A + "--debug get-app --app-id XYZ", "aws"),

    # 7. `Env:PATH` is the named single-variable read the deny message
    #    recommends; blocking it would contradict the guard's own advice.
    ("Get-ChildItem Env:PATH", None),
    ("gci Env:HOME", None),
    ("Get-ChildItem Env:", "env"),
    ("Get-ChildItem Env:*", "env"),
    ("Get-ChildItem -Path Env: | Out-String", "env"),

    # 9. One safe flag does not vouch for the next call. Each separator-
    #    delimited segment is judged on its own.
    (A + "get-app --app-id X --query app.name; " + A + "get-branch --app-id X",
     "aws"),
    (A + "get-app --app-id X --query app.name && " + A + "get-app --app-id Y",
     "aws"),
    (A + "get-app --app-id X --query app.name", None),

    # 10. The *shape* of a projection cannot prove its value is safe: these are
    #     dotted paths with no "environment" in them, and they return
    #     base64-encoded basic-auth credentials. Hence an allowlist.
    (A + "get-app --app-id X --query app.basicAuthCredentials", "aws"),
    (A + "get-branch --app-id X --branch-name m --query branch.basicAuthCredentials",
     "aws"),
    (A + "get-app --app-id X --query app.tags", "aws"),

    # 11. Resource paths nest; the verb sits at the end of the path.
    (S + "--live checkout sessions create --mode payment", "stripe"),
    (S + "checkout sessions create", "stripe"),
    (S + "checkout sessions list", None),
    ("stripe trigger payment_intent.created", None),

    # 12. Quoting and the provider root are ordinary spellings of a bare
    #     enumeration.
    ("Get-ChildItem 'Env:'", "env"),
    ("Get-ChildItem \"Env:\"", "env"),
    ("Get-ChildItem Env:\\", "env"),
    ("Get-ChildItem Env:\\PATH", None),

    # 14. The *list* forms leak more than the get forms the guard was named
    #     for: per the ListApps API reference each element of `apps` is a full
    #     App object with environmentVariables and basicAuthCredentials, so
    #     this hands over every app's secrets instead of one app's. This case
    #     asserted `None` for two review rounds — a bypass written down as
    #     correct behaviour, which is worse than no test.
    (A + "list-apps", "aws"),
    (A + "list-branches --app-id XYZ", "aws"),

    # 15. `--debug` prints the unfiltered response body to stderr before the
    #     projection is applied, so an allowlisted --query proves nothing.
    (A + "get-app --app-id X --query app.name --debug", "aws"),
    (A + "get-app --app-id X --debug --query app.name", "aws"),

    # 16. A commented-out flag is not an argument.
    (A + "get-app --app-id X # --query app.name", "aws"),
    (A + "get-app --app-id X --query 'a#b'", "aws"),

    # 18. Two reads in one segment: a projection cannot be tied to a call by
    #     pattern matching, so one safe --query vouched for the unprojected
    #     read beside it. Reached two ways - a genuine quoted remote script,
    #     and a `\\'` escape that made segments() swallow the real separator.
    ("ssh host '" + A + "get-app --app-id X; " + A
     + "get-app --app-id Y --query app.name'", "aws"),
    (A + "get-app --app-id X --query app.name \\' ; " + A
     + "get-branch --app-id X --branch-name main ; echo \\'", "aws"),

    # 19. Windows filenames are case-insensitive, so these read the same bytes
    #     as the lowercase spellings the guard already blocked.
    ("Get-Content .ENV", "config"),
    ("Get-Content CONFIG.YAML", "config"),
    ("type Config.Yaml", "config"),
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
    ({"glob": ".env.example"}, False),

    # 8. A broader glob selects protected files without naming one: `*.yaml`
    #    and `*` both reach config.yaml. Blocking them costs false positives
    #    on innocent YAML, which is the trade a guard is for.
    ({"glob": "*.yaml"}, True),
    ({"glob": "*.yml"}, True),
    ({"glob": "*"}, True),
    ({"glob": "**/*"}, True),
    ({"glob": "config.*"}, True),
    ({"glob": "*.json"}, False),
    ({"glob": "src/**/*.py"}, False),

    # 13. A probe list cannot enumerate an infinite family: `*.production.yaml`
    #     matched no probe and still selected `config.production.yaml`. The rule
    #     behind the probes is structural, so a wildcard over either family
    #     blocks — `*.example.yaml` included, which selects nothing protected.
    #     That false positive is deliberate; naming the file literally lifts it.
    ({"glob": "*.production.yaml"}, True),
    ({"glob": "*.local.yml"}, True),
    ({"glob": "*.example.yaml"}, True),
    ({"glob": "**/.env.*.local"}, True),
    ({"glob": "*.yaml.tmpl"}, False),

    # 17. Grep's glob syntax expands brace alternatives and `fnmatch` does not,
    #     so this selected config.yaml while matching no probe and no suffix.
    ({"glob": "*.{yaml,yml}"}, True),
    ({"glob": "{.env,.env.*}"}, True),
    ({"glob": "**/*.{js,ts}"}, False),

    # 20. A literal-suffix fallback cannot see a wildcard *inside* the
    #     extension, and a hand-listed probe set kept missing a shape.
    ({"glob": "*.production.y*ml"}, True),
    ({"glob": ".[e]nv.f??"}, True),
    ({"glob": "config.?????"}, True),

    # 21. Braces must expand before the basename is taken: an alternative can
    #     carry its own directory part, and basenaming first yields `*.yaml}`.
    ({"glob": "{src/*.ts,config/*.yaml}"}, True),
    ({"glob": "{src/*.ts,lib/*.js}"}, False),

    # 22. Windows filename casing, as above.
    ({"glob": "*.YAML"}, True),
    ({"path": "/srv/app/.ENV"}, True),
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

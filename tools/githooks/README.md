# Global git hooks — a secret gate that fails closed

These are machine-wide git hooks: one secret scan that blocks, and two
dependency scans that report. They are what makes rule 4 in
[`config/agents/AGENTS.md`](../../config/agents/AGENTS.md) safe — the rule that
lets a non-functional commit skip the pull request and land straight on `main`.

**If you do not install these, do not use rule 4.** That is not a formality. The
rule is safe only because something preventive still runs on a direct commit,
and without a hook a direct push to a branch with a ruleset bypass has nothing
checking it at all.

```sh
sh tools/githooks/install.sh          # -> ~/.githooks, sets core.hooksPath
sh tools/githooks/test-pre-commit.sh  # self-test, spends no Snyk quota
```

You need `gitleaks` on PATH. `snyk` and `node` are optional — without them the
dependency checks skip and the secret gate still runs.

**On WSL, if you also commit from Windows, pass a Windows-visible destination:**

```sh
sh tools/githooks/install.sh /mnt/c/Users/$USER/.githooks
```

Git for Windows is a separate install with its own global config, and it cannot
reach a path on the WSL filesystem — `/home/you/.githooks` has no drive-letter
spelling. The default destination therefore guards WSL only, and the installer
says so rather than pointing Windows git at a path it cannot read: that would
find no hooks and skip the scan silently, which is the worst of the three
outcomes. Installing to a `/mnt/<drive>/` path guards both.

### The one thing it will not do for you

`pip install` is **off by default** (`SNYK_HOOK_PIP_INSTALL=1` opts in). Snyk
reads the versions installed in the Python it runs rather than the pins in a
manifest, so testing `requirements.txt` accurately means installing it — and
installing a source distribution runs its build code (`setup.py`, a PEP 517
backend) as you, with your files and credentials in reach. A requirements file
can also point at a local path or a VCS URL. Wiring that to `git commit` means
editing one line of a manifest executes someone else's build code, which is not
something a secret-scanning hook should do by surprise. A throwaway venv
isolates the installed packages, not the build.

Left off, Snyk still tests the manifest against whatever Python it finds: less
accurate, and harmless.

## What each layer is for

| Layer | Cost | Blocks? | When it runs |
|---|---|---|---|
| `gitleaks` on the staged diff | free, ~1 s | **yes, always** | every commit |
| Snyk Open Source | metered | no (default) | only a manifest whose *resolved dependencies* changed |
| Snyk Code | metered | no (default) | at most once per repo per day, and only when source is staged |

### The secret gate fails closed, and that is the whole point

A secret blocks. So does a scan that could not be trusted — `gitleaks` missing
from PATH, or a scan that errored. **An errored scan is not a clean scan**, and
treating it as one is how a guard becomes decorative.

The hook passes `--exit-code 3`, so the exit code is unambiguous: `0` clean, `3`
secret found, anything else a scan error. Only the scan-error case is
overridable, with `GITLEAKS_DEGRADED_OK=1`, for one commit, explained in the
message. A finding at `3` is never overridable by any environment variable;
`git commit --no-verify` is the only way past it and is itself a smell.

For a genuine false positive, use a `gitleaks:allow` comment on the line or a
`.gitleaksignore` entry — not the override.

**Why this matters more than it looks.** Server-side scanning is *detective*: by
the time CI reports a secret, it is already in history and the only fix is
rotation. A local hook is the only *preventive* gate. And the moment your default
branch grants anyone a ruleset bypass, that bypass is granted to a **role** —
GitHub cannot scope one by path — so a direct push by that role skips the
server-side checks as gates too. This hook is then the only gate left standing,
on every machine holding a token with that role.

### The dependency scans default to warn, and a warn is an obligation

They are *delta-aware*: a manifest is tested only when the commit changes its
dependency fields, or its lockfile beyond the root version fields. A release
commit that bumps `version` is not a dependency change. And they fail only on
findings that **have a fix available** (`--fail-on=all`), which is the same test
as the remediation rule in `AGENTS.md`.

Because of that filter, everything the hook reports already has a fix. The
`warn` default exists so a mid-work commit is not held hostage to a transitive
CVE you have not read yet — it does **not** license pushing or merging with the
finding still open. Open the fix the same day.

## Switches

Every switch is enabled by the exact value `1` and nothing else, so a value
meant to turn one *off* (`false`, `no`, empty) can never turn it on.

| Variable | Effect |
|---|---|
| `SNYK_HOOK_MODE` | `warn` (default), `block` to fail on fixable findings, `off` to skip Snyk entirely — debugging the hook only |
| `SNYK_SKIP=1` | skip the Snyk tests for one commit; `gitleaks` still runs |
| `GITLEAKS_DEGRADED_OK=1` | pass one *degraded* scan; never a found secret |
| `SNYK_CODE_FORCE=1` | run a Code test even with no source staged |
| `SNYK_HOOK_SEVERITY` | severity threshold, default `high` |
| `SNYK_HOOK_OS_CAP` / `SNYK_HOOK_CODE_CAP` | soft monthly caps (180 / 90) that stop testing before the plan limit |
| `SNYK_HOOK_ORG` | Snyk org for this commit; or `git config --local hook.snykOrg <org>` per repo. Free-plan budgets are counted per org |
| `SNYK_HOOK_PIP_INSTALL=1` | install a changed `requirements*.txt` into a throwaway venv so Snyk tests the resolved versions. **Off by default**, because `pip install` builds packages and a source distribution's build runs arbitrary code as you — see below. Or `git config --local hook.snykPipInstall 1` for a repo whose manifests you trust |

## Installing these does not disable your repo-local hooks

It would, if the hooks did nothing about it. Setting `core.hooksPath` makes git
ignore each repo's `.git/hooks` completely — so a naive global install silently
kills every Husky, lefthook and `pre-commit`-framework setup on the machine.

Every hook here sources `_lib.sh` and calls `chain_local_hook`, which looks up
the repo's own hook of the same name and runs it. That is also why the
passthrough hooks (`commit-msg`, `pre-push`, `post-merge`, …) exist at all: they
carry no logic, and are there purely so the repo-local ones keep firing.

`chain_local_hook` resolves the repo's hooks directory from `--git-common-dir`
rather than `--git-path hooks`, because with `core.hooksPath` set the latter
returns the global directory and the hook would recurse into itself.

### But a repo that sets `core.hooksPath` itself wins, and the gate goes quiet

This is the dangerous direction, and the opposite of the paragraph above.
`core.hooksPath` is ordinary config, so a **repo-local** value overrides the
global one. Husky and lefthook both set one (`git config core.hooksPath .husky/_`
and similar), and in those repos git never starts the global `pre-commit` at all.
The chaining above cannot help: it lives inside a hook that is not running.

So the secret gate is **silently absent** in exactly the repos most likely to
have a hook framework, with nothing to tell you. Check before trusting it:

```sh
git config --local --get core.hooksPath   # empty = the global hooks run
```

If it is set, you have two options: drop the local value and let the local hook
chain from the global one (the normal case, since `chain_local_hook` runs
`.git/hooks/pre-commit`), or have the framework's hook invoke the global
`pre-commit` itself. Until one of those is true, treat that repo as
pull-request-only no matter what the install reported — rule 4 in
[`AGENTS.md`](../../config/agents/AGENTS.md) says the same thing, because this
falsifies the rule's premise rather than the hook's behaviour.

## Changing a hook

1. Edit the copy in this repo.
2. Add a case to `test-pre-commit.sh` *before* changing `deps_changed()`,
   `staged_files()` or `code_staged()`.
3. Run `sh tools/githooks/test-pre-commit.sh` — it runs the hook in a throwaway
   repo against a stub `snyk`, so it spends no quota. Then run it again as
   `TEST_NO_HOOK_RUN=1 sh tools/githooks/test-pre-commit.sh` if you touched the
   runner, to exercise the pre-2.36 path too.
4. Re-run `install.sh`. Git runs the installed copy; editing this one changes
   nothing until you do.

The self-test extracts the hook's helper functions from the text between
`DEPS_JS=` and `# ---- 1. Open Source`, so a new helper has to be defined inside
that window to be testable.

**`git hook run` needs Git ≥ 2.36**, and Ubuntu 22.04 LTS still ships 2.34.
That matters more than a portability note usually would: on older git the
subcommand does not exist, git exits non-zero before any hook runs, and every
case asserting a *blocked* commit then passes for the wrong reason. A suite
reporting a working secret gate on a machine where it never ran is worse than no
suite, so the runner detects the version and invokes the hook directly instead.
`TEST_NO_HOOK_RUN=1` forces that path on a modern git; both give 37 assertions.

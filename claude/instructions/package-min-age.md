# Vulnerability fixes vs. minimum package age — per-manager enforcement

Two rules live here, in priority order. The rule text itself is in
`~/.config/agents/AGENTS.md`; this file holds the per-manager mechanics.
Facts below were verified against primary sources on 2026-10-23.

## Why both exist

They defend against different threats and neither covers the other:

- **Scanners** (Snyk, `npm audit`, `pip-audit`, `osv-scanner`, Dependabot)
  match installed versions against a database of **known** advisories. They
  cannot see a malicious version until someone has published an advisory.
- **The age floor** covers the window **before** that advisory exists: a
  compromised maintainer account ships a malicious version and, for hours to
  days, every scanner says "clean" (the 2025 npm worms). Not being the first
  installer is the whole defence. npm made it a first-class config
  (`min-release-age`, npm 11.10.0) in response.

## 1. Remediation wins (highest priority)

If a vulnerability is reported and a fixed version exists, **apply it now** —
no approval, no age floor, however recently the fix shipped. The floor in
section 2 never justifies staying vulnerable.

Overriding the floor does not skip the check; it **swaps** it. A fix version
younger than the window is itself unvetted, and lookalike "patch" releases are
a known attack. So, for the override:

1. Take the **lowest** version that clears the advisory (patch over minor over
   major) so remediation does not smuggle in a feature jump.
2. Verify provenance instead of age: `npm view <pkg>@<ver> dist.attestations`
   should show a provenance attestation, or the publisher must be unchanged
   (`npm view <pkg>@<ver> _npmUser`); `npm audit signatures` must pass after
   the install. For PyPI, check the release's Trusted Publisher / attestation
   on the project page.
3. Confirm the advisory itself names that version as fixed.
4. State in one line what moved and which advisory it closes.

| Manager | Find what's vulnerable | Apply the fix |
|---------|------------------------|---------------|
| **npm** | `npm audit`, `osv-scanner`, `snyk test` | `npm install <pkg>@<fixed> --min-release-age=0` (the CLI flag outranks every `.npmrc`). `npm audit fix` is blocked by the window and exits non-zero rather than installing silently — add `--min-release-age=0` or a `min-release-age-exclude` entry. Transitive-only pins via `overrides` in `package.json` |
| **pnpm** | `pnpm audit`, `snyk test` | `pnpm update <pkg>`; transitive pins via `pnpm.overrides`; `--minimum-release-age=0` to override a floor |
| **yarn** | `yarn npm audit`, `snyk test` | `yarn up <pkg>`; transitive pins via `resolutions` |
| **pip / uv / poetry** | `pip-audit`, `osv-scanner`, `snyk test` | upgrade the pin; drop `--exclude-newer` for the security bump |
| **cargo** | `cargo audit` | `cargo update -p <pkg>` |
| **go modules** | `govulncheck ./...` | `go get <mod>@<fixed>` && `go mod tidy` |
| **Node.js runtime** | the nodejs-sec list / `https://nodejs.org/en/feed/vulnerability.xml` | a host install, not a package bump; user-scope tools are yours, machine-scope installers (e.g. the Windows MSI) are the user's |

No fixed version available? Say so explicitly and name the mitigation (drop the
dep, pin away from the vulnerable path, or accept with a stated reason). That is
the only acceptable "still vulnerable" outcome.

## 2. Minimum package age floor (applies only when nothing is vulnerable)

Supply-chain defence against compromised fresh publishes: never install or
upgrade to a version published <7 days ago without explicit approval.

| Manager | Configuration |
|---------|---------------|
| **npm** (≥ 11.10.0) | `min-release-age=7` in `~/.npmrc` and in the repo's `.npmrc` (value in **DAYS**). Per-package exemption `min-release-age-exclude=<name or glob>` needs **npm ≥ 11.17.0** (npm/cli#9534) and is best-effort: `npm pack` honors it only from **11.19.0** (npm/cli#9811), and `npx` has an open bug. `minimumReleaseAge` is the **pnpm** key; npm ignores it |
| **pnpm** (≥ 10.16) | `minimum-release-age=10080` in `~/.npmrc` or `pnpm-workspace.yaml` (minutes) |
| **Dependabot** | `cooldown: { default-days: 7 }` in `.github/dependabot.yml`. Version updates only — GitHub's docs: "This default cooldown does not apply to security updates" |
| **yarn** | No native flag — pin versions; verify with `npm view <pkg> time` before bumping |
| **pip / pypi** | No native flag — check publish date via `pip index versions <pkg>` or the PyPI JSON API; skip versions <7 days old |
| **uv** | `uv pip install --exclude-newer=$(date -u -d '7 days ago' +%Y-%m-%dT%H:%M:%SZ) <pkg>` |
| **poetry** | No native flag — verify via PyPI JSON API before adding deps |
| **cargo** | No native flag — verify on crates.io before adding |
| **go modules** | Checksum DB mitigates; still prefer versions ≥7 days old |

### What the npm floor does NOT cover

- **`npm ci` ignores it** and installs the lockfile verbatim (npm maintainers
  call this a known hole). Your deploy host, CI, and any clone running `npm ci` are
  protected only by the committed lockfile — which is why the lockfile change
  in a PR is the thing to read, and why `npm audit signatures` runs in CI.
- Precedence is cli > env > project `.npmrc` > user `.npmrc`; `before`, when
  set in the same source, wins over `min-release-age`.

### Verify the floor actually exists

A documented floor is not an enforced one. Check that it is really configured
rather than assuming it:

```bash
npm config get min-release-age
```

`null` means there is no floor, whatever the docs say. Put the line in both
`~/.npmrc` and each repo's `.npmrc` so every contributor gets it.

Watch for a silent npm downgrade: a Node.js installer ships its own bundled npm
and can replace a newer global npm with an older major. If that older npm
predates `min-release-age` (npm < 11.10.0), the floor disappears without any
error. After a Node install, confirm `npm --version` and restore the npm major
you had.

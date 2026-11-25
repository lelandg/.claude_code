# Security: dependency remediation and scanning

Moved from `~/.config/agents/AGENTS.md` on 2026-11-24 so that file stays under agy's rule-file cut (22,035 bytes, measured 2026-11-25). AGENTS.md keeps the rule in brief and points here; this text is the full version and is equally binding.

## Package manager — vulnerability fixes vs. minimum package age

**Precedence: remediation wins.** If a vulnerability is reported against a
package and a fixed version exists, apply it **immediately** — no approval, no
age floor, however recently the fix shipped. This outranks the 7-day rule below;
never cite that rule as a reason to stay vulnerable. "Reported" means Snyk,
`npm audit`, a GitHub/Dependabot advisory, or an upstream security release.

How to apply it: take the **lowest** version that clears the advisory (patch
over minor over major) so remediation doesn't smuggle in a feature jump, confirm
the version is the real upstream release and not a lookalike, then state in one
line what moved and which advisory it closes. If no fixed version exists, say so
and name the mitigation — that is the only acceptable "still vulnerable" answer,
and the four tiers below decide what that mitigation is.

**"Immediately" has a deadline: before you stop working.** A dependency
advisory with an available fix is remediated in the session that found it — on
the current branch when the PR already touches that manifest, otherwise as its
own PR, opened and merged the same day. Not "within 7 days", not "next
release", not a TODO. A pre-existing finding still does not block an
*unrelated* PR from merging, but it does not get to outlive the session that
saw it: open its fix PR before you report the other work done. If the fix
genuinely cannot land today, say in one line why and what the interim
mitigation is — an unexplained carry-forward is not an option.

**Otherwise the floor holds (supply-chain defense):** never install or upgrade to
a package version published **<7 days ago** without explicit approval — if the
latest is younger and nothing is vulnerable, say so and ask first. Per-manager
config/enforcement: `~/.claude/instructions/package-min-age.md`.

#### Advisory with no fix available — four tiers

Decide by **reachability and impact**, not by severity score alone.
Reachability must be traced in the code that ships (the app source, the
dependency's published build, and any bundled artifact), never assumed, and
the evidence is written down.

1. **A fixed version exists:** apply it in the session that finds it. Never
   accept or ignore it. (The precedence rule above, unchanged.)
2. **No fix, and the impact is confidentiality or integrity** (data leak,
   auth bypass, code execution), **and that impact is either reachable from
   untrusted input or happens without untrusted input** (for example, the
   dependency writes credentials to a log during a scheduled job): disable or
   block the
   affected feature until a fix ships. Do not accept it in a scanner ledger.
3. **No fix, reachable from untrusted input, availability impact only**
   (denial of service): mitigate with input limits and timeouts and keep the
   feature on; disable it if there is evidence of exploitation.
4. **No fix, not reachable from untrusted input, and no confidentiality or
   integrity impact without untrusted input:** accept it in the scanner
   ledger with a short expiry (about 30 days), the reachability evidence, and
   the condition that clears it. Re-trace reachability at every renewal and
   whenever the code that could reach it changes.

**Disabling a feature in production is the user's decision:** propose it with
the evidence and wait for a go-ahead — unless a tier 2 finding is being
actively exploited, in which case say so immediately. Never silence a scanner
without a ledger entry that has an expiry. Worked example: a glob-matching
library advisory with no fix, traced as unreachable from untrusted input, was
accepted at tier 4 with a 30-day expiry while the feature that pulled it in
stayed on.

### Dependency, code, and secret scanning

Three tiers, cheapest first. Free and unlimited tools run everywhere; the
metered one runs where it adds something.

| Tier | Tool | When |
|---|---|---|
| Free, unlimited | `npm audit`, `pip-audit`, `osv-scanner`, `gitleaks` | every commit (hook) and every PR (CI) |
| Free, GitHub-side | Dependabot alerts + grouped security-update PRs | always on, per repo |
| Metered (Snyk Free) | `snyk test`, `snyk code test` | before a PR that changes dependencies or app source |

**A global pre-commit hook should default to warn for the metered scanner, and
be delta-aware:** test a manifest only when the commit changes its dependency
fields (a release commit that bumps `version` is not a dependency change), and
fail only on findings that have a fix available (Snyk `--fail-on=all`: an
upgrade or a patch exists) — the same test as the precedence rule. Because of
that filter, **everything the hook reports already has a fix**: a warn is an
obligation, not a grace period. The `warn` default exists so a mid-work commit
is not held hostage to a transitive CVE you have not read yet; it never
licenses pushing or merging with the finding still open. Keep a documented
emergency skip for the metered scanner only (e.g. `SNYK_SKIP=1`) and record
its use in the commit message. Set the hook to block in a clone that wants
every finding to block, and off only while debugging the hook itself.

**`gitleaks` is the one gate that fails closed.** It always runs on the staged
changes, and a finding blocks with nothing to pass it. Run it with
`--exit-code 3` so the exit code is unambiguous — 0 clean, 3 secret found,
anything else a scan error — and treat a scan you cannot trust as a block too:
the binary missing from `PATH`, or an errored run. Only *that* case gets an
override (one commit, explained in the message); a found secret never does.
Make every switch in the hook enable on the exact value `1` alone, so a
`=false` cannot turn one on by truthiness. `--no-verify` is then the only other
way past a finding, and is itself a smell.

**A local hook is preventive; server-side scanning is detective.** Once a
secret is pushed it is already in history, so a CI scan can only tell you.
That asymmetry is why the local hook fails closed — and it becomes the *only*
preventive gate the moment the default branch grants a bypass (rule 4,
`~/.claude/instructions/git-workflow.md`).
A bypass is granted to a *role*, and GitHub cannot scope one by path, so the
same grant also skips those server-side checks as gates on any push by that
role. Every machine holding a token with that role therefore needs the hook
installed; track which ones do.

Before a PR: `snyk test` when the PR adds, removes, or upgrades a dependency;
`snyk code test` when it changes application source in a language Snyk Code
covers. A docs-, config-, or test-only PR gets neither Snyk test — CI's free
scanners still run. Report what ran and what it found in the PR body.

**Sweep Dependabot before every PR.** Checking the queue is part of opening a
PR, not a separate chore. Two commands, both free:

```bash
gh pr list --author app/dependabot --state open --json number,title,mergeStateStatus
```

```bash
gh api "repos/$(gh repo view --json nameWithOwner -q .nameWithOwner)/dependabot/alerts" --paginate --jq '.[] | select(.state=="open") | [.security_advisory.severity, .dependency.package.name, .security_vulnerability.vulnerable_version_range, .security_vulnerability.first_patched_version.identifier, .dependency.manifest_path] | @tsv' | sort -u
```

Then:

- **Merge the green ones as you go.** A Dependabot PR that is green and does
  not touch a deployed artifact is a merge, not a review (`pr_tool.py land`;
  bot PRs land without a version bump). Letting twenty pile up makes each one
  riskier, not safer.
- **"No PR" never means "no vulnerability."** Security PRs go missing for
  real reasons: a transitive-only dependency in a lockfile Dependabot cannot
  rewrite (`uv.lock`), an advisory with no fixed version, a resolution it
  cannot make. (An `update-types: version-update:semver-major` ignore is
  **not** one of them — it gates version updates only; security updates walk
  straight past it, so a semver-major security bump can still open with that
  ignore in place.) The alert list is the source of truth; the PR list is not.
- **Dependabot proposes the latest; the rule wants the lowest.** Its PR title
  may jump several majors, while the alert's `first_patched_version` names a
  much nearer release. Take the lowest version that clears the advisory and
  say in the PR body why it differs from what Dependabot offered.
- **A bump that changes a committed build artifact is work, not a merge** —
  e.g. a bundled Lambda whose `dist/` is checked in. Rebuild and commit the
  artifact in the same PR, or hold it and say why.

Pre-existing findings the PR does not touch do not block that PR — name them.
But they are not free to ignore, and there is no grace window: a dependency
finding with a fix available gets its remediation PR the **same day** it is
reported, owned by whoever saw it first. Never silence a finding the PR itself
introduces. Any finding with a fixed version gets that fix, regardless of how
new the fix is — see the precedence rule above.

**Dependency findings and SAST findings are not the same work.** A dependency
advisory has a deterministic fix — a version — so it is applied, not debated.
A code-scanning (SAST) finding's "fix" is a code change with design
consequences and a real false-positive rate, so it gets **triaged** the same
day instead: fix it now when the change is contained, otherwise record the
verdict — exploitable path or not, with the reasoning — in the PR body, or in
an ignore-file entry carrying a reason and an expiry. Triage is not optional,
and an untriaged SAST finding counts as real.

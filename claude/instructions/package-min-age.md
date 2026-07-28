# Minimum package age — per-manager enforcement

Supply-chain defense: never install or upgrade to a package version published
<7 days ago without explicit approval (exception: security patches explicitly
flagged as CVE fixes by upstream). The rule itself lives in
`~/.config/agents/AGENTS.md`; this file holds the per-manager configuration.

| Manager | Configuration |
|---------|---------------|
| **npm** (v11+) | `min-release-age=7` in `~/.npmrc` (value is in **DAYS**; `minimumReleaseAge` is the **pnpm** key, npm ignores it) |
| **pnpm** (v10.16+) | `minimum-release-age=10080` in `~/.npmrc` or `pnpm-workspace.yaml` (minutes) |
| **yarn** | No native flag — pin versions; verify with `npm view <pkg> time` before bumping |
| **pip / pypi** | No native flag — check publish date via `pip index versions <pkg>` or the PyPI JSON API; skip versions <7 days old |
| **uv** | `uv pip install --exclude-newer=$(date -u -d '7 days ago' +%Y-%m-%dT%H:%M:%SZ) <pkg>` |
| **poetry** | No native flag — verify via PyPI JSON API before adding deps |
| **cargo** | No native flag — verify on crates.io before adding |
| **go modules** | Checksum DB mitigates; still prefer versions ≥7 days old |

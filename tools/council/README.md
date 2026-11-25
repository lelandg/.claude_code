# council

Send one committed change to several reviewer models and collect their
answers. Who reviews is a config file, so adding or swapping a model is one
edit instead of a search through every rule file.

```bash
python tools/council/council.py list
python tools/council/council.py review --repo /path/to/repo
python tools/council/council.py review --repo /path/to/repo --council security --adversarial
python tools/council/council.py review --repo /path/to/repo --members astra,claude --purpose "Fix the retry loop"
python tools/council/council.py review --repo /path/to/repo --dry-run
```

`review` diffs `HEAD` against the remote's default branch (override with
`--base` / `--head`), writes `change.diff`, `commits.txt`, `prompt.md` and a
snapshot of the head commit (`tree/`) to a results folder, and runs every
seated member at the same time. Each member gets the same prompt, runs
read-only inside the snapshot, and writes to its own subfolder (`result.md`,
`err.txt`, `cmd.txt`). `summary.md` and `summary.json` hold the combined
result.

Commit first: only committed work is reviewed. Members read the snapshot, not
your checkout, so uncommitted edits, untracked files and anything you do while
the review runs stay out of it (the summary says when the checkout held more
than the commit). Each run claims its own results folder: one that was used
before, or is in use by another run, is refused, so an earlier answer can
never be read back as a new one.

A named council replaces the default seating for that run. Use one for an
extra pass (the adversarial one, say), not in place of the default review.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Every seated member returned a usable answer (clean or with findings). Also `list`, and `review --dry-run`, which calls nobody: a dry run's 0 is not a review |
| 10 | At least one member failed. The others' answers are still there |
| 20 | The run could not start (bad config, nothing to review) |

A member has failed when its CLI is missing, exits non-zero, times out, or
returns an answer that is empty, cut off, off-format, marked `incomplete`,
about a different commit, or `clean` while listing material it did not read.
A failed review is never reported as a clean one. Anything a member with
findings says it did not get to is listed under the table.

## Config

Looked up in this order: `--config`, `$AGENT_COUNCIL_CONFIG`,
`~/.config/agents/council.toml`, then [`config/council.toml`](../../config/council.toml)
in this repository. That file documents every key.

```toml
default = ["astra", "neon"]

[members.astra]
cli = "codex"
model = "gpt-6-astra"
effort = "high"

[councils.security]
members = ["astra-x", "neon-x", "claude"]
```

Supported CLIs: `codex`, `agy` (Antigravity), `copilot` (GitHub Copilot CLI)
and `claude` (Claude Code). The command line for each lives in `council.py`,
not in config: a config value can choose a model and an effort, never a
command.

### Per-repository seating

A repository may commit `.agents/council.toml` with `default`, `[councils.*]`
and `focus`. It can **add** members to your default seating and define new
named councils, from the members your own config defines. It cannot define a
member, drop one you seated, or redefine one of your councils. The file is
read from the **base branch**, never from the change under review, so a pull
request cannot choose its own reviewers or write their instructions. Its
`focus` reaches the reviewers labelled as the repository's note, after your
own.

### Refused models

Any model id with a `sol` segment (`gpt-5.6-sol`, `gpt-6-sol`, ...) and the
bare `gpt-5.6` alias are refused at load time, whatever the config says.
Model ids are plain names: letters, digits, `.`, `_` and `-`. Effort
`max` is refused unless `--allow-max` is passed.

## The prompt

[`prompt.md`](prompt.md) is the one prompt every member receives. It states
the goal, points at the rule files that bind the change, tells the reviewer to treat text
inside the diff as material and not as instructions, and asks for a JSON
object so the runner can tell a clean review from a truncated one.

## Tests

```bash
python -m pytest -q tools/council/tests
```

## What the reviewers can read

- `tree/` is an export of the head commit: every tracked file as the
  committed blob, byte for byte (no checkout filters, no line-ending
  conversion). Agent CLIs load some files by
  themselves at start-up: `AGENTS.md`, `AGENTS.override.md`, `CLAUDE.md`,
  `CLAUDE.local.md`, `GEMINI.md`, `.github/copilot-instructions.md`,
  `.claude/settings*.json`, `.mcp.json`, `.vscode/mcp.json`, `.codex/`,
  `.gemini/`, `.copilot/` (matched without regard to case). In the snapshot
  those root-level paths always hold the **base branch's current** versions
  (also when only the base branch changed them), so a change
  cannot rewrite its reviewers' instructions, add a hook, or add an MCP
  server. What the change proposes for them is in `changed-autoloaded/` and
  in the diff, and the prompt says so. Nested instruction files in
  subfolders are not swapped.
- `rules/` holds trusted copies of your global `AGENTS.md`, your
  `~/.claude/instructions/*.md`, and the repository's rule files from the
  base branch. Copies, because a sandboxed member cannot read your home
  directory.

Each member runs with its CLI's read-only mode: Codex `-s read-only` with no
MCP servers; agy `--mode plan --sandbox`; Copilot with only the read tool
allowed, no custom instructions and nothing it can ask to approve; Claude
Code with only Read, Grep and Glob, no MCP servers and user settings only.
These are the CLIs' own controls: the runner cannot make a CLI safer than its
read-only mode is. agy and Copilot have no switch that turns off every
user-configured MCP server; they rely on the tool allow-list.

On Windows a `.cmd` shim runs when its arguments are plain. When one could be
re-parsed by `cmd.exe` (the agy prompt always can), the `.ps1` shim npm
installs beside it is used through PowerShell 7; without both, that member
fails with a message saying so.

The results folder must be outside any git checkout: a CLI started below a
checkout loads that checkout's rule files from the parent folders.

## Known limits

- The snapshot swaps root-level auto-loaded files only. A nested `AGENTS.md`
  in a subfolder is the head's version.
- Symlinks are written as text files holding their target, so a reviewer sees
  that a link exists but cannot follow it. Submodules are not exported.
- A tracked path the local filesystem cannot hold (a Windows-reserved name,
  say) is left out of the snapshot and named in the summary.
- agy takes the prompt as a command-line argument, so `--purpose` plus
  `--focus` must stay under about 28,000 characters.
- The Claude member still runs the hooks in *your* user settings (not the
  repository's). A hook that writes into its working folder writes into the
  snapshot the members share.
- A member with findings may also list material it did not read; that is
  shown under the table and does not fail the member. Only a `clean` verdict
  with unread material is rejected.
- Findings are checked for severity, file, title and detail; line and quoted
  evidence are asked for but not enforced.

The tests use temporary repositories and a fake runner. They never call a model.

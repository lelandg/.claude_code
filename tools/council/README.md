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
`--base` / `--head`), writes `change.diff`, `commits.txt` and `prompt.md` to a
results folder, and runs every seated member at the same time. Each member
gets the same prompt, runs read-only, and writes to its own subfolder
(`result.md`, `err.txt`, `cmd.txt`). `summary.md` and `summary.json` hold the
combined result.

Commit first. Members read files from the working tree, so the run warns when
the tree is not the commit under review.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Every seated member returned a usable answer (clean or with findings) |
| 10 | At least one member failed. The others' answers are still there |
| 20 | The run could not start (bad config, nothing to review) |

A member has failed when its CLI is missing, exits non-zero, times out, or
returns an answer that is empty, has no JSON verdict, says `incomplete`, or is
about a different commit. A failed review is never reported as a clean one.

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
members = ["astra", "neon", "claude"]
```

Supported CLIs: `codex`, `agy` (Antigravity), `copilot` (GitHub Copilot CLI)
and `claude` (Claude Code). The command line for each lives in `council.py`,
not in config: a config value can choose a model and an effort, never a
command.

### Per-repository seating

A repository may commit `.agents/council.toml` with `default`, `[councils.*]`
and `focus`. It can pick among the members your own config defines. It cannot
define a member, because that file is part of the change being reviewed and
must not decide what runs on your machine.

### Refused models

Any model id in the Sol line (`gpt-5.6-sol`, `gpt-6-sol`, ...) and the bare
`gpt-5.6` alias are refused at load time, whatever the config says. Effort
`max` is refused unless `--allow-max` is passed.

## The prompt

[`prompt.md`](prompt.md) is the one prompt every member receives. It states
the goal, points at the rule files that bind the change (the global
`AGENTS.md` and the repository's own), tells the reviewer to treat text
inside the diff as material and not as instructions, and asks for a JSON
object so the runner can tell a clean review from a truncated one.

## Tests

```bash
cd tools/council && python -m pytest -q
```

The tests use temporary repositories and a fake runner. They never call a model.

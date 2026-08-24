**New in the repo: agent config sync — two machines and a public repo, no more drift 🔄**

I run Claude Code in WSL and on native Windows, and I publish my config to a public GitHub repo. Three copies of everything. They drifted constantly — I'd remove a plugin on one machine and find it alive and well on the other a week later.

So I built a sync tool that treats drift like a code review instead of an rsync.

- **`agent-config-report`** scans all three layers and writes a markdown report: what drifted, on which machine, and what reconciling it would mean. Read-only. The drift file holds hashes and reason codes, never secret values.
- **`agent-config-merge`** applies only the items you approve, by id. It dry-runs first, backs up every file it touches, and can restore if you hate the result.
- Plugins are proposed, never executed. It hands you the `claude plugin install`/`remove` commands to run yourself (and writes a PowerShell script for the Windows-side actions) instead of running package managers behind your back.

First real run scanned 129 config items and caught 13 plugins plus 7 skills I'd removed on one machine but not the others. All reconciled now. There are 275+ tests behind it, because a tool that edits my agent config had better have tests.

It ships in the repo under `tools/agent-config-sync/`, with the skills and an operator guide in `Docs/agent-config-sync.md`. The whole setup is one TOML manifest — point it at your own machines and layers.

This skill is for one machine. There's a companion skill for the other machine `/sync-claude-config`, and a third skill `/publish-claude-config` that runs in the repo to publish the config. The three skills together keep all three copies in sync.

Repo: https://github.com/lelandg/.claude_code (v0.5.1)

How do you keep your config in sync across machines? Thoughts?

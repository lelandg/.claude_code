# Contributing to .claude_code

Thanks for taking a look. Bug reports, ideas and pull requests are all welcome, whether it's your first contribution or your fiftieth.

## Questions and ideas

The quickest place to talk something through is the [Chameleon Labs Discord](https://discord.gg/chameleonlabs). Once an idea is concrete, open an issue.

## Reporting a bug

Search the [existing issues](https://github.com/lelandg/.claude_code/issues) first. If it's new, open an issue with:

- what you did, step by step
- what you expected, and what happened instead (paste the error text or log output)
- your operating system and the version or commit you're running

Security problems are different. Please report those privately, as described in [SECURITY.md](SECURITY.md).

## Pull requests

1. Fork the repository and create a branch from the default branch.
2. Keep each pull request to one fix or one feature.
3. Match the existing code style, and run any tests the README mentions before you push.
4. Say what changed and why in the description.

### Slash commands live in two folders

`.claude/commands/` is the source. Those are the commands Claude Code loads when you open this repository, and the folder the config mirror is published into. `claude/commands/` is the installable copy that the install options put in `~/.claude/commands/`.

Edit the file in `.claude/commands/`, then copy it to `claude/commands/` in the same commit. The two folders must match file for file, with one exception: `install-claude-config.md` lives only in `.claude/commands/`, because it installs this repository and means nothing once installed. The `tests` workflow fails when the folders drift.

For anything bigger than a small fix, open an issue or ask on Discord first. Nobody wants you to spend a weekend on something that needed a five-minute conversation.

Looking for somewhere to start? Try an issue labelled [`good first issue`](https://github.com/lelandg/.claude_code/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22).

## License

By contributing, you agree that your contribution is licensed under the same license as this project (see [LICENSE](LICENSE)).

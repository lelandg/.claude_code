# Model delegation — cross-provider routing (Claude + Codex + Gemini)

**This guide is for every agent CLI** (Claude Code, Codex, agy, Copilot). The
commands below run the same from any of them; only the way the shell is
reached differs (Claude Code's Bash tool, agy's terminal).

The compact rules live in `~/.config/agents/AGENTS.md` ("Model delegation &
cross-provider review"); this file is the full guide. The Sol ban is in the
AGENTS.md "Security" section, so every CLI sees it.

## Why delegate across providers

A different model family does not share the author's assumptions. The best
shipping loop: **one model writes, the review council audits, the author
reconciles the findings.** Cost routing is secondary; independent review is
the primary benefit. The OpenAI and Google pools are also separate from the
Claude plan, so council work preserves Claude headroom.

Every PR is reviewed by each seated council member before it opens, and by
the repo's automated reviewers (named in the repo's `AGENTS.md`) after. Rate each member from its measured findings, and change
the council file when one stops earning its place.

## Review council (2026-11-25)

The council is a list of reviewer models. **Who sits on it is data**, so no
rule file names the line-up:

- Config: `~/.config/agents/council.toml` (the config repo ships a starting
  copy as `config/council.toml`; agent-config-sync keeps it in step between
  WSL and Windows). Each `[members.<name>]` has a `cli`
  (`codex`, `agy`, `copilot`, `claude`), a `model` and an optional `effort`.
  `default = [...]` is who reviews every PR; `[councils.<name>]` are named
  line-ups. Default seating: `astra` (Codex, GPT-6 Astra, `high`) and `neon`
  (agy, Gemini 4 Neon, `high`). `security` seats the same two at `xhigh`
  plus Claude.
- Runner, the same from every CLI and both runtimes:
  `python /path/to/.claude_code/tools/council/council.py review --repo <abs repo path> --purpose "<PR title and first paragraph>"`
  (`python3` on Linux/WSL; inside the config repo itself the path is
  `tools/council/council.py`).
  `list` shows the members and which CLIs are installed; `--dry-run` prints
  the commands without calling anyone; `--members a,b` or `--council <name>`
  picks a line-up; `--adversarial` is the pass for auth, billing and
  data-migration PRs (use it with `--council security`).
- Commit first. The runner diffs `HEAD` against the remote's default branch
  (`--base <remote>/<branch>` for anything else), writes the diff, one shared
  prompt and a snapshot of the head commit to a results folder, and runs the
  members at the same time, each read-only inside that snapshot. Uncommitted
  edits are not reviewed; the summary says when the checkout held more than
  the commit. The results folder must be outside any git checkout.
- **Exit 0** = every member answered. **Exit 10** = at least one member did
  not review (CLI missing, not signed in, timeout, empty or truncated
  answer). **Exit 20** = the run could not start. Read `summary.md` in the
  results folder; each member's answer is in `<member>/result.md`.
- **A member that cannot run is never a gate.** Name it and the reason in the
  PR body, put the fix on the central runbook if it needs the user (for example
  `codex login`), and go on. Re-run that member if it comes back before the
  PR lands. A failed review is never reported as a clean one.
- PR body, one line per member: `Council review: <member> <verdict>, <n>
  findings (<head sha>)`, or `Council review: <member> owed: <reason>`. Fix
  each finding or answer it there, naming the member.
- A repo may commit `.agents/council.toml` to add members to the default
  seating or define named councils, from the members above (it is read from
  the base branch, never from the change under review). It cannot define a
  member, and it cannot remove the council: a repo's `AGENTS.md` adds
  reviewers, it does not replace these.
- To add a model: add a `[members.<name>]` block and list it in `default` or a
  council. Nothing else changes. The runner refuses the Sol line and the bare
  `gpt-5.6` alias whatever the file says, and `max` effort without
  `--allow-max` (the user's approval).
- The shared prompt is `tools/council/prompt.md` beside the runner. If the
  runner is missing (the `.claude_code` checkout is behind), run the members
  by hand with the per-CLI commands below and the same prompt.

What each CLI loads at start-up (measured 2026-11-25, headless, Windows):

| CLI | Global rules | Project rules | Limit seen |
|---|---|---|---|
| Codex 0.163.0 | `~/.codex/AGENTS.md`, whole | `AGENTS.md`, whole | 48 KB combined arrived intact |
| agy 1.5.16 | `~/.gemini/AGENTS.md` and `GEMINI.md`, whole | `AGENTS.md` and `GEMINI.md`; an `@AGENTS.md` line is not expanded | **cuts one file at 22,035 bytes**, with a `<truncated N bytes>` marker |
| Copilot 1.0.112 | `~/.copilot/copilot-instructions.md`, whole | `AGENTS.md`, `CLAUDE.md` and `GEMINI.md` | none seen at 27 KB |

So keep every `AGENTS.md` under 21 KB, and remember Copilot reads a repo's
`CLAUDE.md` too: "Claude-only" text there still reaches it.

Gemini CLI (`gemini`, not tested here) is a fifth reader: by default it loads
only `GEMINI.md` and reaches other files through `@file` imports. So a
repo's `GEMINI.md` keeps `@AGENTS.md` as its first line, exactly as
`CLAUDE.md` does for Claude Code. agy leaves that line unexpanded and loads
`AGENTS.md` itself, so the rules do not arrive twice.

## Ratings

Higher is better. Assumes paid Claude + ChatGPT subscriptions at medium
reasoning. `quota` = how gently the model uses the relevant plan's allowance
(not API price). Intelligence = unsupervised problem-solving; taste = UI/UX,
code/API design, copy.

| model         | quota | intelligence | taste |
|---------------|---:|---:|---:|
| fable-5       | 6 | 9 | 9 |
| opus-5        | 7 | 9 | 8 |
| sonnet-5      | 8 | 7 | 7 |
| gpt-6-astra   | 9 | 9 | 9 |
| gpt-5.6-sol   | 8 | 9 | 9 |
| gpt-5.6-terra | 9 | 9 | 8 |
| gpt-5.6-luna  | 10 | 8 | 7 |
| gemini-4-neon | — | — | — |

Neon is unrated (added 2026-11-24, reviews only). Rate it from its first
reviews here rather than from launch claims.

These are routing scores, not universal benchmarks — re-rate from observed work
if plan limits or behavior change. Codex usage is included with the ChatGPT
subscription (marginal dollar cost ≈ zero while allowance remains).

Astra notes (2026-09-22): rated approximately equal to Fable and Sol in
reasoning. OpenAI reports about one third of Sol's token use in the Codex
harness and about half as many high-severity misaligned-behavior flags as Sol,
which is why quota is 9 and why it is allowed on write jobs (below). The
system card also places it at "Critical" cybersecurity capability with reduced
chain-of-thought transparency, so the commit-first rule and the guard hooks
stay on. The local Codex model cache reports a 272k context window; some
third-party guides claim 1M. Use the local number.

**Luna caveat:** `gpt-5.6-luna` was absent from the Windows Codex model cache
on 2026-09-21 (Sol, Terra, Astra, 5.5 present). Treat it as possibly retired
for ChatGPT-sign-in Codex; verify with `codex` before routing to it, and fall
back to Astra at `low`.

The table lists only models you can actually route to. Add a row only for a
model you have access to.

## Standing config (2026-09-22)

`~/.codex/config.toml`: `model = "gpt-6-astra"`, `model_reasoning_effort = "high"`.
Keep the same default in every runtime you use (for example Windows and
WSL). Every command
in this guide still pins `-m gpt-6-astra`, so the default is only a backstop.
Agents never run Sol (AGENTS.md, "Security").

Before 2026-09-22 the default was Sol at `max`; the backup is
`~/.codex/config.toml.bak-<timestamp>` beside the file.

## Reasoning effort (Codex)

The full effort scale in Codex CLI ≥0.145.0 is
`none < minimal < low < medium < high < xhigh < max < ultra`. `ultra` is an
effort value (proactive multi-agent behavior) and consumes allowance fastest of
all: fan-out means multiple agents burning tokens at once. Quota impact: treat
`xhigh` ≈ one step worse, `max` ≈ two steps worse, `ultra` worse than `max`.

**Astra accepts `low`, `medium`, `high`, `xhigh`, `max` (and `ultra` in the
desktop app). It rejects `none` and `minimal`** — a call that passes
either fails, so use `low` as Astra's floor.

The CLI takes any accepted effort through `-c model_reasoning_effort=<e>`,
including `max`; `max` still needs the user's approval.

`ultra` rules: use it only deliberately, never as the WSL config default, and
**never with Sol**. If ultra is worth trying it is Astra, on a
committed tree, in your own terminal.

Pick the model first, then the lowest effort that reliably clears the task:

| effort | use it for |
|---|---|
| `none` / `minimal` / `low` | Search, formatting, inventory, simple edits — cheap to verify. Astra: `low` only. |
| `medium` | Default: clear-spec implementation, tests, ordinary debugging, routine analysis. |
| `high` | Ambiguous bugs, unfamiliar code, multi-file changes, concurrency. Astra's standing default. |
| `xhigh` | Subtle failure modes, migrations-adjacent analysis, adversarial depth — only when failure is expensive or a lower effort missed. |

Don't raise effort because a task is *large*; raise it when it's ambiguous,
non-local, hard to verify, or costly to get wrong.

Practical defaults (**always prefer Astra over Terra**):

- `gpt-6-astra` + `low`/`medium` — bulk, mechanical, easily verified work.
- `gpt-6-astra` + `high` — implementation, investigation, difficult bugs, and
  every review pass. This is the default the config carries.
- `gpt-6-astra` + `xhigh` — adversarial depth: the adversarial pass on auth,
  billing and data-migration PRs, and any review where `high` missed.
- `gpt-5.6-terra` — only when the user names it, or when Astra is unavailable
  (rate limit, outage). Luna likewise, if it is still listed.
- `gemini-4-neon-high` (through `agy`) — a default council member,
  read-only. See "Neon reviews through agy".
- Sol — never from an agent; a Sol review is the user's, in their own
  terminal.

## Routing rules

- Defaults, not limits. If output misses the bar, retry with a stronger model
  or higher effort without asking. Judge the result, not the label.
- For work that ships: intelligence > taste > quota.
- Bulk/mechanical: Astra at `low` — or Claude-side Haiku/Sonnet when live
  session context matters more than preserving Claude allowance. Terra is
  the fallback, not the default.
- User-facing UI, copy, or API design: taste ≥ 8 for the final pass — Fable
  or Astra as author, Astra as reviewer (a Sol review is the user's to run
  themselves).
- Important plans/implementations: the author's own review **plus** the
  council. For auth, billing, or data migration: the council's adversarial
  pass too, and reconcile disagreements explicitly.
- The **Claude-side spawned-agent ladder is unchanged** (Haiku = fully-specified
  mechanical implementers, Sonnet = integration/low-risk review, Fable/Opus =
  prod-gating reviews + orchestration). Haiku stays fine for fully-specified
  mechanical tasks with cheap verification.

## Write access — which Codex models may run a write-capable `codex exec`

| model | rescue (`-s workspace-write`) | review (`-s read-only`) |
|---|---|---|
| `gpt-6-astra` | yes, commit-first | yes (pin `-m gpt-6-astra`) |
| `gpt-5.6-terra` | yes, fallback only | yes, fallback only |
| `gpt-5.6-luna` | yes, if still listed | yes, if still listed |
| `gpt-5.6-sol` | **never** | the user's own terminal only |

Commit-first for every writer: clean `git status` before the run, review the
diff after. Long or multi-file jobs run under Bash `run_in_background`.

## Reaching Codex from any agent CLI

Agents call the local Codex CLI (≥0.153.1 for Astra) from their shell.
It uses that install's auth and `~/.codex/config.toml`. The `openai-codex`
plugin's `/codex:*` slash commands are **not** used: they are user-only, and
cloud and project sessions do not have them. Every call pins
`-m gpt-6-astra` and an explicit `-c model_reasoning_effort=<e>`.

- **Council review** — the runner above builds this for the `codex` members:
  `codex exec -m gpt-6-astra -c model_reasoning_effort=<effort> -c mcp_servers={} -s read-only -C <repo> --skip-git-repo-check --ephemeral -o <result.md> - < <prompt.md>`
  (generic `exec` with the shared prompt, so Astra answers the same question
  in the same shape as the other members; `-c mcp_servers={}` because an MCP
  server is a write channel the file sandbox does not cover; `<repo>` is the
  run's `tree/` snapshot). `<effort>` is `high`, or `xhigh`
  for the adversarial pass.
- **Quick manual review** — commit first, then the built-in reviewer:
  `codex exec -s read-only -C <repo> review -m gpt-6-astra -c model_reasoning_effort=high --ephemeral -o <result.md> --base <remote>/<base>`
  `<base>` is the PR's real base branch (`main` or `master`). `--commit <sha>`
  reviews one commit; `--uncommitted` is a pre-commit look only, never the gate.
- **Rescue** (investigation / fix delegation, writes) — clean `git status`,
  task written to a file, then:
  `codex exec -m gpt-6-astra -c model_reasoning_effort=<effort> -s workspace-write -C <repo> --ephemeral -o <result.md> - < <task.md>`
  Terra only as a named fallback. Never Sol, never the bare `gpt-5.6` alias.

Always `-s read-only` on reviews (`exec` can write without the sandbox flag).
Reconcile every review finding in the PR body. If the CLI cannot run, it is
not a gate: say so in the PR body and go on. `gpt-5.6` is an alias for Sol —
never use the bare alias.

**Auth expires silently.** On 2026-09-22 a WSL `codex exec` returned
`401 Unauthorized` / "access token could not be refreshed". Every `codex`
call fails the same way until the user runs `codex login` in a terminal.
When a Codex call fails with 401, report that as the cause, not a model or
plugin fault.

**On any Codex auth failure** the member is unavailable, not broken, and the
PR does not wait (same rule as every council member):

1. Stop the Codex step. Other work in the session continues.
2. Tell the user in its own paragraph, with the exact command (`codex login`,
   in the runtime that failed), and add it to the central runbook
   (`runbook add`).
3. Record `Council review: astra owed: auth` in the PR body and go on with
   the other members.
4. Re-run the Astra review if the login is restored before the PR lands.

## Neon reviews through agy (2026-11-24)

Gemini 4 Neon is a default council member: same moment as the others
(committed branch, before push), same diff, findings reconciled in the PR
body with the member named. It is a third model family, so it catches what
both Claude and Astra assume. **Reviews only**: Neon is not cleared for write
jobs. The council runner builds the command below; this section is the
measured behaviour behind it and the by-hand form.

Facts verified 2026-11-24 (agy 1.5.16 Windows, 1.5.13 WSL; both recipes
below ran end to end from an untrusted directory and returned a review):

- Model IDs carry the effort: `gemini-4-neon-low|medium|high|xhigh`. Reviews
  use `gemini-4-neon-high`; `xhigh` only when `high` missed. There is no
  separate `max`/`ultra` for Neon. Check `agy models` if an ID is refused.
- **Read-only = `--mode plan --sandbox`.** Tested: asked to create a file in
  that mode, it wrote only a plan into its own `~/.gemini/antigravity-cli/`
  folder and the target file was not created. Never pass
  `--dangerously-skip-permissions` or `--mode accept-edits|auto` on a review.
- Headless sandbox mode **refuses every shell command, `git` included.** So
  the agent writes the diff to a file and Neon reads it (plus any repo file it
  wants) through `--add-dir`. Do not widen its permissions to let it run git.
- **File reads need a session-only allow rule.** Headless mode cannot prompt,
  so outside a folder listed in agy's `trustedWorkspaces` (which follows the
  *current directory*, not `--add-dir`) even `read_file` is auto-denied.
  Always pass `--settings '{"permissions":{"allow":["read_file(*)","list_dir(*)"]}}'`
  (session only, never saved). Path-scoped rules (`read_file(<repo>/**)`)
  failed in testing, so `*` it is. That matches Codex's `-s read-only`, which
  also reads anything and writes nothing.
- **A denied tool exits 0 with an empty `result.md`**, the refusal on stderr.
  Empty output is a failed review, never "no findings": capture stderr and
  check the size.
- **The prompt is an argument, not stdin.** `-p` reads the next token as the
  prompt; piping into it exits 2. Use `-p="<text>"`, with the text read from
  a file.
- agy has no `-C`: list every directory it may read with `--add-dir`.

Procedure — commit first. Let the runner prepare the folder, then run the
one member by hand. `O` must be a new, empty folder outside any git checkout;
add `--base <remote>/<branch>` when the PR's base is not the remote's default
branch. Bash / WSL:

```bash
R=/abs/path/to/repo; O=/abs/scratch/neon-run
python3 /path/to/.claude_code/tools/council/council.py review --repo "$R" --members neon --dry-run --out "$O"
# stop here unless that exited 0
S='{"permissions":{"allow":["read_file(*)","list_dir(*)"]}}'
mkdir -p "$O/neon"
( cd "$O/tree" && agy --model gemini-4-neon-high --mode plan --sandbox --settings "$S" --add-dir "$O/tree" --add-dir "$O" -p="$(cat "$O/prompt.md")" > "$O/neon/result.md" 2> "$O/neon/err.txt" )
test -s "$O/neon/result.md" || { echo "Neon review FAILED:"; cat "$O/neon/err.txt"; }
```

PowerShell (Windows):

```powershell
$R = 'D:\abs\path\to\repo'; $O = 'C:\abs\scratch\neon-run'
python C:\path\to\.claude_code\tools\council\council.py review --repo $R --members neon --dry-run --out $O
# stop here unless $LASTEXITCODE is 0
$S = '{"permissions":{"allow":["read_file(*)","list_dir(*)"]}}'
New-Item -ItemType Directory -Force "$O\neon" | Out-Null
Push-Location "$O\tree"
agy --model gemini-4-neon-high --mode plan --sandbox --settings $S --add-dir "$O\tree" --add-dir $O -p="$(Get-Content -Raw "$O\prompt.md")" > "$O\neon\result.md" 2> "$O\neon\err.txt"
Pop-Location
if ((Get-Item "$O\neon\result.md").Length -eq 0) { 'Neon review FAILED:'; Get-Content "$O\neon\err.txt" }
```

The dry run calls nobody. It writes `change.diff`, `commits.txt`, the filled
`prompt.md`, a snapshot of the head commit (`tree/`) and copies of the rule
files (`rules/`) to `<O>`, and prints each member's command. The prompt
names those paths, so Neon needs only `<O>` and `<O>/tree`, as absolute
paths (it cannot `cd`).

Without the runner at all (the `.claude_code` checkout is behind): in an
empty folder write `git -C <repo> diff <remote>/<base>...HEAD` to
`change.diff` and `git -C <repo> log --oneline <remote>/<base>..HEAD` to
`commits.txt`, fill the `{{FIELDS}}` of `tools/council/prompt.md` by hand,
and pass `--add-dir` for the repo, that folder, `~/.config/agents` and
`~/.claude/instructions`. `<base>` is the PR's real base branch (`main`,
`master`, ...), never assumed; stop if the fetch or the diff fails, because
an empty diff still produces an answer.

Long reviews: run in the background (Claude Code: Bash `run_in_background`)
and read `result.md`. If agy is missing, not signed in, or the model is
refused, Neon is not a gate: say so in the PR body and go on.

**Keep the stop-review gate OFF** (verified off 2026-07-23). It can create long
Claude/Codex loops that drain both pools. Invoke reviews deliberately at
commit/PR boundaries and before user-facing or high-risk work ships.

## Copilot reviews (measured 2026-11-25, Copilot CLI 1.0.112, Windows)

Copilot is a defined council member (`copilot`) that is not seated by
default. Facts from the live test:

- Headless, read-only, prompt on stdin:
  `copilot -C <repo> -s --no-color --no-auto-update --no-ask-user --disable-builtin-mcps --no-custom-instructions --stream off --model <model> --reasoning-effort <effort> --deny-tool=write --deny-tool=shell --deny-tool=memory --allow-tool=read --add-dir <results folder> < <prompt.md> > <result.md> 2> <err.txt>`
  A write probe in this mode was refused. Unset `COPILOT_ALLOW_ALL`,
  `COPILOT_ALLOW_ALL_TOOLS` and `COPILOT_ALLOW_ALL_PATHS` for the call: an
  inherited allow-all undoes the deny rules (the runner drops them).
- It serves its own model catalog. On this account `gpt-6-astra`, the Opus
  and Fable models and Gemini 4 Neon are **not** available; usable ids
  include `gpt-6.1-terra`, `claude-sonnet-5.5`, `gemini-4-hydrogen`,
  `grok-4.7`, `kimi-k3`. There is no non-interactive model list: run
  `copilot` and `/model`. An unavailable model exits 1 with an empty answer.
- The catalog lists Sol ids. They are disabled by plan today, not by rule;
  the ban is the rule, and the runner enforces it.
- `--reasoning-effort` is per model; `claude-haiku-4.5` rejects the flag.
- It is signed in through the GitHub account; no separate login was needed.

## Workflows and subagents

Claude Code's native subagent `model:` field selects Claude models only. To use
Codex or Neon from a workflow, have the agent run the `codex exec` or `agy`
forms above with a complete, self-contained prompt file and a pinned model.

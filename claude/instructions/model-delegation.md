# Model delegation — cross-provider routing (Claude + Codex)

Adapted 2026-07-23 from the author's original routing notes, reconciled against the actually-installed `openai-codex` plugin and
`~/.codex/config.toml`. Revised 2026-09-22 for GPT-6 Astra. The compact rules
live in `~/.config/agents/AGENTS.md` ("Model delegation & cross-provider
review"); this file is the full guide. The Sol lockdown lives in
`~/.claude/CLAUDE.md` (Codex delegation section) because it governs how
Claude Code invokes Codex.

## Why delegate across providers

A different model family does not share the author's assumptions. The best
shipping loop: **write with Claude, audit with Codex, reconcile the findings.**
Cost routing is secondary; independent review is the primary benefit. The OpenAI
pool is also separate from the Claude plan, so self-contained Codex work
preserves Claude headroom.

We already run multi-pass Claude reviews plus the GitHub Claude Code App review
on PRs, so treat Codex review as an *additional independent* pass at commit/PR
boundaries — judge over time whether it earns its keep.

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
A second machine may run the same model at `ultra`. Every command
in this guide still pins `-m gpt-6-astra`, so the default is only a backstop.
Agents never run Sol (see the Sol section in `~/.claude/CLAUDE.md`).

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
- `gpt-6-astra` + `xhigh` — adversarial depth when `high` missed.
- `gpt-5.6-terra` — only when the user names it, or when Astra is unavailable
  (rate limit, outage). Luna likewise, if it is still listed.
- Sol — optional second reviewer, review commands only, by config edit.

## Routing rules

- Defaults, not limits. If output misses the bar, retry with a stronger model
  or higher effort without asking. Judge the result, not the label.
- For work that ships: intelligence > taste > quota.
- Bulk/mechanical: Astra at `low` — or Claude-side Haiku/Sonnet when live
  session context matters more than preserving Claude allowance. Terra is
  the fallback, not the default.
- User-facing UI, copy, or API design: taste ≥ 8 for the final pass — Fable
  or Astra as author, Astra or Sol as reviewer.
- Important plans/implementations: Claude review **plus** an independent Codex
  review (Astra by default). For auth, billing, or data migration: an
  adversarial review through the `codex` CLI (below) and reconcile
  disagreements explicitly.
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

## Reaching Codex from Claude Code

Claude Code calls the local Codex CLI (≥0.153.1 for Astra) from the Bash tool.
It uses that install's auth and `~/.codex/config.toml`. The `openai-codex`
plugin's `/codex:*` slash commands are **not** used: they are user-only, and
cloud and project sessions do not have them. Every call pins
`-m gpt-6-astra` and an explicit `-c model_reasoning_effort=<e>`.

- **Review** — commit first. Branch review against the base:
  `codex exec -s read-only -C <repo> review -m gpt-6-astra -c model_reasoning_effort=high --ephemeral -o <result.md> --base origin/main`
  `--commit <sha>` reviews one commit; `--uncommitted` is a pre-commit look
  only, never the gate.
- **Adversarial review** — commit first, write the prompt to a file
  (`<role>` adversarial, `<target>` branch and base, `<focus>`, `<output>`
  severity + file:line + scenario + fix), then:
  `codex exec -m gpt-6-astra -c model_reasoning_effort=high -s read-only -C <repo> --ephemeral -o <result.md> - < <prompt.md>`
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

**Procedure on any Codex auth failure:**

1. Stop the Codex step. Other work in the session may continue.
2. Prompt the user to run `codex login` in a terminal. Make the
   prompt visible: its own paragraph, the exact command, and what is blocked.
3. Wait for one of two answers. Either the user confirms the login, or gives
   a reason to skip (for example, the OpenAI service is down). Never assume.
4. On confirmation, retry the same Codex call. On a skip, record the skipped
   review or task in the session summary and continue without it.

**Keep the stop-review gate OFF** (verified off 2026-07-23). It can create long
Claude/Codex loops that drain both pools. Invoke reviews deliberately at
commit/PR boundaries and before user-facing or high-risk work ships.

## Workflows and subagents

Claude Code's native subagent `model:` field selects Claude models only. To use
Codex from a workflow, have the agent run the `codex exec` forms above with a
complete, self-contained prompt file and a pinned model.

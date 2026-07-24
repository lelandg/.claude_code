# Model delegation — cross-provider routing (Claude + Codex/GPT-5.6)

Reconciled against the officially installed `openai-codex` Claude Code plugin
and `~/.codex/config.toml` (verified 2026-07-23). The compact rules live in
`~/.config/agents/AGENTS.md` ("Model delegation & cross-provider review");
this file is the full guide.

## Why delegate across providers

A different model family does not share the author's assumptions. The best
shipping loop: **write with Claude, audit with Codex, reconcile the findings.**
Cost routing is secondary; independent review is the primary benefit. The OpenAI
pool is also separate from the Claude plan, so self-contained Codex work
preserves Claude headroom.

If you already run multi-pass Claude reviews, treat Codex review as an
*additional independent* pass at commit/PR boundaries — judge over time whether
it earns its keep.

## Ratings

Higher is better. Assumes paid Claude + ChatGPT subscriptions at medium
reasoning. `quota` = how gently the model uses the relevant plan's allowance
(not API price). Intelligence = unsupervised problem-solving; taste = UI/UX,
code/API design, copy.

| model | quota | intelligence | taste |
|---|---:|---:|---:|
| fable-5 | 6 | 9 | 9 |
| opus-5 | 7 | 9 | 8 |
| sonnet-5 | 8 | 7 | 7 |
| gpt-5.6-sol | 8 | 9 | 9 |
| gpt-5.6-terra | 9 | 9 | 8 |
| gpt-5.6-luna | 10 | 8 | 7 |

These are routing scores, not universal benchmarks — re-rate from observed work
if plan limits or behavior change. Codex usage is included with the ChatGPT
subscription (marginal dollar cost ≈ zero while allowance remains).

## Sol restriction — CRITICAL (standing policy; lift it deliberately)

**`gpt-5.6-sol` is REVIEW-ONLY.** There are repeated reports of Sol taking
destructive autonomous action in pursuit of a goal (deleting home directories,
intruding into other systems). Until you deliberately decide otherwise:

1. Sol may only run through the read-only review commands
   (`/codex:review`, `/codex:adversarial-review`). **Never** on
   `/codex:rescue` or any implementation/investigation job that can write.
2. **Commit everything before any Sol run.** `git status` must be clean —
   commit (or stash) first, then review the committed work
   (`--base <ref>` / `--scope branch` for branch review).
3. Keeping `model = "gpt-5.6-sol"` as the `~/.codex/config.toml` default is
   **deliberate**: the review commands can't pin a model, so they inherit
   Sol from config — which is exactly the one place Sol is allowed. The flip
   side: a bare `/codex:rescue` with no `--model` flag would ALSO inherit Sol.
   Therefore **every `/codex:rescue` MUST pin `--model` explicitly**
   (terra or luna). No exceptions. (A hookify rule can enforce this — see
   `~/.claude/hookify-rules/`.)

## Reasoning effort (Codex)

The full effort scale in Codex CLI ≥0.145.0 is
`none < minimal < low < medium < high < xhigh < max < ultra`. **`ultra` is an
effort value too** (as of 0.145.0 it replaces the old standalone multi-agent
mode — "proactive multi-agent behavior") and consumes allowance fastest of
all: fan-out means multiple agents burning tokens at once. Quota impact: treat
`xhigh` ≈ one step worse, `max` ≈ two steps worse, `ultra` worse than `max`.

The plugin's `--effort` flag only accepts up to `xhigh` — its companion script
hard-whitelists `none|minimal|low|medium|high|xhigh` and rejects `max`/`ultra`,
even in the latest release (v1.0.6, checked 2026-07-23). To reach `max`, leave
`--effort` off the call so the `~/.codex/config.toml` default applies (or run
`codex` directly).

A Sol + `max` config default is workable when reviews are the only unflagged
path and plan credits absorb the burn — drop the default to `high` if limits
start biting. Consequence: the **mandatory `--model` + `--effort` pin on every
`/codex:rescue` matters even more** — an unpinned rescue would inherit Sol at
max with write access, the single worst combination under the lockdown.

`ultra` rules while the Sol lockdown holds: use it only deliberately, never as
a config default, and **never with Sol** — proactive multi-agent autonomy is
exactly the behavior the lockdown exists to contain. If ultra is ever worth
trying, it's Terra, on a committed tree, in your own terminal.

Pick the model first, then the lowest effort that reliably clears the task:

| effort | use it for |
|---|---|
| `none` / `minimal` / `low` | Search, formatting, inventory, simple edits — cheap to verify. |
| `medium` | Default: clear-spec implementation, tests, ordinary debugging, routine analysis. |
| `high` | Ambiguous bugs, unfamiliar code, multi-file changes, concurrency. |
| `xhigh` | Subtle failure modes, migrations-adjacent analysis, adversarial depth — only when failure is expensive or a lower effort missed. |

Higher effort consumes more of the Codex allowance. Don't raise effort because
a task is *large*; raise it when it's ambiguous, non-local, hard to verify, or
costly to get wrong.

Practical defaults:

- `gpt-5.6-luna` + `low`/`medium` — bulk, mechanical, easily verified work.
- `gpt-5.6-terra` + `medium` — default implementation and investigation.
- `gpt-5.6-terra` + `high`/`xhigh` — difficult bugs and high-stakes work
  (this replaces the upstream advice of "Sol + high" while the Sol
  restriction holds).
- Sol (via review commands only) — the independent final review pass.

## Routing rules

- Defaults, not limits. If output misses the bar, retry with a stronger model
  or higher effort without asking. Judge the result, not the label.
- For work that ships: intelligence > taste > quota.
- Bulk/mechanical: Luna or Terra — or Claude-side Haiku/Sonnet when live
  session context matters more than preserving Claude allowance.
- User-facing UI, copy, or API design: taste ≥ 8 for the final pass — Fable,
  or Sol *as reviewer*.
- Important plans/implementations: Claude review **plus** an independent Codex
  review. For auth, billing, or data migration: adversarial review
  (`/codex:adversarial-review`) and reconcile disagreements explicitly.
- The **Claude-side spawned-agent ladder is unchanged** (Haiku = fully-specified
  mechanical implementers, Sonnet = integration/low-risk review, Fable/Opus =
  prod-gating reviews + orchestration). "Never Haiku for shipping work" does
  not override the ladder — Haiku stays fine for fully-specified mechanical
  tasks with cheap verification.

## Reaching GPT-5.6 from Claude Code

Use the official `openai-codex` marketplace plugin (`codex`). It reuses the
local Codex CLI install, auth, and `~/.codex/config.toml` — never wrap
`codex exec` in custom shell code.

- `/codex:review [--base <ref>] [--scope auto|working-tree|branch]` —
  read-only native review of local git state.
- `/codex:adversarial-review [focus ...]` — challenge review (assumptions,
  design, tradeoffs); supports the same scope flags plus focus text.
- `/codex:rescue --model <m> --effort <e> [--background] <task>` —
  investigation / fix delegation. **Always pin `--model gpt-5.6-terra` or
  `gpt-5.6-luna`** (Sol forbidden here — see restriction above).
- `/codex:status`, `/codex:result`, `/codex:cancel` — manage background jobs.
- `/codex:setup` — health check / review-gate toggle.

Notes: there is **no `/codex:transfer`** in the installed plugin. `gpt-5.6` is
an alias for Sol — never use the bare alias. Multi-file rescue jobs should
normally use `--background`.

**Keep the stop-review gate OFF.** It can create long Claude/Codex loops that
drain both pools. Invoke reviews deliberately at commit/PR boundaries and
before user-facing or high-risk work ships.

## Workflows and subagents

Claude Code's native subagent `model:` field selects Claude models only. To use
GPT-5.6 from a workflow, delegate through the plugin's commands or the
`codex:codex-rescue` agent with a complete, self-contained task — never a raw
CLI wrapper.

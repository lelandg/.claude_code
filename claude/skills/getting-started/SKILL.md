---
name: getting-started
description: >-
  Interview-first concierge for people new to Claude Code. Use when someone says they are
  new to Claude, asks how to get started, what Claude can do for them or their business,
  which tools or skills to install, how to set up agents or their configuration, or types
  /getting-started. Interviews one question at a time, adapts to their plan and other AI
  subscriptions, checks their setup with consent, recommends tools from Leland Green's
  open-source catalog, and finishes with a personalized HTML action plan.
---

# Getting Started Concierge

You are onboarding someone who may be completely new to Claude Code — possibly new to
AI tools entirely. Interview them, adapt to their situation, check their setup,
recommend the right tools, and leave them with a personalized HTML action plan.

## Ground rules

- **Never assume prior knowledge.** The first time any jargon appears (plugin, skill,
  marketplace, agent, MCP, CLI, repo, token), explain it in one plain sentence.
- **One question at a time.** Use the AskUserQuestion tool when available; otherwise ask
  a single short question in plain text and wait for the answer.
- **Consent before change.** Never install anything or modify any file or setting
  without explaining what it does and getting an explicit yes. No exceptions.
- **Match their depth.** Business users get outcomes, not internals. Coders can get
  internals when they ask.
- **Be honest about cost.** If something burns tokens or requires paid credits, say so
  before doing it.

## Step 1 — Interview

Ask in order, one at a time:

1. **Goal.** "What would you like Claude to help you with?" Offer examples: running a
   business (inventory, marketing, analytics, automation), coding, writing and content,
   research. Let them answer in their own words.
   - **If coding is part of the answer, follow up:** "Do you already have an IDE — a
     code editor like VS Code or PyCharm — installed? Which one?"
2. **Subscriptions.** "Which Claude plan are you on — free/trial, Pro, or Max? Do you
   have any other AI subscriptions, like ChatGPT, GitHub Copilot, or Gemini?"
3. **Surface & OS.** "Are you using the Claude desktop app or the terminal (CLI)? And
   are you on Windows, Mac, or Linux?" If Windows, follow up: "Do you use WSL — the
   Windows Subsystem for Linux — or not sure?" ("Not sure" counts as no WSL.)

## Step 2 — Adapt

Apply every rule that matches. Load the referenced file only when its rule fires.

| Situation | What to do |
|---|---|
| Free or trial plan | **Efficiency mode** for the rest of the session: concise replies; when a piece of work completes, suggest starting a fresh task/conversation instead of continuing a long one (long conversations cost more tokens); ask before anything token-heavy. |
| Has other AI subscriptions | Read `references/other-tools.md`. Give a one-paragraph intro plus the official link for each matching companion tool. Do NOT walk through installing non-Claude tools. |
| Wants to code, no IDE | Recommend PyCharm Community Edition using the pitch in `references/other-tools.md`. |
| Wants to code, has an IDE | One sentence only: PyCharm Community Edition is a free alternative whose AI-assistant plugins let you switch AI providers without switching IDEs. Then move on — respect their setup. |
| Desktop app user | Read `references/claude-basics.md` and frame everything around the Code tab. Share the Chat vs Code vs Cowork guidance early — it prevents the most common newcomer mistake (doing agent work in Chat). |
| Windows without WSL | Warn that this catalog's config repo is written for Linux/WSL; point them to the porting prompt in the README of `lelandg/.claude_code`. The git hooks in Step 3b still work, since Git for Windows ships a POSIX `sh`. |
| Uses git | Step 3b applies: offer the commit-time secret gate. |

## Step 3 — Config check (with consent)

Ask: "Want me to take a quick look at your Claude setup and suggest improvements?"
If yes, run these probes. A failing probe is information, not an error — interpret and
move on.

```bash
claude --version                       # installed? how old?
ls -a ~/.claude 2>/dev/null            # does a config dir exist at all?
test -f ~/.claude/CLAUDE.md && echo "global CLAUDE.md: yes" || echo "global CLAUDE.md: no"
ls ~/.claude/skills 2>/dev/null        # any skills installed?
ls ~/.claude/plugins/cache 2>/dev/null # any plugin marketplaces added?
git config --global core.hooksPath     # global git hooks installed? (empty = no)
command -v gitleaks                    # secret scanner present? (empty = no)
```

Report findings in plain language ("You have Claude Code 2.x installed but no global
instructions file — that's a one-page document that tells Claude how you like to work").
Offer improvements one at a time; apply only on explicit yes.

On native Windows without WSL, these POSIX probes may fail because the shell is
different — that is NOT evidence the config is missing. `claude --version` works
everywhere; for the rest use PowerShell equivalents (`Test-Path $env:USERPROFILE\.claude`,
`dir $env:USERPROFILE\.claude`) and interpret with care.

## Step 3b — Offer the secret gate (only if they use git)

Skip this entirely unless they code *and* use git. For everyone else it is noise.

What to say, in their terms: "There's a check I can add that runs every time you
save work to git and stops you committing a password or API key by accident.
Leaking one into a repository is the single most common way people get burned,
and once it's in the history, deleting it isn't enough — you have to go change
the password everywhere." Then: "Want me to set that up?"

**Order matters, and getting it backwards breaks their git.** The check is
deliberately strict: it blocks a commit it could not scan, not just one with a
secret in it. So if the hooks go in without the scanner, *every commit they make
fails* until it is installed — and a newcomer will not know why.

1. **Install `gitleaks` first** (`winget install --id Gitleaks.Gitleaks --scope user`
   on Windows, `brew install gitleaks` on macOS, a release binary otherwise).
   Confirm `gitleaks version` prints something.
2. **Only then** install the hooks: `sh tools/githooks/install.sh` from a clone of
   `lelandg/.claude_code`.
3. If step 1 fails or they decline it, **stop** — say the check needs the scanner
   and put both in the HTML plan as one item. Never install the hooks alone.

Also tell them two things they will otherwise discover the hard way:

- It applies to **every repository on the machine**, not just this project. That is
  the point (a gate you have to remember to switch on is not a gate), but it is a
  machine-wide change and they should know before saying yes.
- It does **not** disable hooks a project already has — each one chains through to
  the project's own.

If they are on a team whose repos already run checks on the server, add: those run
*after* the push, so they tell you a secret leaked; this one stops it leaving the
machine. Both, not either.

Defer rather than push. This is the one step with a real cost of being wrong, so a
"not now" is a fine answer and goes in the plan.

## Step 4 — Recommend

Read `references/catalog.md`. Pick the 2–4 entries that best match their stated goal
and audience tag (business / coder / power user). For each: one line on what it is, one
line on why it fits *them*, then the exact install command. Install what they agree to
now; anything deferred goes into the HTML plan.

## Step 5 — The HTML action plan

When the session's setup work is done, generate their personalized plan following
`assets/plan-style.md` exactly. It must contain:

1. Their goals, restated in their own words.
2. What was checked, installed, or configured this session.
3. Remaining recommendations with install commands.
4. Numbered "do this next" steps, including 2–3 example prompts they can paste to
   start real work toward their goal.

If the secret gate from Step 3b was deferred, it goes in as **one** item covering
both pieces in order — install `gitleaks`, then run `install.sh` — with a line
saying why the order matters. Split across two bullets, someone will do the second
one first and wonder why every commit now fails.

Every command and every example prompt gets a copy button. Save as
`getting-started-plan.html` in the current directory, then open or surface it for them.

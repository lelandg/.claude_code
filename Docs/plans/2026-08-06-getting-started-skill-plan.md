# `getting-started` Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `getting-started` concierge skill — interview-first onboarding for Claude Code newcomers — and ship it as the headline skill of the `claude-config-skills` plugin in `lelandg/.claude_code`.

**Architecture:** Pure `SKILL.md` + on-demand `references/` + `assets/` — no bundled code. Files are authored live in `~/.claude/skills/getting-started/` (so Leland runs the real thing), then mirrored into the repo at `claude/skills/getting-started/` and committed there after every task.

**Tech Stack:** Markdown skill files, one self-contained HTML template (inline CSS/JS), `jq` for JSON validation, `version-manager` skill for the release.

**Spec:** `Docs/plans/2026-08-06-getting-started-skill-design.md` (approved 2026-08-06).

## Global Constraints

- Live skill dir: `~/.claude/skills/getting-started/`. Repo mirror: `/mnt/d/Documents/Code/GitHub/.claude_code/claude/skills/getting-started/`. After editing live files, every task mirrors with the exact command in its steps, then commits **in the repo**.
- The generated HTML plan must be fully self-contained: inline CSS/JS, no external requests, no CDN.
- Every command or suggested prompt shown in the HTML plan gets a copy-to-clipboard button (house style).
- Repo owners must be exact: `lelandg/.claude_code`, `lelandg/ClaudeAgents`, `lelandg/yt-transcript`, `lelandg/karpathy-task-brief`, `lelandg/ImageAI`, `Chameleon-Labs-LLC/plugins`, `Chameleon-Labs-LLC/agent-spawner`, `Chameleon-Labs-LLC/ClaudeCodeDashboard`, `Chameleon-Labs-LLC/agent-deploy`, `Chameleon-Labs-LLC/model-registry-client`.
- Never hand-edit the marketplace `metadata.version`, plugin `version`, or `CHANGELOG.md` headings — Task 7 uses `version_tool.py` for that, and ONLY Task 7 touches them.
- The skill must never install anything or change config without explicit user consent — this rule appears verbatim in SKILL.md and must survive edits.
- `Notes/` in the repo is gitignored (personal). Never `git add -f` anything under it.
- Commits use the repo's conventional style (`feat(skills): …`, `docs: …`) and end with the Claude Code co-author trailer used in recent history (`git log -3` shows the format).

---

### Task 1: SKILL.md — the concierge flow

**Files:**
- Create: `~/.claude/skills/getting-started/SKILL.md`
- Mirror to: `/mnt/d/Documents/Code/GitHub/.claude_code/claude/skills/getting-started/SKILL.md`

**Interfaces:**
- Produces: the skill's contract. Later tasks MUST use these exact relative paths referenced by SKILL.md: `references/catalog.md`, `references/claude-basics.md`, `references/other-tools.md`, `assets/plan-style.md`. The generated output filename is `getting-started-plan.html`.

- [ ] **Step 1: Create the live skill directory and write SKILL.md**

Write exactly this content to `~/.claude/skills/getting-started/SKILL.md`:

````markdown
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
   are you on Windows, Mac, or Linux?"

## Step 2 — Adapt

Apply every rule that matches. Load the referenced file only when its rule fires.

| Situation | What to do |
|---|---|
| Free or trial plan | **Efficiency mode** for the rest of the session: concise replies; when a piece of work completes, suggest starting a fresh task/conversation instead of continuing a long one (long conversations cost more tokens); ask before anything token-heavy. |
| Has other AI subscriptions | Read `references/other-tools.md`. Give a one-paragraph intro plus the official link for each matching companion tool. Do NOT walk through installing non-Claude tools. |
| Wants to code, no IDE | Recommend PyCharm Community Edition using the pitch in `references/other-tools.md`. |
| Wants to code, has an IDE | One sentence only: PyCharm Community Edition is a free alternative whose AI-assistant plugins let you switch AI providers without switching IDEs. Then move on — respect their setup. |
| Desktop app user | Read `references/claude-basics.md` and frame everything around the Code tab. Share the Chat vs Code vs Cowork guidance early — it prevents the most common newcomer mistake (doing agent work in Chat). |
| Windows without WSL | Warn that this catalog's config repo is written for Linux/WSL; point them to the porting prompt in the README of `lelandg/.claude_code`. |

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
```

Report findings in plain language ("You have Claude Code 2.x installed but no global
instructions file — that's a one-page document that tells Claude how you like to work").
Offer improvements one at a time; apply only on explicit yes.

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

Every command and every example prompt gets a copy button. Save as
`getting-started-plan.html` in the current directory, then open or surface it for them.
````

- [ ] **Step 2: Verify the frontmatter parses and the description is within limits**

Run: `python3 -c "import yaml,sys; d=yaml.safe_load(open('/home/leland/.claude/skills/getting-started/SKILL.md').read().split('---')[1]); print(d['name'], len(d['description']))"`
Expected: prints `getting-started` and a number ≤ 1024.

- [ ] **Step 3: Mirror to the repo**

```bash
mkdir -p /mnt/d/Documents/Code/GitHub/.claude_code/claude/skills/getting-started
rsync -a --delete /home/leland/.claude/skills/getting-started/ /mnt/d/Documents/Code/GitHub/.claude_code/claude/skills/getting-started/
```

- [ ] **Step 4: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/.claude_code add claude/skills/getting-started
git -C /mnt/d/Documents/Code/GitHub/.claude_code commit -m "feat(skills): getting-started concierge — SKILL.md interview flow"
```

---

### Task 2: references/catalog.md — the curated OSS catalog

**Files:**
- Create: `~/.claude/skills/getting-started/references/catalog.md`
- Mirror to: `/mnt/d/Documents/Code/GitHub/.claude_code/claude/skills/getting-started/references/catalog.md`

**Interfaces:**
- Consumes: SKILL.md Step 4 reads this file and filters by the audience tags `business` / `coder` / `power user`.
- Produces: catalog entries in a fixed format: `### Name` heading, `**Audience:**` line, one-line description, `**Install:**` fenced command block.

- [ ] **Step 1: Write catalog.md**

Write exactly this content:

````markdown
# Leland Green's Open-Source Catalog

Curated for the getting-started concierge. Format per entry: what it is, who it's for,
exact install command. Owners matter — `lelandg/…` and `Chameleon-Labs-LLC/…` are
different GitHub accounts.

## Start here (almost everyone)

### Claude Code config + skills marketplace — `lelandg/.claude_code`
**Audience:** business, coder, power user
A production-tested Claude Code configuration that doubles as a plugin marketplace.
Installing the plugin gets you this concierge plus documentation, context-optimization,
and knowledge-graph skills without cloning anything.
**Install:**
```
/plugin marketplace add lelandg/.claude_code
/plugin install claude-config-skills@lelandg-claude-config
```
Power users who want the *full* config (agents, hooks, house rules) instead: clone
https://github.com/lelandg/.claude_code and follow its README / `Docs/SETUP_GUIDE.md`.

### Chameleon Labs plugin marketplace — `Chameleon-Labs-LLC/plugins`
**Audience:** business, coder, power user
Second marketplace with tool-bundled plugins: `repo-hygiene` (version + changelog
discipline), `docs-toolkit` (project documentation), `yt-transcript` (YouTube
transcripts), `humanizer` (de-AI your writing), `model-registry` (current model IDs),
`scan-source` (is this download safe?), `chameleon-agents` (example agent team).
**Install:**
```
/plugin marketplace add Chameleon-Labs-LLC/plugins
```
Then `/plugin install <name>@chameleon-labs` for any plugin above.

## Agents

### Agent Spawner — `Chameleon-Labs-LLC/agent-spawner`
**Audience:** business, power user
Scaffolds, packages, and deploys Claude agents — channel adapters (Discord, etc.),
HMAC bridges, one-command SSH deploy. After installing, Claude knows how to build you
a local agent from a description; if you build agents one at a time, it interviews you.
**Install:**
```
git clone https://github.com/Chameleon-Labs-LLC/agent-spawner
```
Then, inside Claude Code: `/agent-spawner help`.

### ClaudeAgents — `lelandg/ClaudeAgents`
**Audience:** coder, power user
A collection of ready-made agent definitions (code reviewer, researcher, test
generator, …) to drop into `~/.claude/agents/` or borrow patterns from.
**Install:**
```
git clone https://github.com/lelandg/ClaudeAgents
```

### Agent Deploy — `Chameleon-Labs-LLC/agent-deploy`
**Audience:** power user
Secure EC2 setup guide and ops toolkit for running AI coding agents (Claude Code,
Codex, Gemini, pi) on a dedicated always-on instance. For when agents outgrow your
laptop.
**Install:**
```
git clone https://github.com/Chameleon-Labs-LLC/agent-deploy
```

## Utilities

### yt-transcript — `lelandg/yt-transcript`
**Audience:** business, coder
Downloads YouTube video transcripts as text, optionally reformatted into readable
prose. Great for research and content repurposing. Also available as a plugin from the
Chameleon Labs marketplace (no clone needed):
**Install:**
```
/plugin install yt-transcript@chameleon-labs
```

### karpathy-task-brief — `lelandg/karpathy-task-brief`
**Audience:** coder
Tiny local-first CLI that turns rough coding requests into structured execution briefs
Claude can act on precisely.
**Install:**
```
git clone https://github.com/lelandg/karpathy-task-brief
```

### Claude Code Dashboard — `Chameleon-Labs-LLC/ClaudeCodeDashboard`
**Audience:** power user
Local dashboard for Claude Code: search past sessions, view memory, and more.
**Install:**
```
git clone https://github.com/Chameleon-Labs-LLC/ClaudeCodeDashboard
```

### model-registry-client — `Chameleon-Labs-LLC/model-registry-client`
**Audience:** coder
Zero-dependency Python/TypeScript clients that resolve current LLM model IDs at
runtime, so your projects never hardcode stale model names.
**Install:**
```
git clone https://github.com/Chameleon-Labs-LLC/model-registry-client
```

### ImageAI — `lelandg/ImageAI`
**Audience:** business, coder
Python image and video generator that works across LLM providers (Gemini, OpenAI,
Stability, local Stable Diffusion) from one CLI — useful for marketing assets.
**Install:**
```
git clone https://github.com/lelandg/ImageAI
```
````

- [ ] **Step 2: Verify owners are correct**

Run: `grep -oE '(lelandg|Chameleon-Labs-LLC)/[A-Za-z._-]+' ~/.claude/skills/getting-started/references/catalog.md | sort -u`
Expected: exactly the ten owner/repo pairs listed in Global Constraints (`.claude_code`, `ClaudeAgents`, `yt-transcript`, `karpathy-task-brief`, `ImageAI` under `lelandg`; `plugins`, `agent-spawner`, `ClaudeCodeDashboard`, `agent-deploy`, `model-registry-client` under `Chameleon-Labs-LLC`).

- [ ] **Step 3: Mirror and commit**

```bash
rsync -a --delete /home/leland/.claude/skills/getting-started/ /mnt/d/Documents/Code/GitHub/.claude_code/claude/skills/getting-started/
git -C /mnt/d/Documents/Code/GitHub/.claude_code add claude/skills/getting-started
git -C /mnt/d/Documents/Code/GitHub/.claude_code commit -m "feat(skills): getting-started — curated OSS catalog reference"
```

---

### Task 3: references/claude-basics.md — Claude orientation

**Files:**
- Create: `~/.claude/skills/getting-started/references/claude-basics.md`
- Mirror to: `/mnt/d/Documents/Code/GitHub/.claude_code/claude/skills/getting-started/references/claude-basics.md`

**Interfaces:**
- Consumes: loaded by SKILL.md's "Desktop app user" adaptation rule and wherever newcomer orientation is needed.

- [ ] **Step 1: Write claude-basics.md**

Write exactly this content:

````markdown
# Claude Basics for Newcomers

Plain-language orientation. Share these points as they become relevant — don't dump the
whole file on the user.

## Chat vs Code vs Cowork (desktop app)

- **Code** — where almost everything should happen. Claude can read and write files, run
  commands, install tools, and keep working through multi-step jobs.
- **Chat** — for research and conversation. It cannot touch your files. If the user asks
  Chat to "set something up," it can only talk about it.
- **Cowork** — lets Claude control your computer (click, type, see the screen). Powerful
  but slower and costlier; use it only when a task truly needs the mouse.

Rule of thumb to give users: *do almost everything in Code; Chat is for research;
Cowork is for controlling your computer.*

## Tasks and tokens

- A **token** is the unit AI usage is measured in — roughly ¾ of a word.
- Long conversations quietly get expensive: everything said so far is re-read on every
  reply. When a piece of work completes, **start a new task/conversation**. It saves
  tokens and keeps Claude sharp.
- On a free or trial plan this matters double — be efficient, batch related questions.

## Plugins, marketplaces, and skills

- A **skill** is a packaged set of instructions that teaches Claude a workflow (like
  this one). A **plugin** bundles skills and tools. A **marketplace** is a catalog of
  plugins you add with one command.
- Adding a marketplace is safe by itself — nothing runs until you install and use
  something from it.

## Managed agents

- A **managed agent** runs on Anthropic's infrastructure instead of your computer, at
  https://platform.claude.com/ — separate login from claude.ai, and it requires
  prepaid usage credits you enable first.
- Most people starting out **do not need one**. A local agent in the Code tab does the
  same work using your existing subscription. Consider managed agents later, when
  something must run while your computer is off.

## Subscription tiers (as of mid-2026 — verify if it matters)

- **Free/trial** — good for evaluating; usage caps arrive quickly. Be efficient.
- **Pro** — the sweet spot for regular individual use, includes Claude Code.
- **Max** — higher limits for heavy daily agent use.
- Usage-based API billing is separate from all of the above (and separate login);
  it's what managed agents and API scripts draw from.
````

- [ ] **Step 2: Mirror and commit**

```bash
rsync -a --delete /home/leland/.claude/skills/getting-started/ /mnt/d/Documents/Code/GitHub/.claude_code/claude/skills/getting-started/
git -C /mnt/d/Documents/Code/GitHub/.claude_code add claude/skills/getting-started
git -C /mnt/d/Documents/Code/GitHub/.claude_code commit -m "feat(skills): getting-started — claude-basics reference (Chat/Code/Cowork, tokens, managed agents)"
```

---

### Task 4: references/other-tools.md — adapt-and-point companions

**Files:**
- Create: `~/.claude/skills/getting-started/references/other-tools.md`
- Mirror to: `/mnt/d/Documents/Code/GitHub/.claude_code/claude/skills/getting-started/references/other-tools.md`

**Interfaces:**
- Consumes: loaded by SKILL.md's "Has other AI subscriptions" and both IDE adaptation rules.

- [ ] **Step 1: Write other-tools.md**

Write exactly this content:

````markdown
# Other AI Tools — Adapt and Point

Use these when the user already pays for another AI service, or asks. One paragraph and
the official link — never a setup walkthrough for non-Claude tools (v1 policy).

## If they have a ChatGPT subscription → Codex CLI
OpenAI's coding agent for the terminal, comparable in spirit to Claude Code. A ChatGPT
Plus/Pro subscription already includes Codex usage, so it costs nothing extra to try —
some people run Claude Code and Codex side by side and let each review the other's
work. Official: https://developers.openai.com/codex/cli/

## If they have GitHub Copilot → Copilot CLI / coding agent
Their Copilot subscription works in the terminal and as an autonomous coding agent on
GitHub.com — useful when work already lives in GitHub issues and PRs.
Official: https://docs.github.com/copilot

## If they have Google Gemini → Gemini CLI
Google's free-tier-friendly terminal agent; a paid Gemini subscription raises its
limits. Official: https://github.com/google-gemini/gemini-cli

## Antigravity
Google's agent-first IDE (VS Code family) where agents plan and execute across editor,
terminal, and browser. Worth a look for coders who want an agent-native editor rather
than a terminal. Official: https://antigravity.google/

## The IDE recommendation — PyCharm Community Edition

**When they want to code and have no IDE:** recommend PyCharm Community Edition.
- Free and open source, from JetBrains: https://www.jetbrains.com/pycharm/
- Its AI-assistant plugin ecosystem (JetBrains AI/Junie, Copilot, Codex, Gemini, and
  Claude integrations) means **switching AI provider subscriptions never means
  switching IDEs** — the editor stays, the assistant swaps.
- Pairs naturally with Claude Code running in the integrated terminal.

**When they already have an IDE:** one sentence — "PyCharm Community Edition is a free
alternative whose AI plugins let you swap AI providers without changing editors" — then
respect their setup and move on.
````

- [ ] **Step 2: Mirror and commit**

```bash
rsync -a --delete /home/leland/.claude/skills/getting-started/ /mnt/d/Documents/Code/GitHub/.claude_code/claude/skills/getting-started/
git -C /mnt/d/Documents/Code/GitHub/.claude_code add claude/skills/getting-started
git -C /mnt/d/Documents/Code/GitHub/.claude_code commit -m "feat(skills): getting-started — other-tools reference (Codex/Copilot/Gemini/Antigravity, PyCharm CE)"
```

---

### Task 5: assets/plan-style.md — the HTML action-plan template

**Files:**
- Create: `~/.claude/skills/getting-started/assets/plan-style.md`
- Mirror to: `/mnt/d/Documents/Code/GitHub/.claude_code/claude/skills/getting-started/assets/plan-style.md`

**Interfaces:**
- Consumes: SKILL.md Step 5 follows this file when generating `getting-started-plan.html`.
- Produces: the HTML skeleton, the `.cmd` copy-button block pattern, and the four required sections.

- [ ] **Step 1: Write plan-style.md**

Write exactly this content (the HTML inside is the actual skeleton to instantiate):

`````markdown
# HTML Action Plan — Style Guide

Generate `getting-started-plan.html` in the current directory. Rules:

1. Fully self-contained — inline CSS and JS only, no external requests of any kind.
2. Four sections, in order: **Your goals** (their words), **What we did today**,
   **Recommended next installs**, **Do this next** (numbered, ends with 2–3 example
   prompts they can paste to start real work).
3. Every command AND every example prompt lives in a `.cmd` block with a copy button.
4. Friendly plain language; no jargon without a one-line explanation.
5. Keep it to one screen-and-a-bit of reading — this is a plan, not a manual.

## Skeleton

Instantiate this exact structure (replace ALL-CAPS placeholders; repeat `.cmd` blocks
as needed):

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Your Claude Getting-Started Plan</title>
<style>
  :root { --ink:#1a2333; --accent:#3b6ec5; --bg:#f7f9fc; --card:#ffffff; --ok:#2e7d32; }
  @media (prefers-color-scheme: dark) {
    :root { --ink:#e8ecf3; --accent:#7aa5e8; --bg:#12161d; --card:#1b2230; --ok:#81c784; }
  }
  body { font-family: system-ui, sans-serif; color: var(--ink); background: var(--bg);
         max-width: 760px; margin: 2rem auto; padding: 0 1rem; line-height: 1.55; }
  h1 { font-size: 1.6rem; } h2 { font-size: 1.15rem; margin-top: 2rem; }
  .card { background: var(--card); border-radius: 10px; padding: 1rem 1.25rem;
          margin: .75rem 0; box-shadow: 0 1px 4px rgba(0,0,0,.08); }
  .cmd { display: flex; align-items: flex-start; gap: .5rem; background: rgba(0,0,0,.06);
         border-radius: 8px; padding: .6rem .75rem; margin: .5rem 0; }
  .cmd pre { margin: 0; flex: 1; white-space: pre-wrap; word-break: break-word;
             font-size: .9rem; }
  .cmd button { flex-shrink: 0; border: 1px solid var(--accent); color: var(--accent);
                background: transparent; border-radius: 6px; padding: .25rem .6rem;
                cursor: pointer; font-size: .8rem; }
  .cmd button.copied { color: var(--ok); border-color: var(--ok); }
  ol li { margin: .5rem 0; }
</style>
</head>
<body>
<h1>Your Claude Getting-Started Plan</h1>
<p>Made for USER-FIRST-NAME-OR-"you" on DATE.</p>

<h2>Your goals</h2>
<div class="card"><p>GOALS-IN-THEIR-OWN-WORDS</p></div>

<h2>What we did today</h2>
<div class="card"><ul>
  <li>SESSION-ACCOMPLISHMENT</li>
</ul></div>

<h2>Recommended next installs</h2>
<div class="card">
  <p><strong>TOOL-NAME</strong> — WHY-IT-FITS-THEM (one line).</p>
  <div class="cmd"><pre>INSTALL-COMMAND</pre><button onclick="copy(this)">Copy</button></div>
</div>

<h2>Do this next</h2>
<div class="card"><ol>
  <li>NEXT-STEP-INSTRUCTION</li>
  <li>Try a first real prompt:
    <div class="cmd"><pre>EXAMPLE-PROMPT-TOWARD-THEIR-GOAL</pre><button onclick="copy(this)">Copy</button></div>
  </li>
</ol></div>

<script>
function copy(btn) {
  const text = btn.parentElement.querySelector('pre').innerText;
  navigator.clipboard.writeText(text).then(() => {
    btn.textContent = 'Copied!'; btn.classList.add('copied');
    setTimeout(() => { btn.textContent = 'Copy'; btn.classList.remove('copied'); }, 1500);
  });
}
</script>
</body>
</html>
```
`````

- [ ] **Step 2: Verify the skeleton renders and the copy button works**

Extract the HTML block to a scratch file and open it:

```bash
awk '/^```html$/{f=1;next} /^```$/{f=0} f' /home/leland/.claude/skills/getting-started/assets/plan-style.md > /tmp/claude-1000/-mnt-d-Documents-Code-GitHub--claude-code/d798075f-a18d-474a-8666-bbcf9f48b0f7/scratchpad/plan-preview.html
```

Then render `plan-preview.html` (Playwright browser or send the file) and confirm: page renders, clicking Copy changes the button to "Copied!". Expected: both true, zero network requests.

- [ ] **Step 3: Mirror and commit**

```bash
rsync -a --delete /home/leland/.claude/skills/getting-started/ /mnt/d/Documents/Code/GitHub/.claude_code/claude/skills/getting-started/
git -C /mnt/d/Documents/Code/GitHub/.claude_code add claude/skills/getting-started
git -C /mnt/d/Documents/Code/GitHub/.claude_code commit -m "feat(skills): getting-started — HTML action-plan template with copy buttons"
```

---

### Task 6: Marketplace + README integration

**Files:**
- Modify: `/mnt/d/Documents/Code/GitHub/.claude_code/.claude-plugin/marketplace.json` (skills array + plugin description ONLY — not version fields)
- Modify: `/mnt/d/Documents/Code/GitHub/.claude_code/README.md` (new section near top)

**Interfaces:**
- Consumes: the mirrored skill at `./claude/skills/getting-started` (Tasks 1–5).
- Produces: the marketplace path entry `"./claude/skills/getting-started"` as FIRST element of the plugin's `skills` array.

- [ ] **Step 1: Add the skill first in marketplace.json and lead the description with it**

In `.claude-plugin/marketplace.json`, change the plugin's `skills` array so `"./claude/skills/getting-started"` is the first element (keep all existing entries after it), and replace the plugin `description` with:

```
Start with /getting-started — an interview-first concierge that sets newcomers up: it checks your config, adapts to your subscriptions, and recommends the right tools. Also includes: claude-md-optimizer, unify-agents-md, project-documenter, technical-documenter, feature-documenter, raginclude-generator, model-registry, astrocade-game-creation. For version-manager, repo-doctor, update-code-map, and yt-transcript (which ship bundled tools), install repo-hygiene / docs-toolkit / yt-transcript from the Chameleon Labs marketplace (Chameleon-Labs-LLC/plugins) — or clone this repo and follow the README.
```

Do NOT touch `metadata.version` or the plugin `version` — Task 7 owns those.

- [ ] **Step 2: Validate the JSON**

Run: `jq -e '.plugins[0].skills[0] == "./claude/skills/getting-started"' /mnt/d/Documents/Code/GitHub/.claude_code/.claude-plugin/marketplace.json`
Expected: `true` (and jq exiting 0 proves the file is valid JSON).

- [ ] **Step 3: Add the README front-door section**

In `README.md`, insert directly after the opening paragraph (the one beginning "A comprehensive, production-tested configuration"):

```markdown
## New here? Start with `/getting-started`

```
/plugin marketplace add lelandg/.claude_code
/plugin install claude-config-skills@lelandg-claude-config
```

Then say **"help me get started"** (or type `/getting-started`). The concierge interviews
you — goals, subscriptions, setup — then checks your configuration, recommends the right
tools from this catalog, and hands you a personalized HTML action plan.

*Maintainers: when a new public repo ships, add a line for it to
`claude/skills/getting-started/references/catalog.md` before the next publish.*
```

- [ ] **Step 4: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/.claude_code add .claude-plugin/marketplace.json README.md
git -C /mnt/d/Documents/Code/GitHub/.claude_code commit -m "feat(marketplace): getting-started is the headline skill; README front-door section"
```

---

### Task 7: Release — version bump + changelog via version-manager

**Files:**
- Modify (tool-owned): `CHANGELOG.md`, `.claude-plugin/marketplace.json` version fields

**Interfaces:**
- Consumes: all prior commits.
- Produces: released version (minor bump — new feature) and CHANGELOG entry, in one commit.

- [ ] **Step 1: Dry-run the release**

Run: `python3 /home/leland/.claude/skills/version-manager/version_tool.py --repo /mnt/d/Documents/Code/GitHub/.claude_code release minor`
Expected: dry-run output proposing the next minor version and showing detected version locations (marketplace.json) and generated notes. Review that the version locations are the marketplace/plugin version fields.

- [ ] **Step 2: Curate notes and apply**

Write the release notes to the scratchpad, then apply:

```bash
cat > /tmp/claude-1000/-mnt-d-Documents-Code-GitHub--claude-code/d798075f-a18d-474a-8666-bbcf9f48b0f7/scratchpad/release-notes.md <<'EOF'
Added the `getting-started` concierge — the marketplace's new headline skill. It
interviews newcomers one question at a time (goals, subscriptions, surface), adapts
(efficiency mode on trial plans, companion-tool pointers for other AI subscriptions,
PyCharm CE advice scaled to whether an IDE exists), checks configuration with consent,
recommends from a curated catalog of Leland's open source, and generates a personalized
HTML action plan with copy-to-clipboard commands.
EOF
python3 /home/leland/.claude/skills/version-manager/version_tool.py --repo /mnt/d/Documents/Code/GitHub/.claude_code release minor --notes /tmp/claude-1000/-mnt-d-Documents-Code-GitHub--claude-code/d798075f-a18d-474a-8666-bbcf9f48b0f7/scratchpad/release-notes.md --apply
```

Expected: version fields bumped + CHANGELOG entry written.

- [ ] **Step 3: Verify and commit (if the tool didn't auto-commit)**

Run: `git -C /mnt/d/Documents/Code/GitHub/.claude_code status --short && head -20 /mnt/d/Documents/Code/GitHub/.claude_code/CHANGELOG.md`
Expected: CHANGELOG's top entry is the new version with the curated notes. If files are uncommitted:

```bash
git -C /mnt/d/Documents/Code/GitHub/.claude_code add CHANGELOG.md .claude-plugin/marketplace.json
git -C /mnt/d/Documents/Code/GitHub/.claude_code commit -m "chore(release): version bump + changelog for getting-started skill"
```

Do NOT push — Leland pushes after final review (house rule: review before push).

---

### Task 8: Verification — personas and rendered plan

**Files:**
- Read-only verification; no new files except scratchpad artifacts.

**Interfaces:**
- Consumes: the complete live skill in `~/.claude/skills/getting-started/`.

- [ ] **Step 1: Structural check against the spec**

Run: `find /home/leland/.claude/skills/getting-started -type f | sort`
Expected: exactly `SKILL.md`, `references/catalog.md`, `references/claude-basics.md`, `references/other-tools.md`, `assets/plan-style.md`. Also run `diff -r /home/leland/.claude/skills/getting-started /mnt/d/Documents/Code/GitHub/.claude_code/claude/skills/getting-started` — expected: no output (mirror in sync).

- [ ] **Step 2: Persona dry-runs (three, fresh context each)**

For each persona, dispatch a fresh subagent whose prompt is: "Read /home/leland/.claude/skills/getting-started/SKILL.md and role-play the concierge for this user, following it exactly. I will play the user: PERSONA. Report: which questions you asked in what order, which adaptation rules fired, which catalog entries you recommended, and whether anything in the skill was ambiguous or contradictory." Personas:

1. *Josiah-style*: runs a small business (warehouse/inventory, SEO), desktop app, Windows, Claude trial via a free pass, no other AI subscriptions, no coding.
   Expected: efficiency mode fires; Chat/Code/Cowork guidance given; recommends the two marketplaces + Agent Spawner; no PyCharm mention.
2. *Trial minimalist*: free plan, CLI, Linux, wants research help only.
   Expected: efficiency mode fires; light recommendations (yt-transcript, marketplace); no coding content.
3. *Coder with ChatGPT sub*: Pro Claude plan, has VS Code, ChatGPT Plus, wants coding help.
   Expected: Codex CLI paragraph + official link, no Codex setup walkthrough; PyCharm CE gets exactly a one-sentence mention (IDE already installed).

Expected overall: all three reports show one-question-at-a-time behavior, consent asked before config probes, and zero ambiguity findings. Fix SKILL.md and re-run any persona that surfaces a problem, then re-mirror + commit as `fix(skills): getting-started — <what>`.

- [ ] **Step 3: End-to-end HTML plan render**

Using persona 1's session output, generate a real `getting-started-plan.html` into the scratchpad following `assets/plan-style.md`, render it (Playwright or send the file), and confirm: four sections present, copy buttons work, no external requests, dark mode legible.

- [ ] **Step 4: Final summary note**

Per house rules, write a short completion summary to `/mnt/d/Documents/Code/GitHub/.claude_code/Notes/2026-08-06-getting-started-skill-shipped.md` (Notes/ is gitignored — do not commit it) listing: commits made, verification results, and the reminder that Leland reviews then pushes.

---

## Self-Review (completed at plan-writing time)

- **Spec coverage:** triggering → Task 1 frontmatter; interview + IDE follow-up → Task 1; adaptation rules incl. split PyCharm rec → Tasks 1+4; config probes + consent → Task 1; catalog with owners/audiences → Task 2; basics (Chat/Code/Cowork, tasks/tokens, managed agents, tiers) → Task 3; adapt-and-point → Task 4; HTML plan w/ copy buttons → Task 5; marketplace headline + README + catalog-maintenance note → Task 6; version/CHANGELOG via tool → Task 7; three-persona testing + render check → Task 8. Edge cases: Windows-no-WSL and no-AskUserQuestion fallback → Task 1 table/ground rules; offline → catalog is local by design.
- **Placeholders:** the ALL-CAPS tokens inside the Task 5 skeleton are deliberate template variables the skill fills at runtime — not plan placeholders. No TBDs remain.
- **Consistency:** all tasks use the same live path, mirror command, and repo path; `getting-started-plan.html` filename consistent across Tasks 1, 5, 8.

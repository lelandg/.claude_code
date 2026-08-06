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

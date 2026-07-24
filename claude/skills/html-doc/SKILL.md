---
name: html-doc
description: Use when the user asks for "an HTML" — an HTML document, page, report, explainer, announcement, week-in-review, summary, comparison, or any standalone HTML deliverable. Also use when converting a markdown report/notes into a shareable page. NOT for app UI components or pages inside a codebase (that's normal frontend work).
---

# html-doc — ChameleonLabs document style

## Overview

Produce a **self-contained, light/dark-themed, editorial-quality HTML document** in the ChameleonLabs house style. One file, no build step, looks designed — never generic AI output.

**Start from `template.html` in this skill's directory.** It already contains the theme system, fonts, masthead, toggle, and footer. Replace the placeholder content; don't rebuild the scaffolding from scratch.

## Hard requirements (every document)

1. **Both themes.** All colors via CSS variables: `:root` holds the document's default palette, `[data-theme="light"]` / `[data-theme="dark"]` holds the other. Include `color-scheme` in each. No hardcoded colors outside the variable blocks (glows/tints via vars too).
2. **Theme persistence.** Head script (before `</head>`, so no flash) reads localStorage key `cl.docs.theme`, falls back to `prefers-color-scheme`, sets `data-theme` on `<html>`. A `☾ dark / ☀ light` pill button in the kicker toggles and writes back to the **same key** — all CL docs share it.
3. **Brand links.** `https://chameleonlabs.ai` and `https://discord.gg/chameleonlabs` in the kicker AND footer. Add topic-relevant links (GitHub repos, companion docs) where they help — e.g. the Agent Spawner repo is `https://github.com/Chameleon-Labs-LLC/agent-spawner`.
4. **Typography.** Google Fonts via CDN. House default: **Fraunces** (display serif) + **Albert Sans** (body) + **IBM Plex Mono** (mono/labels). You may pick a different characterful pairing for a one-off, but NEVER Inter, Roboto, Arial, or system-font stacks.
5. **Self-contained single file.** Inline CSS/JS, responsive (test the grid breakpoints), subtle staggered entrance animation, generous whitespace.
6. **Real content.** Lead with the outcome. Pull facts from git log, the repo, or memory — never invent numbers or dates. Get today's date via `date '+%Y-%m-%d'`. Plain language for mixed-experience readers; spell out jargon on first use.
7. **File placement.** Save to the project's notes directory (check casing — CL uses `Notes/`), filename `<slug>-YYYY-MM-DD.html`. Send with SendUserFile. Offer to commit.
8. **Pairs/series.** Cross-link companions in the footer (relative href). Share the design language; you may invert which theme each doc emphasizes, but both must support both themes.

## Structure vocabulary (pick what fits, don't use all)

Masthead kicker (mono, uppercase, ◆ brand mark) → big Fraunces headline with an italic accent word → dek paragraph. Then: stat band, announcement banner with pulsing dot, numbered `01 /` section heads, day-by-day timeline, definition card grids, top-to-bottom flow diagrams (TB, never LR), roster tables with badges, guardrail card grids, pull quotes, three-tier "start here" columns. Footer: brand links · companion link · "Compiled YYYY-MM-DD".

## Common mistakes

| Mistake | Fix |
|---|---|
| System/Inter fonts | Google Fonts, characterful pairing (req. 4) |
| Only one theme works | Test toggle both ways; every color must come from a var |
| New localStorage key per doc | Always `cl.docs.theme` |
| Theme script at end of body | Must be in `<head>` or first paint flashes |
| Invented stats/dates | Real data only; `date` for timestamps |
| Left-to-right flow diagrams | Top-to-bottom (TB) |
| Dumping the file silently | SendUserFile + offer commit |

---
name: astrocade-game-creation
description: Create, refine, and ship casual games on Astrocade (astrocade.com), the wish-based AI game creation platform. Use this skill whenever the user mentions Astrocade, "wishes" for a game, wants to design or prototype a casual/mobile/browser game concept, asks for help writing a game-creation prompt, wants to plan playtesting for a web game, or asks how to make a game go viral on a casual platform — even if they don't say "Astrocade" explicitly but are clearly targeting it (e.g., referencing Astro Academy, remixing games, TTF, or a game they're building at astrocade.com). Also use it when turning any game idea into a staged prompt plan for an AI game builder.
---

# Astrocade Game Creation

Astrocade (astrocade.com) is a social gaming platform where anyone creates games by writing **wishes** — natural-language prompts that an AI turns into playable browser games. Games are casual, mobile-first, and instantly shareable; other players can **remix** any game (fork it, with visible wish history). Anthropic-style prompting instincts mostly transfer, but Astrocade has a specific house method taught by its Astro Academy. This skill encodes that method.

Your job when this skill triggers: take the user's game idea wherever it currently is — raw concept, half-built game, or "why isn't this fun?" — and move it through the pipeline below, producing concrete wishes they can paste in.

## The platform's hard constraints

Design everything against these. They are why the method works:

- **TTF (Time to Fun): 5–15 seconds**, measured from the moment the player taps Play — download time included. Heavy assets, long intros, and menu mazes kill games before they start.
- **Mobile-first, usually portrait, one-thumb play.** Taps, drags, and swipes; no keyboard assumptions unless the user says desktop.
- **One core mechanic** (the "verb") per game, almost always. Complexity is the enemy of casual.
- **Casual emotional register**: mastery, autonomy, curiosity, silliness. Rarely dramatic or realistically violent.
- **Remix culture**: assume other players will fork the game and read the wish history. Clean, staged wishes are a public artifact.

## The pipeline

Work through these stages in order. Never skip the playtest gate. The single most important rule, straight from the Academy: **core gameplay mechanic first, everything else second.**

### Stage 1 — Distill the concept to one verb

Ask (or infer from context): what is the player *doing*, moment to moment? Reduce the idea to a single core mechanic — matching, launching, merging, stacking, dodging, placing, slicing. If the user's concept has three mechanics, help them pick one and park the rest for later stages or sequels.

Apply the **70/20/10 adaptation strategy** when the idea derives from an existing game or trend (most do, and that's fine — Candy Crush descends from Bejeweled descends from SameGame):
- 70% borrowed from a proven formula (core mechanic, key features, progression)
- 20% structural improvement (fix what drags, confuses, or frustrates in the original)
- 10% genuinely original (theme, twist, signature moment)

Name the 10% explicitly. It's the identity of the game and usually the thing to protect in every later wish. Fresh mechanic ideas also come from outside gaming: satisfying TikTok/Shorts genres (power washing, slicing, dough stretching, color mixing) are pre-validated dopamine loops waiting to be made interactive.

### Stage 2 — Write the Initial Wish

One prompt that produces a playable demo of the core mechanic and **nothing else**. Read `references/wish-patterns.md` before writing it — it has the template, style rules, and worked examples. The non-negotiables:

- Describe the **player's experience**, not the implementation ("I drag a piece and it snaps into place", not "implement a snapping system").
- Include a **guaranteed win**: the opening state should let the very first action succeed satisfyingly. It doubles as the tutorial and secures the TTF window.
- Include concrete numbers where feel depends on them (counts, speeds, sizes).
- End with a scoping clause: *"For now I only want to test this core experience — we'll add [features] later."* This stops the AI from over-building.

### Stage 3 — Iterate with single-purpose edit wishes

Each follow-up wish changes **one thing**. Batch nothing. If a control feels wrong, remember the Academy's rule: **the player's physical instinct is always right** — tune physics, enlarge hitboxes, or remap gestures to match what players naturally try, never the reverse.

### Stage 4 — The playtest gate

Before any polish, features, or juice: 2–3 human testers, silent-observation protocol. Full procedure, observation rubric (Comprehension / Control / Engagement), and decision rules are in `references/academy-method.md` — read it when the user reaches this stage or asks about testing. The binary outcome: if testers compulsively retry and blame themselves for failures, build the game. If they act relieved when a round ends, abandon the mechanic and return to Stage 1. Astrocade's Discord has a dedicated **Playtest-your-Game** channel for remote sessions.

One exception to "no polish before testing": include a refinement early **only if it fundamentally changes the appeal of the mechanic itself** (a bazooka's recoil, an explosion's shockwave). Eye candy and meta features never qualify.

### Stage 5 — Juice

Juice = the visual and physical effects that make a proven mechanic feel visceral. Method: list the 2–4 **sensations** the mechanic should convey (tension, speed, impact, growth, weight...), then assign one effect per sensation. Never layer effects for flashiness; juice heightens the core mechanic or it gets cut. The effect vocabulary (glows, particles, squash-and-stretch, screen shake, overshoot, easing) and worked wish examples are in the references.

### Stage 6 — Complete the game: core loop + meta loop

- **Core loop**: the mechanic fleshed into a repeating cycle (act → result → reward → repeat).
- **Meta loop**: why the player returns — currency, upgrades, unlocks, progression.
- Difficulty follows a **sawtooth**: each spike followed by a cooldown level that restores the feeling of competence. Content variety (backgrounds, music) cycles linearly.
- Upgrade economics: stats grow **linearly** (fixed % of base per level, hard cap ~5 levels), costs grow **exponentially** (~1.5× per level). This prevents runaway power while keeping each upgrade meaningful.

### Stage 7 — First impression & publish

Title, thumbnail, and opening seconds determine whether anyone plays at all. The Academy's Lesson 6+ covers this and the curriculum is actively growing — **if you have web access, fetch the current lessons at https://www.astrocade.com/create/academy and the creator blog at https://www.astrocade.com/blog before advising on publishing, discoverability, or monetization** (monetization thresholds and creator-fund terms change; never quote them from memory).

## Wish style quick reference

| Do | Don't |
|---|---|
| One change per wish | "Also add X, Y, and Z while you're at it" |
| Player-experience language | Engine/implementation language |
| Concrete numbers ("8 particles", "every half second") | "some", "a few", "fast" |
| "For now... we'll add ___ later" scoping | Open-ended wishes that invite over-building |
| Restate the thing being changed precisely | Pronouns referring to earlier wishes ("make it better") |

## Reference files

- `references/wish-patterns.md` — Read before writing any wish. Template, style rules, worked initial/edit/juice/fix wish examples across genres, common failure patterns.
- `references/academy-method.md` — Read at the playtest gate, or when planning juice, progression, or the meta loop. Full Academy method: TTF details, playtest protocol and rubric, juice taxonomy, loop design, progression math.
- `assets/gdd-template.md` — Lightweight Game Design Document matching the Academy's exercises. Copy it for the user when they start a new game or when planning spans multiple sessions.

## Live sources (fetch when network is available; the platform evolves fast)

- Astro Academy lessons: https://www.astrocade.com/create/academy (Lessons 1–5 are condensed in this skill; later lessons cover publishing and beyond)
- Creator blog (technique cookbooks, e.g. sprite-sheet animation): https://www.astrocade.com/blog
- Create: https://www.astrocade.com/create · Community/playtesting: the Astrocade Discord

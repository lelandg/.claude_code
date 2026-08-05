# The Astro Academy Method (Lessons 1–5, condensed)

Paraphrased working notes from Astrocade's official creator curriculum at
https://www.astrocade.com/create/academy — consult the live lessons for the
originals, videos, and exercises. Everything here is restated in this skill's
own words for agent use.

## Contents

1. [Thinking like a casual designer (L1)](#1-thinking-like-a-casual-designer)
2. [Finding and adapting a mechanic (L2)](#2-finding-and-adapting-a-mechanic)
3. [Building and playtesting the core mechanic (L3)](#3-building-and-playtesting-the-core-mechanic)
4. [Juice (L4)](#4-juice)
5. [Core loop, meta loop, progression (L5)](#5-core-loop-meta-loop-progression)

---

## 1. Thinking like a casual designer

**Game mechanic** = the verb: the action the player takes and how the game
responds. Classic casual verbs: matching (Candy Crush), merging (Merge
Mansion), launching (Angry Birds), stacking, slicing, dodging, sorting.

**TTF (Time to Fun)** = seconds from tapping Play to the first satisfying
moment — *including download/page load*. Target on Astrocade: **5–15 seconds
total**. A 45-second load on slow connections is a 45+ second TTF no matter
how snappy the game is afterward. Consequences:

- Minimal assets; prefer generated/simple art over heavy sprites at first.
- The first playable moment must arrive before any menu, story, or settings.
- The opening state should be pre-arranged so the first action succeeds.

**The casual recipe**: one simple mechanic that rewards repetition · instant
onboarding (interactive, not textual) · fastest possible download · minimal
extraneous features · a guaranteed win up front · tuned progression.

**Target emotions**: mastery (I'm getting good at this), autonomy (my choices
matter), connectedness (multiplayer/community), curiosity (unpredictable
outcomes), humor/cuteness/silliness. Casual games are rarely dramatic,
serious, or realistically violent.

**Creator mentality**: test constantly, iterate fast, abandon freely. The
industry giants prototype thousands of games a year; polish is earned by
engagement signals, never assumed.

---

## 2. Finding and adapting a mechanic

Original mechanics are rare (on par with writing a hit song). The normal,
legitimate path is adaptation — match-3 alone runs SameGame → Bejeweled →
Candy Crush, and hits like Words with Friends, Subway Surfers, and
Survivor.io are all direct descendants of earlier games. What players judge
is execution and identity, not genealogy.

**Where to hunt**: trending/popular sections of web-game portals and app
stores · what streamers play · where crowds gather on Roblox/UEFN · and,
increasingly, **non-game viral video genres** — ASMR slicing, power washing,
color mixing, pet grooming, dough stretching. If millions watch it, an
interactive version has a head start.

**The 70/20/10 strategy**:
- **70%** borrowed from a proven formula: core mechanic, familiar power-ups
  and obstacles, overall progression shape.
- **20%** structural improvement: smooth the difficulty spikes, cut the
  parts that drag, clean the interface, fix what the original gets wrong.
- **10%** original: theme, style, twist, signature moment. Name it and
  protect it — this is the game's identity.

Adapting is real work, not copying homework: big ideas usually need
*simplification* to fit Astrocade (their case study flattened an expansive
3D Roblox survival game into a phone-friendly 2D form). Hybrids of two
mechanics are possible but expert-mode; recommend them only to users who've
shipped simpler games.

**Kickoff sequence**: Inspiration → Adaptation (core mechanic only, as a
playable demo) → Testing (real players, before any features) → Refinement.

---

## 3. Building and playtesting the core mechanic

Loop: **wish for the mechanic → make it just-barely playable → test with
humans → keep / improve / abandon.** Do not add features, styling, or juice
until testing says the mechanic works.

### The playtest protocol

In person or via the **Playtest-your-Game** channel on the Astrocade Discord.
2–3 testers is enough for a first decision; even one beats zero.

Setup rules (both modes):
- Hand over the game **already loaded** on the start screen (in-person) or
  have them screen-share a blank browser window *before* sending the link
  (Discord) so you see loading problems too.
- **Say nothing.** No explanation of the game. Announce that you can't answer
  questions, and ask them to think out loud (mic on, for remote).
- Watch the person at least as much as the screen.

What to record:
- **First impression**: hesitation or asking for help = bad; diving in and
  exploring = good.
- **Time to first intentional action**: momentary confusion is fine; what
  matters is how fast they become un-confused.
- **Failure reaction**: instantly retrying = invested; waiting for you to
  say something, relaxing posture, handing the device back = chore.
- **Unprompted vocalizations**: a frustrated "oh come on!" signals
  investment; a lost "wait, what?" signals confusion.

### The rubric: sort every observation into three buckets

| Bucket | Question | If it fails | Next step |
|---|---|---|---|
| **Comprehension** | Did they understand what the game wanted? | Objective/interactables aren't visually legible | Change shapes, contrast, camera so interactive things stand out. If only text could explain it, the mechanic may be too complex — consider abandoning. |
| **Control** | Could they execute the actions? | Inputs mismatch physical instinct (swiping when a tap is needed; "I pressed it!") | **The player's physical instinct is always right.** Tune gravity/friction, widen hitboxes, remap to the gesture they naturally tried. Never argue. |
| **Engagement** | Did they enjoy it? | The loop doesn't trigger "one more try" | If they compulsively restart and blame themselves: build the game. If they look relieved it's over: abandon the mechanic and start over. |

Consider suggestions from testers seriously but adopt selectively — you must
*consider* every one, you don't have to *implement* every one.

### The one exception to "no polish before testing"

Include a refinement pre-test **only when it fundamentally changes the
mechanic's appeal**. Heuristics from the Academy's examples:
- Rocket launcher game: heavy recoil and a physical shockwave = necessary
  (they're felt on every shot); rocket upgrades and glowing exhaust = later.
- Vegetable farm: the satisfying "pop" on harvest = probably necessary;
  breeze-blown leaves and seasons = later.
- Block breaker: explosion feel = judgment call; combo systems and
  leaderboards = definitely later.

Test: *does this detail contribute to why the game is fun from one moment to
the next?* If it only adds beauty or long-term engagement, defer it.

---

## 4. Juice

Juice = details that make a proven mechanic feel addictive and visceral.
Two families:

**Visual**: glows and tints (energy, heat, magic) · particle systems (fire,
debris, confetti, steam) · squash-and-stretch (cartoon weight) · shaking
(screen or object, for impact or pent-up tension).

**Physical**: gravity and material-true bounce (coins arc high, boulders
thud) · overshoot-and-settle (personality, mechanical clunk) · ease in/out
(nothing important moves linearly).

**Method — the Juice Plan**: decompose the mechanic into the 2–4 sensations
the player should feel, then assign at least one effect per sensation.
Example decomposition for a slingshot game: *tension* (pull-back) → trembling
that scales with draw distance; *speed* (projectile flight) → motion trail;
*impact* (collisions) → object shake + debris particles + screen shake on
ground hits.

Juice wishes work best with exact parameters — counts, sizes, multipliers,
colors, durations ("eject 8 grey fragments of random sizes, rising then
falling with gravity", "particles match the popped object's color, 1.5×
bigger, lasting 2× longer"). Vague juice wishes produce mush.

Overdone or mismatched juice makes a good mechanic *less* fun — keep testing
as you add it. Well-applied juice can make an identical mechanic feel like an
entirely new game.

Related polish (not strictly juice, often worth pairing): richer backgrounds,
drop shadows that scale with height, glowing/pulsing trajectory or guide
lines.

---

## 5. Core loop, meta loop, progression

**Core loop** = the mechanic as a repeating cycle, moment to moment.
Examples: spot → aim → shoot → reload · plant → water → harvest → sell ·
enter room → clear wave → pick power-up → next room.

**Meta loop** ("the meta") = why the player keeps returning; unfolds over a
longer timescale and gives the core loop meaning. Resources earned in the
core loop are spent in the meta loop (upgrades, unlocks, story), which feeds
back by altering the core loop (new weapon, new area, faster tools).

**Progression levers**: difficulty · complexity (more to manage, distinct
from difficulty) · variety (new environments, enemies, items) · purchase and
upgrade opportunities.

**The guaranteed win**: open the game with an instance of the mechanic so
easy it can't fail. It sets a positive tone and *is* the tutorial. Design it
into the opening state (pre-arranged board, pre-connected pieces, a
highlighted first move).

**Sawtooth difficulty**: never increase difficulty monotonically; follow
each spike with a cooldown level that restores the feeling of competence.
Content variety, by contrast, cycles **linearly** (rotate backgrounds/music
evenly).

**Upgrade economics** (standard structure):
- Stats grow **linearly**: each level adds a fixed percentage *of the base
  value* (e.g., +10% of base per level), with a hard cap (commonly 5).
- Costs grow **exponentially**: multiply ~1.5× per level.
- Worked example — base speed 100%, +10%/level, cost ×1.5 from 100:
  L1 110% @150 · L2 120% @225 · L3 130% @338 · L4 140% @506 · L5 150% (cap).
- Rationale: prevents runaway "OP" stat explosions while economic friction
  keeps each upgrade an event.

---

## Beyond Lesson 5

The Academy continues (Lesson 6: optimizing the game's first impression —
title, thumbnail, opening seconds — with more lessons over time) and the
creator blog publishes technique cookbooks (e.g., sprite-sheet animation).
Fetch https://www.astrocade.com/create/academy and
https://www.astrocade.com/blog for current material before advising on
publishing, discoverability, or monetization. Monetization thresholds and
creator-program terms change; always verify live rather than quoting from
this file.

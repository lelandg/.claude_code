# Wish Patterns

How to write Astrocade wishes that produce what the user actually wants.
All examples below are original to this skill (written in the Academy's
house style, not copied from it).

## Contents

1. [Anatomy of a good wish](#anatomy-of-a-good-wish)
2. [The Initial Wish template](#the-initial-wish-template)
3. [Worked initial wishes](#worked-initial-wishes)
4. [Edit wishes](#edit-wishes)
5. [Juice wishes](#juice-wishes)
6. [Fix wishes](#fix-wishes)
7. [Feature wishes](#feature-wishes)
8. [Failure patterns to avoid](#failure-patterns-to-avoid)

---

## Anatomy of a good wish

1. **Player's-eye view.** Describe what the player sees, touches, and feels —
   "I pull back and release to launch", not "implement projectile physics".
   The AI infers implementation; the wish owns experience.
2. **One job per wish.** Initial wishes establish the core mechanic; every
   later wish changes exactly one thing. Batched wishes produce entangled,
   half-right results that take more wishes to untangle than they saved.
3. **Concrete numbers wherever feel depends on them.** Counts, intervals,
   sizes, speeds, multipliers, percentages. "A stream of marbles, one every
   half second" beats "lots of marbles". Numbers are also cheap to revise:
   "make it every 0.3 seconds instead" is a perfect follow-up wish.
4. **Spatial precision.** Screen regions matter on mobile: "along the bottom
   of the screen", "in the top half", "at the left edge of the platform".
5. **The scoping clause.** End initial wishes (and ambitious edit wishes)
   with: *"For now I only want to test this core experience — we'll add
   [named future features] later."* Naming the deferred features tells the
   AI they're intentionally absent, not forgotten.
6. **Self-contained references.** Name the thing being changed precisely
   ("the trajectory line that appears while pulling back"), never "it" or
   "that thing from before". Each wish should be understandable alone —
   remixers will read the history.

## The Initial Wish template

```
I want a [genre/setting one-liner]. [Screen layout: where the play area,
controls, and any tray/HUD live.] [The core interaction, in first person:
what I do and what happens, including the signature moment.] [The opening
state — arranged so the first action succeeds: the guaranteed win.]
[Success/feedback: what the game shows when the mechanic pays off.]
[Feel-critical physics or parameters, with numbers.] For now I only want
to test this core experience — we'll add [deferred features] later.
```

Length: usually 120–250 words. Shorter risks under-specification of the
signature moment; longer usually means features are leaking in.

## Worked initial wishes

**Example 1 — placement/physics sandbox (3D builder):**

> I want a 3D marble machine builder — a free-build sandbox with no fail
> state and no required objective. The scene is a flat wooden platform I can
> orbit by dragging on empty space (pinch to zoom). Along the bottom of the
> screen is a parts tray with four pieces: straight track, banked curve,
> funnel, and goal cup. I drag a piece from the tray and drop it anywhere in
> 3D space at any height; the moment I drop it, a support column
> automatically grows from its underside down to the platform with a quick,
> satisfying stretch, so every piece stands on its own wherever I put it.
> Dragging a placed piece moves it (its column follows); dragging it back to
> the tray removes it. When two track ends come close they gently snap
> together and glow briefly. When the game starts, one straight track is
> already connected from a marble spawner toward a goal cup, so tapping
> "Release marble" gives an instant satisfying roll. Tap releases one marble
> with realistic gravity and rolling; holding releases one every half second.
> For now I only want to test this building-and-rolling experience — we'll
> add more pieces, path preview, and saving later.

Why it works: signature moment named (the growing column), guaranteed win
pre-arranged, controls mapped to natural gestures, numbers where feel lives,
deferred features listed by name.

**Example 2 — timing/launch mechanic:**

> I want a pancake-flipping game. A skillet sits in the bottom third of the
> screen with one pancake in it. Holding my finger anywhere charges a flip
> (a small power meter fills over one second); releasing tosses the pancake
> up with height based on the charge, spinning as it goes. My goal is to
> land it flat back in the skillet. A perfect flat landing stacks a fresh
> pancake on top and the stack grows; a crooked landing wobbles the stack;
> landing outside the skillet ends the round and shows my stack height. The
> first pancake is pre-charged for an easy perfect flip so my first toss
> always lands. For now I only want to test the flip-and-stack feel — we'll
> add toppings, score multipliers, and menus later.

**Example 3 — sorting/streaming mechanic:**

> I want a color-sorting game. Marbles in four colors roll one at a time
> down a chute from the top of the screen toward a junction at the center.
> Four cups in matching colors sit across the bottom. While a marble rolls,
> I tap the cup I want it routed to, and rails smoothly bend to guide it
> there. A correct match plays a soft chime and fills the cup slightly; a
> wrong match plays a dull thud. Marbles arrive every two seconds at first.
> The first three marbles arrive with their matching cup already glowing, so
> my first sorts can't fail. For now I only want to test the route-and-sort
> rhythm — we'll add speed-ups, special marbles, and lives later.

## Edit wishes

One change, precisely located, with the target restated:

> Give the camera gentle momentum: after I release an orbit drag, it should
> glide briefly to a stop.

> Marbles should arrive every 1.4 seconds instead of every 2 seconds.

> Add an Undo button that reverses my last action — placement, move, or
> removal — up to 20 steps back.

## Juice wishes

Sensation → effect, with exact parameters (see academy-method.md §4 for the
planning step). Patterns:

**Tension** (scaling feedback):
> The skillet handle should tremble more and more as my flip charge fills —
> no charge, no tremble; full charge, strong tremble.

**Impact** (particles + shake, fully parameterized):
> When a pancake lands crooked, the whole stack should wobble for half a
> second and eject 6 small crumb particles of random sizes that fall with
> gravity.

**Speed** (trails):
> The marble should leave a short motion trail while rolling, fading over a
> quarter second.

**Reward** (celebration, bounded):
> When a cup fills completely, it should do one squash-and-stretch bounce
> and release a short burst of confetti in the cup's color, then reset.

**Iterating juice numerically** (the normal rhythm — adjust, don't rebuild):
> Spawn twice as many crumb particles and make them 1.5× bigger.

## Fix wishes

State the observed wrong behavior, then the desired behavior. When the
problem is control feel, translate the tester's instinct directly (the
player's physical instinct is always right):

> Testers try to flick the marble sideways with a swipe, but nothing
> happens. A horizontal swipe on a rolling marble should nudge it gently in
> that direction.

> The pancake sometimes lands half-on the skillet edge and jitters forever.
> If a pancake overlaps the skillet by more than half, settle it into the
> skillet; otherwise let it fall off.

## Feature wishes

Reserved for after the playtest gate. Introduce one system at a time and
tie it to the existing loop:

> Add a Challenge mode next to Sandbox: each level gives me a fixed
> inventory of pieces and a spawner and goal placed apart; I must reach the
> goal using only the pieces provided. Start with one guaranteed-win level
> that needs a single straight track.

> Add a coin counter: each perfect flip earns 1 coin, and a shop button
> (top-right) opens a panel with one upgrade — "Wider Skillet", 5 levels,
> each +10% of the base skillet width, costs 10 coins and ×1.5 per level.

## Failure patterns to avoid

- **The kitchen-sink wish**: mechanic + menus + shop + story in one prompt.
  Produces a shallow everything; the mechanic gets no depth.
- **Implementation cosplay**: "use a state machine for..." — constrains the
  AI without improving the experience. Describe outcomes.
- **Vague intensifiers**: "more fun", "better", "juicier", "polished".
  Convert to specific sensations and parameters first.
- **Pronoun drift**: "make it faster" three wishes after "it" was on screen.
  Restate the target.
- **Premature meta**: leaderboards, upgrades, or currencies before the
  playtest gate. If the verb isn't fun, the shop won't save it.
- **Fighting the tester**: wishing tooltips and instructions to explain a
  confusing mechanic. If it needs text to be understood, simplify the
  mechanic or its visual legibility instead.
- **Desktop assumptions**: hover states, right-click, keyboard controls —
  unless the user explicitly targets desktop play.

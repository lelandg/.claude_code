---
name: discord-post
description: Create a Discord post (announcement, release recap, changelog summary, community update) for the current project and save it as a markdown file under a Discord/ directory in the project root. Use this whenever the user asks to "create a Discord post", "write a Discord announcement", "make a Discord update", "post this to Discord", "draft a Discord message", or wants a community-facing summary of changes, a release, or news for a project — even if they don't say the word "skill". This skill only drafts and saves the post to a file; it never sends anything to Discord.
---

# Discord Post

Draft a Discord-native post about whatever the user asked for and save it as a
markdown file in the project's `Discord/` directory. This is a drafting tool —
it writes a file, it does not send to Discord. The user copies the text into
Discord themselves (or wires up posting separately).

## Where the file goes

1. **Find the project root.** Use the git top-level if the working directory is
   a git repo (`git rev-parse --show-toplevel`); otherwise use the current
   working directory. The `Discord/` directory lives at that root, not in a
   subfolder.

2. **Create `Discord/` if it doesn't exist.** A plain `mkdir -p <root>/Discord`
   is enough — no placeholder files, no README.

3. **Name the file `YYYY-MM-DD-<topic-slug>.md`.** Get the real date from
   `date '+%Y-%m-%d'` — never guess it. The slug is a short kebab-case summary
   of the topic (e.g. `2026-05-31-may-recap.md`,
   `2026-06-02-v0-3-0-release.md`). Date-prefixing keeps posts sorted and makes
   "the latest one" obvious. If a file with that exact name already exists, the
   user is likely revising it — update it in place rather than creating a
   near-duplicate, unless they clearly want a separate post.

4. **These posts are committed, not ignored.** They are a record of what was
   announced. Do not add `Discord/` to `.gitignore`. Commit only when the user
   asks (follow normal commit etiquette).

## What to write

Figure out the substance from the user's request and the project. Common cases:

- **Release / changelog recap** — if the user points at a `CHANGELOG.md`, git
  history, merged PRs, or a version bump, read those and summarize the
  user-facing story, not the raw commit list. Lead with what changed for the
  reader; collapse internal refactors.
- **Feature announcement** — what it is, why it matters, how to try it.
- **General update / news** — keep it to the signal the user cares about.

When the source is git history, prefer `git log` with dates and PR context over
guessing, and double-check which changes actually fall in the window the user
asked about (e.g. "changes from May" means filter by date, not by "most recent
commits").

## Voice

**Match the project's existing Discord voice first.** If `Discord/` already has
posts, skim the most recent one or two and mirror their tone, emoji density,
section style, and sign-off. Consistency across a server's posts matters more
than any house style.

If there are no prior posts, default to Discord-native: punchy, skimmable,
genuinely enthusiastic without being breathless. What works on Discord:

- A strong one-line hook up top so it reads well in a notification preview.
- Short sections with bold mini-headers and bullet/emoji lists — walls of text
  get skipped.
- Tasteful emoji as visual anchors (section markers, not confetti on every line).
- Plain language. Translate internal jargon ("Pattern 5 idle gate") into what it
  means for the reader, or cut it.
- A short closing line on the net impact, and a link to the repo/release if
  there is one.

Discord renders standard Markdown (bold, italics, lists, inline code, fenced
code blocks, blockquotes, links) but **not** tables or heading sizes (`#`),
so don't rely on those for layout — use bold text and bullets instead.

Keep it tight. A recap is usually 150–350 words; an announcement can be shorter.
If the user has a personal-voice or humanizer skill and the post is in their own
voice, prefer that for the actual prose.

## After saving

Tell the user the file path and show the post so they can copy it. Note that
nothing was sent to Discord — this is a draft they post themselves.

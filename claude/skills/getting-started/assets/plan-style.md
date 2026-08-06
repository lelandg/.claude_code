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

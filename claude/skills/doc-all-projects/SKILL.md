---
name: doc-all-projects
description: "Sweep all registered projects and regenerate their user-facing feature documentation if stale. Reads ~/.claude/my-projects.yaml, dispatches one parallel agent per project to run the project-documenter skill, commits results, writes per-project reports to Notes/, and displays a sorted summary. Use when you want to refresh docs across all your projects at once."
---

# /doc-all-projects

Sweep all registered projects and regenerate their user-facing feature documentation if
stale. Uses parallel agents — one per project. Read the full instructions below and follow
them exactly.

---

## Step 1: Read the project list

Read `~/.claude/my-projects.yaml` using Bash:

```bash
cat ~/.claude/my-projects.yaml
```

Parse it with Python to get the list of projects:

```bash
python3 -c "
import yaml, json, os
with open(os.path.expanduser('~/.claude/my-projects.yaml')) as f:
    data = yaml.safe_load(f)
print(json.dumps(data['projects'], indent=2))
"
```

You now have a list of `{name, path}` pairs.

**Expected `my-projects.yaml` format:**

```yaml
projects:
  - name: ProjectOne
    path: /absolute/path/to/project-one
  - name: ProjectTwo
    path: /absolute/path/to/project-two
```

---

## Step 2: Dispatch parallel agents

Using the Task tool, dispatch one `general-purpose` agent per project **in a single
message** (all in parallel). Use `mode: bypassPermissions`.

Fill in `{NAME}` and `{PATH}` for each project from the list you parsed above.

### Agent prompt template

Copy this template for each project, substituting `{NAME}` and `{PATH}`:

---
You are running the documentation sweep for the **{NAME}** project at `{PATH}`.
Use absolute paths for all operations. Never use `cd`.

**Step A — Verify the project**

Run:
```bash
test -d {PATH}/.git && echo "IS_GIT_REPO=yes" || echo "IS_GIT_REPO=no"
```

If `IS_GIT_REPO=no` or the path does not exist, print exactly:
```
RESULT:
  NAME={NAME}
  STATUS=Error
  FILES=0
  COMMIT=—
  REPORT=—
  ERROR=path not found or not a git repo
```
Then stop.

**Step B — Staleness check**

Run each check in order. Stop at the first that sets STALE=true.

Check 1 — Docs/Features/ directory missing:
```bash
test -d {PATH}/Docs/Features && echo "DIR_EXISTS=yes" || echo "DIR_EXISTS=no"
```
If `DIR_EXISTS=no` → STALE=true.

Check 2 — No .md files in Docs/Features/:
```bash
ls {PATH}/Docs/Features/*.md 2>/dev/null | wc -l
```
If count is 0 → STALE=true.

Check 3 — Docs older than 30 days:
```bash
DOC_TS=$(git -C {PATH} log -1 --format="%ct" -- Docs/Features/ 2>/dev/null)
CUTOFF=$(date -d "30 days ago" +%s 2>/dev/null || date -v-30d +%s 2>/dev/null)
echo "DOC_TS=$DOC_TS CUTOFF=$CUTOFF"
```
If DOC_TS is empty or DOC_TS < CUTOFF → STALE=true.

Check 4 — Source files newer than docs:
```bash
SRC_TS=$(git -C {PATH} log -1 --format="%ct" -- . ':(exclude)Docs/' ':(exclude)Notes/' 2>/dev/null)
DOC_TS=$(git -C {PATH} log -1 --format="%ct" -- Docs/Features/ 2>/dev/null)
echo "SRC_TS=$SRC_TS DOC_TS=$DOC_TS"
```
If SRC_TS > DOC_TS → STALE=true.

If no check matched → STALE=false.

**Step C — Skip if not stale**

If STALE=false, skip directly to Step F (write a "Skipped" report) then Step H.

**Step D — Run project-documenter**

Read the project-documenter skill instructions:
```bash
cat ~/.claude/skills/project-documenter/SKILL.md
```

Follow its full Phase 1–4 process using `{PATH}` as the project root.
Use absolute paths for all file reads and writes.
Track every file written under `{PATH}/Docs/Features/` for the report.

**Step E — Commit the docs**

```bash
git -C {PATH} add Docs/
git -C {PATH} diff --cached --stat
git -C {PATH} commit -m "docs: regenerate feature documentation [doc-all-projects]

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
COMMIT_HASH=$(git -C {PATH} rev-parse --short HEAD)
echo "COMMIT=$COMMIT_HASH"
```

If nothing was staged (no changes), set COMMIT_HASH=— and note "No changes to commit".

**Step F — Write the report**

```bash
REPORT_DATE=$(date '+%Y-%m-%d')
REPORT_TIME=$(date '+%Y-%m-%d %H:%M')
mkdir -p {PATH}/Notes
```

Write a markdown file to `{PATH}/Notes/doc-report-$REPORT_DATE.md` with this structure:

```markdown
# Documentation Report — {NAME}
Generated: $REPORT_TIME

## Status
- **Action**: Ran  ← or "Skipped"
- **Reason**: Source files newer than docs  ← or actual reason

## Files Generated/Updated
- Docs/Features/example.md (new, 4.2 KB)
← list each file actually created or modified, with size

## Commit
`$COMMIT_HASH` — docs: regenerate feature documentation [doc-all-projects]
← use — if skipped or nothing staged

## Notes
← any warnings, errors, or special cases; "none" if clean
```

**Step G — Update .gitignore**

```bash
grep -q 'doc-report-\*\.md' {PATH}/.gitignore 2>/dev/null \
  && echo "GITIGNORE=already_present" \
  || echo "GITIGNORE=needs_update"
```

If `needs_update`:
```bash
echo 'Notes/doc-report-*.md' >> {PATH}/.gitignore
git -C {PATH} add .gitignore
git -C {PATH} commit -m "chore: ignore auto-generated doc reports

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

**Step H — Return result**

Print exactly this block with real values filled in:
```
RESULT:
  NAME={NAME}
  STATUS=Updated
  FILES=N files updated
  COMMIT=abc1234
  REPORT={PATH}/Notes/doc-report-YYYY-MM-DD.md
  ERROR=none
```
Use `STATUS=Skipped` if not stale, `STATUS=Error` if something failed.
---

## Step 3: Collect results and display summary

After all agents return, collect their RESULT blocks.
Sort the rows **alphabetically by project name**.

Display a markdown table followed by the report file paths:

```
## Documentation Sweep Complete

| Project    | Status  | Docs Updated | Commit  |
|------------|---------|--------------|---------|
| ProjectOne | Updated | 4 files      | mno7890 |
| ProjectTwo | Updated | 8 files      | abc1234 |
| ProjectTri | Skipped | —            | —       |

## Report Files
- /path/to/ProjectOne/Notes/doc-report-YYYY-MM-DD.md
- /path/to/ProjectTwo/Notes/doc-report-YYYY-MM-DD.md
- ... (one per project, sorted alphabetically)
```

---

## Step 4: Offer to save

Ask the user:

> Save a copy of this summary?
> **[summary]** · **[list only]** · **[both]** · **[no]**

- **summary** — write the full table + report file paths to `~/.claude/doc-sweep-YYYY-MM-DD.md`
- **list only** — write only the report file paths to `~/.claude/doc-sweep-YYYY-MM-DD.md`
- **both** — write summary table + report file paths to `~/.claude/doc-sweep-YYYY-MM-DD.md`
- **no** — done, nothing saved

After saving, confirm with the full path of the saved file.

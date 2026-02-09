# Plan File Management

Reference for creating and maintaining implementation plan files.

**CRITICAL**: Plan files must be kept current at all times to ensure continuity across sessions. Store in the project's existing planning/notes directory (check local conventions first - could be `plans/`, `notes/`, `roadmap/`, etc.).

## Implementation Checklist Format

All new plans should use the **Implementation Checklist** format - a flat, actionable list of tasks that can be checked off as completed. This format prioritizes clarity and quick status assessment.

## Plan File Template

```markdown
# [Feature/Project Name] Implementation Checklist

**Last Updated:** YYYY-MM-DD HH:MM
**Status:** [Not Started | In Progress | Blocked | Complete]
**Progress:** X/Y tasks complete

## Overview
[1-3 sentence description of what this plan accomplishes]

## Prerequisites
- [ ] Prerequisite 1 (if any)
- [ ] Prerequisite 2

## Implementation Tasks

### [Section 1: Logical Grouping]
- [ ] Task description (`path/to/file.py`)
- [ ] Task description (`path/to/file.py`)
- [x] Completed task (`path/to/file.py:123`)

### [Section 2: Another Grouping]
- [ ] Task description
- [-] Blocked task - *Reason for block*
- [~] In progress task - *Current status*

## Testing
- [ ] Test task 1
- [ ] Test task 2

## Notes
- Implementation notes, decisions, or issues discovered during work
```

## Checklist Markers

| Marker | Meaning |
|--------|---------|
| `- [ ]` | Pending - not started |
| `- [x]` | Complete |
| `- [~]` | In progress |
| `- [-]` | Blocked |
| `- [s]` | Skipped (with reason) |

## When to Update Plan Files

Update the corresponding plan file **immediately** after:
1. Completing any task - Change `[ ]` to `[x]`
2. Starting a task - Change `[ ]` to `[~]` with status note
3. Hitting a blocker - Change to `[-]` with reason
4. Creating new files - Add file path and line number reference
5. Discovering new tasks - Add new items to appropriate section

## Required Updates

When updating plan files, you MUST:
1. Update task markers immediately when status changes
2. Update "Last Updated" timestamp at top of file
3. Update "Progress" count (X/Y tasks complete)
4. Add file references with line numbers for completed tasks
5. Document blockers inline with the blocked task
6. Add implementation notes to Notes section

## Auto-Update Triggers

Automatically update the plan file when:
- Completing a TodoWrite task that's part of a plan
- Creating new files mentioned in the plan
- Finishing a section or major milestone
- Encountering errors that affect the plan
- User asks to continue a plan (before starting work)

## Recovery After Interruption

When resuming after session interruption:
1. Read the plan file first - Check "Last Updated" and progress count
2. Find `[~]` markers - These show what was in progress
3. Check for `[-]` markers - Understand any blockers
4. Resume from last `[~]` task - Continue where you left off
5. Update immediately - Mark current task as in progress

## Example Checklist

```markdown
# Dark Mode Implementation Checklist

**Last Updated:** 2025-12-06 14:30
**Status:** In Progress
**Progress:** 4/10 tasks complete

## Overview
Add dark mode toggle to application settings with persistent user preference.

## Implementation Tasks

### Theme System
- [x] Create theme constants file (`src/theme/constants.ts:1`)
- [x] Define light/dark color palettes (`src/theme/colors.ts:15`)
- [~] Create ThemeContext provider - *Context created, testing toggle*
- [ ] Add useTheme hook (`src/hooks/useTheme.ts`)

### UI Components
- [x] Add toggle to Settings page (`src/pages/Settings.tsx:45`)
- [ ] Style toggle component
- [-] Update Header component - *Waiting on design specs*

### Persistence
- [x] Add theme to localStorage (`src/utils/storage.ts:20`)
- [ ] Load theme on app init
- [ ] Sync across tabs

## Testing
- [ ] Test toggle functionality
- [ ] Test persistence across sessions
- [ ] Test system preference detection

## Notes
- Decided to use CSS variables instead of styled-components for better performance
- Header redesign blocked pending design team input (2025-12-06)
```

This format ensures quick status assessment and seamless resumption across sessions.

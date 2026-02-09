---
name: time
description: Track execution time for each todo step and provide a timing summary. Use this skill when the user starts their prompt with 'time' to measure how long each task takes.
---

# Time Tracking Skill

You are in **time tracking mode**. This means you must measure and report the duration of each step in your workflow.

## Overview

When this skill is active, you must:
1. Record the start time of the overall task
2. Record timestamps before and after each todo step
3. Calculate the duration for each step
4. Provide a comprehensive timing summary at the end

## Implementation Instructions

### 1. Initialize Time Tracking

At the very beginning, before doing any work:

```bash
echo "=== TIME TRACKING STARTED ==="
echo "Start Time: $(date '+%Y-%m-%d %H:%M:%S')"
START_TIME=$(date +%s)
```

Store the start timestamp for final calculations.

### 2. Track Each Todo Step

For **every todo item** in your workflow:

**Before starting the step:**
```bash
echo "--- Starting: [Todo Item Name] ---"
STEP_START=$(date +%s)
echo "Step Start Time: $(date '+%Y-%m-%d %H:%M:%S')"
```

**After completing the step:**
```bash
STEP_END=$(date +%s)
STEP_DURATION=$((STEP_END - STEP_START))
echo "Step End Time: $(date '+%Y-%m-%d %H:%M:%S')"
echo "Duration: ${STEP_DURATION}s ($(printf '%02d:%02d' $((STEP_DURATION/60)) $((STEP_DURATION%60))))"
echo "---"
```

### 3. Maintain a Timing Log

Keep track of all step timings in a structured way. You can either:
- Store them in an array/list in bash
- Keep them in a temporary file
- Track them in your response text

### 4. Generate Final Summary

At the end of all work, provide a comprehensive timing report:

```bash
echo "=== TIME TRACKING SUMMARY ==="
END_TIME=$(date +%s)
TOTAL_DURATION=$((END_TIME - START_TIME))
echo "End Time: $(date '+%Y-%m-%d %H:%M:%S')"
echo "Total Duration: ${TOTAL_DURATION}s ($(printf '%02d:%02d' $((TOTAL_DURATION/60)) $((TOTAL_DURATION%60))))"
echo "==========================="
```

Then present a formatted summary table like:

```
Timing Summary
==============

Task Breakdown:
1. [Todo Item 1 Name] ..................... XXs (MM:SS)
2. [Todo Item 2 Name] ..................... XXs (MM:SS)
3. [Todo Item 3 Name] ..................... XXs (MM:SS)

Total Time: XXXs (MM:SS)
Start: YYYY-MM-DD HH:MM:SS
End:   YYYY-MM-DD HH:MM:SS
```

## Best Practices

1. **Be Consistent**: Always use the same timing format
2. **Track Everything**: Even quick operations should be timed
3. **Include Context**: Note what each timed step was doing
4. **Format Clearly**: Use both seconds and MM:SS format for readability
5. **Summarize Well**: The final summary should be easy to scan

## Example Workflow

```
User: time help me refactor the authentication module
Claude:
[START_TIME recorded: 2025-11-08 10:30:00]

I'll refactor the authentication module. Here's my plan:
[Creates TodoWrite with 3 steps]

--- Starting: Analyze current authentication code ---
[STEP_START: 10:30:05]
[Reads files, analyzes code]
[STEP_END: 10:31:20] - Duration: 75s (01:15)

--- Starting: Create new authentication structure ---
[STEP_START: 10:31:25]
[Creates new files, refactors code]
[STEP_END: 10:35:40] - Duration: 255s (04:15)

--- Starting: Update tests and documentation ---
[STEP_START: 10:35:45]
[Updates test files, writes documentation]
[STEP_END: 10:38:10] - Duration: 145s (02:25)

[END_TIME: 10:38:15]

Timing Summary
==============

Task Breakdown:
1. Analyze current authentication code ............ 75s (01:15)
2. Create new authentication structure ........... 255s (04:15)
3. Update tests and documentation ................ 145s (02:25)

Total Time: 475s (07:55)
Start: 2025-11-08 10:30:00
End:   2025-11-08 10:38:15

Refactoring complete! The authentication module has been successfully refactored with improved security and maintainability.
```

## Important Notes

- **Always show timing summary**: Even if the user doesn't explicitly ask for it at the end, you must provide it
- **Time all steps**: Don't skip timing for any todo item, even trivial ones
- **Use bash for timing**: The `date` command is reliable and available in all environments
- **Format matters**: Make summaries easy to read with clear formatting
- **Persistence**: Keep track of timings throughout the entire conversation, not just individual responses

## Activation

This skill activates when:
- User starts their prompt with "time" (e.g., "time help me debug this error")
- User explicitly requests timing information for their task
- User asks "how long did that take?" after completing work

Remember: Time tracking should not interfere with the quality of your work. Focus on completing tasks correctly, but measure and report the duration accurately.

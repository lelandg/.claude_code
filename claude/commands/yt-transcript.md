---
description: Download a YouTube transcript into the yt-transcript project's Notes directory
argument-hint: <youtube-url-or-video-id> [extra flags]
---

Invoke the `yt-transcript` skill to download the transcript for: $ARGUMENTS

Save the file to the yt-transcript project's `Notes/` directory (the skill's `scripts/run.sh` handles that automatically via its configured project path). Pass through any extra flags the user included (`-t`, `-r`, `-l <code>`, `-o <name>`, etc.). If no argument was provided, ask the user for a URL or video ID before running.

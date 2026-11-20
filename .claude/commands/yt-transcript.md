---
description: Download a YouTube transcript into the yt-transcript project's Notes directory
argument-hint: <youtube-url-or-video-id> [extra flags]
---

Invoke the `yt-transcript` skill to download the transcript for: $ARGUMENTS

Let the skill choose the output folder (don't pass `-d` unless the user asked): `Notes/` in the git root of the current working directory, or in the working directory itself when it is not a repository. It falls back to the yt-transcript project's own `Notes/` only when there is no usable working folder (home, a drive root, temp). Pass through any extra flags the user included (`-t`, `-r`, `-l <code>`, `-o <name>`, etc.). If no argument was provided, ask the user for a URL or video ID before running.

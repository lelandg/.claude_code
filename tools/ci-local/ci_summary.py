#!/usr/bin/env python3
"""Summarise an act run per job and decide whether it passed.

ci-local.sh runs act with --log-prefix-job-id, so each job's completion line is
`[<job id>] 🏁  Job succeeded` (or `failed`). The planned jobs come from
`act --list` for the same event and arguments.

Prints one line per planned job (`succeeded`, `failed` or `not run`) and exits:
  0   act's own exit code stands
  10  every planned job succeeded and act's only error was removing a finished
      container ("Error occurred running finally ... (original error: <nil>)"),
      which ci-local does itself: the run is a pass
  11  act exited 0, but a planned job did not report success: not a pass

Usage: ci_summary.py <act --list output> <act log> <act exit code>
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

DONE = re.compile(r"^\[(?P<id>[^\]]+?)\s*\]\s+🏁\s+Job (?P<result>succeeded|failed)\s*$")
CLEANUP_ONLY = re.compile(r"^Error: Error occurred running finally: .*\(original error: <nil>\)\s*$")


def planned_jobs(listing: str) -> list[tuple[str, str]]:
    """[(job id, "workflow/job name")] from `act --list`'s column table."""
    lines = listing.splitlines()
    head = next((i for i, l in enumerate(lines) if l.startswith("Stage") and "Job ID" in l), None)
    if head is None:
        return []
    h = lines[head]
    cols = [h.index("Job ID"), h.index("Job name"), h.index("Workflow name"), h.index("Workflow file")]
    jobs = []
    for line in lines[head + 1:]:
        if not line.strip():
            continue
        job_id = line[cols[0]:cols[1]].strip()
        name = line[cols[1]:cols[2]].strip()
        workflow = line[cols[2]:cols[3]].strip()
        if job_id:
            jobs.append((job_id, f"{workflow}/{name}"))
    return jobs


def decide(listing: str, log: str, rc: int) -> tuple[list[str], int]:
    planned = planned_jobs(listing)
    results: dict[str, set[str]] = {}
    for line in log.splitlines():
        m = DONE.match(line)
        if m:
            results.setdefault(m["id"], set()).add(m["result"])
    names = dict(planned)
    unique = len(names) == len(planned)  # two workflows sharing a job id cannot be told apart

    out: list[str] = []
    for job_id, name in planned:
        got = results.get(job_id, set())
        state = "failed" if "failed" in got else "succeeded" if got else "not run"
        out.append(f"{state:<10} {name}")
    for job_id in sorted(set(results) - set(names)):
        state = "failed" if "failed" in results[job_id] else "succeeded"
        out.append(f"{state:<10} {job_id}")

    all_passed = bool(planned) and unique and all(results.get(j) == {"succeeded"} for j, _ in planned)
    errors = [l for l in log.splitlines() if l.startswith("Error: ")]
    if rc != 0 and all_passed and errors and all(CLEANUP_ONLY.match(e) for e in errors):
        return out, 10
    if rc == 0 and planned and unique and not all_passed:
        return out, 11
    return out, 0


def main(argv: list[str]) -> int:
    if len(argv) != 3 or not argv[2].lstrip("-").isdigit():
        print(__doc__.strip().splitlines()[-1], file=sys.stderr)
        return 2
    listing = Path(argv[0]).read_text(encoding="utf-8", errors="replace")
    log = Path(argv[1]).read_text(encoding="utf-8", errors="replace")
    lines, verdict = decide(listing, log, int(argv[2]))
    if lines:
        print("\n".join(lines))
    else:
        print("ci-local: no job reported a result; the end of the log:")
        print("\n".join(log.splitlines()[-20:]))
    return verdict


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

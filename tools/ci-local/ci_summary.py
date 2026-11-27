#!/usr/bin/env python3
"""Summarise an act run per job and decide whether it passed.

ci-local.sh runs act with --log-prefix-job-id, so each job's completion line is
`[<job id>] 🏁  Job succeeded` (or `failed`). The planned jobs come from
`act --list` for the same event and arguments.

Prints one line per planned job and exits:
  0   act's own exit code stands
  10  act's only error was removing a finished container ("Error occurred
      running finally ... (original error: <nil>)") after every planned job
      succeeded, which ci-local does itself: the run is a pass

A planned job with no completion line was skipped by its `if:` when act exited
0 (act prints nothing for a skip at its normal log level), and was never
reached when act failed. The pass in 10 is granted only when every planned job
can be confirmed: not with a skip, a matrix (act's list shows one row however
many instances run) or a reusable workflow (its jobs report under their own ids).

Usage: ci_summary.py <act --list output> <act log> <act exit code> [<workflow dir>]
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import act_compat  # noqa: E402

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


def job_kinds(workflow_dir: str | None) -> tuple[set[str], set[str]]:
    """(ids of matrix jobs, ids of jobs that call a reusable workflow)."""
    matrix, reusable = set(), set()
    if not workflow_dir:
        return matrix, reusable
    for path in Path(workflow_dir).glob("*.y*ml"):
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
        for job, start, end in act_compat.job_blocks(lines):
            block = lines[start:end]
            child, keys = act_compat.child_keys(block)
            if "uses" in keys:
                reusable.add(job)
            if "strategy" in keys:
                s_at = keys["strategy"]
                s_end = act_compat.block_end(block, s_at, child)
                if any((m := act_compat.KEY_LINE.match(block[j])) and m["key"] == "matrix" for j in range(s_at + 1, s_end)):
                    matrix.add(job)
    return matrix, reusable


def decide(listing: str, log: str, rc: int, workflow_dir: str | None = None) -> tuple[list[str], int]:
    planned = planned_jobs(listing)
    matrix, reusable = job_kinds(workflow_dir)
    results: dict[str, set[str]] = {}
    for line in log.splitlines():
        m = DONE.match(line)
        if m:
            results.setdefault(m["id"], set()).add(m["result"])
    names = dict(planned)
    unique = len(names) == len(planned)  # two workflows sharing a job id cannot be told apart
    # A reusable workflow's jobs report under their own ids, which `act --list` does not show.
    delegated: set[str] = set().union(*(results[j] for j in results if j not in names)) if results else set()

    out: list[str] = []
    confirmed = bool(planned) and unique
    for job_id, name in planned:
        got = delegated if job_id in reusable else results.get(job_id, set())
        if "failed" in got:
            state = "failed"
        elif got:
            state = "succeeded"
        else:
            state = "skipped" if rc == 0 else "not run"
        out.append(f"{state:<10} {name}")
        if state != "succeeded" or job_id in matrix or job_id in reusable:
            confirmed = False
    for job_id in sorted(set(results) - set(names)):
        state = "failed" if "failed" in results[job_id] else "succeeded"
        out.append(f"{state:<10} {job_id} (called workflow)")

    errors = [l for l in log.splitlines() if l.startswith("Error: ")]
    if rc != 0 and confirmed and errors and all(CLEANUP_ONLY.match(e) for e in errors):
        return out, 10
    return out, 0


def main(argv: list[str]) -> int:
    if len(argv) not in (3, 4) or not argv[2].lstrip("-").isdigit():
        print(__doc__.strip().splitlines()[-1], file=sys.stderr)
        return 2
    listing = Path(argv[0]).read_text(encoding="utf-8", errors="replace")
    log = Path(argv[1]).read_text(encoding="utf-8", errors="replace")
    lines, verdict = decide(listing, log, int(argv[2]), argv[3] if len(argv) == 4 else None)
    if lines:
        print("\n".join(lines))
    else:
        print("ci-local: no job reported a result; the end of the log:")
        print("\n".join(log.splitlines()[-20:]))
    return verdict


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

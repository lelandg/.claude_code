#!/usr/bin/env python3
"""Make service-container ports start under act on this machine.

ci-local runs this over the workflow files in its THROWAWAY clone, never in
your checkout.

act runs a job's container on the host network and publishes each service's
`ports:` on the host, as GitHub does, so `localhost:5432` reaches the service.
Two things differ from GitHub:

  * GitHub gives every job its own empty VM. Your machine may already listen
    on that port (on WSL with mirrored networking, anything Windows listens on
    counts), and
  * act runs the jobs side by side on ONE host, so two jobs that both publish
    5432 would collide with each other.

So host ports are made unique across every job act will run: a port that is
free and not yet used by another job stays; any other moves to a free port
(`5432:5432` -> `45432:5432`), and `localhost:5432` / `127.0.0.1:5432` move
with it, inside that job only. The edit is line-based, so comments and
formatting survive and each file stays byte-for-byte what you wrote except for
the lines named in the printed report. Standard library only.

Usage: act_compat.py <workflow-dir>
"""
from __future__ import annotations

import re
import socket
import sys
from pathlib import Path

FIRST_FREE = 45432

JOBS_KEY = re.compile(r"^(?P<indent>\s*)jobs:\s*(#.*)?$")
KEY_LINE = re.compile(r"^(?P<indent>\s*)[A-Za-z0-9_-]+:")
# `ports:` followed by a block list, or a flow list on the same line.
PORTS_KEY = re.compile(r"^(?P<indent>\s*)ports:\s*(?P<rest>.*?)\s*(#.*)?$")
LIST_ITEM = re.compile(r"^(?P<indent>\s*)-\s*")
# HOST:CONTAINER, optionally IP:HOST:CONTAINER and /proto, optionally quoted.
MAPPING = re.compile(r"""(?P<q>["']?)(?P<ip>(?:\d{1,3}\.){3}\d{1,3}:)?(?P<host>\d{1,5}):(?P<cport>\d{1,5}(?:/\w+)?)(?P=q)""")


def bindable(port: int) -> bool:
    """True when nothing on this machine holds `port` (what Docker will try)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("0.0.0.0", port))
            return True
        except OSError:
            return False


class Ports:
    """Host ports handed out in this run, across every job and file."""

    def __init__(self, first_free: int = FIRST_FREE, is_free=None):
        self.taken: set[int] = set()
        self.next = first_free
        self.is_free = is_free or (lambda port: bindable(port))

    def keep(self, port: int) -> bool:
        if port in self.taken or not self.is_free(port):
            return False
        self.taken.add(port)
        return True

    def free(self) -> int:
        while self.next in self.taken or not self.is_free(self.next):
            self.next += 1
        self.taken.add(self.next)
        return self.next


def job_blocks(lines: list[str]) -> list[tuple[str, int, int]]:
    """(job id, first line, end line) for each job under the top-level `jobs:`."""
    blocks: list[tuple[str, int, int]] = []
    jobs_indent = job_indent = None
    current: tuple[str, int] | None = None
    for i, line in enumerate(lines):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        if jobs_indent is None:
            m = JOBS_KEY.match(line)
            if m and len(m["indent"]) == 0:
                jobs_indent = 0
            continue
        if indent <= jobs_indent:  # left the jobs map
            break
        key = KEY_LINE.match(line)
        if key and (job_indent is None or indent == job_indent):
            job_indent = indent
            if current:
                blocks.append((current[0], current[1], i))
            current = (line.strip().split(":")[0], i)
    if current:
        end = len(lines)
        if jobs_indent is not None:
            for j in range(current[1] + 1, len(lines)):
                s = lines[j]
                if s.strip() and not s.lstrip().startswith("#") and len(s) - len(s.lstrip()) <= jobs_indent:
                    end = j
                    break
        blocks.append((current[0], current[1], end))
    return blocks


def remap_job(lines: list[str], ports: Ports, label: str) -> tuple[list[str], list[str]]:
    """Move this job's taken host ports; rewrite its localhost uses in one pass."""
    moved: dict[int, int] = {}
    report: list[str] = []

    def fix(segment: str) -> str:
        def one(m: re.Match) -> str:
            host = int(m["host"])
            if host in moved:
                new = moved[host]
            elif ports.keep(host):
                return m.group(0)
            else:
                new = moved[host] = ports.free()
                report.append(f"act-compat: {label}: host port {host} is taken here; using {new} (localhost:{host} -> localhost:{new})")
            return f"{m['q']}{m['ip'] or ''}{new}:{m['cport']}{m['q']}"

        return MAPPING.sub(one, segment)

    out = list(lines)
    in_ports_indent: int | None = None
    mapping_lines: set[int] = set()
    for i, line in enumerate(out):
        key = PORTS_KEY.match(line)
        if key:
            rest = key["rest"]
            if rest.startswith("["):
                out[i] = line.replace(rest, fix(rest), 1)
                mapping_lines.add(i)
                in_ports_indent = None
            else:
                in_ports_indent = len(key["indent"])
            continue
        if in_ports_indent is not None:
            item = LIST_ITEM.match(line)
            if item and len(item["indent"]) >= in_ports_indent:
                head, sep, comment = line.partition("#")
                out[i] = fix(head) + sep + comment
                mapping_lines.add(i)
                continue
            if line.strip() and not line.lstrip().startswith("#"):
                in_ports_indent = None

    if moved:
        # One pass, so a rewritten port can never be rewritten again.
        uses = re.compile(r"\b(localhost|127\.0\.0\.1):(" + "|".join(str(p) for p in moved) + r")\b")
        for i, line in enumerate(out):
            if i not in mapping_lines:
                out[i] = uses.sub(lambda m: f"{m[1]}:{moved[int(m[2])]}", line)
    return out, report


def remap_text(text: str, ports: Ports, label: str = "") -> tuple[str, list[str]]:
    """Return the workflow text with host ports made unique and free, and a report."""
    lines = text.splitlines(keepends=True)
    report: list[str] = []
    for job, start, end in job_blocks(lines):
        new, job_report = remap_job(lines[start:end], ports, f"{label}:{job}" if label else job)
        lines[start:end] = new
        report += job_report
    return "".join(lines), report


def main(directory: str) -> int:
    ports = Ports()
    for path in sorted(Path(directory).glob("*.y*ml")):
        text = path.read_text(encoding="utf-8")
        new, report = remap_text(text, ports, path.name)
        for line in report:
            print(line)
        if new != text:
            path.write_text(new, encoding="utf-8")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__.strip().splitlines()[-1], file=sys.stderr)
        sys.exit(2)
    sys.exit(main(sys.argv[1]))

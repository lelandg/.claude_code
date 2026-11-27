#!/usr/bin/env python3
"""Make service-container ports start under act on this machine.

ci-local runs this over the workflow files in its THROWAWAY clone, never in
your checkout.

act runs a job's container on the host network and publishes each service's
`ports:` on the host, as GitHub does, so `localhost:5432` reaches the service.
The one difference is the host. A GitHub runner is an empty VM, while your
machine may already listen on that port (on WSL with mirrored networking,
anything Windows listens on counts). So for each published host port that is
already taken here:

  * the mapping moves to a free host port (`5432:5432` -> `45432:5432`), and
  * `localhost:5432` / `127.0.0.1:5432` in the same file moves with it.

A port that is free is left alone. The edit is line-based, so comments and
formatting survive and the workflow stays byte-for-byte what you wrote except
for the lines named in the printed report. Standard library only.

Usage: act_compat.py <workflow-dir>
"""
from __future__ import annotations

import re
import socket
import sys
from pathlib import Path

FIRST_FREE = 45432

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
    """Host ports chosen in this run, so two services never get the same one."""

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


def remap_text(text: str, ports: Ports, label: str = "") -> tuple[str, list[str]]:
    """Return the workflow text with taken host ports moved, and a report."""
    lines = text.splitlines(keepends=True)
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

    in_ports_indent: int | None = None
    for i, line in enumerate(lines):
        key = PORTS_KEY.match(line)
        if key:
            rest = key["rest"]
            if rest.startswith("["):
                lines[i] = line.replace(rest, fix(rest), 1)
                in_ports_indent = None
            else:
                in_ports_indent = len(key["indent"])
            continue
        if in_ports_indent is not None:
            item = LIST_ITEM.match(line)
            if item and len(item["indent"]) >= in_ports_indent:
                head, _, comment = line.partition("#")
                lines[i] = fix(head) + ("#" + comment if comment else "")
                continue
            if line.strip() and not line.lstrip().startswith("#"):
                in_ports_indent = None

    out = "".join(lines)
    for old, new in moved.items():
        out = re.sub(rf"\b(localhost|127\.0\.0\.1):{old}\b", rf"\g<1>:{new}", out)
    return out, report


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

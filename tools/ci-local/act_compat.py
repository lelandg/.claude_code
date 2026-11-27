#!/usr/bin/env python3
"""Make workflow jobs run under act on one machine the way they run on GitHub.

ci-local runs this over the workflow files in its THROWAWAY clone, never in
your checkout.

act runs a job's container on the host network and publishes each service's
`ports:` on the host, as GitHub does, so `localhost:5432` reaches the service.
What differs is the host:

  * GitHub gives every job (and every matrix instance) its own empty VM. Your
    machine may already listen on that port (on WSL with mirrored networking,
    anything Windows listens on counts), and
  * act runs the jobs side by side on ONE host, so two jobs that both publish
    5432 would collide with each other.

So, per job:

  * a published host port that is free and not used by another job stays;
    any other moves to a free port (`5432:5432` -> `45432:5432`);
  * the job's own `localhost:5432` / `127.0.0.1:5432` uses move with it,
    including values it inherits from the workflow-level `env:` (copied into
    the job's `env:`, so other jobs keep theirs). Lines inside `services:` and
    `container:` are left alone: a service's health check runs inside the
    service, where the port has not changed;
  * a matrix job that publishes fixed host ports runs one instance at a time
    (`max-parallel: 1`), since its instances would share those ports; any
    other matrix job runs at most --max-parallel instances at once;
  * a job with its own `container:` takes that container's options from the
    workflow instead of act's --container-options, so --container-options
    (the runner's CPU, memory and /proc settings) are added to them.

The edit is line-based, so comments and formatting survive and each file stays
byte-for-byte what you wrote except for the lines named in the printed report.
Standard library only.

Usage: act_compat.py <workflow-dir> [--max-parallel N] [--container-options OPTS]
"""
from __future__ import annotations

import re
import socket
import sys
from pathlib import Path

FIRST_FREE = 45432

TOP_KEY = re.compile(r"^(?P<key>[A-Za-z0-9_-]+):\s*(#.*)?$")
KEY_LINE = re.compile(r"^(?P<indent>\s*)(?P<key>[A-Za-z0-9_.-]+):(?P<rest>.*)$")
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


def split_comment(value: str) -> tuple[str, str]:
    """('--user 1001', '# why') from '--user 1001 # why'; a '#' inside quotes stays."""
    quote = ""
    for i, ch in enumerate(value):
        if quote:
            if ch == quote:
                quote = ""
        elif ch in ("'", '"'):
            quote = ch
        elif ch == "#" and (i == 0 or value[i - 1].isspace()):
            return value[:i].rstrip(), value[i:]
    return value, ""


def indent_of(line: str) -> int:
    return len(line) - len(line.lstrip())


def meaningful(line: str) -> bool:
    return bool(line.strip()) and not line.lstrip().startswith("#")


def block_end(lines: list[str], start: int, indent: int) -> int:
    """First line after `start` that is meaningful and indented <= `indent`."""
    for j in range(start + 1, len(lines)):
        if meaningful(lines[j]) and indent_of(lines[j]) <= indent:
            return j
    return len(lines)


def top_block(lines: list[str], key: str) -> tuple[int, int] | None:
    for i, line in enumerate(lines):
        m = TOP_KEY.match(line)
        if m and m["key"] == key:
            return i, block_end(lines, i, 0)
    return None


def job_blocks(lines: list[str]) -> list[tuple[str, int, int]]:
    """(job id, first line, end line) for each job under the top-level `jobs:`."""
    found = top_block(lines, "jobs")
    if not found:
        return []
    start, end = found
    blocks: list[tuple[str, int, int]] = []
    job_indent = None
    for i in range(start + 1, end):
        line = lines[i]
        if not meaningful(line):
            continue
        m = KEY_LINE.match(line)
        if m and (job_indent is None or indent_of(line) == job_indent):
            job_indent = indent_of(line)
            blocks.append((m["key"], i, block_end(lines, i, job_indent)))
    return blocks


def workflow_env(lines: list[str]) -> dict[str, str]:
    """Single-line `KEY: value` entries of the top-level `env:`."""
    found = top_block(lines, "env")
    out: dict[str, str] = {}
    if found:
        start, end = found
        child = None
        for i in range(start + 1, end):
            if not meaningful(lines[i]):
                continue
            child = child or indent_of(lines[i])
            m = KEY_LINE.match(lines[i])
            if m and indent_of(lines[i]) == child and m["rest"].strip() and not m["rest"].strip().startswith(("|", ">")):
                out[m["key"]] = m["rest"].strip()
    return out


def child_keys(lines: list[str]) -> tuple[int | None, dict[str, int]]:
    """For a job slice (line 0 = the job id), its child indent and key -> line."""
    child, keys = None, {}
    for i in range(1, len(lines)):
        if not meaningful(lines[i]):
            continue
        child = child or indent_of(lines[i])
        m = KEY_LINE.match(lines[i])
        if m and indent_of(lines[i]) == child:
            keys[m["key"]] = i
    return child, keys


def remap_job(lines: list[str], ports: Ports, label: str, wf_env: dict[str, str], max_parallel: int, container_options: str = "") -> tuple[list[str], list[str]]:
    out = list(lines)
    report: list[str] = []
    moved: dict[int, int] = {}
    child, keys = child_keys(out)
    if child is None:
        return out, report

    # Lines inside services: / container: are the containers' own world.
    inside: set[int] = set()
    for key in ("services", "container"):
        if key in keys:
            start = keys[key]
            inside.update(range(start, block_end(out, start, child)))

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

    published = False
    ports_indent: int | None = None
    for i in sorted(inside):
        line = out[i]
        key = PORTS_KEY.match(line)
        if key:
            rest = key["rest"]
            if rest.startswith("["):
                new = fix(rest)
                published = published or MAPPING.search(rest) is not None
                out[i] = line.replace(rest, new, 1)
                ports_indent = None
            else:
                ports_indent = indent_of(line)
            continue
        if ports_indent is not None:
            item = LIST_ITEM.match(line)
            if item and indent_of(line) >= ports_indent:
                head, sep, comment = line.partition("#")
                published = published or MAPPING.search(head) is not None
                out[i] = fix(head) + sep + comment
                continue
            if meaningful(line):
                ports_indent = None

    if moved:
        # One pass, so a rewritten port can never be rewritten again.
        uses = re.compile(r"\b(localhost|127\.0\.0\.1):(" + "|".join(str(p) for p in moved) + r")\b")
        sub = lambda text: uses.sub(lambda m: f"{m[1]}:{moved[int(m[2])]}", text)  # noqa: E731
        for i in range(1, len(out)):
            if i not in inside:
                out[i] = sub(out[i])
        # Values inherited from the workflow-level env move into this job's env.
        inherited = {k: sub(v) for k, v in wf_env.items() if sub(v) != v}
        if inherited:
            pad = " " * child
            added: list[str] = []
            if "env" in keys:
                env_at = keys["env"]
                env_end = block_end(out, env_at, child)
                if KEY_LINE.match(out[env_at])["rest"].split("#")[0].strip():
                    report.append(f"act-compat: {label}: workflow env {', '.join(inherited)} not copied: the job's env is written inline; set it in the job by hand")
                else:
                    entries = [j for j in range(env_at + 1, env_end) if meaningful(out[j])]
                    inner = " " * (indent_of(out[entries[0]]) if entries else child + 2)
                    own = {KEY_LINE.match(out[j])["key"] for j in entries if KEY_LINE.match(out[j])}
                    added = [k for k in inherited if k not in own]
                    out[env_at + 1:env_at + 1] = [f"{inner}{k}: {inherited[k]}\n" for k in added]
            else:
                added = list(inherited)
                out[1:1] = [f"{pad}env:\n"] + [f"{pad}  {k}: {inherited[k]}\n" for k in added]
            for k in added:
                report.append(f"act-compat: {label}: workflow env {k} copied into the job with the new port")
            child, keys = child_keys(out)

    # A job with its own `container:` gets that container's options from the
    # workflow, not from act's --container-options, so the runner's CPU,
    # memory and /proc settings are added to them.
    if container_options and "container" in keys:
        c_at = keys["container"]
        rest = KEY_LINE.match(out[c_at])["rest"].split("#")[0].strip()
        pad = " " * child
        if rest.startswith("{"):
            report.append(f"act-compat: {label}: job container written inline; the runner's CPU, memory and /proc settings were not added")
        elif rest:  # `container: node:22`
            out[c_at:c_at + 1] = [f"{pad}container:\n", f"{pad}  image: {rest}\n", f"{pad}  options: {container_options}\n"]
            report.append(f"act-compat: {label}: job container gets the runner's CPU, memory and /proc settings")
        else:
            c_end = block_end(out, c_at, child)
            entries = [j for j in range(c_at + 1, c_end) if meaningful(out[j])]
            inner = indent_of(out[entries[0]]) if entries else child + 2
            opt = next((j for j in entries if indent_of(out[j]) == inner and KEY_LINE.match(out[j]) and KEY_LINE.match(out[j])["key"] == "options"), None)
            if opt is None:
                out.insert(c_at + 1, f"{' ' * inner}options: {container_options}\n")
            else:
                value, comment = split_comment(KEY_LINE.match(out[opt])["rest"].strip())
                tail = f" {comment}" if comment else ""
                if value.startswith((">", "|")):  # a block scalar: one more line inside it
                    opt_end = block_end(out, opt, inner)  # only the scalar's own lines
                    body = [j for j in range(opt + 1, opt_end) if meaningful(out[j])]
                    at = (body[-1] + 1) if body else opt + 1
                    deeper = indent_of(out[body[0]]) if body else inner + 2
                    out.insert(at, f"{' ' * deeper}{container_options}\n")
                elif value[:1] in ("'", '"') and value[-1:] == value[:1] and len(value) > 1:
                    out[opt] = f"{' ' * inner}options: {value[:-1]} {container_options}{value[-1]}{tail}\n"
                else:
                    out[opt] = f"{' ' * inner}options: {value} {container_options}{tail}\n"
            report.append(f"act-compat: {label}: job container gets the runner's CPU, memory and /proc settings")
        child, keys = child_keys(out)

    # Matrix instances share this one host.
    if "strategy" in keys:
        s_at = keys["strategy"]
        s_end = block_end(out, s_at, child)
        inline = split_comment(KEY_LINE.match(out[s_at])["rest"].strip())[0]
        if inline and re.search(r"\bmatrix\b", inline):
            # `strategy: {matrix: ...}` cannot be edited safely line by line.
            why = "its instances share its service ports" if published else "jobs here share one disk"
            report.append(f"act-compat: {label}: inline matrix strategy left as written; max-parallel not applied ({why})")
        has_matrix = any(KEY_LINE.match(out[j]) and KEY_LINE.match(out[j])["key"] == "matrix" for j in range(s_at + 1, s_end))
        if has_matrix:
            limit = 1 if published else max_parallel
            why = "its instances would share its service ports" if published else "jobs here share one disk"
            mp = next((j for j in range(s_at + 1, s_end) if KEY_LINE.match(out[j]) and KEY_LINE.match(out[j])["key"] == "max-parallel"), None)
            if mp is not None:
                current = KEY_LINE.match(out[mp])["rest"].split("#")[0].strip()
                if not (current.isdigit() and int(current) <= limit):
                    out[mp] = f"{' ' * indent_of(out[mp])}max-parallel: {limit}\n"
                    report.append(f"act-compat: {label}: max-parallel {current} -> {limit} ({why})")
            else:
                inner = next((indent_of(out[j]) for j in range(s_at + 1, s_end) if meaningful(out[j])), child + 2)
                out.insert(s_at + 1, f"{' ' * inner}max-parallel: {limit}\n")
                report.append(f"act-compat: {label}: max-parallel {limit} ({why})")
    return out, report


def remap_text(text: str, ports: Ports, label: str = "", max_parallel: int = 4, container_options: str = "") -> tuple[str, list[str]]:
    """Return the workflow text adjusted for one shared host, and a report."""
    lines = text.splitlines(keepends=True)
    if lines and not lines[-1].endswith("\n"):
        lines[-1] += "\n"
    wf_env = workflow_env(lines)
    report: list[str] = []
    shift = 0  # lines inserted by earlier jobs move the later ones down
    for job, start, end in job_blocks(lines):
        start, end = start + shift, end + shift
        new, job_report = remap_job(lines[start:end], ports, f"{label}:{job}" if label else job, wf_env, max_parallel, container_options)
        lines[start:end] = new
        shift += len(new) - (end - start)
        report += job_report
    out = "".join(lines)
    return (out if text.endswith("\n") else out[:-1]), report


def main(argv: list[str]) -> int:
    if not argv or argv[0].startswith("-"):
        print(__doc__.strip().splitlines()[-1], file=sys.stderr)
        return 2
    directory, max_parallel, container_options = argv[0], 4, ""
    rest = argv[1:]
    while rest:
        if len(rest) >= 2 and rest[0] == "--max-parallel" and rest[1].isdigit() and int(rest[1]) > 0:
            max_parallel = int(rest[1])
        elif len(rest) >= 2 and rest[0] == "--container-options":
            container_options = rest[1]
        else:
            print(__doc__.strip().splitlines()[-1], file=sys.stderr)
            return 2
        rest = rest[2:]
    ports = Ports()
    # Ports are assigned in file and job order: the first job to publish a free
    # port keeps it, and every later one gets a distinct free port.
    for path in sorted(Path(directory).glob("*.y*ml")):
        text = path.read_text(encoding="utf-8")
        new, report = remap_text(text, ports, path.name, max_parallel, container_options)
        for line in report:
            print(line)
        if new != text:
            path.write_text(new, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

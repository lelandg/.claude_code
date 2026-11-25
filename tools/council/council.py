#!/usr/bin/env python3
"""Run a council of reviewer models over one committed change.

A council is a list of members, and a member is a model reached through an
agent CLI (Codex, Antigravity, Copilot, Claude Code). Who sits on it is data:
``council.toml`` names the members, the default seating, and any named
councils. Changing the line-up is an edit to that file, never to this one or
to the rule files that tell agents to "run the council".

Each member gets the same prompt and the same diff file, runs read-only, and
answers with one JSON object. An answer that is empty, unparseable, marked
incomplete, or about a different commit is a failed review, not a clean one.

Config, first one found wins:
  --config PATH, $AGENT_COUNCIL_CONFIG, ~/.config/agents/council.toml,
  then the default shipped in this repo (config/council.toml).
A repository may add ``.agents/council.toml`` to choose its default seating
and define named councils from the members the user's config already has. It
cannot add a member, a CLI, or a model: the file is part of the change under
review, so it must not be able to decide what gets run.

Exit codes: 0 every member answered, 10 at least one member failed,
20 the run could not start.

Runs from WSL (python3) or native Windows (python). Standard library only.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

REPO = Path(__file__).resolve().parents[2]
BUNDLED_CONFIG = REPO / "config" / "council.toml"
PROMPT_TEMPLATE = Path(__file__).resolve().parent / "prompt.md"
USER_CONFIG = Path.home() / ".config" / "agents" / "council.toml"
PROJECT_OVERLAY = Path(".agents") / "council.toml"
# Rule files a reviewer is pointed at, when they exist.
GLOBAL_RULES = Path.home() / ".config" / "agents" / "AGENTS.md"
INSTRUCTIONS = Path.home() / ".claude" / "instructions"

EXIT_OK, EXIT_MEMBER_FAILED, EXIT_ERROR = 0, 10, 20
EFFORTS = ("low", "medium", "high", "xhigh", "max")
NAME = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")
MODEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,79}$")
# Models with a record of destructive autonomous action: the Sol line, and the
# bare gpt-5.6 alias that resolves to it. Refused whatever the config says;
# no flag lifts this.
BANNED_MODEL = re.compile(r"(^gpt-5\.6$)|(-sol($|[-.]))", re.IGNORECASE)
MEMBER_KEYS = {"cli", "model", "effort", "timeout"}
OVERLAY_KEYS = {"schema_version", "default", "councils", "focus"}
VERDICTS = ("clean", "findings", "incomplete")
FENCE = re.compile(r"```(?:json)?\s*\n(.*?)```", re.DOTALL)
DEFAULT_TIMEOUT = 1800
ADVERSARIAL = (
    "Adversarial pass. Assume the change is wrong and look for the way it fails: a caller who is "
    "not who they claim, a request replayed or reordered, a migration interrupted halfway, a "
    "charge or credit applied twice or not at all."
)


class CouncilError(Exception):
    """A condition that stops the run before any member is called."""


@dataclass
class Member:
    name: str
    cli: str
    model: str
    effort: str | None = None
    timeout: int = DEFAULT_TIMEOUT


@dataclass
class Config:
    members: dict[str, Member]
    default: list[str]
    councils: dict[str, list[str]]
    focus: str = ""
    sources: list[str] = field(default_factory=list)


@dataclass
class Job:
    """What one member is asked to do; everything a driver needs."""
    member: Member
    repo: Path
    out: Path                 # this member's own folder
    shared: Path              # run folder holding change.diff, commits.txt, prompt.md
    prompt: str
    read_dirs: list[Path] = field(default_factory=list)   # extra folders the member may read


@dataclass
class Invocation:
    argv: list[str]
    stdin: str | None = None
    cwd: Path | None = None
    result_file: Path | None = None   # set when the CLI writes its answer to a file


# --------------------------------------------------------------------------
# Drivers: one per CLI. Each returns the read-only command line for a member.
# The command shapes are fixed here on purpose; config supplies only the
# model, the effort and the timeout, all validated before they reach an argv.
# Each shape was run against the real CLI on 2026-11-25 (codex-cli 0.163.0,
# agy 1.5.16, Copilot CLI 1.0.112, Claude Code 2.1.332).
# --------------------------------------------------------------------------

def _add_dirs(job: Job) -> list[str]:
    out: list[str] = []
    for d in [job.shared, *job.read_dirs]:
        out += ["--add-dir", str(d)]
    return out


def drive_codex(job: Job) -> Invocation:
    m = job.member
    result = job.out / "result.md"
    argv = ["codex", "exec", "-m", m.model]
    if m.effort:
        argv += ["-c", f"model_reasoning_effort={m.effort}"]
    # Generic exec, not the `review` subcommand: its built-in review prompt
    # would compete with the shared one.
    argv += ["-s", "read-only", "-C", str(job.repo), "--ephemeral", "-o", str(result), "-"]
    return Invocation(argv, stdin=job.prompt, cwd=job.repo, result_file=result)


AGY_READ_RULE = '{"permissions":{"allow":["read_file(*)","list_dir(*)"]}}'


def drive_agy(job: Job) -> Invocation:
    m = job.member
    model = f"{m.model}-{m.effort}" if m.effort else m.model   # agy carries the effort in the id
    # Plan mode plus the sandbox is agy's read-only mode. In it every shell
    # command is refused, so the diff reaches the model as a file, and file
    # reads need the session-only allow rule. The prompt must be an argument:
    # agy exits 2 when it arrives on stdin.
    argv = ["agy", "--model", model, "--mode", "plan", "--sandbox", "--settings", AGY_READ_RULE,
            "--add-dir", str(job.repo), *_add_dirs(job),
            "--print-timeout", f"{m.timeout}s", f"-p={job.prompt}"]
    return Invocation(argv, cwd=job.repo)


def drive_copilot(job: Job) -> Invocation:
    m = job.member
    argv = ["copilot", "-C", str(job.repo), "-s", "--no-color", "--no-auto-update", "--no-ask-user",
            "--disable-builtin-mcps", "--stream", "off", "--model", m.model]
    if m.effort:
        argv += ["--reasoning-effort", m.effort]
    argv += ["--deny-tool=write", "--deny-tool=shell", "--deny-tool=memory", "--allow-tool=read",
             *_add_dirs(job)]
    return Invocation(argv, stdin=job.prompt, cwd=job.repo)


def drive_claude(job: Job) -> Invocation:
    m = job.member
    argv = ["claude", "-p", "--model", m.model]
    if m.effort:
        argv += ["--effort", m.effort]
    argv += ["--permission-mode", "plan", "--tools", "Read", "Grep", "Glob",
             "--no-session-persistence", *_add_dirs(job)]
    return Invocation(argv, stdin=job.prompt, cwd=job.repo)


DRIVERS: dict[str, Callable[[Job], Invocation]] = {
    "codex": drive_codex,
    "agy": drive_agy,
    "copilot": drive_copilot,
    "claude": drive_claude,
}


# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------

def _read_toml(path: Path) -> dict:
    try:
        with path.open("rb") as fh:
            return tomllib.load(fh)
    except FileNotFoundError:
        raise CouncilError(f"config not found: {path}") from None
    except tomllib.TOMLDecodeError as exc:
        raise CouncilError(f"{path}: not valid TOML ({exc})") from None


def _names(value, where: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise CouncilError(f"{where}: expected a list of member names")
    return list(value)


def _member(name: str, raw, where: str) -> Member:
    if not NAME.match(name):
        raise CouncilError(f"{where}: member name {name!r} must be lowercase letters, digits, - or _")
    if not isinstance(raw, dict):
        raise CouncilError(f"{where}: [members.{name}] must be a table")
    unknown = set(raw) - MEMBER_KEYS
    if unknown:
        raise CouncilError(f"{where}: member {name!r} has unknown keys: {', '.join(sorted(unknown))}")
    cli, model = raw.get("cli"), raw.get("model")
    if cli not in DRIVERS:
        raise CouncilError(f"{where}: member {name!r} has cli {cli!r}; known CLIs: {', '.join(sorted(DRIVERS))}")
    if not isinstance(model, str) or not MODEL.match(model):
        raise CouncilError(f"{where}: member {name!r} needs a plain model id")
    if BANNED_MODEL.search(model):
        raise CouncilError(f"{where}: member {name!r} names {model!r}, which no agent may run")
    effort = raw.get("effort")
    if effort is not None and effort not in EFFORTS:
        raise CouncilError(f"{where}: member {name!r} effort {effort!r} is not one of {', '.join(EFFORTS)}")
    timeout = raw.get("timeout", DEFAULT_TIMEOUT)
    if not isinstance(timeout, int) or isinstance(timeout, bool) or not 30 <= timeout <= 7200:
        raise CouncilError(f"{where}: member {name!r} timeout must be 30 to 7200 seconds")
    return Member(name, cli, model, effort, timeout)


def _councils(raw, where: str) -> dict[str, list[str]]:
    if not isinstance(raw, dict):
        raise CouncilError(f"{where}: [councils] must be a table")
    out = {}
    for name, body in raw.items():
        if not NAME.match(name):
            raise CouncilError(f"{where}: council name {name!r} is not valid")
        if not isinstance(body, dict) or set(body) != {"members"}:
            raise CouncilError(f"{where}: [councils.{name}] takes exactly one key, members = [...]")
        out[name] = _names(body["members"], f"{where} councils.{name}.members")
    return out


def find_config(explicit: str | None, env: dict[str, str] | None = None) -> Path:
    env = os.environ if env is None else env
    if explicit:
        return Path(explicit)
    if env.get("AGENT_COUNCIL_CONFIG"):
        return Path(env["AGENT_COUNCIL_CONFIG"])
    return USER_CONFIG if USER_CONFIG.is_file() else BUNDLED_CONFIG


def load_config(path: Path, repo: Path | None = None) -> Config:
    raw = _read_toml(path)
    where = str(path)
    members_raw = raw.get("members")
    if not isinstance(members_raw, dict) or not members_raw:
        raise CouncilError(f"{where}: no [members.*] defined")
    cfg = Config(
        members={n: _member(n, body, where) for n, body in members_raw.items()},
        default=_names(raw.get("default", []), f"{where} default"),
        councils=_councils(raw.get("councils", {}), where),
        focus=str(raw.get("focus", "")),
        sources=[where],
    )
    overlay = (repo / PROJECT_OVERLAY) if repo else None
    if overlay and overlay.is_file():
        apply_overlay(cfg, _read_toml(overlay), str(overlay))
    for label, names in [("default", cfg.default), *((f"councils.{k}", v) for k, v in cfg.councils.items())]:
        for n in names:
            if n not in cfg.members:
                raise CouncilError(f"{label} names {n!r}, which is not a defined member "
                                   f"(defined: {', '.join(sorted(cfg.members))})")
    return cfg


def apply_overlay(cfg: Config, raw: dict, where: str) -> None:
    """Let a repository choose seating. It may not define what gets run."""
    extra = set(raw) - OVERLAY_KEYS
    if extra:
        raise CouncilError(f"{where}: a project council file may set only "
                           f"{', '.join(sorted(OVERLAY_KEYS - {'schema_version'}))}; "
                           f"found {', '.join(sorted(extra))}. Members are defined in the user's own config.")
    if "default" in raw:
        cfg.default = _names(raw["default"], f"{where} default")
    if "councils" in raw:
        cfg.councils.update(_councils(raw["councils"], where))
    if "focus" in raw:
        cfg.focus = str(raw["focus"])
    cfg.sources.append(where)


def seat(cfg: Config, members: str | None, council: str | None) -> list[Member]:
    if members and council:
        raise CouncilError("pass --members or --council, not both")
    if members:
        names = [n.strip() for n in members.split(",") if n.strip()]
    elif council:
        if council not in cfg.councils:
            raise CouncilError(f"no council named {council!r} (defined: {', '.join(sorted(cfg.councils)) or 'none'})")
        names = cfg.councils[council]
    else:
        names = cfg.default
    if not names:
        raise CouncilError("no members selected: set default = [...] in the config or pass --members")
    seated, seen = [], set()
    for n in names:
        if n not in cfg.members:
            raise CouncilError(f"unknown member {n!r} (defined: {', '.join(sorted(cfg.members))})")
        if n not in seen:
            seen.add(n)
            seated.append(cfg.members[n])
    return seated


# --------------------------------------------------------------------------
# The change under review
# --------------------------------------------------------------------------

def git(repo: Path, *args: str, check: bool = True) -> str:
    proc = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        if not check:
            return ""
        raise CouncilError(f"git {' '.join(args)} failed: {proc.stderr.strip() or proc.stdout.strip()}")
    return proc.stdout


def default_base(repo: Path) -> str:
    """The remote default branch: origin/HEAD when set, else main, else master."""
    head = git(repo, "symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD", check=False).strip()
    if head:
        return head
    for ref in ("origin/main", "origin/master"):
        if git(repo, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}", check=False).strip():
            return ref
    raise CouncilError("cannot find the base branch; pass --base <remote>/<branch>")


def collect_change(repo: Path, base: str | None, head: str, shared: Path) -> dict:
    base = base or default_base(repo)
    if base.startswith("-") or head.startswith("-"):
        raise CouncilError("base and head must be refs, not options")
    base_sha = git(repo, "rev-parse", "--verify", f"{base}^{{commit}}").strip()
    head_sha = git(repo, "rev-parse", "--verify", f"{head}^{{commit}}").strip()
    merge_base = git(repo, "merge-base", base_sha, head_sha).strip()
    diff = git(repo, "diff", "--no-color", "--no-ext-diff", f"{merge_base}..{head_sha}")
    if not diff.strip():
        raise CouncilError(f"nothing to review: {base}...{head} is empty")
    log = git(repo, "log", "--no-decorate", "--format=%h %s%n%n%b", f"{merge_base}..{head_sha}").strip()
    (shared / "change.diff").write_text(diff, encoding="utf-8", newline="\n")
    (shared / "commits.txt").write_text(log + "\n", encoding="utf-8", newline="\n")
    dirty = bool(git(repo, "status", "--porcelain", "--untracked-files=no").strip())
    checked_out = git(repo, "rev-parse", "HEAD").strip()
    return {
        "base": base, "head": head, "base_sha": merge_base, "head_sha": head_sha,
        "branch": git(repo, "rev-parse", "--abbrev-ref", head, check=False).strip() or head,
        "subject": git(repo, "log", "-1", "--format=%s", head_sha).strip(),
        "diff_bytes": len(diff.encode("utf-8")),
        # Members read files from the working tree, so say when it is not the reviewed commit.
        "worktree_differs_from_head": dirty or checked_out != head_sha,
    }


def rule_files(repo: Path) -> list[Path]:
    return [p for p in (GLOBAL_RULES, repo / "AGENTS.md") if p.is_file()]


def build_prompt(template: str, repo: Path, change: dict, shared: Path, focus: str,
                 purpose: str, rules: list[Path]) -> str:
    values = {
        "REPO_NAME": repo.name,
        "REPO_DIR": str(repo),
        "HEAD_SHA": change["head_sha"],
        "BASE_REF": change["base"],
        "BASE_SHA": change["base_sha"],
        "BRANCH": change["branch"],
        "PURPOSE": purpose.strip() or change["subject"] or "(not stated; infer it from the commit log)",
        "DIFF_FILE": str(shared / "change.diff"),
        "LOG_FILE": str(shared / "commits.txt"),
        "RULE_FILES": "\n".join(f"- {p}" for p in rules) or "- (none found)",
        "FOCUS": focus.strip() or "No narrower focus was given for this review.",
    }
    out = template
    for key, value in values.items():
        out = out.replace("{{" + key + "}}", value)
    left = re.findall(r"\{\{[A-Z_]+\}\}", out)
    if left:
        raise CouncilError(f"prompt template has unknown fields: {', '.join(sorted(set(left)))}")
    return out


# --------------------------------------------------------------------------
# Running members
# --------------------------------------------------------------------------

def resolve(argv: list[str]) -> list[str]:
    """Find the CLI on PATH. npm installs some as .ps1/.cmd shims on Windows."""
    exe = shutil.which(argv[0])
    if exe is None:
        raise FileNotFoundError(argv[0])
    if exe.lower().endswith(".ps1"):
        shell = shutil.which("pwsh") or shutil.which("powershell") or "powershell"
        return [shell, "-NoProfile", "-NonInteractive", "-File", exe, *argv[1:]]
    return [exe, *argv[1:]]


def execute(inv: Invocation, timeout: int) -> tuple[int, str, str]:
    proc = subprocess.run(resolve(inv.argv), input=inv.stdin, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", cwd=inv.cwd, timeout=timeout + 60)
    return proc.returncode, proc.stdout, proc.stderr


def parse_answer(text: str) -> dict | None:
    """The JSON object the prompt asks for: last fenced block, else the last {...} span."""
    candidates = [m.group(1) for m in FENCE.finditer(text)]
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        candidates.append(text[start:end + 1])
    for raw in reversed(candidates):
        try:
            obj = json.loads(raw)
        except ValueError:
            continue
        if isinstance(obj, dict) and "verdict" in obj:
            return obj
    return None


def judge(code: int | None, text: str, err: str, head_sha: str) -> tuple[str, str, dict | None]:
    """Turn one member's raw output into (status, detail, parsed answer)."""
    if code != 0:
        return "failed", f"exit {code}: {_last_line(err) or 'no error text'}", None
    if not text.strip():
        # Some CLIs exit 0 with nothing when a tool call was refused.
        return "failed", f"empty answer: {_last_line(err) or 'no error text'}", None
    answer = parse_answer(text)
    if answer is None:
        return "failed", "answer has no JSON object with a verdict (truncated or off-format)", None
    verdict = str(answer.get("verdict", "")).strip().lower()
    if verdict not in VERDICTS:
        return "failed", f"unknown verdict {verdict!r}", answer
    if verdict == "incomplete":
        why = "; ".join(str(x) for x in answer.get("not_reviewed") or []) or "no reason given"
        return "failed", f"review incomplete: {why[:300]}", answer
    reviewed = str(answer.get("reviewed_head", ""))
    if not reviewed or not head_sha.startswith(reviewed[:40]) or len(reviewed) < 7:
        return "failed", f"answer is about {reviewed or 'no commit'}, not {head_sha[:12]}", answer
    findings = answer.get("findings")
    if not isinstance(findings, list):
        return "failed", "answer has no findings list", answer
    if verdict == "clean" and findings:
        return "failed", "verdict is clean but findings are listed", answer
    return "ok", "", answer


def run_member(job: Job, head_sha: str, runner=execute) -> dict:
    m = job.member
    job.out.mkdir(parents=True, exist_ok=True)
    inv = DRIVERS[m.cli](job)
    (job.out / "cmd.txt").write_text(" ".join(_shown(inv.argv, job.prompt)) + "\n", encoding="utf-8")
    code, text, err, early = None, "", "", ""
    try:
        code, text, err = runner(inv, m.timeout)
        if inv.result_file is not None and inv.result_file.is_file():
            text = inv.result_file.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        early = f"{m.cli} is not installed or not on PATH"
    except subprocess.TimeoutExpired:
        early = f"timed out after {m.timeout}s"
    (job.out / "result.md").write_text(text, encoding="utf-8")
    (job.out / "err.txt").write_text(err, encoding="utf-8")
    status, detail, answer = ("failed", early, None) if early else judge(code, text, err, head_sha)
    findings = (answer or {}).get("findings") if status == "ok" else None
    return {
        "member": m.name, "cli": m.cli, "model": m.model, "effort": m.effort,
        "status": status, "detail": detail,
        "verdict": str(answer["verdict"]).lower() if status == "ok" else None,
        "findings": findings,
        "summary": str((answer or {}).get("summary", "")) if status == "ok" else "",
        "not_reviewed": (answer or {}).get("not_reviewed") or [],
        "result": str(job.out / "result.md"),
    }


def _shown(argv: list[str], prompt: str) -> list[str]:
    """The command line for the record, with the prompt replaced by its file name."""
    return ["-p=<prompt.md>" if a == f"-p={prompt}" else "<prompt.md>" if a == prompt else a for a in argv]


def _last_line(text: str) -> str:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    return lines[-1][:300] if lines else ""


def review(cfg: Config, members: list[Member], repo: Path, base: str | None, head: str, out: Path,
           focus: str = "", purpose: str = "", runner=execute, dry_run: bool = False) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    change = collect_change(repo, base, head, out)
    rules = rule_files(repo)
    template = PROMPT_TEMPLATE.read_text(encoding="utf-8")
    prompt = build_prompt(template, repo, change, out, focus or cfg.focus, purpose, rules)
    (out / "prompt.md").write_text(prompt, encoding="utf-8", newline="\n")
    read_dirs = [d for d in dict.fromkeys([*(p.parent for p in rules), INSTRUCTIONS])
                 if d.is_dir() and d != repo]
    jobs = [Job(m, repo, out / m.name, out, prompt, read_dirs) for m in members]
    if dry_run:
        results = [{"member": j.member.name, "status": "dry-run",
                    "argv": _shown(DRIVERS[j.member.cli](j).argv, prompt)} for j in jobs]
    else:
        with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
            results = list(pool.map(lambda j: run_member(j, change["head_sha"], runner), jobs))
    summary = {"repo": str(repo), "out": str(out), "config": cfg.sources, "change": change, "members": results}
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (out / "summary.md").write_text(render(summary), encoding="utf-8", newline="\n")
    return summary


def render(summary: dict) -> str:
    c = summary["change"]
    lines = [f"# Council review: {c['base']}...{c['head']}", "",
             f"Repository: `{summary['repo']}`  ", f"Head: `{c['head_sha'][:12]}`  ",
             f"Results: `{summary['out']}`", ""]
    if c.get("worktree_differs_from_head"):
        lines += ["**The working tree is not the reviewed commit (uncommitted changes or another "
                  "checkout). Members read files from the working tree, so re-run on a clean tree "
                  "before relying on this.**", ""]
    lines += ["| Member | Model | Status | Verdict | Findings |", "|---|---|---|---|---|"]
    for r in summary["members"]:
        if r["status"] == "dry-run":
            lines.append(f"| {r['member']} | | dry-run | | |")
            continue
        model = r["model"] + (f" ({r['effort']})" if r.get("effort") else "")
        status = "ok" if r["status"] == "ok" else f"FAILED: {r['detail']}"
        count = "" if r["findings"] is None else str(len(r["findings"]))
        lines.append(f"| {r['member']} | {model} | {status} | {r['verdict'] or ''} | {count} |")
    lines.append("")
    for r in summary["members"]:
        for f in r.get("findings") or []:
            if not isinstance(f, dict):
                continue
            where = f"{f.get('file', '?')}:{f.get('line', '?')}"
            lines.append(f"- **{r['member']}** [{f.get('severity', '?')}] `{where}` {f.get('title', '')}")
    failed = [r["member"] for r in summary["members"] if r["status"] == "failed"]
    if failed:
        lines += ["", f"Failed members did not review this change: {', '.join(failed)}. "
                      "A failed review is not a clean one; say so wherever this is reported."]
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def cmd_list(cfg: Config) -> int:
    print("config: " + " + ".join(cfg.sources))
    print("default: " + (", ".join(cfg.default) or "(none)"))
    for name, names in sorted(cfg.councils.items()):
        print(f"council {name}: {', '.join(names)}")
    print()
    for m in cfg.members.values():
        on_path = "installed" if shutil.which(m.cli) else "NOT INSTALLED"
        print(f"  {m.name:<12} {m.cli:<8} {m.model}{'  effort=' + m.effort if m.effort else ''}  ({on_path})")
    return EXIT_OK


def main(argv: list[str] | None = None, runner=execute) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(prog="council", description=__doc__.split("\n\n")[0])
    ap.add_argument("--config", help="council.toml to use instead of the user or bundled one")
    sub = ap.add_subparsers(dest="cmd", required=True)
    ls = sub.add_parser("list", help="show members, the default seating and named councils")
    ls.add_argument("--repo", default=None, help="also apply this repository's .agents/council.toml")
    rv = sub.add_parser("review", help="send one committed change to every seated member")
    rv.add_argument("--repo", default=".", help="repository to review (default: current directory)")
    rv.add_argument("--base", help="base ref (default: the remote's default branch)")
    rv.add_argument("--head", default="HEAD", help="head ref (default: HEAD)")
    rv.add_argument("--members", help="comma-separated member names, instead of the default seating")
    rv.add_argument("--council", help="a named council from the config")
    rv.add_argument("--purpose", help="what the change is for (PR title and first paragraph); @path reads a file")
    rv.add_argument("--focus", help="narrower focus for the reviewers; @path reads a file")
    rv.add_argument("--adversarial", action="store_true",
                    help="adversarial pass, for auth, billing and data-migration changes")
    rv.add_argument("--out", help="folder for results (default: a new temp folder)")
    rv.add_argument("--allow-max", action="store_true",
                    help="permit effort = \"max\" (costly; needs the owner's approval)")
    rv.add_argument("--dry-run", action="store_true",
                    help="write the diff and prompt, print the commands, call nobody")
    args = ap.parse_args(argv)
    try:
        repo = Path(args.repo).resolve() if args.repo else None
        cfg = load_config(find_config(args.config), repo)
        if args.cmd == "list":
            return cmd_list(cfg)
        seated = seat(cfg, args.members, args.council)
        if not args.allow_max and any(m.effort == "max" for m in seated):
            raise CouncilError("a seated member uses effort \"max\"; pass --allow-max once the owner has approved it")
        focus = _text_arg(args.focus)
        if args.adversarial:
            focus = (ADVERSARIAL + "\n" + focus).strip()
        out = Path(args.out).resolve() if args.out else Path(tempfile.mkdtemp(
            prefix="council-" + datetime.now().strftime("%Y%m%d-%H%M%S-")))
        summary = review(cfg, seated, repo, args.base, args.head, out, focus,
                         _text_arg(args.purpose), runner, args.dry_run)
    except (CouncilError, OSError) as exc:
        print(f"council: {exc}", file=sys.stderr)
        return EXIT_ERROR
    print(render(summary))
    if args.dry_run:
        for r in summary["members"]:
            print(r["member"] + ": " + " ".join(r["argv"]))
        return EXIT_OK
    return EXIT_MEMBER_FAILED if any(r["status"] == "failed" for r in summary["members"]) else EXIT_OK


def _text_arg(value: str | None) -> str:
    if not value:
        return ""
    return Path(value[1:]).read_text(encoding="utf-8") if value.startswith("@") else value


if __name__ == "__main__":
    sys.exit(main())

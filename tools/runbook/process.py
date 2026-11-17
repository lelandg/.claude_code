"""Processor: no model call unless something the owner owns changed."""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import shutil
import signal
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import rblib

ROOT = rblib.ROOT
PROMPT = ROOT / "processor-prompt.md"
LOCK_STALE_S = 2 * 60 * 60
TIMEOUT_S = 45 * 60
POST_WAIT_S = 60.0
TRAILERS = ("Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>", "AI-Model: claude-opus-5-5")

Runner = Callable[[list, Path], tuple]


def default_allowed_tools() -> list:
    """The unattended run reads third-party text (PR bodies, issue text, pasted
    output), so it gets no bare "Bash": only the command prefixes its procedure
    needs. config.json "allowed_tools" replaces this list wholesale; add your
    cloud admin tool's prefix there."""
    land = (Path.home() / ".claude" / "skills" / "land-pr" / "pr_tool.py").as_posix()
    tools = ["Read", "Edit", "Write", "Glob", "Grep", "Agent"]
    for py in ("python", "python3"):
        tools.append(f"Bash(RUNBOOK_AGENT=processor {py} {ROOT.as_posix()}/runbook.py:*)")
        tools.append(f"Bash({py} {land}:*)")
    tools += ["Bash(git -C:*)", "Bash(gh:*)", "Bash(aws:*)", "Bash(codex:*)", "Bash(npm:*)"]
    return tools


def load_config(state_dir: Path) -> dict:
    cfg = {"model": "opus", "effort": "medium", "daily_cap": 30}
    for p in (ROOT / "config.json", state_dir / "config.json"):
        try:
            cfg.update(json.loads(p.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            pass
    return cfg


def render_prompt() -> str:
    """The processor prompt with {RUNBOOK_DIR} and {PROJECTS_ROOT} filled in."""
    text = PROMPT.read_text(encoding="utf-8")
    return (text.replace("{RUNBOOK_DIR}", ROOT.as_posix())
                .replace("{PROJECTS_ROOT}", rblib.projects_root().as_posix()))


def build_command(cfg: dict) -> list:
    tools = [str(t) for t in cfg.get("allowed_tools") or default_allowed_tools()]
    if "Bash" in tools:
        raise ValueError("allowed_tools must not grant bare Bash; list Bash(<prefix>:*) rules")
    return [
        shutil.which("claude") or "claude", "-p", render_prompt(),
        "--model", cfg["model"], "--effort", cfg["effort"],
        "--permission-mode", "acceptEdits",
        "--allowedTools", *tools,
        "--add-dir", rblib.projects_root().as_posix(), "--output-format", "json",
    ]


def _parse_result(code: int, out: str) -> tuple:
    """Return (result line, ok)."""
    if code != 0:
        return f"error: exit {code}", False
    try:
        text = str(json.loads(out)["result"])
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        return (lines[-1] if lines else "error: empty result"), bool(lines)
    except (ValueError, KeyError, TypeError):
        return f"error: {out.strip()[:100]}", False


def _iso(now: datetime) -> str:
    return now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _git(d: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(d), *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def _commit(state_path: Path, reason: str, result: str) -> None:
    d, name = state_path.parent, state_path.name
    if _git(d, "rev-parse", "--is-inside-work-tree").stdout.strip() != "true":
        return
    if not _git(d, "status", "--porcelain", "--", name).stdout.strip():
        return
    subject = f"process: {reason} {result}".replace("\n", " ")
    _git(d, "commit", "-m", subject, "-m", "\n".join(TRAILERS), "--", name)


def run(reason: str, state_path: Path, now: datetime, runner: Runner) -> str:
    state_path = Path(state_path)
    cm = rblib.locked(state_path.parent / "process.lock", stale_s=LOCK_STALE_S, wait_s=0)
    try:
        cm.__enter__()
    except rblib.LockTimeout:
        return "skipped: run in progress"
    try:
        return _run_locked(reason, state_path, now, runner)
    finally:
        cm.__exit__(None, None, None)


def _run_locked(reason: str, state_path: Path, now: datetime, runner: Runner) -> str:
    cfg = load_config(state_path.parent)
    today = now.astimezone().date()
    today_s = today.isoformat()

    def stamp(state: dict, result: str) -> None:
        state["last_run"] = {"at": _iso(now), "reason": reason, "result": result}

    state = rblib.load(state_path)
    if rblib.owner_hash(state, today) == state.get("processed_hash"):
        rblib.mutate(lambda s: stamp(s, "no changes"), state_path)
        return "no changes"
    if (reason == "hourly" and state.get("error_streak", 0) >= 2
            and state.get("attempted_hash") == rblib.owner_hash(state, today)):
        rblib.mutate(lambda s: stamp(s, "skipped: repeated errors"), state_path)
        return "skipped: repeated errors"
    rt = state.get("runs_today") or {}
    if rt.get("date") == today_s and rt.get("count", 0) >= cfg["daily_cap"]:
        rblib.mutate(lambda s: stamp(s, "cap reached"), state_path)
        return "cap reached"

    rev0 = rblib.load(state_path).get("owner_rev", 0)
    code, out = runner(build_command(cfg), ROOT)
    result, ok = _parse_result(code, out)

    def after(s: dict) -> None:
        r = s.get("runs_today") or {}
        count = r.get("count", 0) if r.get("date") == today_s else 0
        s["runs_today"] = {"date": today_s, "count": count + 1}
        if ok:  # a failed run leaves the hash alone so the work is retried
            # An edit made mid-run must not be absorbed: leave it for the next run.
            edited = s.get("owner_rev", 0) != rev0
            s["processed_hash"] = "" if edited else rblib.owner_hash(s, today)
            s["last_processed"] = _iso(now)
            s["error_streak"] = 0
        else:
            s["error_streak"] = s.get("error_streak", 0) + 1
            s["attempted_hash"] = rblib.owner_hash(s, today)
        rblib.prune_done_log(s, now)
        stamp(s, result)

    try:
        with rblib.locked(state_path.with_name(state_path.name + ".lock"), wait_s=POST_WAIT_S):
            st = rblib.load(state_path)
            after(st)
            rblib.save(st, state_path)
    except rblib.LockTimeout:
        return "error: state lock"
    _commit(state_path, reason, result)
    return result


def _kill_tree(proc: subprocess.Popen) -> None:
    if os.name == "nt":
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True)
    else:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except OSError:
            proc.kill()


def _subprocess_runner(reason: str, now: datetime, logs: Path | None = None,
                       state_path: Path | None = None) -> Runner:
    # The model changes state only through runbook.py, which reads RUNBOOK_STATE,
    # so a non-default --state reaches the CLI calls it makes.
    env = dict(os.environ, RUNBOOK_STATE=str(state_path)) if state_path else None

    def runner(cmd: list, cwd: Path) -> tuple:
        d = logs or ROOT / "logs"
        d.mkdir(exist_ok=True)
        stem = f"{now.astimezone(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{reason}"
        log, err = d / f"{stem}.log", d / f"{stem}.err.log"
        with open(log, "wb") as fo, open(err, "wb") as fe:
            try:
                proc = subprocess.Popen(cmd, cwd=cwd, stdin=subprocess.DEVNULL, stdout=fo,
                                        stderr=fe, start_new_session=(os.name != "nt"),
                                        env=env)
            except OSError as e:
                return 127, str(e)
            try:
                code = proc.wait(timeout=TIMEOUT_S)
            except subprocess.TimeoutExpired:
                _kill_tree(proc)
                with contextlib.suppress(subprocess.TimeoutExpired):
                    proc.wait(timeout=10)
                return 124, "timeout"
        return code, log.read_text(encoding="utf-8", errors="replace")
    return runner


def main(argv: list | None = None) -> int:
    ap = argparse.ArgumentParser(prog="process")
    ap.add_argument("--reason", choices=("hourly", "submit"), required=True)
    ap.add_argument("--state", type=Path, default=rblib.STATE)
    args = ap.parse_args(argv)
    now = datetime.now(timezone.utc)
    runner = _subprocess_runner(args.reason, now, state_path=args.state)
    result = run(args.reason, args.state, now, runner)
    print(result)
    return 1 if result.startswith("error") else 0


if __name__ == "__main__":
    sys.exit(main())

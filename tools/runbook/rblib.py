"""State library for the central runbook: locking, atomic I/O, scanners, done log."""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import time
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Callable, TypeVar

T = TypeVar("T")

ROOT = Path(__file__).resolve().parent
STATE = ROOT / "runbook.json"
LOCK = ROOT / "runbook.json.lock"
CONFIG = ROOT / "config.json"

OWNER_ITEM_FIELDS = frozenset({"state", "output", "chosen", "other"})
ITEM_STATES = ("open", "done", "problem")
DONE_LOG_DAYS = 30


def projects_root() -> Path:
    """Directory holding your git repos (scanned for inboxes, given to the processor).

    Order: env RUNBOOK_PROJECTS_ROOT, then "projects_root" in config.json, then the
    parent of this tool's directory.
    """
    env = os.environ.get("RUNBOOK_PROJECTS_ROOT", "").strip()
    if env:
        return Path(env).expanduser()
    try:
        cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
        if isinstance(cfg, dict) and str(cfg.get("projects_root") or "").strip():
            return Path(str(cfg["projects_root"])).expanduser()
    except (OSError, ValueError):
        pass
    return ROOT.parent


class StaleVersion(Exception):
    """The caller's expected version no longer matches the file."""


class LockTimeout(Exception):
    """The lock stayed held by a live writer for the whole wait."""


class CorruptState(Exception):
    """The state file exists but is not valid state JSON."""


def empty_state() -> dict:
    return {
        "version": 0,
        "processed_hash": "",
        "last_processed": None,
        "last_run": None,
        "runs_today": {"date": None, "count": 0},
        "items": [],
        "done_log": [],
        "notes_self": "",
        "notes_claude": [],
    }


def _read_token(lock: Path) -> str | None:
    try:
        return lock.read_text(encoding="utf-8").split(" ", 1)[0]
    except OSError:
        return None


BREAK_STALE_S = 30.0


def _acquire_guard(guard: Path) -> bool:
    """O_EXCL-create the break guard; a guard older than BREAK_STALE_S is cleared."""
    for _ in range(2):
        try:
            os.close(os.open(str(guard), os.O_CREAT | os.O_EXCL | os.O_WRONLY))
            return True
        except FileExistsError:
            try:
                age = time.time() - guard.stat().st_mtime
            except FileNotFoundError:
                continue
            if age <= BREAK_STALE_S:
                return False
            with contextlib.suppress(OSError):
                guard.unlink()  # a breaker crashed; retry the create once
    return False


def _break_stale(lock: Path, stale_s: float, seen: str | None) -> bool:
    """Remove a stale lock under the guard. False means the guard was busy.

    The lock path is never created or moved here: the caller loops back to the
    normal O_EXCL create like every other waiter.
    """
    guard = lock.with_name(lock.name + ".break")
    if not _acquire_guard(guard):
        return False
    try:
        try:
            age = time.time() - lock.stat().st_mtime
        except FileNotFoundError:
            return True
        if age > stale_s and _read_token(lock) == seen:
            lock.unlink()
        return True
    finally:
        with contextlib.suppress(OSError):
            guard.unlink()


@contextlib.contextmanager
def locked(lock: Path = LOCK, stale_s: float = 10.0, wait_s: float = 5.0):
    """Exclusive lock via O_EXCL create; a lock older than stale_s is broken."""
    lock = Path(lock)
    token = uuid.uuid4().hex
    deadline = time.monotonic() + wait_s
    while True:
        try:
            fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                stale = time.time() - lock.stat().st_mtime > stale_s
            except FileNotFoundError:
                continue  # released meanwhile; retry now
            if stale:
                seen = _read_token(lock)
                try:
                    if _break_stale(lock, stale_s, seen):
                        continue
                except OSError:
                    pass  # could not remove it: wait, honouring the deadline
            if time.monotonic() >= deadline:
                raise LockTimeout(f"lock {lock} held")
            time.sleep(0.02)
            continue
        try:
            os.write(fd, f"{token} {os.getpid()} {time.time()}\n".encode())
        finally:
            os.close(fd)
        break
    try:
        yield
    finally:
        if _read_token(lock) == token:
            with contextlib.suppress(OSError):
                lock.unlink()


def load(path: Path = STATE) -> dict:
    path = Path(path)
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return empty_state()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise CorruptState(f"{path}: {e}") from e
    if not isinstance(data, dict):
        raise CorruptState(f"{path}: top level is not an object")
    return data


def _replace(src: str, dst: str) -> None:
    # Windows: replace can fail transiently while another process has dst open.
    for attempt in range(10):
        try:
            os.replace(src, dst)
            return
        except PermissionError:
            if attempt == 9:
                raise
            time.sleep(0.05)


def save(state: dict, path: Path = STATE) -> None:
    """Bump version and write atomically (temp file + os.replace)."""
    path = Path(path)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    old = state.get("version", 0)
    state["version"] = old + 1
    try:
        tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        _replace(str(tmp), str(path))
    except BaseException:
        state["version"] = old
        with contextlib.suppress(OSError):
            tmp.unlink()
        raise


def mutate(fn: Callable[[dict], T], path: Path = STATE, expect_version: int | None = None) -> T:
    """Load, apply fn, save, all under the lock. fn is not called on a stale version."""
    path = Path(path)
    with locked(path.with_name(path.name + ".lock")):
        state = load(path)
        if expect_version is not None and state.get("version", 0) != expect_version:
            raise StaleVersion(f"expected {expect_version}, file is at {state.get('version', 0)}")
        result = fn(state)
        save(state, path)
        return result


def _max_num(ids, prefix: str) -> int:
    top = 0
    for i in ids:
        m = re.fullmatch(re.escape(prefix) + r"(\d+)", str(i))
        if m:
            top = max(top, int(m.group(1)))
    return top


def next_item_id(state: dict) -> str:
    ids = [i.get("id") for i in state.get("items", []) + state.get("done_log", [])]
    return f"rb-{_max_num(ids, 'rb-') + 1:04d}"


def next_note_id(state: dict) -> str:
    ids = [n.get("id") for n in state.get("notes_claude", [])]
    return f"n-{_max_num(ids, 'n-') + 1}"


_SECRET_PATTERNS: tuple[tuple[str, re.Pattern], ...] = (
    ("aws-access-key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("anthropic-key", re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}")),
    ("stripe-live-key", re.compile(r"[rs]k_live_[A-Za-z0-9]{20,}")),
    ("github-token", re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{40,}")),
    ("slack-token", re.compile(r"xox[abpr]-[A-Za-z0-9-]{10,}")),
    ("private-key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    (
        "assigned-secret",
        re.compile(
            r"""(?i)\b(password|passwd|secret|token|api[_-]?key)\s*[=:]\s*['"]?(?!\$|<PASTE-)[^\s'"]{8,}"""
        ),
    ),
)

_PLACEHOLDER = re.compile(r"<[A-Za-z][\w.-]*>|\bYOUR_[A-Z_]+\b|\bTODO\b")


def find_secrets(text: str) -> list[str]:
    return [kind for kind, rx in _SECRET_PATTERNS if rx.search(text)]


def redact(text: str) -> tuple[str, list[str]]:
    kinds: list[str] = []
    for kind, rx in _SECRET_PATTERNS:
        text, n = rx.subn(f"[REDACTED:{kind}]", text)
        if n:
            kinds.append(kind)
    return text, kinds


def find_placeholders(text: str) -> list[str]:
    found: list[str] = []
    for m in _PLACEHOLDER.findall(text):
        if m.startswith("<PASTE-") or m in found:
            continue
        found.append(m)
    return found


def owner_hash(state: dict, today: date) -> str:
    """Hash of everything only the owner changes, plus items that came due."""
    today_s = today.isoformat()
    items = state.get("items", [])
    payload = {
        "items": sorted(
            [i.get("id"), i.get("state"), i.get("output"), i.get("chosen"), i.get("other")]
            for i in items
        ),
        "notes": sorted(
            [n.get("id"), n.get("text")]
            for n in state.get("notes_claude", [])
            if n.get("status") == "new"
        ),
        "due": sorted(i.get("id") for i in items if i.get("due") and str(i["due"]) <= today_s),
    }
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return "sha256:" + hashlib.sha256(blob.encode("utf-8")).hexdigest()


def move_to_done_log(state: dict, item_id: str, reason: str, by: str, now: datetime) -> dict:
    for idx, item in enumerate(state["items"]):
        if item.get("id") == item_id:
            entry = dict(state["items"].pop(idx))
            entry.update(removed_at=now.isoformat(timespec="seconds"), reason=reason, by=by)
            state["done_log"].insert(0, entry)
            return entry
    raise KeyError(item_id)


def restore_from_done_log(state: dict, item_id: str) -> dict:
    for idx, entry in enumerate(state["done_log"]):
        if entry.get("id") == item_id:
            item = dict(state["done_log"].pop(idx))
            for k in ("removed_at", "reason", "by"):
                item.pop(k, None)
            state["items"].append(item)
            return item
    raise KeyError(item_id)


def prune_done_log(state: dict, now: datetime) -> int:
    cutoff = now - timedelta(days=DONE_LOG_DAYS)
    keep = [
        e for e in state["done_log"]
        if not e.get("removed_at") or datetime.fromisoformat(e["removed_at"]) > cutoff
    ]
    removed = len(state["done_log"]) - len(keep)
    state["done_log"] = keep
    return removed

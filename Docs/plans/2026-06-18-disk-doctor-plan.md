# disk-doctor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `disk-doctor` Claude Code skill — scan home/dev locations for reclaimable space + install-hygiene problems, then either clean up (delete only through an audited Trash helper with guaranteed undo) or emit a runbook.

**Architecture:** A Claude-driven skill (`SKILL.md` + per-OS markdown rule packs) orchestrates the workflow, but every deletion is funneled through one hardened Python module (`disk_doctor_core.py`) exposed via two CLIs (`safe-trash`, `disk-doctor-undo`). The Python core is the only code, is the only thing that deletes, and gets the full test suite. Rule packs are data, not logic.

**Tech Stack:** Python 3 (standard library only — no pip dependencies), pytest for tests, Markdown for skill/rule/template files.

## Global Constraints

- **Python standard library only.** No external packages (no `send2trash` etc.). Trash is implemented via the FreeDesktop spec on Linux; quarantine fallback elsewhere. (Sidesteps the min-package-age rule entirely.)
- **Deny-by-default.** A path is trashed only if it is inside an explicitly allowed root AND not inside any denied root. Denylist is checked before allowlist; deny always wins.
- **In-script denylist floor.** The absolute never-touch list lives in `disk_doctor_core.py` and cannot be weakened by any rule pack. Rule packs may only ADD denied paths.
- **Never `rm`.** Deletions move to the OS Trash (FreeDesktop on Linux) or a managed quarantine dir. Never an unrecoverable delete.
- **Dry-run is the default.** `safe-trash` writes nothing unless `--commit` is passed.
- **Manifest before move.** A manifest record is written before each move; if it cannot be written, that deletion is aborted (raise, do not move).
- **Refuse symlinks as targets.** Any input path that is itself a symlink is refused (avoids smuggling denied locations through links).
- **All operations logged** to `~/.disk-doctor/disk-doctor.log` (platform-independent), every refusal/move/undo with reason.
- **Skill location:** `claude/skills/disk-doctor/` (this repo syncs to `~/.claude/`).
- **v1 undo guarantee:** fully automatic on Linux (FreeDesktop restore). On macOS/Windows v1, trashing works but undo is "restore from the system Trash/Recycle Bin using the manifest list" — documented limitation.

---

## File Structure

```
claude/skills/disk-doctor/
├── SKILL.md                       # Task 6 — the workflow Claude follows
├── rules/
│   ├── linux.md                   # Task 5
│   ├── macos.md                   # Task 7
│   └── windows.md                 # Task 7
├── bin/
│   ├── disk_doctor_core.py        # Tasks 1,2,4,5 — the only logic (importable; underscores)
│   ├── safe-trash                 # Task 3 — CLI entry, imports core
│   └── disk-doctor-undo           # Task 4 — CLI entry, imports core
├── reference/
│   └── report-template.md         # Task 6 — plan/runbook shape
└── tests/
    ├── conftest.py                # Task 1 — puts bin/ on sys.path
    ├── test_path_safety.py        # Task 1
    ├── test_trash.py              # Task 2
    ├── test_cli_safe_trash.py     # Task 3
    ├── test_undo.py               # Task 4
    └── test_rules.py              # Task 5
```

Run tests from the skill dir with: `python3 -m pytest tests/ -v` (cwd = `claude/skills/disk-doctor/`).

---

## Task 1: Path-safety core (resolve, denylist, allowlist)

The heart of the safety model. Decides whether a path may ever be touched.

**Files:**
- Create: `claude/skills/disk-doctor/bin/disk_doctor_core.py`
- Create: `claude/skills/disk-doctor/tests/conftest.py`
- Test: `claude/skills/disk-doctor/tests/test_path_safety.py`

**Interfaces:**
- Produces:
  - `home() -> pathlib.Path` — current user home, read dynamically (honors `$HOME`).
  - `resolve_path(p) -> pathlib.Path` — `expanduser().resolve(strict=False)`.
  - `denylist_floor() -> list[Path]` — in-script absolute never-touch roots (resolved).
  - `class Verdict` with string constants `OK`, `DENIED`, `NOT_ALLOWED`, `MISSING`, `SYMLINK`.
  - `classify(path, allowed_roots, extra_denied=()) -> tuple[str, Path]` — returns `(Verdict.*, resolved_path)`.

- [ ] **Step 1: Create the test sys.path shim**

`claude/skills/disk-doctor/tests/conftest.py`:

```python
import os
import sys

# Put the skill's bin/ directory on sys.path so tests can import disk_doctor_core.
BIN = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bin")
if BIN not in sys.path:
    sys.path.insert(0, BIN)
```

- [ ] **Step 2: Write the failing test**

`claude/skills/disk-doctor/tests/test_path_safety.py`:

```python
import os
from pathlib import Path

import pytest

import disk_doctor_core as core


@pytest.fixture
def fake_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path), raising=True)
    return tmp_path


def test_allowed_path_is_ok(fake_home):
    target = fake_home / "Downloads" / "junk.zip"
    target.parent.mkdir(parents=True)
    target.write_text("x")
    verdict, rp = core.classify(target, allowed_roots=[fake_home / "Downloads"])
    assert verdict == core.Verdict.OK
    assert rp == target.resolve()


def test_system_path_is_denied(fake_home):
    verdict, _ = core.classify("/etc/passwd", allowed_roots=["/etc"])
    assert verdict == core.Verdict.DENIED  # deny beats allow


def test_home_root_itself_is_denied(fake_home):
    verdict, _ = core.classify(fake_home, allowed_roots=[fake_home])
    assert verdict == core.Verdict.DENIED


def test_local_share_is_denied(fake_home):
    target = fake_home / ".local" / "share" / "Steam"
    target.mkdir(parents=True)
    verdict, _ = core.classify(target, allowed_roots=[fake_home])
    assert verdict == core.Verdict.DENIED


def test_browser_profile_is_denied(fake_home):
    target = fake_home / ".mozilla" / "firefox"
    target.mkdir(parents=True)
    verdict, _ = core.classify(target, allowed_roots=[fake_home])
    assert verdict == core.Verdict.DENIED


def test_path_outside_allowlist_is_not_allowed(fake_home):
    target = fake_home / "Documents" / "taxes.pdf"
    target.parent.mkdir(parents=True)
    target.write_text("x")
    verdict, _ = core.classify(target, allowed_roots=[fake_home / "Downloads"])
    assert verdict == core.Verdict.NOT_ALLOWED


def test_symlink_target_is_refused(fake_home):
    real = fake_home / "Downloads" / "real.txt"
    real.parent.mkdir(parents=True)
    real.write_text("x")
    link = fake_home / "Downloads" / "link.txt"
    link.symlink_to(real)
    verdict, _ = core.classify(link, allowed_roots=[fake_home / "Downloads"])
    assert verdict == core.Verdict.SYMLINK


def test_missing_path(fake_home):
    verdict, _ = core.classify(fake_home / "Downloads" / "nope", allowed_roots=[fake_home / "Downloads"])
    assert verdict == core.Verdict.MISSING


def test_extra_denied_can_only_add(fake_home):
    target = fake_home / "Downloads" / "keepme"
    target.mkdir(parents=True)
    verdict, _ = core.classify(
        target, allowed_roots=[fake_home / "Downloads"], extra_denied=[fake_home / "Downloads" / "keepme"]
    )
    assert verdict == core.Verdict.DENIED
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `python3 -m pytest tests/test_path_safety.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'disk_doctor_core'`.

- [ ] **Step 4: Write minimal implementation**

`claude/skills/disk-doctor/bin/disk_doctor_core.py`:

```python
"""disk-doctor safety core. Standard library only.

The ONLY code in disk-doctor that can delete. Deny-by-default, in-script
denylist floor, Trash-not-rm, manifest-before-move, dry-run default.
"""
import os
from pathlib import Path


def home():
    return Path(os.path.expanduser("~"))


def resolve_path(p):
    return Path(p).expanduser().resolve(strict=False)


def denylist_floor():
    """Absolute never-touch roots. Cannot be weakened by rule packs."""
    h = home()
    raw = [
        Path("/"), Path("/usr"), Path("/etc"), Path("/bin"), Path("/sbin"),
        Path("/boot"), Path("/lib"), Path("/lib64"), Path("/opt"), Path("/var"),
        Path("/System"), Path("/Library"),
        Path("C:/Windows"), Path("C:/Program Files"), Path("C:/Program Files (x86)"),
        h,                                       # home root itself
        h / ".ssh", h / ".config", h / ".gnupg",
        h / ".local" / "share",                  # app data (Steam, GNOME state, etc.)
        # browser profiles (bookmarks/history/logins)
        h / ".mozilla",
        h / ".config" / "google-chrome",
        h / ".config" / "chromium",
        h / "snap" / "firefox",
        h / "Library" / "Application Support" / "Firefox",
        h / "Library" / "Application Support" / "Google" / "Chrome",
        h / "Library" / "Application Support" / "Chromium",
    ]
    return [resolve_path(p) for p in raw]


class Verdict:
    OK = "ok"
    DENIED = "denied"
    NOT_ALLOWED = "not_allowed"
    MISSING = "missing"
    SYMLINK = "symlink"


def _is_within(path, root):
    return path == root or root in path.parents


def classify(path, allowed_roots, extra_denied=()):
    """Return (Verdict, resolved_path). Deny is checked before allow."""
    raw = Path(path).expanduser()
    if raw.is_symlink():
        return Verdict.SYMLINK, raw
    rp = resolve_path(raw)
    if not rp.exists():
        return Verdict.MISSING, rp
    denied = denylist_floor() + [resolve_path(x) for x in extra_denied]
    for d in denied:
        if _is_within(rp, d):
            return Verdict.DENIED, rp
    for root in allowed_roots:
        if _is_within(rp, resolve_path(root)):
            return Verdict.OK, rp
    return Verdict.NOT_ALLOWED, rp
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_path_safety.py -v`
Expected: PASS (9 passed).

- [ ] **Step 6: Commit**

```bash
git add claude/skills/disk-doctor/bin/disk_doctor_core.py claude/skills/disk-doctor/tests/conftest.py claude/skills/disk-doctor/tests/test_path_safety.py
git commit -m "feat(disk-doctor): path-safety core with denylist/allowlist guard"
```

---

## Task 2: Trash mechanism, manifest, and logging

Adds the actual move-to-Trash with dry-run default, manifest-before-move, and logging. Builds on `classify` from Task 1.

**Files:**
- Modify: `claude/skills/disk-doctor/bin/disk_doctor_core.py`
- Test: `claude/skills/disk-doctor/tests/test_trash.py`

**Interfaces:**
- Consumes: `classify`, `resolve_path`, `home`, `Verdict` (Task 1).
- Produces:
  - `base_dir(base=None) -> Path` — `~/.disk-doctor` unless overridden.
  - `log_event(event, path, detail, base=None) -> None` — appends to `disk-doctor.log`.
  - `trash_item(path, run_id, allowed_roots, *, commit=False, extra_denied=(), base=None, prefer_freedesktop=True) -> dict`
    — returns a record dict with keys `original`, `size`, `action` (`"dry-run"|"trashed"|"refused"`), and on commit also `dest`, `method` (`"freedesktop"|"quarantine"`). Refused records include `reason` (a `Verdict`).
  - Manifest path: `base/runs/<run_id>.jsonl` (one JSON object per line).

- [ ] **Step 1: Write the failing test**

`claude/skills/disk-doctor/tests/test_trash.py`:

```python
import json
from pathlib import Path

import pytest

import disk_doctor_core as core


@pytest.fixture
def fake_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path), raising=True)
    return tmp_path


@pytest.fixture
def dd_base(tmp_path):
    return tmp_path / ".disk-doctor"


def _make(fake_home, name="Downloads/junk.zip", content="data"):
    p = fake_home / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return p


def test_dry_run_moves_nothing_and_writes_no_manifest(fake_home, dd_base):
    target = _make(fake_home)
    rec = core.trash_item(target, "run1", [fake_home / "Downloads"], commit=False, base=dd_base)
    assert rec["action"] == "dry-run"
    assert target.exists()                       # untouched
    assert not (dd_base / "runs" / "run1.jsonl").exists()


def test_commit_quarantine_moves_and_writes_manifest(fake_home, dd_base):
    target = _make(fake_home)
    rec = core.trash_item(
        target, "run1", [fake_home / "Downloads"], commit=True, base=dd_base, prefer_freedesktop=False
    )
    assert rec["action"] == "trashed"
    assert rec["method"] == "quarantine"
    assert not target.exists()                   # moved out
    assert Path(rec["dest"]).exists()            # now in quarantine
    lines = (dd_base / "runs" / "run1.jsonl").read_text().splitlines()
    assert len(lines) == 1
    saved = json.loads(lines[0])
    assert saved["original"] == str(target.resolve())
    assert saved["dest"] == rec["dest"]


def test_commit_freedesktop_lands_in_trash_with_trashinfo(fake_home, dd_base):
    target = _make(fake_home)
    rec = core.trash_item(
        target, "run1", [fake_home / "Downloads"], commit=True, base=dd_base, prefer_freedesktop=True
    )
    assert rec["method"] == "freedesktop"
    trash_files = fake_home / ".local" / "share" / "Trash" / "files"
    trash_info = fake_home / ".local" / "share" / "Trash" / "info"
    assert Path(rec["dest"]).parent == trash_files
    assert Path(rec["dest"]).exists()
    info = list(trash_info.glob("*.trashinfo"))
    assert len(info) == 1
    assert "Path=" in info[0].read_text()


def test_denied_path_is_refused_not_moved(fake_home, dd_base):
    target = _make(fake_home, name=".ssh/id_rsa")
    rec = core.trash_item(target, "run1", [fake_home], commit=True, base=dd_base)
    assert rec["action"] == "refused"
    assert rec["reason"] == core.Verdict.DENIED
    assert target.exists()                       # never moved


def test_abort_when_manifest_unwritable(fake_home, dd_base):
    target = _make(fake_home)
    # Make runs/ a FILE so the manifest append raises before any move.
    (dd_base / "runs").parent.mkdir(parents=True, exist_ok=True)
    dd_base.mkdir(parents=True, exist_ok=True)
    (dd_base / "runs").write_text("not a dir")
    with pytest.raises(OSError):
        core.trash_item(target, "run1", [fake_home / "Downloads"], commit=True, base=dd_base)
    assert target.exists()                       # aborted before move


def test_every_event_is_logged(fake_home, dd_base):
    target = _make(fake_home)
    core.trash_item(target, "run1", [fake_home / "Downloads"], commit=True, base=dd_base, prefer_freedesktop=False)
    log = (dd_base / "disk-doctor.log").read_text()
    assert "trash" in log
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest tests/test_trash.py -v`
Expected: FAIL — `AttributeError: module 'disk_doctor_core' has no attribute 'trash_item'`.

- [ ] **Step 3: Write minimal implementation (append to `disk_doctor_core.py`)**

```python
import json
import shutil
import time
import urllib.parse


def base_dir(base=None):
    return Path(base) if base is not None else home() / ".disk-doctor"


def _now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def log_event(event, path, detail, base=None):
    b = base_dir(base)
    b.mkdir(parents=True, exist_ok=True)
    line = "%s\t%s\t%s\t%s\n" % (_now_iso(), event, path, detail)
    with open(b / "disk-doctor.log", "a", encoding="utf-8") as fh:
        fh.write(line)


def _size(path):
    if path.is_dir():
        total = 0
        for root, _dirs, files in os.walk(path):
            for f in files:
                fp = Path(root) / f
                if not fp.is_symlink() and fp.exists():
                    total += fp.stat().st_size
        return total
    return path.stat().st_size


def _freedesktop_trash_dir():
    data_home = os.environ.get("XDG_DATA_HOME") or str(home() / ".local" / "share")
    return Path(data_home) / "Trash"


def _unique_name(directory, name):
    candidate = directory / name
    i = 1
    while candidate.exists():
        candidate = directory / ("%s.%d" % (name, i))
        i += 1
    return candidate


def _compute_dest(rp, run_id, base, prefer_freedesktop):
    """Decide where the file will go. Does NOT move it."""
    if prefer_freedesktop:
        files_dir = _freedesktop_trash_dir() / "files"
        try:
            files_dir.mkdir(parents=True, exist_ok=True)
            dest = _unique_name(files_dir, rp.name)
            return dest, "freedesktop"
        except OSError:
            pass  # fall through to quarantine
    q = base_dir(base) / "trash" / run_id
    q.mkdir(parents=True, exist_ok=True)
    return _unique_name(q, rp.name), "quarantine"


def _write_trashinfo(dest, original):
    info_dir = _freedesktop_trash_dir() / "info"
    info_dir.mkdir(parents=True, exist_ok=True)
    info_path = info_dir / (dest.name + ".trashinfo")
    quoted = urllib.parse.quote(str(original))
    info_path.write_text(
        "[Trash Info]\nPath=%s\nDeletionDate=%s\n" % (quoted, _now_iso()),
        encoding="utf-8",
    )
    return info_path


def _append_manifest(base, run_id, record):
    runs = base_dir(base) / "runs"
    runs.mkdir(parents=True, exist_ok=True)  # raises OSError if 'runs' exists as a file
    with open(runs / ("%s.jsonl" % run_id), "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")


def trash_item(path, run_id, allowed_roots, *, commit=False,
               extra_denied=(), base=None, prefer_freedesktop=True):
    verdict, rp = classify(path, allowed_roots, extra_denied)
    if verdict != Verdict.OK:
        log_event("refuse", rp, verdict, base)
        return {"original": str(rp), "action": "refused", "reason": verdict}

    record = {"run_id": run_id, "ts": _now_iso(), "original": str(rp), "size": _size(rp)}
    if not commit:
        record["action"] = "dry-run"
        return record

    dest, method = _compute_dest(rp, run_id, base_dir(base), prefer_freedesktop)
    record["dest"] = str(dest)
    record["method"] = method
    record["action"] = "trashed"

    # Manifest BEFORE move. If this raises, we abort without touching the file.
    try:
        _append_manifest(base, run_id, record)
    except OSError as exc:
        log_event("abort-no-manifest", rp, str(exc), base)
        raise

    shutil.move(str(rp), str(dest))
    if method == "freedesktop":
        _write_trashinfo(dest, rp)
    log_event("trash", rp, dest, base)
    return record
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_trash.py -v`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add claude/skills/disk-doctor/bin/disk_doctor_core.py claude/skills/disk-doctor/tests/test_trash.py
git commit -m "feat(disk-doctor): trash mechanism, manifest-before-move, logging"
```

---

## Task 3: `safe-trash` CLI

A thin executable over `trash_item`. Dry-run default; `--commit` to act.

**Files:**
- Create: `claude/skills/disk-doctor/bin/safe-trash`
- Test: `claude/skills/disk-doctor/tests/test_cli_safe_trash.py`

**Interfaces:**
- Consumes: `trash_item` (Task 2).
- Produces: CLI `safe-trash [--allow ROOT]... [--commit] [--run-id ID] [--quarantine] PATH...`
  - `--allow` repeatable; at least one required. `--quarantine` forces quarantine over FreeDesktop. Prints one JSON record per path to stdout. Exit code 0 if all paths handled (incl. refusals), 2 if no `--allow` given.

- [ ] **Step 1: Write the failing test**

`claude/skills/disk-doctor/tests/test_cli_safe_trash.py`:

```python
import json
import os
import subprocess
import sys
from pathlib import Path

BIN = Path(__file__).resolve().parent.parent / "bin" / "safe-trash"


def _run(args, home):
    env = dict(os.environ)
    env["HOME"] = str(home)
    return subprocess.run(
        [sys.executable, str(BIN)] + args,
        capture_output=True, text=True, env=env,
    )


def test_requires_allow(tmp_path):
    res = _run([str(tmp_path / "x")], tmp_path)
    assert res.returncode == 2


def test_dry_run_default_reports_without_moving(tmp_path):
    target = tmp_path / "Downloads" / "junk.zip"
    target.parent.mkdir(parents=True)
    target.write_text("x")
    res = _run(["--allow", str(tmp_path / "Downloads"), str(target)], tmp_path)
    assert res.returncode == 0
    rec = json.loads(res.stdout.strip().splitlines()[0])
    assert rec["action"] == "dry-run"
    assert target.exists()


def test_commit_quarantine_moves(tmp_path):
    target = tmp_path / "Downloads" / "junk.zip"
    target.parent.mkdir(parents=True)
    target.write_text("x")
    res = _run(
        ["--allow", str(tmp_path / "Downloads"), "--commit", "--quarantine",
         "--run-id", "runX", str(target)],
        tmp_path,
    )
    assert res.returncode == 0
    rec = json.loads(res.stdout.strip().splitlines()[0])
    assert rec["action"] == "trashed"
    assert not target.exists()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest tests/test_cli_safe_trash.py -v`
Expected: FAIL — file `bin/safe-trash` does not exist (subprocess errors / non-zero unexpected).

- [ ] **Step 3: Write minimal implementation**

`claude/skills/disk-doctor/bin/safe-trash` (make executable: `chmod +x`):

```python
#!/usr/bin/env python3
"""safe-trash — the only sanctioned deletion path for disk-doctor.

Dry-run by default. Moves to OS Trash (FreeDesktop) or quarantine on --commit.
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import disk_doctor_core as core  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description="Safely move paths to Trash (dry-run by default).")
    parser.add_argument("paths", nargs="+")
    parser.add_argument("--allow", action="append", default=[],
                        help="Allowed root (repeatable). Required.")
    parser.add_argument("--commit", action="store_true", help="Actually move (default: dry-run).")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--quarantine", action="store_true",
                        help="Force managed quarantine instead of FreeDesktop Trash.")
    args = parser.parse_args(argv)

    if not args.allow:
        sys.stderr.write("error: at least one --allow ROOT is required\n")
        return 2

    run_id = args.run_id or time.strftime("run-%Y%m%d-%H%M%S")
    for p in args.paths:
        rec = core.trash_item(
            p, run_id, args.allow,
            commit=args.commit,
            prefer_freedesktop=not args.quarantine,
        )
        sys.stdout.write(json.dumps(rec) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `chmod +x claude/skills/disk-doctor/bin/safe-trash && python3 -m pytest tests/test_cli_safe_trash.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add claude/skills/disk-doctor/bin/safe-trash claude/skills/disk-doctor/tests/test_cli_safe_trash.py
git commit -m "feat(disk-doctor): safe-trash CLI (dry-run default)"
```

---

## Task 4: Undo (core + `disk-doctor-undo` CLI)

Restores a run from its manifest. Never overwrites an existing file.

**Files:**
- Modify: `claude/skills/disk-doctor/bin/disk_doctor_core.py`
- Create: `claude/skills/disk-doctor/bin/disk-doctor-undo`
- Test: `claude/skills/disk-doctor/tests/test_undo.py`

**Interfaces:**
- Consumes: `trash_item`, `base_dir`, `log_event` (Task 2).
- Produces:
  - `restore_run(run_id, *, base=None) -> list[dict]` — each `{"original": str, "status": "restored"|"collision"|"missing-in-trash"}`.
  - `latest_run_id(base=None) -> str | None` — most recent manifest stem by mtime.
  - CLI `disk-doctor-undo [--run ID]` — defaults to latest run; prints one JSON result per item.

- [ ] **Step 1: Write the failing test**

`claude/skills/disk-doctor/tests/test_undo.py`:

```python
from pathlib import Path

import pytest

import disk_doctor_core as core


@pytest.fixture
def fake_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path), raising=True)
    return tmp_path


def test_trash_then_undo_roundtrip(fake_home, tmp_path):
    base = tmp_path / ".disk-doctor"
    target = fake_home / "Downloads" / "junk.zip"
    target.parent.mkdir(parents=True)
    target.write_text("payload")
    core.trash_item(target, "runR", [fake_home / "Downloads"], commit=True, base=base, prefer_freedesktop=False)
    assert not target.exists()

    results = core.restore_run("runR", base=base)
    assert results and all(r["status"] == "restored" for r in results)
    assert target.exists()
    assert target.read_text() == "payload"


def test_undo_does_not_overwrite_collision(fake_home, tmp_path):
    base = tmp_path / ".disk-doctor"
    target = fake_home / "Downloads" / "junk.zip"
    target.parent.mkdir(parents=True)
    target.write_text("original")
    core.trash_item(target, "runR", [fake_home / "Downloads"], commit=True, base=base, prefer_freedesktop=False)
    target.write_text("new file in the way")  # recreate at original path

    results = core.restore_run("runR", base=base)
    assert results[0]["status"] == "collision"
    assert target.read_text() == "new file in the way"  # untouched


def test_latest_run_id(fake_home, tmp_path):
    base = tmp_path / ".disk-doctor"
    runs = base / "runs"
    runs.mkdir(parents=True)
    (runs / "run-A.jsonl").write_text("{}\n")
    (runs / "run-B.jsonl").write_text("{}\n")
    assert core.latest_run_id(base=base) in {"run-A", "run-B"}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest tests/test_undo.py -v`
Expected: FAIL — `AttributeError: ... has no attribute 'restore_run'`.

- [ ] **Step 3: Write minimal implementation (append to `disk_doctor_core.py`)**

```python
def latest_run_id(base=None):
    runs = base_dir(base) / "runs"
    if not runs.is_dir():
        return None
    manifests = sorted(runs.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    return manifests[0].stem if manifests else None


def restore_run(run_id, *, base=None):
    manifest = base_dir(base) / "runs" / ("%s.jsonl" % run_id)
    results = []
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        if rec.get("action") != "trashed":
            continue
        original = Path(rec["original"])
        dest = Path(rec["dest"])
        if original.exists():
            log_event("undo-collision", original, dest, base)
            results.append({"original": str(original), "status": "collision"})
            continue
        if not dest.exists():
            log_event("undo-missing", original, dest, base)
            results.append({"original": str(original), "status": "missing-in-trash"})
            continue
        original.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(dest), str(original))
        # Clean up FreeDesktop .trashinfo sidecar if present.
        if rec.get("method") == "freedesktop":
            info = _freedesktop_trash_dir() / "info" / (dest.name + ".trashinfo")
            if info.exists():
                info.unlink()
        log_event("undo-restore", original, dest, base)
        results.append({"original": str(original), "status": "restored"})
    return results
```

- [ ] **Step 4: Run the core tests to verify they pass**

Run: `python3 -m pytest tests/test_undo.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Create the CLI**

`claude/skills/disk-doctor/bin/disk-doctor-undo` (make executable):

```python
#!/usr/bin/env python3
"""disk-doctor-undo — restore a disk-doctor run from its manifest."""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import disk_doctor_core as core  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description="Restore a disk-doctor run from Trash/quarantine.")
    parser.add_argument("--run", default=None, help="Run id (default: latest).")
    args = parser.parse_args(argv)

    run_id = args.run or core.latest_run_id()
    if not run_id:
        sys.stderr.write("error: no runs found to undo\n")
        return 2

    for result in core.restore_run(run_id):
        sys.stdout.write(json.dumps(result) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 6: Commit**

```bash
chmod +x claude/skills/disk-doctor/bin/disk-doctor-undo
git add claude/skills/disk-doctor/bin/disk_doctor_core.py claude/skills/disk-doctor/bin/disk-doctor-undo claude/skills/disk-doctor/tests/test_undo.py
git commit -m "feat(disk-doctor): one-command undo (restore_run + disk-doctor-undo CLI)"
```

---

## Task 5: Rule-pack validator + Linux rule pack

A rule pack is data Claude reads. The validator guarantees every pack has the required sections so the engine never guesses conventions.

**Files:**
- Modify: `claude/skills/disk-doctor/bin/disk_doctor_core.py`
- Create: `claude/skills/disk-doctor/rules/linux.md`
- Test: `claude/skills/disk-doctor/tests/test_rules.py`

**Interfaces:**
- Produces:
  - `REQUIRED_RULE_SECTIONS = ["Allowed roots", "Never-touch (additional)", "Cache-clean rules", "Install-hygiene rules"]`
  - `validate_rule_pack(path) -> list[str]` — returns a list of missing section names (empty list = valid).

- [ ] **Step 1: Write the failing test**

`claude/skills/disk-doctor/tests/test_rules.py`:

```python
from pathlib import Path

import disk_doctor_core as core

RULES = Path(__file__).resolve().parent.parent / "rules"


def test_linux_rule_pack_is_valid():
    missing = core.validate_rule_pack(RULES / "linux.md")
    assert missing == []


def test_malformed_pack_reports_missing_sections(tmp_path):
    bad = tmp_path / "bad.md"
    bad.write_text("# Bad rule pack\n\nNothing useful here.\n")
    missing = core.validate_rule_pack(bad)
    assert set(missing) == set(core.REQUIRED_RULE_SECTIONS)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest tests/test_rules.py -v`
Expected: FAIL — `AttributeError: ... 'validate_rule_pack'` and missing `rules/linux.md`.

- [ ] **Step 3: Implement the validator (append to `disk_doctor_core.py`)**

```python
REQUIRED_RULE_SECTIONS = [
    "Allowed roots",
    "Never-touch (additional)",
    "Cache-clean rules",
    "Install-hygiene rules",
]


def validate_rule_pack(path):
    """Return list of required section headings missing from the rule pack."""
    text = Path(path).read_text(encoding="utf-8")
    headings = {line.lstrip("#").strip() for line in text.splitlines() if line.lstrip().startswith("#")}
    return [s for s in REQUIRED_RULE_SECTIONS if s not in headings]
```

- [ ] **Step 4: Write the Linux rule pack**

`claude/skills/disk-doctor/rules/linux.md`:

```markdown
# disk-doctor rule pack — Linux (Pop!_OS / Debian family)

This file is DATA the disk-doctor skill reads. It declares conventions and
rules. It can only ADD restrictions; the in-script denylist floor in
`disk_doctor_core.py` always wins and cannot be weakened here.

## Allowed roots

Roots that `safe-trash --allow` may be pointed at (cleanup targets live here):

- `~/Downloads`
- `~/.cache`
- `~/.local/share/Trash` (already-trashed items pending purge)
- `~/.npm/_cacache`
- `~/.cache/pip`
- Dev project working dirs under `~` (for stale `node_modules`, `__pycache__`, `.venv`)

## Never-touch (additional)

Added on top of the in-script floor (`/`, `/usr`, `/etc`, `~`, `~/.ssh`,
`~/.config`, `~/.gnupg`, `~/.local/share`, browser profiles, etc.):

- `~/.local/bin`
- `~/.gitconfig`, `~/.bashrc`, `~/.profile`, `~/.zshrc`
- Any path under a mounted external/removable drive (`/media`, `/mnt`) unless the user names it explicitly

## Cache-clean rules

Safe-to-clean categories and how to find them. These RECLAIM space:

- **pip cache:** `~/.cache/pip`
- **npm cache:** `~/.npm/_cacache`
- **Browser caches (NOT profiles):** `~/.cache/mozilla`, `~/.cache/google-chrome`, `~/.cache/chromium`
- **Thumbnail cache:** `~/.cache/thumbnails`
- **`__pycache__` dirs** anywhere under dev project dirs
- **`node_modules`** in projects whose source was not modified in 90+ days (stale)
- **Old logs:** `*.log` under `~/.cache` and project dirs, older than 30 days
- **Duplicates:** identical files (match by size, then SHA-256) — keep the newest, propose the rest
- **Large-and-old:** files > 500 MB not accessed in 180+ days (propose, never assume)

Note: browser CACHE dirs above are cleanable; browser PROFILE dirs
(`~/.mozilla`, `~/.config/google-chrome`, `~/.config/chromium`,
`~/snap/firefox`) are on the never-touch floor and must not overlap.

## Install-hygiene rules

Report-only. Detect and explain; never auto-fix.

- **pip outside a venv:** packages in `~/.local/lib/python*/site-packages` or system site-packages installed by user-level `pip install`. Fix: `python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
- **Global npm packages:** `npm ls -g --depth=0` shows non-essential packages. Fix: prefer per-project installs or `npx`.
- **Project missing a venv:** dir has `requirements.txt`/`pyproject.toml` but no `.venv`/virtualenv. Fix: create a venv before installing.
- **Duplicate Python toolchains:** conda + system + pyenv all on PATH. Report which `python3`/`pip` actually resolves (`which -a python3 pip`).
- **Orphaned env leftovers:** `.venv`/`node_modules` in abandoned/stale project dirs — surface as a cleanup item, not a hygiene fix.
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_rules.py -v`
Expected: PASS (2 passed).

- [ ] **Step 6: Run the full suite**

Run: `python3 -m pytest tests/ -v`
Expected: PASS (all tasks 1–5 green).

- [ ] **Step 7: Commit**

```bash
git add claude/skills/disk-doctor/bin/disk_doctor_core.py claude/skills/disk-doctor/rules/linux.md claude/skills/disk-doctor/tests/test_rules.py
git commit -m "feat(disk-doctor): rule-pack validator + Linux rule pack"
```

---

## Task 6: SKILL.md engine + report/runbook template

The Claude-driven workflow. Not unit-tested code — verified by a manual smoke test on Pop!_OS. This task ties scanning, the clean-up/runbook fork, and the helpers together.

**Files:**
- Create: `claude/skills/disk-doctor/SKILL.md`
- Create: `claude/skills/disk-doctor/reference/report-template.md`

**Interfaces:**
- Consumes: `rules/<os>.md` (Task 5/7), `bin/safe-trash`, `bin/disk-doctor-undo` (Tasks 3/4).

- [ ] **Step 1: Write the report/runbook template**

`claude/skills/disk-doctor/reference/report-template.md`:

```markdown
# disk-doctor report — {{date}} ({{os}})

**Total reclaimable: {{total_human}}**

## Cleanup candidates (by reclaimable size)

| Category | Size | What it is (plain English) | Path(s) |
|---|---|---|---|
| {{category}} | {{size}} | {{reason}} | {{paths}} |

## Install-hygiene findings (report-only — nothing was changed)

| Issue | Where | Why it matters | Suggested fix (run yourself) |
|---|---|---|---|
| {{issue}} | {{location}} | {{impact}} | `{{fix_command}}` |

## Commands (runbook mode only)

Each cleanup category above maps to a command you can run yourself:

```bash
# {{category}} ({{size}})
safe-trash --allow {{allowed_root}} --commit {{paths}}
```

To undo the most recent cleanup at any time:

```bash
disk-doctor-undo
```
```

- [ ] **Step 2: Write SKILL.md**

`claude/skills/disk-doctor/SKILL.md`:

```markdown
---
name: disk-doctor
description: Use when the user wants to free up disk space or check install hygiene on their machine — "clean up my disk", "my drive is full", "find junk files", "did I install something in the wrong place", "make a cleanup runbook". Scans home + dev/cache locations, proposes a plain-English plan, then either cleans up (recoverable Trash with one-command undo) or writes a runbook. Never touches system files; deletes only via the audited safe-trash helper.
---

# disk-doctor

Reclaim disk space and surface install-hygiene problems — safely. You scan and
reason; the bundled `bin/safe-trash` is the ONLY thing that may delete, and it
only ever moves files to the Trash with a guaranteed undo.

## Absolute rules (never break these)

1. **Never delete with `rm`, `shutil`, `os.remove`, or any direct call.** Every
   deletion goes through `bin/safe-trash`. No exceptions.
2. **Never touch system directories** or anything on the denylist floor in
   `bin/disk_doctor_core.py`. If unsure, don't.
3. **Dry-run first, always.** Show the plan (a `safe-trash` run WITHOUT
   `--commit`) and get explicit approval before committing.
4. **Report hygiene issues; never auto-fix package environments.**

## Workflow

1. **Detect the OS** (`uname`, platform). Load the matching `rules/<os>.md`
   (`linux.md` / `macos.md` / `windows.md`). State which platform you detected.
   If the rule pack is missing or fails `validate_rule_pack`, stop and say so.
2. **Scan** the rule pack's "Allowed roots" read-only. Apply the "Cache-clean
   rules" to find candidates; gather sizes, ages, and categories. Compute
   duplicates by size then SHA-256.
3. **Run the install-hygiene checks** from the rule pack — read-only
   (`pip list`, `npm ls -g`, PATH inspection). Never import or run project code.
4. **Build the plan**: fill `reference/report-template.md` and write it to
   `~/.disk-doctor/runs/<run-id>-plan.md`. Rank by reclaimable size.
5. **Present the plan summary**, then **use the AskUserQuestion tool** to ask:
   - **"Clean up now"** or **"Create a runbook"**.
6. **If "Clean up now":**
   - If there is more than one cleanup category, **use AskUserQuestion again**
     (multi-select) so the user picks which categories — list each with its size,
     plus an "Everything" option. Keep it one decision, not item-by-item.
   - For each chosen category, run `bin/safe-trash --allow <root> --commit
     --run-id <run-id> <paths...>`. Show the JSON results.
   - Report total reclaimed, that files went to the Trash, and that
     `bin/disk-doctor-undo` reverses the whole run.
7. **If "Create a runbook":**
   - **Use AskUserQuestion** for the format: **Markdown**, **HTML**, or **Other**
     (free text — honor what they type; if you can't, say so and give the closest).
   - **Markdown:** fill the template, save `~/.disk-doctor/runs/<run-id>-runbook.md`.
   - **HTML:** invoke the `html-doc` skill to render a polished standalone page from
     the same content; save `...-runbook.html`.
   - The runbook lists every finding + the exact `safe-trash` command to reclaim it,
     plus the hygiene section. **Make no changes to the system.** Surface the file path.

## Helpers

- `bin/safe-trash [--allow ROOT]... [--commit] [--run-id ID] [--quarantine] PATH...`
  — dry-run unless `--commit`. Refuses denied/disallowed/symlink paths. One JSON
  record per path on stdout.
- `bin/disk-doctor-undo [--run ID]` — restores a run (latest by default) from the
  manifest. Never overwrites existing files.

## Platform notes

- **Linux:** trashing uses the FreeDesktop spec — items appear in the system Trash
  AND undo is fully automatic.
- **macOS / Windows (v1):** trashing works; automatic undo is not yet implemented —
  tell the user to restore from the Trash/Recycle Bin using the run's manifest at
  `~/.disk-doctor/runs/<run-id>.jsonl`.
```

- [ ] **Step 3: Manual smoke test (verification, not automated)**

On the Pop!_OS box, with a throwaway file:

```bash
mkdir -p ~/Downloads && echo junk > ~/Downloads/dd-smoke.tmp
claude/skills/disk-doctor/bin/safe-trash --allow ~/Downloads ~/Downloads/dd-smoke.tmp        # dry-run
claude/skills/disk-doctor/bin/safe-trash --allow ~/Downloads --commit ~/Downloads/dd-smoke.tmp
ls ~/Downloads/dd-smoke.tmp 2>&1            # expected: No such file (moved to Trash)
claude/skills/disk-doctor/bin/disk-doctor-undo
ls ~/Downloads/dd-smoke.tmp                 # expected: file restored
```

Verify: dry-run leaves the file; commit moves it to Trash AND it appears in the Files app Trash; undo restores it. Also confirm `~/.disk-doctor/disk-doctor.log` has entries.

- [ ] **Step 4: Commit**

```bash
git add claude/skills/disk-doctor/SKILL.md claude/skills/disk-doctor/reference/report-template.md
git commit -m "feat(disk-doctor): SKILL.md workflow + report/runbook template"
```

---

## Task 7: macOS + Windows rule packs

Cross-platform completeness. Each must pass `validate_rule_pack`.

**Files:**
- Create: `claude/skills/disk-doctor/rules/macos.md`
- Create: `claude/skills/disk-doctor/rules/windows.md`
- Test: extend `claude/skills/disk-doctor/tests/test_rules.py`

**Interfaces:**
- Consumes: `validate_rule_pack`, `REQUIRED_RULE_SECTIONS` (Task 5).

- [ ] **Step 1: Add failing tests for both packs**

Append to `claude/skills/disk-doctor/tests/test_rules.py`:

```python
def test_macos_rule_pack_is_valid():
    assert core.validate_rule_pack(RULES / "macos.md") == []


def test_windows_rule_pack_is_valid():
    assert core.validate_rule_pack(RULES / "windows.md") == []
```

- [ ] **Step 2: Run to verify they fail**

Run: `python3 -m pytest tests/test_rules.py -v`
Expected: FAIL — `FileNotFoundError` for `macos.md` / `windows.md`.

- [ ] **Step 3: Write `rules/macos.md`**

```markdown
# disk-doctor rule pack — macOS

Data the disk-doctor skill reads. Can only ADD restrictions; the in-script
denylist floor always wins. v1 note: trashing works; automatic undo is not yet
implemented on macOS — restore from the Finder Trash using the run manifest.

## Allowed roots

- `~/Downloads`
- `~/Library/Caches`
- `~/.npm/_cacache`
- `~/Library/Caches/pip`
- Dev project working dirs under `~` (stale `node_modules`, `__pycache__`, `.venv`)

## Never-touch (additional)

On top of the in-script floor (`/`, `/System`, `/Library`, `~`, `~/.ssh`,
`~/.config`, `~/Library/Application Support/{Firefox,Google/Chrome,Chromium}`):

- `/Applications`
- `~/Library/Keychains`
- `~/Library/Mobile Documents` (iCloud Drive)

## Cache-clean rules

- **pip cache:** `~/Library/Caches/pip`
- **npm cache:** `~/.npm/_cacache`
- **Browser caches (NOT profiles):** `~/Library/Caches/Firefox`, `~/Library/Caches/Google/Chrome`
- **`__pycache__`** under dev project dirs
- **`node_modules`** in projects untouched 90+ days
- **Duplicates:** match by size then SHA-256; keep newest
- **Large-and-old:** > 500 MB not accessed in 180+ days (propose only)

## Install-hygiene rules

Report-only.

- **pip outside a venv:** user/system site-packages. Fix: `python3 -m venv .venv && ...`
- **Global npm packages:** `npm ls -g --depth=0`. Fix: per-project installs or `npx`.
- **Project missing a venv:** has `requirements.txt`/`pyproject.toml`, no `.venv`.
- **Duplicate Python toolchains:** Homebrew + system + pyenv. Report `which -a python3 pip`.
- **Orphaned env leftovers:** stale `.venv`/`node_modules` → cleanup item.
```

- [ ] **Step 4: Write `rules/windows.md`**

```markdown
# disk-doctor rule pack — Windows

Data the disk-doctor skill reads. Can only ADD restrictions; the in-script
denylist floor always wins. v1 note: trashing works; automatic undo is not yet
implemented on Windows — restore from the Recycle Bin using the run manifest.

## Allowed roots

- `%USERPROFILE%\Downloads`
- `%LOCALAPPDATA%\Temp`
- `%LOCALAPPDATA%\pip\Cache`
- `%APPDATA%\npm-cache`
- Dev project working dirs under `%USERPROFILE%` (stale `node_modules`, `__pycache__`, `.venv`)

## Never-touch (additional)

On top of the in-script floor (`C:\Windows`, `C:\Program Files`,
`C:\Program Files (x86)`, the user profile root, browser profiles under
`%APPDATA%`/`%LOCALAPPDATA%`):

- `%APPDATA%\Microsoft`
- `%LOCALAPPDATA%\Microsoft`
- `%USERPROFILE%\AppData\Local\Programs`

## Cache-clean rules

- **pip cache:** `%LOCALAPPDATA%\pip\Cache`
- **npm cache:** `%APPDATA%\npm-cache`
- **Temp:** `%LOCALAPPDATA%\Temp` (files not modified in 7+ days)
- **Browser caches (NOT profiles):** `...\Google\Chrome\User Data\*\Cache` (cache subdir only)
- **`__pycache__`** under dev project dirs
- **`node_modules`** in projects untouched 90+ days
- **Duplicates:** match by size then SHA-256; keep newest
- **Large-and-old:** > 500 MB not accessed in 180+ days (propose only)

## Install-hygiene rules

Report-only.

- **pip outside a venv:** user site-packages under `%APPDATA%\Python`. Fix: `python -m venv .venv & ...`
- **Global npm packages:** `npm ls -g --depth=0`. Fix: per-project installs or `npx`.
- **Project missing a venv:** has `requirements.txt`/`pyproject.toml`, no `.venv`.
- **Duplicate Python toolchains:** Microsoft Store Python + python.org + conda. Report `where python pip`.
- **Orphaned env leftovers:** stale `.venv`/`node_modules` → cleanup item.
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_rules.py -v`
Expected: PASS (4 passed).

- [ ] **Step 6: Full suite + commit**

```bash
python3 -m pytest tests/ -v   # expected: all green
git add claude/skills/disk-doctor/rules/macos.md claude/skills/disk-doctor/rules/windows.md claude/skills/disk-doctor/tests/test_rules.py
git commit -m "feat(disk-doctor): macOS + Windows rule packs"
```

---

## Self-Review

**1. Spec coverage**

| Spec section | Covered by |
|---|---|
| §3 Architecture (3 layers) | File structure; Tasks 1–7 |
| §4 safe-trash guarantees (resolve, denylist, allowlist, Trash, manifest-before-move, dry-run, symlink refusal) | Tasks 1–3 |
| §4 in-script denylist floor incl. `~/.local/share` + browser profiles | Task 1 `denylist_floor()` + test |
| §4 disk-doctor-undo | Task 4 |
| §4 logging to disk-doctor.log | Task 2 `log_event` + test |
| §5 Workflow incl. clean-up vs runbook fork + AskUserQuestion + format prompt | Task 6 SKILL.md |
| §6 Install-hygiene checks (report-only) | Rule packs (Tasks 5, 7), SKILL.md step 3 |
| §7 Error handling (perm denied, no native trash, dangling symlink, manifest fail, undo collision, malformed pack) | Tasks 1,2,4,5 (+ skill notes) |
| §8 Testing (adversarial path safety, dry-run, round-trip, rule-pack validator, manual smoke) | Tasks 1–7 |
| §9 Future phases | Out of scope (noted) |

No gaps.

**2. Placeholder scan:** No "TBD"/"handle edge cases"/"similar to Task N" — all code is complete and repeated where needed. Template `{{...}}` tokens are intentional Mustache-style fields in a doc template, not plan placeholders.

**3. Type consistency:** `classify` returns `(Verdict, Path)` everywhere; `trash_item` record keys (`original`, `action`, `dest`, `method`, `reason`) match across Tasks 2/3/4; `restore_run` result keys (`original`, `status`) match Task 4 CLI and tests; `validate_rule_pack`/`REQUIRED_RULE_SECTIONS` consistent across Tasks 5/7; `--allow`/`--commit`/`--run-id`/`--quarantine` flags consistent between SKILL.md and the CLI.

Plan is internally consistent and fully covers the spec.

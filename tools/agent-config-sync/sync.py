#!/usr/bin/env python3
"""Two-way sync of agent instruction files between the WSL and Windows homes.

Design: Docs/plans/2026-10-17-slim-agent-config-sync-design.md

Each in-scope file is compared three ways: WSL, Windows, and the last-synced
copy (the baseline). A change on one side is copied to the other; a change on
both sides is a conflict that only ``apply --take`` resolves. Derived files
(per-CLI copies of AGENTS.md) are regenerated from their source. Report-only
files are compared by key name; values are never printed.

Runs from WSL (python3) or native Windows (python). Standard library only.
"""
from __future__ import annotations

import argparse
import difflib
import io
import json
import os
import posixpath
import stat
import subprocess
import sys
import tomllib
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path, PureWindowsPath

REPO = Path(__file__).resolve().parents[2]
DEFAULT_SCOPE = REPO / "config" / "agent-sync.toml"
DEFAULT_STATE = REPO / "baseline"  # gitignored; on shared storage, so both runtimes see it

SIDES = ("wsl", "windows")
IO_REPARSE_TAG_LX_SYMLINK = 0xA000001D
PENDING = {"record", "forget", "to_wsl", "to_windows", "delete_wsl", "delete_windows",
           "regen_wsl", "regen_windows", "regen_both", "conflict", "blocked"}


class SyncError(Exception):
    """A condition that stops the run (bad scope, unsafe write, failed detection)."""


@dataclass
class Derived:
    path: str
    source: str


@dataclass
class Report:
    path: str
    fields: list[str] | None


@dataclass
class Scope:
    files: list[str]
    trees: list[tuple[str, str]]
    derived: list[Derived]
    report: list[Report]


@dataclass
class Roots:
    wsl: Path
    windows: Path
    state: Path

    def side(self, name: str) -> Path:
        return self.wsl if name == "wsl" else self.windows


@dataclass
class Item:
    path: str
    kind: str  # file | derived | report
    action: str
    detail: str = ""
    texts: dict[str, str | None] = field(default_factory=dict)  # normalized text per side
    eols: dict[str, str] = field(default_factory=dict)
    final: str | None = None  # the content both sides hold once this item is applied
    source: str = ""  # derived items only


# --------------------------------------------------------------------------- io


def load_scope(path: Path) -> Scope:
    try:
        data = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise SyncError(f"cannot read scope file {path}: {exc}") from exc
    if data.get("schema_version") != 2:
        raise SyncError(f"{path}: schema_version must be 2")
    try:
        return Scope(
            files=list(data.get("files", [])),
            trees=[(t["path"], t.get("glob", "*.md")) for t in data.get("trees", [])],
            derived=[Derived(d["path"], d["from"]) for d in data.get("derived", [])],
            report=[Report(r["path"], r.get("fields")) for r in data.get("report", [])],
        )
    except (KeyError, TypeError) as exc:
        raise SyncError(f"{path}: malformed entry, missing {exc}") from exc


def _is_link(p: Path) -> bool:
    """True for a symlink, including a WSL symlink seen from Windows.

    Windows sees a WSL symlink under \\wsl.localhost as a reparse point
    (IO_REPARSE_TAG_LX_SYMLINK) that it can neither follow nor report through
    is_symlink(), so the reparse-point attribute is checked as well.
    """
    if p.is_symlink():
        return True
    try:
        st = os.lstat(p)
    except OSError:
        return False
    attrs = getattr(st, "st_file_attributes", 0)
    is_reparse = bool(attrs & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
    return is_reparse and getattr(st, "st_reparse_tag", IO_REPARSE_TAG_LX_SYMLINK) == IO_REPARSE_TAG_LX_SYMLINK


def read_text(p: Path) -> tuple[str | None, str]:
    """Return (normalized text or None if absent, line ending style)."""
    if not p.is_file():
        if _is_link(p):
            raise SyncError(f"{p} is a link this runtime cannot follow; run from the other side")
        return None, "\n"
    raw = p.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise SyncError(f"{p} is not UTF-8 text") from exc
    eol = "\r\n" if b"\r\n" in raw else "\n"
    return text.replace("\r\n", "\n").replace("\r", "\n"), eol


def baseline_path(roots: Roots, rel: str) -> Path:
    return roots.state / "sync" / rel


# ------------------------------------------------------------------------- plan


def _sync_paths(scope: Scope, roots: Roots) -> list[str]:
    paths = list(scope.files)
    for tree, pattern in scope.trees:
        found = set()
        for base in (roots.wsl / tree, roots.windows / tree, baseline_path(roots, tree)):
            if base.is_dir():
                found.update(f"{tree}/{p.relative_to(base).as_posix()}"
                             for p in base.glob(pattern) if p.is_file())
        paths.extend(sorted(found - set(paths)))
    return paths


def _classify(w: str | None, n: str | None, b: str | None) -> tuple[str, str, str | None]:
    """Three-way decision. Returns (action, detail, final text)."""
    if w == n:
        if w is None:
            return ("forget", "gone on both sides", None) if b is not None else ("skip", "", None)
        return ("ok", "", w) if b == w else ("record", "same on both sides; record baseline", w)
    if b is None:
        if w is None:
            return "to_wsl", "new on Windows", n
        if n is None:
            return "to_windows", "new on WSL", w
        return "conflict", "differ and no baseline yet", None
    w_changed, n_changed = w != b, n != b
    if w_changed and not n_changed:
        return ("delete_windows", "deleted on WSL", None) if w is None else ("to_windows", "changed on WSL", w)
    if n_changed and not w_changed:
        return ("delete_wsl", "deleted on Windows", None) if n is None else ("to_wsl", "changed on Windows", n)
    if w is None:
        return "conflict", "deleted on WSL, edited on Windows", None
    if n is None:
        return "conflict", "edited on WSL, deleted on Windows", None
    return "conflict", "changed on both sides", None


def _file_item(roots: Roots, rel: str) -> Item:
    w, w_eol = read_text(roots.wsl / rel)
    n, n_eol = read_text(roots.windows / rel)
    b, _ = read_text(baseline_path(roots, rel))
    action, detail, final = _classify(w, n, b)
    return Item(rel, "file", action, detail, {"wsl": w, "windows": n},
                {"wsl": w_eol, "windows": n_eol}, final)


def _derived_item(roots: Roots, d: Derived, canonical: str | None) -> Item:
    if canonical is None:
        return Item(d.path, "derived", "blocked", f"waits for {d.source} to sync", source=d.source)
    stale = []
    for side in SIDES:
        p = roots.side(side) / d.path
        if _is_link(p) or not p.parent.is_dir():
            continue  # a link follows its target; a missing CLI dir means the CLI is absent
        if read_text(p)[0] != canonical:
            stale.append(side)
    action = {0: "ok", 1: f"regen_{stale[0] if stale else ''}", 2: "regen_both"}[len(stale)]
    detail = f"regenerate from {d.source}" if stale else ""
    return Item(d.path, "derived", action, detail, final=canonical, source=d.source)


def _load_doc(p: Path) -> dict:
    raw = p.read_text(encoding="utf-8-sig")
    return tomllib.loads(raw) if p.suffix == ".toml" else json.loads(raw)


def _describe(name: str, a, b) -> str:
    if isinstance(a, dict) and isinstance(b, dict):
        keys = sorted(k for k in a.keys() | b.keys() if a.get(k) != b.get(k))
        return f"{name}: {', '.join(keys)}"
    if isinstance(a, list) and isinstance(b, list):
        return f"{name}: {len(a)} vs {len(b)} entries" if len(a) != len(b) else f"{name}: entries differ"
    if a is None or b is None:
        return f"{name}: only on {'Windows' if a is None else 'WSL'}"
    return f"{name}: value differs"


def _report_item(roots: Roots, r: Report) -> Item:
    if not any((roots.side(s) / r.path).is_file() for s in SIDES):
        return Item(r.path, "report", "ok", "absent on both sides")
    docs = {}
    for side in SIDES:
        p = roots.side(side) / r.path
        if not p.is_file():
            return Item(r.path, "report", "differs", f"missing on {side}")
        try:
            docs[side] = _load_doc(p)
        except (ValueError, tomllib.TOMLDecodeError):
            return Item(r.path, "report", "differs", f"cannot parse on {side}")
    w, n = docs["wsl"], docs["windows"]
    names = r.fields if r.fields is not None else sorted(w.keys() | n.keys())
    parts = [_describe(f, w.get(f), n.get(f)) for f in names if w.get(f) != n.get(f)]
    return Item(r.path, "report", "differs" if parts else "ok", "; ".join(parts))


def plan(scope: Scope, roots: Roots) -> list[Item]:
    items = [i for i in (_file_item(roots, rel) for rel in _sync_paths(scope, roots))
             if i.action != "skip"]
    finals = {i.path: i.final for i in items}
    for d in scope.derived:
        if d.source in finals:
            items.append(_derived_item(roots, d, finals[d.source]))
        else:  # source absent on both sides: nothing to derive from
            left = [s for s in SIDES if (roots.side(s) / d.path).is_file()
                    and not _is_link(roots.side(s) / d.path)]
            items.append(Item(d.path, "derived", "orphan" if left else "ok",
                              f"{d.source} is gone; remove the {'/'.join(left)} copy by hand"
                              if left else f"{d.source} absent", source=d.source))
    items += [_report_item(roots, r) for r in scope.report]
    return items


# ------------------------------------------------------------------------ apply


class _Writer:
    def __init__(self, roots: Roots):
        self.roots = roots
        self.backup = roots.state / "backups" / datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        self.done: list[str] = []

    def _backup(self, side: str, rel: str, p: Path) -> None:
        dest = self.backup / side / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(p.read_bytes())

    def write(self, side: str, rel: str, text: str, eol: str) -> None:
        p = self.roots.side(side) / rel
        if _is_link(p):
            raise SyncError(f"{side} {rel} is a symlink; refusing to write through it")
        try:
            if p.exists():
                eol = "\r\n" if b"\r\n" in p.read_bytes() else "\n"
                self._backup(side, rel, p)
            p.parent.mkdir(parents=True, exist_ok=True)
            tmp = p.with_name(p.name + ".acs-tmp")
            try:
                tmp.write_bytes(text.replace("\n", eol).encode("utf-8"))
                os.replace(tmp, p)
            finally:
                tmp.unlink(missing_ok=True)
        except OSError as exc:
            raise SyncError(f"cannot write {side} {rel}: {exc}") from exc
        self.done.append(f"wrote   {side:<7} {rel}")

    def delete(self, side: str, rel: str) -> None:
        p = self.roots.side(side) / rel
        if _is_link(p):
            raise SyncError(f"{side} {rel} is a symlink; refusing to delete it")
        try:
            self._backup(side, rel, p)
            p.unlink()
        except OSError as exc:
            raise SyncError(f"cannot delete {side} {rel}: {exc}") from exc
        self.done.append(f"deleted {side:<7} {rel}")

    def baseline(self, rel: str, text: str | None) -> None:
        p = baseline_path(self.roots, rel)
        if text is None:
            p.unlink(missing_ok=True)
        else:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(text.encode("utf-8"))


def _apply_file(wr: _Writer, item: Item, take: str | None) -> None:
    action, final = item.action, item.final
    if action == "conflict":
        if take is None:
            return
        other = "windows" if take == "wsl" else "wsl"
        final = item.texts[take]
        action = f"delete_{other}" if final is None else f"to_{other}"
    other_of = {"to_windows": "wsl", "to_wsl": "windows"}
    if action in other_of:
        dest = action.removeprefix("to_")
        assert final is not None
        wr.write(dest, item.path, final, item.eols[other_of[action]])
    elif action in ("delete_wsl", "delete_windows"):
        wr.delete(action.removeprefix("delete_"), item.path)
    elif action not in ("record", "forget"):
        return  # ok (baseline already current), or an unresolved conflict
    wr.baseline(item.path, final)


def apply(items: list[Item], roots: Roots, take: dict[str, str] | None = None,
          done: list[str] | None = None) -> list[str]:
    """Apply every non-conflict action (plus conflicts named in ``take``).

    ``done`` (if given) receives each completed write as it happens, so a caller
    can still report them when a later item raises SyncError.
    """
    take = take or {}
    wr = _Writer(roots)
    if done is not None:
        wr.done = done
    for item in items:
        if item.kind == "file":
            _apply_file(wr, item, take.get(item.path))
    for item in items:
        if item.kind != "derived":
            continue
        # Re-read the source: a file action or --take above may have changed it.
        texts = {s: read_text(roots.side(s) / item.source)[0] for s in SIDES}
        if texts["wsl"] is None or texts["wsl"] != texts["windows"]:
            continue
        for side in SIDES:
            p = roots.side(side) / item.path
            if _is_link(p) or not p.parent.is_dir():
                continue
            text, eol = read_text(p)
            if text != texts["wsl"]:
                wr.write(side, item.path, texts["wsl"], eol)
    return wr.done


# ------------------------------------------------------------------- detection


def _run(argv: list[str], **kw) -> str:
    try:
        out = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8",
                             errors="replace", timeout=60, check=True, **kw)
    except (OSError, subprocess.SubprocessError) as exc:
        raise SyncError(f"could not run {argv[0]}: {exc}") from exc
    return out.stdout.strip()


def detect_roots(wsl_home: str | None, windows_home: str | None, state: str | None) -> Roots:
    if os.name == "nt":
        win = Path(windows_home) if windows_home else Path.home()
        if wsl_home:
            wsl = Path(wsl_home)
        else:
            distro, home = _run(["wsl.exe", "-e", "sh", "-c",
                                 'printf "%s|%s" "$WSL_DISTRO_NAME" "$HOME"']).split("|", 1)
            wsl = Path(str(PureWindowsPath(rf"\\wsl.localhost\{distro}") / home.lstrip("/")))
    else:
        wsl = Path(wsl_home) if wsl_home else Path.home()
        if windows_home:
            win = Path(windows_home)
        else:
            profile = _run(["cmd.exe", "/c", "echo %USERPROFILE%"], cwd="/mnt/c")
            win = Path(_run(["wslpath", "-u", profile]))
    roots = Roots(wsl=wsl, windows=win, state=Path(state) if state else DEFAULT_STATE)
    for name in SIDES:
        if not roots.side(name).is_dir():
            raise SyncError(f"{name} home not found: {roots.side(name)}")
    return roots


# ------------------------------------------------------------------------- cli

ARROWS = {"to_windows": "-> windows", "to_wsl": "-> wsl", "delete_windows": "delete windows",
          "delete_wsl": "delete wsl", "regen_windows": "regen windows", "regen_wsl": "regen wsl",
          "regen_both": "regen both"}


def _print_plan(items: list[Item], roots: Roots) -> int:
    print(f"WSL:     {roots.wsl}\nWindows: {roots.windows}\n")
    shown = [i for i in items if i.action != "ok"]
    for i in shown:
        label = ARROWS.get(i.action, i.action)
        print(f"{label:<15} {i.path:<48} {i.detail}")
    ok = len(items) - len(shown)
    pending = [i for i in items if i.action in PENDING]
    conflicts = sum(i.action == "conflict" for i in items)
    blocked = sum(i.action == "blocked" for i in items)
    reports = sum(i.action == "differs" for i in items)
    print(f"\n{ok} in sync | {len(pending) - conflicts - blocked} to apply | {conflicts} conflicts"
          f" | {blocked} blocked | {reports} report-only differences")
    return 10 if pending else 0


def normalize_rel(rel: str) -> str:
    """Canonical home-relative POSIX spelling of a user-supplied path."""
    norm = posixpath.normpath(rel.replace("\\", "/"))
    if norm.startswith(("/", "../")) or norm in ("..", ".") or ":" in norm:
        raise SyncError(f"{rel}: give a path relative to the home directory")
    return norm


MAX_DELETES = 2


def _guard_deletes(items: list[Item], roots: Roots, scope: Scope) -> None:
    """Refuse an apply that looks like a wiped or mis-pointed home, not a deletion.

    A home that lost its files (profile reinstall, wrong --windows-home) makes
    every file read as "deleted on that side", and a plain apply would delete
    the other side's copies too. Backups exist, but this stops it first.
    """
    present = {s: any((roots.side(s) / f).is_file() for f in scope.files) for s in SIDES}
    for side in SIDES:
        if any(present.values()) and not present[side]:
            raise SyncError(f"{side} home has none of the core files ({roots.side(side)}); "
                            "wrong home or a wiped profile? Nothing applied")
        other = "windows" if side == "wsl" else "wsl"
        deletes = [i.path for i in items if i.action == f"delete_{other}"]
        if len(deletes) > MAX_DELETES:
            raise SyncError(f"{len(deletes)} files would be deleted on {other} because they are "
                            f"missing on {side}. Check {roots.side(side)}, then re-run with "
                            "--allow-deletes if that is intended. Nothing applied")


def _print_diff(roots: Roots, rel: str) -> None:
    w, _ = read_text(roots.wsl / rel)
    n, _ = read_text(roots.windows / rel)
    b, _ = read_text(baseline_path(roots, rel))

    def show(a, z, la, lz):
        sys.stdout.writelines(difflib.unified_diff(
            (a or "").splitlines(keepends=True), (z or "").splitlines(keepends=True), la, lz))

    if b is None:
        show(w, n, f"wsl/{rel}", f"windows/{rel}")
    else:
        show(b, w, f"baseline/{rel}", f"wsl/{rel}")
        show(b, n, f"baseline/{rel}", f"windows/{rel}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Two-way sync of agent instruction files between WSL and Windows.")
    ap.add_argument("command", nargs="?", default="check", choices=["check", "diff", "apply"])
    ap.add_argument("paths", nargs="*", help="limit to these relative paths")
    ap.add_argument("--take", choices=SIDES, help="resolve the named conflicts with this side")
    ap.add_argument("--allow-deletes", action="store_true",
                    help=f"permit more than {MAX_DELETES} deletes on one side in a single apply")
    ap.add_argument("--scope", default=str(DEFAULT_SCOPE))
    ap.add_argument("--wsl-home")
    ap.add_argument("--windows-home")
    ap.add_argument("--state", help=f"baseline + backups dir (default {DEFAULT_STATE})")
    args = ap.parse_intermixed_args(argv)
    for stream in (sys.stdout, sys.stderr):  # a cp1252 pipe on Windows must not crash on file text
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(errors="replace")
    try:
        scope = load_scope(Path(args.scope))
        roots = detect_roots(args.wsl_home, args.windows_home, args.state)
        if args.command == "diff":
            if not args.paths:
                raise SyncError("diff needs at least one path")
            allowed = set(_sync_paths(scope, roots)) | {d.path for d in scope.derived}
            for rel in map(normalize_rel, args.paths):
                if rel not in allowed:
                    raise SyncError(f"{rel} is not a synced instruction file; diff only shows those")
                _print_diff(roots, rel)
            return 0
        items = plan(scope, roots)
        if args.command == "check":
            return _print_plan(items, roots)
        args.paths = [normalize_rel(p) for p in args.paths]
        if args.take and not args.paths:
            raise SyncError("--take needs the conflict paths it resolves")
        # A derived copy follows its source, so selecting the source selects it too.
        known = {i.path for i in items}
        unknown = [p for p in args.paths if p not in known]
        if unknown:
            raise SyncError(f"no such in-scope item: {', '.join(unknown)}")
        selected = [i for i in items if not args.paths or i.path in args.paths
                    or (i.kind == "derived" and i.source in args.paths)]
        if not args.allow_deletes:
            _guard_deletes(selected, roots, scope)
        take = {p: args.take for p in args.paths} if args.take else None
        done: list[str] = []
        try:
            apply(selected, roots, take, done)
        finally:
            for line in done:
                print(line)
        print()
        return _print_plan(plan(scope, roots), roots)
    except SyncError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 20


if __name__ == "__main__":
    sys.exit(main())

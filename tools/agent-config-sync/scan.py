#!/usr/bin/env python3
"""Deterministic scan: no model is ever invoked from this module.

    scan.py --manifest config/agent-sync.toml [--out FILE] [--root k=v]...

Exit codes: 0 no drift, 10 drift reported, 20 scan failure, 21 lock held.

Design: "Deterministic scan", "Scheduling".
"""
from __future__ import annotations

import argparse
import contextlib
import fcntl
import json
import secrets as _secrets
import sys
from datetime import datetime, timezone
from pathlib import Path

import compare
import drift
import extract
import manifest as mf
import plugins as pl

EXIT_OK = 0
EXIT_DRIFT = 10
EXIT_SCAN_FAILURE = 20
EXIT_LOCKED = 21


class LockHeld(RuntimeError):
    """Another scan is already running."""


@contextlib.contextmanager
def acquire_lock(state_dir: Path):
    state_dir = Path(state_dir)
    state_dir.mkdir(parents=True, exist_ok=True)
    lock_path = state_dir / "scan.lock"
    handle = lock_path.open("w")
    try:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise LockHeld(f"another scan holds {lock_path}") from exc
        yield handle
    finally:
        with contextlib.suppress(OSError):
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


def run_scan(manifest_path, *, root_overrides, now: datetime,
             entropy: str) -> dict:
    m = mf.load_manifest(Path(manifest_path), root_overrides=root_overrides)

    units: list = []
    for entry in m.entries:
        for layer in extract.LAYERS:
            root = m.roots.for_layer(layer)
            units.extend(
                extract.extract_entry(entry, layer, root, m.secrets, m.roots))

    items = compare.compare_all(m, units)

    errors: list[dict] = []
    plugin_entries = [e for e in m.entries if e.kind == "plugins"]
    if plugin_entries:
        entry = plugin_entries[0]
        states: dict[str, dict] = {}
        for layer in extract.LAYERS:
            root = m.roots.for_layer(layer)
            rel = entry.rel_for_layer(layer)
            base = Path(root) / rel if (root and rel) else None
            state, layer_errors = pl.read_layer(base)
            states[layer] = state
            errors.extend({"path": f"{layer}:{entry.id}", "message": message}
                          for message in layer_errors)
        # has_windows must be threaded through: without it, an empty
        # windows_native is indistinguishable from an unconfigured Windows
        # root, and a machine with no Windows target would be told every
        # plugin it owns is missing. (Task 5 ruling, 2026-08-11.)
        items.extend(pl.classify_plugins(
            states["repo"], states["wsl"], states["windows"], m.pins,
            has_windows=m.roots.windows_home is not None))

    for item in items:
        if item.classification == "error":
            errors.append({"path": item.path, "message": item.detail})

    return drift.build_document(m, items, errors, now=now, entropy=entropy,
                                units=units)


def _parse_args(argv):
    parser = argparse.ArgumentParser(
        prog="scan.py", description="Deterministic agent-config drift scan.")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--out", type=Path,
                        help="drift document path "
                             "(default: <state-dir>/latest-drift.json)")
    parser.add_argument("--state-dir", type=Path)
    parser.add_argument("--root", action="append", default=[],
                        metavar="KEY=VALUE",
                        help="override a manifest root, e.g. wsl_home=/tmp/x")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = _parse_args(argv)
    overrides = {}
    for pair in args.root:
        key, _, value = pair.partition("=")
        if not value:
            print(f"scan: --root expects KEY=VALUE, got {pair!r}",
                  file=sys.stderr)
            return EXIT_SCAN_FAILURE
        overrides[key] = value

    try:
        loaded = mf.load_manifest(args.manifest, root_overrides=overrides)
    except mf.ManifestError as exc:
        print(f"scan: {exc}", file=sys.stderr)
        return EXIT_SCAN_FAILURE

    state_dir = args.state_dir or loaded.state_dir
    out = args.out or (state_dir / "latest-drift.json")
    now = datetime.now(timezone.utc)
    entropy = _secrets.token_hex(3)

    try:
        with acquire_lock(state_dir):
            doc = run_scan(args.manifest, root_overrides=overrides, now=now,
                           entropy=entropy)
            problems = drift.validate_document(doc)
            if problems:
                print("scan: drift document failed its own schema:",
                      file=sys.stderr)
                for problem in problems[:10]:
                    print(f"  {problem}", file=sys.stderr)
                return EXIT_SCAN_FAILURE
            drift.write_atomic(out, drift.dump(doc))
            code = EXIT_DRIFT if drift.has_actionable(doc) else EXIT_OK
            drift.write_atomic(state_dir / "latest-status.json", json.dumps({
                "run_id": doc["run_id"],
                "generated_at": doc["generated_at"],
                "scanner_version": doc["scanner_version"],
                "actionable": drift.has_actionable(doc),
                "counts": doc["counts"],
                "drift_document": str(out),
                "exit_code": code,
            }, indent=2, sort_keys=True) + "\n")
            return code
    except LockHeld as exc:
        print(f"scan: {exc}", file=sys.stderr)
        return EXIT_LOCKED
    except (mf.ManifestError, OSError) as exc:
        print(f"scan: {type(exc).__name__}: {exc}", file=sys.stderr)
        return EXIT_SCAN_FAILURE


if __name__ == "__main__":
    raise SystemExit(main())

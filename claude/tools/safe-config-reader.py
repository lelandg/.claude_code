#!/usr/bin/env python3
"""Secret-safe reader for config files (.yaml/.yml, .env, .ini-ish).

Prints the STRUCTURE of a config file — keys, types, and non-sensitive
scalars — while masking every string value. Built after a 2026-07-13
incident where printing line ranges of a config.yaml leaked API keys and
a database password into an agent conversation transcript.

Policy (deliberately strict, no overrides):
  - booleans, numbers, and null are shown (they're what debugging needs)
  - EVERY string is masked and shown as <str:N> (its length) — no
    allowlists, no --reveal flag; if an agent needs a string value, a
    human types it
  - lists/dicts are recursed; list items numbered

Usage:
  safe-config-reader.py <file> [<file>...]
  safe-config-reader.py --key llm.enable_context_intelligence <file>

Exit codes: 0 ok, 1 usage/parse error, 2 file missing.
"""
from __future__ import annotations

import sys


def _mask(value):
    if isinstance(value, bool) or value is None or isinstance(value, (int, float)):
        return repr(value) if value is not None else "null"
    if isinstance(value, str):
        return f"<str:{len(value)}>"
    return f"<{type(value).__name__}>"


def _walk(node, prefix, out):
    if isinstance(node, dict):
        for k, v in node.items():
            path = f"{prefix}{k}"
            if isinstance(v, (dict, list)):
                _walk(v, path + ".", out)
            else:
                out.append((path, _mask(v)))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            path = f"{prefix}{i}"
            if isinstance(v, (dict, list)):
                _walk(v, path + ".", out)
            else:
                out.append((path, _mask(v)))
    else:
        out.append((prefix.rstrip("."), _mask(node)))


def _load(path):
    if path.endswith((".yaml", ".yml")):
        try:
            import yaml
        except ImportError:
            print("PyYAML not available; refusing to parse YAML by hand", file=sys.stderr)
            raise SystemExit(1)
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    # .env / KEY=VALUE style: return names only (values never parsed further)
    data = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, _, value = line.partition("=")
            data[name.strip()] = value.strip().strip("'\"")
    return data


def main(argv):
    args = list(argv[1:])
    want_key = None
    if args[:1] == ["--key"]:
        if len(args) < 3:
            print(__doc__, file=sys.stderr)
            return 1
        want_key = args[1]
        args = args[2:]
    if not args:
        print(__doc__, file=sys.stderr)
        return 1
    for path in args:
        try:
            data = _load(path)
        except FileNotFoundError:
            print(f"{path}: not found", file=sys.stderr)
            return 2
        except Exception as e:  # parse error — never print file content
            print(f"{path}: parse error ({type(e).__name__})", file=sys.stderr)
            return 1
        rows: list[tuple[str, str]] = []
        _walk(data, "", rows)
        if want_key is not None:
            hits = [(k, v) for k, v in rows if k == want_key or k.startswith(want_key + ".")]
            if not hits:
                print(f"{path}: key {want_key!r} not found")
            for k, v in hits:
                print(f"{k}: {v}")
            continue
        print(f"# {path} — {len(rows)} keys (strings masked)")
        for k, v in rows:
            print(f"{k}: {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

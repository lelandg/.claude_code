#!/usr/bin/env python3
"""Allowlist extraction with a hard secret boundary.

The rule (design, "Secret and state boundary"): collect only what the manifest
declares. Denied paths are never opened. Denied keys never have their values
placed in a variable that reaches an output -- only a type and a hash.

Design: "Deterministic scan" step 4.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

import normalize as nz

REDACTED = "<redacted>"

LAYERS = ("wsl", "repo", "windows")


@dataclass(frozen=True)
class Redaction:
    pointer: str
    reason: str
    value_type: str
    value_fingerprint: str

    def as_dict(self) -> dict[str, str]:
        return {"pointer": self.pointer, "reason": self.reason,
                "value_type": self.value_type,
                "value_fingerprint": self.value_fingerprint}


@dataclass(frozen=True)
class Unit:
    """One comparable thing in one layer.

    key: "" for a whole-file entry, a relative path for a tree entry, a dotted
    pointer for a json/toml field entry.
    """
    entry_id: str
    layer: str
    key: str
    path: str
    kind: str
    policy: str | None = None
    normalized: str | None = None
    fingerprint: str | None = None
    redactions: tuple[Redaction, ...] = ()
    portability: tuple[str, ...] = ()
    error: str | None = None

    @property
    def unit_id(self) -> str:
        return f"{self.entry_id}:{self.key}" if self.key else self.entry_id


# --------------------------------------------------------------------------
# path globs
# --------------------------------------------------------------------------

def glob_to_regex(pattern: str) -> re.Pattern[str]:
    """'*' stops at '/', '**' crosses it. Trailing '/**' also matches the dir."""
    out = []
    index = 0
    while index < len(pattern):
        char = pattern[index]
        if pattern.startswith("**/", index):
            out.append("(?:.*/)?")
            index += 3
        elif pattern.startswith("**", index):
            out.append(".*")
            index += 2
        elif char == "*":
            out.append("[^/]*")
            index += 1
        elif char == "?":
            out.append("[^/]")
            index += 1
        else:
            out.append(re.escape(char))
            index += 1
    return re.compile("^" + "".join(out) + "$")


def is_denied(rel: str, globs) -> bool:
    return any(glob_to_regex(pattern).match(rel) for pattern in globs)


# --------------------------------------------------------------------------
# redaction
# --------------------------------------------------------------------------

def _is_secret_key(key: str, secrets) -> bool:
    return any(re.search(pattern, key) for pattern in secrets.deny_key_patterns)


def redact_tree(data, secrets, *, pointer: str = "") -> tuple[object, list[Redaction]]:
    """Return a copy with secret-valued keys replaced, plus the redaction log."""
    redactions: list[Redaction] = []

    if isinstance(data, dict):
        cleaned: dict = {}
        for key, value in data.items():
            child = f"{pointer}.{key}" if pointer else str(key)
            if _is_secret_key(str(key), secrets):
                cleaned[key] = REDACTED
                redactions.append(Redaction(
                    pointer=child,
                    reason="secret_key_pattern",
                    value_type=type(value).__name__,
                    value_fingerprint=nz.fingerprint(repr(value)),
                ))
                continue
            sub, sub_redactions = redact_tree(value, secrets, pointer=child)
            cleaned[key] = sub
            redactions.extend(sub_redactions)
        return cleaned, redactions

    if isinstance(data, list):
        cleaned_list = []
        for index, value in enumerate(data):
            sub, sub_redactions = redact_tree(
                value, secrets, pointer=f"{pointer}[{index}]")
            cleaned_list.append(sub)
            redactions.extend(sub_redactions)
        return cleaned_list, redactions

    return data, redactions


# --------------------------------------------------------------------------
# extraction
# --------------------------------------------------------------------------

def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _display(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _unit_for_file(entry, layer, root, path, key, roots,
                   kind: str, policy: str | None) -> Unit:
    # Explicit keyword arguments, not an untyped dict splat (fix round 1,
    # Finding 3): a dict()-then-**common merges every field into one union
    # value type, which defeats per-field type checking on the Unit call.
    entry_id: str = entry.id
    display = _display(root, path)
    if not path.exists():
        return Unit(entry_id=entry_id, layer=layer, key=key, path=display,
                    kind=kind, policy=policy)
    try:
        raw = _read(path)
    except (UnicodeDecodeError, OSError) as exc:
        return Unit(entry_id=entry_id, layer=layer, key=key, path=display,
                    kind=kind, policy=policy,
                    error=f"unreadable: {type(exc).__name__}")
    try:
        text = nz.normalize_for_kind(raw, kind if kind in ("json", "toml") else "text")
    except nz.NormalizeError as exc:
        return Unit(entry_id=entry_id, layer=layer, key=key, path=display,
                    kind=kind, policy=policy, error=str(exc))
    text = nz.tokenize_paths(text, roots)
    return Unit(entry_id=entry_id, layer=layer, key=key, path=display,
               kind=kind, policy=policy, normalized=text,
               fingerprint=nz.fingerprint(text),
               portability=tuple(nz.portability_warnings(text)))


def _flatten_pointers(data, prefix: str = "") -> list[tuple[str, object]]:
    """Every dict pointer, parents before children."""
    out: list[tuple[str, object]] = []
    if isinstance(data, dict):
        for key, value in data.items():
            child = f"{prefix}.{key}" if prefix else str(key)
            out.append((child, value))
            out.extend(_flatten_pointers(value, child))
    return out


def _redactions_under(pointer: str, redactions) -> tuple[Redaction, ...]:
    """Redactions for exactly this pointer or a genuine descendant of it.

    A plain str.startswith(pointer) has no path boundary and would treat a
    sibling like "envFoo.token" as a descendant of "env" merely because the
    strings share a prefix (fix round 1, Finding 1). Requiring the next
    character to be "." (a dict child) or "[" (a list index) rules that out.
    """
    return tuple(r for r in redactions
                if r.pointer == pointer
                or r.pointer.startswith(pointer + ".")
                or r.pointer.startswith(pointer + "["))


def _extract_structured(entry, layer, root, path, secrets, roots) -> list[Unit]:
    # Explicit keyword arguments, not an untyped dict splat (fix round 1,
    # Finding 3): see the matching note in _unit_for_file.
    kind = entry.kind
    entry_id: str = entry.id
    display = _display(root, path)
    unit_kind = f"{kind}_field"
    if not path.exists():
        return [Unit(entry_id=entry_id, layer=layer, key="", path=display,
                     kind=unit_kind, policy=entry.policy)]
    try:
        raw = _read(path)
        canonical = nz.normalize_for_kind(raw, kind)
    except nz.NormalizeError as exc:
        return [Unit(entry_id=entry_id, layer=layer, key="", path=display,
                     kind=unit_kind, policy=entry.policy, error=str(exc))]
    except (UnicodeDecodeError, OSError) as exc:
        return [Unit(entry_id=entry_id, layer=layer, key="", path=display,
                     kind=unit_kind, policy=entry.policy,
                     error=f"unreadable: {type(exc).__name__}")]

    data = json.loads(canonical)
    data, redactions = redact_tree(data, secrets)

    if not entry.fields:
        text = nz.tokenize_paths(nz.normalize_json(json.dumps(data)), roots)
        return [Unit(entry_id=entry_id, layer=layer, key="", path=display,
                     kind=unit_kind, policy=entry.policy, normalized=text,
                     fingerprint=nz.fingerprint(text),
                     redactions=tuple(redactions),
                     portability=tuple(nz.portability_warnings(text)))]

    units: list[Unit] = []
    covered: set[str] = set()
    pointers = _flatten_pointers(data)
    for pointer, value in pointers:
        policy = entry.policy_for(pointer)
        if policy is None:
            continue
        if policy == "excluded":
            covered.add(pointer.split(".")[0])
            continue
        # Skip a parent when a declared child pattern will emit it instead.
        if any(pointer_is_ancestor(pointer, other)
               for other, _ in pointers
               if other != pointer and entry.policy_for(other) is not None):
            continue
        text = nz.tokenize_paths(
            nz.normalize_json(json.dumps(value)), roots)
        units.append(Unit(
            entry_id=entry_id, layer=layer, key=pointer, path=display,
            kind=unit_kind, policy=policy, normalized=text,
            fingerprint=nz.fingerprint(text),
            redactions=_redactions_under(pointer, redactions),
            portability=tuple(nz.portability_warnings(text))))
        covered.add(pointer.split(".")[0])

    # Undeclared top-level keys: metadata only (design, "Unknown content").
    for key, value in (data.items() if isinstance(data, dict) else []):
        if key in covered:
            continue
        text = nz.normalize_json(json.dumps(value))
        units.append(Unit(entry_id=entry_id, layer=layer, key=str(key),
                          path=display, kind=unit_kind, policy=None,
                          normalized=None, fingerprint=nz.fingerprint(text)))
    return units


def pointer_is_ancestor(ancestor: str, descendant: str) -> bool:
    return descendant.startswith(ancestor + ".")


def extract_entry(entry, layer: str, root: Path | None, secrets, roots) -> list[Unit]:
    """All comparable units for one manifest entry in one layer."""
    if root is None or entry.policy == "excluded" or entry.kind == "plugins":
        return []
    rel = entry.rel_for_layer(layer)
    if rel is None:
        return []
    target = Path(root) / rel

    if entry.kind == "tree":
        if not target.is_dir():
            return []
        units: list[Unit] = []
        for path in sorted(target.rglob("*")):
            if not path.is_file():
                continue
            key = str(path.relative_to(target))
            if is_denied(key, secrets.deny_path_globs) or is_denied(
                    str(path.relative_to(root)), secrets.deny_path_globs):
                continue
            if entry.globs and not any(
                    glob_to_regex(g).match(key) for g in entry.globs):
                continue
            units.append(_unit_for_file(entry, layer, root, path, key,
                                        roots, "text", entry.policy))
        return units

    if is_denied(rel, secrets.deny_path_globs):
        return []

    if entry.kind in ("json", "toml"):
        return _extract_structured(entry, layer, root, target, secrets, roots)

    return [_unit_for_file(entry, layer, root, target, "", roots,
                           "text", entry.policy)]

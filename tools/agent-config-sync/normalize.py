#!/usr/bin/env python3
"""Normalization, path tokenization, and fingerprints.

Two layers can express the same intent with different bytes (CRLF vs LF, JSON
key order, /home/leland vs C:\\Users\\aboog). Everything here exists so that
"same intent" is mechanically decidable before anything is called drift.

Design: "Deterministic scan" steps 5-6.
"""
from __future__ import annotations

import hashlib
import json
import re
import tomllib
from datetime import date, datetime, time
from pathlib import Path

TOKEN_HOME = "{HOME}"
TOKEN_REPO = "{REPO}"

# Absolute-path shapes that cannot survive a move between environments.
_NON_PORTABLE = (
    ("/mnt/", "a WSL mount path"),
    ("/usr/", "a Linux system path"),
    ("/home/", "a Linux home path"),
    ("/opt/", "a Linux system path"),
    ("\\\\wsl$", "a WSL UNC path"),
    (".venv_linux", "a Linux-only virtualenv"),
)

# Characters that may follow a matched root prefix and still be part of a path.
_PATH_TAIL = r"[\w./\\+@~%-]*"


class NormalizeError(ValueError):
    """Input could not be parsed. Message carries a location, never content."""


# --------------------------------------------------------------------------
# text / json / toml
# --------------------------------------------------------------------------

def normalize_text(raw: str) -> str:
    text = raw.lstrip("\ufeff")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in text.split("\n")]
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines) + "\n" if lines else "\n"


def _canonical_json(data: object) -> str:
    def default(value: object) -> str:
        if isinstance(value, (datetime, date, time)):
            return value.isoformat()
        raise TypeError(f"unserializable type {type(value).__name__}")

    return json.dumps(data, sort_keys=True, indent=2,
                      ensure_ascii=False, default=default) + "\n"


def normalize_json(raw: str) -> str:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise NormalizeError(
            f"invalid JSON at line {exc.lineno}, column {exc.colno}") from None
    return _canonical_json(data)


def normalize_toml(raw: str) -> str:
    try:
        data = tomllib.loads(raw)
    except tomllib.TOMLDecodeError as exc:
        line = getattr(exc, "lineno", None)
        where = f" at line {line}" if line else ""
        raise NormalizeError(f"invalid TOML{where}") from None
    return _canonical_json(data)


def normalize_for_kind(raw: str, kind: str) -> str:
    if kind == "json":
        return normalize_json(raw)
    if kind == "toml":
        return normalize_toml(raw)
    return normalize_text(raw)


# --------------------------------------------------------------------------
# path tokenization
# --------------------------------------------------------------------------

def wsl_mount_to_windows(path: Path) -> str | None:
    """/mnt/c/Users/aboog -> C:\\Users\\aboog. None if not a /mnt/<drive> path."""
    parts = Path(path).parts
    if len(parts) >= 3 and parts[0] == "/" and parts[1] == "mnt" and len(parts[2]) == 1:
        drive = parts[2].upper()
        tail = "\\".join(parts[3:])
        return f"{drive}:\\{tail}" if tail else f"{drive}:\\"
    return None


def _spellings(path: Path | None) -> list[str]:
    """Every way a root path can legitimately appear in a config file."""
    if path is None:
        return []
    out = [str(path)]
    windows = wsl_mount_to_windows(path)
    if windows:
        out.append(windows)
        out.append(windows.replace("\\", "/"))
    return out


def _replace_prefix(text: str, prefixes: list[str], token: str) -> str:
    for prefix in sorted(prefixes, key=len, reverse=True):
        pattern = re.compile(re.escape(prefix) + f"(?P<rest>{_PATH_TAIL})")
        text = pattern.sub(
            lambda m: token + m.group("rest").replace("\\", "/"), text)
    return text


def tokenize_paths(text: str, roots) -> str:
    """Replace layer roots with {HOME}/{REPO}. Longest prefix wins."""
    # Repo first: it usually lives under a mount that no other root claims,
    # but ordering by length guards against any future nesting.
    text = _replace_prefix(text, _spellings(roots.repo), TOKEN_REPO)
    homes = _spellings(roots.windows_home) + _spellings(roots.wsl_home)
    return _replace_prefix(text, homes, TOKEN_HOME)


def render_paths(text: str, layer: str, roots) -> str:
    """Replace {HOME}/{REPO} with the native spelling for one layer.

    The repository baseline is rendered in the WSL spelling: the repo is a
    mirror of WSL intent, so publishing round-trips to the same bytes the
    authority holds. Only the windows layer gets drive letters and backslashes.
    """
    if layer == "windows":
        # Fall back to the plain path when the root is not a /mnt/<drive> mount
        # (fixture trees in tests, or a target reached another way).
        home = ((wsl_mount_to_windows(roots.windows_home)
                 or str(roots.windows_home)) if roots.windows_home else None)
        repo = wsl_mount_to_windows(roots.repo) or str(roots.repo)
        out = text
        for token, native in ((TOKEN_HOME, home), (TOKEN_REPO, repo)):
            if native is None:
                continue
            pattern = re.compile(re.escape(token) + f"(?P<rest>{_PATH_TAIL})")
            out = pattern.sub(
                lambda m, n=native: n + m.group("rest").replace("/", "\\"), out)
        return out

    home = (roots.wsl_home if layer in ("wsl", "repo")
            else (roots.windows_home or roots.wsl_home))
    return text.replace(TOKEN_HOME, str(home)).replace(TOKEN_REPO, str(roots.repo))


def portability_warnings(text: str) -> list[str]:
    """Absolute literals that survived tokenization and will not travel."""
    return [f"contains {label}: {needle}"
            for needle, label in _NON_PORTABLE if needle in text]


# --------------------------------------------------------------------------
# fingerprints
# --------------------------------------------------------------------------

def fingerprint(normalized: str) -> str:
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def short(fp: str | None) -> str:
    return fp[:12] if fp else "-"

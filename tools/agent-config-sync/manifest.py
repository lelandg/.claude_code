#!/usr/bin/env python3
"""Ownership manifest: the single place roots, paths, and policies are declared.

Path literals live here and in config/agent-sync.toml -- never spread through
the implementation (design section "Paths").
"""
from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

MANIFEST_SCHEMA_VERSION = 1

POLICIES = (
    "portable_authoritative",
    "portable_additive",
    "platform_overlay",
    "excluded",
)
KINDS = ("text", "tree", "json", "toml", "plugins")


def _pointer_regex(pattern: str) -> re.Pattern[str]:
    parts = []
    for segment in pattern.split("."):
        if segment == "**":
            parts.append(r"[^.]+(?:\.[^.]+)*")
        elif segment == "*":
            parts.append(r"[^.]+")
        else:
            parts.append(re.escape(segment))
    return re.compile("^" + r"\.".join(parts) + "$")


def pointer_match(pattern: str, pointer: str) -> bool:
    """Dotted-pointer glob: '*' matches one segment, '**' matches one or more."""
    return bool(_pointer_regex(pattern).match(pointer))


def _specificity(pattern: str) -> tuple[int, int]:
    """More literal segments and fewer wildcards wins."""
    segments = pattern.split(".")
    wildcards = sum(1 for s in segments if s in ("*", "**"))
    return (len(segments) - wildcards, -wildcards)


class ManifestError(ValueError):
    """Manifest is missing, malformed, or declares something unsupported."""


@dataclass(frozen=True)
class Roots:
    wsl_home: Path
    repo: Path
    windows_home: Path | None = None

    def for_layer(self, layer: str) -> Path | None:
        return {"wsl": self.wsl_home, "repo": self.repo,
                "windows": self.windows_home}[layer]


@dataclass(frozen=True)
class Entry:
    id: str
    policy: str
    kind: str
    wsl: str | None = None
    repo: str | None = None
    windows: str | None = None
    globs: tuple[str, ...] = ()
    fields: dict[str, str] = field(default_factory=dict)

    def rel_for_layer(self, layer: str) -> str | None:
        return {"wsl": self.wsl, "repo": self.repo, "windows": self.windows}[layer]

    def policy_for(self, pointer: str) -> str | None:
        """Field-level policy, most specific pattern first.

        Returns None for a field that no pattern covers -- an undeclared field,
        which the design says to report as metadata only.
        """
        if not self.fields:
            return self.policy
        matches = [(pat, pol) for pat, pol in self.fields.items()
                   if pointer_match(pat, pointer)]
        if not matches:
            return None
        matches.sort(key=lambda pair: _specificity(pair[0]), reverse=True)
        return matches[0][1]


@dataclass(frozen=True)
class SecretPolicy:
    deny_key_patterns: tuple[str, ...] = ()
    deny_path_globs: tuple[str, ...] = ()


@dataclass(frozen=True)
class Manifest:
    schema_version: int
    roots: Roots
    state_dir: Path
    entries: tuple[Entry, ...]
    secrets: SecretPolicy

    def entry(self, entry_id: str) -> Entry:
        for candidate in self.entries:
            if candidate.id == entry_id:
                return candidate
        raise ManifestError(f"no entry with id {entry_id!r}")


def _expand(value: str) -> Path:
    return Path(value).expanduser()


def load_manifest(path: Path,
                  *,
                  root_overrides: dict[str, str] | None = None) -> Manifest:
    """Load and validate the manifest. Errors name the file, never its bytes."""
    path = Path(path)
    try:
        with path.open("rb") as handle:
            data = tomllib.load(handle)
    except FileNotFoundError as exc:
        raise ManifestError(f"{path.name}: manifest not found at {path}") from exc
    except tomllib.TOMLDecodeError as exc:
        # exc carries a line/column in its string repr, not as attributes.
        # Extract only the location (digits) to ensure no source fragment rides along.
        match = re.search(r"at line (\d+), column (\d+)", str(exc))
        where = (f" at line {match.group(1)}, column {match.group(2)}"
                 if match else "")
        raise ManifestError(f"{path.name}: invalid TOML{where}") from None

    version = data.get("schema_version")
    if version != MANIFEST_SCHEMA_VERSION:
        raise ManifestError(
            f"{path.name}: schema_version {version!r}; "
            f"this tool supports {MANIFEST_SCHEMA_VERSION}")

    raw_roots = dict(data.get("roots", {}))
    raw_roots.update(root_overrides or {})
    for required in ("wsl_home", "repo"):
        if not raw_roots.get(required):
            raise ManifestError(f"{path.name}: roots.{required} is required")
    windows = raw_roots.get("windows_home")
    roots = Roots(
        wsl_home=_expand(raw_roots["wsl_home"]),
        repo=_expand(raw_roots["repo"]),
        windows_home=_expand(windows) if windows else None,
    )

    raw_state = data.get("state", {})
    if not raw_state.get("dir"):
        raise ManifestError(f"{path.name}: state.dir is required")
    state_dir = _expand(raw_state["dir"])

    raw_secrets = data.get("secrets", {})
    secrets = SecretPolicy(
        deny_key_patterns=tuple(raw_secrets.get("deny_key_patterns", [])),
        deny_path_globs=tuple(raw_secrets.get("deny_path_globs", [])),
    )

    entries: list[Entry] = []
    seen: set[str] = set()
    for raw in data.get("entries", []):
        entry_id = raw.get("id")
        if not entry_id:
            raise ManifestError(f"{path.name}: an entry is missing 'id'")
        if entry_id in seen:
            raise ManifestError(f"{path.name}: duplicate entry id {entry_id!r}")
        seen.add(entry_id)
        policy = raw.get("policy")
        if policy not in POLICIES:
            raise ManifestError(
                f"{path.name}: entry {entry_id!r} has unknown policy {policy!r}; "
                f"expected one of {list(POLICIES)}")
        kind = raw.get("kind")
        if kind not in KINDS:
            raise ManifestError(
                f"{path.name}: entry {entry_id!r} has unknown kind {kind!r}; "
                f"expected one of {list(KINDS)}")
        fields = dict(raw.get("fields", {}))
        for field_pointer, field_policy in fields.items():
            if field_policy not in POLICIES:
                raise ManifestError(
                    f"{path.name}: entry {entry_id!r} field {field_pointer!r} "
                    f"has unknown policy {field_policy!r}; "
                    f"expected one of {list(POLICIES)}")
        entries.append(Entry(
            id=entry_id,
            policy=policy,
            kind=kind,
            wsl=raw.get("wsl"),
            repo=raw.get("repo"),
            windows=raw.get("windows"),
            globs=tuple(raw.get("globs", [])),
            fields=fields,
        ))

    if not entries:
        raise ManifestError(f"{path.name}: no [[entries]] declared")

    return Manifest(
        schema_version=version,
        roots=roots,
        state_dir=state_dir,
        entries=tuple(entries),
        secrets=secrets,
    )

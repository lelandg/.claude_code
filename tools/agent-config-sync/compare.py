#!/usr/bin/env python3
"""Three-way comparison: WSL authority, repository baseline, Windows target.

Pure functions over fingerprints. No filesystem, no clock, no model.

Design: "Authority model".
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

import extract as ex

SEVERITY_BY_CLASSIFICATION = {
    "unchanged": "info",
    "publish_to_repo": "review",
    "reconcile_windows": "review",
    "conflict": "conflict",
    "wsl_only": "review",
    "windows_only": "review",
    "protected_overlay": "info",
    "additive_delete_requires_approval": "review",
    "error": "error",
}

#: Classifications that mean a report is worth generating at all.
ACTIONABLE = frozenset({
    "publish_to_repo", "reconcile_windows", "conflict", "wsl_only",
    "windows_only", "additive_delete_requires_approval",
    "plugin_missing", "plugin_enabled_differs", "plugin_version_differs",
    "plugin_pin_violation", "plugin_incompatible", "error",
})


@dataclass(frozen=True)
class DriftItem:
    id: str
    entry_id: str
    kind: str
    classification: str
    severity: str
    path: str
    policy: str | None
    detail: str
    wsl_fingerprint: str | None = None
    repo_fingerprint: str | None = None
    windows_fingerprint: str | None = None
    redactions: tuple = ()

    def as_dict(self) -> dict:
        data = {
            "id": self.id,
            "entry_id": self.entry_id,
            "kind": self.kind,
            "classification": self.classification,
            "severity": self.severity,
            "path": self.path,
            "policy": self.policy or "undeclared",
            "detail": self.detail,
        }
        for name, value in (("wsl_fingerprint", self.wsl_fingerprint),
                            ("repo_fingerprint", self.repo_fingerprint),
                            ("windows_fingerprint", self.windows_fingerprint)):
            if value:
                data[name] = value
        return data


def classify(wsl: str | None, repo: str | None, windows: str | None,
             policy: str | None, *, has_windows: bool) -> tuple[str, str, str]:
    """Return (classification, severity, detail) for one comparable unit."""
    if policy == "platform_overlay":
        return ("protected_overlay", "info",
                "Windows owns this value; preserved and reported only.")

    if not has_windows:
        windows = None

    if policy is None:
        present = [fp for fp in (wsl, repo, windows) if fp]
        if len(set(present)) <= 1:
            return ("unchanged", "info", "Ownership undeclared; layers agree.")
        return ("conflict", "conflict",
                "Ownership undeclared and layers differ. Declare a policy for "
                "this field in config/agent-sync.toml before merging.")

    # 2-layer comparison when Windows is not being tracked.
    if not has_windows:
        if repo is None:
            if wsl:
                return ("wsl_only", "review",
                        "Present in WSL only; a new portable item.")
            return ("unchanged", "info", "Absent everywhere.")

        if wsl is None:
            if policy == "portable_additive":
                return ("additive_delete_requires_approval", "review",
                        "Removed in WSL. This item is portable-additive, so the "
                        "deletion is never applied without explicit approval.")
            return ("publish_to_repo", "review",
                    "Removed in WSL. Publishing records the deletion in the "
                    "baseline; review it as a deletion, not an update.")

        if wsl == repo:
            return ("unchanged", "info", "All layers agree.")

        return ("publish_to_repo", "review",
                "WSL intent is ahead of the baseline; publish it.")

    # 3-layer comparison when Windows is being tracked.
    # No baseline in the repository.
    if repo is None:
        if wsl and windows:
            if wsl == windows:
                return ("publish_to_repo", "review",
                        "No baseline recorded; WSL and Windows agree. "
                        "Publishing captures the initial baseline.")
            return ("conflict", "conflict",
                    "No baseline recorded and WSL and Windows differ; "
                    "there is nothing to arbitrate against. Requires judgment.")
        if wsl:
            return ("wsl_only", "review",
                    "Present in WSL only; a new portable item.")
        if windows:
            return ("windows_only", "review",
                    "Present on Windows only; ownership is not declared.")
        return ("unchanged", "info", "Absent everywhere.")

    # Removed from WSL.
    if wsl is None:
        if policy == "portable_additive":
            return ("additive_delete_requires_approval", "review",
                    "Removed in WSL. This item is portable-additive, so the "
                    "deletion is never applied without explicit approval.")
        return ("publish_to_repo", "review",
                "Removed in WSL. Publishing records the deletion in the "
                "baseline; review it as a deletion, not an update.")

    if wsl == repo == windows:
        return ("unchanged", "info", "All layers agree.")

    if wsl != repo and repo == windows:
        return ("publish_to_repo", "review",
                "WSL intent is ahead of the baseline; publish it.")

    if wsl == repo and repo != windows:
        return ("reconcile_windows", "review",
                "Baseline and Windows differ; Windows may need reconciliation.")

    if wsl == windows:
        return ("publish_to_repo", "review",
                "WSL and Windows agree; the baseline is stale. "
                "Publishing brings the record forward without choosing a winner.")

    return ("conflict", "conflict",
            "WSL and Windows changed independently of the baseline. "
            "No winner is chosen automatically; this requires judgment.")


def _item_kind(entry, unit_kind: str) -> str:
    if entry.kind == "tree":
        return "tree_file"
    if entry.kind in ("json", "toml"):
        return f"{entry.kind}_field"
    return unit_kind


def compare_entry(entry, units: list[ex.Unit], *, has_windows: bool) -> list[DriftItem]:
    """Join one entry's units across layers and classify each key."""
    index: dict[str, dict[str, ex.Unit]] = {}
    for unit in units:
        index.setdefault(unit.key, {})[unit.layer] = unit

    items: list[DriftItem] = []
    for key in sorted(index):
        by_layer = index[key]
        wsl: ex.Unit | None = by_layer.get("wsl")
        repo: ex.Unit | None = by_layer.get("repo")
        windows: ex.Unit | None = by_layer.get("windows")
        present = [u for u in (wsl, repo, windows) if u is not None]
        first = present[0]
        item_id = f"{entry.id}:{key}" if key else entry.id
        path = next((u.path for u in (wsl, repo, windows) if u), "")
        kind = _item_kind(entry, first.kind)

        errored = [u for u in present if u.error]
        if errored:
            items.append(DriftItem(
                id=item_id, entry_id=entry.id, kind=kind,
                classification="error", severity="error",
                path=errored[0].path, policy=first.policy,
                detail=f"{errored[0].layer}: {errored[0].error}"))
            continue

        policy = next((u.policy for u in present if u.policy is not None), None)
        classification, severity, detail = classify(
            wsl.fingerprint if wsl else None,
            repo.fingerprint if repo else None,
            windows.fingerprint if windows else None,
            policy, has_windows=has_windows)

        redactions: tuple = ()
        for unit in present:
            if unit.redactions:
                redactions = tuple(unit.redactions)
                break

        items.append(DriftItem(
            id=item_id, entry_id=entry.id, kind=kind,
            classification=classification, severity=severity,
            path=path, policy=policy, detail=detail,
            wsl_fingerprint=wsl.fingerprint if wsl else None,
            repo_fingerprint=repo.fingerprint if repo else None,
            windows_fingerprint=windows.fingerprint if windows else None,
            redactions=redactions))
    return items


def compare_all(manifest, units) -> list[DriftItem]:
    """Compare every non-plugin entry. Plugins are classified by plugins.py."""
    has_windows = manifest.roots.windows_home is not None
    by_entry: dict[str, list] = {}
    for unit in units:
        by_entry.setdefault(unit.entry_id, []).append(unit)

    items: list[DriftItem] = []
    for entry in manifest.entries:
        if entry.policy == "excluded" or entry.kind == "plugins":
            continue
        items.extend(compare_entry(entry, by_entry.get(entry.id, []),
                                   has_windows=has_windows))
    return items


def counts(items) -> dict[str, int]:
    return dict(Counter(item.classification for item in items))

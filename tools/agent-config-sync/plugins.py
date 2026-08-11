#!/usr/bin/env python3
"""Plugin identity, enabled state, version, and pin classification.

Plugin caches and downloaded plugin code are never read or copied. Only the
declarative surface is compared:

  <base>/settings.json                  enabledPlugins {"name@market": bool}
  <base>/plugins/installed_plugins.json {"plugins": {"name@market": [{...}]}}

A newer compatible native build is preserved unless an explicit pin exists.

Design: "Plugin handling".
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from compare import DriftItem

ENTRY_ID = "claude-plugins"


@dataclass(frozen=True)
class PluginState:
    key: str
    enabled: bool | None = None
    version: str | None = None


def _load_json(path: Path, errors: list[str]) -> dict:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"{path.name}: invalid JSON at line {exc.lineno}, "
                      f"column {exc.colno}")
        return {}
    except (UnicodeDecodeError, OSError) as exc:
        errors.append(f"{path.name}: unreadable ({type(exc).__name__})")
        return {}
    return data if isinstance(data, dict) else {}


def read_layer(base: Path | None) -> tuple[dict[str, PluginState], list[str]]:
    """Declarative plugin state for one layer, plus any parse errors."""
    errors: list[str] = []
    if base is None or not Path(base).is_dir():
        return {}, errors
    base = Path(base)

    settings = _load_json(base / "settings.json", errors)
    enabled_map = settings.get("enabledPlugins", {})
    if not isinstance(enabled_map, dict):
        enabled_map = {}

    installed = _load_json(base / "plugins" / "installed_plugins.json", errors)
    raw_plugins = installed.get("plugins", {})
    versions: dict[str, str] = {}
    if isinstance(raw_plugins, dict):
        for key, records in raw_plugins.items():
            if not isinstance(key, str) or not isinstance(records, list):
                continue
            found: list[str] = []
            for record in records:
                if isinstance(record, dict):
                    version = record.get("version")
                    if isinstance(version, str) and version:
                        found.append(version)
            if found:
                versions[key] = max(found, key=lambda v: (parse_version(v) or (), v))

    state: dict[str, PluginState] = {}
    for key in sorted(set(enabled_map) | set(versions)):
        value = enabled_map.get(key)
        state[key] = PluginState(
            key=key,
            enabled=bool(value) if isinstance(value, bool) else None,
            version=versions.get(key),
        )
    return state, errors


# --------------------------------------------------------------------------
# versions
# --------------------------------------------------------------------------

def parse_version(text: str | None) -> tuple[int, ...] | None:
    if not text:
        return None
    parts = text.split(".")
    if not all(part.isdigit() for part in parts):
        return None
    return tuple(int(part) for part in parts)


def compare_versions(a: str | None, b: str | None) -> int | None:
    left, right = parse_version(a), parse_version(b)
    if left is None or right is None:
        return None
    width = max(len(left), len(right))
    left += (0,) * (width - len(left))
    right += (0,) * (width - len(right))
    return (left > right) - (left < right)


# --------------------------------------------------------------------------
# classification
# --------------------------------------------------------------------------

def _item(key: str, suffix: str, classification: str, severity: str,
          detail: str) -> DriftItem:
    return DriftItem(
        id=f"{ENTRY_ID}:{key}{suffix}",
        entry_id=ENTRY_ID,
        kind="plugin",
        classification=classification,
        severity=severity,
        path=key,
        policy="portable_authoritative",
        detail=detail,
    )


def classify_plugins(desired, wsl_native, windows_native, pins,
                     *, entry_id: str = ENTRY_ID) -> list[DriftItem]:
    """Compare the portable record against both native managers."""
    items: list[DriftItem] = []
    natives = (("wsl", wsl_native), ("windows", windows_native))
    all_keys = sorted(set(desired) | set(wsl_native) | set(windows_native))

    for key in all_keys:
        want = desired.get(key)

        if want is None:
            items.append(_item(
                key, "", "plugin_extra", "info",
                "Installed natively but absent from the portable record. "
                "No action proposed; add it to the record if it is intended."))
            continue

        missing_layers = [layer for layer, native in natives if key not in native]
        if missing_layers:
            if len(missing_layers) == len(natives):
                # Missing everywhere: one item, not one per layer.
                items.append(_item(
                    key, "", "plugin_missing", "review",
                    "Desired plugin is not installed on any native layer. "
                    f"Install it with the native manager: "
                    f"claude plugin install {key}"))
            else:
                for layer in missing_layers:
                    items.append(_item(
                        key, f"#missing:{layer}", "plugin_missing", "review",
                        f"Desired plugin is not installed on {layer}. Install "
                        f"it with the native manager: "
                        f"claude plugin install {key}"))

        for layer, native in natives:
            have = native.get(key)
            if have is None:
                continue
            if want.enabled is not None and have.enabled is not None \
                    and want.enabled != have.enabled:
                verb = "enable" if want.enabled else "disable"
                items.append(_item(
                    key, f"#enabled:{layer}", "plugin_enabled_differs", "review",
                    f"Record says enabled={want.enabled}, {layer} says "
                    f"enabled={have.enabled}. Reconcile with: "
                    f"claude plugin {verb} {key}"))

            pin = pins.get(key)
            if pin and have.version and have.version != pin:
                items.append(_item(
                    key, f"#pin:{layer}", "plugin_pin_violation", "conflict",
                    f"Explicit pin {pin} but {layer} has {have.version}. "
                    f"A pin is the only thing that authorizes a downgrade; "
                    f"approve before acting."))

        wsl_version = (wsl_native.get(key).version
                       if wsl_native.get(key) else None)
        win_version = (windows_native.get(key).version
                       if windows_native.get(key) else None)
        if wsl_version and win_version and wsl_version != win_version:
            if pins.get(key):
                continue  # already reported as a pin violation above
            order = compare_versions(wsl_version, win_version)
            if order is None:
                items.append(_item(
                    key, "#version", "plugin_incompatible", "review",
                    f"Versions are not comparable (wsl={wsl_version}, "
                    f"windows={win_version}); resolve by hand."))
            else:
                newer, older = ("wsl", "windows") if order > 0 else ("windows", "wsl")
                newest = wsl_version if order > 0 else win_version
                oldest = win_version if order > 0 else wsl_version
                items.append(_item(
                    key, "#version", "plugin_version_differs", "review",
                    f"{newer} has {newest}, {older} has {oldest}. The newer "
                    f"build is preserved; upgrade {older} with: "
                    f"claude plugin update {key}"))
    return items

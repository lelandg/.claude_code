"""Tests for plugin classification.

Design: "Plugin handling"; test cases 7 (newer Windows plugin, no pin) and
8 (explicit pin violation).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import plugins as pl  # noqa: E402

KEY = "superpowers@claude-plugins-official"
OTHER = "context7@claude-plugins-official"


def build_layer(base: Path, *, enabled: dict[str, bool],
                installed: dict[str, str]) -> Path:
    base.mkdir(parents=True, exist_ok=True)
    (base / "settings.json").write_text(
        json.dumps({"enabledPlugins": enabled}), encoding="utf-8")
    if installed:
        (base / "plugins").mkdir(exist_ok=True)
        (base / "plugins" / "installed_plugins.json").write_text(json.dumps({
            "version": 1,
            "plugins": {key: [{"scope": "user", "installPath": "/x",
                               "version": version,
                               "installedAt": "2026-01-01T00:00:00Z"}]
                        for key, version in installed.items()},
        }), encoding="utf-8")
    return base


# --- reading ---------------------------------------------------------------

def test_read_layer_merges_enabled_state_and_installed_version(tmp_path: Path):
    base = build_layer(tmp_path / "wsl", enabled={KEY: True},
                       installed={KEY: "6.2.0"})
    state, errors = pl.read_layer(base)
    assert errors == []
    assert state[KEY] == pl.PluginState(key=KEY, enabled=True, version="6.2.0")


def test_read_layer_handles_a_repo_layer_with_no_installed_file(tmp_path: Path):
    base = build_layer(tmp_path / "repo", enabled={KEY: True}, installed={})
    state, errors = pl.read_layer(base)
    assert errors == []
    assert state[KEY].version is None
    assert state[KEY].enabled is True


def test_read_layer_of_a_missing_base_is_empty(tmp_path: Path):
    state, errors = pl.read_layer(tmp_path / "nope")
    assert state == {} and errors == []


def test_read_layer_of_none_is_empty():
    assert pl.read_layer(None) == ({}, [])


def test_read_layer_records_a_parse_error_without_content(tmp_path: Path):
    base = tmp_path / "bad"
    base.mkdir()
    (base / "settings.json").write_text('{"enabledPlugins": {,}} token=secret',
                                        encoding="utf-8")
    state, errors = pl.read_layer(base)
    assert state == {}
    assert len(errors) == 1
    assert "secret" not in errors[0]


def test_read_layer_picks_the_highest_version_when_scoped_twice(tmp_path: Path):
    base = tmp_path / "wsl"
    base.mkdir()
    (base / "settings.json").write_text('{"enabledPlugins": {}}',
                                        encoding="utf-8")
    (base / "plugins").mkdir()
    (base / "plugins" / "installed_plugins.json").write_text(json.dumps({
        "plugins": {KEY: [{"version": "1.0.0"}, {"version": "1.3.0"}]},
    }), encoding="utf-8")
    state, _ = pl.read_layer(base)
    assert state[KEY].version == "1.3.0"


# --- version comparison ----------------------------------------------------

def test_parse_version_handles_dotted_integers():
    assert pl.parse_version("6.2.0") == (6, 2, 0)
    assert pl.parse_version("6.2") == (6, 2)


def test_parse_version_rejects_non_numeric():
    assert pl.parse_version("v6.2.0-beta") is None
    assert pl.parse_version(None) is None


def test_compare_versions_orders_numerically_not_lexically():
    assert pl.compare_versions("6.10.0", "6.9.0") == 1
    assert pl.compare_versions("6.2.0", "6.2.0") == 0
    assert pl.compare_versions("1.0", "1.0.0") == 0


def test_compare_versions_returns_none_when_incomparable():
    assert pl.compare_versions("6.2.0", "nightly") is None


# --- classification --------------------------------------------------------

def state(key=KEY, enabled=True, version=None) -> dict[str, pl.PluginState]:
    return {key: pl.PluginState(key=key, enabled=enabled, version=version)}


def test_desired_plugin_absent_from_a_native_manager_is_missing():
    items = pl.classify_plugins(state(), {}, {}, {})
    kinds = {(i.classification, i.severity) for i in items}
    assert ("plugin_missing", "review") in kinds
    assert all(i.kind == "plugin" for i in items)


def test_native_plugin_not_in_the_record_is_extra_and_only_informational():
    items = pl.classify_plugins({}, state(), {}, {})
    assert [(i.classification, i.severity) for i in items] == [
        ("plugin_extra", "info")]


def test_enabled_state_difference_is_reported_per_layer():
    items = pl.classify_plugins(state(enabled=True),
                                state(enabled=False, version="6.2.0"),
                                state(enabled=True, version="6.2.0"), {})
    differing = [i for i in items if i.classification == "plugin_enabled_differs"]
    assert len(differing) == 1
    assert differing[0].id.endswith("#enabled:wsl")


def test_newer_native_version_without_a_pin_is_preserved_not_downgraded():
    # Design test case 7: Windows has a newer build than WSL.
    items = pl.classify_plugins(state(), state(version="6.1.0"),
                                state(version="6.2.0"), {})
    version_items = [i for i in items
                     if i.classification == "plugin_version_differs"]
    assert len(version_items) == 1
    detail = version_items[0].detail
    assert "windows" in detail and "6.2.0" in detail
    assert "downgrade" not in detail.lower()
    assert "upgrade" in detail.lower()
    assert version_items[0].id.endswith("#version")


def test_matching_versions_produce_no_version_item():
    items = pl.classify_plugins(state(), state(version="6.2.0"),
                                state(version="6.2.0"), {})
    assert not [i for i in items if i.classification == "plugin_version_differs"]


def test_incomparable_versions_are_reported_as_incompatible():
    items = pl.classify_plugins(state(), state(version="nightly"),
                                state(version="6.2.0"), {})
    assert any(i.classification == "plugin_incompatible" for i in items)


def test_pin_violation_is_a_conflict():
    # Design test case 8.
    items = pl.classify_plugins(state(), state(version="6.1.0"),
                                state(version="6.2.0"), {KEY: "6.2.0"})
    violations = [i for i in items if i.classification == "plugin_pin_violation"]
    assert len(violations) == 1
    assert violations[0].severity == "conflict"
    assert violations[0].id.endswith("#pin:wsl")
    assert "6.2.0" in violations[0].detail


def test_a_satisfied_pin_produces_no_item():
    items = pl.classify_plugins(state(), state(version="6.2.0"),
                                state(version="6.2.0"), {KEY: "6.2.0"})
    assert not [i for i in items if i.classification == "plugin_pin_violation"]


def test_item_ids_are_stable_and_namespaced():
    items = pl.classify_plugins(state(), {}, {}, {})
    assert items[0].id == f"claude-plugins:{KEY}"
    assert items[0].entry_id == "claude-plugins"


# --- has_windows -------------------------------------------------------
#
# wsl_native/windows_native are always plain dicts, so an empty dict is
# ambiguous by itself. has_windows disambiguates it for the windows layer:
# these tests pin both readings so they can never quietly collapse back
# into one.

def test_has_windows_false_excludes_windows_from_the_missing_check():
    # Same inputs that DO produce a windows plugin_missing item below
    # (has_windows=True); with the layer out of scope, nothing is emitted.
    items = pl.classify_plugins(state(), state(version="6.2.0"), {}, {},
                                has_windows=False)
    assert items == []


def test_has_windows_true_with_an_empty_windows_native_is_a_real_miss():
    items = pl.classify_plugins(state(), state(version="6.2.0"), {}, {},
                                has_windows=True)
    missing = [i for i in items if i.classification == "plugin_missing"]
    assert len(missing) == 1
    assert missing[0].id.endswith("#missing:windows")


def test_has_windows_false_produces_no_version_item():
    items = pl.classify_plugins(state(), state(version="6.1.0"),
                                state(version="6.2.0"), {}, has_windows=False)
    assert not [i for i in items if i.classification == "plugin_version_differs"]
    assert not [i for i in items if i.classification == "plugin_incompatible"]

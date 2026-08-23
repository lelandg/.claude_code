"""Tests for reviewed merge planning, application, and restoration.

Design: "Reviewed application workflow", "Backups and recovery"; test cases
13 (stale report fingerprints), 16 (backup restoration), 17 (idempotence).
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import manifest as mf  # noqa: E402
import merge  # noqa: E402
import scan  # noqa: E402

NOW = datetime(2026, 8, 10, 14, 3, 22, tzinfo=timezone.utc)

MANIFEST_TEMPLATE = """
schema_version = 1

[roots]
wsl_home = "{wsl}"
repo = "{repo}"
windows_home = "{windows}"

[state]
dir = "{state}"

[secrets]
deny_key_patterns = ["(?i)token"]
deny_path_globs = []

[[entries]]
id = "agents-md"
policy = "portable_authoritative"
kind = "text"
wsl = "AGENTS.md"
repo = "AGENTS.md"
windows = "AGENTS.md"

[[entries]]
id = "settings"
policy = "portable_authoritative"
kind = "json"
wsl = "settings.json"
repo = "settings.json"
windows = "settings.json"

[entries.fields]
"model" = "portable_authoritative"
"statusLine.command" = "platform_overlay"
"mcpServers" = "portable_authoritative"

[[entries]]
id = "claude-agents"
policy = "portable_authoritative"
kind = "tree"
wsl = "agents"
repo = "agents"
windows = "agents"
globs = ["**/*.md"]

[[entries]]
id = "claude-skills"
policy = "portable_additive"
kind = "tree"
wsl = "skills"
repo = "skills"
windows = "skills"
globs = ["**/*.md"]

[[entries]]
id = "claude-plugins"
policy = "portable_authoritative"
kind = "plugins"
wsl = "."
repo = "."
windows = "."

[[entries]]
id = "codex-config"
policy = "portable_authoritative"
kind = "toml"
wsl = "config.toml"
repo = "config.toml"
windows = "config.toml"

[entries.fields]
"model" = "portable_authoritative"
"""

#: One merge-path test per manifest ``kind``. The structural guard below reads
#: the real config/agent-sync.toml and fails when a kind in it has no test
#: here. Two Criticals shipped on this branch because the fixtures encoded the
#: plan's shape instead of the manifest's: no test ever planned a "tree" or a
#: "toml" entry, so neither path was ever run.
MERGE_PATH_TESTS_BY_KIND = {
    "text": "test_publish_writes_the_wsl_content_into_the_repository",
    "tree": "test_a_tree_item_targets_the_named_file_not_the_directory",
    "json": "test_set_field_leaves_every_other_key_untouched",
    "toml": "test_a_toml_field_merge_is_refused_with_a_reason",
    "plugins": "test_plan_emits_a_plugin_command_but_never_runs_it",
}

REAL_MANIFEST = (Path(__file__).resolve().parents[3] / "config"
                 / "agent-sync.toml")


@pytest.fixture
def scene(fixture_roots, tmp_path: Path):
    path = tmp_path / "agent-sync.toml"
    path.write_text(MANIFEST_TEMPLATE.format(
        wsl=fixture_roots.wsl, repo=fixture_roots.repo,
        windows=fixture_roots.windows, state=fixture_roots.state),
        encoding="utf-8")
    return path, fixture_roots


def scan_now(manifest_path) -> dict:
    return scan.run_scan(manifest_path, root_overrides=None, now=NOW,
                         entropy="test01")


def seed_text(roots, wsl: str, repo: str, windows: str) -> None:
    roots.write(roots.wsl, "AGENTS.md", wsl)
    roots.write(roots.repo, "AGENTS.md", repo)
    roots.write(roots.windows, "AGENTS.md", windows)


def seed_json(roots, wsl: dict, repo: dict, windows: dict) -> None:
    for layer, data in (("wsl", wsl), ("repo", repo), ("windows", windows)):
        roots.write(getattr(roots, layer), "settings.json", json.dumps(data))


def seed_tree(roots, rel: str, *, wsl=None, repo=None, windows=None) -> None:
    """Write one file inside the 'agents' tree entry, per layer."""
    for layer, content in (("wsl", wsl), ("repo", repo), ("windows", windows)):
        if content is not None:
            roots.write(getattr(roots, layer), f"agents/{rel}", content)


def seed_toml(roots, *, wsl=None, repo=None, windows=None) -> None:
    for layer, content in (("wsl", wsl), ("repo", repo), ("windows", windows)):
        if content is not None:
            roots.write(getattr(roots, layer), "config.toml", content)


def quiet(roots) -> None:
    """Seed every non-tree entry so it contributes no drift of its own."""
    seed_text(roots, "a\n", "a\n", "a\n")
    seed_json(roots, {"model": "x"}, {"model": "x"}, {"model": "x"})


# --- pointers --------------------------------------------------------------

def test_get_and_set_pointer_round_trip():
    data = {"a": {"b": 1}}
    assert merge.get_pointer(data, "a.b") == 1
    assert merge.set_pointer(data, "a.b", 2)["a"]["b"] == 2


def test_set_pointer_creates_missing_parents():
    assert merge.set_pointer({}, "a.b.c", 7) == {"a": {"b": {"c": 7}}}


def test_set_pointer_does_not_mutate_the_input():
    original = {"a": {"b": 1}}
    merge.set_pointer(original, "a.b", 9)
    assert original["a"]["b"] == 1


# --- planning --------------------------------------------------------------

def test_plan_selects_only_the_requested_item_ids(scene):
    manifest_path, roots = scene
    seed_text(roots, "new\n", "old\n", "old\n")
    seed_json(roots, {"model": "x"}, {"model": "y"}, {"model": "y"})
    m = mf.load_manifest(manifest_path)
    doc = scan_now(manifest_path)

    plan = merge.plan_merge(doc, m, ["agents-md"])
    assert [a.item_id for a in plan.actions if a.kind != "noop"] == ["agents-md"]


def test_plan_refuses_an_unknown_item_id(scene):
    manifest_path, roots = scene
    seed_text(roots, "a\n", "a\n", "a\n")
    seed_json(roots, {"model": "x"}, {"model": "x"}, {"model": "x"})
    m = mf.load_manifest(manifest_path)
    plan = merge.plan_merge(scan_now(manifest_path), m, ["no-such-item"])
    assert plan.actions == ()
    assert plan.skipped[0][0] == "no-such-item"


def test_plan_never_proposes_a_protected_overlay_field(scene):
    manifest_path, roots = scene
    seed_text(roots, "a\n", "a\n", "a\n")
    seed_json(roots,
              {"model": "x", "statusLine": {"command": "/wsl.sh"}},
              {"model": "x", "statusLine": {"command": "/wsl.sh"}},
              {"model": "x", "statusLine": {"command": "C:\\win.ps1"}})
    m = mf.load_manifest(manifest_path)
    plan = merge.plan_merge(scan_now(manifest_path), m,
                            ["settings:statusLine.command"])
    assert not [a for a in plan.actions if a.kind != "noop"]
    assert "protected" in plan.skipped[0][1].lower()


def test_plan_emits_a_plugin_command_but_never_runs_it(scene):
    manifest_path, roots = scene
    seed_text(roots, "a\n", "a\n", "a\n")
    seed_json(roots, {"model": "x"}, {"model": "x"}, {"model": "x"})
    m = mf.load_manifest(manifest_path)
    doc = scan_now(manifest_path)
    doc["items"].append({
        "id": "claude-plugins:superpowers@official#missing:windows",
        "entry_id": "claude-plugins", "kind": "plugin",
        "classification": "plugin_missing", "severity": "review",
        "path": "superpowers@official", "policy": "portable_authoritative",
        "detail": "Install it with: claude plugin install superpowers@official"})
    plan = merge.plan_merge(doc, m, [doc["items"][-1]["id"]])
    action = plan.actions[0]
    assert action.kind == "plugin_command"
    assert action.command and action.command[0] == "claude"


def test_render_plan_shows_targets_and_a_dry_run_marker(scene):
    manifest_path, roots = scene
    seed_text(roots, "new\n", "old\n", "old\n")
    seed_json(roots, {"model": "x"}, {"model": "x"}, {"model": "x"})
    m = mf.load_manifest(manifest_path)
    text = merge.render_plan(merge.plan_merge(scan_now(manifest_path), m,
                                              ["agents-md"]))
    assert "DRY RUN" in text
    assert "AGENTS.md" in text


# --- tree entries (fix wave, C1) -------------------------------------------

def test_a_tree_item_targets_the_named_file_not_the_directory(scene):
    """A tree item id is 'entry:path-inside-the-entry'. Every path the action
    touches has to descend into the directory. Taking the target from the
    entry alone pointed the write at the directory itself, and the apply then
    raised IsADirectoryError after the backup directory had been created."""
    manifest_path, roots = scene
    quiet(roots)
    seed_tree(roots, "newagent.md", wsl="new agent body\n")
    m = mf.load_manifest(manifest_path)
    doc = scan_now(manifest_path)

    item = next(i for i in doc["items"] if i["id"] == "claude-agents:newagent.md")
    assert item["classification"] == "wsl_only"

    plan = merge.plan_merge(doc, m, ["claude-agents:newagent.md"])
    action = plan.actions[0]
    assert action.kind == "write_file"
    assert action.target == roots.repo / "agents" / "newagent.md"
    assert action.source == roots.wsl / "agents" / "newagent.md"
    assert action.cascade_target == roots.windows / "agents" / "newagent.md"

    # The dry run has to name the file the operator is approving, not the
    # directory that holds it.
    text = merge.render_plan(plan)
    assert str(roots.repo / "agents" / "newagent.md") in text


def test_applying_a_wsl_only_tree_item_writes_the_file_in_both_targets(scene):
    manifest_path, roots = scene
    quiet(roots)
    seed_tree(roots, "newagent.md", wsl="new agent body\n")
    m = mf.load_manifest(manifest_path)
    plan = merge.plan_merge(scan_now(manifest_path), m,
                            ["claude-agents:newagent.md"])
    merge.apply_plan(plan, m, backups_dir=roots.state / "backups")

    assert (roots.repo / "agents" / "newagent.md").read_text(
        encoding="utf-8") == "new agent body\n"
    assert (roots.windows / "agents" / "newagent.md").read_text(
        encoding="utf-8") == "new agent body\n"


def test_publishing_a_tree_item_updates_the_baseline_and_mirrors_windows(scene):
    manifest_path, roots = scene
    quiet(roots)
    seed_tree(roots, "sub/agent.md", wsl="new\n", repo="old\n", windows="old\n")
    m = mf.load_manifest(manifest_path)
    doc = scan_now(manifest_path)
    item_id = "claude-agents:sub/agent.md"
    assert next(i for i in doc["items"]
                if i["id"] == item_id)["classification"] == "publish_to_repo"

    plan = merge.plan_merge(doc, m, [item_id])
    merge.apply_plan(plan, m, backups_dir=roots.state / "backups")
    assert (roots.repo / "agents" / "sub" / "agent.md").read_text(
        encoding="utf-8") == "new\n"
    assert (roots.windows / "agents" / "sub" / "agent.md").read_text(
        encoding="utf-8") == "new\n"


def test_reconciling_a_tree_item_writes_only_the_windows_file(scene):
    manifest_path, roots = scene
    quiet(roots)
    seed_tree(roots, "agent.md", wsl="same\n", repo="same\n",
              windows="drifted\n")
    m = mf.load_manifest(manifest_path)
    doc = scan_now(manifest_path)
    item_id = "claude-agents:agent.md"
    assert next(i for i in doc["items"]
                if i["id"] == item_id)["classification"] == "reconcile_windows"

    plan = merge.plan_merge(doc, m, [item_id])
    action = plan.actions[0]
    assert action.target == roots.windows / "agents" / "agent.md"
    assert action.cascade_target is None

    merge.apply_plan(plan, m, backups_dir=roots.state / "backups")
    assert (roots.windows / "agents" / "agent.md").read_text(
        encoding="utf-8") == "same\n"
    assert (roots.repo / "agents" / "agent.md").read_text(
        encoding="utf-8") == "same\n"


def test_a_tree_item_renders_paths_for_the_windows_layer(scene):
    manifest_path, roots = scene
    quiet(roots)
    body = f"hook: {roots.wsl}/tools/guard.py\n"
    seed_tree(roots, "agent.md", wsl=body, repo=body, windows="stale\n")
    m = mf.load_manifest(manifest_path)
    plan = merge.plan_merge(scan_now(manifest_path), m,
                            ["claude-agents:agent.md"])
    merge.apply_plan(plan, m, backups_dir=roots.state / "backups")
    written = (roots.windows / "agents" / "agent.md").read_text(encoding="utf-8")
    assert "{HOME}" not in written
    assert str(roots.wsl) not in written


def test_a_target_that_is_a_directory_is_refused_not_written(scene):
    """The guard that turns C1's class of bug into a refusal: an id that
    resolves to an existing directory is skipped with a reason, never handed
    to a writer."""
    manifest_path, roots = scene
    quiet(roots)
    seed_tree(roots, "agent.md", wsl="a\n", repo="a\n", windows="a\n")
    m = mf.load_manifest(manifest_path)
    doc = scan_now(manifest_path)
    doc["items"].append({
        "id": "claude-agents", "entry_id": "claude-agents", "kind": "tree_file",
        "classification": "wsl_only", "severity": "review",
        "path": "agents", "policy": "portable_authoritative",
        "detail": "an id that names the directory itself"})

    plan = merge.plan_merge(doc, m, ["claude-agents"])
    assert plan.actions == ()
    assert "directory" in plan.skipped[0][1]


# --- deletions --------------------------------------------------------------
#
# WSL is the authority. A file or field that is gone from WSL and still
# present in a target is drift the merge must be able to remove -- with the
# same explicit-id approval, backup, and restore as every write. (Leland,
# 2026-08-20: "offer to remove anything missing from the targets; 100%
# thorough -- temp files, scripts, etc.")

def seed_skill(roots, rel: str, *, wsl=None, repo=None, windows=None) -> None:
    """Write one file inside the additive 'skills' tree entry, per layer."""
    for layer, content in (("wsl", wsl), ("repo", repo), ("windows", windows)):
        if content is not None:
            roots.write(getattr(roots, layer), f"skills/{rel}", content)


def test_a_deleted_tree_file_plans_a_delete_with_a_windows_cascade(scene):
    manifest_path, roots = scene
    quiet(roots)
    seed_tree(roots, "keep.md", wsl="k\n", repo="k\n", windows="k\n")
    seed_tree(roots, "old.md", repo="body\n", windows="body\n")
    m = mf.load_manifest(manifest_path)
    doc = scan_now(manifest_path)

    item = next(i for i in doc["items"] if i["id"] == "claude-agents:old.md")
    assert item["classification"] == "publish_to_repo"
    assert "wsl_fingerprint" not in item

    plan = merge.plan_merge(doc, m, ["claude-agents:old.md"])
    action = plan.actions[0]
    assert action.kind == "delete_file"
    assert action.target == roots.repo / "agents" / "old.md"
    assert action.cascade_target == roots.windows / "agents" / "old.md"
    assert "delete" in merge.render_plan(plan).lower()


def test_applying_a_deletion_removes_the_file_from_both_targets(scene):
    manifest_path, roots = scene
    quiet(roots)
    seed_tree(roots, "keep.md", wsl="k\n", repo="k\n", windows="k\n")
    seed_tree(roots, "old.md", repo="body\n", windows="body\n")
    m = mf.load_manifest(manifest_path)
    plan = merge.plan_merge(scan_now(manifest_path), m, ["claude-agents:old.md"])
    _, applied = merge.apply_plan(plan, m, backups_dir=roots.state / "backups")

    assert applied == ["claude-agents:old.md"]
    assert not (roots.repo / "agents" / "old.md").exists()
    assert not (roots.windows / "agents" / "old.md").exists()
    assert (roots.repo / "agents" / "keep.md").exists()
    assert (roots.windows / "agents" / "keep.md").exists()


def test_restore_brings_a_deleted_file_back_in_both_targets(scene):
    manifest_path, roots = scene
    quiet(roots)
    seed_tree(roots, "keep.md", wsl="k\n", repo="k\n", windows="k\n")
    seed_tree(roots, "old.md", repo="body\n", windows="body\n")
    m = mf.load_manifest(manifest_path)
    plan = merge.plan_merge(scan_now(manifest_path), m, ["claude-agents:old.md"])
    backup_dir, _ = merge.apply_plan(plan, m, backups_dir=roots.state / "backups")

    merge.restore(backup_dir)
    assert (roots.repo / "agents" / "old.md").read_text(
        encoding="utf-8") == "body\n"
    assert (roots.windows / "agents" / "old.md").read_text(
        encoding="utf-8") == "body\n"


def test_applying_the_same_deletion_twice_changes_nothing(scene):
    manifest_path, roots = scene
    quiet(roots)
    seed_tree(roots, "keep.md", wsl="k\n", repo="k\n", windows="k\n")
    seed_tree(roots, "old.md", repo="body\n", windows="body\n")
    m = mf.load_manifest(manifest_path)
    plan = merge.plan_merge(scan_now(manifest_path), m, ["claude-agents:old.md"])
    merge.apply_plan(plan, m, backups_dir=roots.state / "backups")
    _, applied = merge.apply_plan(plan, m, backups_dir=roots.state / "backups")
    assert applied == []


def test_a_second_scan_after_a_deletion_shows_no_remaining_drift(scene):
    manifest_path, roots = scene
    quiet(roots)
    seed_tree(roots, "keep.md", wsl="k\n", repo="k\n", windows="k\n")
    seed_tree(roots, "old.md", repo="body\n", windows="body\n")
    m = mf.load_manifest(manifest_path)
    plan = merge.plan_merge(scan_now(manifest_path), m, ["claude-agents:old.md"])
    merge.apply_plan(plan, m, backups_dir=roots.state / "backups")
    after = scan_now(manifest_path)
    assert [i for i in after["items"] if i["severity"] == "review"] == []


def test_an_orphaned_directory_is_swept_including_untracked_files(scene):
    """The manifest globs only **/*.md, so temp files, scripts, and caches
    inside a directory are invisible to the scan. When the directory itself
    is gone from WSL, everything under the target copy is orphaned -- the
    sweep removes it all, not just the globbed files."""
    manifest_path, roots = scene
    quiet(roots)
    seed_tree(roots, "keep.md", wsl="k\n", repo="k\n", windows="k\n")
    roots.write(roots.repo, "agents/gone/a.md", "a\n")
    roots.write(roots.repo, "agents/gone/temp.tmp", "scratch\n")
    roots.write(roots.repo, "agents/gone/script.sh", "#!/bin/sh\n")
    roots.write(roots.windows, "agents/gone/a.md", "a\n")
    roots.write(roots.windows, "agents/gone/cache.pyc", "bytecode\n")
    m = mf.load_manifest(manifest_path)
    doc = scan_now(manifest_path)

    plan = merge.plan_merge(doc, m, ["claude-agents:gone/a.md"])
    action = plan.actions[0]
    assert action.kind == "delete_tree"
    assert action.target == roots.repo / "agents" / "gone"
    assert action.cascade_target == roots.windows / "agents" / "gone"

    backup_dir, applied = merge.apply_plan(plan, m,
                                           backups_dir=roots.state / "backups")
    assert applied == ["claude-agents:gone/a.md"]
    assert not (roots.repo / "agents" / "gone").exists()
    assert not (roots.windows / "agents" / "gone").exists()
    assert (roots.repo / "agents" / "keep.md").exists()

    merge.restore(backup_dir)
    for root, rel in ((roots.repo, "agents/gone/temp.tmp"),
                      (roots.repo, "agents/gone/script.sh"),
                      (roots.repo, "agents/gone/a.md"),
                      (roots.windows, "agents/gone/cache.pyc"),
                      (roots.windows, "agents/gone/a.md")):
        assert (root / rel).exists(), f"restore lost {rel}"
    assert (roots.repo / "agents" / "gone" / "temp.tmp").read_text(
        encoding="utf-8") == "scratch\n"


def test_two_ids_in_one_orphaned_directory_plan_a_single_sweep(scene):
    manifest_path, roots = scene
    quiet(roots)
    seed_tree(roots, "keep.md", wsl="k\n", repo="k\n", windows="k\n")
    roots.write(roots.repo, "agents/gone/a.md", "a\n")
    roots.write(roots.repo, "agents/gone/b.md", "b\n")
    roots.write(roots.windows, "agents/gone/a.md", "a\n")
    roots.write(roots.windows, "agents/gone/b.md", "b\n")
    m = mf.load_manifest(manifest_path)
    plan = merge.plan_merge(scan_now(manifest_path), m,
                            ["claude-agents:gone/a.md",
                             "claude-agents:gone/b.md"])
    sweeps = [a for a in plan.actions if a.kind == "delete_tree"]
    covered = [a for a in plan.actions if a.kind == "noop"]
    assert len(sweeps) == 1
    assert len(covered) == 1
    assert "covered" in covered[0].description


def test_a_deletion_under_an_additive_entry_applies_when_named(scene):
    """portable_additive deletions classify additive_delete_requires_approval.
    Naming the id IS the approval -- the plan turns it into a delete, where it
    used to be skipped unconditionally."""
    manifest_path, roots = scene
    quiet(roots)
    seed_skill(roots, "keep/SKILL.md", wsl="k\n", repo="k\n", windows="k\n")
    seed_skill(roots, "dead.md", repo="body\n", windows="body\n")
    m = mf.load_manifest(manifest_path)
    doc = scan_now(manifest_path)

    item = next(i for i in doc["items"] if i["id"] == "claude-skills:dead.md")
    assert item["classification"] == "additive_delete_requires_approval"

    plan = merge.plan_merge(doc, m, ["claude-skills:dead.md"])
    assert plan.actions[0].kind == "delete_file"
    merge.apply_plan(plan, m, backups_dir=roots.state / "backups")
    assert not (roots.repo / "skills" / "dead.md").exists()
    assert not (roots.windows / "skills" / "dead.md").exists()


def test_a_windows_only_file_is_deleted_from_windows_when_named(scene):
    manifest_path, roots = scene
    quiet(roots)
    seed_tree(roots, "keep.md", wsl="k\n", repo="k\n", windows="k\n")
    seed_tree(roots, "stray.md", windows="windows cruft\n")
    m = mf.load_manifest(manifest_path)
    doc = scan_now(manifest_path)

    item = next(i for i in doc["items"] if i["id"] == "claude-agents:stray.md")
    assert item["classification"] == "windows_only"

    plan = merge.plan_merge(doc, m, ["claude-agents:stray.md"])
    action = plan.actions[0]
    assert action.kind == "delete_file"
    assert action.layer == "windows"
    assert action.target == roots.windows / "agents" / "stray.md"
    assert action.cascade_target is None

    merge.apply_plan(plan, m, backups_dir=roots.state / "backups")
    assert not (roots.windows / "agents" / "stray.md").exists()


def test_a_deleted_json_field_is_removed_not_written_as_null(scene):
    """The latent field-shaped variant from the known-limitations doc: the
    source file exists, the field does not. The old code wrote null into the
    target; the fix removes the key."""
    manifest_path, roots = scene
    seed_text(roots, "a\n", "a\n", "a\n")
    servers = {"gh": {"args": ["x"]}}
    seed_json(roots,
              {"model": "x"},
              {"model": "x", "mcpServers": servers},
              {"model": "x", "mcpServers": servers})
    m = mf.load_manifest(manifest_path)
    doc = scan_now(manifest_path)

    item = next(i for i in doc["items"] if i["id"] == "settings:mcpServers")
    assert item["classification"] == "publish_to_repo"

    plan = merge.plan_merge(doc, m, ["settings:mcpServers"])
    assert plan.actions[0].kind == "delete_field"
    backup_dir, _ = merge.apply_plan(plan, m,
                                     backups_dir=roots.state / "backups")

    for root in (roots.repo, roots.windows):
        after = json.loads((root / "settings.json").read_text(encoding="utf-8"))
        assert "mcpServers" not in after
        assert after["model"] == "x"

    merge.restore(backup_dir)
    after = json.loads((roots.repo / "settings.json").read_text(encoding="utf-8"))
    assert after["mcpServers"] == servers


# --- plugin removal ----------------------------------------------------------

def test_a_removed_plugin_is_dropped_from_the_record_when_named(scene):
    import drift as drift_mod
    manifest_path, roots = scene
    seed_text(roots, "a\n", "a\n", "a\n")
    seed_json(roots,
              {"model": "x"},
              {"model": "x",
               "enabledPlugins": {"foo@bar": True, "keep@m": True}},
              {"model": "x", "enabledPlugins": {"foo@bar": True}})
    m = mf.load_manifest(manifest_path)
    doc = scan_now(manifest_path)
    assert drift_mod.validate_document(doc) == []

    item = next(i for i in doc["items"] if i["id"] == "claude-plugins:foo@bar")
    assert item["classification"] == "plugin_removed"

    plan = merge.plan_merge(doc, m, ["claude-plugins:foo@bar"])
    action = plan.actions[0]
    assert action.kind == "remove_plugin_from_record"
    assert action.command == ("claude", "plugin", "uninstall", "foo@bar")

    backup_dir, applied = merge.apply_plan(plan, m,
                                           backups_dir=roots.state / "backups")
    assert applied == ["claude-plugins:foo@bar"]
    record = json.loads((roots.repo / "settings.json").read_text(
        encoding="utf-8"))
    assert "foo@bar" not in record["enabledPlugins"]
    assert record["enabledPlugins"]["keep@m"] is True
    assert record["model"] == "x"
    # The Windows native state is never touched -- the uninstall is proposed,
    # not executed.
    windows = json.loads((roots.windows / "settings.json").read_text(
        encoding="utf-8"))
    assert windows["enabledPlugins"] == {"foo@bar": True}

    merge.restore(backup_dir)
    record = json.loads((roots.repo / "settings.json").read_text(
        encoding="utf-8"))
    assert record["enabledPlugins"]["foo@bar"] is True


def test_a_windows_only_plugin_proposes_uninstall_without_a_record_edit(scene):
    manifest_path, roots = scene
    seed_text(roots, "a\n", "a\n", "a\n")
    seed_json(roots,
              {"model": "x"},
              {"model": "x"},
              {"model": "x", "enabledPlugins": {"loner@m": True}})
    m = mf.load_manifest(manifest_path)
    doc = scan_now(manifest_path)

    item = next(i for i in doc["items"] if i["id"] == "claude-plugins:loner@m")
    assert item["classification"] == "plugin_removed"

    plan = merge.plan_merge(doc, m, ["claude-plugins:loner@m"])
    action = plan.actions[0]
    assert action.command == ("claude", "plugin", "uninstall", "loner@m")

    before = (roots.repo / "settings.json").read_text(encoding="utf-8")
    _, applied = merge.apply_plan(plan, m, backups_dir=roots.state / "backups")
    assert applied == []
    assert (roots.repo / "settings.json").read_text(
        encoding="utf-8") == before


# --- toml entries (fix wave, C2) -------------------------------------------

def test_a_toml_field_merge_is_refused_with_a_reason(scene):
    """Python 3.12 has no TOML writer, so a field merge could only re-serialize
    the document as JSON into a file named .toml. The refusal is the fix; a
    JSON body in codex/config.toml would be silent corruption, because the
    next scan tokenizes both sides and reports the fingerprints as matching."""
    manifest_path, roots = scene
    quiet(roots)
    # WSL and Windows agree and there is no baseline: publish_to_repo, with
    # the repository target absent -- the branch that wrote JSON.
    seed_toml(roots, wsl='model = "gpt-5.6-terra"\n',
              windows='model = "gpt-5.6-terra"\n')
    m = mf.load_manifest(manifest_path)
    doc = scan_now(manifest_path)
    assert next(i for i in doc["items"]
                if i["id"] == "codex-config:model")["classification"] == \
        "publish_to_repo"

    plan = merge.plan_merge(doc, m, ["codex-config:model"])
    assert plan.actions == ()
    assert plan.skipped == (
        ("codex-config:model",
         "TOML field merge is not implemented; edit the target by hand"),)

    merge.apply_plan(plan, m, backups_dir=roots.state / "backups")
    assert not (roots.repo / "config.toml").exists()
    assert (roots.windows / "config.toml").read_text(
        encoding="utf-8") == 'model = "gpt-5.6-terra"\n'


def test_a_field_merge_refuses_a_target_that_is_not_valid_json(scene):
    manifest_path, roots = scene
    seed_text(roots, "a\n", "a\n", "a\n")
    seed_json(roots, {"model": "opus"}, {"model": "sonnet"},
              {"model": "sonnet"})
    m = mf.load_manifest(manifest_path)
    plan = merge.plan_merge(scan_now(manifest_path), m, ["settings:model"])
    roots.write(roots.repo, "settings.json", "this is not json\n")

    with pytest.raises(merge.MergeError) as caught:
        merge.apply_plan(plan, m, backups_dir=roots.state / "backups")
    assert "not valid JSON" in str(caught.value)
    assert (roots.repo / "settings.json").read_text(
        encoding="utf-8") == "this is not json\n"


# --- field values carrying paths (fix wave, I2) ----------------------------

def test_a_field_value_holding_a_path_is_rendered_for_each_layer(scene):
    """write_file tokenizes and re-renders the path spellings; set_field has
    to do the same. It did not, so a field value holding a WSL path was
    copied verbatim into the Windows file -- and the scanner tokenizes before
    it fingerprints, so the broken result was then reported as clean."""
    manifest_path, roots = scene
    seed_text(roots, "a\n", "a\n", "a\n")
    servers = {"gh": {"args": [f"{roots.wsl}/tools/mcp.py"]}}
    stale = {"gh": {"args": ["old"]}}
    seed_json(roots,
              {"model": "x", "mcpServers": servers},
              {"model": "x", "mcpServers": stale},
              {"model": "x", "mcpServers": stale})
    m = mf.load_manifest(manifest_path)
    plan = merge.plan_merge(scan_now(manifest_path), m, ["settings:mcpServers"])
    assert plan.actions[0].kind == "set_field"
    merge.apply_plan(plan, m, backups_dir=roots.state / "backups")

    repo_arg = json.loads((roots.repo / "settings.json").read_text(
        encoding="utf-8"))["mcpServers"]["gh"]["args"][0]
    windows_arg = json.loads((roots.windows / "settings.json").read_text(
        encoding="utf-8"))["mcpServers"]["gh"]["args"][0]

    assert repo_arg == f"{roots.wsl}/tools/mcp.py"
    assert str(roots.wsl) not in windows_arg
    assert str(roots.windows) in windows_arg


# --- structural guard ------------------------------------------------------

def test_every_manifest_kind_is_exercised_by_a_merge_path_test():
    """Every distinct kind in the real manifest must have a merge-path test.

    C1 and C2 both shipped because no merge test ever planned a "tree" or a
    "toml" entry. This check fails the moment a kind appears in the manifest
    with nothing here exercising it.
    """
    import tomllib
    data = tomllib.loads(REAL_MANIFEST.read_text(encoding="utf-8"))
    kinds = {entry["kind"] for entry in data["entries"]}
    assert kinds - set(MERGE_PATH_TESTS_BY_KIND) == set(), (
        "a manifest kind has no merge-path test")
    module = sys.modules[__name__]
    for kind, name in MERGE_PATH_TESTS_BY_KIND.items():
        assert callable(getattr(module, name, None)), (
            f"the test named for kind {kind!r} does not exist: {name}")


# --- staleness (design test case 13) --------------------------------------

def test_a_report_whose_source_moved_since_the_scan_is_stale(scene):
    manifest_path, roots = scene
    seed_text(roots, "new\n", "old\n", "old\n")
    seed_json(roots, {"model": "x"}, {"model": "x"}, {"model": "x"})
    m = mf.load_manifest(manifest_path)
    doc = scan_now(manifest_path)

    roots.write(roots.wsl, "AGENTS.md", "newer still\n")   # edited after the scan
    assert "agents-md" in merge.stale_items(doc, m)


def test_a_fresh_report_is_not_stale(scene):
    manifest_path, roots = scene
    seed_text(roots, "new\n", "old\n", "old\n")
    seed_json(roots, {"model": "x"}, {"model": "x"}, {"model": "x"})
    m = mf.load_manifest(manifest_path)
    assert merge.stale_items(scan_now(manifest_path), m) == []


def test_apply_refuses_a_stale_item(scene):
    manifest_path, roots = scene
    seed_text(roots, "new\n", "old\n", "old\n")
    seed_json(roots, {"model": "x"}, {"model": "x"}, {"model": "x"})
    doc = scan_now(manifest_path)
    roots.write(roots.wsl, "AGENTS.md", "changed\n")

    code = merge.main(["apply", "--drift-json", json.dumps(doc),
                       "--manifest", str(manifest_path), "--id", "agents-md"])
    assert code == merge.EXIT_STALE
    assert (roots.repo / "AGENTS.md").read_text(encoding="utf-8") == "old\n"


def test_stale_items_only_re_extracts_the_selected_entries(scene, monkeypatch):
    """Ruling 3: scoping stale_items to selected ids must skip other entries."""
    manifest_path, roots = scene
    seed_text(roots, "new\n", "old\n", "old\n")
    seed_json(roots, {"model": "x"}, {"model": "x"}, {"model": "x"})
    m = mf.load_manifest(manifest_path)
    doc = scan_now(manifest_path)

    extracted_entry_ids: list[str] = []
    original = merge.extract.extract_entry

    def spy(entry, layer, root, secrets, roots_arg):
        extracted_entry_ids.append(entry.id)
        return original(entry, layer, root, secrets, roots_arg)

    monkeypatch.setattr(merge.extract, "extract_entry", spy)
    merge.stale_items(doc, m, selected_ids=["agents-md"])
    assert set(extracted_entry_ids) == {"agents-md"}


# --- applying --------------------------------------------------------------

def test_publish_writes_the_wsl_content_into_the_repository(scene):
    manifest_path, roots = scene
    seed_text(roots, "new intent\n", "old\n", "old\n")
    seed_json(roots, {"model": "x"}, {"model": "x"}, {"model": "x"})
    m = mf.load_manifest(manifest_path)
    plan = merge.plan_merge(scan_now(manifest_path), m, ["agents-md"])
    merge.apply_plan(plan, m, backups_dir=roots.state / "backups")
    assert (roots.repo / "AGENTS.md").read_text(encoding="utf-8") == "new intent\n"


def test_reconcile_windows_renders_paths_in_windows_form(scene):
    manifest_path, roots = scene
    body = "hook: {wsl}/tools/guard.py\n".format(wsl=roots.wsl)
    seed_text(roots, body, body, "stale\n")
    seed_json(roots, {"model": "x"}, {"model": "x"}, {"model": "x"})
    m = mf.load_manifest(manifest_path)
    plan = merge.plan_merge(scan_now(manifest_path), m, ["agents-md"])
    merge.apply_plan(plan, m, backups_dir=roots.state / "backups")
    written = (roots.windows / "AGENTS.md").read_text(encoding="utf-8")
    assert "{HOME}" not in written
    assert str(roots.wsl) not in written


def test_set_field_leaves_every_other_key_untouched(scene):
    manifest_path, roots = scene
    seed_text(roots, "a\n", "a\n", "a\n")
    seed_json(roots,
              {"model": "opus", "statusLine": {"command": "/wsl.sh"},
               "keepMe": [1, 2]},
              {"model": "sonnet", "statusLine": {"command": "/wsl.sh"},
               "keepMe": [1, 2]},
              {"model": "sonnet", "statusLine": {"command": "C:\\win.ps1"},
               "keepMe": [1, 2]})
    m = mf.load_manifest(manifest_path)
    plan = merge.plan_merge(scan_now(manifest_path), m, ["settings:model"])
    merge.apply_plan(plan, m, backups_dir=roots.state / "backups")
    after = json.loads((roots.repo / "settings.json").read_text(encoding="utf-8"))
    assert after["model"] == "opus"
    assert after["keepMe"] == [1, 2]
    assert after["statusLine"]["command"] == "/wsl.sh"


def test_windows_owned_field_survives_an_applied_merge(scene):
    manifest_path, roots = scene
    seed_text(roots, "a\n", "a\n", "a\n")
    seed_json(roots,
              {"model": "opus", "statusLine": {"command": "/wsl.sh"}},
              {"model": "sonnet", "statusLine": {"command": "/wsl.sh"}},
              {"model": "sonnet", "statusLine": {"command": "C:\\win.ps1"}})
    m = mf.load_manifest(manifest_path)
    plan = merge.plan_merge(scan_now(manifest_path), m, ["settings:model"])
    merge.apply_plan(plan, m, backups_dir=roots.state / "backups")
    windows = json.loads(
        (roots.windows / "settings.json").read_text(encoding="utf-8"))
    assert windows["statusLine"]["command"] == "C:\\win.ps1"


# --- idempotence (design test case 17) ------------------------------------

def test_applying_the_same_approved_change_twice_changes_nothing(scene):
    manifest_path, roots = scene
    seed_text(roots, "new\n", "old\n", "old\n")
    seed_json(roots, {"model": "x"}, {"model": "x"}, {"model": "x"})
    m = mf.load_manifest(manifest_path)
    plan = merge.plan_merge(scan_now(manifest_path), m, ["agents-md"])
    merge.apply_plan(plan, m, backups_dir=roots.state / "backups")
    first = (roots.repo / "AGENTS.md").read_text(encoding="utf-8")

    second_plan = merge.plan_merge(scan_now(manifest_path), m, ["agents-md"])
    _, applied = merge.apply_plan(second_plan, m,
                                  backups_dir=roots.state / "backups")
    assert (roots.repo / "AGENTS.md").read_text(encoding="utf-8") == first
    assert applied == [] or all(
        a.kind == "noop" for a in second_plan.actions)


def test_a_second_scan_after_applying_shows_no_remaining_drift(scene):
    manifest_path, roots = scene
    seed_text(roots, "new\n", "old\n", "old\n")
    seed_json(roots, {"model": "x"}, {"model": "x"}, {"model": "x"})
    m = mf.load_manifest(manifest_path)
    doc = scan_now(manifest_path)
    ids = [i["id"] for i in doc["items"] if i["severity"] == "review"]
    merge.apply_plan(merge.plan_merge(doc, m, ids), m,
                     backups_dir=roots.state / "backups")
    after = scan_now(manifest_path)
    assert [i for i in after["items"] if i["severity"] == "review"] == []


# --- backups and restore (design test case 16) ----------------------------

def test_apply_backs_up_every_target_it_touches(scene):
    manifest_path, roots = scene
    seed_text(roots, "new\n", "old\n", "old\n")
    seed_json(roots, {"model": "x"}, {"model": "x"}, {"model": "x"})
    m = mf.load_manifest(manifest_path)
    plan = merge.plan_merge(scan_now(manifest_path), m, ["agents-md"])
    backup_dir, _ = merge.apply_plan(plan, m,
                                     backups_dir=roots.state / "backups")
    entries = json.loads(
        (backup_dir / "manifest.json").read_text(encoding="utf-8"))
    assert entries["run_id"] == "2026-08-10T14-03-22Z-test01"
    assert len(entries["files"]) >= 1
    assert (backup_dir / "files").is_dir()


def test_restore_returns_every_target_to_its_pre_merge_content(scene):
    manifest_path, roots = scene
    seed_text(roots, "new\n", "old\n", "old\n")
    seed_json(roots, {"model": "x"}, {"model": "x"}, {"model": "x"})
    m = mf.load_manifest(manifest_path)
    plan = merge.plan_merge(scan_now(manifest_path), m, ["agents-md"])
    backup_dir, _ = merge.apply_plan(plan, m,
                                     backups_dir=roots.state / "backups")
    assert (roots.repo / "AGENTS.md").read_text(encoding="utf-8") == "new\n"

    merge.restore(backup_dir)
    assert (roots.repo / "AGENTS.md").read_text(encoding="utf-8") == "old\n"
    assert (roots.windows / "AGENTS.md").read_text(encoding="utf-8") == "old\n"


def test_restore_recreates_a_file_that_did_not_exist_before(scene):
    manifest_path, roots = scene
    roots.write(roots.wsl, "AGENTS.md", "brand new\n")
    seed_json(roots, {"model": "x"}, {"model": "x"}, {"model": "x"})
    m = mf.load_manifest(manifest_path)
    plan = merge.plan_merge(scan_now(manifest_path), m, ["agents-md"])
    backup_dir, _ = merge.apply_plan(plan, m,
                                     backups_dir=roots.state / "backups")
    assert (roots.repo / "AGENTS.md").exists()
    merge.restore(backup_dir)
    assert not (roots.repo / "AGENTS.md").exists()


def test_a_failed_apply_stops_immediately_and_keeps_the_backup(scene,
                                                               monkeypatch):
    manifest_path, roots = scene
    seed_text(roots, "new\n", "old\n", "old\n")
    seed_json(roots, {"model": "x"}, {"model": "x"}, {"model": "x"})
    m = mf.load_manifest(manifest_path)
    plan = merge.plan_merge(scan_now(manifest_path), m, ["agents-md"])

    def explode(path, text):
        raise OSError("disk full")

    monkeypatch.setattr(merge, "write_target", explode)
    with pytest.raises(OSError):
        merge.apply_plan(plan, m, backups_dir=roots.state / "backups")

    # The backup was taken before the write was attempted, and the target is
    # untouched -- so restoration is possible even though nothing was applied.
    backup_dir = roots.state / "backups" / "2026-08-10T14-03-22Z-test01"
    assert (backup_dir / "manifest.json").is_file()
    assert (roots.repo / "AGENTS.md").read_text(encoding="utf-8") == "old\n"


def test_a_cascade_crash_leaves_a_restorable_backup_for_both_targets(
        scene, monkeypatch):
    """Fix round 1 finding: the primary write can succeed and the cascade
    write can then fail. The per-target loop must still leave a complete,
    restorable manifest -- covering both the applied primary and the
    backed-up-but-unwritten cascade -- not just whichever target happened to
    succeed."""
    manifest_path, roots = scene
    seed_text(roots, "new\n", "old\n", "old\n")   # publish_to_repo + cascade
    seed_json(roots, {"model": "x"}, {"model": "x"}, {"model": "x"})
    m = mf.load_manifest(manifest_path)
    plan = merge.plan_merge(scan_now(manifest_path), m, ["agents-md"])
    assert plan.actions[0].cascade_target is not None, (
        "test setup must actually exercise the cascade path")

    real_write_target = merge.write_target
    calls: list[Path] = []

    def flaky(path: Path, text: str) -> None:
        calls.append(path)
        if len(calls) == 1:
            real_write_target(path, text)   # primary write succeeds
            return
        raise OSError("disk full on the cascade write")   # cascade fails

    monkeypatch.setattr(merge, "write_target", flaky)
    with pytest.raises(OSError):
        merge.apply_plan(plan, m, backups_dir=roots.state / "backups")

    # The primary (repo) write went through; the cascade (windows) did not.
    assert (roots.repo / "AGENTS.md").read_text(encoding="utf-8") == "new\n"
    assert (roots.windows / "AGENTS.md").read_text(encoding="utf-8") == "old\n"

    # The backup manifest covers BOTH targets, including the one that never
    # got written -- a backup covering only the target that happened to
    # succeed would not be a restorable state.
    backup_dir = roots.state / "backups" / "2026-08-10T14-03-22Z-test01"
    entries = json.loads((backup_dir / "manifest.json").read_text(encoding="utf-8"))
    assert {record["layer"] for record in entries["files"]} == {"repo", "windows"}
    assert len(entries["files"]) == 2

    merge.restore(backup_dir)
    assert (roots.repo / "AGENTS.md").read_text(encoding="utf-8") == "old\n"
    assert (roots.windows / "AGENTS.md").read_text(encoding="utf-8") == "old\n"


# --- CLI -------------------------------------------------------------------

def test_cli_plan_is_dry_run_by_default(scene, capsys):
    manifest_path, roots = scene
    seed_text(roots, "new\n", "old\n", "old\n")
    seed_json(roots, {"model": "x"}, {"model": "x"}, {"model": "x"})
    doc = scan_now(manifest_path)
    code = merge.main(["plan", "--drift-json", json.dumps(doc),
                       "--manifest", str(manifest_path), "--id", "agents-md"])
    assert code == 0
    assert "DRY RUN" in capsys.readouterr().out
    assert (roots.repo / "AGENTS.md").read_text(encoding="utf-8") == "old\n"


def test_cli_requires_at_least_one_id(scene):
    manifest_path, roots = scene
    seed_text(roots, "new\n", "old\n", "old\n")
    seed_json(roots, {"model": "x"}, {"model": "x"}, {"model": "x"})
    doc = scan_now(manifest_path)
    code = merge.main(["apply", "--drift-json", json.dumps(doc),
                       "--manifest", str(manifest_path)])
    assert code == merge.EXIT_NOTHING_SELECTED

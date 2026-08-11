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
"""


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

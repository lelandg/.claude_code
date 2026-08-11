"""Tests for the drift document, atomic writes, the lock, and the scan CLI.

Design: "Deterministic scan"; test cases 1 (no drift) and 15 (interrupted
atomic write).
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import drift  # noqa: E402
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
deny_path_globs = ["**/history.jsonl"]

[[entries]]
id = "agents-md"
policy = "portable_authoritative"
kind = "text"
wsl = "AGENTS.md"
repo = "AGENTS.md"
windows = "AGENTS.md"
"""


@pytest.fixture
def scene(fixture_roots, tmp_path: Path):
    """A manifest wired to the fixture roots. Returns (manifest_path, roots)."""
    text = MANIFEST_TEMPLATE.format(
        wsl=fixture_roots.wsl, repo=fixture_roots.repo,
        windows=fixture_roots.windows, state=fixture_roots.state)
    path = tmp_path / "agent-sync.toml"
    path.write_text(text, encoding="utf-8")
    return path, fixture_roots


def seed(roots, *, wsl=None, repo=None, windows=None) -> None:
    for layer, content in (("wsl", wsl), ("repo", repo), ("windows", windows)):
        if content is not None:
            roots.write(getattr(roots, layer), "AGENTS.md", content)


# --- run ids and fingerprints ---------------------------------------------

def test_run_id_is_deterministic_and_filename_safe():
    run_id = drift.make_run_id(NOW, "3f9a1c")
    assert run_id == "2026-08-10T14-03-22Z-3f9a1c"
    assert "/" not in run_id and ":" not in run_id


# --- atomic writes (design test case 15) -----------------------------------

def test_write_atomic_replaces_content(tmp_path: Path):
    target = tmp_path / "out.json"
    drift.write_atomic(target, "first\n")
    drift.write_atomic(target, "second\n")
    assert target.read_text(encoding="utf-8") == "second\n"


def test_write_atomic_leaves_no_temp_files_behind(tmp_path: Path):
    target = tmp_path / "out.json"
    drift.write_atomic(target, "x\n")
    assert [p.name for p in tmp_path.iterdir()] == ["out.json"]


def test_interrupted_write_preserves_the_previous_file(tmp_path: Path,
                                                       monkeypatch):
    target = tmp_path / "out.json"
    drift.write_atomic(target, "good\n")

    def boom(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(drift.os, "replace", boom)
    with pytest.raises(OSError):
        drift.write_atomic(target, "bad\n")
    assert target.read_text(encoding="utf-8") == "good\n"
    assert [p.name for p in tmp_path.iterdir()] == ["out.json"]


# --- document assembly -----------------------------------------------------

def test_document_validates_against_its_own_schema(scene):
    manifest_path, roots = scene
    seed(roots, wsl="a\n", repo="b\n", windows="b\n")
    doc = scan.run_scan(manifest_path, root_overrides=None, now=NOW,
                        entropy="3f9a1c")
    assert drift.validate_document(doc) == []
    assert doc["drift_schema_version"] == drift.DRIFT_SCHEMA_VERSION
    assert doc["scanner_version"] == drift.SCANNER_VERSION
    assert doc["run_id"] == "2026-08-10T14-03-22Z-3f9a1c"


def test_identical_layers_produce_no_actionable_drift(scene):
    manifest_path, roots = scene
    seed(roots, wsl="same\n", repo="same\n", windows="same\n")
    doc = scan.run_scan(manifest_path, root_overrides=None, now=NOW,
                        entropy="x")
    assert drift.has_actionable(doc) is False
    assert doc["counts"].get("publish_to_repo") is None


def test_wsl_ahead_of_the_baseline_is_actionable(scene):
    manifest_path, roots = scene
    seed(roots, wsl="new\n", repo="old\n", windows="old\n")
    doc = scan.run_scan(manifest_path, root_overrides=None, now=NOW,
                        entropy="x")
    assert drift.has_actionable(doc) is True
    assert doc["counts"]["publish_to_repo"] == 1
    assert doc["items"][0]["id"] == "agents-md"


def test_line_ending_differences_alone_are_not_drift(scene):
    manifest_path, roots = scene
    seed(roots, wsl="a\r\nb\r\n", repo="a\nb\n", windows="a\nb\n")
    doc = scan.run_scan(manifest_path, root_overrides=None, now=NOW,
                        entropy="x")
    assert drift.has_actionable(doc) is False


def test_document_records_layer_fingerprints_for_staleness_checks(scene):
    manifest_path, roots = scene
    seed(roots, wsl="a\n", repo="a\n", windows="a\n")
    doc = scan.run_scan(manifest_path, root_overrides=None, now=NOW,
                        entropy="x")
    assert set(doc["layer_fingerprints"]) == {"wsl", "repo", "windows"}
    assert all(len(v) == 64 for v in doc["layer_fingerprints"].values())


def test_no_secret_value_reaches_the_document(scene, tmp_path: Path):
    manifest_path, roots = scene
    extra = manifest_path.read_text(encoding="utf-8") + """
[[entries]]
id = "mcp"
policy = "portable_authoritative"
kind = "json"
wsl = "mcp.json"
repo = "mcp.json"
"""
    manifest_path.write_text(extra, encoding="utf-8")
    seed(roots, wsl="x\n", repo="x\n", windows="x\n")
    roots.write(roots.wsl, "mcp.json",
                '{"mcpServers": {"gh": {"token": "ghp_LEAKME"}}}')
    doc = scan.run_scan(manifest_path, root_overrides=None, now=NOW,
                        entropy="x")
    assert "ghp_LEAKME" not in json.dumps(doc)
    assert doc["redactions"], "the redaction must be recorded"


def test_a_malformed_file_is_recorded_as_an_item_and_not_copied_again(scene):
    """One malformed file, one record. Error items used to be copied into
    doc["errors"] as well, which made the report list each one twice under a
    heading that counted it once."""
    manifest_path, roots = scene
    manifest_path.write_text(manifest_path.read_text(encoding="utf-8") + """
[[entries]]
id = "mcp"
policy = "portable_authoritative"
kind = "json"
wsl = "mcp.json"
repo = "mcp.json"
""", encoding="utf-8")
    seed(roots, wsl="x\n", repo="x\n", windows="x\n")
    roots.write(roots.wsl, "mcp.json", "{not json")

    doc = scan.run_scan(manifest_path, root_overrides=None, now=NOW,
                        entropy="x")
    error_items = [i for i in doc["items"] if i["classification"] == "error"]
    assert [i["id"] for i in error_items] == ["mcp"]
    assert doc["errors"] == []
    assert drift.validate_document(doc) == []


# --- lock ------------------------------------------------------------------

def test_lock_is_exclusive(fixture_roots):
    with scan.acquire_lock(fixture_roots.state):
        with pytest.raises(scan.LockHeld):
            with scan.acquire_lock(fixture_roots.state):
                pass


def test_lock_is_released_on_exit(fixture_roots):
    with scan.acquire_lock(fixture_roots.state):
        pass
    with scan.acquire_lock(fixture_roots.state):
        pass


# --- CLI -------------------------------------------------------------------

def test_cli_exits_zero_when_there_is_no_drift(scene, capsys):
    manifest_path, roots = scene
    seed(roots, wsl="s\n", repo="s\n", windows="s\n")
    code = scan.main(["--manifest", str(manifest_path)])
    assert code == scan.EXIT_OK


def test_cli_exits_ten_when_drift_exists_and_writes_the_document(scene):
    manifest_path, roots = scene
    seed(roots, wsl="new\n", repo="old\n", windows="old\n")
    out = roots.state / "drift.json"
    code = scan.main(["--manifest", str(manifest_path), "--out", str(out)])
    assert code == scan.EXIT_DRIFT
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert drift.validate_document(doc) == []


def test_cli_exits_twenty_on_a_malformed_manifest(tmp_path: Path):
    bad = tmp_path / "agent-sync.toml"
    bad.write_text("[roots\n", encoding="utf-8")
    assert scan.main(["--manifest", str(bad)]) == scan.EXIT_SCAN_FAILURE


def test_cli_writes_latest_status_json(scene):
    manifest_path, roots = scene
    seed(roots, wsl="s\n", repo="s\n", windows="s\n")
    scan.main(["--manifest", str(manifest_path)])
    status = json.loads(
        (roots.state / "latest-status.json").read_text(encoding="utf-8"))
    assert status["actionable"] is False
    assert status["exit_code"] == scan.EXIT_OK
    assert status["scanner_version"] == drift.SCANNER_VERSION


def test_cli_root_override_flag(scene, tmp_path: Path):
    manifest_path, roots = scene
    alternate = tmp_path / "alt-wsl"
    alternate.mkdir()
    (alternate / "AGENTS.md").write_text("override\n", encoding="utf-8")
    seed(roots, repo="baseline\n", windows="baseline\n")
    out = roots.state / "drift.json"
    scan.main(["--manifest", str(manifest_path), "--out", str(out),
               "--root", f"wsl_home={alternate}"])
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["roots"]["wsl"] == str(alternate)

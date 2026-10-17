"""Tests for sync.py. Every test uses tmp_path homes; none touches a live profile."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import sync  # noqa: E402

SCOPE = """
schema_version = 2
files = ["AGENTS.md", ".claude/CLAUDE.md"]
trees = [{ path = ".claude/instructions", glob = "*.md" }]
derived = [{ path = ".codex/AGENTS.md", from = "AGENTS.md" }]

[[report]]
path = ".claude/settings.json"
fields = ["hooks", "env"]
"""


@pytest.fixture
def env(tmp_path: Path):
    wsl, win, state = tmp_path / "wsl", tmp_path / "win", tmp_path / "state"
    for d in (wsl, win):
        d.mkdir()
    scope_file = tmp_path / "scope.toml"
    scope_file.write_text(SCOPE, encoding="utf-8")
    roots = sync.Roots(wsl=wsl, windows=win, state=state)
    return roots, sync.load_scope(scope_file), scope_file


def put(root: Path, rel: str, text: str, eol: str = "\n") -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(text.replace("\n", eol).encode("utf-8"))
    return p


def by_path(items):
    return {i.path: i for i in items}


def sync_all(roots, scope):
    """Bring every in-scope file to a recorded, equal state."""
    sync.apply(sync.plan(scope, roots), roots)


def test_equal_files_without_baseline_record_one(env):
    roots, scope, _ = env
    put(roots.wsl, "AGENTS.md", "rules\n")
    put(roots.windows, "AGENTS.md", "rules\n", eol="\r\n")
    item = by_path(sync.plan(scope, roots))["AGENTS.md"]
    assert item.action == "record"
    sync.apply([item], roots)
    assert (roots.state / "sync" / "AGENTS.md").read_text() == "rules\n"
    assert by_path(sync.plan(scope, roots))["AGENTS.md"].action == "ok"


def test_differing_files_without_baseline_conflict(env):
    roots, scope, _ = env
    put(roots.wsl, "AGENTS.md", "a\n")
    put(roots.windows, "AGENTS.md", "b\n")
    assert by_path(sync.plan(scope, roots))["AGENTS.md"].action == "conflict"


def test_wsl_change_copies_to_windows_keeping_crlf(env):
    roots, scope, _ = env
    put(roots.wsl, "AGENTS.md", "v1\n")
    put(roots.windows, "AGENTS.md", "v1\n", eol="\r\n")
    sync_all(roots, scope)
    put(roots.wsl, "AGENTS.md", "v2\nmore\n")
    item = by_path(sync.plan(scope, roots))["AGENTS.md"]
    assert item.action == "to_windows"
    sync.apply([item], roots)
    assert (roots.windows / "AGENTS.md").read_bytes() == b"v2\r\nmore\r\n"
    assert by_path(sync.plan(scope, roots))["AGENTS.md"].action == "ok"


def test_windows_change_copies_to_wsl(env):
    roots, scope, _ = env
    put(roots.wsl, ".claude/CLAUDE.md", "v1\n")
    put(roots.windows, ".claude/CLAUDE.md", "v1\n")
    sync_all(roots, scope)
    put(roots.windows, ".claude/CLAUDE.md", "v2 from windows\n", eol="\r\n")
    item = by_path(sync.plan(scope, roots))[".claude/CLAUDE.md"]
    assert item.action == "to_wsl"
    sync.apply([item], roots)
    assert (roots.wsl / ".claude/CLAUDE.md").read_bytes() == b"v2 from windows\n"


def test_both_changed_is_conflict_and_apply_skips_it(env):
    roots, scope, _ = env
    put(roots.wsl, "AGENTS.md", "v1\n")
    put(roots.windows, "AGENTS.md", "v1\n")
    sync_all(roots, scope)
    put(roots.wsl, "AGENTS.md", "wsl edit\n")
    put(roots.windows, "AGENTS.md", "win edit\n")
    item = by_path(sync.plan(scope, roots))["AGENTS.md"]
    assert item.action == "conflict"
    done = sync.apply([item], roots)
    assert done == []
    assert (roots.wsl / "AGENTS.md").read_text() == "wsl edit\n"
    assert (roots.windows / "AGENTS.md").read_text() == "win edit\n"


def test_both_changed_identically_records_baseline(env):
    roots, scope, _ = env
    put(roots.wsl, "AGENTS.md", "v1\n")
    put(roots.windows, "AGENTS.md", "v1\n")
    sync_all(roots, scope)
    put(roots.wsl, "AGENTS.md", "same\n")
    put(roots.windows, "AGENTS.md", "same\n", eol="\r\n")
    assert by_path(sync.plan(scope, roots))["AGENTS.md"].action == "record"


def test_take_resolves_conflict(env):
    roots, scope, _ = env
    put(roots.wsl, "AGENTS.md", "a\n")
    put(roots.windows, "AGENTS.md", "b\n", eol="\r\n")
    items = sync.plan(scope, roots)
    sync.apply(items, roots, take={"AGENTS.md": "windows"})
    assert (roots.wsl / "AGENTS.md").read_text() == "b\n"
    assert by_path(sync.plan(scope, roots))["AGENTS.md"].action == "ok"


def test_tree_new_file_on_one_side_is_copied(env):
    roots, scope, _ = env
    put(roots.windows, ".claude/instructions/new.md", "fresh\n")
    item = by_path(sync.plan(scope, roots))[".claude/instructions/new.md"]
    assert item.action == "to_wsl"
    sync.apply([item], roots)
    assert (roots.wsl / ".claude/instructions/new.md").read_text() == "fresh\n"


def test_tree_glob_ignores_other_files(env):
    roots, scope, _ = env
    put(roots.wsl, ".claude/instructions/notes.txt", "x\n")
    assert ".claude/instructions/notes.txt" not in by_path(sync.plan(scope, roots))


def test_delete_on_one_side_propagates(env):
    roots, scope, _ = env
    put(roots.wsl, ".claude/instructions/old.md", "x\n")
    put(roots.windows, ".claude/instructions/old.md", "x\n")
    sync_all(roots, scope)
    (roots.wsl / ".claude/instructions/old.md").unlink()
    item = by_path(sync.plan(scope, roots))[".claude/instructions/old.md"]
    assert item.action == "delete_windows"
    sync.apply([item], roots)
    assert not (roots.windows / ".claude/instructions/old.md").exists()
    assert not (roots.state / "sync" / ".claude/instructions/old.md").exists()
    assert ".claude/instructions/old.md" not in by_path(sync.plan(scope, roots))


def test_delete_versus_edit_is_conflict(env):
    roots, scope, _ = env
    put(roots.wsl, ".claude/instructions/old.md", "x\n")
    put(roots.windows, ".claude/instructions/old.md", "x\n")
    sync_all(roots, scope)
    (roots.wsl / ".claude/instructions/old.md").unlink()
    put(roots.windows, ".claude/instructions/old.md", "edited\n")
    assert by_path(sync.plan(scope, roots))[".claude/instructions/old.md"].action == "conflict"


def test_every_write_and_delete_is_backed_up(env):
    roots, scope, _ = env
    put(roots.wsl, "AGENTS.md", "v1\n")
    put(roots.windows, "AGENTS.md", "v1\n")
    sync_all(roots, scope)
    put(roots.wsl, "AGENTS.md", "v2\n")
    sync.apply(sync.plan(scope, roots), roots)
    backups = list((roots.state / "backups").rglob("AGENTS.md"))
    assert [b.read_text() for b in backups if "windows" in b.parts] == ["v1\n"]


def test_derived_regenerated_from_canonical_and_symlink_left_alone(env):
    roots, scope, _ = env
    put(roots.wsl, "AGENTS.md", "canon\n")
    put(roots.windows, "AGENTS.md", "canon\n", eol="\r\n")
    (roots.wsl / ".codex").mkdir()
    os.symlink(roots.wsl / "AGENTS.md", roots.wsl / ".codex/AGENTS.md")
    put(roots.windows, ".codex/AGENTS.md", "stale copy\n", eol="\r\n")
    items = by_path(sync.plan(scope, roots))
    assert items[".codex/AGENTS.md"].action == "regen_windows"
    sync.apply(list(items.values()), roots)
    assert (roots.windows / ".codex/AGENTS.md").read_bytes() == b"canon\r\n"
    assert (roots.wsl / ".codex/AGENTS.md").is_symlink()
    assert by_path(sync.plan(scope, roots))[".codex/AGENTS.md"].action == "ok"


def test_derived_follows_pending_canonical_change(env):
    roots, scope, _ = env
    put(roots.wsl, "AGENTS.md", "v1\n")
    put(roots.windows, "AGENTS.md", "v1\n")
    put(roots.windows, ".codex/AGENTS.md", "v1\n")
    put(roots.wsl, ".codex/AGENTS.md", "v1\n")
    sync_all(roots, scope)
    put(roots.windows, "AGENTS.md", "v2\n")
    items = sync.plan(scope, roots)
    assert by_path(items)[".codex/AGENTS.md"].action == "regen_both"
    sync.apply(items, roots)
    assert (roots.wsl / ".codex/AGENTS.md").read_text() == "v2\n"
    assert (roots.windows / ".codex/AGENTS.md").read_text() == "v2\n"


def test_derived_blocked_while_canonical_conflicts(env):
    roots, scope, _ = env
    put(roots.wsl, "AGENTS.md", "a\n")
    put(roots.windows, "AGENTS.md", "b\n")
    put(roots.windows, ".codex/AGENTS.md", "old\n")
    assert by_path(sync.plan(scope, roots))[".codex/AGENTS.md"].action == "blocked"


def test_never_writes_through_a_symlinked_file_target(env, tmp_path):
    roots, scope, _ = env
    elsewhere = put(tmp_path, "elsewhere.md", "v1\n")
    put(roots.wsl, ".claude/CLAUDE.md", "v1\n")
    (roots.windows / ".claude").mkdir()
    os.symlink(elsewhere, roots.windows / ".claude/CLAUDE.md")
    sync_all(roots, scope)
    put(roots.wsl, ".claude/CLAUDE.md", "v2\n")
    item = by_path(sync.plan(scope, roots))[".claude/CLAUDE.md"]
    with pytest.raises(sync.SyncError, match="symlink"):
        sync.apply([item], roots)
    assert elsewhere.read_text() == "v1\n"


def test_report_names_differing_keys_never_values(env):
    roots, scope, _ = env
    put(roots.wsl, ".claude/settings.json", json.dumps(
        {"hooks": {"PreToolUse": [1], "Stop": [1]}, "env": {"TOKEN": "s3cret-wsl", "A": "1"}}))
    put(roots.windows, ".claude/settings.json", json.dumps(
        {"hooks": {"PreToolUse": [2], "Stop": [1]}, "env": {"TOKEN": "s3cret-win", "A": "1"}}))
    items = [i for i in sync.plan(scope, roots) if i.kind == "report"]
    text = " ".join(f"{i.path} {i.detail}" for i in items)
    assert "hooks" in text and "PreToolUse" in text and "TOKEN" in text
    assert "Stop" not in text
    assert "s3cret" not in text
    assert all(i.action == "differs" for i in items)


def test_main_exit_codes(env, capsys):
    roots, scope, scope_file = env
    args = ["--scope", str(scope_file), "--wsl-home", str(roots.wsl),
            "--windows-home", str(roots.windows), "--state", str(roots.state)]
    put(roots.wsl, "AGENTS.md", "x\n")
    put(roots.windows, "AGENTS.md", "x\n")
    assert sync.main(["check", *args]) == 10
    assert sync.main(["apply", *args]) == 0
    assert sync.main(["check", *args]) == 0
    put(roots.wsl, "AGENTS.md", "y\n")
    put(roots.windows, "AGENTS.md", "z\n")
    assert sync.main(["check", *args]) == 10
    assert sync.main(["apply", *args]) == 10
    assert sync.main(["apply", "--take", "wsl", "AGENTS.md", *args]) == 0
    assert (roots.windows / "AGENTS.md").read_text() == "y\n"
    assert sync.main(["check", "--scope", str(roots.wsl / "missing.toml")]) == 20


def test_diff_shows_both_sides_against_baseline(env, capsys):
    roots, scope, scope_file = env  # noqa: F841
    put(roots.wsl, "AGENTS.md", "base\n")
    put(roots.windows, "AGENTS.md", "base\n")
    sync_all(roots, scope)
    put(roots.wsl, "AGENTS.md", "base\nwsl line\n")
    put(roots.windows, "AGENTS.md", "base\nwin line\n")
    args = ["--scope", str(scope_file), "--wsl-home", str(roots.wsl),
            "--windows-home", str(roots.windows), "--state", str(roots.state)]
    assert sync.main(["diff", "AGENTS.md", *args]) == 0
    out = capsys.readouterr().out
    assert "+wsl line" in out and "+win line" in out


def test_shipped_scope_file_loads():
    scope = sync.load_scope(Path(str(sync.__file__)).resolve().parents[2] / "config" / "agent-sync.toml")
    assert ".config/agents/AGENTS.md" in scope.files
    assert all(d.source in scope.files for d in scope.derived)


def test_reparse_point_counts_as_link(monkeypatch, tmp_path):
    p = put(tmp_path, "x.md", "x\n")

    class St:
        st_file_attributes = 0x400
        st_reparse_tag = sync.IO_REPARSE_TAG_LX_SYMLINK

    monkeypatch.setattr(sync.os, "lstat", lambda _p: St())
    assert sync._is_link(p)


def test_unfollowable_link_is_never_regenerated_or_written(env, monkeypatch):
    roots, scope, _ = env
    put(roots.wsl, "AGENTS.md", "canon\n")
    put(roots.windows, "AGENTS.md", "canon\n")
    (roots.wsl / ".codex").mkdir()
    lx = roots.wsl / ".codex/AGENTS.md"  # stands in for an LX symlink seen from Windows
    real_is_link = sync._is_link
    monkeypatch.setattr(sync, "_is_link", lambda p: p == lx or real_is_link(p))
    item = by_path(sync.plan(scope, roots))[".codex/AGENTS.md"]
    assert item.action == "ok"
    sync.apply([item], roots)
    assert not lx.exists()
    with pytest.raises(sync.SyncError, match="cannot follow"):
        sync.read_text(lx)


def test_other_reparse_points_are_not_links(monkeypatch, tmp_path):
    p = put(tmp_path, "x.md", "x\n")

    class St:  # e.g. a OneDrive placeholder
        st_file_attributes = 0x400
        st_reparse_tag = 0x9000001A

    monkeypatch.setattr(sync.os, "lstat", lambda _p: St())
    assert not sync._is_link(p)


def _args(roots, scope_file):
    return ["--scope", str(scope_file), "--wsl-home", str(roots.wsl),
            "--windows-home", str(roots.windows), "--state", str(roots.state)]


def test_diff_refuses_report_only_paths(env, capsys):
    roots, _, scope_file = env
    put(roots.wsl, ".claude/settings.json", '{"env": {"TOKEN": "s3cret"}}')
    put(roots.windows, ".claude/settings.json", "{}")
    assert sync.main(["diff", ".claude/settings.json", *_args(roots, scope_file)]) == 20
    assert "s3cret" not in capsys.readouterr().out


def test_failed_apply_still_reports_completed_writes(env, capsys, tmp_path):
    roots, scope, scope_file = env
    put(roots.wsl, "AGENTS.md", "v1\n")
    put(roots.windows, "AGENTS.md", "v1\n")
    elsewhere = put(tmp_path, "elsewhere.md", "v1\n")
    put(roots.wsl, ".claude/CLAUDE.md", "v1\n")
    (roots.windows / ".claude").mkdir()
    os.symlink(elsewhere, roots.windows / ".claude/CLAUDE.md")
    sync_all(roots, scope)
    put(roots.wsl, "AGENTS.md", "v2\n")
    put(roots.wsl, ".claude/CLAUDE.md", "v2\n")
    assert sync.main(["apply", *_args(roots, scope_file)]) == 20
    assert "wrote   windows AGENTS.md" in capsys.readouterr().out


def test_take_on_source_also_regenerates_derived(env):
    roots, _, scope_file = env
    put(roots.wsl, "AGENTS.md", "a\n")
    put(roots.windows, "AGENTS.md", "b\n")
    put(roots.windows, ".codex/AGENTS.md", "old\n")
    assert sync.main(["apply", "--take", "wsl", "AGENTS.md", *_args(roots, scope_file)]) == 0
    assert (roots.windows / ".codex/AGENTS.md").read_text() == "a\n"

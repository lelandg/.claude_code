"""Tests for normalization, path tokenization, and fingerprints.

Design: "Deterministic scan" steps 5-6, and test case 11 (WSL-to-Windows
executable and path adaptation).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import manifest as mf  # noqa: E402
import normalize as nz  # noqa: E402

ROOTS = mf.Roots(
    wsl_home=Path("/home/leland"),
    repo=Path("/mnt/d/Documents/Code/GitHub/.claude_code"),
    windows_home=Path("/mnt/c/Users/aboog"),
)


# --- text ------------------------------------------------------------------

def test_normalize_text_converts_crlf_and_cr_to_lf():
    assert nz.normalize_text("a\r\nb\rc\n") == "a\nb\nc\n"


def test_normalize_text_strips_trailing_whitespace_per_line():
    assert nz.normalize_text("a   \nb\t\n") == "a\nb\n"


def test_normalize_text_ends_with_exactly_one_newline():
    assert nz.normalize_text("a") == "a\n"
    assert nz.normalize_text("a\n\n\n") == "a\n"


def test_normalize_text_strips_bom():
    assert nz.normalize_text("\ufeffhello") == "hello\n"


def test_normalize_text_is_idempotent():
    once = nz.normalize_text("a\r\n  b  \r\n")
    assert nz.normalize_text(once) == once


# --- json / toml -----------------------------------------------------------

def test_normalize_json_sorts_keys_and_reindents():
    a = nz.normalize_json('{"b": 1, "a": {"d": 2, "c": 3}}')
    b = nz.normalize_json('{"a":{"c":3,"d":2},"b":1}')
    assert a == b
    assert a.endswith("\n")
    assert a.splitlines()[1].startswith('  "a"')


def test_normalize_json_reports_location_without_content():
    with pytest.raises(nz.NormalizeError) as excinfo:
        nz.normalize_json('{"token": "hunter2",,}')
    message = str(excinfo.value)
    assert "line" in message and "column" in message
    assert "hunter2" not in message


def test_normalize_toml_produces_the_same_surface_as_json():
    from_toml = nz.normalize_toml('b = 1\n[a]\nc = 3\nd = 2\n')
    from_json = nz.normalize_json('{"a": {"c": 3, "d": 2}, "b": 1}')
    assert from_toml == from_json


def test_normalize_toml_reports_location_without_content():
    with pytest.raises(nz.NormalizeError) as excinfo:
        nz.normalize_toml('[bad\npassword = "hunter2"\n')
    assert "hunter2" not in str(excinfo.value)


def test_normalize_toml_renders_dates_as_strings():
    out = nz.normalize_toml('when = 2026-08-10\n')
    assert '"2026-08-10"' in out


def test_normalize_for_kind_dispatches():
    assert nz.normalize_for_kind("a\r\n", "text") == "a\n"
    assert nz.normalize_for_kind('{"a":1}', "json") == nz.normalize_json('{"a":1}')
    assert nz.normalize_for_kind("a = 1\n", "toml") == nz.normalize_json('{"a":1}')
    assert nz.normalize_for_kind("x\r\n", "tree") == "x\n"


# --- path tokenization -----------------------------------------------------

def test_tokenize_replaces_wsl_home_with_home_token():
    out = nz.tokenize_paths("see /home/leland/.claude/tools/guard.py now", ROOTS)
    assert out == "see {HOME}/.claude/tools/guard.py now"


def test_tokenize_replaces_windows_home_in_all_three_spellings():
    for spelling in ("/mnt/c/Users/aboog", "C:\\Users\\aboog", "C:/Users/aboog"):
        out = nz.tokenize_paths(f"path {spelling}/.claude/CLAUDE.md", ROOTS)
        assert out == "path {HOME}/.claude/CLAUDE.md", spelling


def test_tokenize_replaces_repo_before_its_parent_mount():
    out = nz.tokenize_paths(
        "/mnt/d/Documents/Code/GitHub/.claude_code/claude/skills", ROOTS)
    assert out == "{REPO}/claude/skills"


def test_tokenize_normalizes_backslashes_inside_a_matched_path():
    out = nz.tokenize_paths("C:\\Users\\aboog\\.claude\\settings.json", ROOTS)
    assert out == "{HOME}/.claude/settings.json"


def test_tokenize_leaves_unrelated_absolute_paths_alone():
    assert nz.tokenize_paths("/usr/bin/python3", ROOTS) == "/usr/bin/python3"


# --- path rendering (the Windows adaptation of design test case 11) ---------

def test_render_paths_to_wsl_layer():
    out = nz.render_paths("{HOME}/.claude/x.md", "wsl", ROOTS)
    assert out == "/home/leland/.claude/x.md"


def test_render_paths_to_repo_layer_uses_the_wsl_spelling():
    # The repo is a mirror of WSL intent, so publishing round-trips exactly.
    out = nz.render_paths("{HOME}/.claude/x.md", "repo", ROOTS)
    assert out == "/home/leland/.claude/x.md"


def test_render_paths_falls_back_when_a_root_is_not_a_mount(tmp_path: Path):
    roots = mf.Roots(wsl_home=tmp_path / "wsl", repo=tmp_path / "repo",
                     windows_home=tmp_path / "win")
    out = nz.render_paths("{HOME}/a.md", "windows", roots)
    assert "{HOME}" not in out
    assert out.endswith("a.md")


def test_render_paths_to_windows_layer_uses_drive_and_backslashes():
    out = nz.render_paths("{HOME}/.claude/x.md", "windows", ROOTS)
    assert out == "C:\\Users\\aboog\\.claude\\x.md"


def test_render_repo_token_for_windows_layer():
    out = nz.render_paths("{REPO}/claude/skills", "windows", ROOTS)
    assert out == "D:\\Documents\\Code\\GitHub\\.claude_code\\claude\\skills"


def test_tokenize_then_render_round_trips_wsl_to_windows():
    wsl_text = "hook: /home/leland/.claude/tools/guard.py --strict\n"
    tokenized = nz.tokenize_paths(wsl_text, ROOTS)
    assert nz.render_paths(tokenized, "windows", ROOTS) == (
        "hook: C:\\Users\\aboog\\.claude\\tools\\guard.py --strict\n")


def test_wsl_mount_to_windows_converts_drive_letters():
    assert nz.wsl_mount_to_windows(Path("/mnt/c/Users/aboog")) == "C:\\Users\\aboog"
    assert nz.wsl_mount_to_windows(Path("/mnt/d/x/y")) == "D:\\x\\y"


def test_wsl_mount_to_windows_returns_none_for_non_mount_paths():
    assert nz.wsl_mount_to_windows(Path("/home/leland")) is None


# --- portability warnings --------------------------------------------------

def test_portability_warnings_flags_wsl_only_literals():
    warnings = nz.portability_warnings(
        "run /usr/bin/python3 and /home/other/.venv_linux/bin/x")
    assert any("/usr/" in w for w in warnings)
    assert any("/home/" in w for w in warnings)


def test_portability_warnings_are_quiet_for_tokenized_text():
    assert nz.portability_warnings("{HOME}/.claude/x.md and {REPO}/y") == []


# --- fingerprints ----------------------------------------------------------

def test_fingerprint_is_stable_and_hex():
    fp = nz.fingerprint("hello\n")
    assert fp == nz.fingerprint("hello\n")
    assert len(fp) == 64
    assert all(c in "0123456789abcdef" for c in fp)


def test_fingerprint_differs_for_different_content():
    assert nz.fingerprint("a\n") != nz.fingerprint("b\n")


def test_short_truncates_and_handles_none():
    assert nz.short("a" * 64) == "a" * 12
    assert nz.short(None) == "-"

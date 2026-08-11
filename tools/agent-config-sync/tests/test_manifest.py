"""Tests for the manifest loader and the minimal JSON-Schema validator.

Design: Docs/plans/2026-08-08-wsl-authoritative-agent-config-sync-design.md
sections "Ownership and merge policy" and "Deterministic scan" step 1.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import manifest as mf  # noqa: E402
import schema as sch  # noqa: E402


# --------------------------------------------------------------------------
# schema.py
# --------------------------------------------------------------------------

PERSON = {
    "type": "object",
    "required": ["name", "age"],
    "properties": {
        "name": {"type": "string"},
        "age": {"type": "integer"},
        "role": {"type": "string", "enum": ["admin", "user"]},
        "tags": {"type": "array", "items": {"type": "string"}},
    },
}


def test_schema_accepts_valid_instance():
    assert sch.validate({"name": "a", "age": 3, "role": "admin"}, PERSON) == []


def test_schema_reports_missing_required_field():
    errors = sch.validate({"name": "a"}, PERSON)
    assert errors == ["$: missing required property 'age'"]


def test_schema_reports_wrong_type_with_path():
    errors = sch.validate({"name": "a", "age": "three"}, PERSON)
    assert errors == ["$.age: expected integer, got str"]


def test_schema_reports_bad_enum_value():
    errors = sch.validate({"name": "a", "age": 1, "role": "root"}, PERSON)
    assert errors == ["$.role: 'root' is not one of ['admin', 'user']"]


def test_schema_validates_array_items_by_index():
    errors = sch.validate({"name": "a", "age": 1, "tags": ["x", 2]}, PERSON)
    assert errors == ["$.tags[1]: expected string, got int"]


def test_schema_does_not_leak_values_of_unknown_long_strings():
    # Error text quotes only enum mismatches, never arbitrary string values.
    errors = sch.validate({"name": 1234567890, "age": 1}, PERSON)
    assert errors == ["$.name: expected string, got int"]
    assert "1234567890" not in errors[0]


# --------------------------------------------------------------------------
# manifest.py
# --------------------------------------------------------------------------

MINIMAL = """
schema_version = 1

[roots]
wsl_home = "/fixture/wsl"
repo = "/fixture/repo"
windows_home = "/fixture/win"

[state]
dir = "/fixture/state"

[secrets]
deny_key_patterns = ["(?i)token"]
deny_path_globs = [".credentials.json"]

[[entries]]
id = "agents-md"
policy = "portable_authoritative"
kind = "text"
wsl = ".config/agents/AGENTS.md"
repo = "config/agents/AGENTS.md"
windows = ".config/agents/AGENTS.md"

[[entries]]
id = "claude-settings"
policy = "portable_authoritative"
kind = "json"
wsl = ".claude/settings.json"
repo = "claude/settings.json"
windows = ".claude/settings.json"

[entries.fields]
"model" = "portable_authoritative"
"statusLine.command" = "platform_overlay"
"""


def write_manifest(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "agent-sync.toml"
    path.write_text(text, encoding="utf-8")
    return path


def test_load_manifest_parses_roots_and_entries(tmp_path: Path):
    m = mf.load_manifest(write_manifest(tmp_path, MINIMAL))
    assert m.schema_version == 1
    assert m.roots.wsl_home == Path("/fixture/wsl")
    assert m.roots.windows_home == Path("/fixture/win")
    assert m.state_dir == Path("/fixture/state")
    assert [e.id for e in m.entries] == ["agents-md", "claude-settings"]


def test_load_manifest_parses_field_level_ownership(tmp_path: Path):
    m = mf.load_manifest(write_manifest(tmp_path, MINIMAL))
    entry = m.entry("claude-settings")
    assert entry.fields["statusLine.command"] == "platform_overlay"
    assert entry.fields["model"] == "portable_authoritative"


def test_root_overrides_replace_declared_roots(tmp_path: Path):
    m = mf.load_manifest(
        write_manifest(tmp_path, MINIMAL),
        root_overrides={"wsl_home": str(tmp_path / "alt")},
    )
    assert m.roots.wsl_home == tmp_path / "alt"


def test_unknown_policy_is_rejected(tmp_path: Path):
    bad = MINIMAL.replace('policy = "portable_authoritative"\nkind = "text"',
                          'policy = "whatever"\nkind = "text"', 1)
    with pytest.raises(mf.ManifestError) as excinfo:
        mf.load_manifest(write_manifest(tmp_path, bad))
    assert "whatever" in str(excinfo.value)


def test_duplicate_entry_id_is_rejected(tmp_path: Path):
    dup = MINIMAL + """
[[entries]]
id = "agents-md"
policy = "portable_additive"
kind = "text"
wsl = "x"
"""
    with pytest.raises(mf.ManifestError) as excinfo:
        mf.load_manifest(write_manifest(tmp_path, dup))
    assert "duplicate" in str(excinfo.value).lower()


def test_future_schema_version_is_rejected(tmp_path: Path):
    future = MINIMAL.replace("schema_version = 1", "schema_version = 99", 1)
    with pytest.raises(mf.ManifestError):
        mf.load_manifest(write_manifest(tmp_path, future))


def test_malformed_toml_error_names_the_file_not_its_contents(tmp_path: Path):
    path = write_manifest(tmp_path, 'schema_version = 1\n[roots\nsecret = "hunter2"\n')
    with pytest.raises(mf.ManifestError) as excinfo:
        mf.load_manifest(path)
    message = str(excinfo.value)
    assert "agent-sync.toml" in message
    assert "line" in message and "column" in message
    assert "hunter2" not in message


def test_windows_home_may_be_absent(tmp_path: Path):
    no_win = MINIMAL.replace('windows_home = "/fixture/win"\n', "")
    m = mf.load_manifest(write_manifest(tmp_path, no_win))
    assert m.roots.windows_home is None


def test_real_repository_manifest_loads(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[3]
    m = mf.load_manifest(repo_root / "config" / "agent-sync.toml")
    assert m.schema_version == mf.MANIFEST_SCHEMA_VERSION
    ids = {e.id for e in m.entries}
    assert {"agents-md", "claude-md", "claude-instructions",
            "claude-settings", "claude-plugins", "claude-mcp"} <= ids


def test_invalid_field_policy_is_rejected(tmp_path: Path):
    bad = MINIMAL.replace(
        '"statusLine.command" = "platform_overlay"',
        '"statusLine.command" = "portable_authoritatve"', 1)
    with pytest.raises(mf.ManifestError) as excinfo:
        mf.load_manifest(write_manifest(tmp_path, bad))
    message = str(excinfo.value)
    assert "claude-settings" in message
    assert "statusLine.command" in message


def test_missing_state_table_is_rejected(tmp_path: Path):
    no_state = MINIMAL.replace('[state]\ndir = "/fixture/state"\n\n', "")
    with pytest.raises(mf.ManifestError) as excinfo:
        mf.load_manifest(write_manifest(tmp_path, no_state))
    assert "state.dir" in str(excinfo.value)

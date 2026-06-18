from pathlib import Path

import disk_doctor_core as core

RULES = Path(__file__).resolve().parent.parent / "rules"


def test_linux_rule_pack_is_valid():
    missing = core.validate_rule_pack(RULES / "linux.md")
    assert missing == []


def test_malformed_pack_reports_missing_sections(tmp_path):
    bad = tmp_path / "bad.md"
    bad.write_text("# Bad rule pack\n\nNothing useful here.\n")
    missing = core.validate_rule_pack(bad)
    assert set(missing) == set(core.REQUIRED_RULE_SECTIONS)


def test_macos_rule_pack_is_valid():
    assert core.validate_rule_pack(RULES / "macos.md") == []


def test_windows_rule_pack_is_valid():
    assert core.validate_rule_pack(RULES / "windows.md") == []

"""Tests for the Windows PowerShell script that render.py emits.

Decision (Leland, 2026-08-14): Windows-side plugin actions also land in a
.ps1 file so the report can point at one runnable artifact by its Windows
name. Files consumed on Windows use Windows paths only; the D: drive and
/mnt/d are the same storage, so the WSL-side renderer can write the file
directly into the repo.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import render as rd  # noqa: E402


def plugin_item(classification: str, item_id: str, path: str, detail: str) -> dict:
    return {"id": item_id, "entry_id": "claude-plugins", "kind": "plugins",
            "classification": classification, "severity": "review",
            "policy": "portable_authoritative", "path": path, "detail": detail}


def doc_with(items: list[dict], repo: str = "/repo") -> dict:
    return {
        "drift_schema_version": 1,
        "run_id": "2026-08-14T19-38-33Z-3af1c2",
        "generated_at": "2026-08-14T19:38:33+00:00",
        "scanner_version": "1.0.0",
        "manifest_version": 1,
        "roots": {"wsl": "/home/leland", "repo": repo,
                  "windows": "/mnt/c/Users/winuser"},
        "layer_fingerprints": {"wsl": "a" * 64, "repo": "b" * 64,
                               "windows": "c" * 64},
        "counts": {},
        "items": items,
        "errors": [],
        "redactions": [],
    }


WINDOWS_ACTIONS = [
    plugin_item("plugin_missing",
                "claude-plugins:blueprint@owainlewis-blueprint#missing:windows",
                "blueprint@owainlewis-blueprint",
                "Desired plugin is not installed on windows. Install it with "
                "the native manager: claude plugin install "
                "blueprint@owainlewis-blueprint"),
    plugin_item("plugin_enabled_differs",
                "claude-plugins:serena@claude-plugins-official#enabled:windows",
                "serena@claude-plugins-official",
                "Record says enabled=True, windows says enabled=False. "
                "Reconcile with: claude plugin enable "
                "serena@claude-plugins-official"),
    plugin_item("plugin_version_differs",
                "claude-plugins:superpowers@claude-plugins-official#version",
                "superpowers@claude-plugins-official",
                "wsl has 6.2.0, windows has 5.1.0. The newer build is "
                "preserved; upgrade windows with: claude plugin update "
                "superpowers@claude-plugins-official"),
]

SKIPPED_ACTIONS = [
    plugin_item("plugin_enabled_differs",
                "claude-plugins:canva@claude-plugins-official#enabled:wsl",
                "canva@claude-plugins-official",
                "Record says enabled=True, wsl says enabled=False. Reconcile "
                "with: claude plugin enable canva@claude-plugins-official"),
    plugin_item("plugin_extra",
                "claude-plugins:stripe@claude-plugins-official",
                "stripe@claude-plugins-official",
                "Installed natively but absent from the portable record."),
]


REMOVAL_ACTIONS = [
    plugin_item("plugin_removed",
                "claude-plugins:hookify@claude-plugins-official",
                "hookify@claude-plugins-official",
                "Recorded as desired but absent from WSL, the authority. "
                "Approving this id removes it from the portable record and "
                "proposes: claude plugin uninstall "
                "hookify@claude-plugins-official"),
    plugin_item("plugin_removed",
                "claude-plugins:ghost@claude-plugins-official",
                "ghost@claude-plugins-official",
                "Recorded as desired but absent from WSL, the authority. "
                "Approving this id removes it from the portable record."),
]


class TestWindowsScript:
    def test_uninstalls_land_in_the_script_but_record_only_removals_do_not(self):
        script = rd.windows_script(doc_with(WINDOWS_ACTIONS + REMOVAL_ACTIONS))
        assert script is not None
        assert ("claude plugin uninstall hookify@claude-plugins-official"
                in script)
        assert "ghost" not in script

    def test_enable_mismatch_follows_the_record_direction(self):
        # Record wants the plugin DISABLED, Windows has it enabled: the
        # script must disable, not re-assert the drift with an enable.
        item = plugin_item(
            "plugin_enabled_differs",
            "claude-plugins:mintlify@claude-plugins-official#enabled:windows",
            "mintlify@claude-plugins-official",
            "Record says enabled=False, windows says enabled=True. "
            "Reconcile with: claude plugin disable "
            "mintlify@claude-plugins-official")
        script = rd.windows_script(doc_with([item]))
        assert script is not None
        assert ("claude plugin disable mintlify@claude-plugins-official"
                in script)
        assert "claude plugin enable" not in script

    def test_selects_only_windows_side_actions(self):
        script = rd.windows_script(doc_with(WINDOWS_ACTIONS + SKIPPED_ACTIONS))
        assert script is not None
        assert "claude plugin install blueprint@owainlewis-blueprint" in script
        assert "claude plugin enable serena@claude-plugins-official" in script
        assert "claude plugin update superpowers@claude-plugins-official" in script
        assert "canva" not in script
        assert "stripe" not in script

    def test_names_the_run_id(self):
        script = rd.windows_script(doc_with(WINDOWS_ACTIONS))
        assert script is not None
        assert "2026-08-14T19-38-33Z-3af1c2" in script

    def test_none_when_no_windows_actions(self):
        assert rd.windows_script(doc_with(SKIPPED_ACTIONS)) is None
        assert rd.windows_script(doc_with([])) is None

    def test_uses_crlf_line_endings(self):
        script = rd.windows_script(doc_with(WINDOWS_ACTIONS))
        assert script is not None
        assert "\r\n" in script
        # No bare-LF lines: stripping CRLF leaves no stray carriage returns
        # and joining back with CRLF reproduces the script exactly.
        assert script == "\r\n".join(script.split("\r\n"))
        assert "\n" not in script.replace("\r\n", "")


class TestWindowsPath:
    def test_converts_mnt_paths_to_drive_letters(self):
        assert (rd.windows_path("/mnt/d/Documents/Code/GitHub/.claude_code")
                == "D:\\Documents\\Code\\GitHub\\.claude_code")

    def test_non_mnt_paths_have_no_windows_name(self):
        assert rd.windows_path("/home/leland/x") is None


class TestReportReference:
    def test_report_names_the_script_when_given(self):
        doc = doc_with(WINDOWS_ACTIONS)
        out = rd.render_markdown(doc, rd.empty_analysis(),
                                 windows_script_ref="D:\\repo\\Notes\\scripts\\x.ps1")
        assert "D:\\repo\\Notes\\scripts\\x.ps1" in out

    def test_report_has_no_script_section_without_ref(self):
        doc = doc_with(WINDOWS_ACTIONS)
        out = rd.render_markdown(doc, rd.empty_analysis())
        assert "Windows script" not in out


class TestMainIntegration:
    def test_main_writes_script_and_references_it(self, tmp_path):
        import json
        repo = tmp_path / "repo"
        repo.mkdir()
        state = tmp_path / "state"
        doc = doc_with(WINDOWS_ACTIONS, repo=str(repo))
        drift = tmp_path / "drift.json"
        drift.write_text(json.dumps(doc), encoding="utf-8")

        rc = rd.main(["--drift", str(drift), "--state-dir", str(state),
                      "--no-model"])
        assert rc == 0

        script_path = (repo / "Notes" / "scripts"
                       / "agent-config-2026-08-14T19-38-33Z-3af1c2.ps1")
        assert script_path.exists()
        content = script_path.read_bytes().decode("utf-8")
        assert "claude plugin install blueprint@owainlewis-blueprint" in content
        assert "\r\n" in content

        report = (state / "latest-report.md").read_text(encoding="utf-8")
        # tmp repo is not under /mnt, so the reference falls back to the
        # native path of the written file.
        assert str(script_path) in report

    def test_main_writes_no_script_without_windows_actions(self, tmp_path):
        import json
        repo = tmp_path / "repo"
        repo.mkdir()
        state = tmp_path / "state"
        doc = doc_with(SKIPPED_ACTIONS, repo=str(repo))
        drift = tmp_path / "drift.json"
        drift.write_text(json.dumps(doc), encoding="utf-8")

        rc = rd.main(["--drift", str(drift), "--state-dir", str(state),
                      "--no-model"])
        assert rc == 0
        assert not (repo / "Notes").exists()

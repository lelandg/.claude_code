"""Tests for deterministic Markdown rendering.

Design: "Report format". The renderer is deterministic so that an invalid or
partial model response can never replace the last valid report.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import render as rd  # noqa: E402

GOLDEN = Path(__file__).resolve().parent / "golden" / "report-basic.md"

DOC = {
    "drift_schema_version": 1,
    "run_id": "2026-08-10T14-03-22Z-3f9a1c",
    "generated_at": "2026-08-10T14:03:22+00:00",
    "scanner_version": "1.0.0",
    "manifest_version": 1,
    "roots": {"wsl": "/home/leland", "repo": "/repo", "windows": "/mnt/c/Users/aboog"},
    "layer_fingerprints": {"wsl": "a" * 64, "repo": "b" * 64, "windows": "c" * 64},
    "counts": {"publish_to_repo": 1, "conflict": 1, "protected_overlay": 1,
               "plugin_version_differs": 1},
    "items": [
        {"id": "agents-md", "entry_id": "agents-md", "kind": "text",
         "classification": "publish_to_repo", "severity": "review",
         "path": ".config/agents/AGENTS.md", "policy": "portable_authoritative",
         "detail": "WSL intent is ahead of the baseline; publish it.",
         "wsl_fingerprint": "d" * 64, "repo_fingerprint": "e" * 64},
        {"id": "claude-settings:model", "entry_id": "claude-settings",
         "kind": "json_field", "classification": "conflict",
         "severity": "conflict", "path": ".claude/settings.json",
         "policy": "portable_authoritative",
         "detail": "WSL and Windows changed independently of the baseline."},
        {"id": "claude-settings:statusLine.command",
         "entry_id": "claude-settings", "kind": "json_field",
         "classification": "protected_overlay", "severity": "info",
         "path": ".claude/settings.json", "policy": "platform_overlay",
         "detail": "Windows owns this value; preserved and reported only."},
        {"id": "claude-plugins:superpowers@claude-plugins-official#version",
         "entry_id": "claude-plugins", "kind": "plugin",
         "classification": "plugin_version_differs", "severity": "review",
         "path": "superpowers@claude-plugins-official",
         "policy": "portable_authoritative",
         "detail": "windows has 6.2.0, wsl has 6.1.0. The newer build is "
                   "preserved; upgrade wsl."},
    ],
    "redactions": [{"pointer": "mcpServers.gh.env.GITHUB_TOKEN",
                    "reason": "secret_key_pattern", "value_type": "str",
                    "value_fingerprint": "f" * 64}],
    "errors": [{"path": ".codex/config.toml", "message": "invalid TOML at line 12"}],
}

ANALYSIS = {
    "response_schema_version": 1,
    "summary": "One portable update is safe; the settings model field needs a "
               "decision.",
    "severity": "conflict",
    "recommended_order": ["agents-md", "claude-settings:model"],
    "notes": [{"item_id": "claude-settings:model",
               "note": "Both sides edited the model pin since the baseline."}],
    "codex_review_recommended": True,
    "codex_reason": "An ambiguous semantic merge in a settings field.",
}


def test_every_required_section_is_present_in_order():
    out = rd.render_markdown(DOC, ANALYSIS)
    positions = [out.index(f"## {name}") for name in rd.SECTIONS]
    assert positions == sorted(positions)


def test_header_carries_every_version_and_fingerprint():
    out = rd.render_markdown(DOC, ANALYSIS)
    for needle in ("2026-08-10T14-03-22Z-3f9a1c", "scanner 1.0.0",
                   "manifest 1", "drift schema 1",
                   f"template {rd.REPORT_TEMPLATE_VERSION}",
                   "aaaaaaaaaaaa", "bbbbbbbbbbbb", "cccccccccccc"):
        assert needle in out, needle


def test_items_are_listed_under_their_section_with_stable_ids():
    out = rd.render_markdown(DOC, ANALYSIS)
    safe = out.split("## Safe portable updates")[1].split("## ")[0]
    assert "`agents-md`" in safe
    conflicts = out.split("## Conflicts requiring judgment")[1].split("## ")[0]
    assert "`claude-settings:model`" in conflicts
    assert "`agents-md`" not in conflicts


def test_protected_windows_state_is_its_own_section_and_not_actionable():
    out = rd.render_markdown(DOC, ANALYSIS)
    protected = out.split("## Protected Windows state")[1].split("## ")[0]
    assert "statusLine.command" in protected
    safe = out.split("## Safe portable updates")[1].split("## ")[0]
    assert "statusLine.command" not in safe


def test_plugin_differences_get_their_own_section():
    out = rd.render_markdown(DOC, ANALYSIS)
    section = out.split("## Plugin differences")[1].split("## ")[0]
    assert "superpowers@claude-plugins-official" in section
    assert "6.2.0" in section


def test_redactions_show_reason_codes_and_never_values():
    out = rd.render_markdown(DOC, ANALYSIS)
    section = out.split("## Excluded and redacted")[1].split("## ")[0]
    assert "secret_key_pattern" in section
    assert "GITHUB_TOKEN" in section          # the NAME may be recorded
    assert "f" * 64 not in section            # the hash is truncated, not raw
    assert "ffffffffffff" in section


def test_model_notes_are_attached_to_their_items():
    out = rd.render_markdown(DOC, ANALYSIS)
    assert "Both sides edited the model pin" in out


def test_recommended_merge_order_is_rendered_as_a_numbered_list():
    out = rd.render_markdown(DOC, ANALYSIS)
    section = out.split("## Recommended merge order")[1].split("## ")[0]
    assert "1. `agents-md`" in section
    assert "2. `claude-settings:model`" in section


def test_handoff_prompt_names_the_merge_skill_and_the_run_id():
    out = rd.render_markdown(DOC, ANALYSIS)
    section = out.split("## Claude handoff prompt")[1].split("## ")[0]
    assert "agent-config-merge" in section
    assert "2026-08-10T14-03-22Z-3f9a1c" in section


def test_codex_prompt_appears_only_when_recommended():
    with_codex = rd.render_markdown(DOC, ANALYSIS)
    assert "## Independent review (/codex)" in with_codex
    quiet = dict(ANALYSIS, codex_review_recommended=False)
    assert "## Independent review (/codex)" not in rd.render_markdown(DOC, quiet)


def test_errors_are_reported_with_location_only():
    out = rd.render_markdown(DOC, ANALYSIS)
    assert "invalid TOML at line 12" in out
    assert ".codex/config.toml" in out


def test_empty_analysis_renders_without_a_model():
    out = rd.render_markdown(DOC, rd.empty_analysis())
    assert "no model analysis" in out.lower()
    assert "## Safe portable updates" in out


def test_rendering_is_deterministic():
    assert rd.render_markdown(DOC, ANALYSIS) == rd.render_markdown(DOC, ANALYSIS)


def test_matches_the_golden_report():
    expected = GOLDEN.read_text(encoding="utf-8")
    actual = rd.render_markdown(DOC, ANALYSIS)
    if os.environ.get("UPDATE_GOLDEN") == "1":
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_text(actual, encoding="utf-8")
        expected = actual
    assert actual == expected

"""Tests for the bounded claude -p wrapper.

A stub executable stands in for claude, so no network, subscription, or live
model is involved. Design: "Claude-first report generation"; test case 14
(invalid, incomplete, or timed-out model output).
"""
from __future__ import annotations

import json
import stat
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import analyze as az  # noqa: E402

VALID = {
    "response_schema_version": 1,
    "summary": "One safe update.",
    "severity": "review",
    "recommended_order": ["agents-md"],
    "notes": [{"item_id": "agents-md", "note": "publish it"}],
    "codex_review_recommended": False,
    "codex_reason": "",
}

DOC = {
    "drift_schema_version": 1, "run_id": "r1",
    "generated_at": "2026-08-10T00:00:00+00:00", "scanner_version": "1.0.0",
    "manifest_version": 1, "roots": {"wsl": "/w", "repo": "/r"},
    "layer_fingerprints": {"wsl": "a" * 64, "repo": "b" * 64},
    "counts": {"publish_to_repo": 1},
    "items": [{"id": "agents-md", "entry_id": "agents-md", "kind": "text",
               "classification": "publish_to_repo", "severity": "review",
               "path": "AGENTS.md", "policy": "portable_authoritative",
               "detail": "ahead of baseline"}],
    "redactions": [], "errors": [],
}

PROMPT = Path(__file__).resolve().parents[1] / "prompts" / "report-v1.md"


def stub(tmp_path: Path, body: str) -> str:
    """Write an executable shell script that impersonates `claude`."""
    path = tmp_path / "claude-stub"
    path.write_text("#!/bin/sh\n" + body, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return str(path)


# --- command construction --------------------------------------------------

def test_command_uses_print_mode_and_bounded_turns():
    argv = az.build_command("/usr/bin/claude", max_turns=4)
    assert argv[0] == "/usr/bin/claude"
    assert "--print" in argv
    assert "--max-turns" in argv and "4" in argv


def test_command_grants_read_tools_only():
    argv = az.build_command("/usr/bin/claude", max_turns=4)
    allowed = argv[argv.index("--allowedTools") + 1]
    assert set(allowed.split(",")) <= {"Read", "Grep", "Glob"}
    disallowed = argv[argv.index("--disallowedTools") + 1].split(",")
    for mutator in ("Bash", "Write", "Edit"):
        assert mutator in disallowed


def test_command_never_uses_bare_mode():
    # The design requires normal configuration so skills/instructions load.
    assert "--bare" not in az.build_command("/usr/bin/claude", max_turns=4)


# --- prompt ----------------------------------------------------------------

def test_prompt_embeds_the_drift_document_and_the_schema():
    prompt = az.build_prompt(DOC, PROMPT)
    assert "agents-md" in prompt
    assert "response_schema_version" in prompt
    assert az.PROMPT_VERSION in prompt


def test_prompt_forbids_writing_and_inventing_items():
    prompt = az.build_prompt(DOC, PROMPT)
    lowered = prompt.lower()
    assert "do not" in lowered
    assert "item id" in lowered


# --- response parsing ------------------------------------------------------

def test_extract_json_reads_a_bare_object():
    assert az.extract_json(json.dumps(VALID))["summary"] == "One safe update."


def test_extract_json_reads_a_fenced_block():
    text = "Here you go:\n```json\n" + json.dumps(VALID) + "\n```\n"
    assert az.extract_json(text)["severity"] == "review"


def test_extract_json_reads_the_claude_print_json_envelope():
    envelope = json.dumps({"type": "result", "subtype": "success",
                           "result": json.dumps(VALID)})
    assert az.extract_json(envelope)["summary"] == "One safe update."


def test_extract_json_raises_when_there_is_no_object():
    with pytest.raises(az.AnalysisError):
        az.extract_json("I could not do that.")


def test_validate_accepts_a_good_analysis():
    assert az.validate_analysis(VALID) == []


def test_validate_rejects_a_missing_required_field():
    broken = {k: v for k, v in VALID.items() if k != "summary"}
    assert az.validate_analysis(broken)


def test_validate_rejects_an_unknown_severity():
    assert az.validate_analysis(dict(VALID, severity="catastrophic"))


def test_validate_rejects_a_future_response_schema_version():
    assert az.validate_analysis(dict(VALID, response_schema_version=2))


# --- running the stub ------------------------------------------------------

def test_run_returns_the_parsed_analysis(tmp_path: Path):
    binary = stub(tmp_path, f"cat >/dev/null\necho '{json.dumps(VALID)}'\n")
    result = az.run(DOC, claude_bin=binary, prompt_path=PROMPT,
                    timeout_s=10, max_turns=4)
    assert result["summary"] == "One safe update."


def test_run_raises_on_a_nonzero_exit(tmp_path: Path):
    binary = stub(tmp_path, "cat >/dev/null\necho boom >&2\nexit 3\n")
    with pytest.raises(az.AnalysisError) as excinfo:
        az.run(DOC, claude_bin=binary, prompt_path=PROMPT, timeout_s=10,
               max_turns=4)
    assert "exit 3" in str(excinfo.value)


def test_run_raises_on_unparseable_output(tmp_path: Path):
    binary = stub(tmp_path, "cat >/dev/null\necho 'sorry, no'\n")
    with pytest.raises(az.AnalysisError):
        az.run(DOC, claude_bin=binary, prompt_path=PROMPT, timeout_s=10,
               max_turns=4)


def test_run_raises_on_a_schema_invalid_response(tmp_path: Path):
    bad = json.dumps(dict(VALID, severity="nope"))
    binary = stub(tmp_path, f"cat >/dev/null\necho '{bad}'\n")
    with pytest.raises(az.AnalysisError) as excinfo:
        az.run(DOC, claude_bin=binary, prompt_path=PROMPT, timeout_s=10,
               max_turns=4)
    assert "severity" in str(excinfo.value)


def test_run_raises_on_timeout(tmp_path: Path):
    binary = stub(tmp_path, "cat >/dev/null\nsleep 5\n")
    with pytest.raises(az.AnalysisError) as excinfo:
        az.run(DOC, claude_bin=binary, prompt_path=PROMPT, timeout_s=1,
               max_turns=4)
    assert "timed out" in str(excinfo.value)


def test_run_raises_when_the_binary_is_missing(tmp_path: Path):
    with pytest.raises(az.AnalysisError):
        az.run(DOC, claude_bin=str(tmp_path / "nope"), prompt_path=PROMPT,
               timeout_s=5, max_turns=4)


def test_error_messages_never_echo_the_model_output_verbatim(tmp_path: Path):
    binary = stub(tmp_path, "cat >/dev/null\necho 'sk-live-DO-NOT-LEAK'\n")
    with pytest.raises(az.AnalysisError) as excinfo:
        az.run(DOC, claude_bin=binary, prompt_path=PROMPT, timeout_s=10,
               max_turns=4)
    assert "sk-live-DO-NOT-LEAK" not in str(excinfo.value)


# --- regression: schema.validate() error strings can embed the offending ---
# --- value or key verbatim; run() must keep only the path, never that ------

def test_schema_error_never_echoes_a_secret_shaped_enum_value(tmp_path: Path):
    # An enum mismatch's message is "{path}: {instance!r} is not one of
    # [...]" -- the offending *value* is attacker-controlled once analyze.py
    # validates model output (unlike drift.py, which only validates our own
    # scanner's output against the same validator).
    bad = json.dumps(dict(VALID, severity="sk-live-SECRET-VALUE"))
    binary = stub(tmp_path, f"cat >/dev/null\necho '{bad}'\n")
    with pytest.raises(az.AnalysisError) as excinfo:
        az.run(DOC, claude_bin=binary, prompt_path=PROMPT, timeout_s=10,
               max_turns=4)
    message = str(excinfo.value)
    assert "sk-live-SECRET-VALUE" not in message
    assert message == "analyzer response failed the schema at: $.severity"


def test_schema_error_never_echoes_a_secret_shaped_extra_key(tmp_path: Path):
    # An additionalProperties violation's message is "{path}: unexpected
    # property {key!r}" -- the extra JSON key is also attacker-chosen text.
    bad = json.dumps(dict(VALID, **{"ghp_ATTACKER_KEY": "leak-me-too"}))
    binary = stub(tmp_path, f"cat >/dev/null\necho '{bad}'\n")
    with pytest.raises(az.AnalysisError) as excinfo:
        az.run(DOC, claude_bin=binary, prompt_path=PROMPT, timeout_s=10,
               max_turns=4)
    message = str(excinfo.value)
    assert "ghp_ATTACKER_KEY" not in message
    assert "leak-me-too" not in message
    assert message == "analyzer response failed the schema at: $"


def test_schema_error_path_extraction_survives_a_colon_in_the_value(tmp_path: Path):
    # split(":", 1) must isolate the path even when the offending value
    # itself contains ": " -- the path's own colon always comes first in
    # "{path}: {message}", because a JSON-Schema path (dots, brackets,
    # property names) never contains a colon.
    bad = json.dumps(dict(VALID, severity="not real: has a colon too"))
    binary = stub(tmp_path, f"cat >/dev/null\necho '{bad}'\n")
    with pytest.raises(az.AnalysisError) as excinfo:
        az.run(DOC, claude_bin=binary, prompt_path=PROMPT, timeout_s=10,
               max_turns=4)
    message = str(excinfo.value)
    assert "has a colon too" not in message
    assert message == "analyzer response failed the schema at: $.severity"


# --- render.py CLI ---------------------------------------------------------

def test_render_cli_promotes_only_a_valid_report(tmp_path: Path):
    import render as rd

    drift_path = tmp_path / "drift.json"
    drift_path.write_text(json.dumps(DOC), encoding="utf-8")
    state = tmp_path / "state"
    binary = stub(tmp_path, f"cat >/dev/null\necho '{json.dumps(VALID)}'\n")

    code = rd.main(["--drift", str(drift_path), "--state-dir", str(state),
                    "--claude-bin", binary, "--prompt", str(PROMPT)])
    assert code == 0
    latest = (state / "latest-report.md").read_text(encoding="utf-8")
    assert "Agent config drift report" in latest
    assert list((state / "reports").glob("*.md"))


def test_render_cli_keeps_the_previous_report_when_the_model_fails(tmp_path: Path):
    import render as rd

    drift_path = tmp_path / "drift.json"
    drift_path.write_text(json.dumps(DOC), encoding="utf-8")
    state = tmp_path / "state"
    state.mkdir()
    (state / "latest-report.md").write_text("PREVIOUS GOOD REPORT\n",
                                            encoding="utf-8")
    binary = stub(tmp_path, "cat >/dev/null\necho 'garbage'\n")

    code = rd.main(["--drift", str(drift_path), "--state-dir", str(state),
                    "--claude-bin", binary, "--prompt", str(PROMPT)])
    assert code == rd.EXIT_MODEL_FAILURE
    assert (state / "latest-report.md").read_text(
        encoding="utf-8") == "PREVIOUS GOOD REPORT\n"


def test_render_cli_no_model_flag_renders_without_claude(tmp_path: Path):
    import render as rd

    drift_path = tmp_path / "drift.json"
    drift_path.write_text(json.dumps(DOC), encoding="utf-8")
    state = tmp_path / "state"
    code = rd.main(["--drift", str(drift_path), "--state-dir", str(state),
                    "--no-model"])
    assert code == 0
    assert "no model analysis" in (
        state / "latest-report.md").read_text(encoding="utf-8").lower()

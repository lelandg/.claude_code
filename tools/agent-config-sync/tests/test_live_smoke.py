"""Opt-in live smoke test.

Skipped unless ACS_LIVE=1. It runs the real scanner against the real machine
read-only, and (with ACS_LIVE_MODEL=1) the real `claude -p` analyzer.

    ACS_LIVE=1 python3 -m pytest tools/agent-config-sync/tests/test_live_smoke.py -v
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

REPO = Path(__file__).resolve().parents[3]
MANIFEST = REPO / "config" / "agent-sync.toml"

live = pytest.mark.skipif(os.environ.get("ACS_LIVE") != "1",
                          reason="set ACS_LIVE=1 to run against this machine")


@live
def test_scanner_runs_clean_against_this_machine(tmp_path: Path):
    out = tmp_path / "drift.json"
    result = subprocess.run(
        [sys.executable, str(REPO / "tools/agent-config-sync/scan.py"),
         "--manifest", str(MANIFEST), "--out", str(out),
         "--state-dir", str(tmp_path)],
        capture_output=True, text=True)
    assert result.returncode in (0, 10), result.stderr
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["scanner_version"]
    # Nothing that looks like a credential may appear anywhere in the document.
    blob = json.dumps(doc)
    for needle in ("sk-", "ghp_", "-----BEGIN", "AKIA"):
        assert needle not in blob, f"possible secret leak: {needle}"


@live
def test_scan_is_read_only(tmp_path: Path):
    import manifest as mf

    m = mf.load_manifest(MANIFEST)
    watched = [m.roots.wsl_home / ".claude" / "settings.json",
               m.roots.wsl_home / ".config" / "agents" / "AGENTS.md"]
    before = {p: p.stat().st_mtime_ns for p in watched if p.exists()}
    subprocess.run(
        [sys.executable, str(REPO / "tools/agent-config-sync/scan.py"),
         "--manifest", str(MANIFEST), "--out", str(tmp_path / "d.json"),
         "--state-dir", str(tmp_path)], capture_output=True, text=True)
    for path, mtime in before.items():
        assert path.stat().st_mtime_ns == mtime, f"scan modified {path}"


@pytest.mark.skipif(os.environ.get("ACS_LIVE_MODEL") != "1",
                    reason="set ACS_LIVE_MODEL=1 to call the real claude CLI")
def test_real_claude_returns_a_schema_valid_analysis(tmp_path: Path):
    import analyze as az

    out = tmp_path / "drift.json"
    subprocess.run(
        [sys.executable, str(REPO / "tools/agent-config-sync/scan.py"),
         "--manifest", str(MANIFEST), "--out", str(out),
         "--state-dir", str(tmp_path)], capture_output=True, text=True)
    doc = json.loads(out.read_text(encoding="utf-8"))
    analysis = az.run(doc, claude_bin="claude",
                      prompt_path=REPO / "tools/agent-config-sync/prompts/report-v1.md",
                      timeout_s=300, max_turns=6)
    assert az.validate_analysis(analysis) == []

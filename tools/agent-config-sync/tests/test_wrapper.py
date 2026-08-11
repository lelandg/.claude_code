"""Tests for the cron wrapper.

Design: "Scheduling"; test case 1 -- when there is no drift, Claude is never
invoked.
"""
from __future__ import annotations

import stat
import subprocess
from pathlib import Path

import pytest

WRAPPER = Path(__file__).resolve().parents[1] / "bin" / "agent-config-sync.sh"


def stub(path: Path, body: str) -> str:
    path.write_text("#!/bin/sh\n" + body, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return str(path)


@pytest.fixture
def scene(tmp_path: Path):
    state = tmp_path / "state"
    state.mkdir()
    marker = tmp_path / "render-was-called"
    return tmp_path, state, marker


def run_wrapper(tmp_path: Path, state: Path, *, scan_exit: int,
                render_exit: int, marker: Path):
    scan = stub(tmp_path / "scan-stub", f'exit {scan_exit}\n')
    render = stub(tmp_path / "render-stub",
                  f'echo called >"{marker}"\nexit {render_exit}\n')
    env = {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "HOME": str(tmp_path),
        "ACS_STATE": str(state),
        "ACS_MANIFEST": str(tmp_path / "agent-sync.toml"),
        "ACS_SCAN": scan,
        "ACS_RENDER": render,
        "ACS_CLAUDE": "/nonexistent/claude",
    }
    return subprocess.run(["bash", str(WRAPPER)], env=env,
                          capture_output=True, text=True)


def test_no_drift_exits_zero_and_never_calls_the_model(scene):
    tmp_path, state, marker = scene
    result = run_wrapper(tmp_path, state, scan_exit=0, render_exit=0,
                         marker=marker)
    assert result.returncode == 0
    assert not marker.exists(), "Claude must not run when there is no drift"


def test_drift_calls_render_and_exits_ten(scene):
    tmp_path, state, marker = scene
    result = run_wrapper(tmp_path, state, scan_exit=10, render_exit=0,
                         marker=marker)
    assert result.returncode == 10
    assert marker.exists()


def test_scan_failure_exits_twenty_and_never_calls_the_model(scene):
    tmp_path, state, marker = scene
    result = run_wrapper(tmp_path, state, scan_exit=20, render_exit=0,
                         marker=marker)
    assert result.returncode == 20
    assert not marker.exists()


def test_lock_held_exits_twenty_one(scene):
    tmp_path, state, marker = scene
    result = run_wrapper(tmp_path, state, scan_exit=21, render_exit=0,
                         marker=marker)
    assert result.returncode == 21
    assert not marker.exists()


def test_model_failure_exits_thirty_not_twenty(scene):
    tmp_path, state, marker = scene
    result = run_wrapper(tmp_path, state, scan_exit=10, render_exit=30,
                         marker=marker)
    assert result.returncode == 30


def test_unwritable_state_dir_exits_twenty(tmp_path):
    parent = tmp_path / "locked"
    parent.mkdir()
    state = parent / "state"
    marker = tmp_path / "render-was-called"
    scan = stub(tmp_path / "scan-stub", "exit 0\n")
    render = stub(tmp_path / "render-stub", f'echo called >"{marker}"\nexit 0\n')
    parent.chmod(0o000)
    try:
        env = {
            "PATH": "/usr/local/bin:/usr/bin:/bin",
            "HOME": str(tmp_path),
            "ACS_STATE": str(state),
            "ACS_MANIFEST": str(tmp_path / "agent-sync.toml"),
            "ACS_SCAN": scan,
            "ACS_RENDER": render,
            "ACS_CLAUDE": "/nonexistent/claude",
        }
        result = subprocess.run(["bash", str(WRAPPER)], env=env,
                                capture_output=True, text=True)
    finally:
        parent.chmod(0o755)
    assert result.returncode == 20
    assert not marker.exists(), "Claude must not run when the state dir can't be created"
    assert "cannot create state directory" in result.stderr


def test_home_unset_and_no_overrides_exits_twenty_mentioning_home(tmp_path):
    scan = stub(tmp_path / "scan-stub", "exit 0\n")
    render = stub(tmp_path / "render-stub", "exit 0\n")
    env = {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "ACS_SCAN": scan,
        "ACS_RENDER": render,
    }
    result = subprocess.run(["env", "-u", "HOME", "bash", str(WRAPPER)],
                            env=env, capture_output=True, text=True)
    assert result.returncode == 20
    assert "HOME" in result.stderr
    assert "ACS_CLAUDE" in result.stderr
    assert "ACS_STATE" in result.stderr


def test_home_unset_but_both_overrides_provided_runs_normally(tmp_path):
    state = tmp_path / "state"
    state.mkdir()
    marker = tmp_path / "render-was-called"
    scan = stub(tmp_path / "scan-stub", "exit 10\n")
    render = stub(tmp_path / "render-stub", f'echo called >"{marker}"\nexit 0\n')
    env = {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "ACS_STATE": str(state),
        "ACS_CLAUDE": "/nonexistent/claude",
        "ACS_MANIFEST": str(tmp_path / "agent-sync.toml"),
        "ACS_SCAN": scan,
        "ACS_RENDER": render,
    }
    result = subprocess.run(["env", "-u", "HOME", "bash", str(WRAPPER)],
                            env=env, capture_output=True, text=True)
    assert result.returncode == 10, result.stderr
    assert marker.exists()


def test_wrapper_is_executable_and_uses_absolute_defaults():
    assert WRAPPER.stat().st_mode & stat.S_IXUSR
    text = WRAPPER.read_text(encoding="utf-8")
    assert text.startswith("#!/usr/bin/env bash")
    assert "set -euo pipefail" in text
    assert "export PATH=" in text, "cron gets a minimal explicit environment"

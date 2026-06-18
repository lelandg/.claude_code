from pathlib import Path
import os
import subprocess
import sys

import pytest

import disk_doctor_core as core

UNDO_BIN = Path(__file__).resolve().parent.parent / "bin" / "disk-doctor-undo"


@pytest.fixture
def fake_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path), raising=True)
    return tmp_path


def test_trash_then_undo_roundtrip(fake_home, tmp_path):
    base = tmp_path / ".disk-doctor"
    target = fake_home / "Downloads" / "junk.zip"
    target.parent.mkdir(parents=True)
    target.write_text("payload")
    core.trash_item(target, "runR", [fake_home / "Downloads"], commit=True, base=base, prefer_freedesktop=False)
    assert not target.exists()

    results = core.restore_run("runR", base=base)
    assert results and all(r["status"] == "restored" for r in results)
    assert target.exists()
    assert target.read_text() == "payload"


def test_undo_does_not_overwrite_collision(fake_home, tmp_path):
    base = tmp_path / ".disk-doctor"
    target = fake_home / "Downloads" / "junk.zip"
    target.parent.mkdir(parents=True)
    target.write_text("original")
    core.trash_item(target, "runR", [fake_home / "Downloads"], commit=True, base=base, prefer_freedesktop=False)
    target.write_text("new file in the way")  # recreate at original path

    results = core.restore_run("runR", base=base)
    assert results[0]["status"] == "collision"
    assert target.read_text() == "new file in the way"  # untouched


def test_latest_run_id(fake_home, tmp_path):
    base = tmp_path / ".disk-doctor"
    runs = base / "runs"
    runs.mkdir(parents=True)
    (runs / "run-A.jsonl").write_text("{}\n")
    (runs / "run-B.jsonl").write_text("{}\n")
    os.utime(runs / "run-A.jsonl", (1000, 1000))
    os.utime(runs / "run-B.jsonl", (2000, 2000))
    assert core.latest_run_id(base=base) == "run-B"


def test_undo_bogus_run_exits_2(tmp_path):
    env = dict(os.environ)
    env["HOME"] = str(tmp_path)
    res = subprocess.run(
        [sys.executable, str(UNDO_BIN), "--run", "does-not-exist"],
        capture_output=True, text=True, env=env,
    )
    assert res.returncode == 2

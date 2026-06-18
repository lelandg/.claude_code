from pathlib import Path

import pytest

import disk_doctor_core as core


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
    assert core.latest_run_id(base=base) in {"run-A", "run-B"}

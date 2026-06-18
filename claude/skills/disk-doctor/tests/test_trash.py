import json
from pathlib import Path

import pytest

import disk_doctor_core as core


@pytest.fixture
def fake_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path), raising=True)
    return tmp_path


@pytest.fixture
def dd_base(tmp_path):
    return tmp_path / ".disk-doctor"


def _make(fake_home, name="Downloads/junk.zip", content="data"):
    p = fake_home / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return p


def test_dry_run_moves_nothing_and_writes_no_manifest(fake_home, dd_base):
    target = _make(fake_home)
    rec = core.trash_item(target, "run1", [fake_home / "Downloads"], commit=False, base=dd_base)
    assert rec["action"] == "dry-run"
    assert target.exists()                       # untouched
    assert not (dd_base / "runs" / "run1.jsonl").exists()


def test_commit_quarantine_moves_and_writes_manifest(fake_home, dd_base):
    target = _make(fake_home)
    rec = core.trash_item(
        target, "run1", [fake_home / "Downloads"], commit=True, base=dd_base, prefer_freedesktop=False
    )
    assert rec["action"] == "trashed"
    assert rec["method"] == "quarantine"
    assert not target.exists()                   # moved out
    assert Path(rec["dest"]).exists()            # now in quarantine
    lines = (dd_base / "runs" / "run1.jsonl").read_text().splitlines()
    assert len(lines) == 1
    saved = json.loads(lines[0])
    assert saved["original"] == str(target.resolve())
    assert saved["dest"] == rec["dest"]


def test_commit_freedesktop_lands_in_trash_with_trashinfo(fake_home, dd_base):
    target = _make(fake_home)
    rec = core.trash_item(
        target, "run1", [fake_home / "Downloads"], commit=True, base=dd_base, prefer_freedesktop=True
    )
    assert rec["method"] == "freedesktop"
    trash_files = fake_home / ".local" / "share" / "Trash" / "files"
    trash_info = fake_home / ".local" / "share" / "Trash" / "info"
    assert Path(rec["dest"]).parent == trash_files
    assert Path(rec["dest"]).exists()
    info = list(trash_info.glob("*.trashinfo"))
    assert len(info) == 1
    assert "Path=" in info[0].read_text()


def test_denied_path_is_refused_not_moved(fake_home, dd_base):
    target = _make(fake_home, name=".ssh/id_rsa")
    rec = core.trash_item(target, "run1", [fake_home], commit=True, base=dd_base)
    assert rec["action"] == "refused"
    assert rec["reason"] == core.Verdict.DENIED
    assert target.exists()                       # never moved
    log = (dd_base / "disk-doctor.log").read_text()
    assert "refuse" in log


def test_abort_when_manifest_unwritable(fake_home, dd_base):
    target = _make(fake_home)
    # Make runs/ a FILE so the manifest append raises before any move.
    (dd_base / "runs").parent.mkdir(parents=True, exist_ok=True)
    dd_base.mkdir(parents=True, exist_ok=True)
    (dd_base / "runs").write_text("not a dir")
    with pytest.raises(OSError):
        core.trash_item(target, "run1", [fake_home / "Downloads"], commit=True, base=dd_base)
    assert target.exists()                       # aborted before move
    log = (dd_base / "disk-doctor.log").read_text()
    assert "abort-no-manifest" in log


def test_every_event_is_logged(fake_home, dd_base):
    target = _make(fake_home)
    core.trash_item(target, "run1", [fake_home / "Downloads"], commit=True, base=dd_base, prefer_freedesktop=False)
    log = (dd_base / "disk-doctor.log").read_text()
    assert "trash" in log

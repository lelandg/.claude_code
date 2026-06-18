import os
from pathlib import Path

import pytest

import disk_doctor_core as core


@pytest.fixture
def fake_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path), raising=True)
    return tmp_path


def test_allowed_path_is_ok(fake_home):
    target = fake_home / "Downloads" / "junk.zip"
    target.parent.mkdir(parents=True)
    target.write_text("x")
    verdict, rp = core.classify(target, allowed_roots=[fake_home / "Downloads"])
    assert verdict == core.Verdict.OK
    assert rp == target.resolve()


def test_system_path_is_denied(fake_home):
    verdict, _ = core.classify("/etc/passwd", allowed_roots=["/etc"])
    assert verdict == core.Verdict.DENIED  # deny beats allow


def test_home_root_itself_is_denied(fake_home):
    verdict, _ = core.classify(fake_home, allowed_roots=[fake_home])
    assert verdict == core.Verdict.DENIED


def test_local_share_is_denied(fake_home):
    target = fake_home / ".local" / "share" / "Steam"
    target.mkdir(parents=True)
    verdict, _ = core.classify(target, allowed_roots=[fake_home])
    assert verdict == core.Verdict.DENIED


def test_browser_profile_is_denied(fake_home):
    target = fake_home / ".mozilla" / "firefox"
    target.mkdir(parents=True)
    verdict, _ = core.classify(target, allowed_roots=[fake_home])
    assert verdict == core.Verdict.DENIED


def test_path_outside_allowlist_is_not_allowed(fake_home):
    target = fake_home / "Documents" / "taxes.pdf"
    target.parent.mkdir(parents=True)
    target.write_text("x")
    verdict, _ = core.classify(target, allowed_roots=[fake_home / "Downloads"])
    assert verdict == core.Verdict.NOT_ALLOWED


def test_symlink_target_is_refused(fake_home):
    real = fake_home / "Downloads" / "real.txt"
    real.parent.mkdir(parents=True)
    real.write_text("x")
    link = fake_home / "Downloads" / "link.txt"
    link.symlink_to(real)
    verdict, _ = core.classify(link, allowed_roots=[fake_home / "Downloads"])
    assert verdict == core.Verdict.SYMLINK


def test_missing_path(fake_home):
    verdict, _ = core.classify(fake_home / "Downloads" / "nope", allowed_roots=[fake_home / "Downloads"])
    assert verdict == core.Verdict.MISSING


def test_extra_denied_can_only_add(fake_home):
    target = fake_home / "Downloads" / "keepme"
    target.mkdir(parents=True)
    verdict, _ = core.classify(
        target, allowed_roots=[fake_home / "Downloads"], extra_denied=[fake_home / "Downloads" / "keepme"]
    )
    assert verdict == core.Verdict.DENIED

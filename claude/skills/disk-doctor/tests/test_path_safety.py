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


def test_filesystem_root_is_denied(fake_home):
    verdict, _ = core.classify("/", allowed_roots=["/"])
    assert verdict == core.Verdict.DENIED


def test_proc_and_dev_are_denied(fake_home):
    for p in ("/proc", "/dev"):
        verdict, _ = core.classify(p, allowed_roots=[p])
        assert verdict == core.Verdict.DENIED


def test_symlinked_parent_into_denied_is_denied(fake_home):
    # A path THROUGH a symlinked parent directory that resolves into a denied
    # location must be DENIED — this is exactly what canonicalize-first defends
    # against. The leaf is a real file (not itself a symlink), so this exercises
    # the resolve-then-deny path, not the SYMLINK short-circuit.
    denied_dir = fake_home / ".config"
    denied_dir.mkdir(parents=True, exist_ok=True)
    secret = denied_dir / "secret.conf"
    secret.write_text("x")
    downloads = fake_home / "Downloads"
    downloads.mkdir(parents=True, exist_ok=True)
    link = downloads / "cfglink"
    link.symlink_to(denied_dir)
    target = link / "secret.conf"  # path through the symlinked parent
    verdict, rp = core.classify(target, allowed_roots=[downloads])
    assert verdict == core.Verdict.DENIED
    assert rp == secret.resolve()

import json
import os
import subprocess
import sys
from pathlib import Path

BIN = Path(__file__).resolve().parent.parent / "bin" / "safe-trash"


def _run(args, home):
    env = dict(os.environ)
    env["HOME"] = str(home)
    return subprocess.run(
        [sys.executable, str(BIN)] + args,
        capture_output=True, text=True, env=env,
    )


def test_requires_allow(tmp_path):
    res = _run([str(tmp_path / "x")], tmp_path)
    assert res.returncode == 2


def test_dry_run_default_reports_without_moving(tmp_path):
    target = tmp_path / "Downloads" / "junk.zip"
    target.parent.mkdir(parents=True)
    target.write_text("x")
    res = _run(["--allow", str(tmp_path / "Downloads"), str(target)], tmp_path)
    assert res.returncode == 0
    rec = json.loads(res.stdout.strip().splitlines()[0])
    assert rec["action"] == "dry-run"
    assert target.exists()


def test_commit_quarantine_moves(tmp_path):
    target = tmp_path / "Downloads" / "junk.zip"
    target.parent.mkdir(parents=True)
    target.write_text("x")
    res = _run(
        ["--allow", str(tmp_path / "Downloads"), "--commit", "--quarantine",
         "--run-id", "runX", str(target)],
        tmp_path,
    )
    assert res.returncode == 0
    rec = json.loads(res.stdout.strip().splitlines()[0])
    assert rec["action"] == "trashed"
    assert not target.exists()

"""Tests for ci-local.sh. Real git repos in tmp_path; `act` and `docker` are stubs on PATH."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "ci-local.sh"

pytestmark = pytest.mark.skipif(
    os.name == "nt" or not shutil.which("bash") or not shutil.which("flock"),
    reason="ci-local.sh runs under Linux bash (WSL or a Linux runner)",
)

WORKFLOW = """\
name: tests
on:
  pull_request:
  push:
    branches: [main]
jobs:
  unit:
    runs-on: ubuntu-latest
    steps:
      - run: echo hi
"""

# Records what act was asked to do, then reports one job, like act does.
STUB_ACT = """\
#!/usr/bin/env bash
out="$CI_LOCAL_TEST_OUT"
ev=""; prev=""
for a in "$@"; do [ "$prev" = "-e" ] && ev="$a"; prev="$a"; done
python3 - "$out" "$ev" "$@" <<'PY'
import json, os, subprocess, sys
out, ev, *args = sys.argv[1:]
event = json.load(open(ev)) if ev else None
parents = subprocess.run(["git", "log", "-1", "--format=%P"], capture_output=True, text=True).stdout.split()
head = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
json.dump({"args": args, "event": event, "parents": parents, "head": head, "cwd": os.getcwd()}, open(out, "w"))
PY
if printf '%s\\n' "$@" | grep -qx -- --list; then echo "Stage  Job ID  Job name"; exit 0; fi
echo "[tests/unit] 🏁  Job ${CI_LOCAL_TEST_JOB:-succeeded}"
[ -n "${CI_LOCAL_TEST_FINALLY:-}" ] && echo "Error: Error occurred running finally: context deadline exceeded (original error: <nil>)"
exit "${CI_LOCAL_TEST_RC:-0}"
"""


def git(cwd: Path, *args: str) -> str:
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
    return subprocess.run(["git", "-c", "init.defaultBranch=main", "-c", "commit.gpgsign=false", *args], cwd=cwd, env=env, check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def env(tmp_path: Path):
    home, bin_dir = tmp_path / "home", tmp_path / "bin"
    home.mkdir(); bin_dir.mkdir()
    (bin_dir / "act").write_text(STUB_ACT)
    (bin_dir / "docker").write_text("#!/bin/sh\nexit 0\n")
    for f in bin_dir.iterdir():
        f.chmod(0o755)
    remote, src = tmp_path / "remote.git", tmp_path / "src"
    git(tmp_path, "init", "-q", "--bare", str(remote))
    git(tmp_path, "init", "-q", str(src))
    (src / ".github" / "workflows").mkdir(parents=True)
    (src / ".github" / "workflows" / "tests.yml").write_text(WORKFLOW)
    (src / "a.txt").write_text("base\n")
    git(src, "add", "-A"); git(src, "commit", "-q", "-m", "base")
    git(src, "remote", "add", "origin", str(remote))
    git(src, "push", "-q", "origin", "main")
    git(src, "remote", "set-head", "origin", "main")
    git(src, "checkout", "-q", "-b", "feature")
    (src / "b.txt").write_text("feature\n")
    git(src, "add", "-A"); git(src, "commit", "-q", "-m", "feature")
    out = tmp_path / "act-call.json"
    run_env = {**os.environ, "HOME": str(home), "PATH": f"{bin_dir}:{os.environ['PATH']}", "CI_LOCAL_TEST_OUT": str(out)}
    return {"src": src, "remote": remote, "out": out, "env": run_env, "tmp": tmp_path}


def run(env, *args, **extra):
    e = {**env["env"], **extra}
    return subprocess.run(["bash", str(SCRIPT), str(env["src"]), *args], env=e, capture_output=True, text=True)


def call(env) -> dict:
    return json.loads(env["out"].read_text())


def test_pull_request_tests_the_merge_of_head_into_base(env):
    r = run(env, "--pr", "7")
    assert r.returncode == 0, r.stderr
    c = call(env)
    base, head = git(env["src"], "rev-parse", "main"), git(env["src"], "rev-parse", "feature")
    assert c["parents"] == [base, head]  # a merge commit, like refs/pull/N/merge
    assert c["event"]["pull_request"] == {"number": 7, "head": {"ref": "feature", "sha": head}, "base": {"ref": "main", "sha": base}}
    assert "succeeded  tests/unit" in r.stdout


def test_runner_size_cleanup_and_offline_flags(env):
    run(env)
    args = call(env)["args"]
    opts = args[args.index("--container-options") + 1]
    assert "--cpus 2" in opts and "--memory 7g" in opts
    assert ":/proc/cpuinfo:ro" in opts and ":/proc/stat:ro" in opts
    assert "--rm" in args and "--pull=false" in args
    assert "--action-offline-mode" in args  # nothing to fetch, so everything is cached


def test_uncommitted_edits_are_not_tested_and_say_so(env):
    (env["src"] / "a.txt").write_text("dirty\n")
    r = run(env)
    assert "uncommitted changes; they are NOT tested" in r.stderr
    assert not Path(call(env)["cwd"], "a.txt").read_text().startswith("dirty")


def test_conflict_fails_before_act(env):
    git(env["src"], "checkout", "-q", "main")
    (env["src"] / "b.txt").write_text("main side\n")
    git(env["src"], "add", "-A"); git(env["src"], "commit", "-q", "-m", "main side")
    git(env["src"], "push", "-q", "origin", "main")
    git(env["src"], "checkout", "-q", "feature")
    r = run(env)
    assert r.returncode == 2
    assert "does not merge cleanly" in r.stderr
    assert not env["out"].exists()


def test_push_of_a_remote_tracking_ref_names_the_branch_as_github_does(env):
    r = run(env, "--event", "push", "--ref", "origin/main")
    assert r.returncode == 0, r.stderr
    ev = call(env)["event"]
    assert ev["ref"] == "refs/heads/main"
    assert ev["after"] == git(env["src"], "rev-parse", "origin/main")


def test_detached_head_finds_a_real_branch(env):
    git(env["src"], "checkout", "-q", "--detach", "feature")
    run(env)
    assert call(env)["event"]["pull_request"]["head"]["ref"] == "feature"


def test_act_exit_code_is_returned(env):
    r = run(env, CI_LOCAL_TEST_RC="1")
    assert r.returncode == 1
    assert "ci-local: exit 1" in r.stdout


def test_a_cleanup_timeout_after_all_jobs_passed_is_a_pass(env):
    r = run(env, CI_LOCAL_TEST_RC="1", CI_LOCAL_TEST_FINALLY="1")
    assert r.returncode == 0
    assert "came only from removing a finished container" in r.stdout


def test_a_failed_job_still_fails_with_a_cleanup_timeout(env):
    r = run(env, CI_LOCAL_TEST_RC="1", CI_LOCAL_TEST_FINALLY="1", CI_LOCAL_TEST_JOB="failed")
    assert r.returncode == 1
    assert "failed  tests/unit" in r.stdout


def test_list_shows_acts_own_output(env):
    r = run(env, "--", "--list")
    assert r.returncode == 0
    assert "Job ID" in r.stdout


def test_offline_only_when_every_action_is_sha_pinned(env):
    sha = "a" * 40
    wf = env["src"] / ".github" / "workflows" / "tests.yml"
    wf.write_text(WORKFLOW + f"      - uses: acme/tool@{sha}\n      - uses: 'acme/kit/sub@{sha}'\n")
    git(env["src"], "commit", "-q", "-am", "pinned")
    run(env)
    assert "--action-offline-mode" in call(env)["args"]
    wf.write_text(WORKFLOW + f"      - uses: acme/tool@{sha}\n      - uses: acme/other@v4\n")
    git(env["src"], "commit", "-q", "-am", "tag")
    r = run(env)
    assert "--action-offline-mode" not in call(env)["args"]
    assert "pinned to a tag or branch" in r.stderr


def test_new_action_cache_and_job_cap(env):
    run(env)
    args = call(env)["args"]
    assert "--use-new-action-cache" in args
    assert args[args.index("--concurrent-jobs") + 1] == "4"
    run(env, CI_LOCAL_JOBS="2")
    args = call(env)["args"]
    assert args[args.index("--concurrent-jobs") + 1] == "2"
    assert run(env, CI_LOCAL_JOBS="zero").returncode == 2


def test_a_second_run_on_the_machine_is_refused(env):
    run(env)  # creates the lock file
    home = Path(env["env"]["HOME"])
    lock = home / "ci-local" / ".lock"
    holder = subprocess.Popen(["flock", str(lock), "sleep", "5"])
    try:
        import time
        time.sleep(0.3)
        r = run(env)
        assert r.returncode == 2
        assert "another ci-local run is in progress" in r.stderr
    finally:
        holder.kill()

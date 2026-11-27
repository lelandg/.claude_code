"""Tests for ci-local.sh. Real git repos in tmp_path; `act` and `docker` are stubs on PATH."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
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

# Records what act was asked to do, then answers like act: a job table for
# --list, otherwise one job-ID-prefixed completion line.
STUB_ACT = r"""#!/usr/bin/env bash
out="$CI_LOCAL_TEST_OUT"
ev=""; prev=""
for a in "$@"; do [ "$prev" = "-e" ] && ev="$a"; prev="$a"; done
python3 - "$out" "$ev" "$@" <<'PY'
import json, os, subprocess, sys
out, ev, *args = sys.argv[1:]
event = json.load(open(ev)) if ev else None
run = lambda *c: subprocess.run(list(c), capture_output=True, text=True).stdout.strip()
json.dump({"args": args, "event": event, "parents": run("git", "log", "-1", "--format=%P").split(),
           "head": run("git", "rev-parse", "HEAD"), "origin": run("git", "remote", "get-url", "origin"),
           "cwd": os.getcwd()}, open(out, "w"))
PY
if printf '%s\n' "$@" | grep -qx -- --list; then
  echo "Stage  Job ID  Job name  Workflow name  Workflow file  Events"
  echo "0      unit    unit      tests          tests.yml      pull_request,push"
  exit 0
fi
echo "[unit] 🏁  Job ${CI_LOCAL_TEST_JOB:-succeeded}"
if [ -n "${CI_LOCAL_TEST_FINALLY:-}" ]; then
  echo "Error: Error occurred running finally: context deadline exceeded (original error: <nil>)"
fi
exit "${CI_LOCAL_TEST_RC:-0}"
"""

# Answers like Docker for one job container of this run ("act-tests-unit-abc",
# found by the run's /proc mount) and lists one network of this run and one of
# another run. Logs every call.
STUB_DOCKER = r"""#!/usr/bin/env bash
echo "$*" >> "$CI_LOCAL_TEST_DOCKER_LOG"
case "$*" in
  "ps -a --filter volume="*"--format {{.ID}} {{.Names}}") echo "jobcontainer1 act-tests-unit-abc" ;;
  "network ls --filter name=^act- --format {{.ID}} {{.Name}}") printf '%s\n' "net1 act-tests-unit-abc-unit-network" "net2 act-other-run-xyz-other-network" ;;
  "network inspect -f "*" net1") echo "service1 " ;;
  "network inspect -f "*) echo "foreign1 " ;;
  "container inspect "*|"network inspect "*) [ -n "${CI_LOCAL_TEST_STUCK:-}" ] || exit 1 ;;
esac
exit 0
"""


def git(cwd: Path, *args: str) -> str:
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
    return subprocess.run(["git", "-c", "init.defaultBranch=main", "-c", "commit.gpgsign=false", *args], cwd=cwd, env=env, check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def env(tmp_path: Path):
    home, bin_dir = tmp_path / "home", tmp_path / "bin"
    home.mkdir(); bin_dir.mkdir()
    (bin_dir / "act").write_text(STUB_ACT)
    (bin_dir / "docker").write_text(STUB_DOCKER)
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
    out, docker_log = tmp_path / "act-call.json", tmp_path / "docker.log"
    run_env = {**os.environ, "HOME": str(home), "PATH": f"{bin_dir}:{os.environ['PATH']}",
               "CI_LOCAL_TEST_OUT": str(out), "CI_LOCAL_TEST_DOCKER_LOG": str(docker_log)}
    return {"src": src, "remote": remote, "out": out, "env": run_env, "tmp": tmp_path, "docker_log": docker_log}


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


def test_runner_size_cleanup_and_cache_flags(env):
    run(env)
    args = call(env)["args"]
    opts = args[args.index("--container-options") + 1]
    assert "--cpus 2" in opts and "--memory 7g" in opts
    assert ":/proc/cpuinfo:ro" in opts and ":/proc/stat:ro" in opts
    assert "--rm" in args and "--pull=false" in args and "--log-prefix-job-id" in args
    assert "--use-new-action-cache" in args
    assert "--action-offline-mode" in args  # no tag-pinned actions


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


def test_a_cleanup_timeout_after_all_planned_jobs_passed_is_a_pass(env):
    r = run(env, CI_LOCAL_TEST_RC="1", CI_LOCAL_TEST_FINALLY="1")
    assert r.returncode == 0, r.stdout
    assert "every planned job succeeded" in r.stdout


def test_a_failed_job_still_fails_with_a_cleanup_timeout(env):
    r = run(env, CI_LOCAL_TEST_RC="1", CI_LOCAL_TEST_FINALLY="1", CI_LOCAL_TEST_JOB="failed")
    assert r.returncode == 1
    assert "failed     tests/unit" in r.stdout


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


def test_job_cap(env):
    run(env)
    args = call(env)["args"]
    assert args[args.index("--concurrent-jobs") + 1] == "2"
    run(env, CI_LOCAL_JOBS="3")
    args = call(env)["args"]
    assert args[args.index("--concurrent-jobs") + 1] == "3"
    assert run(env, CI_LOCAL_JOBS="zero").returncode == 2


def test_cleanup_removes_only_this_runs_containers_and_networks(env):
    assert run(env).returncode == 0
    calls = env["docker_log"].read_text()
    assert "rm -f jobcontainer1" in calls
    assert "rm -f service1" in calls
    assert "network rm net1" in calls
    assert "network rm net2" not in calls
    assert "foreign1" not in calls


def test_back_to_back_runs_are_not_refused(env):
    # The watcher must not keep the lock (fd 9) after a run ends.
    assert run(env).returncode == 0
    r = run(env)
    assert r.returncode == 0, r.stderr


def test_the_clone_keeps_the_sources_github_identity(env):
    git(env["src"], "remote", "set-url", "origin", "https://github.com/acme/widget.git")
    r = run(env)  # origin/main is still known from the fixture's push
    assert r.returncode == 0, r.stderr
    assert call(env)["origin"] == "https://github.com/acme/widget.git"


def test_a_detached_commit_on_no_branch_is_fetched_by_id(env):
    run(env)  # the first run makes the clone
    git(env["src"], "checkout", "-q", "--detach", "feature")
    (env["src"] / "c.txt").write_text("loose\n")
    git(env["src"], "add", "-A"); git(env["src"], "commit", "-q", "-m", "loose")
    loose = git(env["src"], "rev-parse", "HEAD")
    r = run(env)
    assert r.returncode == 0, r.stderr
    assert call(env)["event"]["pull_request"]["head"]["sha"] == loose
    assert call(env)["parents"][1] == loose


def test_a_windows_worktree_pointer_is_followed(env):
    mnt = env["tmp"] / "mnt"
    main = mnt / "d" / "repo"
    main.parent.mkdir(parents=True)
    shutil.move(str(env["src"]), str(main))
    wt = env["tmp"] / "wt"
    git(main, "worktree", "add", "-q", "-b", "wt-branch", str(wt), "feature")
    (wt / ".git").write_text("gitdir: D:/repo/.git/worktrees/wt\n")
    e = {**env["env"], "CI_LOCAL_MNT": str(mnt)}
    r = subprocess.run(["bash", str(SCRIPT), str(wt)], env=e, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert call(env)["event"]["pull_request"]["head"]["ref"] == "wt-branch"


def test_a_second_run_on_the_machine_is_refused(env):
    run(env)  # creates the lock file
    lock = Path(env["env"]["HOME"]) / "ci-local" / ".lock"
    holder = subprocess.Popen(["flock", str(lock), "sleep", "5"])
    try:
        time.sleep(0.3)
        r = run(env)
        assert r.returncode == 2
        assert "another ci-local run is in progress" in r.stderr
    finally:
        holder.kill()


def test_a_container_docker_cannot_remove_is_reported(env):
    r = run(env, CI_LOCAL_TEST_STUCK="1")
    assert r.returncode == 0
    assert "could not remove this run's" in r.stderr
    leftovers = list((Path(env["env"]["HOME"]) / "ci-local" / "logs").glob("leftover-*.txt"))
    assert leftovers and "container:jobcontainer1" in leftovers[0].read_text()

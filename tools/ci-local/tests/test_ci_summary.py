"""Tests for ci_summary.py, from real `act --list` and log line shapes."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ci_summary  # noqa: E402

LIST = """\
Stage  Job ID  Job name                     Workflow name  Workflow file  Events
0      build   next build                   build          build.yml      pull_request,push
1      test    node --test (needs build)    tests          tests.yml      pull_request,push
"""
OK = "[build] 🏁  Job succeeded"
OK_TEST = "[test ] 🏁  Job succeeded"
FINALLY = "Error: Error occurred running finally: context deadline exceeded (original error: <nil>)"


def test_planned_jobs_reads_the_column_table():
    assert ci_summary.planned_jobs(LIST) == [("build", "build/next build", "build.yml"), ("test", "tests/node --test (needs build)", "tests.yml")]


def test_all_planned_jobs_passed_and_act_exited_zero():
    lines, verdict = ci_summary.decide(LIST, f"{OK}\n{OK_TEST}\n", 0)
    assert verdict == 0
    assert lines == ["succeeded  build/next build", "succeeded  tests/node --test (needs build)"]


def test_a_cleanup_timeout_after_every_planned_job_passed_is_a_pass():
    _, verdict = ci_summary.decide(LIST, f"{OK}\n{OK_TEST}\n{FINALLY}\n", 1)
    assert verdict == 10


def test_a_needs_stage_that_never_ran_is_not_a_pass():
    # act stops before `test` when cleanup of `build` times out.
    lines, verdict = ci_summary.decide(LIST, f"{OK}\n{FINALLY}\n", 1)
    assert verdict == 0  # act's exit 1 stands
    assert "not run    tests/node --test (needs build)" in lines


def test_another_error_keeps_acts_exit_code():
    _, verdict = ci_summary.decide(LIST, f"{OK}\n{OK_TEST}\n{FINALLY}\nError: Job 'x' failed\n", 1)
    assert verdict == 0


def test_a_failed_matrix_instance_fails_the_job():
    log = f"{OK}\n{OK_TEST}\n[test] 🏁  Job failed\n"
    lines, verdict = ci_summary.decide(LIST, log, 1)
    assert "failed     tests/node --test (needs build)" in lines
    assert verdict == 0


def test_job_output_that_mentions_success_is_not_a_result():
    log = f"{OK}\n[test]   | echo 'Job succeeded'\n"
    lines, _ = ci_summary.decide(LIST, log, 1)
    assert "not run    tests/node --test (needs build)" in lines


def test_a_job_skipped_by_its_condition_keeps_act_exit_zero():
    lines, verdict = ci_summary.decide(LIST, f"{OK}\n", 0)
    assert verdict == 0
    assert "skipped    tests/node --test (needs build)" in lines


def test_a_skip_blocks_the_cleanup_override():
    _, verdict = ci_summary.decide(LIST, f"{OK}\n{FINALLY}\n", 1)
    assert verdict == 0


def write(tmp_path, text, name="build.yml"):
    (tmp_path / name).write_text(text)
    return str(tmp_path)


def test_a_matrix_job_blocks_the_cleanup_override(tmp_path):
    wf = write(tmp_path, "jobs:\n  build:\n    strategy:\n      matrix:\n        n: [1, 2]\n  test:\n    steps: []\n")
    _, verdict = ci_summary.decide(LIST, f"{OK}\n{OK_TEST}\n{FINALLY}\n", 1, wf)
    assert verdict == 0


def test_a_reusable_workflow_reports_through_its_called_jobs(tmp_path):
    listing = "Stage  Job ID  Job name  Workflow name  Workflow file  Events\n0      ci      ci        main           main.yml       push\n"
    wf = write(tmp_path, "jobs:\n  ci:\n    uses: ./.github/workflows/inner.yml\n", "main.yml")
    lines, verdict = ci_summary.decide(listing, "[inner-build] 🏁  Job succeeded\n", 0, wf)
    assert "succeeded  main/ci" in lines
    assert "succeeded  inner-build (called workflow)" in lines
    assert verdict == 0
    lines, _ = ci_summary.decide(listing, "[inner-build] 🏁  Job failed\n", 1, wf)
    assert "failed     main/ci" in lines
    _, verdict = ci_summary.decide(listing, f"[inner-build] 🏁  Job succeeded\n{FINALLY}\n", 1, wf)
    assert verdict == 0  # its instances cannot all be confirmed


def test_without_a_plan_acts_exit_code_stands():
    _, verdict = ci_summary.decide("", f"{OK}\n{FINALLY}\n", 1)
    assert verdict == 0


def test_shared_job_ids_across_workflows_never_override():
    listing = LIST + "0      build   other build                  other          other.yml      push\n"
    _, verdict = ci_summary.decide(listing, f"{OK}\n{OK_TEST}\n{FINALLY}\n", 1)
    assert verdict == 0


def test_an_inline_matrix_blocks_the_cleanup_override(tmp_path):
    wf = write(tmp_path, "jobs:\n  build:\n    strategy: {matrix: {node: [20, 22]}}\n")
    _, verdict = ci_summary.decide(LIST, f"{OK}\n{OK_TEST}\n{FINALLY}\n", 1, wf)
    assert verdict == 0


def test_a_same_named_job_in_another_workflow_does_not_count(tmp_path):
    # deploy.yml has a reusable caller and a matrix both named `build`; build.yml's `build` is plain.
    wf = write(tmp_path, "jobs:\n  build:\n    uses: ./x.yml\n  test:\n    strategy:\n      matrix:\n        n: [1]\n", "deploy.yml")
    lines, verdict = ci_summary.decide(LIST, f"{OK}\n{OK_TEST}\n{FINALLY}\n", 1, wf)
    assert "succeeded  build/next build" in lines
    assert verdict == 10


def test_a_caller_whose_called_job_shares_its_id(tmp_path):
    listing = "Stage  Job ID  Job name  Workflow name  Workflow file  Events\n0      ci      ci        main           main.yml       push\n"
    wf = write(tmp_path, "jobs:\n  ci:\n    uses: ./.github/workflows/ci-inner.yml\n", "main.yml")
    lines, _ = ci_summary.decide(listing, "[ci] \U0001F3C1  Job failed\n", 1, wf)
    assert "failed     main/ci" in lines

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
    assert ci_summary.planned_jobs(LIST) == [("build", "build/next build"), ("test", "tests/node --test (needs build)")]


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


def test_exit_zero_with_a_missing_job_is_not_a_pass():
    _, verdict = ci_summary.decide(LIST, f"{OK}\n", 0)
    assert verdict == 11


def test_without_a_plan_acts_exit_code_stands():
    _, verdict = ci_summary.decide("", f"{OK}\n{FINALLY}\n", 1)
    assert verdict == 0


def test_shared_job_ids_across_workflows_never_override():
    listing = LIST + "0      build   other build                  other          other.yml      push\n"
    _, verdict = ci_summary.decide(listing, f"{OK}\n{OK_TEST}\n{FINALLY}\n", 1)
    assert verdict == 0

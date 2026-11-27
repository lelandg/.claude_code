"""Tests for act_compat.py. Port availability is injected; no test binds a real port."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import act_compat  # noqa: E402

WORKFLOW = """\
name: tests
on:
  pull_request:
jobs:
  db:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:17.4
        ports:
          - 5432:5432 # the database
        options: >-
          --health-cmd "pg_isready -U app"
    env:
      DATABASE_URL: postgresql://app:pw@localhost:5432/app_test
    steps:
      - run: psql -h 127.0.0.1 -p 5432 -c 'select 1' # unchanged: not host:port
      - run: curl http://127.0.0.1:5432/
"""

TWO_JOBS = """\
jobs:
  first:
    services:
      postgres:
        ports:
          - 5432:5432
    env:
      URL: postgresql://localhost:5432/one
  second:
    services:
      postgres:
        ports:
          - 5432:5432
    env:
      URL: postgresql://localhost:5432/two
"""


def ports(taken=()):
    return act_compat.Ports(first_free=45432, is_free=lambda p: p not in set(taken))


def job(text: str, name: str) -> str:
    start = text.index(f"  {name}:")
    nxt = [text.index(f"\n  {n}:", start + 1) for n in ("first", "second") if f"\n  {n}:" in text[start + 1:]]
    return text[start:min(nxt)] if nxt else text[start:]


def test_free_port_is_left_alone():
    out, report = act_compat.remap_text(WORKFLOW, ports(), "tests.yml")
    assert out == WORKFLOW
    assert report == []


def test_taken_port_moves_with_its_localhost_uses_and_keeps_comments():
    out, report = act_compat.remap_text(WORKFLOW, ports(taken={5432}), "tests.yml")
    assert "- 45432:5432 # the database" in out
    assert "@localhost:45432/app_test" in out
    assert "http://127.0.0.1:45432/" in out
    assert "-p 5432" in out  # a bare port number is not a host:port use
    assert out.count("\n") == WORKFLOW.count("\n")
    assert report == ["act-compat: tests.yml:db: host port 5432 is taken here; using 45432 (localhost:5432 -> localhost:45432)"]


def test_two_jobs_on_one_free_port_get_distinct_ports_each_with_its_own_localhost():
    out, _ = act_compat.remap_text(TWO_JOBS, ports(), "x.yml")
    first, second = job(out, "first"), job(out, "second")
    assert "- 5432:5432" in first and "localhost:5432/one" in first
    assert "- 45432:5432" in second and "localhost:45432/two" in second


def test_two_jobs_on_one_taken_port_never_share_the_new_port():
    out, _ = act_compat.remap_text(TWO_JOBS, ports(taken={5432}), "x.yml")
    first, second = job(out, "first"), job(out, "second")
    assert "- 45432:5432" in first and "localhost:45432/one" in first
    assert "- 45433:5432" in second and "localhost:45433/two" in second


def test_ports_stay_unique_across_files():
    shared = ports()
    act_compat.remap_text(WORKFLOW, shared, "a.yml")
    out, _ = act_compat.remap_text(WORKFLOW, shared, "b.yml")
    assert "- 45432:5432 # the database" in out


def test_rewrite_is_single_pass():
    # 5432 -> 45432 must not then match a later rule; the new port is never rewritten again.
    text = "jobs:\n  a:\n    services:\n      s:\n        ports:\n          - 5432:5432\n          - 45432:80\n    env:\n      A: localhost:5432\n"
    out, _ = act_compat.remap_text(text, ports(taken={5432, 45432}), "x.yml")
    assert "- 45433:5432" in out and "- 45434:80" in out
    assert "A: localhost:45433" in out


def test_quoted_ip_and_flow_style_mappings():
    text = 'jobs:\n  a:\n    services:\n      s:\n        ports: ["6379:6379", "127.0.0.1:5432:5432/tcp"]\n'
    out, _ = act_compat.remap_text(text, ports(taken={6379, 5432}), "x.yml")
    assert 'ports: ["45432:6379", "127.0.0.1:45433:5432/tcp"]' in out


def test_container_only_ports_and_other_lists_are_untouched():
    text = "jobs:\n  a:\n    services:\n      s:\n        ports:\n          - 5432\n        volumes:\n          - 5432:5432\n"
    out, report = act_compat.remap_text(text, ports(taken={5432}), "x.yml")
    assert out == text
    assert report == []


def test_main_rewrites_only_files_that_change(tmp_path, monkeypatch):
    (tmp_path / "a.yml").write_text(WORKFLOW)
    (tmp_path / "b.yaml").write_text("on: push\n")
    monkeypatch.setattr(act_compat, "bindable", lambda p: p != 5432)
    assert act_compat.main([str(tmp_path)]) == 0
    assert "45432:5432" in (tmp_path / "a.yml").read_text()
    assert (tmp_path / "b.yaml").read_text() == "on: push\n"


def test_service_health_checks_keep_the_containers_own_port():
    text = (
        "jobs:\n  a:\n    services:\n      es:\n        ports:\n          - 9200:9200\n"
        '        options: --health-cmd "curl -f http://localhost:9200/_cluster/health"\n'
        "    steps:\n      - run: curl http://localhost:9200/\n"
    )
    out, _ = act_compat.remap_text(text, ports(taken={9200}), "x.yml")
    assert "- 45432:9200" in out
    assert "http://localhost:9200/_cluster/health" in out  # runs inside the service
    assert "run: curl http://localhost:45432/" in out


def test_a_ports_key_outside_services_is_not_a_mapping():
    text = "jobs:\n  a:\n    steps:\n      - uses: acme/tool@v1\n        with:\n          ports:\n            - 5432:5432\n"
    out, report = act_compat.remap_text(text, ports(taken={5432}), "x.yml")
    assert out == text and report == []


def test_workflow_env_moves_into_each_job_that_moved_its_port():
    text = (
        "env:\n  DATABASE_URL: postgresql://localhost:5432/app\n  OTHER: keep\n"
        "jobs:\n"
        "  a:\n    services:\n      pg:\n        ports:\n          - 5432:5432\n    steps:\n      - run: echo a\n"
        "  b:\n    env:\n      DATABASE_URL: postgresql://localhost:5432/own\n    services:\n      pg:\n        ports:\n          - 5432:5432\n    steps:\n      - run: echo b\n"
        "  c:\n    steps:\n      - run: echo c\n"
    )
    out, report = act_compat.remap_text(text, ports(taken={5432}), "x.yml")
    assert out.startswith("env:\n  DATABASE_URL: postgresql://localhost:5432/app\n")  # workflow level untouched
    assert "  a:\n    env:\n      DATABASE_URL: postgresql://localhost:45432/app\n" in out
    assert "DATABASE_URL: postgresql://localhost:45433/own" in out  # b's own value, rewritten in place
    assert out.count("/app") == 2  # b keeps its override; c gets nothing
    assert any("workflow env DATABASE_URL copied" in r for r in report)


def test_matrix_with_published_ports_runs_one_instance_at_a_time():
    text = (
        "jobs:\n  a:\n    strategy:\n      matrix:\n        node: [20, 22]\n"
        "    services:\n      pg:\n        ports:\n          - 5432:5432\n"
    )
    out, report = act_compat.remap_text(text, ports(), "x.yml")
    assert "    strategy:\n      max-parallel: 1\n      matrix:\n" in out
    assert any("share its service ports" in r for r in report)


def test_other_matrices_are_capped_at_max_parallel():
    text = "jobs:\n  a:\n    strategy:\n      max-parallel: 10\n      matrix:\n        n: [1, 2, 3, 4, 5, 6]\n  b:\n    strategy:\n      max-parallel: 2\n      matrix:\n        n: [1, 2, 3]\n"
    out, _ = act_compat.remap_text(text, ports(), "x.yml", max_parallel=4)
    assert "max-parallel: 4\n      matrix:\n        n: [1, 2, 3, 4, 5, 6]" in out
    assert "max-parallel: 2\n      matrix:\n        n: [1, 2, 3]" in out


def test_main_rejects_bad_arguments():
    assert act_compat.main([]) == 2
    assert act_compat.main(["dir", "--max-parallel", "0"]) == 2
    assert act_compat.main(["dir", "--container-options"]) == 2


def test_inherited_env_follows_the_jobs_own_indentation_and_reports_only_added_keys():
    text = (
        "env:\n  URL: postgresql://localhost:5432/app\n  OTHER_URL: http://localhost:5432/x\n"
        "jobs:\n  a:\n    env:\n        OTHER_URL: mine\n    services:\n      pg:\n        ports:\n          - 5432:5432\n"
    )
    out, report = act_compat.remap_text(text, ports(taken={5432}), "x.yml")
    assert "    env:\n        URL: postgresql://localhost:45432/app\n        OTHER_URL: mine\n" in out
    assert [r for r in report if "copied" in r] == ["act-compat: x.yml:a: workflow env URL copied into the job with the new port"]


def test_inline_job_env_is_reported_not_broken():
    text = "env:\n  URL: localhost:5432\njobs:\n  a:\n    env: {A: b}\n    services:\n      pg:\n        ports: [5432:5432]\n"
    out, report = act_compat.remap_text(text, ports(taken={5432}), "x.yml")
    assert "env: {A: b}\n" in out
    assert any("written inline" in r for r in report)


OPTS = "--cpus 2 -v /r/proc/cpuinfo:/proc/cpuinfo:ro"


def test_a_string_job_container_gets_the_runner_options():
    text = "jobs:\n  a:\n    container: node:22\n    steps: []\n"
    out, _ = act_compat.remap_text(text, ports(), "x.yml", container_options=OPTS)
    assert f"    container:\n      image: node:22\n      options: {OPTS}\n    steps: []\n" in out


def test_a_mapping_job_container_keeps_its_options_and_gains_ours():
    plain = "jobs:\n  a:\n    container:\n      image: node:22\n      options: --user 1001\n"
    out, _ = act_compat.remap_text(plain, ports(), "x.yml", container_options=OPTS)
    assert f"options: --user 1001 {OPTS}\n" in out
    quoted = 'jobs:\n  a:\n    container:\n      image: node:22\n      options: "--user 1001"\n'
    out, _ = act_compat.remap_text(quoted, ports(), "x.yml", container_options=OPTS)
    assert f'options: "--user 1001 {OPTS}"\n' in out
    block = "jobs:\n  a:\n    container:\n      image: node:22\n      options: >-\n        --user 1001\n    steps: []\n"
    out, _ = act_compat.remap_text(block, ports(), "x.yml", container_options=OPTS)
    assert f"      options: >-\n        --user 1001\n        {OPTS}\n    steps: []\n" in out
    none = "jobs:\n  a:\n    container:\n      image: node:22\n"
    out, _ = act_compat.remap_text(none, ports(), "x.yml", container_options=OPTS)
    assert f"    container:\n      options: {OPTS}\n      image: node:22\n" in out


def test_an_inline_job_container_is_reported():
    text = "jobs:\n  a:\n    container: {image: node:22}\n"
    out, report = act_compat.remap_text(text, ports(), "x.yml", container_options=OPTS)
    assert out == text
    assert any("written inline" in r for r in report)

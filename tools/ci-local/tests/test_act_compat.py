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


def ports(taken=()):
    return act_compat.Ports(first_free=45432, is_free=lambda p: p not in set(taken))


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
    assert report == ["act-compat: tests.yml: host port 5432 is taken here; using 45432 (localhost:5432 -> localhost:45432)"]


def test_quoted_ip_and_flow_style_mappings():
    text = 'services:\n  a:\n    ports: ["6379:6379", "127.0.0.1:5432:5432/tcp"]\n'
    out, _ = act_compat.remap_text(text, ports(taken={6379, 5432}), "x.yml")
    assert out == 'services:\n  a:\n    ports: ["45432:6379", "127.0.0.1:45433:5432/tcp"]\n'


def test_two_services_never_share_a_new_port():
    text = "services:\n  a:\n    ports:\n      - 5432:5432\n  b:\n    ports:\n      - '5433:5432'\n"
    out, _ = act_compat.remap_text(text, ports(taken={5432, 5433, 45432}), "x.yml")
    assert "- 45433:5432" in out
    assert "- '45434:5432'" in out


def test_container_only_ports_and_other_lists_are_untouched():
    text = "services:\n  a:\n    ports:\n      - 5432\n    volumes:\n      - 5432:5432\n"
    out, report = act_compat.remap_text(text, ports(taken={5432}), "x.yml")
    assert out == text
    assert report == []


def test_main_rewrites_only_files_that_change(tmp_path, monkeypatch):
    (tmp_path / "a.yml").write_text(WORKFLOW)
    (tmp_path / "b.yaml").write_text("on: push\n")
    monkeypatch.setattr(act_compat, "bindable", lambda p: p != 5432)
    assert act_compat.main(str(tmp_path)) == 0
    assert "45432:5432" in (tmp_path / "a.yml").read_text()
    assert (tmp_path / "b.yaml").read_text() == "on: push\n"

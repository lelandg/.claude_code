"""Tests for council.py. Every test uses a tmp_path repo and a fake runner; none calls a model."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import council  # noqa: E402

CONFIG = """
schema_version = 1
default = ["astra", "neon"]

[members.astra]
cli = "codex"
model = "gpt-6-astra"
effort = "high"

[members.neon]
cli = "agy"
model = "gemini-4-neon"
effort = "high"

[members.claude]
cli = "claude"
model = "claude-opus-5-5"

[members.copilot]
cli = "copilot"
model = "gpt-6.1-terra"
effort = "low"
timeout = 600

[councils.security]
members = ["astra", "neon", "claude"]
"""


def sh(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    r.mkdir()
    sh(r, "init", "-q", "-b", "main")
    sh(r, "config", "user.email", "t@example.com")
    sh(r, "config", "user.name", "T")
    sh(r, "config", "commit.gpgsign", "false")
    (r / "a.txt").write_text("one\n", encoding="utf-8")
    sh(r, "add", "-A")
    sh(r, "commit", "-q", "-m", "base")
    sh(r, "branch", "base")
    (r / "a.txt").write_text("one\ntwo\n", encoding="utf-8")
    sh(r, "commit", "-q", "-am", "add two")
    return r


@pytest.fixture
def cfg_file(tmp_path: Path) -> Path:
    p = tmp_path / "council.toml"
    p.write_text(CONFIG, encoding="utf-8")
    return p


def write_cfg(tmp_path: Path, text: str) -> Path:
    p = tmp_path / "c.toml"
    p.write_text(text, encoding="utf-8")
    return p


def answer(head: str, verdict: str = "clean", findings=None, **extra) -> str:
    body = {"verdict": verdict, "reviewed_head": head, "findings": findings or [], "summary": "s", **extra}
    return "Some preamble.\n```json\n" + json.dumps(body) + "\n```\n"


def head_of(repo: Path) -> str:
    return sh(repo, "rev-parse", "HEAD").strip()


class FakeRunner:
    """Stands in for the CLIs. reply maps argv[0] to (code, stdout, stderr) or an exception."""

    def __init__(self, reply):
        self.reply = reply
        self.calls: list[council.Invocation] = []

    def __call__(self, inv: council.Invocation, timeout: int):
        self.calls.append(inv)
        r = self.reply[inv.argv[0]]
        if isinstance(r, BaseException):
            raise r
        code, out, err = r
        if inv.result_file is not None:      # codex writes its answer to -o
            inv.result_file.write_text(out, encoding="utf-8")
            out = ""
        return code, out, err


# ---------------------------------------------------------------- config

def test_loads_members_default_and_councils(cfg_file):
    cfg = council.load_config(cfg_file)
    assert cfg.default == ["astra", "neon"]
    assert cfg.councils == {"security": ["astra", "neon", "claude"]}
    assert cfg.members["copilot"].timeout == 600
    assert cfg.members["claude"].effort is None


@pytest.mark.parametrize("model", ["gpt-5.6-sol", "gpt-5.6", "GPT-5.6-SOL", "gpt-6-sol", "gpt-6.1-sol"])
def test_banned_models_are_refused(tmp_path, model):
    p = write_cfg(tmp_path, f'default=["x"]\n[members.x]\ncli="codex"\nmodel="{model}"\n')
    with pytest.raises(council.CouncilError, match="no agent may run"):
        council.load_config(p)


@pytest.mark.parametrize("model", ["gpt-5.6-terra", "gpt-6-astra", "claude-sonnet-5.5", "gpt-oss-120b-solar"])
def test_other_models_are_allowed(tmp_path, model):
    p = write_cfg(tmp_path, f'default=["x"]\n[members.x]\ncli="codex"\nmodel="{model}"\n')
    assert council.load_config(p).members["x"].model == model


@pytest.mark.parametrize("body,match", [
    ('cli="bash"\nmodel="m"', "known CLIs"),
    ('cli="codex"\nmodel="m; rm -rf /"', "plain model id"),
    ('cli="codex"\nmodel="m"\neffort="ultra"', "effort"),
    ('cli="codex"\nmodel="m"\ntimeout=5', "timeout"),
    ('cli="codex"\nmodel="m"\ncommand="evil"', "unknown keys"),
])
def test_bad_member_fields_are_refused(tmp_path, body, match):
    p = write_cfg(tmp_path, f'default=["x"]\n[members.x]\n{body}\n')
    with pytest.raises(council.CouncilError, match=match):
        council.load_config(p)


def test_default_naming_an_undefined_member_is_an_error(tmp_path):
    p = write_cfg(tmp_path, 'default=["ghost"]\n[members.x]\ncli="codex"\nmodel="m"\n')
    with pytest.raises(council.CouncilError, match="not a defined member"):
        council.load_config(p)


def test_config_lookup_order(tmp_path, monkeypatch):
    user = tmp_path / "user.toml"
    monkeypatch.setattr(council, "USER_CONFIG", user)
    assert council.find_config(None, {}) == council.BUNDLED_CONFIG
    user.write_text("x", encoding="utf-8")
    assert council.find_config(None, {}) == user
    assert council.find_config(None, {"AGENT_COUNCIL_CONFIG": "e.toml"}) == Path("e.toml")
    assert council.find_config("c.toml", {"AGENT_COUNCIL_CONFIG": "e.toml"}) == Path("c.toml")


def test_bundled_config_is_valid():
    cfg = council.load_config(council.BUNDLED_CONFIG)
    assert cfg.default and all(n in cfg.members for n in cfg.default)


# ---------------------------------------------------------------- project overlay

def test_project_overlay_can_change_seating(cfg_file, repo):
    (repo / ".agents").mkdir()
    (repo / ".agents" / "council.toml").write_text(
        'default = ["astra", "claude"]\nfocus = "Stripe is live."\n[councils.ui]\nmembers = ["neon"]\n',
        encoding="utf-8")
    cfg = council.load_config(cfg_file, repo)
    assert cfg.default == ["astra", "claude"]
    assert cfg.councils["ui"] == ["neon"] and "security" in cfg.councils
    assert cfg.focus == "Stripe is live."
    assert len(cfg.sources) == 2


def test_project_overlay_cannot_define_members(cfg_file, repo):
    (repo / ".agents").mkdir()
    (repo / ".agents" / "council.toml").write_text(
        'default = ["evil"]\n[members.evil]\ncli = "codex"\nmodel = "gpt-6-astra"\n', encoding="utf-8")
    with pytest.raises(council.CouncilError, match="may set only"):
        council.load_config(cfg_file, repo)


def test_project_overlay_cannot_seat_an_undefined_member(cfg_file, repo):
    (repo / ".agents").mkdir()
    (repo / ".agents" / "council.toml").write_text('default = ["ghost"]\n', encoding="utf-8")
    with pytest.raises(council.CouncilError, match="not a defined member"):
        council.load_config(cfg_file, repo)


# ---------------------------------------------------------------- seating

def test_seating(cfg_file):
    cfg = council.load_config(cfg_file)
    assert [m.name for m in council.seat(cfg, None, None)] == ["astra", "neon"]
    assert [m.name for m in council.seat(cfg, None, "security")] == ["astra", "neon", "claude"]
    assert [m.name for m in council.seat(cfg, "copilot, astra,copilot", None)] == ["copilot", "astra"]
    for members, named, match in [("astra", "security", "not both"), ("ghost", None, "unknown member"),
                                  (None, "ghost", "no council named")]:
        with pytest.raises(council.CouncilError, match=match):
            council.seat(cfg, members, named)


# ---------------------------------------------------------------- drivers

def job_for(cfg, name, tmp_path, prompt="PROMPT TEXT"):
    return council.Job(cfg.members[name], tmp_path / "repo", tmp_path / "out" / name, tmp_path / "out",
                       prompt, [tmp_path / "rules"])


def test_codex_driver_is_read_only_and_pins_model(cfg_file, tmp_path):
    inv = council.drive_codex(job_for(council.load_config(cfg_file), "astra", tmp_path))
    a = inv.argv
    assert a[:4] == ["codex", "exec", "-m", "gpt-6-astra"]
    assert a[a.index("-s") + 1] == "read-only"
    assert "model_reasoning_effort=high" in a and "--ephemeral" in a and a[-1] == "-"
    assert inv.stdin == "PROMPT TEXT" and inv.result_file is not None
    assert not any(x in a for x in ("workspace-write", "danger-full-access"))


def test_agy_driver_is_plan_sandbox_with_prompt_as_argument(cfg_file, tmp_path):
    inv = council.drive_agy(job_for(council.load_config(cfg_file), "neon", tmp_path))
    a = inv.argv
    assert a[a.index("--model") + 1] == "gemini-4-neon-high"
    assert a[a.index("--mode") + 1] == "plan" and "--sandbox" in a
    assert a[-1] == "-p=PROMPT TEXT" and inv.stdin is None
    assert str(tmp_path / "rules") in a


def test_copilot_driver_denies_write_and_shell(cfg_file, tmp_path):
    inv = council.drive_copilot(job_for(council.load_config(cfg_file), "copilot", tmp_path))
    a = inv.argv
    assert {"--deny-tool=write", "--deny-tool=shell", "--allow-tool=read", "--no-ask-user"} <= set(a)
    assert a[a.index("--model") + 1] == "gpt-6.1-terra" and a[a.index("--reasoning-effort") + 1] == "low"
    assert inv.stdin == "PROMPT TEXT"


def test_claude_driver_is_plan_mode_with_read_tools_only(cfg_file, tmp_path):
    inv = council.drive_claude(job_for(council.load_config(cfg_file), "claude", tmp_path))
    a = inv.argv
    assert a[a.index("--permission-mode") + 1] == "plan"
    tools = a[a.index("--tools") + 1:a.index("--no-session-persistence")]
    assert tools == ["Read", "Grep", "Glob"] and "--effort" not in a


# ---------------------------------------------------------------- the change

def test_collect_change_writes_diff_and_log(repo, tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    change = council.collect_change(repo, "base", "HEAD", out)
    assert "+two" in (out / "change.diff").read_text(encoding="utf-8")
    assert "add two" in (out / "commits.txt").read_text(encoding="utf-8")
    assert change["head_sha"] == head_of(repo) and change["subject"] == "add two"
    assert change["worktree_differs_from_head"] is False


def test_empty_change_and_option_like_refs_are_errors(repo, tmp_path):
    with pytest.raises(council.CouncilError, match="nothing to review"):
        council.collect_change(repo, "HEAD", "HEAD", tmp_path)
    with pytest.raises(council.CouncilError, match="not options"):
        council.collect_change(repo, "--output=x", "HEAD", tmp_path)


def test_uncommitted_edits_are_flagged(repo, tmp_path):
    (repo / "a.txt").write_text("dirty\n", encoding="utf-8")
    assert council.collect_change(repo, "base", "HEAD", tmp_path)["worktree_differs_from_head"] is True


def test_default_base_prefers_origin_head_then_main_then_master(repo):
    with pytest.raises(council.CouncilError, match="cannot find the base"):
        council.default_base(repo)
    sh(repo, "update-ref", "refs/remotes/origin/master", "base")
    assert council.default_base(repo) == "origin/master"
    sh(repo, "update-ref", "refs/remotes/origin/main", "base")
    assert council.default_base(repo) == "origin/main"
    sh(repo, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/master")
    assert council.default_base(repo) == "origin/master"


def test_prompt_fills_every_field(repo, tmp_path):
    change = council.collect_change(repo, "base", "HEAD", tmp_path)
    prompt = council.build_prompt(council.PROMPT_TEMPLATE.read_text(encoding="utf-8"), repo, change,
                                  tmp_path, "", "Add the second line.", [repo / "AGENTS.md"])
    assert "{{" not in prompt
    assert change["head_sha"] in prompt and "Add the second line." in prompt
    assert str(tmp_path / "change.diff") in prompt and str(repo / "AGENTS.md") in prompt
    with pytest.raises(council.CouncilError, match="unknown fields"):
        council.build_prompt("x {{NOPE}}", repo, change, tmp_path, "", "", [])


# ---------------------------------------------------------------- judging answers

HEAD = "a" * 40


@pytest.mark.parametrize("code,text,expect", [
    (0, answer(HEAD), ("ok", "")),
    (0, answer(HEAD, "findings", [{"severity": "major", "file": "a", "line": 1, "title": "t"}]), ("ok", "")),
    (0, answer(HEAD[:12]), ("ok", "")),
    (1, answer(HEAD), ("failed", "exit 1")),
    (0, "", ("failed", "empty answer")),
    (0, "   \n", ("failed", "empty answer")),
    (0, "Looks good to me!", ("failed", "no JSON object")),
    (0, '```json\n{"verdict": "clean", "reviewed_head": "' + HEAD, ("failed", "no JSON object")),
    (0, answer(HEAD, "incomplete", not_reviewed=["shell refused"]), ("failed", "incomplete: shell refused")),
    (0, answer("b" * 40), ("failed", "not aaaaaaaaaaaa")),
    (0, answer(""), ("failed", "no commit")),
    (0, answer(HEAD, "approved"), ("failed", "unknown verdict")),
    (0, answer(HEAD, "clean", [{"title": "x"}]), ("failed", "clean but findings")),
])
def test_judge(code, text, expect):
    status, detail, _ = council.judge(code, text, "boom", HEAD)
    assert status == expect[0] and expect[1] in detail


def test_parse_answer_takes_the_last_json_block_and_bare_json():
    two = '```json\n{"verdict": "findings"}\n```\ntext\n```json\n{"verdict": "clean"}\n```'
    assert council.parse_answer(two)["verdict"] == "clean"
    assert council.parse_answer('prefix {"verdict": "clean", "findings": []} suffix')["verdict"] == "clean"
    assert council.parse_answer('```json\n{"other": 1}\n```') is None


# ---------------------------------------------------------------- end to end

def run(cfg_file, repo, tmp_path, runner, *extra):
    return council.main(["--config", str(cfg_file), "review", "--repo", str(repo), "--base", "base",
                         "--out", str(tmp_path / "out"), *extra], runner)


def test_review_all_members_clean_exits_0(cfg_file, repo, tmp_path, capsys):
    ok = (0, answer(head_of(repo)), "")
    runner = FakeRunner({"codex": ok, "agy": ok})
    assert run(cfg_file, repo, tmp_path, runner) == council.EXIT_OK
    out = tmp_path / "out"
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert [m["status"] for m in summary["members"]] == ["ok", "ok"]
    assert (out / "astra" / "result.md").read_text(encoding="utf-8").strip()
    assert "PROMPT" not in (out / "neon" / "cmd.txt").read_text(encoding="utf-8").upper().replace("<PROMPT.MD>", "")
    assert "| astra | gpt-6-astra (high) | ok | clean | 0 |" in capsys.readouterr().out
    # every member got the same prompt
    sent = [c.stdin or c.argv[-1][3:] for c in runner.calls]
    assert sent[0] == sent[1] == (out / "prompt.md").read_text(encoding="utf-8")


def test_one_failed_member_exits_10_and_is_named(cfg_file, repo, tmp_path, capsys):
    runner = FakeRunner({"codex": (0, answer(head_of(repo)), ""), "agy": (0, "", "tool read_file denied")})
    assert run(cfg_file, repo, tmp_path, runner) == council.EXIT_MEMBER_FAILED
    text = capsys.readouterr().out
    assert "FAILED: empty answer: tool read_file denied" in text
    assert "Failed members did not review this change: neon" in text


def test_missing_cli_and_timeout_are_failures_not_crashes(cfg_file, repo, tmp_path):
    runner = FakeRunner({"codex": FileNotFoundError("codex"),
                         "agy": subprocess.TimeoutExpired("agy", 1800)})
    assert run(cfg_file, repo, tmp_path, runner) == council.EXIT_MEMBER_FAILED
    members = json.loads((tmp_path / "out" / "summary.json").read_text(encoding="utf-8"))["members"]
    assert "not installed" in members[0]["detail"] and "timed out" in members[1]["detail"]


def test_findings_are_listed_per_member(cfg_file, repo, tmp_path, capsys):
    f = [{"severity": "major", "file": "a.txt", "line": 2, "title": "second line is wrong"}]
    runner = FakeRunner({"codex": (0, answer(head_of(repo), "findings", f), "")})
    assert run(cfg_file, repo, tmp_path, runner, "--members", "astra") == council.EXIT_OK
    assert "- **astra** [major] `a.txt:2` second line is wrong" in capsys.readouterr().out


def test_adversarial_flag_and_purpose_reach_the_prompt(cfg_file, repo, tmp_path):
    runner = FakeRunner({"codex": (0, answer(head_of(repo)), "")})
    run(cfg_file, repo, tmp_path, runner, "--members", "astra", "--adversarial", "--purpose", "Fix billing.")
    prompt = (tmp_path / "out" / "prompt.md").read_text(encoding="utf-8")
    assert "Adversarial pass." in prompt and "Fix billing." in prompt


def test_dry_run_calls_nobody(cfg_file, repo, tmp_path, capsys):
    runner = FakeRunner({})
    assert run(cfg_file, repo, tmp_path, runner, "--dry-run") == council.EXIT_OK
    assert runner.calls == []
    out = capsys.readouterr().out
    assert "astra: codex exec -m gpt-6-astra" in out and "-p=<prompt.md>" in out


def test_max_effort_needs_the_flag(tmp_path, repo):
    p = write_cfg(tmp_path, 'default=["x"]\n[members.x]\ncli="codex"\nmodel="gpt-6-astra"\neffort="max"\n')
    ok = FakeRunner({"codex": (0, answer(head_of(repo)), "")})
    assert run(p, repo, tmp_path, ok) == council.EXIT_ERROR and ok.calls == []
    assert run(p, repo, tmp_path, ok, "--allow-max") == council.EXIT_OK


def test_config_errors_exit_20(tmp_path, repo, capsys):
    assert run(tmp_path / "missing.toml", repo, tmp_path, FakeRunner({})) == council.EXIT_ERROR
    assert "config not found" in capsys.readouterr().err


def test_list_shows_seating(cfg_file, capsys):
    assert council.main(["--config", str(cfg_file), "list"]) == council.EXIT_OK
    out = capsys.readouterr().out
    assert "default: astra, neon" in out and "council security: astra, neon, claude" in out

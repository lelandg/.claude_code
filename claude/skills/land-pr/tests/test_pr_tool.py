"""Tests for pr_tool.py.

Classification and release-plan tests are pure. The bump tests build real git
repositories (a bare origin plus a clone) and run the real version tool, so a
failure there means a real branch would be mishandled at landing.

    python -m pytest ~/.claude/skills/land-pr/tests/ -q
"""
from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pr_tool as pt  # noqa: E402

# The shipped OWNERS are placeholders; pin a known set so the tests do not
# depend on what a user has configured.
pt.OWNERS = ["octo-user", "Octo-Org"]

NOW = datetime(2026, 11, 11, 15, 0, tzinfo=timezone.utc)
ME = {"octo-user"}


def make(**kw) -> pt.PR:
    base = dict(repo="octo-user/r", number=7, title="fix: thing", author="octo-user",
                head="fix/thing", head_oid="a" * 40,
                updated=NOW - timedelta(hours=2),
                head_committed=NOW - timedelta(hours=2),
                files=["src/app.py"], files_total=1,
                subjects=["fix: thing"], checks=[("ci", "pass")],
                reviewer_seen=True)
    base.update(kw)
    return pt.PR(**base)


def state(**kw) -> str:
    return pt.classify(make(**kw), NOW, ME).label


# ---- classification -------------------------------------------------------

def test_green_reviewed_pr_is_ready():
    assert state() == "READY"


def test_pending_check_waits_and_failing_check_fails():
    assert state(checks=[("ci", "pass"), ("CodeRabbit", "pending")]) == "WAITING"
    assert state(checks=[("ci", "fail"), ("x", "pending")]) == "FAILING"


def test_unresolved_thread_blocks_even_when_outdated():
    thread = {"id": "T1", "path": "a.py", "line": 3, "outdated": True,
              "author": "coderabbitai", "body": "x", "url": ""}
    assert state(threads=[thread]) == "THREADS"


def test_conflict_and_blocked():
    assert state(mergeable="CONFLICTING") == "CONFLICT"
    assert state(merge_state="BLOCKED") == "BLOCKED"


def test_review_grace_only_while_no_reviewer_and_fresh_push():
    fresh = NOW - timedelta(minutes=3)
    assert state(reviewer_seen=False, head_committed=fresh) == "WAITING"
    assert state(reviewer_seen=False) == "READY"          # grace expired
    assert state(reviewer_seen=False, head_committed=fresh,
                 author="dependabot", author_is_bot=True) == "READY"


def test_outside_contributor_is_never_ready():
    assert state(author="Mr-Neutr0n") == "EXTERNAL"


def test_autofix_follows_its_source():
    assert state(head="autofix/pr-3", draft=True,
                 autofix_source_state="MERGED") == "SUPERSEDED"
    assert state(head="autofix/pr-3", draft=True,
                 autofix_source_state="OPEN") == "AUTOFIX"


def test_stale_marks_only_stuck_states():
    old = NOW - timedelta(days=40)
    assert state(draft=True, updated=old) == "STALE(DRAFT)"
    assert state(mergeable="CONFLICTING", updated=old) == "STALE(CONFLICT)"
    assert state(updated=old) == "STALE(READY)"   # parked: sweep leaves it


def test_my_pr_in_someone_elses_repo_is_theirs_to_merge():
    assert state(repo="someone-else/their-repo") == "ELSEWHERE"
    assert state(repo="octo-org/x") == "READY"   # owner match ignores case


def test_owner_override_reaches_classification(monkeypatch):
    # PR_TOOL_OWNERS must change what counts as "home", not only which PRs
    # the survey query returns: otherwise every row comes back ELSEWHERE.
    theirs = make(repo="acme/widgets", author="pat")
    assert pt.classify(theirs, NOW, {"pat"}).label == "ELSEWHERE"
    monkeypatch.setenv("PR_TOOL_OWNERS", "acme")
    assert pt.classify(theirs, NOW, {"pat"}).label == "READY"
    assert pt.classify(make(), NOW, ME).label == "ELSEWHERE"   # octo-user is not home now


def test_survey_classifies_with_the_owners_it_was_given(monkeypatch):
    theirs = make(repo="acme/widgets", author="pat")
    monkeypatch.setattr(pt, "collect", lambda owners, repo: [("acme/widgets", 7)])
    monkeypatch.setattr(pt, "fetch_pr", lambda repo, number: theirs)
    assert [v.label for _, v in pt.survey(["acme"], None, {"pat"})] == ["READY"]
    assert [v.label for _, v in pt.survey(["octo-user"], None, {"pat"})] == ["ELSEWHERE"]


def test_sensitive_paths_need_recorded_adversarial_review():
    files = ["lib/auth/session.ts"]
    assert state(files=files) == "REVIEW"
    assert state(files=files, body="Adversarial Codex review: clean") == "READY"
    # a test file with 'auth' in its name ships nothing and is not sensitive
    assert state(files=["tests/test_auth.py"]) == "READY"


def test_check_bucket_maps_rollup_nodes():
    run = lambda **k: pt.check_bucket({"__typename": "CheckRun", **k})[1]  # noqa: E731
    assert run(status="IN_PROGRESS", conclusion=None) == "pending"
    assert run(status="COMPLETED", conclusion="SUCCESS") == "pass"
    assert run(status="COMPLETED", conclusion="NEUTRAL") == "skip"
    assert run(status="COMPLETED", conclusion="TIMED_OUT") == "fail"
    # GitHub can report a stale status beside a real conclusion: the
    # conclusion wins, in both directions.
    assert run(status="IN_PROGRESS", conclusion="SUCCESS") == "pass"
    assert run(status="IN_PROGRESS", conclusion="FAILURE") == "fail"
    assert run(status="QUEUED", conclusion=None) == "pending"
    ctx = lambda s: pt.check_bucket({"__typename": "StatusContext",  # noqa: E731
                                     "context": "CodeRabbit", "state": s})[1]
    assert (ctx("SUCCESS"), ctx("PENDING"), ctx("ERROR")) == ("pass", "pending", "fail")


# ---- release plan ---------------------------------------------------------

BODY = """## What

Fixes the thing.

## Release notes

Release: minor

### Added
- A new thing users can see.

### Fixed
- The old thing.

## Verification

- tests pass

<!-- coderabbit summary -->
"""


def test_release_line_and_notes_come_from_the_body():
    plan = pt.release_plan(make(body=BODY))
    assert plan.level == "minor"
    assert plan.notes.startswith("### Added")
    assert "The old thing." in plan.notes
    assert "Verification" not in plan.notes and "Release:" not in plan.notes


def test_notes_stop_at_reviewer_markers():
    body = "## Release notes\n- one\n\n<!-- bot -->\n## Summary by CodeRabbit\n- x"
    assert pt.release_notes(body) == "- one"


def test_ci_only_pr_lands_without_a_bump():
    plan = pt.release_plan(make(files=[".github/workflows/security.yml"]))
    assert plan.level == "none"


def test_level_falls_back_to_commit_subjects():
    assert pt.release_plan(make()).level == "patch"
    assert pt.release_plan(make(subjects=["feat(x): y", "fix: z"])).level == "minor"
    assert pt.release_plan(make(subjects=["feat!: drop v1"])).level == "major"


def test_truncated_file_list_never_proves_ships_nothing():
    pr = make(files=[".github/a.yml"], files_total=250)
    assert pt.release_plan(pr).level == "patch"


def test_explicit_release_line_beats_the_path_heuristic():
    pr = make(files=[".github/a.yml"], body="Release: patch")
    assert pt.release_plan(pr).level == "patch"
    assert pt.release_plan(make(body="**Release:** none")).level == "none"


def test_bot_and_no_bump():
    assert pt.release_plan(make(author_is_bot=True)).level == "none"
    assert pt.release_plan(make(), no_bump=True).level == "none"


def test_squash_subject_replaces_a_stale_title_version():
    assert pt.squash_subject("fix(admin): lint (v0.22.5)", 449, "0.22.7") \
        == "fix(admin): lint (v0.22.7) (#449)"
    assert pt.squash_subject("ci: template", 3, None) == "ci: template (#3)"


def test_parse_ref():
    assert pt.parse_ref("octo-user/example#63") == ("octo-user/example", 63)
    assert pt.parse_ref("https://github.com/a/b.c/pull/9") == ("a/b.c", 9)
    with pytest.raises(pt.ToolError):
        pt.parse_ref("nope")


# ---- changelog surgery ----------------------------------------------------

def test_strip_sections_removes_only_unknown_versions():
    vt, _ = pt.load_version_tool()
    text = ("# Changelog\n\n## [1.1.0] - 2026-11-01\n\n- branch notes\n\n"
            "## [1.0.0] - 2026-10-01\n\n- old\n")
    out, removed = pt.strip_sections(text, {"1.0.0"}, vt.CHANGELOG_HEADING)
    assert "1.1.0" not in out and "## [1.0.0]" in out and "- old" in out
    assert removed == ["- branch notes"]


# ---- real git: the bump at landing ---------------------------------------

def sh(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(cwd), *args], check=True,
                          capture_output=True, text=True).stdout.strip()


CHANGELOG = "# Changelog\n\n## [1.0.0] - 2026-10-01\n\n- first\n"


@pytest.fixture
def repo(tmp_path: Path):
    """A clone on branch `feature` of an origin whose main is at 1.0.0."""
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", "-b", "main", str(origin)],
                   check=True, capture_output=True)
    work = tmp_path / "work"
    subprocess.run(["git", "clone", str(origin), str(work)],
                   check=True, capture_output=True)
    nohooks = tmp_path / "nohooks"
    nohooks.mkdir()
    for key, value in (("user.name", "t"), ("user.email", "t@example.invalid"),
                       ("core.hooksPath", str(nohooks)),
                       ("commit.gpgsign", "false"), ("core.autocrlf", "false")):
        sh(work, "config", key, value)
    (work / "package.json").write_bytes(
        b'{\n  "name": "x",\n  "version": "1.0.0",\n  "private": true,\n'
        b'  "description": "fixture",\n  "scripts": {\n    "test": "true"\n  },\n'
        b'  "dependencies": {}\n}\n')
    (work / "CHANGELOG.md").write_bytes(CHANGELOG.encode())
    (work / "app.js").write_bytes(b"1\n")
    sh(work, "add", "-A")
    sh(work, "commit", "-m", "chore(release): v1.0.0")
    sh(work, "push", "origin", "HEAD:main")
    sh(work, "checkout", "-b", "feature")
    return work


def commit(work: Path, name: str, data: str, msg: str) -> None:
    (work / name).write_bytes(data.encode())
    sh(work, "add", "-A")
    sh(work, "commit", "-m", msg)


def advance_main(work: Path, version: str) -> None:
    """Simulate another PR landing on origin/main with its own bump."""
    sh(work, "checkout", "-q", "--detach", "origin/main")
    pkg = (work / "package.json").read_bytes().decode()
    old = pkg.split('"version": "')[1].split('"')[0]
    (work / "package.json").write_bytes(pkg.replace(old, version).encode())
    log = (work / "CHANGELOG.md").read_bytes().decode()
    (work / "CHANGELOG.md").write_bytes(log.replace(
        "## [", f"## [{version}] - 2026-11-10\n\n- other PR\n\n## [", 1).encode())
    (work / "other.js").write_bytes(b"other\n")
    sh(work, "add", "-A")
    sh(work, "commit", "-m", f"fix: other (v{version})")
    sh(work, "push", "origin", "HEAD:main")
    sh(work, "fetch", "origin")
    sh(work, "checkout", "-q", "feature")


def never(_tag: str) -> bool:
    return False


def prepare(work: Path, tmp_path: Path, level="patch", notes=None, taken=never):
    vt, vt_path = pt.load_version_tool()
    scratch = tmp_path / "scratch"
    scratch.mkdir(exist_ok=True)
    return pt.prepare_branch(vt, vt_path, work, "origin/main", level, notes,
                             taken, scratch)


def test_fresh_branch_gets_one_bump_and_no_tag(repo, tmp_path):
    commit(repo, "app.js", "2\n", "fix: app")
    vt, _ = pt.load_version_tool()
    assert pt.bump_state(vt, repo, "origin/main", never) == ("absent", "1.0.0")
    assert prepare(repo, tmp_path, notes="### Fixed\n- The app.") == "1.0.1"
    assert '"version": "1.0.1"' in (repo / "package.json").read_text()
    log = (repo / "CHANGELOG.md").read_text()
    assert "## [1.0.1]" in log and "- The app." in log
    assert sh(repo, "log", "-1", "--format=%s") == "chore(release): v1.0.1"
    assert sh(repo, "tag") == ""                     # the lander tags after merge
    assert pt.bump_state(vt, repo, "origin/main", never) == ("current", "1.0.1")


def test_stale_bump_is_dropped_and_recut_after_main_moves(repo, tmp_path):
    commit(repo, "app.js", "2\n", "fix: app")
    assert prepare(repo, tmp_path, notes="- Hand-written branch notes.") == "1.0.1"
    advance_main(repo, "1.0.1")                      # someone else took 1.0.1
    vt, _ = pt.load_version_tool()
    assert pt.bump_state(vt, repo, "origin/main", never)[0] == "stale"

    assert prepare(repo, tmp_path) == "1.0.2"        # no notes passed this time
    log = (repo / "CHANGELOG.md").read_text()
    assert log.count("## [1.0.1]") == 1 and "- other PR" in log
    assert "## [1.0.2]" in log
    # the branch's own notes were carried over from the dropped section
    section = log.split("## [1.0.2]")[1].split("## [1.0.1]")[0]
    assert "Hand-written branch notes." in section
    assert (repo / "other.js").exists()              # main was merged in
    assert sh(repo, "status", "--porcelain") == ""


def test_dropping_a_bump_keeps_other_edits_to_the_version_file(repo, tmp_path):
    pkg = (repo / "package.json").read_text().replace(
        '"dependencies": {}', '"dependencies": {"left-pad": "1.3.0"}')
    commit(repo, "package.json", pkg, "feat: add left-pad")
    assert prepare(repo, tmp_path, level="minor") == "1.1.0"
    advance_main(repo, "1.0.1")
    assert prepare(repo, tmp_path, level="minor") == "1.1.0"   # 1.0.1 -> 1.1.0
    text = (repo / "package.json").read_text()
    assert '"left-pad": "1.3.0"' in text and '"version": "1.1.0"' in text


def test_taken_tag_makes_a_bump_stale(repo, tmp_path):
    commit(repo, "app.js", "2\n", "fix: app")
    prepare(repo, tmp_path)
    vt, _ = pt.load_version_tool()
    taken = lambda tag: tag == "v1.0.1"  # noqa: E731
    assert pt.bump_state(vt, repo, "origin/main", taken)[0] == "stale"


def test_real_conflict_with_main_is_refused_and_left_clean(repo, tmp_path):
    commit(repo, "other.js", "mine\n", "feat: other")
    advance_main(repo, "1.0.1")                      # also writes other.js
    with pytest.raises(pt.ToolError, match="conflicts in: other.js"):
        prepare(repo, tmp_path)
    assert sh(repo, "status", "--porcelain") == ""


def test_bump_keeps_lf_line_endings(repo, tmp_path):
    commit(repo, "app.js", "2\n", "fix: app")
    prepare(repo, tmp_path)
    assert b"\r\n" not in (repo / "package.json").read_bytes()
    assert b"\r\n" not in (repo / "CHANGELOG.md").read_bytes()


def test_local_draft_tag_is_moved_aside_not_deleted(repo, tmp_path):
    commit(repo, "app.js", "2\n", "fix: app")
    sh(repo, "tag", "v1.0.1")                        # left by an older flow
    assert prepare(repo, tmp_path) == "1.0.1"
    tags = sh(repo, "tag").split()
    assert "v1.0.1" not in tags
    assert any(t.startswith("v1.0.1-draft-") for t in tags)

#!/usr/bin/env python3
"""PR lander: drive every pull request to merged or closed.

    pr_tool.py status  [--repo OWNER/NAME] [--owner LOGIN ...] [--json]
    pr_tool.py land    OWNER/NAME#N | URL [--apply] [--level L] [--no-bump]
                       [--method squash|merge|rebase] [--clone PATH] [--wait MIN]
    pr_tool.py sweep   [--repo OWNER/NAME] [--owner LOGIN ...] [--apply]
                       [--max N] [--wait MIN]
    pr_tool.py threads OWNER/NAME#N [--resolve ID ...]

Standard library plus the `gh` and `git` CLIs. Read-only until --apply (or
--resolve) is passed.

Exit codes: 0 done or nothing to do; 1 refused or error; 3 waiting on checks
(re-run the same command); 10 work is pending (status, sweep dry run).

`land` is resumable. It reads all of its state from the pull request, so a run
that stops while checks are pending is finished by running it again, from any
session on any machine.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from fnmatch import fnmatchcase
from pathlib import Path

# --------------------------------------------------------------------------
# POLICY. These constants are the judgment calls. Everything below them is
# mechanism. Tune them here; nothing else needs to change.
# --------------------------------------------------------------------------

# Accounts whose open PRs `status` and `sweep` look at (PR_TOOL_OWNERS=a,b
# overrides). PRs you authored elsewhere are always included.
# EDIT THIS: your GitHub login and any organizations you land PRs in.
OWNERS = ["your-github-username", "your-org"]

# A PR that is not READY and has not moved for this long is STALE: a decision
# for a person (close or revive), never something the tool settles.
STALE_DAYS = 14

# With no reviewer bot seen on a PR, wait this long after the last push before
# treating it as "this repo has no automated reviewer".
REVIEW_GRACE_MIN = 15

REVIEWER_BOTS = {"coderabbitai", "greptile-apps",
                 "copilot-pull-request-reviewer", "claude"}

# A PR whose every changed path matches one of these changes nothing the
# product ships, so it lands with no version bump (`Release: none`).
SHIPS_NOTHING = [
    ".github/*", ".greptile/*", ".coderabbit.yaml", ".coderabbit.yml",
    ".snyk", ".gitleaks*", ".gitignore", ".gitattributes", ".editorconfig",
    ".pre-commit-config.yaml", "osv-scanner.toml", ".osv-scanner.toml",
    "tests/*", "test/*", "*/tests/*", "*/test/*", "*/__tests__/*",
    "*.test.*", "*.spec.*", "*_test.py", "test_*.py", "*/test_*.py",
    "Docs/*", "docs/*", "Plans/*", "Notes/*", "Discord/*",
    "README*", "CHANGELOG*", "LICENSE*", "SECURITY*", "CONTRIBUTING*",
    "AGENTS.md", "CLAUDE.md", "GEMINI.md",
]

# Paths that put a PR in the auth / billing / data-migration class. `sweep`
# will not land one unless the PR body records the adversarial review.
SENSITIVE = [
    "*auth*", "*billing*", "*stripe*", "*payment*", "*license*", "*licens*",
    "*/migrations/*", "migrations/*", "*.sql", "*schema.prisma",
]
SENSITIVE_EVIDENCE = re.compile(r"adversarial", re.I)

# Where local clones live (PR_TOOL_CODE_ROOT=a;b prepends). Each is also
# searched one level down in Web/.
# EDIT THIS: the folders that hold your clones. Missing folders are skipped;
# with no local clone the tool makes a throwaway one.
CODE_ROOTS = ["~/code/GitHub", "~/code", "~/src"]

# --------------------------------------------------------------------------
# plumbing
# --------------------------------------------------------------------------


class ToolError(RuntimeError):
    pass


def run(cmd: list[str], cwd: str | Path | None = None, check: bool = True
        ) -> subprocess.CompletedProcess:
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    if check and proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip()
        raise ToolError(f"{' '.join(cmd[:5])}: {detail}")
    return proc


def gh(*args: str, check: bool = True) -> str:
    # cwd is a neutral directory so gh never picks up a repo by accident
    return run(["gh", *args], cwd=tempfile.gettempdir(), check=check).stdout


def git(repo: Path, *args: str, check: bool = True) -> str:
    return run(["git", "-C", str(repo), *args], check=check).stdout


def gql(query: str, **variables: object) -> dict:
    args = ["api", "graphql", "-f", f"query={query}"]
    for key, value in variables.items():
        args += ["-F" if isinstance(value, int) else "-f", f"{key}={value}"]
    data = json.loads(gh(*args))
    if data.get("errors"):
        raise ToolError(f"graphql: {data['errors'][0].get('message')}")
    return data["data"]


def load_version_tool():
    """Import the sibling version-manager tool; it owns every version write."""
    path = Path(os.environ.get("VERSION_TOOL") or
                Path(__file__).resolve().parent.parent
                / "version-manager" / "version_tool.py")
    if not path.exists():
        raise ToolError(f"version tool not found at {path}")
    spec = importlib.util.spec_from_file_location("version_tool", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["version_tool"] = mod   # dataclasses resolve via sys.modules
    spec.loader.exec_module(mod)
    return mod, path


REF_RE = re.compile(
    r"^(?:https?://github\.com/)?(?P<owner>[\w.-]+)/(?P<name>[\w.-]+)"
    r"(?:#|/pull/)(?P<n>\d+)")


def parse_ref(text: str) -> tuple[str, int]:
    m = REF_RE.match(text.strip())
    if not m:
        raise ToolError(f"not a pull request reference: {text!r} "
                        "(want OWNER/NAME#N or a PR URL)")
    return f"{m['owner']}/{m['name']}", int(m["n"])


def _when(text: str | None) -> datetime:
    if not text:
        return datetime.now(timezone.utc)
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


# --------------------------------------------------------------------------
# reading a pull request
# --------------------------------------------------------------------------

PR_QUERY = """
query($owner:String!,$name:String!,$number:Int!){
  repository(owner:$owner,name:$name){
    squashMergeAllowed mergeCommitAllowed rebaseMergeAllowed
    pullRequest(number:$number){
      number title body state isDraft url createdAt updatedAt
      isCrossRepository mergeable mergeStateStatus
      author{login __typename}
      baseRefName headRefName headRefOid
      mergeCommit{oid}
      files(first:100){totalCount nodes{path}}
      commits(last:100){nodes{commit{messageHeadline committedDate}}}
      statusCheckRollup{contexts(first:100){nodes{__typename
        ... on CheckRun{name status conclusion}
        ... on StatusContext{context state}}}}
      reviewThreads(first:100){nodes{id isResolved isOutdated path line
        comments(first:1){nodes{author{login} body url}}}}
      reviews(last:50){nodes{author{login}}}
      comments(last:50){nodes{author{login}}}
    }}}
"""


@dataclass
class PR:
    repo: str
    number: int
    title: str = ""
    body: str = ""
    state: str = "OPEN"            # OPEN | MERGED | CLOSED
    draft: bool = False
    url: str = ""
    author: str = ""
    author_is_bot: bool = False
    cross_repo: bool = False
    base: str = "main"
    head: str = ""
    head_oid: str = ""
    mergeable: str = "MERGEABLE"   # MERGEABLE | CONFLICTING | UNKNOWN
    merge_state: str = "CLEAN"
    created: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    head_committed: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc))
    files: list[str] = field(default_factory=list)
    files_total: int = 0
    subjects: list[str] = field(default_factory=list)
    checks: list[tuple[str, str]] = field(default_factory=list)  # (name, bucket)
    threads: list[dict] = field(default_factory=list)            # unresolved
    reviewer_seen: bool = False
    merge_commit: str | None = None
    methods: list[str] = field(default_factory=lambda: ["squash", "merge"])
    autofix_source_state: str | None = None

    @property
    def ref(self) -> str:
        return f"{self.repo}#{self.number}"


def check_bucket(node: dict) -> tuple[str, str]:
    """(name, pass|fail|pending|skip) for one status-check rollup entry."""
    if node.get("__typename") == "CheckRun":
        name = node.get("name") or "check"
        conclusion = node.get("conclusion")
        # A conclusion is the verdict. GitHub can leave status IN_PROGRESS on
        # a run that already has one (seen for a day on Heimdallr#6 and
        # AppTemplateWPF#3, 2026-11-11), so status only decides when there is
        # no conclusion yet.
        if not conclusion and node.get("status") != "COMPLETED":
            return name, "pending"
        if conclusion == "SUCCESS":
            return name, "pass"
        if conclusion in ("SKIPPED", "NEUTRAL"):
            return name, "skip"
        return name, "fail"
    name = node.get("context") or "status"
    state = node.get("state")
    if state == "SUCCESS":
        return name, "pass"
    if state in ("PENDING", "EXPECTED"):
        return name, "pending"
    return name, "fail"


def pr_from_node(repo: str, repo_node: dict) -> PR:
    n = repo_node["pullRequest"]
    if n is None:
        raise ToolError(f"{repo}: pull request not found")
    author = n.get("author") or {}
    commits = [c["commit"] for c in (n.get("commits") or {}).get("nodes", [])]
    rollup = (n.get("statusCheckRollup") or {}).get("contexts", {}).get("nodes", [])
    threads = []
    for t in (n.get("reviewThreads") or {}).get("nodes", []):
        if t.get("isResolved"):
            continue
        first = (t.get("comments", {}).get("nodes") or [{}])[0]
        threads.append({
            "id": t["id"], "path": t.get("path"), "line": t.get("line"),
            "outdated": bool(t.get("isOutdated")),
            "author": (first.get("author") or {}).get("login", ""),
            "body": (first.get("body") or "").strip(),
            "url": first.get("url", ""),
        })
    voices = [(x.get("author") or {}).get("login", "")
              for key in ("reviews", "comments")
              for x in (n.get(key) or {}).get("nodes", [])]
    methods = [m for m, ok in (("squash", repo_node.get("squashMergeAllowed")),
                               ("merge", repo_node.get("mergeCommitAllowed")),
                               ("rebase", repo_node.get("rebaseMergeAllowed")))
               if ok]
    return PR(
        repo=repo, number=n["number"], title=n.get("title") or "",
        body=n.get("body") or "", state=n.get("state") or "OPEN",
        draft=bool(n.get("isDraft")), url=n.get("url") or "",
        author=author.get("login") or "",
        author_is_bot=author.get("__typename") == "Bot",
        cross_repo=bool(n.get("isCrossRepository")),
        base=n.get("baseRefName") or "main", head=n.get("headRefName") or "",
        head_oid=n.get("headRefOid") or "",
        mergeable=n.get("mergeable") or "UNKNOWN",
        merge_state=n.get("mergeStateStatus") or "UNKNOWN",
        created=_when(n.get("createdAt")), updated=_when(n.get("updatedAt")),
        head_committed=_when(commits[-1]["committedDate"]) if commits
        else _when(n.get("updatedAt")),
        files=[f["path"] for f in (n.get("files") or {}).get("nodes", [])],
        files_total=(n.get("files") or {}).get("totalCount", 0),
        subjects=[c["messageHeadline"] for c in commits],
        checks=[check_bucket(c) for c in rollup],
        threads=threads,
        reviewer_seen=any(v.lower() in REVIEWER_BOTS for v in voices),
        merge_commit=(n.get("mergeCommit") or {}).get("oid"),
        methods=methods or ["merge"],
    )


def fetch_pr(repo: str, number: int) -> PR:
    owner, name = repo.split("/", 1)
    data = gql(PR_QUERY, owner=owner, name=name, number=number)
    pr = pr_from_node(repo, data["repository"])
    if pr.state == "OPEN" and pr.mergeable == "UNKNOWN":
        time.sleep(2)   # GitHub computes mergeability lazily; ask once more
        data = gql(PR_QUERY, owner=owner, name=name, number=number)
        pr = pr_from_node(repo, data["repository"])
    src = autofix_source(pr)
    if pr.state == "OPEN" and src:
        pr.autofix_source_state = gh(
            "pr", "view", str(src), "-R", repo, "--json", "state",
            "--jq", ".state", check=False).strip() or None
    return pr


# --------------------------------------------------------------------------
# classification (pure: no network, no clock of its own)
# --------------------------------------------------------------------------

AUTOFIX_HEAD = re.compile(r"^autofix/pr-(\d+)$")


def autofix_source(pr: PR) -> int | None:
    m = AUTOFIX_HEAD.match(pr.head)
    return int(m.group(1)) if m else None


def is_autofix(pr: PR) -> bool:
    return autofix_source(pr) is not None or pr.title.startswith("[autofix]")


def _matches(path: str, patterns: list[str]) -> bool:
    return any(fnmatchcase(path, p) for p in patterns)


def ships_nothing(pr: PR) -> bool:
    """True only when every changed path is provably outside the product."""
    if not pr.files or pr.files_total > len(pr.files):
        return False
    return all(_matches(p, SHIPS_NOTHING) for p in pr.files)


def is_sensitive(pr: PR) -> bool:
    return any(_matches(p.lower(), SENSITIVE) for p in pr.files
               if not _matches(p, SHIPS_NOTHING))


@dataclass
class Verdict:
    state: str
    reasons: list[str] = field(default_factory=list)
    stale: bool = False

    @property
    def label(self) -> str:
        return f"STALE({self.state})" if self.stale else self.state


NEXT_STEP = {
    "READY": "land it",
    "WAITING": "nothing yet; checks or review are still running",
    "THREADS": "fix or answer each thread, resolve it, then land",
    "FAILING": "fix the failing check, push, then land",
    "CONFLICT": "merge the base branch in, resolve, push, then land",
    "BLOCKED": "a branch rule blocks the merge; read `gh pr merge` output",
    "REVIEW": "run the adversarial review, record it in the PR body, land",
    "SUPERSEDED": "close it (sweep --apply does)",
    "AUTOFIX": "fold the fix into its source PR, or close it",
    "DRAFT": "finish it or close it",
    "EXTERNAL": "outside contributor: the repo owner decides",
    "ELSEWHERE": "your PR in someone else's repo: its owner merges",
}
STALE_STEP = "no movement: the repo owner decides, close or revive"


def classify(pr: PR, now: datetime, trusted: set[str],
             owners: list[str] | None = None) -> Verdict:
    if pr.state != "OPEN":
        return Verdict(pr.state)
    idle_days = (now - pr.updated).days

    def verdict(state: str, *reasons: str) -> Verdict:
        # A READY PR nobody has touched for weeks was parked on purpose or
        # forgotten; either way a person decides. `land` still takes it when
        # asked by name; `sweep` does not.
        stale = state not in ("WAITING", "SUPERSEDED", "EXTERNAL", "ELSEWHERE") \
            and idle_days >= STALE_DAYS
        return Verdict(state, list(reasons), stale)

    if not pr.author_is_bot and pr.author.lower() not in trusted:
        return verdict("EXTERNAL", f"author {pr.author or 'unknown'}")
    # No explicit list means "whatever this run is configured for", so the
    # PR_TOOL_OWNERS override reaches every caller, not just the survey query.
    home = {o.lower() for o in (owners if owners is not None else _owners(None))}
    if pr.repo.split("/", 1)[0].lower() not in home:
        return verdict("ELSEWHERE", "someone else's repository")
    if is_autofix(pr):
        src = autofix_source(pr)
        if pr.autofix_source_state in ("MERGED", "CLOSED"):
            return verdict("SUPERSEDED",
                           f"source #{src} is {pr.autofix_source_state.lower()}")
        return verdict("AUTOFIX", f"source #{src} still open" if src
                       else "autofix PR with no source in its branch name")
    if pr.draft:
        return verdict("DRAFT")
    if pr.mergeable == "CONFLICTING":
        return verdict("CONFLICT", f"conflicts with {pr.base}")
    failing = [n for n, b in pr.checks if b == "fail"]
    if failing:
        return verdict("FAILING", *failing)
    pending = [n for n, b in pr.checks if b == "pending"]
    if pending:
        return verdict("WAITING", *(f"{n} running" for n in pending))
    if pr.threads:
        return verdict("THREADS", f"{len(pr.threads)} unresolved review "
                       f"thread{'s' if len(pr.threads) != 1 else ''}")
    if pr.mergeable == "UNKNOWN":
        return verdict("WAITING", "GitHub is still computing mergeability")
    if pr.merge_state == "BLOCKED":
        return verdict("BLOCKED", "mergeStateStatus BLOCKED")
    if is_sensitive(pr) and not SENSITIVE_EVIDENCE.search(pr.body):
        return verdict("REVIEW", "auth/billing/migration paths and no "
                       "adversarial review recorded in the PR body")
    since_push = (now - pr.head_committed).total_seconds() / 60
    if not pr.reviewer_seen and not pr.author_is_bot \
            and since_push < REVIEW_GRACE_MIN:
        return verdict("WAITING", "automated review has not arrived yet")
    return verdict("READY")


# --------------------------------------------------------------------------
# release plan: what the PR says about its own version bump
# --------------------------------------------------------------------------

RELEASE_LINE = re.compile(
    r"^[ \t>*-]*\**Release\**[ \t]*:[ \t]*\**[ \t]*`?"
    r"(major|minor|patch|none)\b", re.I | re.M)
NOTES_HEADING = re.compile(r"^(#{2,4})[ \t]*Release notes[ \t]*$", re.I | re.M)
# the section also ends at a heading of its own level or higher (built per PR,
# so `### Added` inside `## Release notes` stays part of the notes)
NOTES_END = r"<!--|---[ \t]*$|\U0001F916"
BREAKING = re.compile(r"^\w+(\([^)]*\))?!:|BREAKING[ -]CHANGE", re.M)
FEAT = re.compile(r"^feat(\(|!|:)")


@dataclass
class ReleasePlan:
    level: str           # major | minor | patch | none
    notes: str | None    # curated changelog body, when the PR supplies one
    source: str          # where the level came from, for the printed plan


def release_notes(body: str) -> str | None:
    m = NOTES_HEADING.search(body)
    if not m:
        return None
    rest = body[m.end():].replace("\r\n", "\n")
    depth = len(m.group(1))
    end = re.search(rf"^(?:#{{1,{depth}}}[ \t]|{NOTES_END})", rest, re.M)
    text = rest[:end.start()] if end else rest
    lines = [ln.rstrip() for ln in text.split("\n")
             if not RELEASE_LINE.match(ln)]
    return "\n".join(lines).strip() or None


def release_plan(pr: PR, override: str | None = None,
                 no_bump: bool = False) -> ReleasePlan:
    notes = release_notes(pr.body)
    if no_bump:
        return ReleasePlan("none", None, "--no-bump")
    if override:
        return ReleasePlan(override, notes, "--level")
    m = RELEASE_LINE.search(pr.body)
    if m:
        return ReleasePlan(m.group(1).lower(), notes, "PR body `Release:` line")
    if pr.author_is_bot:
        return ReleasePlan("none", None, "bot PR: lands without a bump")
    if ships_nothing(pr):
        return ReleasePlan("none", None, "every changed path ships nothing")
    blob = "\n".join(pr.subjects)
    if BREAKING.search(blob):
        return ReleasePlan("major", notes, "commit subjects (breaking)")
    if any(FEAT.match(s) for s in pr.subjects):
        return ReleasePlan("minor", notes, "commit subjects (feat)")
    return ReleasePlan("patch", notes, "commit subjects")


TITLE_VERSION = re.compile(r"\s*\(v?\d+\.\d+\.\d+\)|\s+[\u2014-]\s+v\d+\.\d+\.\d+\s*$")


def squash_subject(title: str, number: int, version: str | None) -> str:
    """`title (vX.Y.Z) (#N)`: the version comes from the landing, not the title."""
    clean = TITLE_VERSION.sub("", title).strip()
    return f"{clean} (v{version}) (#{number})" if version else f"{clean} (#{number})"


# --------------------------------------------------------------------------
# git mechanics for the bump (operate on a working tree; no network but push)
# --------------------------------------------------------------------------

ANY_H2 = re.compile(r"^##\s", re.M)


def strip_sections(text: str, known: set[str], heading_re: re.Pattern[str]
                   ) -> tuple[str, list[str]]:
    """Remove changelog sections whose version is not in `known`.

    Returns the new text and the bodies removed, oldest heading last, so a
    hand-written section survives as the notes for the re-cut release.
    """
    out, removed = text, []
    for m in reversed(list(heading_re.finditer(text))):
        if m.group("v") in known:
            continue
        nxt = ANY_H2.search(text, m.end())
        end = nxt.start() if nxt else len(text)
        tail = text[m.end():end]
        body = tail.split("\n", 1)[1] if "\n" in tail else ""
        if body.strip():
            removed.insert(0, body.strip())
        out = out[:m.start()] + out[end:]
    return out, removed


def _show(wt: Path, rev: str, rel: Path) -> str | None:
    proc = run(["git", "-C", str(wt), "show", f"{rev}:{rel.as_posix()}"],
               check=False)
    return proc.stdout if proc.returncode == 0 else None


def version_at(vt, wt: Path, rev: str, loc) -> str | None:
    text = _show(wt, rev, loc.path)
    return vt._extract(text, loc.kind) if text else None


def remote_tag_exists(repo: str, tag: str) -> bool:
    proc = run(["gh", "api", f"repos/{repo}/git/ref/tags/{tag}"],
               cwd=tempfile.gettempdir(), check=False)
    return proc.returncode == 0


def bump_state(vt, wt: Path, base_ref: str, tag_taken) -> tuple[str, str | None]:
    """How the branch stands against the base: (state, branch version).

    noversion  the repo has no version location: land without a bump
    absent     the branch carries no bump: cut one
    current    the branch's bump is still the next version: merge as it is
    stale      the base moved past it, or its tag is taken: drop and re-cut
    """
    canonical, _, _ = vt.detect(wt)
    if canonical is None or vt.parse_version(canonical.value or "") is None:
        return "noversion", None
    head_v = canonical.value
    mb = git(wt, "merge-base", "HEAD", base_ref).strip()
    mb_v = version_at(vt, wt, mb, canonical)
    if mb_v is None or head_v == mb_v:
        return "absent", head_v
    base_v = version_at(vt, wt, base_ref, canonical) or "0.0.0"
    if vt.parse_version(head_v) > (vt.parse_version(base_v) or (0, 0, 0)) \
            and not tag_taken(f"v{head_v}"):
        return "current", head_v
    return "stale", head_v


def drop_stale_bump(vt, wt: Path, base_ref: str) -> str | None:
    """Undo a bump cut before landing, surgically, and return its notes.

    Version fields go back to their merge-base values and the changelog
    sections the branch added come out. Nothing else in those files moves,
    so dependency edits sharing package.json with the version are untouched.
    """
    canonical, mirrors, _ = vt.detect(wt)
    if canonical is None:
        return None
    mb = git(wt, "merge-base", "HEAD", base_ref).strip()
    mb_v = version_at(vt, wt, mb, canonical)
    if mb_v is None or mb_v == canonical.value:
        return None
    for loc in [canonical, *mirrors]:
        old = version_at(vt, wt, mb, loc)
        if old and old != loc.value:
            vt.write_version(wt, loc, old)
    removed: list[str] = []
    rel = vt.changelog_path(wt)
    mb_changelog = _show(wt, mb, rel)
    if mb_changelog is not None and (wt / rel).exists():
        known = {m.group("v") for m in vt.CHANGELOG_HEADING.finditer(mb_changelog)}
        with open(wt / rel, encoding="utf-8", newline="") as fh:
            text = fh.read()
        updated, removed = strip_sections(text, known, vt.CHANGELOG_HEADING)
        if updated != text:
            with open(wt / rel, "w", encoding="utf-8", newline="") as fh:
                fh.write(updated)
    git(wt, "add", "-A")
    if run(["git", "-C", str(wt), "diff", "--cached", "--quiet"],
           check=False).returncode != 0:
        git(wt, "commit", "-m",
            "chore(release): drop pre-landing bump (re-cut at landing)")
    return "\n\n".join(removed).strip() or None


def prepare_branch(vt, vt_path: Path, wt: Path, base_ref: str, level: str,
                   notes: str | None, tag_taken, scratch: Path) -> str:
    """Bring the branch to 'base + one fresh bump commit'. Returns the version."""
    carried = drop_stale_bump(vt, wt, base_ref)
    if int(git(wt, "rev-list", "--count", f"HEAD..{base_ref}").strip() or 0):
        merge = run(["git", "-C", str(wt), "merge", "--no-edit", base_ref],
                    check=False)
        if merge.returncode != 0:
            conflicted = git(wt, "diff", "--name-only", "--diff-filter=U",
                             check=False).split()
            run(["git", "-C", str(wt), "merge", "--abort"], check=False)
            raise ToolError("merging the base branch conflicts in: "
                            + (", ".join(conflicted) or "unknown paths"))
    canonical, _, _ = vt.detect(wt)
    current = vt.parse_version((canonical.value if canonical else "") or "")
    if current is None:
        raise ToolError("no parseable version after merging the base branch")
    target = vt.fmt_version(vt.bump(current, level))
    tag = f"v{target}"
    if tag_taken(tag):
        raise ToolError(f"tag {tag} already exists on the remote but the base "
                        f"branch is still at {canonical.value}; run "
                        "version_tool.py check on the base branch")
    if tag in git(wt, "tag", "--list", tag).split():
        # a local-only draft from an earlier cut: move it aside, never delete
        sha = git(wt, "rev-parse", "--short", f"{tag}^{{commit}}").strip()
        git(wt, "tag", f"{tag}-draft-{sha}", f"{tag}^{{commit}}", check=False)
        git(wt, "tag", "-d", tag)
    cmd = [sys.executable, str(vt_path), "--repo", str(wt),
           "release", level, "--apply", "--no-tag"]
    body = notes or carried
    if body:
        notes_file = scratch / "release-notes.md"
        notes_file.write_text(body.rstrip() + "\n", encoding="utf-8")
        cmd += ["--notes", str(notes_file)]
    out = run(cmd, check=False)
    if out.returncode != 0:
        raise ToolError("version tool refused the release:\n"
                        + (out.stdout + out.stderr).strip())
    canonical, _, _ = vt.detect(wt)
    if canonical is None or canonical.value != target:
        raise ToolError(f"expected version {target} after the release, found "
                        f"{canonical.value if canonical else 'none'}")
    return target


# --------------------------------------------------------------------------
# workspace: a detached worktree off a local clone, or a throwaway clone
# --------------------------------------------------------------------------

def find_clone(repo: str, hint: str | None = None) -> Path | None:
    name = repo.split("/", 1)[1]
    roots = [r for r in os.environ.get("PR_TOOL_CODE_ROOT", "").split(os.pathsep)
             if r] + CODE_ROOTS
    candidates = [Path(hint)] if hint else []
    for root in roots:
        base = Path(root).expanduser()
        candidates += [base / name, base / "Web" / name]
    want = repo.lower()
    for cand in candidates:
        if not (cand / ".git").exists():
            continue
        url = run(["git", "-C", str(cand), "remote", "get-url", "origin"],
                  check=False).stdout.strip().lower()
        url = url[:-4] if url.endswith(".git") else url
        if url.endswith("/" + want) or url.endswith(":" + want):
            return cand
    if hint:
        raise ToolError(f"--clone {hint} is not a clone of {repo}")
    return None


class Workspace:
    def __init__(self, pr: PR, hint: str | None = None):
        self.clone = find_clone(pr.repo, hint)
        self.tmp = Path(tempfile.mkdtemp(prefix="land-pr-"))
        self.wt = self.tmp / "wt"
        try:
            if self.clone is None:
                self.clone = self.tmp / "clone"
                gh("repo", "clone", pr.repo, str(self.clone))
            git(self.clone, "fetch", "origin",
                f"+refs/heads/{pr.head}:refs/remotes/origin/{pr.head}",
                f"+refs/heads/{pr.base}:refs/remotes/origin/{pr.base}")
            git(self.clone, "worktree", "add", "--detach", str(self.wt),
                f"origin/{pr.head}")
            if git(self.wt, "rev-parse", "HEAD").strip() != pr.head_oid:
                raise ToolError("the branch moved while landing started; "
                                "run again")
        except ToolError:
            self.close()
            raise

    def close(self) -> None:
        run(["git", "-C", str(self.clone), "worktree", "remove", "--force",
             str(self.wt)], check=False)
        shutil.rmtree(self.tmp, ignore_errors=True)
        run(["git", "-C", str(self.clone), "worktree", "prune"], check=False)


class Lock:
    """One landing per repo per machine; the remote check covers the rest."""

    def __init__(self, repo: str):
        root = Path.home() / ".claude" / "state" / "land-pr"
        root.mkdir(parents=True, exist_ok=True)
        self.path = root / (repo.replace("/", "__") + ".lock")

    def __enter__(self) -> "Lock":
        for _ in range(2):
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, f"{os.getpid()} {datetime.now(timezone.utc)}".encode())
                os.close(fd)
                return self
            except FileExistsError:
                if time.time() - self.path.stat().st_mtime > 45 * 60:
                    self.path.unlink(missing_ok=True)   # abandoned
                    continue
                raise ToolError(f"another landing holds {self.path}; "
                                "wait for it or delete the file if it died")
        raise ToolError(f"could not take {self.path}")

    def __exit__(self, *_: object) -> None:
        self.path.unlink(missing_ok=True)


# --------------------------------------------------------------------------
# GitHub actions
# --------------------------------------------------------------------------

def trusted_authors() -> set[str]:
    me = gh("api", "user", "--jq", ".login", check=False).strip().lower()
    return {me} if me else set()


def detect_method(pr: PR) -> str:
    """The repo's merge style, read from how its last merges actually landed."""
    out = gh("api", f"repos/{pr.repo}/commits?sha={pr.base}&per_page=20",
             "--jq", '.[] | "\\(.parents|length)\\t\\(.commit.message|split("\\n")[0])"',
             check=False)
    squash = merge = 0
    for line in out.splitlines():
        parents, _, subject = line.partition("\t")
        if parents == "2" and subject.startswith("Merge pull request"):
            merge += 1
        elif parents == "1" and re.search(r"\(#\d+\)$", subject):
            squash += 1
    want = "merge" if merge > squash else "squash"
    return want if want in pr.methods else pr.methods[0]


def create_tag(repo: str, version: str, oid: str) -> str:
    tag = f"v{version}"
    if remote_tag_exists(repo, tag):
        return f"tag {tag} already on the remote"
    sha = gh("api", f"repos/{repo}/git/tags", "-f", f"tag={tag}",
             "-f", f"message=Version {version}", "-f", f"object={oid}",
             "-f", "type=commit", "--jq", ".sha").strip()
    gh("api", f"repos/{repo}/git/refs", "-f", f"ref=refs/tags/{tag}",
       "-f", f"sha={sha}")
    return f"tagged {tag} at {oid[:9]}"


def close_superseded(repo: str, number: int, why: str) -> None:
    gh("pr", "close", str(number), "-R", repo, "--delete-branch",
       "--comment", why)


def wait_ready(repo: str, number: int, oid: str, minutes: float,
               trusted: set[str], had_checks: bool,
               owners: list[str] | None = None) -> tuple[bool, PR]:
    """Poll until the PR is READY at `oid` twice running, or time runs out."""
    deadline = time.time() + minutes * 60
    streak = 0
    time.sleep(min(20, max(0, minutes * 60)))   # let the push register
    while True:
        pr = fetch_pr(repo, number)
        if pr.state != "OPEN":
            raise ToolError(f"{pr.ref} is {pr.state.lower()} now")
        if pr.head_oid != oid:
            raise ToolError("someone else pushed to the branch; run again")
        v = classify(pr, datetime.now(timezone.utc), trusted, owners)
        settled = v.state == "READY" and (pr.checks or not had_checks)
        if v.state not in ("READY", "WAITING"):
            raise ToolError(f"{pr.ref} is {v.label}: {'; '.join(v.reasons)}")
        streak = streak + 1 if settled else 0
        if streak >= 2:
            return True, pr
        if time.time() >= deadline:
            return False, pr
        time.sleep(20)


# --------------------------------------------------------------------------
# verbs
# --------------------------------------------------------------------------

def print_threads(pr: PR) -> None:
    for t in pr.threads:
        where = f"{t['path']}:{t['line']}" if t.get("line") else (t.get("path") or "")
        mark = " (outdated)" if t["outdated"] else ""
        text = re.sub(r"<!--.*?-->|<[^>]+>", " ", t["body"], flags=re.S)
        first = " ".join(text.split())[:160]
        print(f"    {t['id']}  {where}{mark}  @{t['author']}")
        print(f"      {first}")
        if t["url"]:
            print(f"      {t['url']}")


def cmd_land(ref: str, apply: bool = False, level: str | None = None,
             no_bump: bool = False, method: str | None = None,
             clone: str | None = None, wait: float = 8.0,
             trusted: set[str] | None = None,
             owners: list[str] | None = None, **_: object) -> int:
    repo, number = parse_ref(ref)
    trusted = trusted if trusted is not None else trusted_authors()
    pr = fetch_pr(repo, number)
    print(f"{pr.ref}  {pr.title}")
    if pr.state != "OPEN":
        print(f"  already {pr.state.lower()}; nothing to land")
        return 0

    v = classify(pr, datetime.now(timezone.utc), trusted, owners)
    if v.state == "WAITING" and apply and wait > 0:
        print(f"  waiting up to {wait:g} min: {'; '.join(v.reasons)}")
        ok, pr = wait_ready(repo, number, pr.head_oid, wait, trusted,
                            bool(pr.checks), owners)
        if not ok:
            print("  WAITING: still running. Run the same command again.")
            return 3
        v = classify(pr, datetime.now(timezone.utc), trusted, owners)
    if v.state != "READY":
        print(f"  {v.label}: {'; '.join(v.reasons) or 'not ready'}")
        print(f"  next: {STALE_STEP if v.stale else NEXT_STEP.get(v.state, '')}")
        if v.state == "THREADS":
            print_threads(pr)
        return 3 if v.state == "WAITING" else 1

    plan = release_plan(pr, level, no_bump)
    if pr.cross_repo and plan.level != "none":
        plan = ReleasePlan("none", None, "fork PR: its branch cannot take a bump")
    method = method or detect_method(pr)
    print(f"  release: {plan.level}  ({plan.source})")
    if plan.level != "none":
        print("  notes:   " + ("from the PR body" if plan.notes
                               else "none in the PR body; drafted from commits"))
    print(f"  merge:   {method}, delete branch, tag after merge")
    if not apply:
        print("  (dry run: pass --apply to land)")
        return 0

    version: str | None = None
    with Lock(repo):
        if plan.level != "none":
            vt, vt_path = load_version_tool()
            ws = Workspace(pr, clone)
            try:
                base_ref = f"origin/{pr.base}"
                taken = lambda tag: remote_tag_exists(repo, tag)  # noqa: E731
                state, head_v = bump_state(vt, ws.wt, base_ref, taken)
                if state == "noversion":
                    print("  NOTE: no version location in this repo; landing "
                          "without a bump. Run version_tool.py backfill here.")
                elif state == "current":
                    version = head_v
                    print(f"  bump v{version} on the branch is current")
                else:
                    if state == "stale":
                        print(f"  bump v{head_v} on the branch is stale; re-cutting")
                    version = prepare_branch(vt, vt_path, ws.wt, base_ref,
                                             plan.level, plan.notes, taken,
                                             ws.tmp)
                    git(ws.wt, "push", "origin", f"HEAD:refs/heads/{pr.head}")
                    oid = git(ws.wt, "rev-parse", "HEAD").strip()
                    print(f"  pushed bump v{version} ({oid[:9]}); waiting on checks")
                    ok, pr = wait_ready(repo, number, oid, wait, trusted,
                                        bool(pr.checks))
                    if not ok:
                        print("  WAITING: checks on the bump commit are still "
                              "running. Run the same command again.")
                        return 3
            finally:
                ws.close()

        args = ["pr", "merge", str(number), "-R", repo, f"--{method}",
                "--delete-branch", "--match-head-commit", pr.head_oid]
        if method == "squash":
            args += ["--subject", squash_subject(pr.title, number, version)]
        gh(*args)
        merged = fetch_pr(repo, number)
        print(f"  merged ({method}) as {(merged.merge_commit or '?')[:9]}")
        if version and merged.merge_commit:
            try:
                print("  " + create_tag(repo, version, merged.merge_commit))
            except ToolError as exc:
                print(f"  WARNING: merged, but tagging v{version} failed: {exc}")

    leftovers = gh("pr", "list", "-R", repo, "--state", "open", "--head",
                   f"autofix/pr-{number}", "--json", "number",
                   "--jq", ".[].number", check=False).split()
    for n in leftovers:
        close_superseded(repo, int(n), f"Closing: source PR #{number} merged, "
                         "so this autofix draft is superseded.")
        print(f"  closed superseded autofix #{n}")
    print(f"  LANDED {pr.ref}" + (f" as v{version}" if version else ""))
    return 0


def collect(owners: list[str], repo: str | None) -> list[tuple[str, int]]:
    refs: set[tuple[str, int]] = set()
    queries = [["--owner", o] for o in owners] + [["--author", "@me"]]
    if repo:
        queries = [["--repo", repo]]
    for q in queries:
        out = gh("search", "prs", "--state", "open", "--archived=false",
                 "--limit", "300", *q, "--json", "repository,number",
                 "--jq", '.[] | "\\(.repository.nameWithOwner)\\t\\(.number)"')
        for line in out.splitlines():
            name, _, num = line.partition("\t")
            if name and num:
                refs.add((name, int(num)))
    return sorted(refs)


ORDER = ["READY", "SUPERSEDED", "THREADS", "FAILING", "CONFLICT", "REVIEW",
         "BLOCKED", "WAITING", "AUTOFIX", "DRAFT", "EXTERNAL", "ELSEWHERE"]


def survey(owners: list[str], repo: str | None, trusted: set[str]
           ) -> list[tuple[PR, Verdict]]:
    refs = collect(owners, repo)
    with ThreadPoolExecutor(max_workers=6) as pool:
        prs = list(pool.map(lambda r: fetch_pr(*r), refs))
    now = datetime.now(timezone.utc)
    rows = [(pr, classify(pr, now, trusted, owners)) for pr in prs]
    rows.sort(key=lambda row: (row[1].stale, ORDER.index(row[1].state)
                               if row[1].state in ORDER else 99,
                               row[0].repo.lower(), row[0].number))
    return rows


def print_survey(rows: list[tuple[PR, Verdict]]) -> None:
    now = datetime.now(timezone.utc)
    last = None
    for pr, v in rows:
        if v.label != last:
            step = STALE_STEP if v.stale else NEXT_STEP.get(v.state, "")
            print(f"\n{v.label}  ({step})")
            last = v.label
        idle = (now - pr.updated).days
        why = f"  [{'; '.join(v.reasons)}]" if v.reasons else ""
        print(f"  {pr.ref:<46} {idle:>3}d  {pr.title[:60]}{why}")
    counts: dict[str, int] = {}
    for _, v in rows:
        counts[v.label] = counts.get(v.label, 0) + 1
    print(f"\n{len(rows)} open: "
          + ", ".join(f"{k} {n}" for k, n in sorted(counts.items())))


def _owners(args_owner: list[str] | None) -> list[str]:
    env = [o for o in os.environ.get("PR_TOOL_OWNERS", "").split(",") if o]
    return args_owner or env or OWNERS


def cmd_status(owner: list[str] | None = None, repo: str | None = None,
               as_json: bool = False, **_: object) -> int:
    trusted = trusted_authors()
    rows = survey(_owners(owner), repo, trusted)
    if as_json:
        print(json.dumps([{"ref": pr.ref, "state": v.state, "stale": v.stale,
                           "reasons": v.reasons, "title": pr.title,
                           "url": pr.url, "author": pr.author,
                           "updated": pr.updated.isoformat()}
                          for pr, v in rows], indent=2))
    else:
        print_survey(rows)
    actionable = any(v.state == "SUPERSEDED" or (v.state == "READY" and not v.stale)
                     for _, v in rows)
    return 10 if actionable else 0


def cmd_sweep(owner: list[str] | None = None, repo: str | None = None,
              apply: bool = False, limit: int = 25, wait: float = 8.0,
              **_: object) -> int:
    trusted = trusted_authors()
    owners = _owners(owner)
    rows = survey(owners, repo, trusted)
    print_survey(rows)
    ready = [pr for pr, v in rows if v.state == "READY" and not v.stale]
    dead = [pr for pr, v in rows if v.state == "SUPERSEDED"]
    if not apply:
        print(f"\nsweep would close {len(dead)} superseded and land "
              f"{min(len(ready), limit)} ready (dry run: pass --apply)")
        return 10 if (ready or dead) else 0

    failures = waiting = 0
    for pr in dead:
        src = autofix_source(pr)
        try:
            close_superseded(pr.repo, pr.number, f"Closing: source PR #{src} is "
                             f"{(pr.autofix_source_state or 'done').lower()}, "
                             "so this autofix draft is superseded.")
            print(f"closed superseded {pr.ref}")
        except ToolError as exc:
            failures += 1
            print(f"FAILED to close {pr.ref}: {exc}")
    for pr in ready[:limit]:
        print()
        try:
            code = cmd_land(pr.ref, apply=True, wait=wait, trusted=trusted,
                            owners=owners)
        except ToolError as exc:
            code = 1
            print(f"  FAILED: {exc}")
        failures += code == 1
        waiting += code == 3
    print(f"\nsweep done: {failures} failed, {waiting} still waiting on checks")
    return 1 if failures else (3 if waiting else 0)


RESOLVE = ("mutation($id:ID!){resolveReviewThread(input:{threadId:$id})"
           "{thread{isResolved}}}")


def cmd_threads(ref: str, resolve: list[str] | None = None, **_: object) -> int:
    repo, number = parse_ref(ref)
    for thread_id in resolve or []:
        gql(RESOLVE, id=thread_id)
        print(f"resolved {thread_id}")
    pr = fetch_pr(repo, number)
    print(f"{pr.ref}: {len(pr.threads)} unresolved thread(s)")
    print_threads(pr)
    return 0


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(prog="pr_tool.py", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="verb", required=True)

    def scope(p: argparse.ArgumentParser) -> None:
        p.add_argument("--owner", action="append", help="account to survey (repeatable)")
        p.add_argument("--repo", help="limit to one OWNER/NAME")

    s = sub.add_parser("status", help="classify every open PR; never writes")
    scope(s)
    s.add_argument("--json", dest="as_json", action="store_true")

    la = sub.add_parser("land", help="bump, wait for checks, merge, tag")
    la.add_argument("ref", help="OWNER/NAME#N or a PR URL")
    la.add_argument("--apply", action="store_true")
    la.add_argument("--level", choices=["major", "minor", "patch"])
    la.add_argument("--no-bump", action="store_true")
    la.add_argument("--method", choices=["squash", "merge", "rebase"])
    la.add_argument("--clone", help="local clone to work from")
    la.add_argument("--wait", type=float, default=8.0,
                    help="minutes to wait on checks before exiting 3 (default 8)")

    sw = sub.add_parser("sweep", help="close superseded, land everything READY")
    scope(sw)
    sw.add_argument("--apply", action="store_true")
    sw.add_argument("--max", dest="limit", type=int, default=25)
    sw.add_argument("--wait", type=float, default=8.0)

    th = sub.add_parser("threads", help="list (and resolve) review threads")
    th.add_argument("ref")
    th.add_argument("--resolve", nargs="+", metavar="ID")

    args = ap.parse_args(argv)
    verbs = {"status": cmd_status, "land": cmd_land, "sweep": cmd_sweep,
             "threads": cmd_threads}
    try:
        return verbs[args.verb](**{k: v for k, v in vars(args).items()
                                   if k != "verb"})
    except ToolError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

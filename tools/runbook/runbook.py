"""Agent CLI for the central runbook: add items waiting on a human, verify, reopen.

Exit codes: 0 ok, 1 error, 2 refused (secret/placeholder/bad input/unknown id),
3 written to the repo inbox because the state file was not writable.
"""
from __future__ import annotations

import argparse
import errno
import json
import os
import subprocess
import sys
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

import rblib

OK, ERROR, REFUSED, INBOXED = 0, 1, 2, 3
PRIORITIES = ("urgent", "normal", "later")

# Keys a re-add may refresh on an existing item, and only when the caller passed
# them; `tags` is unioned. Everything else (id, state, output, chosen, other, added,
# added_by, agent_note, verified) belongs to the item, to the owner, or to the processor.
_AGENT_FIELDS = (
    "why", "kind", "steps", "verify", "rollback", "source", "due", "after",
    "priority", "tags",
)
# The answer to a decision lives only at item top level (`chosen`, `other`).
_DECISION_OWNER_KEYS = ("chosen", "other")
# Errors that mean "the state file is not writable here"; only these fall back to
# the repo inbox. Anything else (missing directory, disk full) is a plain error.
_NOT_WRITABLE = (errno.EACCES, errno.EROFS, errno.EPERM)


class Refused(Exception):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _agent() -> str:
    return os.environ.get("RUNBOOK_AGENT") or "unknown"


# ---------------------------------------------------------------- items

def _new_item(**kw) -> dict:
    item = {
        "id": None,
        "repo": "",
        "title": "",
        "why": "",
        "kind": "steps",
        "steps": [],
        "verify": "",
        "rollback": "",
        "source": "",
        "added_by": _agent(),
        "added": _now().isoformat(timespec="seconds"),
        "due": None,
        "after": [],
        "priority": "normal",
        "decision": None,
        "tags": [],
        "state": "open",
        "output": "",
        "chosen": None,
        "other": "",
        "agent_note": "",
        "verified": None,
    }
    item.update(kw)
    return item


def _clean_decision(dec):
    if not isinstance(dec, dict):
        return dec
    return {k: v for k, v in dec.items() if k not in _DECISION_OWNER_KEYS}


def _upsert(state: dict, passed: dict) -> tuple[str, bool]:
    """Add an item, or refresh the duplicate (same repo+title). Returns (id, is_new).

    `passed` holds only what the caller supplied. A new item gets the defaults for
    the rest; an existing one keeps every key the caller did not pass, and its tags
    are unioned, so a re-add never wipes a diagnosis, a tag, a priority or a date.
    """
    passed = dict(passed)
    if "decision" in passed:
        passed["decision"] = _clean_decision(passed["decision"])
    for existing in state["items"]:
        if existing.get("repo") == passed.get("repo") and existing.get("title") == passed.get("title"):
            for k in _AGENT_FIELDS:
                if k not in passed:
                    continue
                if k == "tags":
                    tags = list(existing.get("tags") or [])
                    tags += [t for t in passed["tags"] if t not in tags]
                    existing["tags"] = tags
                else:
                    existing[k] = passed[k]
            if passed.get("decision"):
                existing["decision"] = passed["decision"]
            return existing["id"], False
    item = _new_item(**{k: v for k, v in passed.items() if k != "id"})
    item["id"] = rblib.next_item_id(state)
    state["items"].append(item)
    return item["id"], True


def merge_inbox(state: dict, item: dict) -> str | None:
    """Merge an inbox item into state (caller holds the lock and saves).

    Returns the new id, or None when it duplicated an open item and only updated it.
    """
    item_id, is_new = _upsert(state, item)
    return item_id if is_new else None


def write_inbox(item: dict, repo_root: Path) -> Path:
    inbox = Path(repo_root) / ".runbook" / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    path = inbox / f"{uuid.uuid4()}.json"
    path.write_text(json.dumps(item, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def _repo_root(cwd: Path) -> Path | None:
    try:
        r = subprocess.run(
            ["git", "-C", str(cwd), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    out = r.stdout.strip()
    return Path(out) if r.returncode == 0 and out else None


# ---------------------------------------------------------------- checks

def _check_text(texts: list[str]) -> None:
    secrets: list[str] = []
    placeholders: list[str] = []
    for t in texts:
        for k in rblib.find_secrets(t):
            if k not in secrets:
                secrets.append(k)
        for p in rblib.find_placeholders(t):
            if p not in placeholders:
                placeholders.append(p)
    msgs = []
    if secrets:
        msgs.append("looks like a secret (" + ", ".join(secrets) + ")")
    if placeholders:
        msgs.append("unfilled placeholder(s): " + ", ".join(placeholders))
    if msgs:
        raise Refused("refused: " + "; ".join(msgs))


def _parse_step(raw: str) -> dict:
    """shell = before the first '|', expect = after the last '|', cmd = between (may hold '|')."""
    if raw.count("|") < 2:
        raise Refused(f'--step must look like "shell|cmd|expect" (trailing |expect required), got: {raw!r}')
    shell, rest = raw.split("|", 1)
    cmd, expect = rest.rsplit("|", 1)
    if not shell.strip() or not cmd.strip():
        raise Refused(f'--step needs a shell and a cmd, got: {raw!r}')
    return {"shell": shell.strip(), "cmd": cmd, "expect": expect, "prompts": ""}


def _parse_option(raw: str) -> dict:
    label, _, detail = raw.partition("|")
    detail = detail.strip()
    recommended = detail.endswith("*")
    if recommended:
        detail = detail[:-1].rstrip()
    if not label.strip():
        raise Refused(f'--option must look like "label|detail", got: {raw!r}')
    return {"label": label.strip(), "detail": detail, "recommended": recommended}


def is_iso_date(s) -> bool:
    if not isinstance(s, str) or len(s) != 10:
        return False
    try:
        date.fromisoformat(s)
    except ValueError:
        return False
    return True


def _common(args, item: dict) -> dict:
    """Add the optional fields, but only the ones the caller actually passed."""
    if args.due is not None:
        if not is_iso_date(args.due):
            raise Refused(f"--due must be YYYY-MM-DD, got: {args.due!r}")
        item["due"] = args.due
    if args.priority is not None:
        if args.priority not in PRIORITIES:
            raise Refused(f"--priority must be one of {', '.join(PRIORITIES)}")
        item["priority"] = args.priority
    if args.after:
        item["after"] = list(args.after)
    if args.tag:
        item["tags"] = list(args.tag)
    if args.source is not None:
        item["source"] = args.source
    item["added_by"] = _agent()  # used for a new item only; a re-add keeps the original
    item["added"] = _now().isoformat(timespec="seconds")
    return item


def _shared_texts(args) -> list[str]:
    return [args.repo, args.title, args.why or "", args.source or ""] + list(args.tag)


# ---------------------------------------------------------------- verbs

def _build_add(args) -> dict:
    """The fields this call passed (not a full item: see `_upsert`)."""
    steps = [_parse_step(s) for s in args.step]
    if not steps:
        raise Refused("add needs at least one --step")
    texts = _shared_texts(args) + [args.verify, args.rollback or ""]
    for s in steps:
        texts += [s["cmd"], s["expect"], s["prompts"]]
    _check_text(texts)
    item = {"repo": args.repo, "title": args.title, "why": args.why, "kind": "steps",
            "steps": steps, "verify": args.verify}
    if args.rollback is not None:
        item["rollback"] = args.rollback
    return _common(args, item)


def _build_decision(args) -> dict:
    """The fields this call passed. The answer goes to top-level `chosen`/`other` only."""
    options = [_parse_option(o) for o in args.option]
    if len(options) < 2:
        raise Refused("add-decision needs at least two --option")
    _check_text(_shared_texts(args) + [o["label"] + " " + o["detail"] for o in options])
    item = {"repo": args.repo, "title": args.title, "kind": "decision",
            "decision": {"options": options}}
    if args.why:
        item["why"] = args.why
    return _common(args, item)


def _redacted(text: str) -> str:
    """Free text from the processor is redacted, not refused; say what was removed."""
    text, kinds = rblib.redact(text)
    if kinds:
        print("redacted: " + ", ".join(kinds), file=sys.stderr)
    return text


def _find(state: dict, item_id: str) -> dict:
    for it in state["items"]:
        if it.get("id") == item_id:
            return it
    raise Refused(f"unknown item id: {item_id}")


def _add_like(item: dict, state_path: Path, cwd: Path | None) -> int:
    def fn(state):
        return _upsert(state, item)[0]

    try:
        item_id = rblib.mutate(fn, state_path)
    except OSError as e:
        if not isinstance(e, PermissionError) and e.errno not in _NOT_WRITABLE:
            raise  # e.g. a missing state directory: an error, not an inbox case
        root = _repo_root(cwd or Path.cwd())
        if root is None:
            print(f"error: cannot write {state_path} ({e}) and {cwd or Path.cwd()} "
                  "is not inside a git repo, so no inbox fallback", file=sys.stderr)
            return ERROR
        path = write_inbox(item, root)
        print(f"state not writable; queued in inbox: {path}")
        return INBOXED
    print(item_id)
    return OK


def _mutating(fn, state_path: Path) -> int:
    rblib.mutate(fn, state_path)
    return OK


def _run(args, state_path: Path, cwd: Path | None) -> int:
    cmd = args.cmd
    if cmd == "add":
        return _add_like(_build_add(args), state_path, cwd)
    if cmd == "add-decision":
        return _add_like(_build_decision(args), state_path, cwd)
    if cmd == "list":
        for it in rblib.load(state_path)["items"]:
            if args.state and it.get("state") != args.state:
                continue
            print(f'{it["id"]}  {it.get("state")}  {it.get("repo")}  {it.get("title")}')
        return OK
    if cmd == "show":
        st = rblib.load(state_path)
        for it in st["items"] + st["done_log"]:
            if it.get("id") == args.id:
                print(json.dumps(it, indent=2, ensure_ascii=False))
                return OK
        raise Refused(f"unknown item id: {args.id}")
    if cmd == "verified":
        note = _redacted(args.note)

        def fn(state):
            try:
                rblib.move_to_done_log(state, args.id, f"verified: {note}", _agent(), _now())
            except KeyError:
                raise Refused(f"unknown item id: {args.id}") from None
        return _mutating(fn, state_path)
    if cmd == "reopen":
        note = _redacted(args.note)

        def fn(state):
            it = _find(state, args.id)
            it["state"] = "open"
            it["agent_note"] = note
        return _mutating(fn, state_path)
    if cmd == "reply":
        text = _redacted(args.text)

        def fn(state):
            for n in state["notes_claude"]:
                if n.get("id") == args.note_id:
                    n["reply"] = text
                    n["status"] = "asked-back" if args.asked_back else "answered"
                    return
            raise Refused(f"unknown note id: {args.note_id}")
        return _mutating(fn, state_path)
    if cmd == "restore":
        def fn(state):
            try:
                it = rblib.restore_from_done_log(state, args.id)
            except KeyError:
                raise Refused(f"unknown done-log id: {args.id}") from None
            it["state"] = "open"
        return _mutating(fn, state_path)
    raise Refused(f"unknown command: {cmd}")


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="runbook")
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp, why_required):
        sp.add_argument("--repo", required=True)
        sp.add_argument("--title", required=True)
        sp.add_argument("--why", required=why_required, default="")
        sp.add_argument("--due")
        sp.add_argument("--after", action="append", default=[])
        sp.add_argument("--priority")
        sp.add_argument("--tag", action="append", default=[])
        sp.add_argument("--source")

    a = sub.add_parser("add")
    common(a, True)
    a.add_argument("--step", action="append", default=[])
    a.add_argument("--verify", required=True)
    a.add_argument("--rollback")

    d = sub.add_parser("add-decision")
    common(d, False)
    d.add_argument("--option", action="append", default=[])

    ls = sub.add_parser("list")
    ls.add_argument("--state", choices=rblib.ITEM_STATES)
    sub.add_parser("show").add_argument("id")
    for name in ("verified", "reopen"):
        v = sub.add_parser(name)
        v.add_argument("id")
        v.add_argument("--note", required=True)
    r = sub.add_parser("reply")
    r.add_argument("note_id")
    r.add_argument("--text", required=True)
    r.add_argument("--asked-back", action="store_true")
    sub.add_parser("restore").add_argument("id")
    return p


def main(argv: list[str], state_path: Path = rblib.STATE, cwd: Path | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
    except SystemExit as e:  # argparse exits 2 on bad usage, 0 on --help
        return int(e.code or 0)
    try:
        return _run(args, Path(state_path), cwd)
    except Refused as e:
        print(str(e), file=sys.stderr)
        return REFUSED
    except (rblib.LockTimeout, rblib.CorruptState, rblib.StaleVersion, OSError) as e:
        print(f"error: {type(e).__name__}: {e}", file=sys.stderr)
        return ERROR


if __name__ == "__main__":
    # process.py sets RUNBOOK_STATE when it runs against a non-default state file.
    sys.exit(main(sys.argv[1:], Path(os.environ.get("RUNBOOK_STATE") or rblib.STATE)))

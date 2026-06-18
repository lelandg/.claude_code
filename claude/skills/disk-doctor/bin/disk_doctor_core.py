"""disk-doctor safety core. Standard library only.

The ONLY code in disk-doctor that can delete. Deny-by-default, in-script
denylist floor, Trash-not-rm, manifest-before-move, dry-run default.
"""
import json
import os
import shutil
import time
import urllib.parse
from pathlib import Path


def home():
    return Path(os.path.expanduser("~"))


def resolve_path(p):
    return Path(p).expanduser().resolve(strict=False)


def denylist_floor():
    """Absolute never-touch roots. Cannot be weakened by rule packs."""
    h = home()
    raw = [
        Path("/usr"), Path("/etc"), Path("/bin"), Path("/sbin"),
        Path("/boot"), Path("/lib"), Path("/lib64"), Path("/opt"), Path("/var"),
        Path("/proc"), Path("/dev"), Path("/run"), Path("/sys"),
        Path("/System"), Path("/Library"),
        Path("C:/Windows"), Path("C:/Program Files"), Path("C:/Program Files (x86)"),
        h / ".ssh", h / ".config", h / ".gnupg",
        h / ".local" / "share",                  # app data (Steam, GNOME state, etc.)
        # browser profiles (bookmarks/history/logins)
        h / ".mozilla",
        h / ".config" / "google-chrome",
        h / ".config" / "chromium",
        h / "snap" / "firefox",
        h / "Library" / "Application Support" / "Firefox",
        h / "Library" / "Application Support" / "Google" / "Chrome",
        h / "Library" / "Application Support" / "Chromium",
    ]
    return [resolve_path(p) for p in raw]


class Verdict:
    OK = "ok"
    DENIED = "denied"
    NOT_ALLOWED = "not_allowed"
    MISSING = "missing"
    SYMLINK = "symlink"


def _is_within(path, root):
    return path == root or root in path.parents


def classify(path, allowed_roots, extra_denied=()):
    """Return (Verdict, resolved_path). Deny is checked before allow."""
    raw = Path(path).expanduser()
    if raw.is_symlink():
        return Verdict.SYMLINK, raw
    rp = resolve_path(raw)
    if not rp.exists():
        return Verdict.MISSING, rp

    # Roots denied by EXACT match only. Ancestor-matching these would block
    # every path beneath them (they are ancestors of the entire tree).
    exact_only_denied = [resolve_path(home()), resolve_path(Path("/"))]
    if rp in exact_only_denied:
        return Verdict.DENIED, rp

    denied = denylist_floor() + [resolve_path(x) for x in extra_denied]
    for d in denied:
        if _is_within(rp, d):
            return Verdict.DENIED, rp
    for root in allowed_roots:
        if _is_within(rp, resolve_path(root)):
            return Verdict.OK, rp
    return Verdict.NOT_ALLOWED, rp


def base_dir(base=None):
    return Path(base) if base is not None else home() / ".disk-doctor"


def _now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def log_event(event, path, detail, base=None):
    b = base_dir(base)
    b.mkdir(parents=True, exist_ok=True)
    line = "%s\t%s\t%s\t%s\n" % (_now_iso(), event, path, detail)
    with open(b / "disk-doctor.log", "a", encoding="utf-8") as fh:
        fh.write(line)


def _size(path):
    if path.is_dir():
        total = 0
        for root, _dirs, files in os.walk(path):
            for f in files:
                fp = Path(root) / f
                if not fp.is_symlink() and fp.exists():
                    total += fp.stat().st_size
        return total
    return path.stat().st_size


def _freedesktop_trash_dir():
    data_home = os.environ.get("XDG_DATA_HOME") or str(home() / ".local" / "share")
    return Path(data_home) / "Trash"


def _unique_name(directory, name):
    candidate = directory / name
    i = 1
    while candidate.exists():
        candidate = directory / ("%s.%d" % (name, i))
        i += 1
    return candidate


def _compute_dest(rp, run_id, base, prefer_freedesktop):
    """Decide where the file will go. Does NOT move it."""
    if prefer_freedesktop:
        files_dir = _freedesktop_trash_dir() / "files"
        try:
            files_dir.mkdir(parents=True, exist_ok=True)
            dest = _unique_name(files_dir, rp.name)
            return dest, "freedesktop"
        except OSError:
            pass  # fall through to quarantine
    q = base_dir(base) / "trash" / run_id
    q.mkdir(parents=True, exist_ok=True)
    return _unique_name(q, rp.name), "quarantine"


def _write_trashinfo(dest, original):
    info_dir = _freedesktop_trash_dir() / "info"
    info_dir.mkdir(parents=True, exist_ok=True)
    info_path = info_dir / (dest.name + ".trashinfo")
    quoted = urllib.parse.quote(str(original))
    info_path.write_text(
        "[Trash Info]\nPath=%s\nDeletionDate=%s\n" % (quoted, _now_iso()),
        encoding="utf-8",
    )
    return info_path


def _append_manifest(base, run_id, record):
    runs = base_dir(base) / "runs"
    runs.mkdir(parents=True, exist_ok=True)  # raises OSError if 'runs' exists as a file
    with open(runs / ("%s.jsonl" % run_id), "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")


def trash_item(path, run_id, allowed_roots, *, commit=False,
               extra_denied=(), base=None, prefer_freedesktop=True):
    verdict, rp = classify(path, allowed_roots, extra_denied)
    if verdict != Verdict.OK:
        log_event("refuse", rp, verdict, base)
        return {"original": str(rp), "action": "refused", "reason": verdict}

    record = {"run_id": run_id, "ts": _now_iso(), "original": str(rp), "size": _size(rp)}
    if not commit:
        record["action"] = "dry-run"
        return record

    dest, method = _compute_dest(rp, run_id, base_dir(base), prefer_freedesktop)
    record["dest"] = str(dest)
    record["method"] = method
    record["action"] = "trashed"

    # Manifest BEFORE move. If this raises, we abort without touching the file.
    try:
        _append_manifest(base, run_id, record)
    except OSError as exc:
        log_event("abort-no-manifest", rp, str(exc), base)
        raise

    shutil.move(str(rp), str(dest))
    if method == "freedesktop":
        _write_trashinfo(dest, rp)
    log_event("trash", rp, dest, base)
    return record


def latest_run_id(base=None):
    runs = base_dir(base) / "runs"
    if not runs.is_dir():
        return None
    manifests = sorted(runs.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    return manifests[0].stem if manifests else None


def restore_run(run_id, *, base=None):
    manifest = base_dir(base) / "runs" / ("%s.jsonl" % run_id)
    results = []
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        if rec.get("action") != "trashed":
            continue
        original = Path(rec["original"])
        dest = Path(rec["dest"])
        if original.exists():
            log_event("undo-collision", original, dest, base)
            results.append({"original": str(original), "status": "collision"})
            continue
        if not dest.exists():
            log_event("undo-missing", original, dest, base)
            results.append({"original": str(original), "status": "missing-in-trash"})
            continue
        original.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(dest), str(original))
        # Clean up FreeDesktop .trashinfo sidecar if present.
        if rec.get("method") == "freedesktop":
            info = _freedesktop_trash_dir() / "info" / (dest.name + ".trashinfo")
            if info.exists():
                info.unlink()
        log_event("undo-restore", original, dest, base)
        results.append({"original": str(original), "status": "restored"})
    return results


REQUIRED_RULE_SECTIONS = [
    "Allowed roots",
    "Never-touch (additional)",
    "Cache-clean rules",
    "Install-hygiene rules",
]


def validate_rule_pack(path):
    """Return list of required section headings missing from the rule pack."""
    text = Path(path).read_text(encoding="utf-8")
    headings = {line.lstrip("#").strip() for line in text.splitlines() if line.lstrip().startswith("#")}
    return [s for s in REQUIRED_RULE_SECTIONS if s not in headings]

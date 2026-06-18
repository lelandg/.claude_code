"""disk-doctor safety core. Standard library only.

The ONLY code in disk-doctor that can delete. Deny-by-default, in-script
denylist floor, Trash-not-rm, manifest-before-move, dry-run default.
"""
import os
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

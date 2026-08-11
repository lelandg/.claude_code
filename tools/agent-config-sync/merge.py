#!/usr/bin/env python3
"""Reviewed merge: the only module that writes to a target.

Nothing is applied that was not named by id, re-verified against a fresh scan,
and backed up first. Plugin operations are proposed, never executed.

    merge.py plan    --drift FILE --manifest FILE --id ID [--id ID ...]
    merge.py apply   --drift FILE --manifest FILE --id ID [--id ID ...]
    merge.py restore --backup-dir DIR | --run-id ID [--state-dir DIR]

Design: "Reviewed application workflow", "Backups and recovery".
"""
from __future__ import annotations

import argparse
import copy
import json
import shutil
from dataclasses import dataclass
from pathlib import Path

import drift
import extract
import manifest as mf
import normalize as nz

EXIT_OK = 0
EXIT_FAILURE = 20
EXIT_STALE = 22
EXIT_NOTHING_SELECTED = 23


class MergeError(RuntimeError):
    """A target cannot be merged safely. The message names the target."""


#: Classifications this tool knows how to act on.
_PUBLISH = "publish_to_repo"
_WSL_ONLY = "wsl_only"
_RECONCILE = "reconcile_windows"
_PLUGIN = ("plugin_missing", "plugin_enabled_differs",
           "plugin_version_differs", "plugin_pin_violation")

#: classify() only ever reaches "publish_to_repo" when Windows was not
#: independently diverged: either Windows already matches WSL (nothing to
#: cascade), or Windows still mirrors the old, stale baseline -- the same
#: bytes repo is about to move away from. Bringing repo forward is safe to
#: mirror onto Windows in the same action; "wsl_only" (a brand-new item, not
#: present in repo or Windows) is the same case with an absent baseline.
#: "reconcile_windows" is different in kind: repo already matches WSL and
#: Windows alone has drifted, which is exactly the situation that needs a
#: human to look before overwriting Windows-specific state.
_PUBLISH_LIKE = (_PUBLISH, _WSL_ONLY)

#: Layers this tool is ever allowed to write. WSL is authoritative and is
#: never a merge target -- the whole point of the merge is to bring the
#: repository baseline and the Windows mirror into line with it.
_WRITABLE_LAYERS = ("repo", "windows")


@dataclass(frozen=True)
class Action:
    item_id: str
    kind: str            # write_file | set_field | plugin_command | noop
    layer: str
    target: Path | None
    pointer: str | None
    description: str
    command: tuple[str, ...] | None = None
    #: A publish also mirrors to Windows in the same reviewed action when
    #: Windows was only ever a passive copy of the (now stale) baseline --
    #: see the comment on _PUBLISH_LIKE in plan_merge. None when there is
    #: nothing to mirror (reconcile actions, or no Windows root configured).
    cascade_target: Path | None = None
    #: The WSL path this action reads. Planned here, not re-derived in
    #: apply_plan: a tree item names one file inside the entry directory, so
    #: an apply that rebuilds the source from the entry alone reads the
    #: directory and never the file the id names (fix wave, C1). One
    #: derivation means the dry run shows exactly what the apply will read.
    source: Path | None = None


@dataclass(frozen=True)
class Plan:
    run_id: str
    actions: tuple[Action, ...]
    skipped: tuple[tuple[str, str], ...]


# --------------------------------------------------------------------------
# pointers
# --------------------------------------------------------------------------

def get_pointer(data, pointer: str):
    current = data
    for segment in pointer.split("."):
        if not isinstance(current, dict) or segment not in current:
            return None
        current = current[segment]
    return current


def set_pointer(data: dict, pointer: str, value) -> dict:
    out = copy.deepcopy(data)
    current = out
    segments = pointer.split(".")
    for segment in segments[:-1]:
        nxt = current.get(segment)
        if not isinstance(nxt, dict):
            nxt = {}
            current[segment] = nxt
        current = nxt
    current[segments[-1]] = value
    return out


# --------------------------------------------------------------------------
# staleness
# --------------------------------------------------------------------------

def _current_units(m, entries) -> dict[tuple[str, str], extract.Unit]:
    """Live fingerprints for exactly the given entries, in every layer.

    Scoped deliberately (Task 11 ruling 3): extracting every entry in the
    manifest across every layer takes minutes on a real profile, which would
    make every ``plan``/``apply`` invocation appear to hang. The caller
    narrows ``entries`` to only what the selected item ids reference.
    """
    units: dict[tuple[str, str], extract.Unit] = {}
    for entry in entries:
        for layer in extract.LAYERS:
            root = m.roots.for_layer(layer)
            for unit in extract.extract_entry(entry, layer, root, m.secrets,
                                              m.roots):
                units[(layer, unit.unit_id)] = unit
    return units


def stale_items(doc: dict, m, selected_ids: list[str] | None = None) -> list[str]:
    """Item ids whose recorded fingerprints no longer match the filesystem.

    ``selected_ids``, when given, restricts both which items are checked and
    which manifest entries are re-extracted to answer the question -- see
    ``_current_units``. Left ``None``, every actionable item in the document
    is checked, scoped to only the entries those items reference (still far
    less than the whole manifest for a partial report).
    """
    items = doc.get("items", [])
    if selected_ids is not None:
        selected = set(selected_ids)
        items = [item for item in items if item["id"] in selected]

    entry_ids = {item["entry_id"] for item in items if item["kind"] != "plugin"}
    entries = [e for e in m.entries if e.id in entry_ids]
    current = _current_units(m, entries)

    stale: list[str] = []
    for item in items:
        if item["kind"] == "plugin":
            continue
        for layer, key in (("wsl", "wsl_fingerprint"),
                           ("repo", "repo_fingerprint"),
                           ("windows", "windows_fingerprint")):
            recorded = item.get(key)
            unit = current.get((layer, item["id"]))
            live = unit.fingerprint if unit else None
            if recorded != live:
                stale.append(item["id"])
                break
    return stale


# --------------------------------------------------------------------------
# planning
# --------------------------------------------------------------------------

def _entry_for(m, entry_id: str):
    try:
        return m.entry(entry_id)
    except mf.ManifestError:
        return None


def _target_path(m, entry, layer: str) -> Path | None:
    if layer not in _WRITABLE_LAYERS:
        return None
    root = m.roots.for_layer(layer)
    rel = entry.rel_for_layer(layer)
    if root is None or rel is None:
        return None
    return Path(root) / rel


def _plugin_command(detail: str) -> tuple[str, ...] | None:
    marker = "claude plugin"
    if marker not in detail:
        return None
    tail = detail[detail.index(marker):]
    for stop in (".", "\n"):
        if stop in tail:
            tail = tail[:tail.index(stop)]
    return tuple(tail.split())


def plan_merge(doc: dict, m, selected_ids) -> Plan:
    by_id = {item["id"]: item for item in doc.get("items", [])}
    actions: list[Action] = []
    skipped: list[tuple[str, str]] = []

    for item_id in selected_ids:
        item = by_id.get(item_id)
        if item is None:
            skipped.append((item_id, "not present in this report"))
            continue
        if item["policy"] == "platform_overlay":
            skipped.append((item_id, "protected Windows state; never applied"))
            continue
        classification = item["classification"]

        if classification in _PLUGIN:
            command = _plugin_command(item["detail"])
            if command is None:
                skipped.append((item_id, "no native command proposed"))
                continue
            actions.append(Action(
                item_id=item_id, kind="plugin_command", layer="native",
                target=None, pointer=None, command=command,
                description=f"run by hand: {' '.join(command)}"))
            continue

        if classification not in _PUBLISH_LIKE and classification != _RECONCILE:
            skipped.append((item_id,
                            f"{classification} requires a decision, not an "
                            f"automatic action"))
            continue

        entry = _entry_for(m, item["entry_id"])
        if entry is None:
            skipped.append((item_id, "entry is no longer in the manifest"))
            continue

        # The part of the id after the colon: a path inside the directory for
        # a tree entry, a dotted field pointer for a json/toml entry.
        key = item_id.split(":", 1)[1] if ":" in item_id else ""

        if entry.kind == "toml" and key:
            # Python 3.12 ships a TOML reader and no TOML writer, so the only
            # way to merge one field would be to re-serialize the document as
            # JSON into a file named .toml -- silent corruption a later scan
            # cannot see, because both sides tokenize to the same fingerprint
            # (fix wave, C2). A refusal is correct until a writer is adopted.
            skipped.append((item_id, "TOML field merge is not implemented; "
                                     "edit the target by hand"))
            continue

        primary_layer = "repo" if classification in _PUBLISH_LIKE else "windows"
        target = _target_path(m, entry, primary_layer)
        if target is None:
            skipped.append((item_id, f"no {primary_layer} root configured"))
            continue

        source = _target_path_any_layer(m, entry, "wsl")
        if source is None:
            skipped.append((item_id, "no wsl path declared for this entry"))
            continue

        cascade_target = (_target_path(m, entry, "windows")
                          if classification in _PUBLISH_LIKE else None)

        if entry.kind == "tree" and key:
            # A tree item names one file inside the entry directory. Every
            # path this action touches has to descend into it.
            target = target / key
            source = source / key
            cascade_target = (cascade_target / key
                              if cascade_target is not None else None)

        # A path that is a directory means the id was resolved to the wrong
        # place. Refuse here rather than hand a directory to a reader or a
        # writer: the old apply raised IsADirectoryError from inside the
        # write loop, after the backup directory had already been created.
        if source.is_dir():
            skipped.append((item_id, f"{source} is a directory, not a file; "
                                     f"this id names no file to copy"))
            continue
        directory = next((path for path in (target, cascade_target)
                          if path is not None and path.is_dir()), None)
        if directory is not None:
            skipped.append((item_id, f"{directory} is a directory, not a "
                                     f"file; refusing to write it"))
            continue

        mirror_note = f" (mirrors to {cascade_target})" if cascade_target else ""

        if entry.kind == "json" and key:
            actions.append(Action(
                item_id=item_id, kind="set_field", layer=primary_layer,
                target=target, pointer=key,
                description=f"set {key} in {target} from WSL{mirror_note}",
                cascade_target=cascade_target, source=source))
        else:
            actions.append(Action(
                item_id=item_id, kind="write_file", layer=primary_layer,
                target=target, pointer=None,
                description=f"write {target} from WSL{mirror_note}",
                cascade_target=cascade_target, source=source))

    return Plan(run_id=doc["run_id"], actions=tuple(actions),
                skipped=tuple(skipped))


def render_plan(plan: Plan) -> str:
    lines = [f"DRY RUN — merge plan for report {plan.run_id}", ""]
    if plan.actions:
        for action in plan.actions:
            lines.append(f"- [{action.kind}] `{action.item_id}` → "
                         f"{action.description}")
    else:
        lines.append("- (nothing to do)")
    if plan.skipped:
        lines.append("")
        lines.append("Skipped:")
        lines.extend(f"- `{item_id}`: {reason}"
                     for item_id, reason in plan.skipped)
    lines.append("")
    lines.append("Nothing above has been applied. Re-run with --apply to act.")
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------
# applying
# --------------------------------------------------------------------------

def write_target(path: Path, text: str) -> None:
    """Indirection so tests can simulate a mid-apply failure."""
    drift.write_atomic(path, text)


def _read_source(source: Path | None) -> str | None:
    """Read the planned WSL source. None when there is nothing to copy.

    The path comes from the plan (``Action.source``) and is never re-derived
    here -- see the note on that field.
    """
    if source is None or not source.is_file():
        return None
    return source.read_text(encoding="utf-8")


def _target_path_any_layer(m, entry, layer: str) -> Path | None:
    """Like ``_target_path`` but not restricted to writable layers.

    The merge source is always read from WSL, which is never a write target.
    """
    root = m.roots.for_layer(layer)
    rel = entry.rel_for_layer(layer)
    if root is None or rel is None:
        return None
    return Path(root) / rel


def _desired_for_layer(m, entry, raw: str, layer: str) -> str:
    normalized = nz.normalize_for_kind(raw, "text")
    tokenized = nz.tokenize_paths(normalized, m.roots)
    return nz.render_paths(tokenized, layer, m.roots)


def _render_value(m, value, layer: str):
    """Tokenize and re-render every string inside one field value.

    A whole-file write goes through _desired_for_layer, which tokenizes the
    WSL path spellings and renders them for the target layer. A field write
    has to do the same or it copies /home/... verbatim into a Windows file --
    and the scanner tokenizes before it fingerprints, so the broken result
    would be reported as clean (fix wave, I2). String leaves are rendered
    one at a time; rendering the serialized JSON instead would emit Windows
    backslashes that JSON cannot re-parse.
    """
    if isinstance(value, str):
        return nz.render_paths(nz.tokenize_paths(value, m.roots), layer,
                               m.roots)
    if isinstance(value, list):
        return [_render_value(m, item, layer) for item in value]
    if isinstance(value, dict):
        return {key: _render_value(m, item, layer)
                for key, item in value.items()}
    return value


def _desired_for_target(m, entry, raw: str, layer: str, action: Action,
                        target: Path) -> str:
    if action.kind == "write_file":
        return _desired_for_layer(m, entry, raw, layer)
    pointer = action.pointer or ""
    source_data = json.loads(nz.normalize_for_kind(raw, entry.kind))
    value = _render_value(m, get_pointer(source_data, pointer), layer)
    existing: object = {}
    if target.exists():
        try:
            existing = json.loads(target.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise MergeError(
                f"{target} is not valid JSON (line {exc.lineno}, column "
                f"{exc.colno}); refusing to replace it with a merged "
                f"document") from None
    if not isinstance(existing, dict):
        raise MergeError(f"{target} holds a JSON "
                         f"{type(existing).__name__}, not an object; "
                         f"a field merge has nothing to set {pointer} on")
    return json.dumps(set_pointer(existing, pointer, value),
                      indent=2, sort_keys=True) + "\n"


def apply_plan(plan: Plan, m, *, backups_dir: Path) -> tuple[Path, list[str]]:
    backup_dir = Path(backups_dir) / plan.run_id
    files_dir = backup_dir / "files"
    files_dir.mkdir(parents=True, exist_ok=True)

    records: list[dict] = []
    applied: list[str] = []
    manual: list[list[str]] = []

    def flush_manifest() -> None:
        # The backup manifest must be on disk before write_target runs: a
        # crash mid-write must still leave something to restore from (Task
        # 11 ruling 4).
        drift.write_atomic(backup_dir / "manifest.json", json.dumps({
            "run_id": plan.run_id, "files": records,
            "manual_recovery": manual,
        }, indent=2) + "\n")

    for index, action in enumerate(plan.actions):
        if action.kind == "plugin_command":
            manual.append(list(action.command or ()))
            continue
        if action.target is None:
            continue

        entry = _entry_for(m, action.item_id.split(":", 1)[0])
        if entry is None:
            continue
        raw = _read_source(action.source)
        if raw is None:
            continue

        targets = [(action.layer, action.target)]
        if action.cascade_target is not None:
            targets.append(("windows", action.cascade_target))

        item_applied = False
        for sub_index, (layer, target) in enumerate(targets):
            desired = _desired_for_target(m, entry, raw, layer, action, target)

            existed = target.exists()
            current = target.read_text(encoding="utf-8") if existed else None
            if current == desired:
                continue                              # already applied: no-op

            stored = files_dir / f"{index:03d}-{sub_index}"
            if existed:
                shutil.copy2(target, stored)
            records.append({
                "index": index,
                "item_id": action.item_id,
                "target": str(target),
                "layer": layer,
                "existed": existed,
                "stored": stored.name if existed else None,
                "sha256_before": (nz.fingerprint(current)
                                 if current is not None else None),
            })
            flush_manifest()

            write_target(target, desired)
            item_applied = True

        if item_applied:
            applied.append(action.item_id)

    flush_manifest()
    return backup_dir, applied


def restore(backup_dir: Path) -> list[str]:
    backup_dir = Path(backup_dir)
    data = json.loads((backup_dir / "manifest.json").read_text(encoding="utf-8"))
    restored: list[str] = []
    for record in reversed(data["files"]):
        target = Path(record["target"])
        if record["existed"]:
            shutil.copy2(backup_dir / "files" / record["stored"], target)
        elif target.exists():
            target.unlink()
        restored.append(record["item_id"])
    return restored


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def _load_doc(args) -> dict:
    if args.drift_json:
        return json.loads(args.drift_json)
    return json.loads(Path(args.drift).read_text(encoding="utf-8"))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="merge.py")
    sub = parser.add_subparsers(dest="verb", required=True)

    for verb in ("plan", "apply"):
        sp = sub.add_parser(verb)
        sp.add_argument("--drift", type=Path)
        sp.add_argument("--drift-json", help="the document inline (for tests)")
        sp.add_argument("--manifest", required=True, type=Path)
        sp.add_argument("--id", action="append", default=[], dest="ids")

    sp = sub.add_parser("restore")
    sp.add_argument("--backup-dir", type=Path)
    sp.add_argument("--run-id")
    sp.add_argument("--state-dir", type=Path)

    args = parser.parse_args(argv)

    if args.verb == "restore":
        backup_dir = args.backup_dir
        if backup_dir is None:
            if not (args.run_id and args.state_dir):
                print("restore: need --backup-dir, or --run-id with --state-dir")
                return EXIT_FAILURE
            backup_dir = Path(args.state_dir) / "backups" / args.run_id
        for item_id in restore(backup_dir):
            print(f"restored {item_id}")
        return EXIT_OK

    try:
        m = mf.load_manifest(args.manifest)
        doc = _load_doc(args)
    except (mf.ManifestError, OSError, json.JSONDecodeError) as exc:
        print(f"merge: {type(exc).__name__}: {exc}")
        return EXIT_FAILURE

    if not args.ids:
        print("merge: name at least one --id; nothing is applied by default")
        return EXIT_NOTHING_SELECTED

    # Scoped to the selected ids (Task 11 ruling 3): re-extracting only the
    # entries those ids reference keeps a stale check fast on a real profile.
    stale = stale_items(doc, m, selected_ids=args.ids)
    if stale:
        print("merge: this report is stale for: " + ", ".join(stale))
        print("Re-run the scan and use the new report.")
        return EXIT_STALE

    plan = plan_merge(doc, m, args.ids)
    print(render_plan(plan), end="")
    if args.verb == "plan":
        return EXIT_OK

    try:
        backup_dir, applied = apply_plan(plan, m,
                                         backups_dir=m.state_dir / "backups")
    except MergeError as exc:
        print(f"merge: {exc}")
        return EXIT_FAILURE
    print(f"backup: {backup_dir}")
    for item_id in applied:
        print(f"applied {item_id}")
    manual = [a for a in plan.actions if a.kind == "plugin_command"]
    if manual:
        print("\nRun these by hand — this tool never executes a package "
              "manager:")
        for action in manual:
            print("  " + " ".join(action.command or ()))
    print(f"\nRestore with: merge.py restore --backup-dir {backup_dir}")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Deterministic Markdown rendering of a drift document plus model analysis.

The model supplies judgment (summary, ordering, notes); this module supplies
every fact and every heading. A malformed analysis degrades the prose, never
the facts.

Design: "Report format".
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import analyze
import drift as drift_mod

REPORT_TEMPLATE_VERSION = 1

SECTIONS = (
    "Executive summary",
    "Safe portable updates",
    "Conflicts requiring judgment",
    "WSL-only and Windows-only items",
    "Protected Windows state",
    "Plugin differences",
    "Portability warnings",
    "Excluded and redacted",
    "Scan errors",
    "Recommended merge order",
    "Claude handoff prompt",
    "Validation and restoration",
)

#: Every non-"unchanged" classification maps to exactly one section. This is a
#: partition by construction: a classification in two sections double-counts,
#: and one in none disappears from the body while still being tallied in the
#: header. (Review ruling, 2026-08-11.)
SECTION_OF = {
    "publish_to_repo": "Safe portable updates",
    "reconcile_windows": "Safe portable updates",
    "conflict": "Conflicts requiring judgment",
    "wsl_only": "WSL-only and Windows-only items",
    "windows_only": "WSL-only and Windows-only items",
    "additive_delete_requires_approval": "WSL-only and Windows-only items",
    "protected_overlay": "Protected Windows state",
    "plugin_missing": "Plugin differences",
    "plugin_removed": "Plugin differences",
    "plugin_extra": "Plugin differences",
    "plugin_enabled_differs": "Plugin differences",
    "plugin_version_differs": "Plugin differences",
    "plugin_pin_violation": "Plugin differences",
    "plugin_incompatible": "Plugin differences",
    "error": "Scan errors",
}


def empty_analysis() -> dict:
    return {
        "response_schema_version": 1,
        "summary": "(no model analysis: the report was rendered from the "
                   "deterministic scan alone)",
        "severity": "review",
        "recommended_order": [],
        "notes": [],
        "codex_review_recommended": False,
        "codex_reason": "",
    }


def _short(value: str | None) -> str:
    return value[:12] if value else "-"


def _heading(name: str, count: int) -> str:
    """An item-bearing H2, with its count so a reader can skip cheaply."""
    return f"## {name} ({count})"


def _by(items, section: str) -> list[dict]:
    return [i for i in items if SECTION_OF.get(i["classification"]) == section]


def _notes(analysis) -> dict[str, str]:
    return {n["item_id"]: n["note"] for n in analysis.get("notes", [])
            if isinstance(n, dict) and "item_id" in n and "note" in n}


def _item_lines(items, notes) -> list[str]:
    lines: list[str] = []
    for item in items:
        lines.append(
            f"- `{item['id']}` — **{item['classification']}** "
            f"({item['policy']})  \n"
            f"  path: `{item['path']}`  \n"
            f"  wsl `{_short(item.get('wsl_fingerprint'))}` · "
            f"repo `{_short(item.get('repo_fingerprint'))}` · "
            f"windows `{_short(item.get('windows_fingerprint'))}`  \n"
            f"  {item['detail']}")
        if item["id"] in notes:
            lines.append(f"  \n  > {notes[item['id']]}")
    return lines or ["_None._"]


def windows_path(posix: str) -> str | None:
    """The Windows spelling of a WSL /mnt/<drive> path, or None when the
    path has no drive-letter equivalent. Files consumed on Windows are
    referenced by their Windows name only (Leland, 2026-08-14)."""
    match = re.match(r"^/mnt/([a-z])(/.*)?$", posix)
    if not match:
        return None
    drive = match.group(1).upper()
    rest = (match.group(2) or "").replace("/", "\\")
    return f"{drive}:{rest}"


def windows_script(doc: dict) -> str | None:
    """A PowerShell script holding the Windows-side plugin actions of this
    run, CRLF-terminated, or None when the run proposes none.

    Selection mirrors the actions the report asks Leland to run by hand on
    the Windows machine: installs missing there, applies the record's
    enabled state where Windows disagrees (either direction), updates
    where Windows holds the older build, and uninstalls where the plugin
    is gone from WSL (the authority) but still installed on Windows.
    WSL-side enable mismatches are record maintenance, not Windows work,
    so they are excluded."""
    commands: list[str] = []
    for item in doc.get("items", []):
        classification = item.get("classification")
        item_id = item.get("id", "")
        detail = item.get("detail", "")
        if (classification == "plugin_missing"
                and item_id.endswith("#missing:windows")):
            commands.append(f"claude plugin install {item['path']}")
        elif (classification == "plugin_enabled_differs"
                and item_id.endswith("#enabled:windows")):
            # The record decides the direction; the detail's proposed
            # command already carries the right verb.
            verb = "disable" if "claude plugin disable" in detail else "enable"
            commands.append(f"claude plugin {verb} {item['path']}")
        elif (classification == "plugin_version_differs"
                and "upgrade windows with:" in detail):
            commands.append(f"claude plugin update {item['path']}")
        elif (classification == "plugin_removed"
                and "claude plugin uninstall" in detail):
            commands.append(f"claude plugin uninstall {item['path']}")
    if not commands:
        return None
    lines = [
        f"# agent-config-sync — Windows plugin actions for run {doc['run_id']}",
        "# Run in PowerShell on the Windows machine.",
        "# The sync tool never executes a package manager; these commands are",
        "# generated for you to run and review by hand.",
        "",
        *commands,
        "",
    ]
    return "\r\n".join(lines)


def render_markdown(doc: dict, analysis: dict,
                    windows_script_ref: str | None = None) -> str:
    items = doc.get("items", [])
    notes = _notes(analysis)
    out: list[str] = []
    add = out.append

    add(f"# Agent config drift report — {doc['run_id']}")
    add("")
    add(f"- **Generated:** {doc['generated_at']}")
    add(f"- **Versions:** scanner {doc['scanner_version']} · "
        f"manifest {doc['manifest_version']} · "
        f"drift schema {doc['drift_schema_version']} · "
        f"template {REPORT_TEMPLATE_VERSION} · "
        f"response schema {analysis.get('response_schema_version', '-')}")
    for layer in ("wsl", "repo", "windows"):
        root = doc["roots"].get(layer)
        if root:
            add(f"- **{layer}:** `{root}` "
                f"(`{_short(doc['layer_fingerprints'].get(layer))}`)")
    add(f"- **Severity:** {analysis.get('severity', 'review')}")
    add("")
    add("> This report changes nothing. Application is a separate, approved "
        "operation — see the handoff prompt below.")
    add("")

    add("## Executive summary")
    add("")
    add(analysis.get("summary") or empty_analysis()["summary"])
    add("")
    if doc["counts"]:
        add("| Classification | Count |")
        add("|---|---|")
        for name in sorted(doc["counts"]):
            add(f"| `{name}` | {doc['counts'][name]} |")
    else:
        add("_No drift detected._")
    add("")

    for heading in ("Safe portable updates", "Conflicts requiring judgment",
                    "WSL-only and Windows-only items", "Protected Windows state",
                    "Plugin differences"):
        section_items = _by(items, heading)
        add(_heading(heading, len(section_items)))
        add("")
        if heading == "Conflicts requiring judgment":
            add("> Plugin pin violations are severity `conflict` too, but "
                "render under **Plugin differences** below so every plugin "
                "item is in one place.")
            add("")
        out.extend(_item_lines(section_items, notes))
        add("")

    warned = [i for i in items if i.get("portability")]
    add(_heading("Portability warnings", len(warned)))
    add("")
    out.extend([f"- `{i['id']}` (`{i['path']}`): " + "; ".join(i["portability"])
                for i in warned] or ["_None._"])
    add("")

    # No count in the heading (unlike the item-classification sections above):
    # redactions are pointer-level facts, not drift items, so folding this
    # count into the same "## Name (N)" shape would let it get swept into a
    # count of *items* by anything scanning headings for the item partition.
    add("## Excluded and redacted")
    add("")
    redaction_count = len(doc["redactions"])
    add(f"{redaction_count} value{'' if redaction_count == 1 else 's'} "
        "redacted. Values are never recorded — only a pointer, a reason "
        "code, a type, and a truncated hash.")
    add("")
    if doc["redactions"]:
        add("| Pointer | Reason | Type | Hash |")
        add("|---|---|---|---|")
        for redaction in doc["redactions"]:
            add(f"| `{redaction['pointer']}` | `{redaction['reason']}` | "
                f"{redaction['value_type']} | "
                f"`{_short(redaction['value_fingerprint'])}` |")
    else:
        add("_None._")
    add("")

    # The heading counts items, and the items are listed in the same shape as
    # every other item section. doc["errors"] holds only failures with no
    # comparable item (see the note in scan.run_scan); they are listed under
    # their own label so nothing appears twice and the count still matches the
    # bullets it heads.
    error_items = _by(items, "Scan errors")
    add(_heading("Scan errors", len(error_items)))
    add("")
    if error_items:
        out.extend(_item_lines(error_items, notes))
        add("")
    if doc["errors"]:
        add("Read failures with no comparable item (not counted above):")
        add("")
        out.extend(f"- `{e['path']}`: {e['message']}" for e in doc["errors"])
        add("")
    if not error_items and not doc["errors"]:
        add("_None._")
        add("")

    add("## Recommended merge order")
    add("")
    order = [i for i in analysis.get("recommended_order", [])
             if any(item["id"] == i for item in items)]
    if order:
        out.extend(f"{index}. `{item_id}`"
                   for index, item_id in enumerate(order, start=1))
    else:
        add("_No ordering supplied; apply safe portable updates before "
            "resolving conflicts._")
    add("")

    add("## Claude handoff prompt")
    add("")
    add("```text")
    add(f"Use the agent-config-merge skill on report {doc['run_id']}.")
    add("Apply only these item ids: <paste the ids you approve>")
    add("Dry-run first, show me the patch, then wait for my approval.")
    add("```")
    add("")

    if analysis.get("codex_review_recommended"):
        add("## Independent review (/codex)")
        add("")
        add(analysis.get("codex_reason") or
            "An independent cross-provider review is warranted.")
        add("")
        add("```text")
        add("/codex:review --base HEAD")
        add(f"Focus on report {doc['run_id']}: the conflict items above. "
            "Recommendations are advisory and cannot expand the approved scope.")
        add("```")
        add("")

    if windows_script_ref is not None:
        add("## Windows script")
        add("")
        add("The Windows-side plugin actions above are also written as one "
            "runnable script. Run it by hand in PowerShell on the Windows "
            "machine:")
        add("")
        add("```powershell")
        add(f"powershell -ExecutionPolicy Bypass -File \"{windows_script_ref}\"")
        add("```")
        add("")

    add("## Validation and restoration")
    add("")
    add("- Every applied change is backed up first, keyed by this run id.")
    add("- Re-run the scanner after applying; expected drift should be gone "
        "and nothing new should appear.")
    add("- Restore with: "
        "`python3 tools/agent-config-sync/merge.py restore --run-id "
        f"{doc['run_id']}`")
    add("")

    return "\n".join(out).rstrip() + "\n"


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

EXIT_OK = 0
EXIT_RENDER_FAILURE = 20
EXIT_MODEL_FAILURE = 30


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="render.py",
        description="Validate a model analysis and render the Markdown report.")
    parser.add_argument("--drift", required=True, type=Path)
    parser.add_argument("--state-dir", required=True, type=Path)
    parser.add_argument("--claude-bin", default="claude")
    parser.add_argument("--prompt", type=Path,
                        default=Path(__file__).resolve().parent / "prompts"
                        / "report-v1.md")
    parser.add_argument("--no-model", action="store_true",
                        help="render from the scan alone; do not call Claude")
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--max-turns", type=int, default=6)
    args = parser.parse_args(argv)

    try:
        doc = json.loads(args.drift.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"render: cannot read drift document: {type(exc).__name__}")
        return EXIT_RENDER_FAILURE

    if args.no_model:
        analysis = empty_analysis()
    else:
        try:
            analysis = analyze.run(doc, claude_bin=args.claude_bin,
                                   prompt_path=args.prompt,
                                   timeout_s=args.timeout,
                                   max_turns=args.max_turns)
        except analyze.AnalysisError as exc:
            print(f"render: {exc}")
            return EXIT_MODEL_FAILURE

    script = windows_script(doc)
    script_ref = None
    if script is not None:
        script_path = (Path(doc["roots"]["repo"]) / "Notes" / "scripts"
                       / f"agent-config-{doc['run_id']}.ps1")
        drift_mod.write_atomic(script_path, script)
        script_ref = windows_path(str(script_path)) or str(script_path)

    markdown = render_markdown(doc, analysis, windows_script_ref=script_ref)
    state_dir = args.state_dir
    drift_mod.write_atomic(state_dir / "reports" / f"{doc['run_id']}.md",
                           markdown)
    drift_mod.write_atomic(state_dir / "latest-report.md", markdown)
    print(str(state_dir / "latest-report.md"))
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())

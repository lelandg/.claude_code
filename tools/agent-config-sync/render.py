#!/usr/bin/env python3
"""Deterministic Markdown rendering of a drift document plus model analysis.

The model supplies judgment (summary, ordering, notes); this module supplies
every fact and every heading. A malformed analysis degrades the prose, never
the facts.

Design: "Report format".
"""
from __future__ import annotations

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

_SAFE = ("publish_to_repo", "reconcile_windows")
_ONLY = ("wsl_only", "windows_only", "additive_delete_requires_approval")
_CONFLICT = ("conflict", "plugin_pin_violation")
_PLUGIN = ("plugin_missing", "plugin_extra", "plugin_enabled_differs",
           "plugin_version_differs", "plugin_incompatible",
           "plugin_pin_violation")


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


def _by(items, classifications) -> list[dict]:
    return [i for i in items if i["classification"] in classifications]


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


def render_markdown(doc: dict, analysis: dict) -> str:
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

    for heading, selector in (
            ("Safe portable updates", _SAFE),
            ("Conflicts requiring judgment", _CONFLICT),
            ("WSL-only and Windows-only items", _ONLY),
            ("Protected Windows state", ("protected_overlay",)),
            ("Plugin differences", _PLUGIN)):
        add(f"## {heading}")
        add("")
        out.extend(_item_lines(_by(items, selector), notes))
        add("")

    add("## Portability warnings")
    add("")
    warnings = [i for i in items if "portability" in i.get("detail", "").lower()]
    out.extend([f"- `{i['id']}`: {i['detail']}" for i in warnings] or ["_None._"])
    add("")

    add("## Excluded and redacted")
    add("")
    add("Values are never recorded — only a pointer, a reason code, a type, "
        "and a truncated hash.")
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

    add("## Scan errors")
    add("")
    out.extend([f"- `{e['path']}`: {e['message']}" for e in doc["errors"]]
               or ["_None._"])
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

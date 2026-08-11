#!/usr/bin/env python3
"""The sanitized drift document: assembly, validation, and atomic emission.

This document is the only thing the model ever sees. Everything in it has
already passed the secret boundary in extract.py.

Design: "Deterministic scan" steps 6-8.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

import compare
import normalize as nz
import schema as sch

DRIFT_SCHEMA_VERSION = 1
SCANNER_VERSION = "1.0.0"

_SCHEMA_PATH = Path(__file__).resolve().parent / "schemas" / "drift-v1.json"


def make_run_id(now: datetime, entropy: str) -> str:
    return now.strftime("%Y-%m-%dT%H-%M-%SZ") + f"-{entropy}"


def layer_fingerprint(units, layer: str) -> str:
    """One value summarizing a whole layer; used for staleness checks."""
    parts = sorted(f"{u.unit_id}={u.fingerprint or '-'}"
                   for u in units if u.layer == layer)
    return nz.fingerprint("\n".join(parts) + "\n")


def build_document(manifest, items, errors, *, now: datetime, entropy: str,
                   units) -> dict:
    redactions: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for item in items:
        for redaction in item.redactions:
            key = (item.id, redaction.pointer)
            if key in seen:
                continue
            seen.add(key)
            redactions.append(redaction.as_dict())

    roots = {"wsl": str(manifest.roots.wsl_home), "repo": str(manifest.roots.repo)}
    if manifest.roots.windows_home:
        roots["windows"] = str(manifest.roots.windows_home)

    return {
        "drift_schema_version": DRIFT_SCHEMA_VERSION,
        "run_id": make_run_id(now, entropy),
        "generated_at": now.isoformat(),
        "scanner_version": SCANNER_VERSION,
        "manifest_version": manifest.schema_version,
        "roots": roots,
        "layer_fingerprints": {
            layer: layer_fingerprint(units, layer)
            for layer in ("wsl", "repo", "windows")
        },
        "counts": compare.counts(
            [i for i in items if i.classification != "unchanged"]),
        "items": [item.as_dict() for item in items
                  if item.classification != "unchanged"],
        "redactions": redactions,
        "errors": errors,
    }


def validate_document(doc: dict) -> list[str]:
    schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    return sch.validate(doc, schema)


def has_actionable(doc: dict) -> bool:
    return any(item["classification"] in compare.ACTIONABLE
               for item in doc.get("items", []))


def write_atomic(path: Path, text: str) -> None:
    """Write via a sibling temp file + os.replace, so readers never see a
    partial document and a failure leaves the previous file intact."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.tmp")
    try:
        with temp.open("w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()


def dump(doc: dict) -> str:
    return json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=False) + "\n"

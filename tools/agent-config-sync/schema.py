#!/usr/bin/env python3
"""Minimal JSON-Schema subset validator (stdlib only).

Supports exactly what the drift and analysis-response schemas need:
type, required, properties, items, enum, additionalProperties.

Error strings are "{path}: {message}". Most messages carry only a JSON path
and a type name, but two carry a data value verbatim: an enum mismatch
embeds the offending value, and an additionalProperties violation embeds the
offending key. Both are safe to surface as-is when the instance is trusted
(for example drift.validate_document, which validates our own scanner's
output -- an operator debugging a scanner bug wants to see the value).

They are NOT safe to surface as-is when the instance is untrusted, such as a
model response. A caller in that position must keep only the path and drop
the message half before the error reaches a user or a log; see
analyze.run(), which splits each error on its first ": " for exactly this
reason. This module does not redact on its own -- the sanitization boundary
belongs to the caller that knows whether its instance is trusted.

Design: "Deterministic scan" step 1; "Claude-first report generation".
"""
from __future__ import annotations

from typing import Any

TYPE_NAMES = {
    "object": dict,
    "array": list,
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "null": type(None),
}


class SchemaError(ValueError):
    """Raised when a schema document itself is malformed."""


def _type_name(value: Any) -> str:
    return type(value).__name__


def validate(instance: Any, schema: dict, *, path: str = "$") -> list[str]:
    """Return a list of human-readable errors; empty means valid."""
    errors: list[str] = []
    expected = schema.get("type")

    if expected is not None:
        if expected not in TYPE_NAMES:
            raise SchemaError(f"unknown type {expected!r} at {path}")
        # bool is a subclass of int in Python; reject it for integer/number.
        py_type = TYPE_NAMES[expected]
        ok = isinstance(instance, py_type)
        if expected in ("integer", "number") and isinstance(instance, bool):
            ok = False
        if not ok:
            return [f"{path}: expected {expected}, got {_type_name(instance)}"]

    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path}: {instance!r} is not one of {schema['enum']!r}")

    if isinstance(instance, dict):
        for key in schema.get("required", []):
            if key not in instance:
                errors.append(f"{path}: missing required property {key!r}")
        props = schema.get("properties", {})
        for key, sub in props.items():
            if key in instance:
                errors.extend(validate(instance[key], sub, path=f"{path}.{key}"))
        if schema.get("additionalProperties") is False:
            for key in instance:
                if key not in props:
                    errors.append(f"{path}: unexpected property {key!r}")

    if isinstance(instance, list) and "items" in schema:
        for index, item in enumerate(instance):
            errors.extend(validate(item, schema["items"], path=f"{path}[{index}]"))

    return errors

#!/usr/bin/env python3
"""Bounded headless Claude analyzer.

Claude supplies judgment; it never writes the report and never gets a mutation
tool. Invalid output raises, so the caller can keep the last valid report.

Design: "Claude-first report generation".
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import schema as sch

RESPONSE_SCHEMA_VERSION = 1
PROMPT_VERSION = "report-v1"

_SCHEMA_PATH = Path(__file__).resolve().parent / "schemas" / "response-v1.json"
_FENCE = re.compile(r"```(?:json)?\s*(?P<body>\{.*?\})\s*```", re.DOTALL)


class AnalysisError(RuntimeError):
    """The analyzer failed, timed out, or returned something unusable."""


def build_command(claude_bin: str, *, max_turns: int) -> list[str]:
    """Read-only, bounded, normal configuration (never --bare).

    --allowedTools is a prompt-SKIP list, not an allowlist: it does not
    restrict what exists. --disallowedTools is the real control -- it removes
    those tools from the model's context entirely. Both are kept on purpose;
    do not "simplify" by dropping the disallow list.

    Anything named in neither list fails closed: under the default permission
    mode (never overridden here) a tool needing approval aborts the --print
    run, since no interactive prompt is possible; that surfaces here as a
    non-zero exit, which run() turns into an AnalysisError, so no report is
    written. (Verified against the published CLI/headless/permission-modes
    docs, 2026-08-11. One residual: the abort-on-attempt rule is stated
    explicitly for shell/network tools and for org-connector/
    requiresUserInteraction MCP cases, but not spelled out by name for an
    ordinary locally-configured MCP tool.)
    """
    return [
        claude_bin,
        "--print",
        "--output-format", "json",
        "--max-turns", str(max_turns),
        "--allowedTools", "Read,Grep,Glob",
        "--disallowedTools", "Bash,Write,Edit,NotebookEdit,WebFetch,WebSearch",
    ]


def build_prompt(doc: dict, prompt_path: Path) -> str:
    template = Path(prompt_path).read_text(encoding="utf-8")
    return (template
            .replace("{SCHEMA}", _SCHEMA_PATH.read_text(encoding="utf-8"))
            .replace("{DRIFT}", json.dumps(doc, indent=2, sort_keys=True)))


def extract_json(stdout: str) -> dict:
    """Accept a bare object, a fenced block, or claude's --output-format json."""
    text = stdout.strip()
    candidates: list[str] = []

    if text.startswith("{"):
        candidates.append(text)
    fenced = _FENCE.search(text)
    if fenced:
        candidates.append(fenced.group("body"))

    for candidate in list(candidates):
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and "response_schema_version" in data:
            return data
        # claude --output-format json wraps the answer in an envelope.
        inner = data.get("result") if isinstance(data, dict) else None
        if isinstance(inner, str):
            try:
                nested = json.loads(inner)
            except json.JSONDecodeError:
                nested = None
            if isinstance(nested, dict):
                return nested
            fenced_inner = _FENCE.search(inner)
            if fenced_inner:
                try:
                    return json.loads(fenced_inner.group("body"))
                except json.JSONDecodeError:
                    pass

    raise AnalysisError(
        "the analyzer returned no JSON object matching the response schema "
        f"(stdout was {len(stdout)} characters)")


def validate_analysis(obj: dict) -> list[str]:
    schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    return sch.validate(obj, schema)


def run(doc: dict, *, claude_bin: str, prompt_path: Path, timeout_s: int,
        max_turns: int) -> dict:
    prompt = build_prompt(doc, Path(prompt_path))
    argv = build_command(claude_bin, max_turns=max_turns)
    try:
        proc = subprocess.run(argv, input=prompt, capture_output=True,
                              text=True, timeout=timeout_s)
    except subprocess.TimeoutExpired:
        raise AnalysisError(f"analyzer timed out after {timeout_s}s") from None
    except OSError as exc:
        raise AnalysisError(
            f"could not run {claude_bin}: {type(exc).__name__}") from None

    if proc.returncode != 0:
        raise AnalysisError(f"analyzer failed with exit {proc.returncode}")

    analysis = extract_json(proc.stdout)
    problems = validate_analysis(analysis)
    if problems:
        # schema.validate() error strings are "{path}: {message}", and the
        # message half can embed attacker-controlled content verbatim (an
        # enum mismatch reports the offending value; additionalProperties
        # reports the offending key). Keep only the path -- never the value.
        paths = [problem.split(":", 1)[0] for problem in problems[:5]]
        raise AnalysisError("analyzer response failed the schema at: "
                            + "; ".join(paths))
    return analysis

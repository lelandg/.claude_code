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


def _is_answer(data: object) -> dict | None:
    """A parsed JSON value is the answer itself if it's a dict carrying our
    version key -- the one field every valid response must have."""
    if isinstance(data, dict) and "response_schema_version" in data:
        return data
    return None


def _find_in_text(text: str) -> dict | None:
    """A bare object or a fenced ```json block in already-decoded text (no
    further envelope wrapping this text)."""
    text = text.strip()
    if text.startswith("{"):
        try:
            found = _is_answer(json.loads(text))
        except json.JSONDecodeError:
            found = None
        if found is not None:
            return found
    fenced = _FENCE.search(text)
    if fenced:
        try:
            return _is_answer(json.loads(fenced.group("body")))
        except json.JSONDecodeError:
            return None
    return None


def extract_json(stdout: str) -> dict:
    """Accept a bare object, a fenced block, or claude's --output-format json
    envelope -- a single result object, or (Claude Code >= 2.1.228) a
    top-level array of stream events whose terminal type == "result" event
    carries the answer as a JSON-encoded string in its own "result" field.

    The envelope is parsed as JSON *before* any fence matching, because a
    fence nested inside a JSON string is preceded by the literal two-
    character escape "\\n" in the raw text -- not whitespace -- so the fence
    regex cannot find it there. Only after `json.loads` decodes that string
    does its leading "\\n" become a real newline the regex can match.
    """
    text = stdout.strip()

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = None

    if isinstance(parsed, dict):
        found = _is_answer(parsed)
        if found is not None:
            return found
        inner = parsed.get("result")
        if isinstance(inner, str):
            found = _find_in_text(inner)
            if found is not None:
                return found
    elif isinstance(parsed, list):
        for event in parsed:
            if isinstance(event, dict) and event.get("type") == "result":
                inner = event.get("result")
                if isinstance(inner, str):
                    found = _find_in_text(inner)
                    if found is not None:
                        return found
                break  # exactly one terminal result event; stop scanning

    # No envelope recognized, or nothing usable inside it: fall back to
    # scanning stdout itself, in case the model printed the answer directly.
    found = _find_in_text(text)
    if found is not None:
        return found

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

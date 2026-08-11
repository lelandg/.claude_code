# Agent Config Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deterministic scanner, Claude-first report generator, and reviewed-merge workflow that keeps WSL-authoritative agent configuration aligned with this repository and a Windows target, without ever applying a change unattended or letting a secret leave the machine.

**Architecture:** A stdlib-only Python toolchain in `tools/agent-config-sync/` reads an ownership manifest (`config/agent-sync.toml`), extracts only allowlisted files and fields from three layers (WSL live config, this repository, Windows home), normalizes and fingerprints them, and emits a sanitized JSON drift document. When — and only when — drift exists, a bounded `claude -p` wrapper turns that document into a structured analysis, which a deterministic renderer converts into a Markdown report. A separate merge tool applies only explicitly selected report items, after re-verifying fingerprints and taking backups. Two Claude skills (`agent-config-report`, `agent-config-merge`) are the human-facing entry points.

**Tech Stack:** Python 3.12 standard library only (`tomllib`, `json`, `hashlib`, `fcntl`, `argparse`, `subprocess`, `dataclasses`), pytest 9.x for tests, `claude -p` as the headless analyzer, Bash for the cron wrapper, Markdown for skills.

**Source design:** `Docs/plans/2026-08-08-wsl-authoritative-agent-config-sync-design.md` (approved). Every ownership, secret-boundary, and acceptance rule in this plan traces to that document.

## Global Constraints

These apply to **every** task. They are not repeated per task.

- **Python 3.12, standard library only.** No third-party runtime dependencies. `pytest` is a test-time dependency only. This matches `claude/skills/version-manager/version_tool.py` and `claude/skills/repo-doctor/audit.py`.
- **Import convention:** modules in `tools/agent-config-sync/` import each other by bare module name (`import normalize`). Running `python3 tools/agent-config-sync/scan.py` puts that directory on `sys.path[0]`. Tests do `sys.path.insert(0, str(Path(__file__).resolve().parents[1]))` before importing — copy this from `claude/skills/version-manager/tests/test_version_tool.py`.
- **Every module starts with `from __future__ import annotations`** and a module docstring naming the design section it implements.
- **Never `cd`.** Absolute paths always; `git -C <abs-path> …` for git.
- **Tests never read or write the live user profile.** Every test builds a fixture tree under pytest's `tmp_path`. A test that references `/home/leland`, `~`, `Path.home()`, or `/mnt/c/Users` outside of a *string literal being normalized* is a plan violation.
- **Secret boundary (design §Secret and state boundary):** the tools use allowlist extraction, never ingest-then-redact. No secret value may appear in a drift document, prompt, report, log line, test snapshot, exception message, or commit. Values that are excluded are represented by *path, type, and hash* only.
- **Report-only by default.** Nothing in Tasks 1–10 may write to `/home/leland` or `/mnt/c/Users/aboog`. Only Task 11's merge tool writes to targets, and only with an explicit `--apply` flag plus selected item IDs.
- **Atomic writes only.** Every output file is written to a temporary file in the same directory, `fsync`ed, then `os.replace`d into position.
- **Exit codes (fixed contract, used by the cron wrapper):** `0` = success/no drift, `10` = drift reported, `20` = scan failure, `21` = lock held by another run, `30` = model/analysis failure. Never conflate ordinary drift with an infrastructure error.
- **Versions:** `SCANNER_VERSION = "1.0.0"`, `DRIFT_SCHEMA_VERSION = 1`, `RESPONSE_SCHEMA_VERSION = 1`, `REPORT_TEMPLATE_VERSION = 1`, `MANIFEST_SCHEMA_VERSION = 1`. Bump only when the shape changes.
- **No wall-clock or randomness inside pure functions.** Timestamps and entropy are passed in as parameters so tests are deterministic. Only CLI entry points call `datetime.now()`.
- **Commit after every task**, with the tests passing. Conventional Commits style, matching this repo's history (`feat:`, `fix:`, `docs:`, `test:`).

### Ownership policy vocabulary (design §Ownership and merge policy)

Exactly four policy values, used verbatim as strings in the manifest and in code:

| Policy | Meaning |
|---|---|
| `portable_authoritative` | WSL intent is the desired value everywhere. |
| `portable_additive` | WSL additions/updates are candidates; **deletions require explicit approval**. |
| `platform_overlay` | Windows owns the value. Preserved, reported as protected, never proposed for change. |
| `excluded` | Not collected, not compared, not reported beyond an exclusion reason code. |

### Classification vocabulary (design §Authority model)

Exactly these classification strings. Task 4 implements the truth table; every later task consumes these names.

| Classification | Severity | Meaning |
|---|---|---|
| `unchanged` | `info` | All three layers agree. Not emitted into the report body. |
| `publish_to_repo` | `review` | WSL intent needs publishing into the repository baseline. |
| `reconcile_windows` | `review` | Repository baseline differs from Windows; Windows may need reconciliation. |
| `conflict` | `conflict` | WSL and Windows moved apart relative to the baseline, or there is no baseline to arbitrate. No winner is chosen. |
| `wsl_only` | `review` | Present in WSL only; a new portable item. |
| `windows_only` | `review` | Present on Windows only; ownership undeclared. |
| `protected_overlay` | `info` | Windows-owned state. Reported, never actionable. |
| `additive_delete_requires_approval` | `review` | A `portable_additive` item disappeared from WSL. Never deleted unattended. |
| `plugin_missing` | `review` | Desired plugin absent from a native manager. |
| `plugin_extra` | `info` | Native plugin not in the portable record. |
| `plugin_enabled_differs` | `review` | Enabled/disabled state differs. |
| `plugin_version_differs` | `info` or `review` | Version differs with no pin. `info` when the native side is newer (preserved); `review` when it is older. |
| `plugin_pin_violation` | `conflict` | Installed version violates an explicit pin. |
| `plugin_incompatible` | `review` | Native manager or platform cannot satisfy the desired state. |
| `error` | `error` | Read/parse failure. Carries a location, never file content. |

**One documented refinement to the design:** the design says "WSL and Windows both differ from the repository in the same portable field: report a conflict." When WSL and Windows differ from the baseline but **agree with each other**, there is no winner to choose — the baseline is simply stale — so this plan classifies that case as `publish_to_repo` (severity `review`), not `conflict`. Disagreement between WSL and Windows is still always a `conflict`. This preserves the design's rule ("do not choose a winner automatically") because no arbitration occurs.

---

## File Structure

**New top-level directories.** `tools/` is repository-owned tooling, deliberately *outside* `claude/` and `config/`, which are sanitized mirrors of the live machine config.

```text
config/
└── agent-sync.toml                     # ownership manifest (Task 1)

tools/agent-config-sync/
├── schema.py                           # minimal JSON-Schema subset validator (Task 1)
├── manifest.py                         # manifest load + validation (Task 1)
├── normalize.py                        # line endings, JSON/TOML canonicalization, path tokens, fingerprints (Task 2)
├── extract.py                          # allowlist extraction + secret boundary (Task 3)
├── compare.py                          # three-way comparison + classification truth table (Task 4)
├── plugins.py                          # plugin identity/enabled/version/pin classification (Task 5)
├── drift.py                            # drift document assembly + atomic write (Task 6)
├── scan.py                             # CLI: deterministic scan, process lock, exit codes (Task 6)
├── render.py                           # CLI: validate analysis + render Markdown (Tasks 7, 8)
├── analyze.py                          # bounded `claude -p` wrapper (Task 8)
├── merge.py                            # reviewed merge planning, backup, apply, restore (Task 11)
├── schemas/
│   ├── drift-v1.json                   # (Task 1)
│   └── response-v1.json                # (Task 8)
├── prompts/
│   └── report-v1.md                    # analyzer prompt, versioned (Task 8)
├── bin/
│   └── agent-config-sync.sh            # cron wrapper (Task 9)
└── tests/
    ├── conftest.py                     # fixture-tree builders (Task 1)
    ├── test_manifest.py                # (Task 1)
    ├── test_normalize.py               # (Task 2)
    ├── test_extract.py                 # (Task 3)
    ├── test_compare.py                 # (Task 4)
    ├── test_plugins.py                 # (Task 5)
    ├── test_scan.py                    # (Task 6)
    ├── test_render.py                  # (Task 7)
    ├── test_analyze.py                 # (Task 8)
    ├── test_wrapper.py                 # (Task 9)
    ├── test_merge.py                   # (Task 11)
    └── golden/
        └── report-basic.md             # (Task 7)

claude/skills/
├── agent-config-report/SKILL.md        # (Task 10)
└── agent-config-merge/SKILL.md         # (Task 12)

Docs/
└── agent-config-sync.md                # operator documentation + cron install (Task 9)
```

Responsibility boundaries: `normalize.py` knows nothing about manifests; `extract.py` knows nothing about comparison; `compare.py` is pure functions over fingerprints; `scan.py`/`render.py`/`merge.py` are the only modules that touch `argparse`, the clock, or process state. This is what makes the truth table testable in isolation.

---

## Task 1: Manifest, schema validator, and drift schema

**Files:**
- Create: `config/agent-sync.toml`
- Create: `tools/agent-config-sync/schema.py`
- Create: `tools/agent-config-sync/manifest.py`
- Create: `tools/agent-config-sync/schemas/drift-v1.json`
- Create: `tools/agent-config-sync/tests/conftest.py`
- Test: `tools/agent-config-sync/tests/test_manifest.py`

**Interfaces:**
- Consumes: nothing (first task).
- Produces:
  - `schema.py`: `validate(instance: object, schema: dict, *, path: str = "$") -> list[str]` returning human-readable error strings (empty list = valid). `class SchemaError(ValueError)`.
  - `manifest.py`: dataclasses `Roots(wsl_home: Path, repo: Path, windows_home: Path | None)`, `Entry(id: str, policy: str, kind: str, wsl: str | None, repo: str | None, windows: str | None, globs: tuple[str, ...], fields: dict[str, str])`, `SecretPolicy(deny_key_patterns: tuple[str, ...], deny_path_globs: tuple[str, ...])`, `Manifest(schema_version: int, roots: Roots, state_dir: Path, entries: tuple[Entry, ...], secrets: SecretPolicy)`; functions `load_manifest(path: Path, *, root_overrides: dict[str, str] | None = None) -> Manifest`, `Manifest.entry(entry_id: str) -> Entry`; `class ManifestError(ValueError)`.
  - Constants in `manifest.py`: `MANIFEST_SCHEMA_VERSION = 1`, `POLICIES = ("portable_authoritative", "portable_additive", "platform_overlay", "excluded")`, `KINDS = ("text", "tree", "json", "toml", "plugins")`.
  - `tests/conftest.py`: pytest fixture `fixture_roots(tmp_path)` returning a `SimpleNamespace` with `.wsl`, `.repo`, `.windows`, `.state` directories created, plus helper `write(root: Path, rel: str, content: str) -> Path`.

- [ ] **Step 1: Write the failing tests for the schema validator**

Create `tools/agent-config-sync/tests/test_manifest.py`:

```python
"""Tests for the manifest loader and the minimal JSON-Schema validator.

Design: Docs/plans/2026-08-08-wsl-authoritative-agent-config-sync-design.md
sections "Ownership and merge policy" and "Deterministic scan" step 1.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import manifest as mf  # noqa: E402
import schema as sch  # noqa: E402


# --------------------------------------------------------------------------
# schema.py
# --------------------------------------------------------------------------

PERSON = {
    "type": "object",
    "required": ["name", "age"],
    "properties": {
        "name": {"type": "string"},
        "age": {"type": "integer"},
        "role": {"type": "string", "enum": ["admin", "user"]},
        "tags": {"type": "array", "items": {"type": "string"}},
    },
}


def test_schema_accepts_valid_instance():
    assert sch.validate({"name": "a", "age": 3, "role": "admin"}, PERSON) == []


def test_schema_reports_missing_required_field():
    errors = sch.validate({"name": "a"}, PERSON)
    assert errors == ["$: missing required property 'age'"]


def test_schema_reports_wrong_type_with_path():
    errors = sch.validate({"name": "a", "age": "three"}, PERSON)
    assert errors == ["$.age: expected integer, got str"]


def test_schema_reports_bad_enum_value():
    errors = sch.validate({"name": "a", "age": 1, "role": "root"}, PERSON)
    assert errors == ["$.role: 'root' is not one of ['admin', 'user']"]


def test_schema_validates_array_items_by_index():
    errors = sch.validate({"name": "a", "age": 1, "tags": ["x", 2]}, PERSON)
    assert errors == ["$.tags[1]: expected string, got int"]


def test_schema_does_not_leak_values_of_unknown_long_strings():
    # Error text quotes only enum mismatches, never arbitrary string values.
    errors = sch.validate({"name": 1234567890, "age": 1}, PERSON)
    assert errors == ["$.name: expected string, got int"]
    assert "1234567890" not in errors[0]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest tools/agent-config-sync/tests/test_manifest.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'schema'`

- [ ] **Step 3: Implement `schema.py`**

Create `tools/agent-config-sync/schema.py`:

```python
#!/usr/bin/env python3
"""Minimal JSON-Schema subset validator (stdlib only).

Supports exactly what the drift and analysis-response schemas need:
type, required, properties, items, enum, additionalProperties.
Error strings carry a JSON path and a type name -- never a data value,
except for enum mismatches where the value is by definition a known token.

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
```

- [ ] **Step 4: Run the schema tests to verify they pass**

Run: `python3 -m pytest tools/agent-config-sync/tests/test_manifest.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Write the failing tests for the manifest loader**

Append to `tools/agent-config-sync/tests/test_manifest.py`:

```python
# --------------------------------------------------------------------------
# manifest.py
# --------------------------------------------------------------------------

MINIMAL = """
schema_version = 1

[roots]
wsl_home = "/fixture/wsl"
repo = "/fixture/repo"
windows_home = "/fixture/win"

[state]
dir = "/fixture/state"

[secrets]
deny_key_patterns = ["(?i)token"]
deny_path_globs = [".credentials.json"]

[[entries]]
id = "agents-md"
policy = "portable_authoritative"
kind = "text"
wsl = ".config/agents/AGENTS.md"
repo = "config/agents/AGENTS.md"
windows = ".config/agents/AGENTS.md"

[[entries]]
id = "claude-settings"
policy = "portable_authoritative"
kind = "json"
wsl = ".claude/settings.json"
repo = "claude/settings.json"
windows = ".claude/settings.json"

[entries.fields]
"model" = "portable_authoritative"
"statusLine.command" = "platform_overlay"
"""


def write_manifest(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "agent-sync.toml"
    path.write_text(text, encoding="utf-8")
    return path


def test_load_manifest_parses_roots_and_entries(tmp_path: Path):
    m = mf.load_manifest(write_manifest(tmp_path, MINIMAL))
    assert m.schema_version == 1
    assert m.roots.wsl_home == Path("/fixture/wsl")
    assert m.roots.windows_home == Path("/fixture/win")
    assert m.state_dir == Path("/fixture/state")
    assert [e.id for e in m.entries] == ["agents-md", "claude-settings"]


def test_load_manifest_parses_field_level_ownership(tmp_path: Path):
    m = mf.load_manifest(write_manifest(tmp_path, MINIMAL))
    entry = m.entry("claude-settings")
    assert entry.fields["statusLine.command"] == "platform_overlay"
    assert entry.fields["model"] == "portable_authoritative"


def test_root_overrides_replace_declared_roots(tmp_path: Path):
    m = mf.load_manifest(
        write_manifest(tmp_path, MINIMAL),
        root_overrides={"wsl_home": str(tmp_path / "alt")},
    )
    assert m.roots.wsl_home == tmp_path / "alt"


def test_unknown_policy_is_rejected(tmp_path: Path):
    bad = MINIMAL.replace('policy = "portable_authoritative"\nkind = "text"',
                          'policy = "whatever"\nkind = "text"', 1)
    with pytest.raises(mf.ManifestError) as excinfo:
        mf.load_manifest(write_manifest(tmp_path, bad))
    assert "whatever" in str(excinfo.value)


def test_duplicate_entry_id_is_rejected(tmp_path: Path):
    dup = MINIMAL + """
[[entries]]
id = "agents-md"
policy = "portable_additive"
kind = "text"
wsl = "x"
"""
    with pytest.raises(mf.ManifestError) as excinfo:
        mf.load_manifest(write_manifest(tmp_path, dup))
    assert "duplicate" in str(excinfo.value).lower()


def test_unknown_field_level_policy_is_rejected(tmp_path: Path):
    bad = MINIMAL.replace('"statusLine.command" = "platform_overlay"',
                          '"statusLine.command" = "platform_overlaid"', 1)
    with pytest.raises(mf.ManifestError) as excinfo:
        mf.load_manifest(write_manifest(tmp_path, bad))
    message = str(excinfo.value)
    assert "statusLine.command" in message
    assert "platform_overlaid" in message


def test_missing_state_dir_is_rejected(tmp_path: Path):
    no_state = MINIMAL.replace('[state]\ndir = "/fixture/state"\n', "")
    with pytest.raises(mf.ManifestError) as excinfo:
        mf.load_manifest(write_manifest(tmp_path, no_state))
    assert "state.dir" in str(excinfo.value)


def test_future_schema_version_is_rejected(tmp_path: Path):
    future = MINIMAL.replace("schema_version = 1", "schema_version = 99", 1)
    with pytest.raises(mf.ManifestError):
        mf.load_manifest(write_manifest(tmp_path, future))


def test_malformed_toml_error_names_the_file_not_its_contents(tmp_path: Path):
    path = write_manifest(tmp_path, 'schema_version = 1\n[roots\nsecret = "hunter2"\n')
    with pytest.raises(mf.ManifestError) as excinfo:
        mf.load_manifest(path)
    message = str(excinfo.value)
    assert "agent-sync.toml" in message
    assert "hunter2" not in message


def test_windows_home_may_be_absent(tmp_path: Path):
    no_win = MINIMAL.replace('windows_home = "/fixture/win"\n', "")
    m = mf.load_manifest(write_manifest(tmp_path, no_win))
    assert m.roots.windows_home is None


def test_real_repository_manifest_loads(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[3]
    m = mf.load_manifest(repo_root / "config" / "agent-sync.toml")
    assert m.schema_version == mf.MANIFEST_SCHEMA_VERSION
    ids = {e.id for e in m.entries}
    assert {"agents-md", "claude-md", "claude-instructions",
            "claude-settings", "claude-plugins", "claude-mcp"} <= ids
```

- [ ] **Step 6: Run the manifest tests to verify they fail**

Run: `python3 -m pytest tools/agent-config-sync/tests/test_manifest.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'manifest'`

- [ ] **Step 7: Implement `manifest.py`**

Create `tools/agent-config-sync/manifest.py`:

```python
#!/usr/bin/env python3
"""Ownership manifest: the single place roots, paths, and policies are declared.

Path literals live here and in config/agent-sync.toml -- never spread through
the implementation (design section "Paths").
"""
from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

MANIFEST_SCHEMA_VERSION = 1

POLICIES = (
    "portable_authoritative",
    "portable_additive",
    "platform_overlay",
    "excluded",
)
KINDS = ("text", "tree", "json", "toml", "plugins")


class ManifestError(ValueError):
    """Manifest is missing, malformed, or declares something unsupported."""


@dataclass(frozen=True)
class Roots:
    wsl_home: Path
    repo: Path
    windows_home: Path | None = None

    def for_layer(self, layer: str) -> Path | None:
        return {"wsl": self.wsl_home, "repo": self.repo,
                "windows": self.windows_home}[layer]


@dataclass(frozen=True)
class Entry:
    id: str
    policy: str
    kind: str
    wsl: str | None = None
    repo: str | None = None
    windows: str | None = None
    globs: tuple[str, ...] = ()
    fields: dict[str, str] = field(default_factory=dict)

    def rel_for_layer(self, layer: str) -> str | None:
        return {"wsl": self.wsl, "repo": self.repo, "windows": self.windows}[layer]


@dataclass(frozen=True)
class SecretPolicy:
    deny_key_patterns: tuple[str, ...] = ()
    deny_path_globs: tuple[str, ...] = ()


@dataclass(frozen=True)
class Manifest:
    schema_version: int
    roots: Roots
    state_dir: Path
    entries: tuple[Entry, ...]
    secrets: SecretPolicy

    def entry(self, entry_id: str) -> Entry:
        for candidate in self.entries:
            if candidate.id == entry_id:
                return candidate
        raise ManifestError(f"no entry with id {entry_id!r}")


def _expand(value: str) -> Path:
    return Path(value).expanduser()


def load_manifest(path: Path,
                  *,
                  root_overrides: dict[str, str] | None = None) -> Manifest:
    """Load and validate the manifest. Errors name the file, never its bytes."""
    path = Path(path)
    try:
        with path.open("rb") as handle:
            data = tomllib.load(handle)
    except FileNotFoundError as exc:
        raise ManifestError(f"{path.name}: manifest not found at {path}") from exc
    except tomllib.TOMLDecodeError as exc:
        # TOMLDecodeError has no .lineno; the location lives in str(exc).
        # Extract ONLY line/column and rebuild the message, so no source
        # fragment can ride along. (Review ruling, 2026-08-11.)
        match = re.search(r"at line (\d+), column (\d+)", str(exc))
        where = (f" at line {match.group(1)}, column {match.group(2)}"
                 if match else "")
        raise ManifestError(f"{path.name}: invalid TOML{where}") from None

    version = data.get("schema_version")
    if version != MANIFEST_SCHEMA_VERSION:
        raise ManifestError(
            f"{path.name}: schema_version {version!r}; "
            f"this tool supports {MANIFEST_SCHEMA_VERSION}")

    raw_roots = dict(data.get("roots", {}))
    raw_roots.update(root_overrides or {})
    for required in ("wsl_home", "repo"):
        if not raw_roots.get(required):
            raise ManifestError(f"{path.name}: roots.{required} is required")
    windows = raw_roots.get("windows_home")
    roots = Roots(
        wsl_home=_expand(raw_roots["wsl_home"]),
        repo=_expand(raw_roots["repo"]),
        windows_home=_expand(windows) if windows else None,
    )

    # [state].dir is required, not defaulted: a default here would duplicate
    # the literal that config/agent-sync.toml already declares, and the two
    # could drift. (Review ruling, 2026-08-10.)
    raw_state = data.get("state", {})
    if not raw_state.get("dir"):
        raise ManifestError(f"{path.name}: state.dir is required")
    state_dir = _expand(raw_state["dir"])

    raw_secrets = data.get("secrets", {})
    secrets = SecretPolicy(
        deny_key_patterns=tuple(raw_secrets.get("deny_key_patterns", [])),
        deny_path_globs=tuple(raw_secrets.get("deny_path_globs", [])),
    )

    entries: list[Entry] = []
    seen: set[str] = set()
    for raw in data.get("entries", []):
        entry_id = raw.get("id")
        if not entry_id:
            raise ManifestError(f"{path.name}: an entry is missing 'id'")
        if entry_id in seen:
            raise ManifestError(f"{path.name}: duplicate entry id {entry_id!r}")
        seen.add(entry_id)
        policy = raw.get("policy")
        if policy not in POLICIES:
            raise ManifestError(
                f"{path.name}: entry {entry_id!r} has unknown policy {policy!r}; "
                f"expected one of {list(POLICIES)}")
        kind = raw.get("kind")
        if kind not in KINDS:
            raise ManifestError(
                f"{path.name}: entry {entry_id!r} has unknown kind {kind!r}; "
                f"expected one of {list(KINDS)}")
        # Field-level policies get the same check as the entry-level one.
        # platform_overlay is what protects Windows-owned values; a typo that
        # loaded silently would downgrade a protected field to portable.
        # (Review ruling, 2026-08-10.)
        raw_fields = dict(raw.get("fields", {}))
        for pointer, field_policy in raw_fields.items():
            if field_policy not in POLICIES:
                raise ManifestError(
                    f"{path.name}: entry {entry_id!r} field {pointer!r} has "
                    f"unknown policy {field_policy!r}; "
                    f"expected one of {list(POLICIES)}")
        entries.append(Entry(
            id=entry_id,
            policy=policy,
            kind=kind,
            wsl=raw.get("wsl"),
            repo=raw.get("repo"),
            windows=raw.get("windows"),
            globs=tuple(raw.get("globs", [])),
            fields=raw_fields,
        ))

    if not entries:
        raise ManifestError(f"{path.name}: no [[entries]] declared")

    return Manifest(
        schema_version=version,
        roots=roots,
        state_dir=state_dir,
        entries=tuple(entries),
        secrets=secrets,
    )
```

- [ ] **Step 8: Write the real repository manifest**

Create `config/agent-sync.toml`. Paths trace to design §Paths and the policy table in §Ownership and merge policy.

```toml
# Ownership manifest for tools/agent-config-sync.
#
# WSL is the operational authority for portable intent; this repository is the
# sanitized record; Windows is a derived target with a protected overlay.
# Design: Docs/plans/2026-08-08-wsl-authoritative-agent-config-sync-design.md
#
# Policies: portable_authoritative | portable_additive | platform_overlay | excluded

schema_version = 1

[roots]
wsl_home = "/home/leland"
repo = "/mnt/d/Documents/Code/GitHub/.claude_code"
windows_home = "/mnt/c/Users/aboog"

[state]
dir = "~/.local/state/agent-config-sync"

[secrets]
# Keys whose VALUES are never collected. Matched case-insensitively against
# each JSON/TOML key on the path to a scalar.
deny_key_patterns = [
  "(?i)token",
  "(?i)secret",
  "(?i)password",
  "(?i)passwd",
  "(?i)api[_-]?key",
  "(?i)access[_-]?key",
  "(?i)credential",
  "(?i)authorization",
  "(?i)bearer",
  "(?i)private[_-]?key",
  "(?i)session[_-]?id",
]
# Paths never read at all, relative to any layer root.
deny_path_globs = [
  "**/.credentials.json",
  "**/history.jsonl",
  "**/*.sqlite",
  "**/*.db",
  "**/.env",
  "**/.env.*",
  "**/projects/**",
  "**/sessions/**",
  "**/session-env/**",
  "**/shell-snapshots/**",
  "**/file-history/**",
  "**/todos/**",
  "**/tasks/**",
  "**/statsig/**",
  "**/telemetry/**",
  "**/downloads/**",
  "**/plugins/cache/**",
  "**/security/**",
  "**/*.log",
]

# ---------------------------------------------------------------------------
# Portable authoritative: WSL intent is the desired value.
# ---------------------------------------------------------------------------

[[entries]]
id = "agents-md"
policy = "portable_authoritative"
kind = "text"
wsl = ".config/agents/AGENTS.md"
repo = "config/agents/AGENTS.md"
windows = ".config/agents/AGENTS.md"

[[entries]]
id = "claude-md"
policy = "portable_authoritative"
kind = "text"
wsl = ".claude/CLAUDE.md"
repo = "claude/CLAUDE.md"
windows = ".claude/CLAUDE.md"

[[entries]]
id = "claude-instructions"
policy = "portable_authoritative"
kind = "tree"
wsl = ".claude/instructions"
repo = "claude/instructions"
windows = ".claude/instructions"
globs = ["**/*.md"]

[[entries]]
id = "claude-agents"
policy = "portable_authoritative"
kind = "tree"
wsl = ".claude/agents"
repo = "claude/agents"
windows = ".claude/agents"
globs = ["**/*.md"]

# ---------------------------------------------------------------------------
# Portable additive: additions/updates are candidates; deletions need approval.
# ---------------------------------------------------------------------------

[[entries]]
id = "claude-skills"
policy = "portable_additive"
kind = "tree"
wsl = ".claude/skills"
repo = "claude/skills"
windows = ".claude/skills"
globs = ["**/*.md", "**/*.py", "**/*.sh", "**/*.json", "**/*.toml"]

[[entries]]
id = "claude-commands"
policy = "portable_additive"
kind = "tree"
wsl = ".claude/commands"
repo = "claude/commands"
windows = ".claude/commands"
globs = ["**/*.md"]

[[entries]]
id = "claude-tools"
policy = "portable_additive"
kind = "tree"
wsl = ".claude/tools"
repo = "claude/tools"
windows = ".claude/tools"
globs = ["**/*.py", "**/*.ts", "**/*.sh"]

[[entries]]
id = "codex-instructions"
policy = "portable_additive"
kind = "tree"
wsl = ".codex"
repo = "codex"
windows = ".codex"
globs = ["**/*.md"]

[[entries]]
id = "copilot-instructions"
policy = "portable_additive"
kind = "tree"
wsl = ".copilot"
repo = "copilot"
windows = ".copilot"
globs = ["**/*.md"]

[[entries]]
id = "gemini-instructions"
policy = "portable_additive"
kind = "tree"
wsl = ".gemini"
repo = "gemini"
windows = ".gemini"
globs = ["**/*.md"]

[[entries]]
id = "pi-instructions"
policy = "portable_additive"
kind = "tree"
wsl = ".pi"
repo = "pi"
windows = ".pi"
globs = ["**/*.md"]

[[entries]]
id = "agents-dir"
policy = "portable_additive"
kind = "tree"
wsl = ".agents"
repo = "agents"
windows = ".agents"
globs = ["**/*.md"]

# ---------------------------------------------------------------------------
# Settings: semantic field-level merge.
# ---------------------------------------------------------------------------

[[entries]]
id = "claude-settings"
policy = "portable_authoritative"
kind = "json"
wsl = ".claude/settings.json"
repo = "claude/settings.json"
windows = ".claude/settings.json"

[entries.fields]
"model" = "portable_authoritative"
"outputStyle" = "portable_authoritative"
"permissions" = "portable_authoritative"
"hooks" = "portable_authoritative"
"env" = "portable_authoritative"
"statusLine.command" = "platform_overlay"
"awsAuthRefresh" = "excluded"
"forceLoginMethod" = "platform_overlay"

[[entries]]
id = "codex-config"
policy = "portable_authoritative"
kind = "toml"
wsl = ".codex/config.toml"
repo = "codex/config.toml"
windows = ".codex/config.toml"

[entries.fields]
"model" = "portable_authoritative"
"model_reasoning_effort" = "portable_authoritative"
"projects" = "platform_overlay"
"desktop" = "platform_overlay"
"windows" = "platform_overlay"
"shell" = "platform_overlay"

[[entries]]
id = "claude-mcp"
policy = "portable_authoritative"
kind = "json"
wsl = ".claude/mcp.json"
repo = "claude/mcp.json"
windows = ".claude/mcp.json"

[entries.fields]
"mcpServers.*.command" = "platform_overlay"
"mcpServers.*.args" = "portable_authoritative"
"mcpServers.*.env" = "excluded"

# ---------------------------------------------------------------------------
# Plugins: identities reconciled through native managers, never copied.
#
# The path below is a BASE directory, not a file. plugins.py reads two
# well-known files under it (verified against the live machine 2026-08-10):
#   <base>/settings.json                  -> enabledPlugins {"name@market": bool}
#                                            extraKnownMarketplaces
#   <base>/plugins/installed_plugins.json -> {"plugins": {"name@market": [
#                                              {"scope","installPath",
#                                               "version","installedAt"}]}}
# installed_plugins.json is native runtime state -- gitignored, never committed,
# and present only in the wsl/windows layers. The repo layer therefore supplies
# desired identity + enabled state only, which is exactly the design's rule that
# plugin code is never copied across the boundary.
# ---------------------------------------------------------------------------

[[entries]]
id = "claude-plugins"
policy = "portable_authoritative"
kind = "plugins"
wsl = ".claude"
repo = "claude"
windows = ".claude"

# ---------------------------------------------------------------------------
# Explicitly excluded: never collected (belt-and-braces alongside [secrets]).
# ---------------------------------------------------------------------------

[[entries]]
id = "claude-local-state"
policy = "excluded"
kind = "tree"
wsl = ".claude"
globs = [".claude.json", "my-projects.yaml", "policy-limits.json"]
```

- [ ] **Step 9: Write `tests/conftest.py`**

Create `tools/agent-config-sync/tests/conftest.py`:

```python
"""Fixture-tree builders. No test may touch a live user profile."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def write(root: Path, rel: str, content: str) -> Path:
    """Write content to root/rel, creating parents. Returns the path."""
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


@pytest.fixture
def fixture_roots(tmp_path: Path) -> SimpleNamespace:
    """Three empty layer roots plus a state dir, all under tmp_path."""
    layers = SimpleNamespace(
        wsl=tmp_path / "wsl",
        repo=tmp_path / "repo",
        windows=tmp_path / "windows",
        state=tmp_path / "state",
        write=write,
    )
    for path in (layers.wsl, layers.repo, layers.windows, layers.state):
        path.mkdir(parents=True)
    return layers
```

- [ ] **Step 10: Write `schemas/drift-v1.json`**

Create `tools/agent-config-sync/schemas/drift-v1.json`:

```json
{
  "type": "object",
  "required": ["drift_schema_version", "run_id", "generated_at",
               "scanner_version", "manifest_version", "roots",
               "counts", "items", "redactions", "errors"],
  "properties": {
    "drift_schema_version": {"type": "integer"},
    "run_id": {"type": "string"},
    "generated_at": {"type": "string"},
    "scanner_version": {"type": "string"},
    "manifest_version": {"type": "integer"},
    "roots": {
      "type": "object",
      "properties": {
        "wsl": {"type": "string"},
        "repo": {"type": "string"},
        "windows": {"type": "string"}
      }
    },
    "layer_fingerprints": {
      "type": "object",
      "properties": {
        "wsl": {"type": "string"},
        "repo": {"type": "string"},
        "windows": {"type": "string"}
      }
    },
    "counts": {"type": "object"},
    "items": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["id", "entry_id", "kind", "classification",
                     "severity", "path", "detail"],
        "properties": {
          "id": {"type": "string"},
          "entry_id": {"type": "string"},
          "kind": {"type": "string",
                   "enum": ["text", "tree_file", "json_field",
                            "toml_field", "plugin"]},
          "classification": {
            "type": "string",
            "enum": ["unchanged", "publish_to_repo", "reconcile_windows",
                     "conflict", "wsl_only", "windows_only",
                     "protected_overlay",
                     "additive_delete_requires_approval",
                     "plugin_missing", "plugin_extra",
                     "plugin_enabled_differs", "plugin_version_differs",
                     "plugin_pin_violation", "plugin_incompatible",
                     "error"]
          },
          "severity": {"type": "string",
                       "enum": ["info", "review", "conflict", "error"]},
          "path": {"type": "string"},
          "policy": {"type": "string"},
          "detail": {"type": "string"},
          "wsl_fingerprint": {"type": "string"},
          "repo_fingerprint": {"type": "string"},
          "windows_fingerprint": {"type": "string"}
        }
      }
    },
    "redactions": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["pointer", "reason", "value_type", "value_fingerprint"],
        "properties": {
          "pointer": {"type": "string"},
          "reason": {"type": "string"},
          "value_type": {"type": "string"},
          "value_fingerprint": {"type": "string"}
        }
      }
    },
    "errors": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["path", "message"],
        "properties": {
          "path": {"type": "string"},
          "message": {"type": "string"}
        }
      }
    }
  }
}
```

- [ ] **Step 11: Run the full test file to verify it passes**

Run: `python3 -m pytest tools/agent-config-sync/tests/test_manifest.py -v`
Expected: PASS (15 tests)

- [ ] **Step 12: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/.claude_code add config/agent-sync.toml tools/agent-config-sync/schema.py tools/agent-config-sync/manifest.py tools/agent-config-sync/schemas/drift-v1.json tools/agent-config-sync/tests/conftest.py tools/agent-config-sync/tests/test_manifest.py
git -C /mnt/d/Documents/Code/GitHub/.claude_code commit -m "feat(agent-config-sync): ownership manifest, schema validator, drift schema"
```

---

## Task 2: Normalization, path tokenization, and fingerprints

Two layers can hold the *same intent* in different bytes: CRLF vs LF, key order in JSON, `/home/leland/...` vs `C:\Users\aboog\...`. Comparing raw bytes would report drift that isn't there. This task makes "same intent" mechanically decidable.

**Files:**
- Create: `tools/agent-config-sync/normalize.py`
- Test: `tools/agent-config-sync/tests/test_normalize.py`

**Interfaces:**
- Consumes: `manifest.Roots` (Task 1).
- Produces:
  - `normalize_text(raw: str) -> str`
  - `normalize_json(raw: str) -> str` — raises `NormalizeError`
  - `normalize_toml(raw: str) -> str` — raises `NormalizeError`
  - `normalize_for_kind(raw: str, kind: str) -> str`
  - `tokenize_paths(text: str, roots: Roots) -> str`
  - `render_paths(text: str, layer: str, roots: Roots) -> str`
  - `portability_warnings(text: str) -> list[str]`
  - `wsl_mount_to_windows(path: Path) -> str`
  - `fingerprint(normalized: str) -> str` (full sha256 hex)
  - `short(fp: str | None) -> str` (first 12 chars, or `"-"` for `None`)
  - `class NormalizeError(ValueError)`
  - Constants: `TOKEN_HOME = "{HOME}"`, `TOKEN_REPO = "{REPO}"`

- [ ] **Step 1: Write the failing tests**

Create `tools/agent-config-sync/tests/test_normalize.py`:

```python
"""Tests for normalization, path tokenization, and fingerprints.

Design: "Deterministic scan" steps 5-6, and test case 11 (WSL-to-Windows
executable and path adaptation).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import manifest as mf  # noqa: E402
import normalize as nz  # noqa: E402

ROOTS = mf.Roots(
    wsl_home=Path("/home/leland"),
    repo=Path("/mnt/d/Documents/Code/GitHub/.claude_code"),
    windows_home=Path("/mnt/c/Users/aboog"),
)


# --- text ------------------------------------------------------------------

def test_normalize_text_converts_crlf_and_cr_to_lf():
    assert nz.normalize_text("a\r\nb\rc\n") == "a\nb\nc\n"


def test_normalize_text_strips_trailing_whitespace_per_line():
    assert nz.normalize_text("a   \nb\t\n") == "a\nb\n"


def test_normalize_text_ends_with_exactly_one_newline():
    assert nz.normalize_text("a") == "a\n"
    assert nz.normalize_text("a\n\n\n") == "a\n"


def test_normalize_text_strips_bom():
    assert nz.normalize_text("\ufeffhello") == "hello\n"


def test_normalize_text_is_idempotent():
    once = nz.normalize_text("a\r\n  b  \r\n")
    assert nz.normalize_text(once) == once


# --- json / toml -----------------------------------------------------------

def test_normalize_json_sorts_keys_and_reindents():
    a = nz.normalize_json('{"b": 1, "a": {"d": 2, "c": 3}}')
    b = nz.normalize_json('{"a":{"c":3,"d":2},"b":1}')
    assert a == b
    assert a.endswith("\n")
    assert a.splitlines()[1].startswith('  "a"')


def test_normalize_json_reports_location_without_content():
    with pytest.raises(nz.NormalizeError) as excinfo:
        nz.normalize_json('{"token": "hunter2",,}')
    message = str(excinfo.value)
    assert "line" in message and "column" in message
    assert "hunter2" not in message


def test_normalize_toml_produces_the_same_surface_as_json():
    from_toml = nz.normalize_toml('b = 1\n[a]\nc = 3\nd = 2\n')
    from_json = nz.normalize_json('{"a": {"c": 3, "d": 2}, "b": 1}')
    assert from_toml == from_json


def test_normalize_toml_reports_location_without_content():
    with pytest.raises(nz.NormalizeError) as excinfo:
        nz.normalize_toml('[bad\npassword = "hunter2"\n')
    assert "hunter2" not in str(excinfo.value)


def test_normalize_toml_renders_dates_as_strings():
    out = nz.normalize_toml('when = 2026-08-10\n')
    assert '"2026-08-10"' in out


def test_normalize_for_kind_dispatches():
    assert nz.normalize_for_kind("a\r\n", "text") == "a\n"
    assert nz.normalize_for_kind('{"a":1}', "json") == nz.normalize_json('{"a":1}')
    assert nz.normalize_for_kind("a = 1\n", "toml") == nz.normalize_json('{"a":1}')
    assert nz.normalize_for_kind("x\r\n", "tree") == "x\n"


# --- path tokenization -----------------------------------------------------

def test_tokenize_replaces_wsl_home_with_home_token():
    out = nz.tokenize_paths("see /home/leland/.claude/tools/guard.py now", ROOTS)
    assert out == "see {HOME}/.claude/tools/guard.py now"


def test_tokenize_replaces_windows_home_in_all_three_spellings():
    for spelling in ("/mnt/c/Users/aboog", "C:\\Users\\aboog", "C:/Users/aboog"):
        out = nz.tokenize_paths(f"path {spelling}/.claude/CLAUDE.md", ROOTS)
        assert out == "path {HOME}/.claude/CLAUDE.md", spelling


def test_tokenize_replaces_repo_before_its_parent_mount():
    out = nz.tokenize_paths(
        "/mnt/d/Documents/Code/GitHub/.claude_code/claude/skills", ROOTS)
    assert out == "{REPO}/claude/skills"


def test_tokenize_normalizes_backslashes_inside_a_matched_path():
    out = nz.tokenize_paths("C:\\Users\\aboog\\.claude\\settings.json", ROOTS)
    assert out == "{HOME}/.claude/settings.json"


def test_tokenize_leaves_unrelated_absolute_paths_alone():
    assert nz.tokenize_paths("/usr/bin/python3", ROOTS) == "/usr/bin/python3"


# --- path rendering (the Windows adaptation of design test case 11) ---------

def test_render_paths_to_wsl_layer():
    out = nz.render_paths("{HOME}/.claude/x.md", "wsl", ROOTS)
    assert out == "/home/leland/.claude/x.md"


def test_render_paths_to_repo_layer_uses_the_wsl_spelling():
    # The repo is a mirror of WSL intent, so publishing round-trips exactly.
    out = nz.render_paths("{HOME}/.claude/x.md", "repo", ROOTS)
    assert out == "/home/leland/.claude/x.md"


def test_render_paths_falls_back_when_a_root_is_not_a_mount(tmp_path: Path):
    roots = mf.Roots(wsl_home=tmp_path / "wsl", repo=tmp_path / "repo",
                     windows_home=tmp_path / "win")
    out = nz.render_paths("{HOME}/a.md", "windows", roots)
    assert "{HOME}" not in out
    assert out.endswith("a.md")


def test_render_paths_to_windows_layer_uses_drive_and_backslashes():
    out = nz.render_paths("{HOME}/.claude/x.md", "windows", ROOTS)
    assert out == "C:\\Users\\aboog\\.claude\\x.md"


def test_render_repo_token_for_windows_layer():
    out = nz.render_paths("{REPO}/claude/skills", "windows", ROOTS)
    assert out == "D:\\Documents\\Code\\GitHub\\.claude_code\\claude\\skills"


def test_tokenize_then_render_round_trips_wsl_to_windows():
    wsl_text = "hook: /home/leland/.claude/tools/guard.py --strict\n"
    tokenized = nz.tokenize_paths(wsl_text, ROOTS)
    assert nz.render_paths(tokenized, "windows", ROOTS) == (
        "hook: C:\\Users\\aboog\\.claude\\tools\\guard.py --strict\n")


def test_wsl_mount_to_windows_converts_drive_letters():
    assert nz.wsl_mount_to_windows(Path("/mnt/c/Users/aboog")) == "C:\\Users\\aboog"
    assert nz.wsl_mount_to_windows(Path("/mnt/d/x/y")) == "D:\\x\\y"


def test_wsl_mount_to_windows_returns_none_for_non_mount_paths():
    assert nz.wsl_mount_to_windows(Path("/home/leland")) is None


# --- portability warnings --------------------------------------------------

def test_portability_warnings_flags_wsl_only_literals():
    warnings = nz.portability_warnings(
        "run /usr/bin/python3 and /home/other/.venv_linux/bin/x")
    assert any("/usr/" in w for w in warnings)
    assert any("/home/" in w for w in warnings)


def test_portability_warnings_are_quiet_for_tokenized_text():
    assert nz.portability_warnings("{HOME}/.claude/x.md and {REPO}/y") == []


# --- fingerprints ----------------------------------------------------------

def test_fingerprint_is_stable_and_hex():
    fp = nz.fingerprint("hello\n")
    assert fp == nz.fingerprint("hello\n")
    assert len(fp) == 64
    assert all(c in "0123456789abcdef" for c in fp)


def test_fingerprint_differs_for_different_content():
    assert nz.fingerprint("a\n") != nz.fingerprint("b\n")


def test_short_truncates_and_handles_none():
    assert nz.short("a" * 64) == "a" * 12
    assert nz.short(None) == "-"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest tools/agent-config-sync/tests/test_normalize.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'normalize'`

- [ ] **Step 3: Implement `normalize.py`**

Create `tools/agent-config-sync/normalize.py`:

```python
#!/usr/bin/env python3
"""Normalization, path tokenization, and fingerprints.

Two layers can express the same intent with different bytes (CRLF vs LF, JSON
key order, /home/leland vs C:\\Users\\aboog). Everything here exists so that
"same intent" is mechanically decidable before anything is called drift.

Design: "Deterministic scan" steps 5-6.
"""
from __future__ import annotations

import hashlib
import json
import re
import tomllib
from datetime import date, datetime, time
from pathlib import Path

TOKEN_HOME = "{HOME}"
TOKEN_REPO = "{REPO}"

# Absolute-path shapes that cannot survive a move between environments.
_NON_PORTABLE = (
    ("/mnt/", "a WSL mount path"),
    ("/usr/", "a Linux system path"),
    ("/home/", "a Linux home path"),
    ("/opt/", "a Linux system path"),
    ("\\\\wsl$", "a WSL UNC path"),
    (".venv_linux", "a Linux-only virtualenv"),
)

# Characters that may follow a matched root prefix and still be part of a path.
_PATH_TAIL = r"[\w./\\+@~%-]*"


class NormalizeError(ValueError):
    """Input could not be parsed. Message carries a location, never content."""


# --------------------------------------------------------------------------
# text / json / toml
# --------------------------------------------------------------------------

def normalize_text(raw: str) -> str:
    text = raw.lstrip("\ufeff")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in text.split("\n")]
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines) + "\n" if lines else "\n"


def _canonical_json(data: object) -> str:
    def default(value: object) -> str:
        if isinstance(value, (datetime, date, time)):
            return value.isoformat()
        raise TypeError(f"unserializable type {type(value).__name__}")

    return json.dumps(data, sort_keys=True, indent=2,
                      ensure_ascii=False, default=default) + "\n"


def normalize_json(raw: str) -> str:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise NormalizeError(
            f"invalid JSON at line {exc.lineno}, column {exc.colno}") from None
    return _canonical_json(data)


def normalize_toml(raw: str) -> str:
    """Canonicalize TOML onto the shared JSON comparison surface.

    ONE-WAY: this accepts raw TOML bytes and emits JSON-shaped text, so a
    .toml and a .json file holding the same intent compare equal. It must
    never be applied to its own output. (Review ruling, 2026-08-11.)
    """
    try:
        data = tomllib.loads(raw)
    except tomllib.TOMLDecodeError as exc:
        # TOMLDecodeError has no .lineno; the location lives in str(exc).
        # Extract ONLY line/column and discard the rest of the message, so
        # no fragment of the source can ride along. (Review ruling.)
        match = re.search(r"at line (\d+), column (\d+)", str(exc))
        where = (f" at line {match.group(1)}, column {match.group(2)}"
                 if match else "")
        raise NormalizeError(f"invalid TOML{where}") from None
    return _canonical_json(data)


def normalize_for_kind(raw: str, kind: str) -> str:
    if kind == "json":
        return normalize_json(raw)
    if kind == "toml":
        return normalize_toml(raw)
    return normalize_text(raw)


# --------------------------------------------------------------------------
# path tokenization
# --------------------------------------------------------------------------

def wsl_mount_to_windows(path: Path) -> str | None:
    """/mnt/c/Users/aboog -> C:\\Users\\aboog. None if not a /mnt/<drive> path."""
    parts = Path(path).parts
    if len(parts) >= 3 and parts[0] == "/" and parts[1] == "mnt" and len(parts[2]) == 1:
        drive = parts[2].upper()
        tail = "\\".join(parts[3:])
        return f"{drive}:\\{tail}" if tail else f"{drive}:\\"
    return None


def _spellings(path: Path | None) -> list[str]:
    """Every way a root path can legitimately appear in a config file."""
    if path is None:
        return []
    out = [str(path)]
    windows = wsl_mount_to_windows(path)
    if windows:
        out.append(windows)
        out.append(windows.replace("\\", "/"))
    return out


def _replace_prefix(text: str, prefixes: list[str], token: str) -> str:
    for prefix in sorted(prefixes, key=len, reverse=True):
        # The lookahead is load-bearing: without it, /home/lelandxyz (a
        # different directory) matches the /home/leland prefix and becomes
        # "{HOME}xyz", which is not even a valid path. Admit / and \ (real
        # children) and end-of-token punctuation; reject name characters.
        # (Review ruling, 2026-08-11.)
        pattern = re.compile(re.escape(prefix) + r"(?![\w.+@~%-])"
                             + f"(?P<rest>{_PATH_TAIL})")
        text = pattern.sub(
            lambda m: token + m.group("rest").replace("\\", "/"), text)
    return text


def tokenize_paths(text: str, roots) -> str:
    """Replace layer roots with {HOME}/{REPO}. Longest prefix wins."""
    # Repo first: it usually lives under a mount that no other root claims,
    # but ordering by length guards against any future nesting.
    text = _replace_prefix(text, _spellings(roots.repo), TOKEN_REPO)
    homes = _spellings(roots.windows_home) + _spellings(roots.wsl_home)
    return _replace_prefix(text, homes, TOKEN_HOME)


def render_paths(text: str, layer: str, roots) -> str:
    """Replace {HOME}/{REPO} with the native spelling for one layer.

    The repository baseline is rendered in the WSL spelling: the repo is a
    mirror of WSL intent, so publishing round-trips to the same bytes the
    authority holds. Only the windows layer gets drive letters and backslashes.
    """
    if layer == "windows":
        # Fall back to the plain path when the root is not a /mnt/<drive> mount
        # (fixture trees in tests, or a target reached another way).
        home = ((wsl_mount_to_windows(roots.windows_home)
                 or str(roots.windows_home)) if roots.windows_home else None)
        repo = wsl_mount_to_windows(roots.repo) or str(roots.repo)
        out = text
        for token, native in ((TOKEN_HOME, home), (TOKEN_REPO, repo)):
            if native is None:
                continue
            pattern = re.compile(re.escape(token) + f"(?P<rest>{_PATH_TAIL})")
            out = pattern.sub(
                lambda m, n=native: n + m.group("rest").replace("/", "\\"), out)
        return out

    home = (roots.wsl_home if layer in ("wsl", "repo")
            else (roots.windows_home or roots.wsl_home))
    return text.replace(TOKEN_HOME, str(home)).replace(TOKEN_REPO, str(roots.repo))


def portability_warnings(text: str) -> list[str]:
    """Absolute literals that survived tokenization and will not travel."""
    return [f"contains {label}: {needle}"
            for needle, label in _NON_PORTABLE if needle in text]


# --------------------------------------------------------------------------
# fingerprints
# --------------------------------------------------------------------------

def fingerprint(normalized: str) -> str:
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def short(fp: str | None) -> str:
    return fp[:12] if fp else "-"
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest tools/agent-config-sync/tests/test_normalize.py -v`
Expected: PASS (27 tests)

- [ ] **Step 5: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/.claude_code add tools/agent-config-sync/normalize.py tools/agent-config-sync/tests/test_normalize.py
git -C /mnt/d/Documents/Code/GitHub/.claude_code commit -m "feat(agent-config-sync): normalization, path tokenization, fingerprints"
```

---

## Task 3: Allowlist extraction and the secret boundary

This is the task where a mistake leaks a credential. The rule from the design is absolute: **allowlist extraction, never ingest-then-redact**. A denied path is never opened; a denied key's value is never placed in a variable that reaches an output.

**Files:**
- Create: `tools/agent-config-sync/extract.py`
- Modify: `tools/agent-config-sync/manifest.py` (add `pointer_match` and `Entry.policy_for`)
- Test: `tools/agent-config-sync/tests/test_extract.py`

**Interfaces:**
- Consumes: `manifest.Entry`, `manifest.SecretPolicy` (Task 1); `normalize.*` (Task 2).
- Produces:
  - `manifest.pointer_match(pattern: str, pointer: str) -> bool` — dotted pointers; `*` matches one segment, `**` matches one or more.
  - `manifest.Entry.policy_for(pointer: str) -> str | None` — most-specific declared field policy, else the entry policy for `""`, else `None` (undeclared field).
  - `extract.Redaction(pointer: str, reason: str, value_type: str, value_fingerprint: str)` — frozen dataclass with `.as_dict()`.
  - `extract.Unit(entry_id: str, layer: str, key: str, path: str, kind: str, policy: str | None, normalized: str | None, fingerprint: str | None, redactions: tuple[Redaction, ...], error: str | None)` — frozen dataclass.
  - `extract.glob_to_regex(pattern: str) -> re.Pattern`
  - `extract.is_denied(rel: str, globs) -> bool`
  - `extract.redact_tree(data, secrets, *, pointer: str = "") -> tuple[object, list[Redaction]]`
  - `extract.extract_entry(entry, layer: str, root: Path | None, secrets, roots) -> list[Unit]`
  - Constant: `REDACTED = "<redacted>"`

- [ ] **Step 1: Write the failing tests**

Create `tools/agent-config-sync/tests/test_extract.py`:

```python
"""Tests for allowlist extraction and the secret boundary.

Design: "Secret and state boundary"; test cases 9 (inline MCP secrets),
10 (malformed JSON/TOML), 12 (unknown files and fields).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import extract as ex  # noqa: E402
import manifest as mf  # noqa: E402

ROOTS = mf.Roots(wsl_home=Path("/home/leland"), repo=Path("/repo"),
                 windows_home=Path("/mnt/c/Users/aboog"))

SECRETS = mf.SecretPolicy(
    deny_key_patterns=("(?i)token", "(?i)api[_-]?key", "(?i)password"),
    deny_path_globs=("**/.credentials.json", "**/history.jsonl", "**/*.log"),
)


# --- pointer matching (manifest.py) ---------------------------------------

def test_pointer_match_exact():
    assert mf.pointer_match("model", "model")
    assert not mf.pointer_match("model", "modelX")


def test_pointer_star_matches_one_segment():
    assert mf.pointer_match("mcpServers.*.env", "mcpServers.github.env")
    assert not mf.pointer_match("mcpServers.*.env", "mcpServers.a.b.env")


def test_pointer_double_star_matches_many_segments():
    assert mf.pointer_match("mcpServers.**", "mcpServers.a.b.env")


def test_policy_for_prefers_the_most_specific_pattern():
    entry = mf.Entry(id="e", policy="portable_authoritative", kind="json",
                     fields={"mcpServers.**": "portable_authoritative",
                             "mcpServers.*.env": "excluded"})
    assert entry.policy_for("mcpServers.github.env") == "excluded"
    assert entry.policy_for("mcpServers.github.args") == "portable_authoritative"


def test_policy_for_returns_none_for_undeclared_field():
    entry = mf.Entry(id="e", policy="portable_authoritative", kind="json",
                     fields={"model": "portable_authoritative"})
    assert entry.policy_for("somethingNew") is None


def test_policy_for_falls_back_to_entry_policy_when_no_fields_declared():
    entry = mf.Entry(id="e", policy="portable_additive", kind="text")
    assert entry.policy_for("") == "portable_additive"


# --- glob denial -----------------------------------------------------------

def test_glob_star_does_not_cross_a_slash():
    assert ex.is_denied("a.log", ("*.log",))
    assert not ex.is_denied("dir/a.log", ("*.log",))


def test_double_star_crosses_slashes():
    assert ex.is_denied("deep/dir/a.log", ("**/*.log",))
    assert ex.is_denied(".credentials.json", ("**/.credentials.json",))


def test_denied_directory_prefix():
    assert ex.is_denied("projects/x/y.json", ("**/projects/**",))


# --- redaction -------------------------------------------------------------

def test_redact_replaces_secret_valued_keys_and_records_a_hash():
    data = {"mcpServers": {"gh": {"command": "npx",
                                  "env": {"GITHUB_TOKEN": "ghp_realsecret"}}}}
    cleaned, redactions = ex.redact_tree(data, SECRETS)
    assert cleaned["mcpServers"]["gh"]["env"]["GITHUB_TOKEN"] == ex.REDACTED
    assert cleaned["mcpServers"]["gh"]["command"] == "npx"
    assert [r.pointer for r in redactions] == ["mcpServers.gh.env.GITHUB_TOKEN"]
    assert redactions[0].reason == "secret_key_pattern"
    assert redactions[0].value_type == "str"
    assert len(redactions[0].value_fingerprint) == 64


def test_redaction_never_carries_the_value_anywhere():
    data = {"apiKey": "sk-live-DO-NOT-LEAK"}
    cleaned, redactions = ex.redact_tree(data, SECRETS)
    blob = repr(cleaned) + repr(redactions) + str(redactions[0].as_dict())
    assert "sk-live-DO-NOT-LEAK" not in blob


def test_redact_keeps_env_variable_names():
    data = {"env": {"API_KEY": "x", "NODE_ENV": "production"}}
    cleaned, _ = ex.redact_tree(data, SECRETS)
    assert set(cleaned["env"]) == {"API_KEY", "NODE_ENV"}
    assert cleaned["env"]["API_KEY"] == ex.REDACTED
    assert cleaned["env"]["NODE_ENV"] == "production"


def test_redact_walks_lists():
    data = {"servers": [{"password": "p"}, {"name": "ok"}]}
    cleaned, redactions = ex.redact_tree(data, SECRETS)
    assert cleaned["servers"][0]["password"] == ex.REDACTED
    assert redactions[0].pointer == "servers[0].password"


# --- extraction ------------------------------------------------------------

def make_entry(**kwargs) -> mf.Entry:
    base = dict(id="e", policy="portable_authoritative", kind="text",
                wsl="a.md", repo="a.md", windows="a.md")
    base.update(kwargs)
    return mf.Entry(**base)


def test_extract_text_entry_normalizes_and_fingerprints(tmp_path: Path):
    (tmp_path / "a.md").write_text("hello\r\n", encoding="utf-8")
    units = ex.extract_entry(make_entry(), "wsl", tmp_path, SECRETS, ROOTS)
    assert len(units) == 1
    assert units[0].normalized == "hello\n"
    assert units[0].fingerprint is not None
    assert units[0].key == ""


def test_extract_missing_file_yields_a_unit_with_no_fingerprint(tmp_path: Path):
    units = ex.extract_entry(make_entry(), "wsl", tmp_path, SECRETS, ROOTS)
    assert len(units) == 1
    assert units[0].fingerprint is None
    assert units[0].error is None


def test_extract_absent_layer_root_yields_nothing():
    assert ex.extract_entry(make_entry(), "windows", None, SECRETS, ROOTS) == []


def test_extract_tokenizes_paths_so_layers_compare_equal(tmp_path: Path):
    (tmp_path / "a.md").write_text("run /home/leland/.claude/x.py\n",
                                   encoding="utf-8")
    units = ex.extract_entry(make_entry(), "wsl", tmp_path, SECRETS, ROOTS)
    assert units[0].normalized == "run {HOME}/.claude/x.py\n"


def test_extract_tree_emits_one_unit_per_matching_file(tmp_path: Path):
    (tmp_path / "skills" / "a").mkdir(parents=True)
    (tmp_path / "skills" / "a" / "SKILL.md").write_text("x\n", encoding="utf-8")
    (tmp_path / "skills" / "notes.txt").write_text("ignored\n", encoding="utf-8")
    entry = make_entry(kind="tree", wsl="skills", globs=("**/*.md",))
    units = ex.extract_entry(entry, "wsl", tmp_path, SECRETS, ROOTS)
    assert [u.key for u in units] == ["a/SKILL.md"]


def test_extract_tree_skips_denied_paths_entirely(tmp_path: Path):
    (tmp_path / "d").mkdir()
    (tmp_path / "d" / "history.jsonl").write_text("SECRET-TRANSCRIPT\n",
                                                  encoding="utf-8")
    (tmp_path / "d" / "ok.md").write_text("fine\n", encoding="utf-8")
    entry = make_entry(kind="tree", wsl="d", globs=("**/*",))
    units = ex.extract_entry(entry, "wsl", tmp_path, SECRETS, ROOTS)
    assert [u.key for u in units] == ["ok.md"]
    assert "SECRET-TRANSCRIPT" not in repr(units)


def test_extract_json_with_declared_fields_emits_one_unit_per_field(tmp_path: Path):
    (tmp_path / "s.json").write_text(
        '{"model": "opus", "statusLine": {"command": "/win/x.sh"}}',
        encoding="utf-8")
    entry = make_entry(kind="json", wsl="s.json",
                       fields={"model": "portable_authoritative",
                               "statusLine.command": "platform_overlay"})
    units = ex.extract_entry(entry, "wsl", tmp_path, SECRETS, ROOTS)
    by_key = {u.key: u for u in units}
    assert by_key["model"].policy == "portable_authoritative"
    assert by_key["statusLine.command"].policy == "platform_overlay"


def test_extract_json_reports_undeclared_top_level_keys_as_unknown(tmp_path: Path):
    (tmp_path / "s.json").write_text('{"model": "opus", "brandNew": {"a": 1}}',
                                     encoding="utf-8")
    entry = make_entry(kind="json", wsl="s.json",
                       fields={"model": "portable_authoritative"})
    units = ex.extract_entry(entry, "wsl", tmp_path, SECRETS, ROOTS)
    unknown = [u for u in units if u.key == "brandNew"]
    assert len(unknown) == 1
    assert unknown[0].policy is None
    assert unknown[0].normalized is None      # metadata only, per the design
    assert unknown[0].fingerprint is not None


def test_extract_json_omits_excluded_fields_completely(tmp_path: Path):
    (tmp_path / "s.json").write_text(
        '{"mcpServers": {"gh": {"env": {"TOKEN": "leak"}, "args": ["x"]}}}',
        encoding="utf-8")
    entry = make_entry(kind="json", wsl="s.json",
                       fields={"mcpServers.*.args": "portable_authoritative",
                               "mcpServers.*.env": "excluded"})
    units = ex.extract_entry(entry, "wsl", tmp_path, SECRETS, ROOTS)
    keys = [u.key for u in units]
    assert "mcpServers.gh.args" in keys
    assert "mcpServers.gh.env" not in keys
    assert "leak" not in repr(units)


def test_extract_json_redacts_inline_secret_values(tmp_path: Path):
    (tmp_path / "s.json").write_text(
        '{"mcpServers": {"gh": {"apiKey": "sk-leak", "args": []}}}',
        encoding="utf-8")
    entry = make_entry(kind="json", wsl="s.json",
                       fields={"mcpServers.**": "portable_authoritative"})
    units = ex.extract_entry(entry, "wsl", tmp_path, SECRETS, ROOTS)
    assert "sk-leak" not in repr(units)
    assert any(u.redactions for u in units)


def test_extract_malformed_json_records_a_location_not_content(tmp_path: Path):
    (tmp_path / "s.json").write_text('{"password": "hunter2",,}',
                                     encoding="utf-8")
    entry = make_entry(kind="json", wsl="s.json")
    units = ex.extract_entry(entry, "wsl", tmp_path, SECRETS, ROOTS)
    assert len(units) == 1
    assert units[0].error is not None
    assert "line" in units[0].error
    assert "hunter2" not in units[0].error
    assert units[0].normalized is None


def test_extract_unreadable_file_records_an_error(tmp_path: Path):
    target = tmp_path / "a.md"
    target.write_bytes(b"\xff\xfe\x00binary")
    units = ex.extract_entry(make_entry(), "wsl", tmp_path, SECRETS, ROOTS)
    assert units[0].error is not None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest tools/agent-config-sync/tests/test_extract.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'extract'`

- [ ] **Step 3: Add pointer matching to `manifest.py`**

Add to `tools/agent-config-sync/manifest.py`, after the `KINDS` constant:

```python
import re


def _pointer_regex(pattern: str) -> re.Pattern[str]:
    parts = []
    for segment in pattern.split("."):
        if segment == "**":
            parts.append(r"[^.]+(?:\.[^.]+)*")
        elif segment == "*":
            parts.append(r"[^.]+")
        else:
            parts.append(re.escape(segment))
    return re.compile("^" + r"\.".join(parts) + "$")


def pointer_match(pattern: str, pointer: str) -> bool:
    """Dotted-pointer glob: '*' matches one segment, '**' matches one or more."""
    return bool(_pointer_regex(pattern).match(pointer))


def _specificity(pattern: str) -> tuple[int, int]:
    """More literal segments and fewer wildcards wins."""
    segments = pattern.split(".")
    wildcards = sum(1 for s in segments if s in ("*", "**"))
    return (len(segments) - wildcards, -wildcards)
```

And add this method to the `Entry` dataclass:

```python
    def policy_for(self, pointer: str) -> str | None:
        """Field-level policy, most specific pattern first.

        Returns None for a field that no pattern covers -- an undeclared field,
        which the design says to report as metadata only.
        """
        if not self.fields:
            return self.policy
        matches = [(pat, pol) for pat, pol in self.fields.items()
                   if pointer_match(pat, pointer)]
        if not matches:
            return None
        matches.sort(key=lambda pair: _specificity(pair[0]), reverse=True)
        return matches[0][1]
```

- [ ] **Step 4: Implement `extract.py`**

Create `tools/agent-config-sync/extract.py`:

```python
#!/usr/bin/env python3
"""Allowlist extraction with a hard secret boundary.

The rule (design, "Secret and state boundary"): collect only what the manifest
declares. Denied paths are never opened. Denied keys never have their values
placed in a variable that reaches an output -- only a type and a hash.

Design: "Deterministic scan" step 4.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import manifest as mf
import normalize as nz

REDACTED = "<redacted>"

LAYERS = ("wsl", "repo", "windows")


@dataclass(frozen=True)
class Redaction:
    pointer: str
    reason: str
    value_type: str
    value_fingerprint: str

    def as_dict(self) -> dict[str, str]:
        return {"pointer": self.pointer, "reason": self.reason,
                "value_type": self.value_type,
                "value_fingerprint": self.value_fingerprint}


@dataclass(frozen=True)
class Unit:
    """One comparable thing in one layer.

    key: "" for a whole-file entry, a relative path for a tree entry, a dotted
    pointer for a json/toml field entry.
    """
    entry_id: str
    layer: str
    key: str
    path: str
    kind: str
    policy: str | None = None
    normalized: str | None = None
    fingerprint: str | None = None
    redactions: tuple[Redaction, ...] = ()
    error: str | None = None

    @property
    def unit_id(self) -> str:
        return f"{self.entry_id}:{self.key}" if self.key else self.entry_id


# --------------------------------------------------------------------------
# path globs
# --------------------------------------------------------------------------

def glob_to_regex(pattern: str) -> re.Pattern[str]:
    """'*' stops at '/', '**' crosses it. Trailing '/**' also matches the dir."""
    out = []
    index = 0
    while index < len(pattern):
        char = pattern[index]
        if pattern.startswith("**/", index):
            out.append("(?:.*/)?")
            index += 3
        elif pattern.startswith("**", index):
            out.append(".*")
            index += 2
        elif char == "*":
            out.append("[^/]*")
            index += 1
        elif char == "?":
            out.append("[^/]")
            index += 1
        else:
            out.append(re.escape(char))
            index += 1
    return re.compile("^" + "".join(out) + "$")


def is_denied(rel: str, globs) -> bool:
    return any(glob_to_regex(pattern).match(rel) for pattern in globs)


# --------------------------------------------------------------------------
# redaction
# --------------------------------------------------------------------------

def _is_secret_key(key: str, secrets) -> bool:
    return any(re.search(pattern, key) for pattern in secrets.deny_key_patterns)


def redact_tree(data, secrets, *, pointer: str = "") -> tuple[object, list[Redaction]]:
    """Return a copy with secret-valued keys replaced, plus the redaction log."""
    redactions: list[Redaction] = []

    if isinstance(data, dict):
        cleaned: dict = {}
        for key, value in data.items():
            child = f"{pointer}.{key}" if pointer else str(key)
            if _is_secret_key(str(key), secrets):
                cleaned[key] = REDACTED
                redactions.append(Redaction(
                    pointer=child,
                    reason="secret_key_pattern",
                    value_type=type(value).__name__,
                    value_fingerprint=nz.fingerprint(repr(value)),
                ))
                continue
            sub, sub_redactions = redact_tree(value, secrets, pointer=child)
            cleaned[key] = sub
            redactions.extend(sub_redactions)
        return cleaned, redactions

    if isinstance(data, list):
        cleaned_list = []
        for index, value in enumerate(data):
            sub, sub_redactions = redact_tree(
                value, secrets, pointer=f"{pointer}[{index}]")
            cleaned_list.append(sub)
            redactions.extend(sub_redactions)
        return cleaned_list, redactions

    return data, redactions


# --------------------------------------------------------------------------
# extraction
# --------------------------------------------------------------------------

def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _display(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _unit_for_file(entry, layer, root, path, key, secrets, roots,
                   kind: str, policy: str | None) -> Unit:
    common = dict(entry_id=entry.id, layer=layer, key=key,
                  path=_display(root, path), kind=kind, policy=policy)
    if not path.exists():
        return Unit(**common)
    try:
        raw = _read(path)
    except (UnicodeDecodeError, OSError) as exc:
        return Unit(**common, error=f"unreadable: {type(exc).__name__}")
    try:
        text = nz.normalize_for_kind(raw, kind if kind in ("json", "toml") else "text")
    except nz.NormalizeError as exc:
        return Unit(**common, error=str(exc))
    text = nz.tokenize_paths(text, roots)
    return Unit(**common, normalized=text, fingerprint=nz.fingerprint(text))


def _flatten_pointers(data, prefix: str = "") -> list[tuple[str, object]]:
    """Every dict pointer, parents before children."""
    out: list[tuple[str, object]] = []
    if isinstance(data, dict):
        for key, value in data.items():
            child = f"{prefix}.{key}" if prefix else str(key)
            out.append((child, value))
            out.extend(_flatten_pointers(value, child))
    return out


def _extract_structured(entry, layer, root, path, secrets, roots) -> list[Unit]:
    kind = entry.kind
    common = dict(entry_id=entry.id, layer=layer,
                  path=_display(root, path), kind=f"{kind}_field")
    if not path.exists():
        return [Unit(**common, key="", policy=entry.policy)]
    try:
        raw = _read(path)
        canonical = nz.normalize_for_kind(raw, kind)
    except nz.NormalizeError as exc:
        return [Unit(**common, key="", policy=entry.policy, error=str(exc))]
    except (UnicodeDecodeError, OSError) as exc:
        return [Unit(**common, key="", policy=entry.policy,
                     error=f"unreadable: {type(exc).__name__}")]

    import json as _json
    data = _json.loads(canonical)
    data, redactions = redact_tree(data, secrets)

    if not entry.fields:
        text = nz.tokenize_paths(nz.normalize_json(_json.dumps(data)), roots)
        return [Unit(**common, key="", policy=entry.policy, normalized=text,
                     fingerprint=nz.fingerprint(text),
                     redactions=tuple(redactions))]

    units: list[Unit] = []
    covered: set[str] = set()
    for pointer, value in _flatten_pointers(data):
        policy = entry.policy_for(pointer)
        if policy is None:
            continue
        if policy == "excluded":
            covered.add(pointer.split(".")[0])
            continue
        # Skip a parent when a declared child pattern will emit it instead.
        if any(pointer_is_ancestor(pointer, other)
               for other, _ in _flatten_pointers(data)
               if other != pointer and entry.policy_for(other) is not None):
            continue
        text = nz.tokenize_paths(
            nz.normalize_json(_json.dumps(value)), roots)
        # Boundary check, not a bare startswith: "envFoo.token" must not be
        # attributed to the sibling field "env". Same bug class as the path
        # prefix over-match. (Review ruling, 2026-08-11.)
        units.append(Unit(**common, key=pointer, policy=policy,
                          normalized=text, fingerprint=nz.fingerprint(text),
                          redactions=tuple(
                              r for r in redactions
                              if r.pointer == pointer
                              or r.pointer.startswith(pointer + ".")
                              or r.pointer.startswith(pointer + "["))))
        covered.add(pointer.split(".")[0])

    # Undeclared top-level keys: metadata only (design, "Unknown content").
    for key, value in (data.items() if isinstance(data, dict) else []):
        if key in covered:
            continue
        text = nz.normalize_json(_json.dumps(value))
        units.append(Unit(**common, key=str(key), policy=None,
                          normalized=None,
                          fingerprint=nz.fingerprint(text)))
    return units


def pointer_is_ancestor(ancestor: str, descendant: str) -> bool:
    return descendant.startswith(ancestor + ".")


def extract_entry(entry, layer: str, root: Path | None, secrets, roots) -> list[Unit]:
    """All comparable units for one manifest entry in one layer."""
    if root is None or entry.policy == "excluded":
        return []
    rel = entry.rel_for_layer(layer)
    if rel is None:
        return []
    target = Path(root) / rel

    if entry.kind == "tree":
        if not target.is_dir():
            return []
        units: list[Unit] = []
        for path in sorted(target.rglob("*")):
            if not path.is_file():
                continue
            key = str(path.relative_to(target))
            if is_denied(key, secrets.deny_path_globs) or is_denied(
                    str(path.relative_to(root)), secrets.deny_path_globs):
                continue
            if entry.globs and not any(
                    glob_to_regex(g).match(key) for g in entry.globs):
                continue
            units.append(_unit_for_file(entry, layer, root, path, key,
                                        secrets, roots, "text", entry.policy))
        return units

    if is_denied(rel, secrets.deny_path_globs):
        return []

    if entry.kind in ("json", "toml"):
        return _extract_structured(entry, layer, root, target, secrets, roots)

    return [_unit_for_file(entry, layer, root, target, "", secrets, roots,
                           "text", entry.policy)]
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m pytest tools/agent-config-sync/tests/test_extract.py -v`
Expected: PASS (22 tests)

- [ ] **Step 6: Run the whole suite to catch regressions in `manifest.py`**

Run: `python3 -m pytest tools/agent-config-sync/tests/ -v`
Expected: PASS (62 tests)

- [ ] **Step 7: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/.claude_code add tools/agent-config-sync/extract.py tools/agent-config-sync/manifest.py tools/agent-config-sync/tests/test_extract.py
git -C /mnt/d/Documents/Code/GitHub/.claude_code commit -m "feat(agent-config-sync): allowlist extraction with hard secret boundary"
```

---

## Task 4: Three-way comparison and the classification truth table

This is the heart of the authority model. It is pure functions over fingerprints — no filesystem, no clock — so the truth table can be exercised exhaustively.

**Files:**
- Create: `tools/agent-config-sync/compare.py`
- Modify: `tools/agent-config-sync/extract.py` (skip `kind == "plugins"`; Task 5 owns those)
- Test: `tools/agent-config-sync/tests/test_compare.py`

**Interfaces:**
- Consumes: `extract.Unit`, `extract.Redaction` (Task 3); `manifest.Entry`, `manifest.Manifest` (Task 1).
- Produces:
  - `compare.DriftItem(id, entry_id, kind, classification, severity, path, policy, detail, wsl_fingerprint, repo_fingerprint, windows_fingerprint, redactions)` — frozen dataclass with `.as_dict() -> dict` that omits `None` fingerprints.
  - `compare.classify(wsl, repo, windows, policy, *, has_windows) -> tuple[str, str, str]` returning `(classification, severity, detail)`.
  - `compare.compare_entry(entry, units: list[Unit], *, has_windows: bool) -> list[DriftItem]`
  - `compare.compare_all(manifest, units: list[Unit]) -> list[DriftItem]`
  - `compare.ACTIONABLE: frozenset[str]` — classifications that mean the report is worth generating.
  - `compare.counts(items) -> dict[str, int]`

- [ ] **Step 1: Write the failing tests**

Create `tools/agent-config-sync/tests/test_compare.py`:

```python
"""Tests for the three-way comparison truth table.

Design: "Authority model". Covers design test cases 2 (portable WSL addition),
3 (repo record awaiting Windows reconciliation), 4 (independent WSL and Windows
edits), 5 (Windows-only protected keys), 6 (additive deletion), 12 (unknown).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import compare as cmp  # noqa: E402
import extract as ex  # noqa: E402
import manifest as mf  # noqa: E402

A, B, C = "a" * 64, "b" * 64, "c" * 64
AUTH = "portable_authoritative"
ADD = "portable_additive"


def unit(layer: str, fp: str | None, *, entry_id="e", key="",
         policy=AUTH, kind="text", error=None) -> ex.Unit:
    return ex.Unit(entry_id=entry_id, layer=layer, key=key, path="a.md",
                   kind=kind, policy=policy, normalized=None,
                   fingerprint=fp, error=error)


# --- classify(): the truth table -------------------------------------------

def test_all_three_agree_is_unchanged():
    assert cmp.classify(A, A, A, AUTH, has_windows=True)[0] == "unchanged"


def test_wsl_ahead_of_an_aligned_baseline_publishes():
    kind, severity, _ = cmp.classify(B, A, A, AUTH, has_windows=True)
    assert (kind, severity) == ("publish_to_repo", "review")


def test_baseline_ahead_of_windows_reconciles_windows():
    kind, severity, _ = cmp.classify(A, A, B, AUTH, has_windows=True)
    assert (kind, severity) == ("reconcile_windows", "review")


def test_wsl_and_windows_disagree_is_a_conflict_with_no_winner():
    kind, severity, detail = cmp.classify(B, A, C, AUTH, has_windows=True)
    assert (kind, severity) == ("conflict", "conflict")
    assert "winner" in detail or "judgment" in detail


def test_wsl_and_windows_agree_against_a_stale_baseline_publishes():
    # Documented refinement: agreement means there is no winner to choose.
    kind, severity, detail = cmp.classify(B, A, B, AUTH, has_windows=True)
    assert (kind, severity) == ("publish_to_repo", "review")
    assert "stale" in detail


def test_wsl_only_item_is_a_new_portable_candidate():
    assert cmp.classify(A, None, None, AUTH, has_windows=True)[0] == "wsl_only"


def test_windows_only_item_is_reported_as_windows_only():
    assert cmp.classify(None, None, A, AUTH, has_windows=True)[0] == "windows_only"


def test_no_baseline_with_agreeing_layers_captures_the_baseline():
    kind, _, detail = cmp.classify(A, None, A, AUTH, has_windows=True)
    assert kind == "publish_to_repo"
    assert "baseline" in detail


def test_no_baseline_with_disagreeing_layers_is_a_conflict():
    assert cmp.classify(A, None, B, AUTH, has_windows=True)[0] == "conflict"


def test_additive_deletion_requires_approval():
    kind, severity, _ = cmp.classify(None, A, A, ADD, has_windows=True)
    assert (kind, severity) == ("additive_delete_requires_approval", "review")


def test_authoritative_deletion_publishes_but_says_so():
    kind, _, detail = cmp.classify(None, A, A, AUTH, has_windows=True)
    assert kind == "publish_to_repo"
    assert "deletion" in detail


def test_platform_overlay_is_always_protected_and_never_actionable():
    kind, severity, _ = cmp.classify(A, B, C, "platform_overlay", has_windows=True)
    assert (kind, severity) == ("protected_overlay", "info")


def test_undeclared_field_that_agrees_is_unchanged():
    assert cmp.classify(A, A, A, None, has_windows=True)[0] == "unchanged"


def test_undeclared_field_that_differs_is_a_conflict_asking_for_a_policy():
    kind, _, detail = cmp.classify(A, B, A, None, has_windows=True)
    assert kind == "conflict"
    assert "agent-sync.toml" in detail


def test_without_a_windows_layer_only_wsl_and_repo_are_compared():
    assert cmp.classify(A, A, None, AUTH, has_windows=False)[0] == "unchanged"
    assert cmp.classify(B, A, None, AUTH, has_windows=False)[0] == "publish_to_repo"


# --- compare_entry() -------------------------------------------------------

def test_compare_entry_joins_layers_by_key():
    entry = mf.Entry(id="e", policy=AUTH, kind="text", wsl="a.md",
                     repo="a.md", windows="a.md")
    items = cmp.compare_entry(
        entry, [unit("wsl", B), unit("repo", A), unit("windows", A)],
        has_windows=True)
    assert len(items) == 1
    assert items[0].id == "e"
    assert items[0].classification == "publish_to_repo"
    assert items[0].wsl_fingerprint == B


def test_compare_entry_emits_one_item_per_tree_file():
    entry = mf.Entry(id="skills", policy=ADD, kind="tree", wsl="skills")
    items = cmp.compare_entry(entry, [
        unit("wsl", A, entry_id="skills", key="a/SKILL.md", policy=ADD),
        unit("repo", A, entry_id="skills", key="a/SKILL.md", policy=ADD),
        unit("wsl", B, entry_id="skills", key="b/SKILL.md", policy=ADD),
    ], has_windows=False)
    by_id = {item.id: item for item in items}
    assert by_id["skills:a/SKILL.md"].classification == "unchanged"
    assert by_id["skills:b/SKILL.md"].classification == "wsl_only"
    assert by_id["skills:b/SKILL.md"].kind == "tree_file"


def test_compare_entry_uses_the_field_policy_not_the_entry_policy():
    entry = mf.Entry(id="settings", policy=AUTH, kind="json", wsl="s.json",
                     fields={"statusLine.command": "platform_overlay"})
    items = cmp.compare_entry(entry, [
        unit("wsl", A, entry_id="settings", key="statusLine.command",
             policy="platform_overlay", kind="json_field"),
        unit("windows", B, entry_id="settings", key="statusLine.command",
             policy="platform_overlay", kind="json_field"),
    ], has_windows=True)
    assert items[0].classification == "protected_overlay"
    assert items[0].severity == "info"


def test_compare_entry_surfaces_extraction_errors():
    entry = mf.Entry(id="e", policy=AUTH, kind="json", wsl="s.json")
    items = cmp.compare_entry(
        entry, [unit("wsl", None, error="invalid JSON at line 1, column 3")],
        has_windows=False)
    assert items[0].classification == "error"
    assert items[0].severity == "error"
    assert "line 1" in items[0].detail


def test_compare_entry_carries_redactions_through():
    redaction = ex.Redaction(pointer="env.TOKEN", reason="secret_key_pattern",
                             value_type="str", value_fingerprint=A)
    wsl = ex.Unit(entry_id="e", layer="wsl", key="", path="s.json",
                  kind="json_field", policy=AUTH, fingerprint=B,
                  redactions=(redaction,))
    entry = mf.Entry(id="e", policy=AUTH, kind="json", wsl="s.json")
    items = cmp.compare_entry(entry, [wsl], has_windows=False)
    assert items[0].redactions == (redaction,)


# --- aggregation -----------------------------------------------------------

def test_counts_tallies_by_classification():
    entry = mf.Entry(id="e", policy=AUTH, kind="text", wsl="a.md", repo="a.md")
    items = cmp.compare_entry(entry, [unit("wsl", B), unit("repo", A)],
                              has_windows=False)
    assert cmp.counts(items) == {"publish_to_repo": 1}


def test_unchanged_and_protected_are_not_actionable():
    assert "unchanged" not in cmp.ACTIONABLE
    assert "protected_overlay" not in cmp.ACTIONABLE
    assert "conflict" in cmp.ACTIONABLE
    assert "publish_to_repo" in cmp.ACTIONABLE


def test_as_dict_omits_absent_fingerprints():
    item = cmp.DriftItem(id="e", entry_id="e", kind="text",
                         classification="wsl_only", severity="review",
                         path="a.md", policy=AUTH, detail="d",
                         wsl_fingerprint=A)
    data = item.as_dict()
    assert data["wsl_fingerprint"] == A
    assert "repo_fingerprint" not in data
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest tools/agent-config-sync/tests/test_compare.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'compare'`

- [ ] **Step 3: Implement `compare.py`**

Create `tools/agent-config-sync/compare.py`:

```python
#!/usr/bin/env python3
"""Three-way comparison: WSL authority, repository baseline, Windows target.

Pure functions over fingerprints. No filesystem, no clock, no model.

Design: "Authority model".
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

SEVERITY_BY_CLASSIFICATION = {
    "unchanged": "info",
    "publish_to_repo": "review",
    "reconcile_windows": "review",
    "conflict": "conflict",
    "wsl_only": "review",
    "windows_only": "review",
    "protected_overlay": "info",
    "additive_delete_requires_approval": "review",
    "error": "error",
}

#: Classifications that mean a report is worth generating at all.
ACTIONABLE = frozenset({
    "publish_to_repo", "reconcile_windows", "conflict", "wsl_only",
    "windows_only", "additive_delete_requires_approval",
    "plugin_missing", "plugin_enabled_differs", "plugin_version_differs",
    "plugin_pin_violation", "plugin_incompatible", "error",
})


@dataclass(frozen=True)
class DriftItem:
    id: str
    entry_id: str
    kind: str
    classification: str
    severity: str
    path: str
    policy: str | None
    detail: str
    wsl_fingerprint: str | None = None
    repo_fingerprint: str | None = None
    windows_fingerprint: str | None = None
    redactions: tuple = ()

    def as_dict(self) -> dict:
        data = {
            "id": self.id,
            "entry_id": self.entry_id,
            "kind": self.kind,
            "classification": self.classification,
            "severity": self.severity,
            "path": self.path,
            "policy": self.policy or "undeclared",
            "detail": self.detail,
        }
        for name, value in (("wsl_fingerprint", self.wsl_fingerprint),
                            ("repo_fingerprint", self.repo_fingerprint),
                            ("windows_fingerprint", self.windows_fingerprint)):
            if value:
                data[name] = value
        return data


def classify(wsl: str | None, repo: str | None, windows: str | None,
             policy: str | None, *, has_windows: bool) -> tuple[str, str, str]:
    """Return (classification, severity, detail) for one comparable unit."""
    if policy == "platform_overlay":
        return ("protected_overlay", "info",
                "Windows owns this value; preserved and reported only.")

    if not has_windows:
        windows = None

    if policy is None:
        present = [fp for fp in (wsl, repo, windows) if fp]
        if len(set(present)) <= 1:
            return ("unchanged", "info", "Ownership undeclared; layers agree.")
        return ("conflict", "conflict",
                "Ownership undeclared and layers differ. Declare a policy for "
                "this field in config/agent-sync.toml before merging.")

    # No baseline in the repository.
    if repo is None:
        if wsl and windows:
            if wsl == windows:
                return ("publish_to_repo", "review",
                        "No baseline recorded; WSL and Windows agree. "
                        "Publishing captures the initial baseline.")
            return ("conflict", "conflict",
                    "No baseline recorded and WSL and Windows differ; "
                    "there is nothing to arbitrate against. Requires judgment.")
        if wsl:
            return ("wsl_only", "review",
                    "Present in WSL only; a new portable item.")
        if windows:
            return ("windows_only", "review",
                    "Present on Windows only; ownership is not declared.")
        return ("unchanged", "info", "Absent everywhere.")

    # Removed from WSL.
    if wsl is None:
        if policy == "portable_additive":
            return ("additive_delete_requires_approval", "review",
                    "Removed in WSL. This item is portable-additive, so the "
                    "deletion is never applied without explicit approval.")
        return ("publish_to_repo", "review",
                "Removed in WSL. Publishing records the deletion in the "
                "baseline; review it as a deletion, not an update.")

    if wsl == repo == windows:
        return ("unchanged", "info", "All layers agree.")

    if wsl != repo and repo == windows:
        return ("publish_to_repo", "review",
                "WSL intent is ahead of the baseline; publish it.")

    if wsl == repo and repo != windows:
        return ("reconcile_windows", "review",
                "Baseline and Windows differ; Windows may need reconciliation.")

    if wsl == windows:
        return ("publish_to_repo", "review",
                "WSL and Windows agree; the baseline is stale. "
                "Publishing brings the record forward without choosing a winner.")

    return ("conflict", "conflict",
            "WSL and Windows changed independently of the baseline. "
            "No winner is chosen automatically; this requires judgment.")


def _item_kind(entry, unit_kind: str) -> str:
    if entry.kind == "tree":
        return "tree_file"
    if entry.kind in ("json", "toml"):
        return f"{entry.kind}_field"
    return unit_kind


def compare_entry(entry, units, *, has_windows: bool) -> list[DriftItem]:
    """Join one entry's units across layers and classify each key."""
    index: dict[str, dict[str, object]] = {}
    for unit in units:
        index.setdefault(unit.key, {})[unit.layer] = unit

    items: list[DriftItem] = []
    for key in sorted(index):
        by_layer = index[key]
        wsl = by_layer.get("wsl")
        repo = by_layer.get("repo")
        windows = by_layer.get("windows")
        present = [u for u in (wsl, repo, windows) if u is not None]
        first = present[0]
        item_id = f"{entry.id}:{key}" if key else entry.id
        path = next((u.path for u in (wsl, repo, windows) if u), "")
        kind = _item_kind(entry, first.kind)

        errored = [u for u in present if u.error]
        if errored:
            items.append(DriftItem(
                id=item_id, entry_id=entry.id, kind=kind,
                classification="error", severity="error",
                path=errored[0].path, policy=first.policy,
                detail=f"{errored[0].layer}: {errored[0].error}"))
            continue

        policy = next((u.policy for u in present if u.policy is not None), None)
        classification, severity, detail = classify(
            wsl.fingerprint if wsl else None,
            repo.fingerprint if repo else None,
            windows.fingerprint if windows else None,
            policy, has_windows=has_windows)

        redactions: tuple = ()
        for unit in present:
            if unit.redactions:
                redactions = tuple(unit.redactions)
                break

        items.append(DriftItem(
            id=item_id, entry_id=entry.id, kind=kind,
            classification=classification, severity=severity,
            path=path, policy=policy, detail=detail,
            wsl_fingerprint=wsl.fingerprint if wsl else None,
            repo_fingerprint=repo.fingerprint if repo else None,
            windows_fingerprint=windows.fingerprint if windows else None,
            redactions=redactions))
    return items


def compare_all(manifest, units) -> list[DriftItem]:
    """Compare every non-plugin entry. Plugins are classified by plugins.py."""
    has_windows = manifest.roots.windows_home is not None
    by_entry: dict[str, list] = {}
    for unit in units:
        by_entry.setdefault(unit.entry_id, []).append(unit)

    items: list[DriftItem] = []
    for entry in manifest.entries:
        if entry.policy == "excluded" or entry.kind == "plugins":
            continue
        items.extend(compare_entry(entry, by_entry.get(entry.id, []),
                                   has_windows=has_windows))
    return items


def counts(items) -> dict[str, int]:
    return dict(Counter(item.classification for item in items))
```

- [ ] **Step 4: Make `extract.py` skip plugin entries**

In `tools/agent-config-sync/extract.py`, inside `extract_entry`, change the guard at the top:

```python
    if root is None or entry.policy == "excluded" or entry.kind == "plugins":
        return []
```

(Plugin entries name a base *directory* with two well-known files inside it; `plugins.py` in Task 5 reads them.)

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m pytest tools/agent-config-sync/tests/test_compare.py -v`
Expected: PASS (23 tests)

- [ ] **Step 6: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/.claude_code add tools/agent-config-sync/compare.py tools/agent-config-sync/extract.py tools/agent-config-sync/tests/test_compare.py
git -C /mnt/d/Documents/Code/GitHub/.claude_code commit -m "feat(agent-config-sync): three-way comparison and classification truth table"
```

---

## Task 5: Plugin identity, enabled state, version, and pin classification

Plugin *code* is never copied. Only identities, enabled state, declared pins, and installed versions are compared, and a newer native build is never downgraded without an explicit pin.

The file shapes below were verified against the live machine on 2026-08-10:
- `~/.claude/settings.json` → `enabledPlugins: {"name@marketplace": bool}` and `extraKnownMarketplaces` — **committed** to this repo as `claude/settings.json`, so it is the portable desired state.
- `~/.claude/plugins/installed_plugins.json` → `{"version": 1, "plugins": {"name@marketplace": [{"scope", "installPath", "version", "installedAt"}]}}` — **gitignored** native runtime state, present only in the WSL and Windows layers.

**Files:**
- Create: `tools/agent-config-sync/plugins.py`
- Modify: `tools/agent-config-sync/manifest.py` (parse `[plugin_pins]` into `Manifest.pins`)
- Modify: `config/agent-sync.toml` (add the `[plugin_pins]` table)
- Test: `tools/agent-config-sync/tests/test_plugins.py`

**Interfaces:**
- Consumes: `compare.DriftItem` (Task 4); `manifest.Manifest` (Task 1).
- Produces:
  - `manifest.Manifest.pins: dict[str, str]` (new field, defaults to `{}`).
  - `plugins.PluginState(key: str, enabled: bool | None, version: str | None)` — frozen dataclass.
  - `plugins.read_layer(base: Path | None) -> tuple[dict[str, PluginState], list[str]]` — returns `(state_by_key, errors)`.
  - `plugins.parse_version(text: str | None) -> tuple[int, ...] | None`
  - `plugins.compare_versions(a: str | None, b: str | None) -> int | None` — `-1/0/1`, or `None` when incomparable.
  - `plugins.classify_plugins(desired, wsl_native, windows_native, pins, *, entry_id="claude-plugins") -> list[DriftItem]`

- [ ] **Step 1: Write the failing tests**

Create `tools/agent-config-sync/tests/test_plugins.py`:

```python
"""Tests for plugin classification.

Design: "Plugin handling"; test cases 7 (newer Windows plugin, no pin) and
8 (explicit pin violation).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import plugins as pl  # noqa: E402

KEY = "superpowers@claude-plugins-official"
OTHER = "context7@claude-plugins-official"


def build_layer(base: Path, *, enabled: dict[str, bool],
                installed: dict[str, str]) -> Path:
    base.mkdir(parents=True, exist_ok=True)
    (base / "settings.json").write_text(
        json.dumps({"enabledPlugins": enabled}), encoding="utf-8")
    if installed:
        (base / "plugins").mkdir(exist_ok=True)
        (base / "plugins" / "installed_plugins.json").write_text(json.dumps({
            "version": 1,
            "plugins": {key: [{"scope": "user", "installPath": "/x",
                               "version": version,
                               "installedAt": "2026-01-01T00:00:00Z"}]
                        for key, version in installed.items()},
        }), encoding="utf-8")
    return base


# --- reading ---------------------------------------------------------------

def test_read_layer_merges_enabled_state_and_installed_version(tmp_path: Path):
    base = build_layer(tmp_path / "wsl", enabled={KEY: True},
                       installed={KEY: "6.2.0"})
    state, errors = pl.read_layer(base)
    assert errors == []
    assert state[KEY] == pl.PluginState(key=KEY, enabled=True, version="6.2.0")


def test_read_layer_handles_a_repo_layer_with_no_installed_file(tmp_path: Path):
    base = build_layer(tmp_path / "repo", enabled={KEY: True}, installed={})
    state, errors = pl.read_layer(base)
    assert errors == []
    assert state[KEY].version is None
    assert state[KEY].enabled is True


def test_read_layer_of_a_missing_base_is_empty(tmp_path: Path):
    state, errors = pl.read_layer(tmp_path / "nope")
    assert state == {} and errors == []


def test_read_layer_of_none_is_empty():
    assert pl.read_layer(None) == ({}, [])


def test_read_layer_records_a_parse_error_without_content(tmp_path: Path):
    base = tmp_path / "bad"
    base.mkdir()
    (base / "settings.json").write_text('{"enabledPlugins": {,}} token=secret',
                                        encoding="utf-8")
    state, errors = pl.read_layer(base)
    assert state == {}
    assert len(errors) == 1
    assert "secret" not in errors[0]


def test_read_layer_picks_the_highest_version_when_scoped_twice(tmp_path: Path):
    base = tmp_path / "wsl"
    base.mkdir()
    (base / "settings.json").write_text('{"enabledPlugins": {}}',
                                        encoding="utf-8")
    (base / "plugins").mkdir()
    (base / "plugins" / "installed_plugins.json").write_text(json.dumps({
        "plugins": {KEY: [{"version": "1.0.0"}, {"version": "1.3.0"}]},
    }), encoding="utf-8")
    state, _ = pl.read_layer(base)
    assert state[KEY].version == "1.3.0"


# --- version comparison ----------------------------------------------------

def test_parse_version_handles_dotted_integers():
    assert pl.parse_version("6.2.0") == (6, 2, 0)
    assert pl.parse_version("6.2") == (6, 2)


def test_parse_version_rejects_non_numeric():
    assert pl.parse_version("v6.2.0-beta") is None
    assert pl.parse_version(None) is None


def test_compare_versions_orders_numerically_not_lexically():
    assert pl.compare_versions("6.10.0", "6.9.0") == 1
    assert pl.compare_versions("6.2.0", "6.2.0") == 0
    assert pl.compare_versions("1.0", "1.0.0") == 0


def test_compare_versions_returns_none_when_incomparable():
    assert pl.compare_versions("6.2.0", "nightly") is None


# --- classification --------------------------------------------------------

def state(key=KEY, enabled=True, version=None) -> dict[str, pl.PluginState]:
    return {key: pl.PluginState(key=key, enabled=enabled, version=version)}


def test_desired_plugin_absent_from_a_native_manager_is_missing():
    items = pl.classify_plugins(state(), {}, {}, {})
    kinds = {(i.classification, i.severity) for i in items}
    assert ("plugin_missing", "review") in kinds
    assert all(i.kind == "plugin" for i in items)


def test_native_plugin_not_in_the_record_is_extra_and_only_informational():
    items = pl.classify_plugins({}, state(), {}, {})
    assert [(i.classification, i.severity) for i in items] == [
        ("plugin_extra", "info")]


def test_enabled_state_difference_is_reported_per_layer():
    items = pl.classify_plugins(state(enabled=True),
                                state(enabled=False, version="6.2.0"),
                                state(enabled=True, version="6.2.0"), {})
    differing = [i for i in items if i.classification == "plugin_enabled_differs"]
    assert len(differing) == 1
    assert differing[0].id.endswith("#enabled:wsl")


def test_newer_native_version_without_a_pin_is_preserved_not_downgraded():
    # Design test case 7: Windows has a newer build than WSL.
    items = pl.classify_plugins(state(), state(version="6.1.0"),
                                state(version="6.2.0"), {})
    version_items = [i for i in items
                     if i.classification == "plugin_version_differs"]
    assert len(version_items) == 1
    detail = version_items[0].detail
    assert "windows" in detail and "6.2.0" in detail
    assert "downgrade" not in detail.lower()
    assert "upgrade" in detail.lower()
    assert version_items[0].id.endswith("#version")


def test_matching_versions_produce_no_version_item():
    items = pl.classify_plugins(state(), state(version="6.2.0"),
                                state(version="6.2.0"), {})
    assert not [i for i in items if i.classification == "plugin_version_differs"]


def test_incomparable_versions_are_reported_as_incompatible():
    items = pl.classify_plugins(state(), state(version="nightly"),
                                state(version="6.2.0"), {})
    assert any(i.classification == "plugin_incompatible" for i in items)


def test_pin_violation_is_a_conflict():
    # Design test case 8.
    items = pl.classify_plugins(state(), state(version="6.1.0"),
                                state(version="6.2.0"), {KEY: "6.2.0"})
    violations = [i for i in items if i.classification == "plugin_pin_violation"]
    assert len(violations) == 1
    assert violations[0].severity == "conflict"
    assert violations[0].id.endswith("#pin:wsl")
    assert "6.2.0" in violations[0].detail


def test_a_satisfied_pin_produces_no_item():
    items = pl.classify_plugins(state(), state(version="6.2.0"),
                                state(version="6.2.0"), {KEY: "6.2.0"})
    assert not [i for i in items if i.classification == "plugin_pin_violation"]


def test_item_ids_are_stable_and_namespaced():
    items = pl.classify_plugins(state(), {}, {}, {})
    assert items[0].id == f"claude-plugins:{KEY}"
    assert items[0].entry_id == "claude-plugins"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest tools/agent-config-sync/tests/test_plugins.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'plugins'`

- [ ] **Step 3: Add `pins` to `manifest.py`**

Add the field to the `Manifest` dataclass (after `secrets`):

```python
    pins: dict[str, str] = field(default_factory=dict)
```

And in `load_manifest`, just before the `return Manifest(...)`, read the table and pass it:

```python
    pins = dict(data.get("plugin_pins", {}))
```

then add `pins=pins,` to the `Manifest(...)` call.

- [ ] **Step 4: Add the pins table to `config/agent-sync.toml`**

Append to the end of `config/agent-sync.toml`:

```toml
# ---------------------------------------------------------------------------
# Explicit plugin version pins. A pin -- and only a pin -- authorizes a
# downgrade. Empty by default: newer native builds are preserved.
# Format: "<plugin>@<marketplace>" = "<exact version>"
# ---------------------------------------------------------------------------

[plugin_pins]
```

- [ ] **Step 5: Implement `plugins.py`**

Create `tools/agent-config-sync/plugins.py`:

```python
#!/usr/bin/env python3
"""Plugin identity, enabled state, version, and pin classification.

Plugin caches and downloaded plugin code are never read or copied. Only the
declarative surface is compared:

  <base>/settings.json                  enabledPlugins {"name@market": bool}
  <base>/plugins/installed_plugins.json {"plugins": {"name@market": [{...}]}}

A newer compatible native build is preserved unless an explicit pin exists.

Design: "Plugin handling".
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from compare import DriftItem

ENTRY_ID = "claude-plugins"


@dataclass(frozen=True)
class PluginState:
    key: str
    enabled: bool | None = None
    version: str | None = None


def _load_json(path: Path, errors: list[str]) -> dict:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"{path.name}: invalid JSON at line {exc.lineno}, "
                      f"column {exc.colno}")
        return {}
    except (UnicodeDecodeError, OSError) as exc:
        errors.append(f"{path.name}: unreadable ({type(exc).__name__})")
        return {}
    return data if isinstance(data, dict) else {}


def read_layer(base: Path | None) -> tuple[dict[str, PluginState], list[str]]:
    """Declarative plugin state for one layer, plus any parse errors."""
    errors: list[str] = []
    if base is None or not Path(base).is_dir():
        return {}, errors
    base = Path(base)

    settings = _load_json(base / "settings.json", errors)
    enabled_map = settings.get("enabledPlugins", {})
    if not isinstance(enabled_map, dict):
        enabled_map = {}

    installed = _load_json(base / "plugins" / "installed_plugins.json", errors)
    raw_plugins = installed.get("plugins", {})
    versions: dict[str, str] = {}
    if isinstance(raw_plugins, dict):
        for key, records in raw_plugins.items():
            if not isinstance(records, list):
                continue
            found = [r.get("version") for r in records
                     if isinstance(r, dict) and r.get("version")]
            if found:
                versions[key] = max(found, key=lambda v: (parse_version(v) or (), v))

    state: dict[str, PluginState] = {}
    for key in sorted(set(enabled_map) | set(versions)):
        value = enabled_map.get(key)
        state[key] = PluginState(
            key=key,
            enabled=bool(value) if isinstance(value, bool) else None,
            version=versions.get(key),
        )
    return state, errors


# --------------------------------------------------------------------------
# versions
# --------------------------------------------------------------------------

def parse_version(text: str | None) -> tuple[int, ...] | None:
    if not text:
        return None
    parts = text.split(".")
    if not all(part.isdigit() for part in parts):
        return None
    return tuple(int(part) for part in parts)


def compare_versions(a: str | None, b: str | None) -> int | None:
    left, right = parse_version(a), parse_version(b)
    if left is None or right is None:
        return None
    width = max(len(left), len(right))
    left += (0,) * (width - len(left))
    right += (0,) * (width - len(right))
    return (left > right) - (left < right)


# --------------------------------------------------------------------------
# classification
# --------------------------------------------------------------------------

def _item(key: str, suffix: str, classification: str, severity: str,
          detail: str) -> DriftItem:
    return DriftItem(
        id=f"{ENTRY_ID}:{key}{suffix}",
        entry_id=ENTRY_ID,
        kind="plugin",
        classification=classification,
        severity=severity,
        path=key,
        policy="portable_authoritative",
        detail=detail,
    )


def classify_plugins(desired, wsl_native, windows_native, pins,
                     *, entry_id: str = ENTRY_ID) -> list[DriftItem]:
    """Compare the portable record against both native managers."""
    items: list[DriftItem] = []
    natives = (("wsl", wsl_native), ("windows", windows_native))
    all_keys = sorted(set(desired) | set(wsl_native) | set(windows_native))

    for key in all_keys:
        want = desired.get(key)

        if want is None:
            items.append(_item(
                key, "", "plugin_extra", "info",
                "Installed natively but absent from the portable record. "
                "No action proposed; add it to the record if it is intended."))
            continue

        for layer, native in natives:
            if not native:
                continue
            have = native.get(key)
            if have is None:
                items.append(_item(
                    key, f"#missing:{layer}", "plugin_missing", "review",
                    f"Desired plugin is not installed on {layer}. Install it "
                    f"with the native manager: claude plugin install {key}"))
                continue
            if want.enabled is not None and have.enabled is not None \
                    and want.enabled != have.enabled:
                verb = "enable" if want.enabled else "disable"
                items.append(_item(
                    key, f"#enabled:{layer}", "plugin_enabled_differs", "review",
                    f"Record says enabled={want.enabled}, {layer} says "
                    f"enabled={have.enabled}. Reconcile with: "
                    f"claude plugin {verb} {key}"))

            pin = pins.get(key)
            if pin and have.version and have.version != pin:
                items.append(_item(
                    key, f"#pin:{layer}", "plugin_pin_violation", "conflict",
                    f"Explicit pin {pin} but {layer} has {have.version}. "
                    f"A pin is the only thing that authorizes a downgrade; "
                    f"approve before acting."))

        wsl_version = (wsl_native.get(key).version
                       if wsl_native.get(key) else None)
        win_version = (windows_native.get(key).version
                       if windows_native.get(key) else None)
        if wsl_version and win_version and wsl_version != win_version:
            if pins.get(key):
                continue  # already reported as a pin violation above
            order = compare_versions(wsl_version, win_version)
            if order is None:
                items.append(_item(
                    key, "#version", "plugin_incompatible", "review",
                    f"Versions are not comparable (wsl={wsl_version}, "
                    f"windows={win_version}); resolve by hand."))
            else:
                newer, older = ("wsl", "windows") if order > 0 else ("windows", "wsl")
                newest = wsl_version if order > 0 else win_version
                oldest = win_version if order > 0 else wsl_version
                items.append(_item(
                    key, "#version", "plugin_version_differs", "review",
                    f"{newer} has {newest}, {older} has {oldest}. The newer "
                    f"build is preserved; upgrade {older} with: "
                    f"claude plugin update {key}"))
    return items
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `python3 -m pytest tools/agent-config-sync/tests/test_plugins.py -v`
Expected: PASS (19 tests)

- [ ] **Step 7: Run the whole suite**

Run: `python3 -m pytest tools/agent-config-sync/tests/ -v`
Expected: PASS (all tests from Tasks 1–5)

- [ ] **Step 8: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/.claude_code add tools/agent-config-sync/plugins.py tools/agent-config-sync/manifest.py config/agent-sync.toml tools/agent-config-sync/tests/test_plugins.py
git -C /mnt/d/Documents/Code/GitHub/.claude_code commit -m "feat(agent-config-sync): plugin identity, enabled, version, and pin classification"
```

---

## Task 6: Drift document, atomic writes, process lock, and the `scan.py` CLI

**Files:**
- Create: `tools/agent-config-sync/drift.py`
- Create: `tools/agent-config-sync/scan.py`
- Test: `tools/agent-config-sync/tests/test_scan.py`

**Interfaces:**
- Consumes: everything from Tasks 1–5.
- Produces:
  - `drift.DRIFT_SCHEMA_VERSION = 1`, `drift.SCANNER_VERSION = "1.0.0"`
  - `drift.make_run_id(now: datetime, entropy: str) -> str` — e.g. `2026-08-10T14-03-22Z-3f9a1c`
  - `drift.layer_fingerprint(units, layer: str) -> str`
  - `drift.build_document(manifest, items, errors, *, now, entropy, units) -> dict`
  - `drift.validate_document(doc) -> list[str]`
  - `drift.has_actionable(doc) -> bool`
  - `drift.write_atomic(path: Path, text: str) -> None`
  - `scan.LockHeld(RuntimeError)`, `scan.acquire_lock(state_dir: Path)` (context manager)
  - `scan.run_scan(manifest_path, *, root_overrides, now, entropy) -> dict`
  - `scan.main(argv: list[str] | None = None) -> int`
  - Exit codes: `EXIT_OK = 0`, `EXIT_DRIFT = 10`, `EXIT_SCAN_FAILURE = 20`, `EXIT_LOCKED = 21`

- [ ] **Step 1: Write the failing tests**

Create `tools/agent-config-sync/tests/test_scan.py`:

```python
"""Tests for the drift document, atomic writes, the lock, and the scan CLI.

Design: "Deterministic scan"; test cases 1 (no drift) and 15 (interrupted
atomic write).
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import drift  # noqa: E402
import scan  # noqa: E402

NOW = datetime(2026, 8, 10, 14, 3, 22, tzinfo=timezone.utc)

MANIFEST_TEMPLATE = """
schema_version = 1

[roots]
wsl_home = "{wsl}"
repo = "{repo}"
windows_home = "{windows}"

[state]
dir = "{state}"

[secrets]
deny_key_patterns = ["(?i)token"]
deny_path_globs = ["**/history.jsonl"]

[[entries]]
id = "agents-md"
policy = "portable_authoritative"
kind = "text"
wsl = "AGENTS.md"
repo = "AGENTS.md"
windows = "AGENTS.md"
"""


@pytest.fixture
def scene(fixture_roots, tmp_path: Path):
    """A manifest wired to the fixture roots. Returns (manifest_path, roots)."""
    text = MANIFEST_TEMPLATE.format(
        wsl=fixture_roots.wsl, repo=fixture_roots.repo,
        windows=fixture_roots.windows, state=fixture_roots.state)
    path = tmp_path / "agent-sync.toml"
    path.write_text(text, encoding="utf-8")
    return path, fixture_roots


def seed(roots, *, wsl=None, repo=None, windows=None) -> None:
    for layer, content in (("wsl", wsl), ("repo", repo), ("windows", windows)):
        if content is not None:
            roots.write(getattr(roots, layer), "AGENTS.md", content)


# --- run ids and fingerprints ---------------------------------------------

def test_run_id_is_deterministic_and_filename_safe():
    run_id = drift.make_run_id(NOW, "3f9a1c")
    assert run_id == "2026-08-10T14-03-22Z-3f9a1c"
    assert "/" not in run_id and ":" not in run_id


# --- atomic writes (design test case 15) -----------------------------------

def test_write_atomic_replaces_content(tmp_path: Path):
    target = tmp_path / "out.json"
    drift.write_atomic(target, "first\n")
    drift.write_atomic(target, "second\n")
    assert target.read_text(encoding="utf-8") == "second\n"


def test_write_atomic_leaves_no_temp_files_behind(tmp_path: Path):
    target = tmp_path / "out.json"
    drift.write_atomic(target, "x\n")
    assert [p.name for p in tmp_path.iterdir()] == ["out.json"]


def test_interrupted_write_preserves_the_previous_file(tmp_path: Path,
                                                       monkeypatch):
    target = tmp_path / "out.json"
    drift.write_atomic(target, "good\n")

    def boom(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(drift.os, "replace", boom)
    with pytest.raises(OSError):
        drift.write_atomic(target, "bad\n")
    assert target.read_text(encoding="utf-8") == "good\n"
    assert [p.name for p in tmp_path.iterdir()] == ["out.json"]


# --- document assembly -----------------------------------------------------

def test_document_validates_against_its_own_schema(scene):
    manifest_path, roots = scene
    seed(roots, wsl="a\n", repo="b\n", windows="b\n")
    doc = scan.run_scan(manifest_path, root_overrides=None, now=NOW,
                        entropy="3f9a1c")
    assert drift.validate_document(doc) == []
    assert doc["drift_schema_version"] == drift.DRIFT_SCHEMA_VERSION
    assert doc["scanner_version"] == drift.SCANNER_VERSION
    assert doc["run_id"] == "2026-08-10T14-03-22Z-3f9a1c"


def test_identical_layers_produce_no_actionable_drift(scene):
    manifest_path, roots = scene
    seed(roots, wsl="same\n", repo="same\n", windows="same\n")
    doc = scan.run_scan(manifest_path, root_overrides=None, now=NOW,
                        entropy="x")
    assert drift.has_actionable(doc) is False
    assert doc["counts"].get("publish_to_repo") is None


def test_wsl_ahead_of_the_baseline_is_actionable(scene):
    manifest_path, roots = scene
    seed(roots, wsl="new\n", repo="old\n", windows="old\n")
    doc = scan.run_scan(manifest_path, root_overrides=None, now=NOW,
                        entropy="x")
    assert drift.has_actionable(doc) is True
    assert doc["counts"]["publish_to_repo"] == 1
    assert doc["items"][0]["id"] == "agents-md"


def test_line_ending_differences_alone_are_not_drift(scene):
    manifest_path, roots = scene
    seed(roots, wsl="a\r\nb\r\n", repo="a\nb\n", windows="a\nb\n")
    doc = scan.run_scan(manifest_path, root_overrides=None, now=NOW,
                        entropy="x")
    assert drift.has_actionable(doc) is False


def test_document_records_layer_fingerprints_for_staleness_checks(scene):
    manifest_path, roots = scene
    seed(roots, wsl="a\n", repo="a\n", windows="a\n")
    doc = scan.run_scan(manifest_path, root_overrides=None, now=NOW,
                        entropy="x")
    assert set(doc["layer_fingerprints"]) == {"wsl", "repo", "windows"}
    assert all(len(v) == 64 for v in doc["layer_fingerprints"].values())


def test_no_secret_value_reaches_the_document(scene, tmp_path: Path):
    manifest_path, roots = scene
    extra = manifest_path.read_text(encoding="utf-8") + """
[[entries]]
id = "mcp"
policy = "portable_authoritative"
kind = "json"
wsl = "mcp.json"
repo = "mcp.json"
"""
    manifest_path.write_text(extra, encoding="utf-8")
    seed(roots, wsl="x\n", repo="x\n", windows="x\n")
    roots.write(roots.wsl, "mcp.json",
                '{"mcpServers": {"gh": {"token": "ghp_LEAKME"}}}')
    doc = scan.run_scan(manifest_path, root_overrides=None, now=NOW,
                        entropy="x")
    assert "ghp_LEAKME" not in json.dumps(doc)
    assert doc["redactions"], "the redaction must be recorded"


# --- lock ------------------------------------------------------------------

def test_lock_is_exclusive(fixture_roots):
    with scan.acquire_lock(fixture_roots.state):
        with pytest.raises(scan.LockHeld):
            with scan.acquire_lock(fixture_roots.state):
                pass


def test_lock_is_released_on_exit(fixture_roots):
    with scan.acquire_lock(fixture_roots.state):
        pass
    with scan.acquire_lock(fixture_roots.state):
        pass


# --- CLI -------------------------------------------------------------------

def test_cli_exits_zero_when_there_is_no_drift(scene, capsys):
    manifest_path, roots = scene
    seed(roots, wsl="s\n", repo="s\n", windows="s\n")
    code = scan.main(["--manifest", str(manifest_path)])
    assert code == scan.EXIT_OK


def test_cli_exits_ten_when_drift_exists_and_writes_the_document(scene):
    manifest_path, roots = scene
    seed(roots, wsl="new\n", repo="old\n", windows="old\n")
    out = roots.state / "drift.json"
    code = scan.main(["--manifest", str(manifest_path), "--out", str(out)])
    assert code == scan.EXIT_DRIFT
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert drift.validate_document(doc) == []


def test_cli_exits_twenty_on_a_malformed_manifest(tmp_path: Path):
    bad = tmp_path / "agent-sync.toml"
    bad.write_text("[roots\n", encoding="utf-8")
    assert scan.main(["--manifest", str(bad)]) == scan.EXIT_SCAN_FAILURE


def test_cli_writes_latest_status_json(scene):
    manifest_path, roots = scene
    seed(roots, wsl="s\n", repo="s\n", windows="s\n")
    scan.main(["--manifest", str(manifest_path)])
    status = json.loads(
        (roots.state / "latest-status.json").read_text(encoding="utf-8"))
    assert status["actionable"] is False
    assert status["exit_code"] == scan.EXIT_OK
    assert status["scanner_version"] == drift.SCANNER_VERSION


def test_cli_root_override_flag(scene, tmp_path: Path):
    manifest_path, roots = scene
    alternate = tmp_path / "alt-wsl"
    alternate.mkdir()
    (alternate / "AGENTS.md").write_text("override\n", encoding="utf-8")
    seed(roots, repo="baseline\n", windows="baseline\n")
    out = roots.state / "drift.json"
    scan.main(["--manifest", str(manifest_path), "--out", str(out),
               "--root", f"wsl_home={alternate}"])
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["roots"]["wsl"] == str(alternate)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest tools/agent-config-sync/tests/test_scan.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'drift'`

- [ ] **Step 3: Implement `drift.py`**

Create `tools/agent-config-sync/drift.py`:

```python
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
```

- [ ] **Step 4: Implement `scan.py`**

Create `tools/agent-config-sync/scan.py`:

```python
#!/usr/bin/env python3
"""Deterministic scan: no model is ever invoked from this module.

    scan.py --manifest config/agent-sync.toml [--out FILE] [--root k=v]...

Exit codes: 0 no drift, 10 drift reported, 20 scan failure, 21 lock held.

Design: "Deterministic scan", "Scheduling".
"""
from __future__ import annotations

import argparse
import contextlib
import fcntl
import json
import secrets as _secrets
import sys
from datetime import datetime, timezone
from pathlib import Path

import compare
import drift
import extract
import manifest as mf
import plugins as pl

EXIT_OK = 0
EXIT_DRIFT = 10
EXIT_SCAN_FAILURE = 20
EXIT_LOCKED = 21


class LockHeld(RuntimeError):
    """Another scan is already running."""


@contextlib.contextmanager
def acquire_lock(state_dir: Path):
    state_dir = Path(state_dir)
    state_dir.mkdir(parents=True, exist_ok=True)
    lock_path = state_dir / "scan.lock"
    handle = lock_path.open("w")
    try:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise LockHeld(f"another scan holds {lock_path}") from exc
        yield handle
    finally:
        with contextlib.suppress(OSError):
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


def run_scan(manifest_path, *, root_overrides, now: datetime,
             entropy: str) -> dict:
    m = mf.load_manifest(Path(manifest_path), root_overrides=root_overrides)

    units: list = []
    for entry in m.entries:
        for layer in extract.LAYERS:
            root = m.roots.for_layer(layer)
            units.extend(
                extract.extract_entry(entry, layer, root, m.secrets, m.roots))

    items = compare.compare_all(m, units)

    errors: list[dict] = []
    plugin_entries = [e for e in m.entries if e.kind == "plugins"]
    if plugin_entries:
        entry = plugin_entries[0]
        states: dict[str, dict] = {}
        for layer in extract.LAYERS:
            root = m.roots.for_layer(layer)
            rel = entry.rel_for_layer(layer)
            base = Path(root) / rel if (root and rel) else None
            state, layer_errors = pl.read_layer(base)
            states[layer] = state
            errors.extend({"path": f"{layer}:{entry.id}", "message": message}
                          for message in layer_errors)
        items.extend(pl.classify_plugins(
            states["repo"], states["wsl"], states["windows"], m.pins))

    for item in items:
        if item.classification == "error":
            errors.append({"path": item.path, "message": item.detail})

    return drift.build_document(m, items, errors, now=now, entropy=entropy,
                                units=units)


def _parse_args(argv):
    parser = argparse.ArgumentParser(
        prog="scan.py", description="Deterministic agent-config drift scan.")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--out", type=Path,
                        help="drift document path "
                             "(default: <state-dir>/latest-drift.json)")
    parser.add_argument("--state-dir", type=Path)
    parser.add_argument("--root", action="append", default=[],
                        metavar="KEY=VALUE",
                        help="override a manifest root, e.g. wsl_home=/tmp/x")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = _parse_args(argv)
    overrides = {}
    for pair in args.root:
        key, _, value = pair.partition("=")
        if not value:
            print(f"scan: --root expects KEY=VALUE, got {pair!r}",
                  file=sys.stderr)
            return EXIT_SCAN_FAILURE
        overrides[key] = value

    try:
        loaded = mf.load_manifest(args.manifest, root_overrides=overrides)
    except mf.ManifestError as exc:
        print(f"scan: {exc}", file=sys.stderr)
        return EXIT_SCAN_FAILURE

    state_dir = args.state_dir or loaded.state_dir
    out = args.out or (state_dir / "latest-drift.json")
    now = datetime.now(timezone.utc)
    entropy = _secrets.token_hex(3)

    try:
        with acquire_lock(state_dir):
            doc = run_scan(args.manifest, root_overrides=overrides, now=now,
                           entropy=entropy)
            problems = drift.validate_document(doc)
            if problems:
                print("scan: drift document failed its own schema:",
                      file=sys.stderr)
                for problem in problems[:10]:
                    print(f"  {problem}", file=sys.stderr)
                return EXIT_SCAN_FAILURE
            drift.write_atomic(out, drift.dump(doc))
            code = EXIT_DRIFT if drift.has_actionable(doc) else EXIT_OK
            drift.write_atomic(state_dir / "latest-status.json", json.dumps({
                "run_id": doc["run_id"],
                "generated_at": doc["generated_at"],
                "scanner_version": doc["scanner_version"],
                "actionable": drift.has_actionable(doc),
                "counts": doc["counts"],
                "drift_document": str(out),
                "exit_code": code,
            }, indent=2, sort_keys=True) + "\n")
            return code
    except LockHeld as exc:
        print(f"scan: {exc}", file=sys.stderr)
        return EXIT_LOCKED
    except (mf.ManifestError, OSError) as exc:
        print(f"scan: {type(exc).__name__}: {exc}", file=sys.stderr)
        return EXIT_SCAN_FAILURE


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m pytest tools/agent-config-sync/tests/test_scan.py -v`
Expected: PASS (16 tests)

- [ ] **Step 6: Smoke-run the scanner against the real machine, read-only**

This is the first time the tool touches live paths. It only reads.

```bash
python3 /mnt/d/Documents/Code/GitHub/.claude_code/tools/agent-config-sync/scan.py \
  --manifest /mnt/d/Documents/Code/GitHub/.claude_code/config/agent-sync.toml \
  --out /tmp/claude-1000/drift-smoke.json
echo "exit=$?"
python3 -c "
import json; d=json.load(open('/tmp/claude-1000/drift-smoke.json'))
print('counts:', d['counts']); print('errors:', len(d['errors']))
print('redactions:', len(d['redactions']))
for i in d['items'][:15]: print(' ', i['classification'], i['id'])
"
```

Verify by reading the output: exit is `0` or `10` (never `20`), no value that looks like a credential appears, and the classifications are plausible for this machine. If `errors` is large, the manifest paths need adjusting — fix `config/agent-sync.toml`, not the scanner.

- [ ] **Step 7: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/.claude_code add tools/agent-config-sync/drift.py tools/agent-config-sync/scan.py tools/agent-config-sync/tests/test_scan.py config/agent-sync.toml
git -C /mnt/d/Documents/Code/GitHub/.claude_code commit -m "feat(agent-config-sync): drift document, process lock, and scan CLI"
```

---

## Task 7: Deterministic Markdown renderer

The model never writes the report. It returns structured judgment; this module renders it. That is what makes an invalid model response unable to replace a good report.

**Files:**
- Create: `tools/agent-config-sync/render.py`
- Create: `tools/agent-config-sync/tests/golden/report-basic.md` (generated in Step 5, then reviewed)
- Test: `tools/agent-config-sync/tests/test_render.py`

**Interfaces:**
- Consumes: the drift document (Task 6).
- Produces:
  - `render.REPORT_TEMPLATE_VERSION = 1`
  - `render.render_markdown(doc: dict, analysis: dict) -> str`
  - `render.empty_analysis() -> dict` — the neutral analysis used when no model ran
  - `render.SECTIONS: tuple[str, ...]` — the required H2 headings, in order

**Analysis shape** (produced by Task 8's model call, consumed here):

```json
{
  "response_schema_version": 1,
  "summary": "one paragraph",
  "severity": "none|review|conflict",
  "recommended_order": ["agents-md", "claude-settings:model"],
  "notes": [{"item_id": "agents-md", "note": "why this one matters"}],
  "codex_review_recommended": false,
  "codex_reason": ""
}
```

- [ ] **Step 1: Write the failing tests**

Create `tools/agent-config-sync/tests/test_render.py`:

```python
"""Tests for deterministic Markdown rendering.

Design: "Report format". The renderer is deterministic so that an invalid or
partial model response can never replace the last valid report.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import render as rd  # noqa: E402

GOLDEN = Path(__file__).resolve().parent / "golden" / "report-basic.md"

DOC = {
    "drift_schema_version": 1,
    "run_id": "2026-08-10T14-03-22Z-3f9a1c",
    "generated_at": "2026-08-10T14:03:22+00:00",
    "scanner_version": "1.0.0",
    "manifest_version": 1,
    "roots": {"wsl": "/home/leland", "repo": "/repo", "windows": "/mnt/c/Users/aboog"},
    "layer_fingerprints": {"wsl": "a" * 64, "repo": "b" * 64, "windows": "c" * 64},
    "counts": {"publish_to_repo": 1, "conflict": 1, "protected_overlay": 1,
               "plugin_version_differs": 1},
    "items": [
        {"id": "agents-md", "entry_id": "agents-md", "kind": "text",
         "classification": "publish_to_repo", "severity": "review",
         "path": ".config/agents/AGENTS.md", "policy": "portable_authoritative",
         "detail": "WSL intent is ahead of the baseline; publish it.",
         "wsl_fingerprint": "d" * 64, "repo_fingerprint": "e" * 64},
        {"id": "claude-settings:model", "entry_id": "claude-settings",
         "kind": "json_field", "classification": "conflict",
         "severity": "conflict", "path": ".claude/settings.json",
         "policy": "portable_authoritative",
         "detail": "WSL and Windows changed independently of the baseline."},
        {"id": "claude-settings:statusLine.command",
         "entry_id": "claude-settings", "kind": "json_field",
         "classification": "protected_overlay", "severity": "info",
         "path": ".claude/settings.json", "policy": "platform_overlay",
         "detail": "Windows owns this value; preserved and reported only."},
        {"id": "claude-plugins:superpowers@claude-plugins-official#version",
         "entry_id": "claude-plugins", "kind": "plugin",
         "classification": "plugin_version_differs", "severity": "review",
         "path": "superpowers@claude-plugins-official",
         "policy": "portable_authoritative",
         "detail": "windows has 6.2.0, wsl has 6.1.0. The newer build is "
                   "preserved; upgrade wsl."},
    ],
    "redactions": [{"pointer": "mcpServers.gh.env.GITHUB_TOKEN",
                    "reason": "secret_key_pattern", "value_type": "str",
                    "value_fingerprint": "f" * 64}],
    "errors": [{"path": ".codex/config.toml", "message": "invalid TOML at line 12"}],
}

ANALYSIS = {
    "response_schema_version": 1,
    "summary": "One portable update is safe; the settings model field needs a "
               "decision.",
    "severity": "conflict",
    "recommended_order": ["agents-md", "claude-settings:model"],
    "notes": [{"item_id": "claude-settings:model",
               "note": "Both sides edited the model pin since the baseline."}],
    "codex_review_recommended": True,
    "codex_reason": "An ambiguous semantic merge in a settings field.",
}


def test_every_required_section_is_present_in_order():
    out = rd.render_markdown(DOC, ANALYSIS)
    positions = [out.index(f"## {name}") for name in rd.SECTIONS]
    assert positions == sorted(positions)


def test_header_carries_every_version_and_fingerprint():
    out = rd.render_markdown(DOC, ANALYSIS)
    for needle in ("2026-08-10T14-03-22Z-3f9a1c", "scanner 1.0.0",
                   "manifest 1", "drift schema 1",
                   f"template {rd.REPORT_TEMPLATE_VERSION}",
                   "aaaaaaaaaaaa", "bbbbbbbbbbbb", "cccccccccccc"):
        assert needle in out, needle


def test_items_are_listed_under_their_section_with_stable_ids():
    out = rd.render_markdown(DOC, ANALYSIS)
    safe = out.split("## Safe portable updates")[1].split("## ")[0]
    assert "`agents-md`" in safe
    conflicts = out.split("## Conflicts requiring judgment")[1].split("## ")[0]
    assert "`claude-settings:model`" in conflicts
    assert "`agents-md`" not in conflicts


def test_protected_windows_state_is_its_own_section_and_not_actionable():
    out = rd.render_markdown(DOC, ANALYSIS)
    protected = out.split("## Protected Windows state")[1].split("## ")[0]
    assert "statusLine.command" in protected
    safe = out.split("## Safe portable updates")[1].split("## ")[0]
    assert "statusLine.command" not in safe


def test_plugin_differences_get_their_own_section():
    out = rd.render_markdown(DOC, ANALYSIS)
    section = out.split("## Plugin differences")[1].split("## ")[0]
    assert "superpowers@claude-plugins-official" in section
    assert "6.2.0" in section


def test_redactions_show_reason_codes_and_never_values():
    out = rd.render_markdown(DOC, ANALYSIS)
    section = out.split("## Excluded and redacted")[1].split("## ")[0]
    assert "secret_key_pattern" in section
    assert "GITHUB_TOKEN" in section          # the NAME may be recorded
    assert "f" * 64 not in section            # the hash is truncated, not raw
    assert "ffffffffffff" in section


def test_model_notes_are_attached_to_their_items():
    out = rd.render_markdown(DOC, ANALYSIS)
    assert "Both sides edited the model pin" in out


def test_recommended_merge_order_is_rendered_as_a_numbered_list():
    out = rd.render_markdown(DOC, ANALYSIS)
    section = out.split("## Recommended merge order")[1].split("## ")[0]
    assert "1. `agents-md`" in section
    assert "2. `claude-settings:model`" in section


def test_handoff_prompt_names_the_merge_skill_and_the_run_id():
    out = rd.render_markdown(DOC, ANALYSIS)
    section = out.split("## Claude handoff prompt")[1].split("## ")[0]
    assert "agent-config-merge" in section
    assert "2026-08-10T14-03-22Z-3f9a1c" in section


def test_codex_prompt_appears_only_when_recommended():
    with_codex = rd.render_markdown(DOC, ANALYSIS)
    assert "## Independent review (/codex)" in with_codex
    quiet = dict(ANALYSIS, codex_review_recommended=False)
    assert "## Independent review (/codex)" not in rd.render_markdown(DOC, quiet)


def test_errors_are_reported_with_location_only():
    out = rd.render_markdown(DOC, ANALYSIS)
    assert "invalid TOML at line 12" in out
    assert ".codex/config.toml" in out


def test_empty_analysis_renders_without_a_model():
    out = rd.render_markdown(DOC, rd.empty_analysis())
    assert "no model analysis" in out.lower()
    assert "## Safe portable updates" in out


def test_rendering_is_deterministic():
    assert rd.render_markdown(DOC, ANALYSIS) == rd.render_markdown(DOC, ANALYSIS)


def test_matches_the_golden_report():
    expected = GOLDEN.read_text(encoding="utf-8")
    actual = rd.render_markdown(DOC, ANALYSIS)
    if os.environ.get("UPDATE_GOLDEN") == "1":
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_text(actual, encoding="utf-8")
        expected = actual
    assert actual == expected
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest tools/agent-config-sync/tests/test_render.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'render'`

- [ ] **Step 3: Implement `render.py`**

Create `tools/agent-config-sync/render.py`:

```python
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
        add(f"/codex:review --base HEAD")
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
```

- [ ] **Step 4: Run the assertion tests (the golden test will still fail)**

Run: `python3 -m pytest tools/agent-config-sync/tests/test_render.py -v -k "not golden"`
Expected: PASS (13 tests)

- [ ] **Step 5: Generate the golden report, then read it**

```bash
UPDATE_GOLDEN=1 python3 -m pytest tools/agent-config-sync/tests/test_render.py -k golden -q
```

Now **read** `tools/agent-config-sync/tests/golden/report-basic.md` end to end. It is a review artifact, not just a fixture: confirm every section from design §Report format is present, the tone is usable as a handoff, and no value that looks like a secret appears. Fix `render.py` and regenerate if anything reads wrong.

- [ ] **Step 6: Run the full render suite**

Run: `python3 -m pytest tools/agent-config-sync/tests/test_render.py -v`
Expected: PASS (14 tests)

- [ ] **Step 7: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/.claude_code add tools/agent-config-sync/render.py tools/agent-config-sync/tests/test_render.py tools/agent-config-sync/tests/golden/report-basic.md
git -C /mnt/d/Documents/Code/GitHub/.claude_code commit -m "feat(agent-config-sync): deterministic Markdown report renderer"
```

---

## Task 8: Bounded `claude -p` analyzer and response validation

**Files:**
- Create: `tools/agent-config-sync/analyze.py`
- Create: `tools/agent-config-sync/schemas/response-v1.json`
- Create: `tools/agent-config-sync/prompts/report-v1.md`
- Modify: `tools/agent-config-sync/render.py` (add the `render.py` CLI entry point)
- Test: `tools/agent-config-sync/tests/test_analyze.py`

**Interfaces:**
- Consumes: the drift document (Task 6); `render.render_markdown` (Task 7); `schema.validate` (Task 1).
- Produces:
  - `analyze.RESPONSE_SCHEMA_VERSION = 1`, `analyze.PROMPT_VERSION = "report-v1"`
  - `analyze.AnalysisError(RuntimeError)`
  - `analyze.build_command(claude_bin: str, *, max_turns: int) -> list[str]`
  - `analyze.build_prompt(doc: dict, prompt_path: Path) -> str`
  - `analyze.extract_json(stdout: str) -> dict`
  - `analyze.validate_analysis(obj: dict) -> list[str]`
  - `analyze.run(doc, *, claude_bin, prompt_path, timeout_s, max_turns) -> dict`
  - `render.main(argv) -> int` with exit code `30` (`EXIT_MODEL_FAILURE`) on invalid analysis

- [ ] **Step 1: Write the failing tests**

Create `tools/agent-config-sync/tests/test_analyze.py`:

```python
"""Tests for the bounded claude -p wrapper.

A stub executable stands in for claude, so no network, subscription, or live
model is involved. Design: "Claude-first report generation"; test case 14
(invalid, incomplete, or timed-out model output).
"""
from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import analyze as az  # noqa: E402

VALID = {
    "response_schema_version": 1,
    "summary": "One safe update.",
    "severity": "review",
    "recommended_order": ["agents-md"],
    "notes": [{"item_id": "agents-md", "note": "publish it"}],
    "codex_review_recommended": False,
    "codex_reason": "",
}

DOC = {
    "drift_schema_version": 1, "run_id": "r1",
    "generated_at": "2026-08-10T00:00:00+00:00", "scanner_version": "1.0.0",
    "manifest_version": 1, "roots": {"wsl": "/w", "repo": "/r"},
    "layer_fingerprints": {"wsl": "a" * 64, "repo": "b" * 64},
    "counts": {"publish_to_repo": 1},
    "items": [{"id": "agents-md", "entry_id": "agents-md", "kind": "text",
               "classification": "publish_to_repo", "severity": "review",
               "path": "AGENTS.md", "policy": "portable_authoritative",
               "detail": "ahead of baseline"}],
    "redactions": [], "errors": [],
}

PROMPT = Path(__file__).resolve().parents[1] / "prompts" / "report-v1.md"


def stub(tmp_path: Path, body: str) -> str:
    """Write an executable shell script that impersonates `claude`."""
    path = tmp_path / "claude-stub"
    path.write_text("#!/bin/sh\n" + body, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return str(path)


# --- command construction --------------------------------------------------

def test_command_uses_print_mode_and_bounded_turns():
    argv = az.build_command("/usr/bin/claude", max_turns=4)
    assert argv[0] == "/usr/bin/claude"
    assert "--print" in argv
    assert "--max-turns" in argv and "4" in argv


def test_command_grants_read_tools_only():
    argv = az.build_command("/usr/bin/claude", max_turns=4)
    allowed = argv[argv.index("--allowedTools") + 1]
    assert set(allowed.split(",")) <= {"Read", "Grep", "Glob"}
    disallowed = argv[argv.index("--disallowedTools") + 1].split(",")
    for mutator in ("Bash", "Write", "Edit"):
        assert mutator in disallowed


def test_command_never_uses_bare_mode():
    # The design requires normal configuration so skills/instructions load.
    assert "--bare" not in az.build_command("/usr/bin/claude", max_turns=4)


# --- prompt ----------------------------------------------------------------

def test_prompt_embeds_the_drift_document_and_the_schema():
    prompt = az.build_prompt(DOC, PROMPT)
    assert "agents-md" in prompt
    assert "response_schema_version" in prompt
    assert az.PROMPT_VERSION in prompt


def test_prompt_forbids_writing_and_inventing_items():
    prompt = az.build_prompt(DOC, PROMPT)
    lowered = prompt.lower()
    assert "do not" in lowered
    assert "item id" in lowered


# --- response parsing ------------------------------------------------------

def test_extract_json_reads_a_bare_object():
    assert az.extract_json(json.dumps(VALID))["summary"] == "One safe update."


def test_extract_json_reads_a_fenced_block():
    text = "Here you go:\n```json\n" + json.dumps(VALID) + "\n```\n"
    assert az.extract_json(text)["severity"] == "review"


def test_extract_json_reads_the_claude_print_json_envelope():
    envelope = json.dumps({"type": "result", "subtype": "success",
                           "result": json.dumps(VALID)})
    assert az.extract_json(envelope)["summary"] == "One safe update."


def test_extract_json_raises_when_there_is_no_object():
    with pytest.raises(az.AnalysisError):
        az.extract_json("I could not do that.")


def test_validate_accepts_a_good_analysis():
    assert az.validate_analysis(VALID) == []


def test_validate_rejects_a_missing_required_field():
    broken = {k: v for k, v in VALID.items() if k != "summary"}
    assert az.validate_analysis(broken)


def test_validate_rejects_an_unknown_severity():
    assert az.validate_analysis(dict(VALID, severity="catastrophic"))


def test_validate_rejects_a_future_response_schema_version():
    assert az.validate_analysis(dict(VALID, response_schema_version=2))


# --- running the stub ------------------------------------------------------

def test_run_returns_the_parsed_analysis(tmp_path: Path):
    binary = stub(tmp_path, f"cat >/dev/null\necho '{json.dumps(VALID)}'\n")
    result = az.run(DOC, claude_bin=binary, prompt_path=PROMPT,
                    timeout_s=10, max_turns=4)
    assert result["summary"] == "One safe update."


def test_run_raises_on_a_nonzero_exit(tmp_path: Path):
    binary = stub(tmp_path, "cat >/dev/null\necho boom >&2\nexit 3\n")
    with pytest.raises(az.AnalysisError) as excinfo:
        az.run(DOC, claude_bin=binary, prompt_path=PROMPT, timeout_s=10,
               max_turns=4)
    assert "exit 3" in str(excinfo.value)


def test_run_raises_on_unparseable_output(tmp_path: Path):
    binary = stub(tmp_path, "cat >/dev/null\necho 'sorry, no'\n")
    with pytest.raises(az.AnalysisError):
        az.run(DOC, claude_bin=binary, prompt_path=PROMPT, timeout_s=10,
               max_turns=4)


def test_run_raises_on_a_schema_invalid_response(tmp_path: Path):
    bad = json.dumps(dict(VALID, severity="nope"))
    binary = stub(tmp_path, f"cat >/dev/null\necho '{bad}'\n")
    with pytest.raises(az.AnalysisError) as excinfo:
        az.run(DOC, claude_bin=binary, prompt_path=PROMPT, timeout_s=10,
               max_turns=4)
    assert "severity" in str(excinfo.value)


def test_run_raises_on_timeout(tmp_path: Path):
    binary = stub(tmp_path, "cat >/dev/null\nsleep 5\n")
    with pytest.raises(az.AnalysisError) as excinfo:
        az.run(DOC, claude_bin=binary, prompt_path=PROMPT, timeout_s=1,
               max_turns=4)
    assert "timed out" in str(excinfo.value)


def test_run_raises_when_the_binary_is_missing(tmp_path: Path):
    with pytest.raises(az.AnalysisError):
        az.run(DOC, claude_bin=str(tmp_path / "nope"), prompt_path=PROMPT,
               timeout_s=5, max_turns=4)


def test_error_messages_never_echo_the_model_output_verbatim(tmp_path: Path):
    binary = stub(tmp_path, "cat >/dev/null\necho 'sk-live-DO-NOT-LEAK'\n")
    with pytest.raises(az.AnalysisError) as excinfo:
        az.run(DOC, claude_bin=binary, prompt_path=PROMPT, timeout_s=10,
               max_turns=4)
    assert "sk-live-DO-NOT-LEAK" not in str(excinfo.value)


# --- render.py CLI ---------------------------------------------------------

def test_render_cli_promotes_only_a_valid_report(tmp_path: Path):
    import render as rd

    drift_path = tmp_path / "drift.json"
    drift_path.write_text(json.dumps(DOC), encoding="utf-8")
    state = tmp_path / "state"
    binary = stub(tmp_path, f"cat >/dev/null\necho '{json.dumps(VALID)}'\n")

    code = rd.main(["--drift", str(drift_path), "--state-dir", str(state),
                    "--claude-bin", binary, "--prompt", str(PROMPT)])
    assert code == 0
    latest = (state / "latest-report.md").read_text(encoding="utf-8")
    assert "Agent config drift report" in latest
    assert list((state / "reports").glob("*.md"))


def test_render_cli_keeps_the_previous_report_when_the_model_fails(tmp_path: Path):
    import render as rd

    drift_path = tmp_path / "drift.json"
    drift_path.write_text(json.dumps(DOC), encoding="utf-8")
    state = tmp_path / "state"
    state.mkdir()
    (state / "latest-report.md").write_text("PREVIOUS GOOD REPORT\n",
                                            encoding="utf-8")
    binary = stub(tmp_path, "cat >/dev/null\necho 'garbage'\n")

    code = rd.main(["--drift", str(drift_path), "--state-dir", str(state),
                    "--claude-bin", binary, "--prompt", str(PROMPT)])
    assert code == rd.EXIT_MODEL_FAILURE
    assert (state / "latest-report.md").read_text(
        encoding="utf-8") == "PREVIOUS GOOD REPORT\n"


def test_render_cli_no_model_flag_renders_without_claude(tmp_path: Path):
    import render as rd

    drift_path = tmp_path / "drift.json"
    drift_path.write_text(json.dumps(DOC), encoding="utf-8")
    state = tmp_path / "state"
    code = rd.main(["--drift", str(drift_path), "--state-dir", str(state),
                    "--no-model"])
    assert code == 0
    assert "no model analysis" in (
        state / "latest-report.md").read_text(encoding="utf-8").lower()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest tools/agent-config-sync/tests/test_analyze.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'analyze'`

- [ ] **Step 3: Write `schemas/response-v1.json`**

Create `tools/agent-config-sync/schemas/response-v1.json`:

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["response_schema_version", "summary", "severity",
               "recommended_order", "notes", "codex_review_recommended"],
  "properties": {
    "response_schema_version": {"type": "integer", "enum": [1]},
    "summary": {"type": "string"},
    "severity": {"type": "string", "enum": ["none", "review", "conflict"]},
    "recommended_order": {"type": "array", "items": {"type": "string"}},
    "notes": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["item_id", "note"],
        "properties": {
          "item_id": {"type": "string"},
          "note": {"type": "string"}
        }
      }
    },
    "codex_review_recommended": {"type": "boolean"},
    "codex_reason": {"type": "string"}
  }
}
```

- [ ] **Step 4: Write `prompts/report-v1.md`**

Create `tools/agent-config-sync/prompts/report-v1.md`:

````markdown
<!-- prompt version: report-v1 -->
You are analyzing a sanitized configuration-drift document for a machine where
WSL is the authority for portable agent configuration, a git repository holds
the sanitized baseline record, and Windows is a derived target with a protected
platform overlay.

<task>
Read the drift document below and return judgment only. You are not writing the
report — a deterministic renderer does that. Your job is the parts a program
cannot do: a plain-English summary, a sensible merge order, short notes on the
items that need human judgment, and a decision about whether an independent
cross-provider review is warranted.
</task>

<rules>
- Return ONE JSON object and nothing else. No prose before or after it.
- Every string in `recommended_order` and every `item_id` in `notes` MUST be an
  item id that appears verbatim in the drift document. Do not invent item ids.
- Order safe portable updates before conflicts. Within conflicts, order the
  lowest-risk first.
- Do not propose applying anything. Do not write files. Do not run commands.
- Do not restate fingerprints or counts; the renderer already prints them.
- Set `codex_review_recommended` to true only for a concrete advantage: an
  ambiguous semantic merge, a Codex-specific setting, or a high-risk conflict.
  Scheduling alone is never a reason. Put the reason in `codex_reason`.
- `severity`: "none" if nothing needs attention, "review" if everything is
  routine, "conflict" if any item requires a human decision.
</rules>

<response_schema>
{SCHEMA}
</response_schema>

<drift_document>
{DRIFT}
</drift_document>
````

- [ ] **Step 5: Implement `analyze.py`**

Create `tools/agent-config-sync/analyze.py`:

```python
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
    """Read-only, bounded, normal configuration (never --bare)."""
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
        raise AnalysisError("analyzer response failed the schema: "
                            + "; ".join(problems[:5]))
    return analysis
```

Note the deliberate design of the error strings: they carry sizes and schema
paths, never model output. `test_error_messages_never_echo_the_model_output_verbatim`
enforces this.

- [ ] **Step 6: Add the CLI entry point to `render.py`**

Append to `tools/agent-config-sync/render.py`:

```python
# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

EXIT_OK = 0
EXIT_RENDER_FAILURE = 20
EXIT_MODEL_FAILURE = 30


def main(argv=None) -> int:
    import argparse
    import json
    from pathlib import Path

    import analyze
    import drift as drift_mod

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

    markdown = render_markdown(doc, analysis)
    state_dir = args.state_dir
    drift_mod.write_atomic(state_dir / "reports" / f"{doc['run_id']}.md",
                           markdown)
    drift_mod.write_atomic(state_dir / "latest-report.md", markdown)
    print(str(state_dir / "latest-report.md"))
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `python3 -m pytest tools/agent-config-sync/tests/test_analyze.py -v`
Expected: PASS (22 tests)

- [ ] **Step 8: Run the whole suite**

Run: `python3 -m pytest tools/agent-config-sync/tests/ -v`
Expected: PASS (all tests from Tasks 1–8)

- [ ] **Step 9: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/.claude_code add tools/agent-config-sync/analyze.py tools/agent-config-sync/render.py tools/agent-config-sync/schemas/response-v1.json tools/agent-config-sync/prompts/report-v1.md tools/agent-config-sync/tests/test_analyze.py
git -C /mnt/d/Documents/Code/GitHub/.claude_code commit -m "feat(agent-config-sync): bounded claude -p analyzer with schema-validated output"
```

---

## Task 9: Cron wrapper, status contract, and operator documentation

**Files:**
- Create: `tools/agent-config-sync/bin/agent-config-sync.sh`
- Create: `Docs/agent-config-sync.md`
- Test: `tools/agent-config-sync/tests/test_wrapper.py`

**Interfaces:**
- Consumes: `scan.py` and `render.py` exit codes (Tasks 6, 8).
- Produces: a wrapper whose behaviour is fully controlled by environment variables so it can be tested without touching live paths:
  - `ACS_REPO`, `ACS_PYTHON`, `ACS_CLAUDE`, `ACS_MANIFEST`, `ACS_STATE`, `ACS_SCAN`, `ACS_RENDER`.
  - Wrapper exit codes: `0` no drift (Claude not invoked), `10` drift reported, `20` scan failure, `21` lock held, `30` model failure.

- [ ] **Step 1: Write the failing tests**

Create `tools/agent-config-sync/tests/test_wrapper.py`:

```python
"""Tests for the cron wrapper.

Design: "Scheduling"; test case 1 -- when there is no drift, Claude is never
invoked.
"""
from __future__ import annotations

import stat
import subprocess
import sys
from pathlib import Path

import pytest

WRAPPER = Path(__file__).resolve().parents[1] / "bin" / "agent-config-sync.sh"


def stub(path: Path, body: str) -> str:
    path.write_text("#!/bin/sh\n" + body, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return str(path)


@pytest.fixture
def scene(tmp_path: Path):
    state = tmp_path / "state"
    state.mkdir()
    marker = tmp_path / "render-was-called"
    return tmp_path, state, marker


def run_wrapper(tmp_path: Path, state: Path, *, scan_exit: int,
                render_exit: int, marker: Path):
    scan = stub(tmp_path / "scan-stub", f'exit {scan_exit}\n')
    render = stub(tmp_path / "render-stub",
                  f'echo called >"{marker}"\nexit {render_exit}\n')
    env = {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "HOME": str(tmp_path),
        "ACS_STATE": str(state),
        "ACS_MANIFEST": str(tmp_path / "agent-sync.toml"),
        "ACS_SCAN": scan,
        "ACS_RENDER": render,
        "ACS_CLAUDE": "/nonexistent/claude",
    }
    return subprocess.run(["bash", str(WRAPPER)], env=env,
                          capture_output=True, text=True)


def test_no_drift_exits_zero_and_never_calls_the_model(scene):
    tmp_path, state, marker = scene
    result = run_wrapper(tmp_path, state, scan_exit=0, render_exit=0,
                         marker=marker)
    assert result.returncode == 0
    assert not marker.exists(), "Claude must not run when there is no drift"


def test_drift_calls_render_and_exits_ten(scene):
    tmp_path, state, marker = scene
    result = run_wrapper(tmp_path, state, scan_exit=10, render_exit=0,
                         marker=marker)
    assert result.returncode == 10
    assert marker.exists()


def test_scan_failure_exits_twenty_and_never_calls_the_model(scene):
    tmp_path, state, marker = scene
    result = run_wrapper(tmp_path, state, scan_exit=20, render_exit=0,
                         marker=marker)
    assert result.returncode == 20
    assert not marker.exists()


def test_lock_held_exits_twenty_one(scene):
    tmp_path, state, marker = scene
    result = run_wrapper(tmp_path, state, scan_exit=21, render_exit=0,
                         marker=marker)
    assert result.returncode == 21
    assert not marker.exists()


def test_model_failure_exits_thirty_not_twenty(scene):
    tmp_path, state, marker = scene
    result = run_wrapper(tmp_path, state, scan_exit=10, render_exit=30,
                         marker=marker)
    assert result.returncode == 30


def test_wrapper_is_executable_and_uses_absolute_defaults():
    assert WRAPPER.stat().st_mode & stat.S_IXUSR
    text = WRAPPER.read_text(encoding="utf-8")
    assert text.startswith("#!/usr/bin/env bash")
    assert "set -euo pipefail" in text
    assert "export PATH=" in text, "cron gets a minimal explicit environment"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest tools/agent-config-sync/tests/test_wrapper.py -v`
Expected: FAIL — the wrapper does not exist

- [ ] **Step 3: Implement the wrapper**

Create `tools/agent-config-sync/bin/agent-config-sync.sh`:

```bash
#!/usr/bin/env bash
# Scheduled agent-config drift check. Report-only: this script can never apply
# a configuration change.
#
# Exit codes: 0 no drift (Claude was not invoked), 10 drift reported,
#             20 scan failure, 21 another run holds the lock, 30 model failure.
#
# Design: "Scheduling".
set -euo pipefail

ACS_REPO="${ACS_REPO:-/mnt/d/Documents/Code/GitHub/.claude_code}"
ACS_PYTHON="${ACS_PYTHON:-/usr/bin/python3}"
ACS_CLAUDE="${ACS_CLAUDE:-$HOME/.local/bin/claude}"
ACS_MANIFEST="${ACS_MANIFEST:-$ACS_REPO/config/agent-sync.toml}"
ACS_STATE="${ACS_STATE:-$HOME/.local/state/agent-config-sync}"
ACS_SCAN="${ACS_SCAN:-$ACS_PYTHON $ACS_REPO/tools/agent-config-sync/scan.py}"
ACS_RENDER="${ACS_RENDER:-$ACS_PYTHON $ACS_REPO/tools/agent-config-sync/render.py}"

# cron has no useful environment; establish a minimal explicit one.
export PATH=/usr/local/bin:/usr/bin:/bin
export LC_ALL=C.UTF-8

mkdir -p "$ACS_STATE"
DRIFT="$ACS_STATE/latest-drift.json"
LOG="$ACS_STATE/wrapper.log"

log() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >>"$LOG"; }

# Deterministic scan first. Word splitting on $ACS_SCAN is intentional: it is a
# command line, not a single path.
# shellcheck disable=SC2086
set +e
$ACS_SCAN --manifest "$ACS_MANIFEST" --out "$DRIFT" --state-dir "$ACS_STATE"
scan_code=$?
set -e

case "$scan_code" in
  0)
    log "no drift; Claude not invoked"
    exit 0
    ;;
  10)
    log "drift detected; invoking the analyzer"
    ;;
  21)
    log "another run holds the lock; exiting"
    exit 21
    ;;
  *)
    log "scan failed with exit $scan_code; previous report left untouched"
    exit 20
    ;;
esac

# shellcheck disable=SC2086
set +e
$ACS_RENDER --drift "$DRIFT" --state-dir "$ACS_STATE" \
            --claude-bin "$ACS_CLAUDE"
render_code=$?
set -e

if [ "$render_code" -ne 0 ]; then
  log "analyzer/render failed with exit $render_code; last valid report kept"
  exit 30
fi

log "report written to $ACS_STATE/latest-report.md"
exit 10
```

Then make it executable:

```bash
chmod +x /mnt/d/Documents/Code/GitHub/.claude_code/tools/agent-config-sync/bin/agent-config-sync.sh
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest tools/agent-config-sync/tests/test_wrapper.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Write the operator documentation**

Create `Docs/agent-config-sync.md`:

````markdown
# Agent Config Sync — operator guide

WSL is the authority for portable agent configuration. This repository is the
sanitized record. Windows is a derived target with a protected overlay. The
scheduled job **reports**; it never applies a change.

Design: `Docs/plans/2026-08-08-wsl-authoritative-agent-config-sync-design.md`

## Run a scan by hand

```bash
python3 /mnt/d/Documents/Code/GitHub/.claude_code/tools/agent-config-sync/scan.py \
  --manifest /mnt/d/Documents/Code/GitHub/.claude_code/config/agent-sync.toml
```

Exit codes: `0` no drift · `10` drift reported · `20` scan failure ·
`21` another run holds the lock.

## Render a report

```bash
python3 /mnt/d/Documents/Code/GitHub/.claude_code/tools/agent-config-sync/render.py \
  --drift ~/.local/state/agent-config-sync/latest-drift.json \
  --state-dir ~/.local/state/agent-config-sync
```

Add `--no-model` to render from the deterministic scan alone. Exit code `30`
means the analyzer failed — the previous valid report is left in place.

## Install the nightly job

The repository ships the wrapper; you own the cron entry. Add it with
`crontab -e`:

```cron
# Agent config drift report, 06:15 daily. Report-only.
15 6 * * * /mnt/d/Documents/Code/GitHub/.claude_code/tools/agent-config-sync/bin/agent-config-sync.sh
```

Set `ACS_CLAUDE` to the absolute path of your Claude executable if it is not
`~/.local/bin/claude`:

```bash
command -v claude
```

## Where state lives

```text
~/.local/state/agent-config-sync/
├── latest-status.json   # machine-readable result of the last scan
├── latest-drift.json    # sanitized drift document (no secret values)
├── latest-report.md     # last VALID report; an invalid run cannot replace it
├── reports/             # one timestamped report per run, retained
├── backups/             # one directory per applied merge, keyed by run id
└── wrapper.log
```

Nothing here is in git, and nothing here contains a secret value — only
pointers, reason codes, types, and hashes.

## Apply an approved change

Never automatic. Hand the report to Claude:

```text
Use the agent-config-merge skill on report <run-id>.
Apply only these item ids: <ids>
Dry-run first, show me the patch, then wait for my approval.
```

Or drive the tool directly:

```bash
python3 /mnt/d/Documents/Code/GitHub/.claude_code/tools/agent-config-sync/merge.py plan \
  --drift ~/.local/state/agent-config-sync/latest-drift.json \
  --manifest /mnt/d/Documents/Code/GitHub/.claude_code/config/agent-sync.toml \
  --id agents-md
```

Add `--apply` only after reading the plan. Restore with:

```bash
python3 /mnt/d/Documents/Code/GitHub/.claude_code/tools/agent-config-sync/merge.py restore \
  --run-id <run-id>
```

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| exit `20` every run | manifest path wrong for this machine | fix `config/agent-sync.toml` roots |
| exit `21` every run | a stale lock from a killed run | `rm ~/.local/state/agent-config-sync/scan.lock` |
| exit `30` every run | `ACS_CLAUDE` is not the real executable | `command -v claude`, then set `ACS_CLAUDE` |
| huge `errors` list | a declared path does not exist on this machine | remove or correct that `[[entries]]` block |
````

- [ ] **Step 6: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/.claude_code add tools/agent-config-sync/bin/agent-config-sync.sh Docs/agent-config-sync.md tools/agent-config-sync/tests/test_wrapper.py
git -C /mnt/d/Documents/Code/GitHub/.claude_code commit -m "feat(agent-config-sync): cron wrapper, status contract, operator guide"
```

---

## Task 10: The `agent-config-report` skill

**Files:**
- Create: `claude/skills/agent-config-report/SKILL.md`

**Interfaces:**
- Consumes: `scan.py`, `render.py`, `Docs/agent-config-sync.md`.
- Produces: a skill that runs the scan on demand and explains the result. It is read-only; it never invokes `merge.py`.

- [ ] **Step 1: Write the skill**

Create `claude/skills/agent-config-report/SKILL.md`:

````markdown
---
name: agent-config-report
description: Scan for drift between WSL agent configuration (the authority), this repository's sanitized record, and the Windows target, then explain the resulting report. Use when Leland asks "what config has drifted", "check my agent config sync", "is Windows out of date", "run the config drift scan", or asks about a drift report by run id. Read-only — it never applies a change; use agent-config-merge for that.
---

# Agent Config Drift Report

WSL is the authority for portable agent configuration. This repository is the
sanitized record. Windows is a derived target with a protected overlay.
This skill **reports**. Applying anything is the `agent-config-merge` skill,
and always needs explicit approval.

Design: `Docs/plans/2026-08-08-wsl-authoritative-agent-config-sync-design.md`
Operator guide: `Docs/agent-config-sync.md`

## 1. Run the deterministic scan

```bash
python3 /mnt/d/Documents/Code/GitHub/.claude_code/tools/agent-config-sync/scan.py \
  --manifest /mnt/d/Documents/Code/GitHub/.claude_code/config/agent-sync.toml
echo "exit=$?"
```

Read the exit code before anything else:

| Exit | Meaning | Do next |
|---|---|---|
| `0` | No drift | Say so and stop. Do not render a report. |
| `10` | Drift found | Continue to step 2. |
| `20` | Scan failure | Report the stderr message. Do **not** fall back to reading config by hand — fix the manifest. |
| `21` | Lock held | Another scan is running. Wait and retry once. |

## 2. Render the report

```bash
python3 /mnt/d/Documents/Code/GitHub/.claude_code/tools/agent-config-sync/render.py \
  --drift ~/.local/state/agent-config-sync/latest-drift.json \
  --state-dir ~/.local/state/agent-config-sync
```

Exit `30` means the analyzer failed. The previous valid report is untouched —
say so, and offer `--no-model` to render from the scan alone.

## 3. Explain it

Read `~/.local/state/agent-config-sync/latest-report.md` and summarize for
Leland in this order:

1. **Conflicts requiring judgment** — these are the only items that need a
   decision. Say what changed on each side; never pick a winner yourself.
2. **Safe portable updates** — one line each.
3. **Plugin differences** — call out any pin violation explicitly. Never
   propose a downgrade unless the report shows an explicit pin.
4. **Protected Windows state** — mention only if Leland asks; it is not
   actionable by design.
5. **Scan errors** — a malformed file blocks its own item, nothing else.

Then quote the item ids Leland would need to approve. Nothing is applied.

## Rules

- Never read a live config file to "double-check" the scanner. If the scanner
  and your intuition disagree, the manifest is wrong — fix `config/agent-sync.toml`.
- Never print a value from a secret-bearing field, even if you can see it. The
  report deliberately carries pointers, reason codes, and hashes only.
- Never run `merge.py` from this skill.
- If the report recommends `/codex`, mention it and paste the prompt the report
  generated; do not run it unprompted.
````

- [ ] **Step 2: Verify the skill file loads and the paths in it resolve**

```bash
python3 - <<'PY'
import re, pathlib
p = pathlib.Path('/mnt/d/Documents/Code/GitHub/.claude_code/claude/skills/agent-config-report/SKILL.md')
text = p.read_text(encoding='utf-8')
assert text.startswith('---'), 'missing frontmatter'
front = text.split('---')[1]
assert 'name: agent-config-report' in front and 'description:' in front
for ref in re.findall(r'/mnt/d/[^\s`"]+\.(?:py|toml|md)', text):
    print('ok ' if pathlib.Path(ref).exists() else 'MISSING ', ref)
PY
```

Expected: every referenced path prints `ok`.

- [ ] **Step 3: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/.claude_code add claude/skills/agent-config-report/SKILL.md
git -C /mnt/d/Documents/Code/GitHub/.claude_code commit -m "feat(agent-config-sync): agent-config-report skill"
```

---

## Task 11: Reviewed merge — staleness, backups, atomic apply, restore

The only module that writes to a target. Everything about it is designed so that an unreviewed or stale change cannot be applied.

**Scope limit, deliberate and documented:** plugin operations are **proposed, never executed**. `merge.py` prints the exact `claude plugin …` commands and records them in the backup manifest as manual-recovery steps. Running a package manager unattended is exactly the class of action the design keeps behind human approval.

**Files:**
- Create: `tools/agent-config-sync/merge.py`
- Test: `tools/agent-config-sync/tests/test_merge.py`

**Interfaces:**
- Consumes: drift document (Task 6); `manifest`, `extract`, `normalize`, `compare`.
- Produces:
  - `merge.Action(item_id, kind, layer, target, pointer, description, command)` — frozen dataclass; `kind` ∈ `{"write_file", "set_field", "plugin_command", "noop"}`.
  - `merge.Plan(run_id, actions: tuple[Action, ...], skipped: tuple[tuple[str, str], ...])`
  - `merge.stale_items(doc, m) -> list[str]`
  - `merge.plan_merge(doc, m, selected_ids: list[str]) -> Plan`
  - `merge.render_plan(plan) -> str`
  - `merge.apply_plan(plan, m, *, backups_dir: Path) -> tuple[Path, list[str]]` — returns `(backup_dir, applied_ids)`
  - `merge.restore(backup_dir: Path) -> list[str]`
  - `merge.set_pointer(data: dict, pointer: str, value) -> dict`
  - `merge.get_pointer(data: dict, pointer: str)`
  - `merge.main(argv) -> int`; exit codes `0`, `20` failure, `22` stale, `23` nothing selected.

- [ ] **Step 1: Write the failing tests**

Create `tools/agent-config-sync/tests/test_merge.py`:

```python
"""Tests for reviewed merge planning, application, and restoration.

Design: "Reviewed application workflow", "Backups and recovery"; test cases
13 (stale report fingerprints), 16 (backup restoration), 17 (idempotence).
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import manifest as mf  # noqa: E402
import merge  # noqa: E402
import scan  # noqa: E402

NOW = datetime(2026, 8, 10, 14, 3, 22, tzinfo=timezone.utc)

MANIFEST_TEMPLATE = """
schema_version = 1

[roots]
wsl_home = "{wsl}"
repo = "{repo}"
windows_home = "{windows}"

[state]
dir = "{state}"

[secrets]
deny_key_patterns = ["(?i)token"]
deny_path_globs = []

[[entries]]
id = "agents-md"
policy = "portable_authoritative"
kind = "text"
wsl = "AGENTS.md"
repo = "AGENTS.md"
windows = "AGENTS.md"

[[entries]]
id = "settings"
policy = "portable_authoritative"
kind = "json"
wsl = "settings.json"
repo = "settings.json"
windows = "settings.json"

[entries.fields]
"model" = "portable_authoritative"
"statusLine.command" = "platform_overlay"
"""


@pytest.fixture
def scene(fixture_roots, tmp_path: Path):
    path = tmp_path / "agent-sync.toml"
    path.write_text(MANIFEST_TEMPLATE.format(
        wsl=fixture_roots.wsl, repo=fixture_roots.repo,
        windows=fixture_roots.windows, state=fixture_roots.state),
        encoding="utf-8")
    return path, fixture_roots


def scan_now(manifest_path) -> dict:
    return scan.run_scan(manifest_path, root_overrides=None, now=NOW,
                         entropy="test01")


def seed_text(roots, wsl: str, repo: str, windows: str) -> None:
    roots.write(roots.wsl, "AGENTS.md", wsl)
    roots.write(roots.repo, "AGENTS.md", repo)
    roots.write(roots.windows, "AGENTS.md", windows)


def seed_json(roots, wsl: dict, repo: dict, windows: dict) -> None:
    for layer, data in (("wsl", wsl), ("repo", repo), ("windows", windows)):
        roots.write(getattr(roots, layer), "settings.json", json.dumps(data))


# --- pointers --------------------------------------------------------------

def test_get_and_set_pointer_round_trip():
    data = {"a": {"b": 1}}
    assert merge.get_pointer(data, "a.b") == 1
    assert merge.set_pointer(data, "a.b", 2)["a"]["b"] == 2


def test_set_pointer_creates_missing_parents():
    assert merge.set_pointer({}, "a.b.c", 7) == {"a": {"b": {"c": 7}}}


def test_set_pointer_does_not_mutate_the_input():
    original = {"a": {"b": 1}}
    merge.set_pointer(original, "a.b", 9)
    assert original["a"]["b"] == 1


# --- planning --------------------------------------------------------------

def test_plan_selects_only_the_requested_item_ids(scene):
    manifest_path, roots = scene
    seed_text(roots, "new\n", "old\n", "old\n")
    seed_json(roots, {"model": "x"}, {"model": "y"}, {"model": "y"})
    m = mf.load_manifest(manifest_path)
    doc = scan_now(manifest_path)

    plan = merge.plan_merge(doc, m, ["agents-md"])
    assert [a.item_id for a in plan.actions if a.kind != "noop"] == ["agents-md"]


def test_plan_refuses_an_unknown_item_id(scene):
    manifest_path, roots = scene
    seed_text(roots, "a\n", "a\n", "a\n")
    seed_json(roots, {"model": "x"}, {"model": "x"}, {"model": "x"})
    m = mf.load_manifest(manifest_path)
    plan = merge.plan_merge(scan_now(manifest_path), m, ["no-such-item"])
    assert plan.actions == ()
    assert plan.skipped[0][0] == "no-such-item"


def test_plan_never_proposes_a_protected_overlay_field(scene):
    manifest_path, roots = scene
    seed_text(roots, "a\n", "a\n", "a\n")
    seed_json(roots,
              {"model": "x", "statusLine": {"command": "/wsl.sh"}},
              {"model": "x", "statusLine": {"command": "/wsl.sh"}},
              {"model": "x", "statusLine": {"command": "C:\\win.ps1"}})
    m = mf.load_manifest(manifest_path)
    plan = merge.plan_merge(scan_now(manifest_path), m,
                            ["settings:statusLine.command"])
    assert not [a for a in plan.actions if a.kind != "noop"]
    assert "protected" in plan.skipped[0][1].lower()


def test_plan_emits_a_plugin_command_but_never_runs_it(scene):
    manifest_path, roots = scene
    seed_text(roots, "a\n", "a\n", "a\n")
    seed_json(roots, {"model": "x"}, {"model": "x"}, {"model": "x"})
    m = mf.load_manifest(manifest_path)
    doc = scan_now(manifest_path)
    doc["items"].append({
        "id": "claude-plugins:superpowers@official#missing:windows",
        "entry_id": "claude-plugins", "kind": "plugin",
        "classification": "plugin_missing", "severity": "review",
        "path": "superpowers@official", "policy": "portable_authoritative",
        "detail": "Install it with: claude plugin install superpowers@official"})
    plan = merge.plan_merge(doc, m, [doc["items"][-1]["id"]])
    action = plan.actions[0]
    assert action.kind == "plugin_command"
    assert action.command and action.command[0] == "claude"


def test_render_plan_shows_targets_and_a_dry_run_marker(scene):
    manifest_path, roots = scene
    seed_text(roots, "new\n", "old\n", "old\n")
    seed_json(roots, {"model": "x"}, {"model": "x"}, {"model": "x"})
    m = mf.load_manifest(manifest_path)
    text = merge.render_plan(merge.plan_merge(scan_now(manifest_path), m,
                                              ["agents-md"]))
    assert "DRY RUN" in text
    assert "AGENTS.md" in text


# --- staleness (design test case 13) --------------------------------------

def test_a_report_whose_source_moved_since_the_scan_is_stale(scene):
    manifest_path, roots = scene
    seed_text(roots, "new\n", "old\n", "old\n")
    seed_json(roots, {"model": "x"}, {"model": "x"}, {"model": "x"})
    m = mf.load_manifest(manifest_path)
    doc = scan_now(manifest_path)

    roots.write(roots.wsl, "AGENTS.md", "newer still\n")   # edited after the scan
    assert "agents-md" in merge.stale_items(doc, m)


def test_a_fresh_report_is_not_stale(scene):
    manifest_path, roots = scene
    seed_text(roots, "new\n", "old\n", "old\n")
    seed_json(roots, {"model": "x"}, {"model": "x"}, {"model": "x"})
    m = mf.load_manifest(manifest_path)
    assert merge.stale_items(scan_now(manifest_path), m) == []


def test_apply_refuses_a_stale_item(scene):
    manifest_path, roots = scene
    seed_text(roots, "new\n", "old\n", "old\n")
    seed_json(roots, {"model": "x"}, {"model": "x"}, {"model": "x"})
    m = mf.load_manifest(manifest_path)
    doc = scan_now(manifest_path)
    roots.write(roots.wsl, "AGENTS.md", "changed\n")

    code = merge.main(["apply", "--drift-json", json.dumps(doc),
                       "--manifest", str(manifest_path), "--id", "agents-md"])
    assert code == merge.EXIT_STALE
    assert (roots.repo / "AGENTS.md").read_text(encoding="utf-8") == "old\n"


# --- applying --------------------------------------------------------------

def test_publish_writes_the_wsl_content_into_the_repository(scene):
    manifest_path, roots = scene
    seed_text(roots, "new intent\n", "old\n", "old\n")
    seed_json(roots, {"model": "x"}, {"model": "x"}, {"model": "x"})
    m = mf.load_manifest(manifest_path)
    plan = merge.plan_merge(scan_now(manifest_path), m, ["agents-md"])
    merge.apply_plan(plan, m, backups_dir=roots.state / "backups")
    assert (roots.repo / "AGENTS.md").read_text(encoding="utf-8") == "new intent\n"


def test_reconcile_windows_renders_paths_in_windows_form(scene):
    manifest_path, roots = scene
    body = "hook: {wsl}/tools/guard.py\n".format(wsl=roots.wsl)
    seed_text(roots, body, body, "stale\n")
    seed_json(roots, {"model": "x"}, {"model": "x"}, {"model": "x"})
    m = mf.load_manifest(manifest_path)
    plan = merge.plan_merge(scan_now(manifest_path), m, ["agents-md"])
    merge.apply_plan(plan, m, backups_dir=roots.state / "backups")
    written = (roots.windows / "AGENTS.md").read_text(encoding="utf-8")
    assert "{HOME}" not in written
    assert str(roots.wsl) not in written


def test_set_field_leaves_every_other_key_untouched(scene):
    manifest_path, roots = scene
    seed_text(roots, "a\n", "a\n", "a\n")
    seed_json(roots,
              {"model": "opus", "statusLine": {"command": "/wsl.sh"},
               "keepMe": [1, 2]},
              {"model": "sonnet", "statusLine": {"command": "/wsl.sh"},
               "keepMe": [1, 2]},
              {"model": "sonnet", "statusLine": {"command": "C:\\win.ps1"},
               "keepMe": [1, 2]})
    m = mf.load_manifest(manifest_path)
    plan = merge.plan_merge(scan_now(manifest_path), m, ["settings:model"])
    merge.apply_plan(plan, m, backups_dir=roots.state / "backups")
    after = json.loads((roots.repo / "settings.json").read_text(encoding="utf-8"))
    assert after["model"] == "opus"
    assert after["keepMe"] == [1, 2]
    assert after["statusLine"]["command"] == "/wsl.sh"


def test_windows_owned_field_survives_an_applied_merge(scene):
    manifest_path, roots = scene
    seed_text(roots, "a\n", "a\n", "a\n")
    seed_json(roots,
              {"model": "opus", "statusLine": {"command": "/wsl.sh"}},
              {"model": "sonnet", "statusLine": {"command": "/wsl.sh"}},
              {"model": "sonnet", "statusLine": {"command": "C:\\win.ps1"}})
    m = mf.load_manifest(manifest_path)
    plan = merge.plan_merge(scan_now(manifest_path), m, ["settings:model"])
    merge.apply_plan(plan, m, backups_dir=roots.state / "backups")
    windows = json.loads(
        (roots.windows / "settings.json").read_text(encoding="utf-8"))
    assert windows["statusLine"]["command"] == "C:\\win.ps1"


# --- idempotence (design test case 17) ------------------------------------

def test_applying_the_same_approved_change_twice_changes_nothing(scene):
    manifest_path, roots = scene
    seed_text(roots, "new\n", "old\n", "old\n")
    seed_json(roots, {"model": "x"}, {"model": "x"}, {"model": "x"})
    m = mf.load_manifest(manifest_path)
    plan = merge.plan_merge(scan_now(manifest_path), m, ["agents-md"])
    merge.apply_plan(plan, m, backups_dir=roots.state / "backups")
    first = (roots.repo / "AGENTS.md").read_text(encoding="utf-8")

    second_plan = merge.plan_merge(scan_now(manifest_path), m, ["agents-md"])
    _, applied = merge.apply_plan(second_plan, m,
                                  backups_dir=roots.state / "backups")
    assert (roots.repo / "AGENTS.md").read_text(encoding="utf-8") == first
    assert applied == [] or all(
        a.kind == "noop" for a in second_plan.actions)


def test_a_second_scan_after_applying_shows_no_remaining_drift(scene):
    manifest_path, roots = scene
    seed_text(roots, "new\n", "old\n", "old\n")
    seed_json(roots, {"model": "x"}, {"model": "x"}, {"model": "x"})
    m = mf.load_manifest(manifest_path)
    doc = scan_now(manifest_path)
    ids = [i["id"] for i in doc["items"] if i["severity"] == "review"]
    merge.apply_plan(merge.plan_merge(doc, m, ids), m,
                     backups_dir=roots.state / "backups")
    after = scan_now(manifest_path)
    assert [i for i in after["items"] if i["severity"] == "review"] == []


# --- backups and restore (design test case 16) ----------------------------

def test_apply_backs_up_every_target_it_touches(scene):
    manifest_path, roots = scene
    seed_text(roots, "new\n", "old\n", "old\n")
    seed_json(roots, {"model": "x"}, {"model": "x"}, {"model": "x"})
    m = mf.load_manifest(manifest_path)
    plan = merge.plan_merge(scan_now(manifest_path), m, ["agents-md"])
    backup_dir, _ = merge.apply_plan(plan, m,
                                     backups_dir=roots.state / "backups")
    entries = json.loads(
        (backup_dir / "manifest.json").read_text(encoding="utf-8"))
    assert entries["run_id"] == "2026-08-10T14-03-22Z-test01"
    assert len(entries["files"]) >= 1
    assert (backup_dir / "files").is_dir()


def test_restore_returns_every_target_to_its_pre_merge_content(scene):
    manifest_path, roots = scene
    seed_text(roots, "new\n", "old\n", "old\n")
    seed_json(roots, {"model": "x"}, {"model": "x"}, {"model": "x"})
    m = mf.load_manifest(manifest_path)
    plan = merge.plan_merge(scan_now(manifest_path), m, ["agents-md"])
    backup_dir, _ = merge.apply_plan(plan, m,
                                     backups_dir=roots.state / "backups")
    assert (roots.repo / "AGENTS.md").read_text(encoding="utf-8") == "new\n"

    merge.restore(backup_dir)
    assert (roots.repo / "AGENTS.md").read_text(encoding="utf-8") == "old\n"
    assert (roots.windows / "AGENTS.md").read_text(encoding="utf-8") == "old\n"


def test_restore_recreates_a_file_that_did_not_exist_before(scene):
    manifest_path, roots = scene
    roots.write(roots.wsl, "AGENTS.md", "brand new\n")
    seed_json(roots, {"model": "x"}, {"model": "x"}, {"model": "x"})
    m = mf.load_manifest(manifest_path)
    plan = merge.plan_merge(scan_now(manifest_path), m, ["agents-md"])
    backup_dir, _ = merge.apply_plan(plan, m,
                                     backups_dir=roots.state / "backups")
    assert (roots.repo / "AGENTS.md").exists()
    merge.restore(backup_dir)
    assert not (roots.repo / "AGENTS.md").exists()


def test_a_failed_apply_stops_immediately_and_keeps_the_backup(scene,
                                                               monkeypatch):
    manifest_path, roots = scene
    seed_text(roots, "new\n", "old\n", "old\n")
    seed_json(roots, {"model": "x"}, {"model": "x"}, {"model": "x"})
    m = mf.load_manifest(manifest_path)
    plan = merge.plan_merge(scan_now(manifest_path), m, ["agents-md"])

    def explode(path, text):
        raise OSError("disk full")

    monkeypatch.setattr(merge, "write_target", explode)
    with pytest.raises(OSError):
        merge.apply_plan(plan, m, backups_dir=roots.state / "backups")

    # The backup was taken before the write was attempted, and the target is
    # untouched -- so restoration is possible even though nothing was applied.
    backup_dir = roots.state / "backups" / "2026-08-10T14-03-22Z-test01"
    assert (backup_dir / "manifest.json").is_file()
    assert (roots.repo / "AGENTS.md").read_text(encoding="utf-8") == "old\n"


# --- CLI -------------------------------------------------------------------

def test_cli_plan_is_dry_run_by_default(scene, capsys):
    manifest_path, roots = scene
    seed_text(roots, "new\n", "old\n", "old\n")
    seed_json(roots, {"model": "x"}, {"model": "x"}, {"model": "x"})
    doc = scan_now(manifest_path)
    code = merge.main(["plan", "--drift-json", json.dumps(doc),
                       "--manifest", str(manifest_path), "--id", "agents-md"])
    assert code == 0
    assert "DRY RUN" in capsys.readouterr().out
    assert (roots.repo / "AGENTS.md").read_text(encoding="utf-8") == "old\n"


def test_cli_requires_at_least_one_id(scene):
    manifest_path, roots = scene
    seed_text(roots, "new\n", "old\n", "old\n")
    seed_json(roots, {"model": "x"}, {"model": "x"}, {"model": "x"})
    doc = scan_now(manifest_path)
    code = merge.main(["apply", "--drift-json", json.dumps(doc),
                       "--manifest", str(manifest_path)])
    assert code == merge.EXIT_NOTHING_SELECTED
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest tools/agent-config-sync/tests/test_merge.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'merge'`

- [ ] **Step 3: Implement `merge.py`**

Create `tools/agent-config-sync/merge.py`:

```python
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
import sys
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

#: Classifications this tool knows how to act on.
_PUBLISH = "publish_to_repo"
_RECONCILE = "reconcile_windows"
_PLUGIN = ("plugin_missing", "plugin_enabled_differs",
           "plugin_version_differs", "plugin_pin_violation")


@dataclass(frozen=True)
class Action:
    item_id: str
    kind: str            # write_file | set_field | plugin_command | noop
    layer: str
    target: Path | None
    pointer: str | None
    description: str
    command: tuple[str, ...] | None = None


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

def _current_units(m) -> dict[tuple[str, str], object]:
    units: dict[tuple[str, str], object] = {}
    for entry in m.entries:
        for layer in extract.LAYERS:
            root = m.roots.for_layer(layer)
            for unit in extract.extract_entry(entry, layer, root, m.secrets,
                                              m.roots):
                units[(layer, unit.unit_id)] = unit
    return units


def stale_items(doc: dict, m) -> list[str]:
    """Item ids whose recorded fingerprints no longer match the filesystem."""
    current = _current_units(m)
    stale: list[str] = []
    for item in doc.get("items", []):
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

        if classification not in (_PUBLISH, _RECONCILE):
            skipped.append((item_id,
                            f"{classification} requires a decision, not an "
                            f"automatic action"))
            continue

        entry = _entry_for(m, item["entry_id"])
        if entry is None:
            skipped.append((item_id, "entry is no longer in the manifest"))
            continue

        layers = ["repo", "windows"] if classification == _PUBLISH else ["windows"]
        for layer in layers:
            target = _target_path(m, entry, layer)
            if target is None:
                continue
            if entry.kind in ("json", "toml") and ":" in item_id:
                pointer = item_id.split(":", 1)[1]
                actions.append(Action(
                    item_id=item_id, kind="set_field", layer=layer,
                    target=target, pointer=pointer,
                    description=f"set {pointer} in {target} from WSL"))
            else:
                actions.append(Action(
                    item_id=item_id, kind="write_file", layer=layer,
                    target=target, pointer=None,
                    description=f"write {target} from WSL"))

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


def _source_text(m, entry, item_id: str) -> str | None:
    source = _target_path(m, entry, "wsl")
    if source is None or not source.exists():
        return None
    return source.read_text(encoding="utf-8")


def _desired_for_layer(m, entry, raw: str, layer: str) -> str:
    normalized = nz.normalize_for_kind(raw, "text")
    tokenized = nz.tokenize_paths(normalized, m.roots)
    return nz.render_paths(tokenized, layer, m.roots)


def apply_plan(plan: Plan, m, *, backups_dir: Path) -> tuple[Path, list[str]]:
    backup_dir = Path(backups_dir) / plan.run_id
    files_dir = backup_dir / "files"
    files_dir.mkdir(parents=True, exist_ok=True)

    records: list[dict] = []
    applied: list[str] = []
    manual: list[list[str]] = []

    for index, action in enumerate(plan.actions):
        if action.kind == "plugin_command":
            manual.append(list(action.command or ()))
            continue
        if action.target is None:
            continue

        entry = _entry_for(m, action.item_id.split(":", 1)[0])
        if entry is None:
            continue
        raw = _source_text(m, entry, action.item_id)
        if raw is None:
            continue

        if action.kind == "write_file":
            desired = _desired_for_layer(m, entry, raw, action.layer)
        else:
            source_data = json.loads(nz.normalize_for_kind(raw, entry.kind))
            value = get_pointer(source_data, action.pointer or "")
            existing = ({} if not action.target.exists()
                        else json.loads(action.target.read_text(encoding="utf-8")))
            desired = json.dumps(set_pointer(existing, action.pointer or "",
                                             value),
                                 indent=2, sort_keys=True) + "\n"

        existed = action.target.exists()
        current = action.target.read_text(encoding="utf-8") if existed else None
        if current == desired:
            continue                                  # already applied: no-op

        stored = files_dir / f"{index:03d}"
        if existed:
            shutil.copy2(action.target, stored)
        records.append({
            "index": index,
            "item_id": action.item_id,
            "target": str(action.target),
            "layer": action.layer,
            "existed": existed,
            "stored": stored.name if existed else None,
            "sha256_before": nz.fingerprint(current) if existed else None,
        })
        drift.write_atomic(backup_dir / "manifest.json", json.dumps({
            "run_id": plan.run_id, "files": records,
            "manual_recovery": manual,
        }, indent=2) + "\n")

        write_target(action.target, desired)
        applied.append(action.item_id)

    drift.write_atomic(backup_dir / "manifest.json", json.dumps({
        "run_id": plan.run_id, "files": records, "manual_recovery": manual,
    }, indent=2) + "\n")
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

    stale = [i for i in stale_items(doc, m) if i in args.ids]
    if stale:
        print("merge: this report is stale for: " + ", ".join(stale))
        print("Re-run the scan and use the new report.")
        return EXIT_STALE

    plan = plan_merge(doc, m, args.ids)
    print(render_plan(plan), end="")
    if args.verb == "plan":
        return EXIT_OK

    backup_dir, applied = apply_plan(plan, m,
                                     backups_dir=m.state_dir / "backups")
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest tools/agent-config-sync/tests/test_merge.py -v`
Expected: PASS (22 tests)

`test_a_failed_apply_stops_immediately_and_keeps_the_backup` is the one that constrains ordering inside `apply_plan`: the backup must be written **before** `write_target` is called, or a crashed apply leaves nothing to restore from. If it fails, fix the ordering in `apply_plan` — never the test.

- [ ] **Step 5: Run the whole suite**

Run: `python3 -m pytest tools/agent-config-sync/tests/ -v`
Expected: PASS (all tests from Tasks 1–11)

- [ ] **Step 6: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/.claude_code add tools/agent-config-sync/merge.py tools/agent-config-sync/tests/test_merge.py
git -C /mnt/d/Documents/Code/GitHub/.claude_code commit -m "feat(agent-config-sync): reviewed merge with staleness checks, backups, and restore"
```

---

## Task 12: The `agent-config-merge` skill and `/codex` escalation

**Files:**
- Create: `claude/skills/agent-config-merge/SKILL.md`

**Interfaces:**
- Consumes: `merge.py` (Task 11), the rendered report (Task 7).
- Produces: the only human-facing path that applies a change. It always dry-runs first, always asks, and never expands scope on a Codex recommendation.

- [ ] **Step 1: Write the skill**

Create `claude/skills/agent-config-merge/SKILL.md`:

````markdown
---
name: agent-config-merge
description: Apply approved items from an agent-config drift report — publish WSL intent into this repository's sanitized record, reconcile the Windows target, and propose native plugin commands. Use when Leland says "apply the drift report", "publish those config changes", "merge items X and Y from the report", "reconcile Windows config", or "restore the last config merge". Always dry-runs and asks before writing anything.
---

# Apply an Agent Config Drift Report

This is the only skill that writes configuration. It applies **explicitly named
item ids** from a report, and nothing else. WSL live configuration is never
rewritten — only the repository record and the Windows target.

Design: `Docs/plans/2026-08-08-wsl-authoritative-agent-config-sync-design.md`
Report skill: `agent-config-report` · Operator guide: `Docs/agent-config-sync.md`

## 1. Get the item ids

Read `~/.local/state/agent-config-sync/latest-report.md` (or the run id Leland
named, from `reports/<run-id>.md`).

If Leland has not named specific ids, **ask** with AskUserQuestion — do not
infer "all of them". Offer, as separate choices: the safe portable updates
only, safe updates plus a specific conflict resolution, or a list he types.

## 2. Dry-run — always first

```bash
python3 /mnt/d/Documents/Code/GitHub/.claude_code/tools/agent-config-sync/merge.py plan \
  --drift ~/.local/state/agent-config-sync/latest-drift.json \
  --manifest /mnt/d/Documents/Code/GitHub/.claude_code/config/agent-sync.toml \
  --id <ID> [--id <ID> ...]
```

Exit `22` means the report is **stale** — a file changed since the scan. Do not
work around it. Re-run `agent-config-report` and start over with the new ids.

Show Leland the plan verbatim, plus a one-line explanation per action of what
changes and why it is safe.

## 3. Get approval for the exact scope

Ask explicitly, naming the item ids and the files that will be written. An
approval covers only the ids in that message. If Leland adds one afterwards,
dry-run again.

## 4. Apply

```bash
python3 /mnt/d/Documents/Code/GitHub/.claude_code/tools/agent-config-sync/merge.py apply \
  --drift ~/.local/state/agent-config-sync/latest-drift.json \
  --manifest /mnt/d/Documents/Code/GitHub/.claude_code/config/agent-sync.toml \
  --id <ID> [--id <ID> ...]
```

Report the backup directory it prints. **Plugin commands are printed, never
run** — hand them to Leland to execute; that is deliberate.

## 5. Verify

Re-run the scan (`agent-config-report` step 1). Expected drift should be gone
and nothing new should appear. If something new appears, say so plainly and
offer the restore command:

```bash
python3 /mnt/d/Documents/Code/GitHub/.claude_code/tools/agent-config-sync/merge.py restore \
  --backup-dir <the directory printed by apply>
```

If a repository file changed, follow the house rules: typecheck-equivalent
(`python3 -m pytest tools/agent-config-sync/tests/ -q`), then commit —
only when Leland asks.

## When to escalate to /codex

Recommend an independent cross-provider review — and only then — when there is
a **concrete** advantage:

- An ambiguous semantic merge in a settings field where both sides look valid.
- A Codex-specific setting (anything under `~/.codex/`).
- A high-risk conflict: hooks, permissions, or anything touching credentials
  handling.

Scheduling is never a reason. Commit everything first (`/codex:review` needs a
clean tree, and Sol is review-only). Codex recommendations are **advisory** —
they can change how you explain a conflict, never which ids get applied.
Leland approves the final patch, not an agent-to-agent conversation.

## Rules

- Never apply an id that was not named.
- Never touch a `platform_overlay` item; the tool refuses, and so should you.
- Never edit `/home/leland` config to "fix" drift — WSL is the authority, and
  changing it is Leland's job, not a merge.
- Never bypass a stale-report rejection.
- Never run `claude plugin install/update/enable/disable` yourself.
- Never print a value from a redacted field.
````

- [ ] **Step 2: Verify the skill file and its paths**

```bash
python3 - <<'PY'
import re, pathlib
p = pathlib.Path('/mnt/d/Documents/Code/GitHub/.claude_code/claude/skills/agent-config-merge/SKILL.md')
text = p.read_text(encoding='utf-8')
assert text.startswith('---') and 'name: agent-config-merge' in text
for ref in re.findall(r'/mnt/d/[^\s`"]+\.(?:py|toml|md)', text):
    print('ok ' if pathlib.Path(ref).exists() else 'MISSING ', ref)
PY
```

Expected: every referenced path prints `ok`.

- [ ] **Step 3: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/.claude_code add claude/skills/agent-config-merge/SKILL.md
git -C /mnt/d/Documents/Code/GitHub/.claude_code commit -m "feat(agent-config-sync): agent-config-merge skill with /codex escalation guidance"
```

---

## Task 13: Repository wiring, live smoke test, version bump, and changelog

**Files:**
- Create: `tools/agent-config-sync/tests/test_live_smoke.py`
- Modify: `README.md`
- Modify: `CHANGELOG.md` (via the version tool — never by hand)
- Modify: `.claude-plugin/marketplace.json` (**only** if the decision in Step 4 is to package)

**Interfaces:**
- Consumes: everything.
- Produces: an installed, documented, versioned feature.

- [ ] **Step 1: Write the opt-in live smoke test**

Create `tools/agent-config-sync/tests/test_live_smoke.py`:

```python
"""Opt-in live smoke test.

Skipped unless ACS_LIVE=1. It runs the real scanner against the real machine
read-only, and (with ACS_LIVE_MODEL=1) the real `claude -p` analyzer.

    ACS_LIVE=1 python3 -m pytest tools/agent-config-sync/tests/test_live_smoke.py -v
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

REPO = Path(__file__).resolve().parents[3]
MANIFEST = REPO / "config" / "agent-sync.toml"

live = pytest.mark.skipif(os.environ.get("ACS_LIVE") != "1",
                          reason="set ACS_LIVE=1 to run against this machine")


@live
def test_scanner_runs_clean_against_this_machine(tmp_path: Path):
    out = tmp_path / "drift.json"
    result = subprocess.run(
        [sys.executable, str(REPO / "tools/agent-config-sync/scan.py"),
         "--manifest", str(MANIFEST), "--out", str(out),
         "--state-dir", str(tmp_path)],
        capture_output=True, text=True)
    assert result.returncode in (0, 10), result.stderr
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["scanner_version"]
    # Nothing that looks like a credential may appear anywhere in the document.
    blob = json.dumps(doc)
    for needle in ("sk-", "ghp_", "-----BEGIN", "AKIA"):
        assert needle not in blob, f"possible secret leak: {needle}"


@live
def test_scan_is_read_only(tmp_path: Path):
    import manifest as mf

    m = mf.load_manifest(MANIFEST)
    watched = [m.roots.wsl_home / ".claude" / "settings.json",
               m.roots.wsl_home / ".config" / "agents" / "AGENTS.md"]
    before = {p: p.stat().st_mtime_ns for p in watched if p.exists()}
    subprocess.run(
        [sys.executable, str(REPO / "tools/agent-config-sync/scan.py"),
         "--manifest", str(MANIFEST), "--out", str(tmp_path / "d.json"),
         "--state-dir", str(tmp_path)], capture_output=True, text=True)
    for path, mtime in before.items():
        assert path.stat().st_mtime_ns == mtime, f"scan modified {path}"


@pytest.mark.skipif(os.environ.get("ACS_LIVE_MODEL") != "1",
                    reason="set ACS_LIVE_MODEL=1 to call the real claude CLI")
def test_real_claude_returns_a_schema_valid_analysis(tmp_path: Path):
    import analyze as az

    out = tmp_path / "drift.json"
    subprocess.run(
        [sys.executable, str(REPO / "tools/agent-config-sync/scan.py"),
         "--manifest", str(MANIFEST), "--out", str(out),
         "--state-dir", str(tmp_path)], capture_output=True, text=True)
    doc = json.loads(out.read_text(encoding="utf-8"))
    analysis = az.run(doc, claude_bin="claude",
                      prompt_path=REPO / "tools/agent-config-sync/prompts/report-v1.md",
                      timeout_s=300, max_turns=6)
    assert az.validate_analysis(analysis) == []
```

- [ ] **Step 2: Run the live smoke test and read its output**

```bash
ACS_LIVE=1 python3 -m pytest /mnt/d/Documents/Code/GitHub/.claude_code/tools/agent-config-sync/tests/test_live_smoke.py -v
```

Expected: PASS (2 tests; the model test skips). If the secret-leak assertion trips, **stop** — fix `config/agent-sync.toml` and the secret patterns before going further, and do not commit the drift output.

- [ ] **Step 3: Run the real end-to-end pipeline once and read the report**

```bash
/mnt/d/Documents/Code/GitHub/.claude_code/tools/agent-config-sync/bin/agent-config-sync.sh
echo "exit=$?"
```

Then read `~/.local/state/agent-config-sync/latest-report.md` in full. This is the acceptance moment for the whole feature: the report should be something you could hand to a colleague. Fix `render.py` wording or the manifest if it is not.

- [ ] **Step 4: Decide whether these skills get packaged**

Both skills call `python3 /mnt/d/Documents/Code/GitHub/.claude_code/tools/...` — absolute machine paths. Per the precedent already set in `CHANGELOG.md` (2026-08-02) for `version-manager`, `repo-doctor`, `update-code-map`, and `yt-transcript`, skills that ship bundled tools are **not** added to `.claude-plugin/marketplace.json`.

Do not add them to the marketplace. If you disagree after reading that changelog entry, raise it with Leland rather than deciding alone.

- [ ] **Step 5: Add a README section**

In `README.md`, add this after the existing skills listing (match the surrounding heading level and tone — read the neighbouring sections first):

```markdown
### Agent config sync (WSL-authoritative)

`tools/agent-config-sync/` keeps agent configuration aligned across WSL, this
repository, and a Windows desktop — **report-first, never automatic**.

- WSL is the authority for portable intent; this repo is the sanitized record;
  Windows is a derived target with a protected overlay.
- A deterministic scanner (`scan.py`) produces a drift document containing no
  secret values — only pointers, reason codes, types, and hashes.
- When (and only when) there is drift, a bounded `claude -p` call adds judgment
  and `render.py` writes the Markdown report.
- Applying anything is a separate, approved operation (`merge.py`), which
  re-verifies fingerprints, backs up every target, and can restore.
- Plugin code is never copied; plugin commands are proposed, never executed.

Skills: `agent-config-report` (scan and explain) and `agent-config-merge`
(apply approved items). Operator guide: `Docs/agent-config-sync.md`.
```

- [ ] **Step 6: Run the full suite one last time**

```bash
python3 -m pytest /mnt/d/Documents/Code/GitHub/.claude_code/tools/agent-config-sync/tests/ -q
```

Expected: PASS, with the live-smoke tests skipped.

- [ ] **Step 7: Bump the version and write the changelog with the tool**

Per the house rule, never hand-edit a version or a changelog heading.

```bash
python3 ~/.claude/skills/version-manager/version_tool.py --repo /mnt/d/Documents/Code/GitHub/.claude_code check
python3 ~/.claude/skills/version-manager/version_tool.py --repo /mnt/d/Documents/Code/GitHub/.claude_code release minor
```

Read the dry-run output. Then curate the generated notes into prose in a file and apply:

```bash
cat > /tmp/claude-1000/acs-notes.md <<'EOF'
- **New: WSL-authoritative agent config sync.** A report-first pipeline that
  keeps agent configuration aligned across WSL, this repository, and a Windows
  desktop without ever applying a change unattended. A deterministic scanner
  (`tools/agent-config-sync/scan.py`) reads only what `config/agent-sync.toml`
  declares, normalizes away cosmetic differences (line endings, JSON key order,
  `/home/leland` vs `C:\Users\...`), and emits a drift document that carries no
  secret values — denied keys are represented by a pointer, a reason code, a
  type, and a hash. When there is no drift, no model runs at all. When there is,
  a bounded `claude -p` call supplies judgment only, and a deterministic renderer
  writes the Markdown report, so a malformed model response can never replace the
  last good one. Applying is a separate approved step: `merge.py` acts only on
  item ids you name, rejects a report whose files moved since the scan, backs up
  every target, and restores. Plugin code is never copied between environments —
  a newer native build is preserved unless you pin it, and plugin commands are
  printed for you to run rather than executed. Two skills drive it:
  `agent-config-report` and `agent-config-merge`. Operator guide:
  `Docs/agent-config-sync.md`.
EOF
python3 ~/.claude/skills/version-manager/version_tool.py \
  --repo /mnt/d/Documents/Code/GitHub/.claude_code \
  release minor --notes /tmp/claude-1000/acs-notes.md --apply
```

- [ ] **Step 8: Local review before pushing**

Per the house rules, review runs **before** push. Use the `code-reviewer` agent
on the full feature diff, focusing on the secret boundary, and reconcile any
findings before continuing.

```bash
git -C /mnt/d/Documents/Code/GitHub/.claude_code log --oneline -14
git -C /mnt/d/Documents/Code/GitHub/.claude_code diff --stat HEAD~13
```

Auth/credential-adjacent work also warrants an independent
`/codex:adversarial-review` — this feature reads credential-bearing files, so
run it and reconcile disagreements explicitly.

- [ ] **Step 9: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/.claude_code add README.md CHANGELOG.md tools/agent-config-sync/tests/test_live_smoke.py
git -C /mnt/d/Documents/Code/GitHub/.claude_code status --porcelain
git -C /mnt/d/Documents/Code/GitHub/.claude_code commit -m "docs(agent-config-sync): README, live smoke test, changelog and version bump"
```

---

## Self-Review

Run after Task 13, before declaring the feature done.

### Design coverage

| Design section | Task(s) |
|---|---|
| Authority model (three-way comparison) | 4 |
| Paths / manifest-declared roots | 1 |
| Repository structure | 1–13 (File Structure above) |
| Ownership and merge policy (4 policies) | 1, 3, 4 |
| Plugin handling | 5, 11, 12 |
| Secret and state boundary | 1, 3 (+ live assertion in 13) |
| Deterministic scan (8 steps) | 1–6 |
| Claude-first report generation | 8 |
| Report format | 7 |
| Reviewed application workflow (11 steps) | 11, 12 |
| Backups and recovery | 11 |
| Scheduling | 9 |
| Testing (17 cases) | table below |
| Acceptance criteria | table below |

### Design test-case coverage

| # | Case | Test |
|---|---|---|
| 1 | No drift; Claude not invoked | `test_no_drift_exits_zero_and_never_calls_the_model` (T9), `test_identical_layers_produce_no_actionable_drift` (T6) |
| 2 | Portable WSL addition | `test_wsl_ahead_of_an_aligned_baseline_publishes` (T4) |
| 3 | Repo record awaiting Windows reconciliation | `test_baseline_ahead_of_windows_reconciles_windows` (T4) |
| 4 | Independent WSL and Windows edits | `test_wsl_and_windows_disagree_is_a_conflict_with_no_winner` (T4) |
| 5 | Windows-only protected keys | `test_platform_overlay_is_always_protected_and_never_actionable` (T4), `test_windows_owned_field_survives_an_applied_merge` (T11) |
| 6 | Additive skill change and attempted deletion | `test_additive_deletion_requires_approval` (T4) |
| 7 | Newer Windows plugin, no pin | `test_newer_native_version_without_a_pin_is_preserved_not_downgraded` (T5) |
| 8 | Explicit pin violation | `test_pin_violation_is_a_conflict` (T5) |
| 9 | MCP definition with inline secrets | `test_extract_json_redacts_inline_secret_values` (T3), `test_no_secret_value_reaches_the_document` (T6) |
| 10 | Malformed JSON and TOML | `test_extract_malformed_json_records_a_location_not_content` (T3), `test_normalize_toml_reports_location_without_content` (T2) |
| 11 | WSL-to-Windows path adaptation | `test_tokenize_then_render_round_trips_wsl_to_windows` (T2), `test_reconcile_windows_renders_paths_in_windows_form` (T11) |
| 12 | Unknown files and fields | `test_extract_json_reports_undeclared_top_level_keys_as_unknown` (T3), `test_undeclared_field_that_differs_is_a_conflict_asking_for_a_policy` (T4) |
| 13 | Stale report fingerprints | `test_a_report_whose_source_moved_since_the_scan_is_stale`, `test_apply_refuses_a_stale_item` (T11) |
| 14 | Invalid / incomplete / timed-out model output | `test_run_raises_on_*` ×5, `test_render_cli_keeps_the_previous_report_when_the_model_fails` (T8) |
| 15 | Interrupted atomic write | `test_interrupted_write_preserves_the_previous_file` (T6) |
| 16 | Backup restoration | `test_restore_returns_every_target_to_its_pre_merge_content`, `test_restore_recreates_a_file_that_did_not_exist_before` (T11) |
| 17 | Idempotence after an approved merge | `test_applying_the_same_approved_change_twice_changes_nothing`, `test_a_second_scan_after_applying_shows_no_remaining_drift` (T11) |

### Acceptance-criteria checks

Confirm each by pointing at a passing test or a command you ran — not by reasoning:

- [ ] WSL is never written. `merge.py` has no code path targeting the `wsl` layer — grep it: `grep -n '"wsl"' tools/agent-config-sync/merge.py` should show only *reads*.
- [ ] No secret value in drift, prompts, reports, logs, exceptions, snapshots, or commits — T3 + T6 + T8 assertions, plus the live check in T13.
- [ ] No model runs without drift — T9.
- [ ] Windows-owned fields survive — T4 + T11.
- [ ] Plugin code is never copied — `plugins.py` opens exactly two JSON files; grep for `shutil`/`copy` in it (expect none).
- [ ] No downgrade without a pin — T5.
- [ ] Invalid analysis cannot replace a valid report — T8.
- [ ] Stale reports cannot be applied — T11.
- [ ] Applying twice changes nothing — T11.
- [ ] Every applied change has a verified restoration path — T11.

### Type and name consistency

Names that cross task boundaries — verify they match everywhere before finishing:

- `Roots`, `Entry`, `SecretPolicy`, `Manifest`, `Manifest.pins`, `Entry.policy_for`, `Entry.rel_for_layer`, `Roots.for_layer`
- `Unit` (with `.unit_id`), `Redaction` (with `.as_dict`), `extract.LAYERS`
- `DriftItem` (with `.as_dict`), `compare.ACTIONABLE`, `compare.counts`
- `PluginState`, `classify_plugins(desired, wsl_native, windows_native, pins)`
- `drift.write_atomic`, `drift.dump`, `drift.has_actionable`, `drift.validate_document`
- `render.render_markdown(doc, analysis)`, `render.empty_analysis`, `render.SECTIONS`
- `analyze.run(doc, *, claude_bin, prompt_path, timeout_s, max_turns)`
- `merge.Action`, `merge.Plan`, `merge.write_target`, exit constants

Run a mechanical check:

```bash
grep -rn "def \(load_manifest\|policy_for\|extract_entry\|classify\|compare_entry\|classify_plugins\|render_markdown\|plan_merge\|apply_plan\|restore\)\b" \
  /mnt/d/Documents/Code/GitHub/.claude_code/tools/agent-config-sync/*.py
```

Every signature printed must match the **Interfaces** block of the task that declared it.

### Known scope limits (state these when reporting completion)

1. **Plugin operations are proposed, never executed.** `merge.py` prints `claude plugin …` commands; a human runs them. Recorded in each backup's `manual_recovery`.
2. **Backups are never pruned.** Per design, retention is out of scope for the initial implementation.
3. **`portable_additive` deletions are reported, never applied.** There is no code path that deletes a file from a target.
4. **Non-Claude CLIs (Codex, Copilot, Gemini, Pi) are compared, not reconciled through their own managers** — their instruction files are ordinary text entries.

---

## Execution Handoff

Plan complete and saved to `Docs/plans/2026-08-10-agent-config-sync-implementation-plan.md`.

Two execution options:

1. **Subagent-Driven (recommended)** — a fresh subagent per task, with review between tasks and fast iteration.
2. **Inline Execution** — execute tasks in this session using `superpowers:executing-plans`, batching with checkpoints for review.



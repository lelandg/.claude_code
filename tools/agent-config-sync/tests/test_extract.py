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
    # redact_tree's return type is honestly `object` (a redacted tree can be
    # a dict, a list, or a scalar) -- narrow before indexing rather than
    # loosening the signature.
    assert isinstance(cleaned, dict)
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
    assert isinstance(cleaned, dict)
    assert set(cleaned["env"]) == {"API_KEY", "NODE_ENV"}
    assert cleaned["env"]["API_KEY"] == ex.REDACTED
    assert cleaned["env"]["NODE_ENV"] == "production"


def test_redact_walks_lists():
    data = {"servers": [{"password": "p"}, {"name": "ok"}]}
    cleaned, redactions = ex.redact_tree(data, SECRETS)
    assert isinstance(cleaned, dict)
    assert cleaned["servers"][0]["password"] == ex.REDACTED
    assert redactions[0].pointer == "servers[0].password"


# --- extraction ------------------------------------------------------------

def make_entry(*, id: str = "e", policy: str = "portable_authoritative",
              kind: str = "text", wsl: str | None = "a.md",
              repo: str | None = "a.md", windows: str | None = "a.md",
              globs: tuple[str, ...] = (),
              fields: dict[str, str] | None = None) -> mf.Entry:
    # Explicit keyword arguments, not a dict-splat (Task 3 fix round 1,
    # Finding I3): dict(id=..., ...) infers dict[str, str] from its all-str
    # literal, so a later override with a tuple (globs) or dict (fields)
    # collides with that inferred type at the mf.Entry(**base) call.
    return mf.Entry(id=id, policy=policy, kind=kind, wsl=wsl, repo=repo,
                    windows=windows, globs=globs,
                    fields=fields if fields is not None else {})


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


def test_extract_records_portability_warnings_after_tokenization(tmp_path: Path):
    (tmp_path / "a.md").write_text(
        "hook: /usr/bin/python3 /home/leland/.claude/tools/guard.py\n",
        encoding="utf-8")
    units = ex.extract_entry(make_entry(), "wsl", tmp_path, SECRETS, ROOTS)
    # The home path tokenizes to {HOME} and is portable; /usr/bin is not.
    assert units[0].portability
    assert any("/usr/" in w for w in units[0].portability)
    assert not any("/home/" in w for w in units[0].portability)


def test_extract_records_no_portability_warning_for_portable_text(tmp_path: Path):
    (tmp_path / "a.md").write_text("hook: /home/leland/.claude/x.py\n",
                                   encoding="utf-8")
    units = ex.extract_entry(make_entry(), "wsl", tmp_path, SECRETS, ROOTS)
    assert units[0].portability == ()


def test_extract_redaction_is_not_misattributed_to_a_sibling_pointer(tmp_path: Path):
    # Fix round 1, Finding 1: r.pointer.startswith(pointer) has no path
    # boundary, so a secret at "envFoo.token" was wrongly attributed to the
    # unrelated sibling unit "env" because "envFoo.token".startswith("env").
    (tmp_path / "s.json").write_text(
        '{"env": {"NODE_ENV": "production"}, '
        '"envFoo": {"a": 1, "token": "leak-value"}}',
        encoding="utf-8")
    entry = make_entry(kind="json", wsl="s.json",
                       fields={"env": "portable_authoritative",
                               "envFoo.a": "portable_authoritative"})
    units = ex.extract_entry(entry, "wsl", tmp_path, SECRETS, ROOTS)
    by_key = {u.key: u for u in units}
    assert by_key["env"].redactions == ()
    assert by_key["envFoo.a"].redactions == ()
    all_redacted_pointers = {r.pointer for u in units for r in u.redactions}
    assert "envFoo.token" not in all_redacted_pointers

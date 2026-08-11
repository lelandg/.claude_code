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

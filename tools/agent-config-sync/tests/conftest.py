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

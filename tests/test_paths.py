"""Tests for STE100_WORKSPACE path resolution."""

from __future__ import annotations

from pathlib import Path

import pytest

from ste100.core.paths import (
    WORKSPACE_ENV,
    resolve_optional_user_path,
    resolve_user_path,
)


def test_resolve_absolute_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(WORKSPACE_ENV, raising=False)
    absolute = tmp_path / "doc.txt"
    assert resolve_user_path(str(absolute)) == absolute


def test_resolve_relative_with_workspace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(WORKSPACE_ENV, str(tmp_path))
    assert resolve_user_path("docs/a.txt") == tmp_path / "docs" / "a.txt"


def test_resolve_relative_without_workspace_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(WORKSPACE_ENV, raising=False)
    with pytest.raises(ValueError, match=WORKSPACE_ENV):
        resolve_user_path("relative.txt")


def test_resolve_rejects_relative_workspace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(WORKSPACE_ENV, "not/absolute")
    with pytest.raises(ValueError, match="absolute path"):
        resolve_user_path("file.txt")


def test_resolve_optional_none() -> None:
    assert resolve_optional_user_path(None) is None
    assert resolve_optional_user_path("  ") is None


def test_resolve_optional_relative(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(WORKSPACE_ENV, str(tmp_path))
    assert resolve_optional_user_path("g.yml") == str(tmp_path / "g.yml")

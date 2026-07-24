"""Tests for git working-tree changed-file discovery and check."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from ste100.core.git_files import (
    DEFAULT_GLOBS,
    NotAGitRepositoryError,
    check_changed_files,
    filter_by_globs,
    find_git_root,
    list_changed_paths,
)


def _run_git(cwd: Path, *args: str) -> None:
    completed = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0


@pytest.fixture
def git_fixture(tmp_path: Path) -> Path:
    """Tiny git repo: committed baseline + local doc changes."""
    root = tmp_path / "repo"
    root.mkdir()
    _run_git(root, "init")
    _run_git(root, "config", "user.email", "test@example.com")
    _run_git(root, "config", "user.name", "Test User")

    (root / "README.md").write_text("Close the valve.\n", encoding="utf-8")
    (root / "notes.py").write_text("print('hi')\n", encoding="utf-8")
    _run_git(root, "add", "README.md", "notes.py")
    _run_git(root, "commit", "-m", "baseline")

    # Modified tracked doc (non-compliant)
    (root / "README.md").write_text("Utilize the tool.\n", encoding="utf-8")
    # New untracked doc
    (root / "guide.txt").write_text("Close the valve.\n", encoding="utf-8")
    # Untracked non-doc should be ignored by default globs
    (root / "scratch.py").write_text("x = 1\n", encoding="utf-8")
    # New adoc
    (root / "proc.adoc").write_text("Utilize the system.\n", encoding="utf-8")
    return root


def test_find_git_root_and_not_repo(tmp_path: Path, git_fixture: Path) -> None:
    assert find_git_root(git_fixture) == git_fixture.resolve()
    bare = tmp_path / "not-a-repo"
    bare.mkdir()
    with pytest.raises(NotAGitRepositoryError):
        find_git_root(bare)


def test_list_changed_paths_includes_modified_and_untracked(
    git_fixture: Path,
) -> None:
    paths = list_changed_paths(cwd=git_fixture)
    rels = {str(p.relative_to(git_fixture)) for p in paths}
    assert "README.md" in rels
    assert "guide.txt" in rels
    assert "proc.adoc" in rels
    assert "scratch.py" in rels


def test_filter_by_default_globs(git_fixture: Path) -> None:
    paths = list_changed_paths(cwd=git_fixture)
    filtered = filter_by_globs(paths, DEFAULT_GLOBS)
    rels = {str(p.relative_to(git_fixture)) for p in filtered}
    assert rels == {"README.md", "guide.txt", "proc.adoc"}


def test_check_changed_files_aggregate(git_fixture: Path) -> None:
    payload = check_changed_files(cwd=git_fixture)
    assert payload["files_checked"] == 3
    assert payload["compliant"] is False
    assert payload["files_with_errors"] >= 1
    by_path = {f["path"]: f for f in payload["files"]}
    assert by_path["README.md"]["compliant"] is False
    assert by_path["guide.txt"]["compliant"] is True
    assert by_path["proc.adoc"]["compliant"] is False
    assert set(payload["globs"]) == set(DEFAULT_GLOBS)


def test_check_changed_custom_glob(git_fixture: Path) -> None:
    payload = check_changed_files(globs=["*.txt"], cwd=git_fixture)
    assert payload["files_checked"] == 1
    assert payload["files"][0]["path"] == "guide.txt"
    assert payload["compliant"] is True


def test_check_changed_files_base_merge_base(tmp_path: Path) -> None:
    """branch-vs-base: files differing from merge-base(HEAD, base)."""
    root = tmp_path / "repo"
    root.mkdir()
    _run_git(root, "init")
    _run_git(root, "config", "user.email", "test@example.com")
    _run_git(root, "config", "user.name", "Test User")
    # Ensure a default branch name for older/newer git.
    _run_git(root, "checkout", "-b", "main")
    (root / "README.md").write_text("Close the valve.\n", encoding="utf-8")
    _run_git(root, "add", "README.md")
    _run_git(root, "commit", "-m", "baseline")

    _run_git(root, "checkout", "-b", "feature")
    (root / "feature.md").write_text("Utilize the tool.\n", encoding="utf-8")
    _run_git(root, "add", "feature.md")
    _run_git(root, "commit", "-m", "feature change")

    payload = check_changed_files(cwd=root, base="main", include_untracked=False)
    assert payload["base"] == "main"
    assert payload["merge_base"]
    paths = {f["path"] for f in payload["files"]}
    assert "feature.md" in paths
    assert payload["compliant"] is False

"""Discover and check git working-tree / branch-vs-base changes for STE."""

from __future__ import annotations

import fnmatch
import subprocess
from pathlib import Path
from typing import Any

from ste100.core.analyzer import analyze
from ste100.core.schema import AnalysisResult
from ste100.core.serialize import to_json, to_sarif

DEFAULT_GLOBS: tuple[str, ...] = ("*.md", "*.txt", "*.rst", "*.adoc")


class NotAGitRepositoryError(RuntimeError):
    """Raised when no git repository is found walking up from cwd."""


def find_git_root(start: Path | None = None) -> Path:
    """Return the git work tree root, walking up from ``start`` (default cwd)."""
    cwd = (start or Path.cwd()).resolve()
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise NotAGitRepositoryError(
            "git executable not found; install git to use check-changed."
        ) from exc
    if completed.returncode != 0:
        err = (completed.stderr or completed.stdout or "").strip()
        raise NotAGitRepositoryError(
            err or f"Not a git repository (or any parent): {cwd}"
        )
    return Path(completed.stdout.strip()).resolve()


def _git_lines(args: list[str], *, cwd: Path) -> list[str]:
    completed = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        err = (completed.stderr or completed.stdout or "").strip()
        raise RuntimeError(err or f"git {' '.join(args)} failed")
    return [line for line in completed.stdout.splitlines() if line.strip()]


def resolve_merge_base(base: str, *, cwd: Path) -> str:
    """Return the merge-base commit of HEAD and ``base``."""
    lines = _git_lines(["merge-base", "HEAD", base], cwd=cwd)
    if not lines:
        raise RuntimeError(f"git merge-base HEAD {base} returned no commit")
    return lines[0].strip()


def list_changed_paths(
    *,
    cwd: Path | None = None,
    include_untracked: bool = True,
    base: str | None = None,
) -> list[Path]:
    """Union of changed paths relative to HEAD or a branch merge-base.

    When ``base`` is None: working tree vs HEAD (unstaged + staged) and optional
    untracked. When ``base`` is set: files differing from
    ``git merge-base HEAD <base>`` (working tree + index) plus optional untracked.

    Paths are absolute and unique, sorted by path relative to the git root.
    Missing (deleted) paths are skipped.
    """
    root = find_git_root(cwd)
    names: set[str] = set()

    if base:
        merge_base = resolve_merge_base(base, cwd=root)
        names.update(_git_lines(["diff", "--name-only", merge_base], cwd=root))
        names.update(
            _git_lines(["diff", "--cached", "--name-only", merge_base], cwd=root)
        )
    else:
        names.update(_git_lines(["diff", "--name-only", "HEAD"], cwd=root))
        names.update(_git_lines(["diff", "--cached", "--name-only"], cwd=root))

    if include_untracked:
        names.update(
            _git_lines(["ls-files", "--others", "--exclude-standard"], cwd=root)
        )

    paths: list[Path] = []
    for name in names:
        candidate = (root / name).resolve()
        if candidate.is_file():
            paths.append(candidate)

    paths.sort(key=lambda p: str(p.relative_to(root)))
    return paths


def _matches_globs(path: Path, globs: list[str] | tuple[str, ...]) -> bool:
    name = path.name
    for pattern in globs:
        if fnmatch.fnmatch(name, pattern):
            return True
        if fnmatch.fnmatch(str(path), pattern):
            return True
    return False


def filter_by_globs(
    paths: list[Path],
    globs: list[str] | tuple[str, ...] | None = None,
) -> list[Path]:
    """Keep paths whose basename (or full path) matches any glob."""
    patterns = tuple(globs) if globs else DEFAULT_GLOBS
    return [p for p in paths if _matches_globs(p, patterns)]


def _collect_changed_analyses(
    globs: list[str] | None,
    text_type: str,
    glossary: str | None,
    *,
    cwd: Path | None,
    include_untracked: bool,
    base: str | None,
) -> tuple[Path, list[str], list[tuple[str, AnalysisResult]], str | None]:
    root = find_git_root(cwd)
    patterns = list(globs) if globs else list(DEFAULT_GLOBS)
    merge_base: str | None = None
    if base:
        merge_base = resolve_merge_base(base, cwd=root)
    changed = list_changed_paths(
        cwd=root,
        include_untracked=include_untracked,
        base=base,
    )
    matched = filter_by_globs(changed, patterns)

    analyses: list[tuple[str, AnalysisResult]] = []
    for path in matched:
        text = path.read_text(encoding="utf-8")
        result = analyze(text, text_type=text_type, glossary_path=glossary)
        analyses.append((str(path.relative_to(root)), result))
    return root, patterns, analyses, merge_base


def check_changed_files(
    globs: list[str] | None = None,
    text_type: str = "auto",
    glossary: str | None = None,
    *,
    cwd: Path | None = None,
    include_untracked: bool = True,
    base: str | None = None,
) -> dict[str, Any]:
    """Analyze changed doc files in the working tree vs HEAD or merge-base.

    ``compliant`` is true only when every analyzed file has no ERROR findings.
    """
    root, patterns, analyses, merge_base = _collect_changed_analyses(
        globs,
        text_type,
        glossary,
        cwd=cwd,
        include_untracked=include_untracked,
        base=base,
    )

    files: list[dict[str, Any]] = []
    error_files = 0
    for rel, result in analyses:
        if not result.compliant:
            error_files += 1
        files.append(
            {
                "path": rel,
                "absolute_path": str(root / rel),
                "compliant": result.compliant,
                "result": to_json(result),
            }
        )

    payload: dict[str, Any] = {
        "git_root": str(root),
        "globs": patterns,
        "text_type": text_type,
        "base": base,
        "merge_base": merge_base,
        "files_checked": len(files),
        "files_with_errors": error_files,
        "compliant": error_files == 0,
        "files": files,
    }
    return payload


def check_changed_files_sarif(
    globs: list[str] | None = None,
    text_type: str = "auto",
    glossary: str | None = None,
    *,
    cwd: Path | None = None,
    include_untracked: bool = True,
    base: str | None = None,
) -> dict[str, Any]:
    """Aggregate SARIF for all matching changed files."""
    root, patterns, analyses, merge_base = _collect_changed_analyses(
        globs,
        text_type,
        glossary,
        cwd=cwd,
        include_untracked=include_untracked,
        base=base,
    )

    all_results: list[dict[str, Any]] = []
    error_files = 0
    for rel, result in analyses:
        if not result.compliant:
            error_files += 1
        sarif = to_sarif(result)
        for item in sarif["runs"][0]["results"]:
            locations = item.setdefault("locations", [{}])
            phys = locations[0].setdefault("physicalLocation", {})
            phys["artifactLocation"] = {"uri": rel}
            all_results.append(item)

    return {
        "version": "2.1.0",
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "asd-ste100-checker",
                        "informationUri": (
                            "https://github.com/search?q=asd-ste100-checker"
                        ),
                    }
                },
                "results": all_results,
                "properties": {
                    "compliant": error_files == 0,
                    "files_checked": len(analyses),
                    "files_with_errors": error_files,
                    "git_root": str(root),
                    "globs": patterns,
                    "base": base,
                    "merge_base": merge_base,
                },
            }
        ],
    }


def run_check_changed(
    output: str = "json",
    globs: list[str] | None = None,
    text_type: str = "auto",
    glossary: str | None = None,
    *,
    cwd: Path | None = None,
    include_untracked: bool = True,
    base: str | None = None,
) -> dict[str, Any]:
    """Analyze changed doc files once and serialize as json or sarif.

    Single entry point for adapters; ``check_changed_files`` and
    ``check_changed_files_sarif`` remain as back-compat wrappers.
    """
    fmt = (output or "json").strip().lower()
    if fmt == "sarif":
        return check_changed_files_sarif(
            globs=globs,
            text_type=text_type,
            glossary=glossary,
            cwd=cwd,
            include_untracked=include_untracked,
            base=base,
        )
    if fmt == "json":
        return check_changed_files(
            globs=globs,
            text_type=text_type,
            glossary=glossary,
            cwd=cwd,
            include_untracked=include_untracked,
            base=base,
        )
    raise ValueError(f"Invalid output format {output!r}; expected 'json' or 'sarif'")

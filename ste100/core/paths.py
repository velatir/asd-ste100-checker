"""User path resolution for MCP / env-relative paths."""

from __future__ import annotations

import os
from pathlib import Path

WORKSPACE_ENV = "STE100_WORKSPACE"


def resolve_user_path(path: str) -> Path:
    """Resolve a user-supplied path for MCP tools.

    Absolute paths are returned as-is (canonical for host filesystems).
    Relative paths require ``STE100_WORKSPACE`` and are joined under that root.
    """
    raw = (path or "").strip()
    if not raw:
        raise ValueError("path must be a non-empty string")

    candidate = Path(raw)
    if candidate.is_absolute():
        return candidate

    workspace = (os.environ.get(WORKSPACE_ENV) or "").strip()
    if not workspace:
        raise ValueError(
            f"relative path {raw!r} requires {WORKSPACE_ENV} "
            "(set it to an absolute workspace root, or pass an absolute path)"
        )
    root = Path(workspace)
    if not root.is_absolute():
        raise ValueError(
            f"{WORKSPACE_ENV} must be an absolute path, got {workspace!r}"
        )
    return root / candidate


def resolve_optional_user_path(path: str | None) -> str | None:
    """Resolve an optional path; return ``None`` when unset."""
    if path is None:
        return None
    stripped = path.strip()
    if not stripped:
        return None
    return str(resolve_user_path(stripped))

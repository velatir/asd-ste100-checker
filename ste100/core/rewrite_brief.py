"""Backward-compatible re-exports; implementation lives in agent_brief."""

from ste100.core.agent_brief import (
    DEFAULT_MAX_FINDINGS,
    REWRITE_SPEC,
    build_prompt,
    select_findings,
    suggest_rewrite,
)
from ste100.core.schema import AnalysisResult, Finding

__all__ = [
    "DEFAULT_MAX_FINDINGS",
    "build_prompt",
    "build_rewrite_prompt",
    "select_findings",
    "suggest_rewrite",
]


def build_rewrite_prompt(
    text: str,
    result: AnalysisResult,
    selected: list[Finding],
) -> str:
    return build_prompt(text, result, selected, REWRITE_SPEC)

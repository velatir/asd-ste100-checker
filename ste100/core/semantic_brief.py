"""Backward-compatible re-exports; implementation lives in agent_brief."""

from ste100.core.agent_brief import (
    DEFAULT_MAX_FINDINGS,
    SEMANTIC_SPEC,
    TIER3_RULE_IDS,
    build_prompt,
    filter_tier3_findings,
    select_findings,
    suggest_semantic_review,
)
from ste100.core.schema import AnalysisResult, Finding

__all__ = [
    "DEFAULT_MAX_FINDINGS",
    "TIER3_RULE_IDS",
    "build_prompt",
    "build_semantic_prompt",
    "filter_tier3_findings",
    "select_findings",
    "suggest_semantic_review",
]


def build_semantic_prompt(
    text: str,
    result: AnalysisResult,
    selected: list[Finding],
) -> str:
    return build_prompt(text, result, selected, SEMANTIC_SPEC)

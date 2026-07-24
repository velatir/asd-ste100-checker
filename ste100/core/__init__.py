"""Core engine: schema, analyzer, serializers, safe fixes."""

from __future__ import annotations

from typing import Any

from ste100.core.schema import (
    AnalysisResult,
    DictionaryRecord,
    Finding,
    Glossary,
    GlossaryEntry,
    RuleMeta,
    Severity,
    Suggestion,
    TextType,
    WordStatus,
)

__all__ = [
    "AnalysisResult",
    "DictionaryRecord",
    "Finding",
    "Glossary",
    "GlossaryEntry",
    "RuleMeta",
    "Severity",
    "Suggestion",
    "TextType",
    "WordStatus",
    "analyze",
    "apply_safe_fixes",
    "to_json",
    "to_sarif",
]


def __getattr__(name: str) -> Any:
    # Lazy imports avoid circular deps (analyzer <-> dictionary.engine).
    if name == "analyze":
        from ste100.core.analyzer import analyze

        return analyze
    if name == "apply_safe_fixes":
        from ste100.core.fixes import apply_safe_fixes

        return apply_safe_fixes
    if name == "to_json":
        from ste100.core.serialize import to_json

        return to_json
    if name == "to_sarif":
        from ste100.core.serialize import to_sarif

        return to_sarif
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

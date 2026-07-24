"""Safe 1:1 synonym fixes and shared formatting helpers."""

from __future__ import annotations

import difflib
import re
from typing import Any

from ste100.dictionary.engine import DictionaryEngine, resolve_engine


def _preserve_case(original: str, replacement: str) -> str:
    if original.isupper():
        return replacement.upper()
    if original[:1].isupper() and original[1:].islower():
        return replacement[:1].upper() + replacement[1:].lower()
    if original[:1].isupper():
        return replacement[:1].upper() + replacement[1:]
    return replacement


def apply_safe_fixes(
    text: str,
    glossary_path: str | None = None,
    *,
    dictionary: DictionaryEngine | None = None,
) -> dict[str, Any]:
    """Apply unambiguous 1:1 synonym replacements; return text + unified diff."""
    engine = resolve_engine(dictionary, glossary_path)
    mapping = engine.safe_replacements()
    if not mapping:
        return {
            "original": text,
            "fixed": text,
            "diff": "",
            "replacements_applied": [],
        }

    # Longest keys first to prefer multi-word forms if present
    keys = sorted(mapping.keys(), key=len, reverse=True)
    pattern = re.compile(
        r"\b(" + "|".join(re.escape(k) for k in keys) + r")\b",
        re.IGNORECASE,
    )

    replacements_applied: list[dict[str, str | int]] = []

    def _repl(match: re.Match[str]) -> str:
        original = match.group(0)
        key = original.lower()
        dest = mapping.get(key)
        if dest is None:
            return original
        fixed = _preserve_case(original, dest)
        if fixed != original:
            replacements_applied.append(
                {
                    "from": original,
                    "to": fixed,
                    "start": match.start(),
                    "end": match.end(),
                }
            )
        return fixed

    fixed_text = pattern.sub(_repl, text)
    diff = "".join(
        difflib.unified_diff(
            text.splitlines(keepends=True),
            fixed_text.splitlines(keepends=True),
            fromfile="original",
            tofile="fixed",
        )
    )
    return {
        "original": text,
        "fixed": fixed_text,
        "diff": diff,
        "replacements_applied": replacements_applied,
    }

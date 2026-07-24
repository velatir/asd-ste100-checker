"""Shared PDF-text helpers for the curate pipeline.

Centralizes the line-noise regexes and ``_join_lines`` that were copy-pasted
across ``agent.py``, ``alternatives.py``, and ``rules_parse.py`` after the
curate split.
"""

from __future__ import annotations

import re
from typing import Iterable

# Help / cross-reference prose that bleeds into the alternatives column.
_HELP_NOISE_RE = re.compile(
    r"^(For other|Use this word|Do not use|No other verb|Frequently|"
    r"Help|Category\s+\d|Refer to|See also)\b",
    re.IGNORECASE,
)

# "1. ..." numbered meaning lines.
_NUMBERED_MEANING_RE = re.compile(r"^\d+\.\s*")

# Page / section header noise to drop when mining rule bodies.
_HEADER_NOISE = re.compile(
    r"^(ASD-STE100|Issue\s+\d+|Part\s+[12]|Page\s+|20\d{2}-\d{2}-\d{2}"
    r"|Simplified Technical English|Word$|Approved meaning|"
    r"ALTERNATIVES|STE EXAMPLE|Non-STE example|\(part of speech\))",
    re.IGNORECASE,
)


def join_lines(lines: Iterable[str]) -> str:
    """Collapse an iterable of raw PDF lines into one trimmed string."""
    parts = [re.sub(r"\s+", " ", ln).strip() for ln in lines if ln and ln.strip()]
    return " ".join(parts).strip()

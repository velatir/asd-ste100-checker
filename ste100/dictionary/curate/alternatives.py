"""Extract approved alternatives from ASD-STE100 dictionary columns."""

from __future__ import annotations

import re
from typing import Iterable

from ste100.dictionary.curate.text_util import (
    _HELP_NOISE_RE,
    _NUMBERED_MEANING_RE,
    join_lines as _join_lines,
)

_ALT_WITH_POS_RE = re.compile(
    r"^([A-Z][A-Z0-9\-]*(?:\s+[A-Z][A-Z0-9\-]*){0,5})"
    r"\s*\((?:n|v|adj|adv|prep|conj|art|pron|TN|TV)\)"
    r"(?:\s+[A-Za-z].*)?$"  # tolerate STE-column bleed after POS
)

_STOPWORDS = frozenset(
    {
        "the",
        "a",
        "an",
        "of",
        "to",
        "and",
        "or",
        "in",
        "on",
        "for",
        "is",
        "are",
        "be",
        "by",
        "with",
        "from",
        "that",
        "this",
        "it",
        "as",
        "at",
        "if",
        "when",
        "than",
        "more",
        "must",
        "not",
        "does",
        "did",
        "you",
        "your",
    }
)


def _clean_alt_token(tok: str) -> str | None:
    tok = re.sub(r"\s+", " ", tok).strip().lower()
    if len(tok) < 2:
        return None
    # Fragments from "For other meanings, use:" help lines — not real alts.
    if tok in {"for", "other", "meanings", "this", "word", "do", "not"}:
        return None
    if tok in {"for other", "for other meanings"}:
        return None
    return tok


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[A-Za-z][A-Za-z0-9\-]*", text.lower())


def _alts_from_example_diff(
    headword: str,
    ste_lines: list[str],
    nonste_lines: list[str],
) -> list[str]:
    """Infer approved alternatives by comparing STE vs Non-STE examples.

    When the alternatives column is empty, the STE rewrite often replaces the
    unapproved headword with an approved word visible only in the STE column.
    """
    ste_t = _tokenize(_join_lines(ste_lines))
    non_t = _tokenize(_join_lines(nonste_lines))
    if not ste_t or not non_t:
        return []
    head = headword.lower()
    if head not in non_t and not any(
        n == head or n.startswith(head) or head.startswith(n)
        for n in non_t
        if len(n) > 3
    ):
        return []
    ste_only = [
        t
        for t in ste_t
        if t not in non_t and t not in _STOPWORDS and t != head and len(t) > 1
    ]
    # Prefer content words that look like dictionary alternatives (short).
    candidates = [t for t in ste_only if len(t) <= 20][:5]
    out: list[str] = []
    seen: set[str] = set()
    for a in candidates:
        if a not in seen:
            seen.add(a)
            out.append(a)
    return out


def _extract_alternatives(
    meaning_lines: list[str],
    *,
    approved: bool,
    ste_lines: list[str] | None = None,
    nonste_lines: list[str] | None = None,
    headword: str | None = None,
) -> list[str]:
    alts: list[str] = []

    def _from_line(s: str) -> None:
        # Split multiple WORD (pos) tokens on one line (column bleed / multi-alt).
        embedded = list(
            re.finditer(
                r"\b([A-Z][A-Z0-9\-]*(?:\s+[A-Z][A-Z0-9\-]*){0,4})"
                r"\s*\((?:n|v|adj|adv|prep|conj|art|pron|TN|TV)\)",
                s,
            )
        )
        if len(embedded) > 1:
            for em in embedded:
                cleaned = _clean_alt_token(em.group(1))
                if cleaned:
                    alts.append(cleaned)
            return
        m = _ALT_WITH_POS_RE.match(s.strip())
        if m:
            cleaned = _clean_alt_token(m.group(1))
            if cleaned:
                alts.append(cleaned)
            return
        m = re.match(
            r"^([A-Z][A-Z0-9\-]*(?:\s+[A-Z][A-Z0-9\-]*){0,6})\s*$",
            s.strip(),
        )
        if m:
            cleaned = _clean_alt_token(m.group(1))
            if cleaned:
                alts.append(cleaned)

    if approved:
        text = _join_lines(meaning_lines)
        if not re.search(r"for other meanings", text, re.I):
            return []
        past_help = False
        for line in meaning_lines:
            s = line.strip()
            if re.search(r"for other meanings", s, re.I) or (
                past_help is False and s.lower().startswith("meanings")
            ):
                past_help = True
                # "meanings, use:" line — no alt yet
                if "use:" in s.lower() or s.lower().startswith("for other"):
                    continue
            if not past_help:
                # Also treat "For other" / "meanings, use:" split across lines
                if s.lower() in {"for other", "meanings, use:", "meanings, use"}:
                    past_help = True
                continue
            if _HELP_NOISE_RE.match(s):
                continue
            _from_line(s)
    else:
        for line in meaning_lines:
            s = line.strip()
            if not s:
                continue
            if _NUMBERED_MEANING_RE.match(s):
                continue
            # Skip lowercase prose bleed from STE/Non-STE columns.
            if re.match(r"^[a-z]", s) and not re.search(
                r"\([nv]|adj|adv|prep|conj|art|pron|TN|TV\)",
                s,
            ):
                continue
            # Ellipsis phrase alternatives: NOT… AT THIS TIME / UNTIL…NOT
            if re.search(r"[…\.]{2,}|…", s) and re.match(r"^[A-Z]", s):
                cleaned = _clean_alt_token(
                    s.replace("…", " ").replace("...", " ")
                )
                if cleaned:
                    alts.append(re.sub(r"\s+", " ", cleaned).strip())
                    continue
            if _HELP_NOISE_RE.match(s):
                # Still mine embedded WORD (pos) tokens from help prose
                for em in re.finditer(
                    r"\b([A-Z][A-Z0-9\-]*(?:\s+[A-Z][A-Z0-9\-]*){0,3})"
                    r"\s*\((?:n|v|adj|adv|prep|conj|art|pron|TN|TV)\)",
                    s,
                ):
                    cleaned = _clean_alt_token(em.group(1))
                    if cleaned:
                        alts.append(cleaned)
                continue
            _from_line(s)
        # Also mine WORD (pos) across joined help when line-local miss
        joined = " ".join(meaning_lines)
        if not alts:
            for em in re.finditer(
                r"\b([A-Z][A-Z0-9\-]*(?:\s+[A-Z][A-Z0-9\-]*){0,3})"
                r"\s*\((?:n|v|adj|adv|prep|conj|art|pron|TN|TV)\)",
                joined,
            ):
                cleaned = _clean_alt_token(em.group(1))
                if cleaned:
                    alts.append(cleaned)

        # Fallback: STE vs Non-STE example diff when alternatives column empty.
        if not alts and headword and ste_lines and nonste_lines:
            alts.extend(
                _alts_from_example_diff(headword, ste_lines, nonste_lines)
            )

    out: list[str] = []
    seen: set[str] = set()
    for a in alts:
        if a not in seen:
            seen.add(a)
            out.append(a)
    return out

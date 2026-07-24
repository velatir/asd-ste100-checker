"""Parse ASD-STE100 writing-rule metadata from extracted text."""

from __future__ import annotations

import re
from typing import Iterable

from ste100.core.schema import RuleMeta, TextType
from ste100.dictionary.curate.text_util import _HEADER_NOISE, join_lines as _join_lines

_SECTION_RE = re.compile(
    r"^Section\s+(\d+)\s*[–\-—]\s*(.+)$",
    re.IGNORECASE | re.MULTILINE,
)


def _rule_sort_key(r: RuleMeta) -> tuple:
    m = re.match(r"Rule\s+(\d+)\.(\d+)", r.rule_id)
    if m:
        return (0, int(m.group(1)), int(m.group(2)), r.rule_id)
    g = re.match(r"GR-(\d+)", r.rule_id)
    if g:
        return (1, int(g.group(1)), 0, r.rule_id)
    return (2, 0, 0, r.rule_id)


def parse_rules_from_text(text: str) -> list[RuleMeta]:
    """Extract RuleMeta entries from writing-rules raw text."""
    # Strip page markers
    cleaned = re.sub(r"^----- PAGE \d+ -----\s*", "", text, flags=re.MULTILINE)
    section_map: dict[str, str] = {}
    current_section: str | None = None
    current_section_title: str | None = None

    lines = cleaned.splitlines()
    rules: list[RuleMeta] = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        sec = _SECTION_RE.match(line)
        if sec:
            current_section = f"Section {sec.group(1)}"
            current_section_title = sec.group(2).strip()
            section_map[current_section] = current_section_title
            i += 1
            continue

        rh = re.match(r"^(Rule\s+\d+\.\d+|GR-\d+)\s*$", line, re.I)
        if rh:
            rule_id = rh.group(1)
            # Normalize "Rule 1.1"
            if rule_id.upper().startswith("GR"):
                rule_id = rule_id.upper()
            else:
                m = re.match(r"Rule\s+(\d+\.\d+)", rule_id, re.I)
                rule_id = f"Rule {m.group(1)}" if m else rule_id

            # Title: often on same block — next non-empty lines until blank
            # or next rule/section. First line(s) form the title.
            body_lines: list[str] = []
            j = i + 1
            while j < len(lines):
                nxt = lines[j].strip()
                if re.match(r"^(Rule\s+\d+\.\d+|GR-\d+)\s*$", nxt, re.I):
                    break
                if _SECTION_RE.match(nxt):
                    break
                if nxt.startswith("----- PAGE"):
                    j += 1
                    continue
                if _HEADER_NOISE.match(nxt):
                    j += 1
                    continue
                body_lines.append(nxt)
                j += 1

            # Drop leading empty
            while body_lines and not body_lines[0]:
                body_lines.pop(0)
            # Title = first paragraph (until blank)
            title_parts: list[str] = []
            summary_parts: list[str] = []
            hit_blank = False
            for bl in body_lines:
                if not bl:
                    hit_blank = True
                    continue
                if not hit_blank and len(title_parts) < 3:
                    title_parts.append(bl)
                else:
                    summary_parts.append(bl)
            title = _join_lines(title_parts) or rule_id
            # Keep title short
            if len(title) > 160:
                title = title[:157] + "…"
            summary = _join_lines(summary_parts)[:500] or None

            text_type = None
            blob = f"{title} {summary or ''}".lower()
            if "procedur" in blob:
                text_type = TextType.PROCEDURE
            elif "descript" in blob:
                text_type = TextType.DESCRIPTION

            rules.append(
                RuleMeta(
                    rule_id=rule_id,
                    section=current_section,
                    title=title,
                    summary=summary,
                    text_type=text_type,
                )
            )
            i = j
            continue
        i += 1

    # Deduplicate by rule_id (keep first / richest)
    by_id: dict[str, RuleMeta] = {}
    for r in rules:
        prev = by_id.get(r.rule_id)
        if prev is None:
            by_id[r.rule_id] = r
        elif r.summary and len(r.summary) > len(prev.summary or ""):
            by_id[r.rule_id] = r
    return sorted(by_id.values(), key=_rule_sort_key)

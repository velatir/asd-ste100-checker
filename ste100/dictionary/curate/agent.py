"""Heuristic curation of ASD-STE100 dictionary + rules.

Pipeline:
  1. Read raw extracted text or call ``ste100.dictionary.extract``.
  2. Parse dictionary pages with column-aware heuristics.
  3. Parse writing-rule metadata with regex.
  4. Write ``dictionary.json``, ``rules.json``, and ``ambiguous.md``.

Unofficial project. Not affiliated with ASD.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from ste100.core.schema import DictionaryRecord, WordStatus
from ste100.dictionary import extract as extract_mod
from ste100.dictionary.curate.alternatives import _extract_alternatives
from ste100.dictionary.curate.rules_parse import parse_rules_from_text
from ste100.dictionary.curate.text_util import (
    _HEADER_NOISE,
    _HELP_NOISE_RE,
    _NUMBERED_MEANING_RE,
    join_lines as _join_lines,
)

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_DEFAULT_PDF = Path(__file__).resolve().parents[3] / "ASD-STE100-ISSUE-9.pdf"

_POS_MAP = {
    "n": "noun",
    "v": "verb",
    "adj": "adjective",
    "adv": "adverb",
    "prep": "preposition",
    "conj": "conjunction",
    "art": "article",
    "pron": "pronoun",
    "prefix": "prefix",
    "suffix": "suffix",
    "tn": "technical_noun",
    "tv": "technical_verb",
}

# Headword: "WORD (pos)" / "word (pos)" optionally trailing comma.
_HEAD_RE = re.compile(
    r"^([A-Za-z][A-Za-z0-9\-]*(?:\s+[A-Za-z][A-Za-z0-9\-]*){0,4})"
    r"\s*\(([^)]+)\)\s*,?\s*$"
)
# Standalone POS line for multi-line headwords: "(adv)"
_POS_ONLY_RE = re.compile(r"^\(([^)]+)\)\s*,?\s*$")
_ALSO_FORMS_RE = re.compile(r"^\(also\s+([^)]+)\)\s*$", re.IGNORECASE)


@dataclass
class _ColumnBands:
    word_max: float = 140.0
    meaning_max: float = 280.0
    ste_max: float = 400.0


@dataclass
class _RawEntry:
    page: int
    head_y: float
    word_lines: list[str] = field(default_factory=list)
    meaning_lines: list[str] = field(default_factory=list)
    ste_lines: list[str] = field(default_factory=list)
    nonste_lines: list[str] = field(default_factory=list)
    ambiguous_notes: list[str] = field(default_factory=list)


def _expand_pos(raw: str) -> str:
    token = raw.strip().lower().split(",")[0].strip()
    # Drop comparative notes accidentally captured: "adj" from "adj" OK;
    # junk like "or matte" -> keep as-is lowered.
    if token in _POS_MAP:
        return _POS_MAP[token]
    if token in _POS_MAP.values():
        return token
    # Unknown POS fragment — keep cleaned token for review.
    return token


def _is_approved_surface(word: str) -> bool:
    letters = [c for c in word if c.isalpha()]
    if not letters:
        return False
    return all(c.isupper() for c in letters)


def _split_examples(text: str) -> list[str]:
    return [text] if text else []


def _detect_columns(lines: list[dict[str, Any]]) -> _ColumnBands:
    """Infer column boundaries from header labels when present."""
    word_x = meaning_x = ste_x = nonste_x = None
    for ln in lines:
        if ln["y"] > 100:
            break
        t = ln["text"].strip()
        x = ln["x"]
        if t == "Word" or t.startswith("(part of speech)"):
            word_x = x if word_x is None else min(word_x, x)
        elif "ALTERNATIVES" in t.upper() or t.startswith("Approved meaning"):
            meaning_x = x if meaning_x is None else min(meaning_x, x)
        elif t.upper().startswith("STE EXAMPLE"):
            ste_x = x if ste_x is None else min(ste_x, x)
        elif "NON-STE" in t.upper():
            nonste_x = x if nonste_x is None else min(nonste_x, x)

    if meaning_x is not None and ste_x is not None and nonste_x is not None:
        if word_x is not None:
            word_max = (word_x + meaning_x) / 2.0
        else:
            word_max = meaning_x - 10.0
        return _ColumnBands(
            word_max=word_max,
            meaning_max=(meaning_x + ste_x) / 2.0,
            ste_max=(ste_x + nonste_x) / 2.0,
        )
    return _ColumnBands()


def _assign_col(x: float, bands: _ColumnBands) -> str:
    if x < bands.word_max:
        return "word"
    if x < bands.meaning_max:
        return "meaning"
    if x < bands.ste_max:
        return "ste"
    return "nonste"


def _is_header_footer(text: str, y: float, page_height: float = 792.0) -> bool:
    if y < 82 or y > page_height - 70:
        return True
    if _HEADER_NOISE.match(text.strip()):
        return True
    return False


def _parse_head_and_inflections(
    word_lines: list[str],
) -> tuple[str | None, str | None, list[str], list[str]]:
    """Return (word, pos, inflections, notes_fragments)."""
    if not word_lines:
        return None, None, [], ["empty word column"]

    notes: list[str] = []
    buffer = [ln.strip() for ln in word_lines if ln and ln.strip()]
    if not buffer:
        return None, None, [], ["empty word column"]

    head_text = buffer[0]
    idx = 1
    word: str | None = None
    pos: str | None = None
    alt_spellings: list[str] = []

    m = _HEAD_RE.match(head_text.rstrip(","))
    if m:
        word = m.group(1).strip()
        pos_raw = m.group(2).strip()
        first = pos_raw.split(",")[0].strip().lower()
        if first in _POS_MAP or first in {"tn", "tv"}:
            pos = _expand_pos(pos_raw)
        elif re.match(r"^or\s+", pos_raw, re.I):
            # MATT (or MATTE)
            alt = re.sub(r"^or\s+", "", pos_raw, flags=re.I).strip()
            if alt:
                alt_spellings.append(alt.lower())
            # POS expected on next line
            if idx < len(buffer):
                m = _POS_ONLY_RE.match(buffer[idx])
                if m:
                    pos = _expand_pos(m.group(1))
                    idx += 1
                else:
                    notes.append(f"missing pos after alt spelling in {head_text!r}")
                    return None, None, [], notes
            else:
                notes.append(f"missing pos after alt spelling in {head_text!r}")
                return None, None, [], notes
        else:
            # Phrase form: case (in case of) / least (at least) / provided (that)
            phrase = pos_raw.strip()
            if phrase.lower() == "that" and word:
                word = f"{word} that"
            elif phrase:
                # Prefer the full phrase inside parens when it looks multi-word
                # or is a known particle phrase; else "word phrase".
                if " " in phrase or phrase.lower() in {
                    "that",
                    "of",
                    "to",
                    "for",
                }:
                    if phrase.lower() in {"that", "of", "to", "for"}:
                        word = f"{word} {phrase}"
                    else:
                        word = phrase
                else:
                    word = f"{word} {phrase}"
            if idx < len(buffer):
                m = _POS_ONLY_RE.match(buffer[idx])
                if m:
                    pos = _expand_pos(m.group(1))
                    idx += 1
                else:
                    notes.append(f"missing pos after phrase head {head_text!r}")
                    return None, None, [], notes
            else:
                notes.append(f"missing pos after phrase head {head_text!r}")
                return None, None, [], notes
    else:
        # Multi-line: "back and forth" / "LONGITUDINAL" then "(adv)" / "(adj)"
        if idx < len(buffer):
            m = _POS_ONLY_RE.match(buffer[idx])
            if m:
                word = head_text.rstrip(",").strip()
                pos = _expand_pos(m.group(1))
                idx += 1
        elif idx < len(buffer):
            combined = f"{head_text} {buffer[idx]}".strip()
            m2 = _HEAD_RE.match(combined.rstrip(","))
            if m2:
                word = m2.group(1).strip()
                pos = _expand_pos(m2.group(2))
                idx += 1
            else:
                return None, None, [], [f"unparsed head: {head_text!r}"]
        else:
            return None, None, [], [f"unparsed head: {head_text!r}"]

    assert word is not None and pos is not None

    if pos not in _POS_MAP.values() and pos not in {
        "technical_noun",
        "technical_verb",
    }:
        notes.append(f"odd pos {pos!r}")
        return None, None, [], notes

    inflections: list[str] = list(alt_spellings)
    while idx < len(buffer):
        line = buffer[idx]
        idx += 1
        if not line:
            continue
        also = _ALSO_FORMS_RE.match(line)
        if also:
            for part in re.split(r"[,/]", also.group(1)):
                tok = part.strip(" ()")
                if tok:
                    inflections.append(tok.lower())
            continue
        pos_only = _POS_ONLY_RE.match(line)
        if pos_only:
            inner = pos_only.group(1)
            if re.search(r"[A-Za-z]", inner) and not re.fullmatch(
                r"n|v|adj|adv|prep|conj|art|pron|TN|TV|prefix",
                inner,
                re.I,
            ):
                for part in inner.split(","):
                    tok = part.strip()
                    if tok and not tok.lower().startswith("also"):
                        inflections.append(tok.lower())
            continue
        # Split comparative forms across lines: "(LONGER," then "LONGEST)"
        m_open = re.match(r"^\(([A-Za-z][A-Za-z0-9\-]*)\s*,\s*$", line)
        if m_open:
            inflections.append(m_open.group(1).lower())
            continue
        m_close = re.match(r"^([A-Za-z][A-Za-z0-9\-]*)\)\s*$", line)
        if m_close:
            inflections.append(m_close.group(1).lower())
            continue
        clean = line.rstrip(",").strip()
        if re.fullmatch(
            r"[A-Za-z][A-Za-z0-9\-]*(?:\s+[A-Za-z][A-Za-z0-9\-]*)*",
            clean,
        ):
            inflections.append(clean.lower())
            continue
        if "," in line and re.match(r"^[A-Za-z]", line):
            for part in line.split(","):
                tok = part.strip(" ()")
                if tok and re.fullmatch(r"[A-Za-z][A-Za-z0-9\- ]*", tok):
                    inflections.append(tok.lower())
            continue
        notes.append(f"skipped word-col line: {line!r}")

    head_l = word.lower()
    inflections = [i for i in inflections if i != head_l]
    seen: set[str] = set()
    uniq: list[str] = []
    for i in inflections:
        if i not in seen:
            seen.add(i)
            uniq.append(i)
    return word, pos, uniq, notes


def _extract_meaning(meaning_lines: list[str], *, approved: bool) -> str | None:
    if not approved:
        return None
    parts: list[str] = []
    for line in meaning_lines:
        s = line.strip()
        if not s:
            continue
        if _HELP_NOISE_RE.match(s):
            break
        # Stop at alternative tokens that are ALL CAPS with POS (other meanings)
        if re.match(
            r"^[A-Z][A-Z\- ]+\s*\((?:n|v|adj|adv|prep|conj|art|pron|TN|TV)\)",
            s,
        ):
            break
        if re.match(r"^[A-Z][A-Z\- ]{2,}$", s) and len(s.split()) <= 4:
            # Likely an alternative phrase starting
            if parts:
                break
        parts.append(s)
    text = _join_lines(parts)
    text = _NUMBERED_MEANING_RE.sub("", text)
    text = re.sub(r"\s+", " ", text).strip(" :;-")
    return text or None


def _raw_entry_to_record(raw: _RawEntry) -> tuple[DictionaryRecord | None, str | None]:
    word, pos, inflections, parse_notes = _parse_head_and_inflections(raw.word_lines)
    if not word or not pos:
        note = "; ".join(parse_notes) or "failed to parse headword"
        return None, f"page {raw.page}: {note}"

    # Reject bogus POS
    if pos not in _POS_MAP.values() and pos not in {"technical_noun", "technical_verb"}:
        return None, f"page {raw.page}: {word!r} odd pos {pos!r}"

    approved = _is_approved_surface(word)
    status = WordStatus.APPROVED if approved else WordStatus.UNAPPROVED
    meaning = _extract_meaning(raw.meaning_lines, approved=approved)
    ste = _split_examples(_join_lines(raw.ste_lines))
    nonste = _split_examples(_join_lines(raw.nonste_lines))
    alternatives = _extract_alternatives(
        raw.meaning_lines,
        approved=approved,
        ste_lines=raw.ste_lines,
        nonste_lines=raw.nonste_lines,
        headword=word,
    )

    # Unapproved entries should have alternatives or examples; else flag.
    ambiguous = None
    if parse_notes:
        ambiguous = f"{word}: " + "; ".join(parse_notes)
    if not approved and not alternatives and not ste:
        ambiguous = (ambiguous + "; " if ambiguous else f"{word}: ") + (
            "unapproved entry missing alternatives/examples"
        )

    notes_bits = []
    help_text = _join_lines(
        ln for ln in raw.meaning_lines if _HELP_NOISE_RE.match(ln.strip())
    )
    if help_text:
        notes_bits.append(help_text[:240])

    record = DictionaryRecord(
        word=word.lower(),
        part_of_speech=pos,
        status=status,
        approved_meaning=meaning,
        inflections=inflections,
        alternatives=[a for a in alternatives if a != word.lower()],
        category=None,
        rule_ref="Rule 1.1",
        examples_ste=ste,
        examples_non_ste=nonste if (not approved or nonste) else [],
        notes="; ".join(notes_bits) if notes_bits else None,
    )
    return record, ambiguous


def _collect_page_entries(
    pdf_path: Path,
    page_no: int,
) -> list[_RawEntry]:
    lines = extract_mod.extract_page_lines(pdf_path, page_no)
    if not lines:
        return []
    bands = _detect_columns(lines)
    usable = [
        ln
        for ln in lines
        if not _is_header_footer(ln["text"], ln["y"])
    ]

    # Build per-column streams sorted by y
    annotated: list[tuple[float, str, str]] = []
    for ln in usable:
        col = _assign_col(ln["x"], bands)
        annotated.append((ln["y"], col, ln["text"]))

    # Identify headword starts in word column
    head_indices: list[int] = []
    word_items = [(y, t) for y, col, t in annotated if col == "word"]
    i = 0
    while i < len(word_items):
        y, t = word_items[i]
        t_strip = t.strip()
        if _HEAD_RE.match(t_strip.rstrip(",")):
            head_indices.append(i)
        elif (
            i + 1 < len(word_items)
            and re.match(r"^[A-Za-z][A-Za-z0-9\- ]*$", t_strip)
            and _POS_ONLY_RE.match(word_items[i + 1][1].strip())
        ):
            # Multi-line headword + POS
            head_indices.append(i)
        i += 1

    entries: list[_RawEntry] = []
    for hi, start in enumerate(head_indices):
        end = head_indices[hi + 1] if hi + 1 < len(head_indices) else len(word_items)
        y0 = word_items[start][0]
        y1 = word_items[end][0] if end < len(word_items) else 1e9
        # Slight overlap tolerance
        y_lo = y0 - 3.0
        y_hi = y1 - 3.0

        word_lines = [word_items[j][1] for j in range(start, end)]
        meaning_lines = [
            t for y, col, t in annotated if col == "meaning" and y_lo <= y < y_hi
        ]
        ste_lines = [
            t for y, col, t in annotated if col == "ste" and y_lo <= y < y_hi
        ]
        nonste_lines = [
            t for y, col, t in annotated if col == "nonste" and y_lo <= y < y_hi
        ]
        entries.append(
            _RawEntry(
                page=page_no,
                head_y=y0,
                word_lines=word_lines,
                meaning_lines=meaning_lines,
                ste_lines=ste_lines,
                nonste_lines=nonste_lines,
            )
        )
    return entries


def parse_dictionary_from_pdf(
    pdf_path: Path,
    *,
    start_page: int,
    end_page: int,
) -> tuple[list[DictionaryRecord], list[str]]:
    """Parse alphabetical dictionary pages into DictionaryRecord list."""
    records: list[DictionaryRecord] = []
    ambiguous: list[str] = []
    seen_keys: set[tuple[str, str]] = set()

    for page_no in range(start_page, end_page + 1):
        for raw in _collect_page_entries(pdf_path, page_no):
            rec, amb = _raw_entry_to_record(raw)
            if amb:
                ambiguous.append(amb)
            if rec is None:
                continue
            key = (rec.word, rec.part_of_speech)
            if key in seen_keys:
                # Merge alternatives / examples into existing
                for existing in records:
                    if (existing.word, existing.part_of_speech) == key:
                        for a in rec.alternatives:
                            if a not in existing.alternatives:
                                existing.alternatives.append(a)
                        for ex in rec.examples_ste:
                            if ex and ex not in existing.examples_ste:
                                existing.examples_ste.append(ex)
                        for ex in rec.examples_non_ste:
                            if ex and ex not in existing.examples_non_ste:
                                existing.examples_non_ste.append(ex)
                        if (
                            not existing.approved_meaning
                            and rec.approved_meaning
                        ):
                            existing.approved_meaning = rec.approved_meaning
                        for inf in rec.inflections:
                            if inf not in existing.inflections:
                                existing.inflections.append(inf)
                        break
                continue
            seen_keys.add(key)
            records.append(rec)

    records.sort(key=lambda r: (r.word, r.part_of_speech))
    return records, ambiguous


def _auto_resolve_ambiguous(
    records: list[DictionaryRecord],
    ambiguous: list[str],
) -> list[str]:
    """Drop clear false-positive ambiguous notes; keep true edge cases."""
    known = {(r.word, r.part_of_speech) for r in records}
    kept: list[str] = []
    for note in ambiguous:
        # Skip "skipped word-col line" noise when record exists
        m = re.match(r"^([a-z0-9\- ]+): skipped word-col", note, re.I)
        if m and any(w == m.group(1).lower() for w, _p in known):
            continue
        # Keep unparsed heads and missing-alternative cases
        if "unparsed head" in note or "missing alternatives" in note or "odd pos" in note:
            kept.append(note)
            continue
        if "failed to parse" in note or "empty word column" in note:
            kept.append(note)
            continue
        # Drop soft "skipped word-col" alone
        if "skipped word-col line" in note:
            continue
        kept.append(note)
    return kept


def _write_ambiguous_md(path: Path, items: list[str]) -> None:
    body = [
        "# Ambiguous cases for human review",
        "",
        "Edge cases left after automated curation of ASD-STE100 Issue 9.",
        "Items below could not be resolved with high confidence from PDF layout.",
        "",
        "> Unofficial project. Not affiliated with, endorsed by, or sponsored by ASD.",
        "> ASD-STE100 is a registered European Union Trade Mark (No. 017966390).",
        "",
    ]
    if not items:
        body.append("_No unresolved ambiguous items._")
        body.append("")
    else:
        body.append(f"Count: {len(items)}")
        body.append("")
        for i, item in enumerate(items, 1):
            body.append(f"{i}. {item}")
        body.append("")
    path.write_text("\n".join(body), encoding="utf-8")


def curate(
    pdf_path: str | Path | None = None,
    *,
    data_dir: str | Path | None = None,
    raw_dir: str | Path | None = None,
    run_extract: bool = True,
) -> dict[str, Any]:
    """Run the full curation pipeline and write JSON + ambiguous.md."""
    pdf = Path(pdf_path) if pdf_path else _DEFAULT_PDF
    data = Path(data_dir) if data_dir else _DATA_DIR
    data.mkdir(parents=True, exist_ok=True)
    raw = Path(raw_dir) if raw_dir else data / "raw"

    if run_extract:
        extract_mod.dump_sections(pdf, raw)

    ranges = extract_mod.probe_section_ranges(pdf)
    alpha_start, alpha_end = ranges.get("dictionary_alpha", (149, 434))
    rules_start, rules_end = ranges.get("writing_rules", (43, 128))

    records, ambiguous = parse_dictionary_from_pdf(
        pdf, start_page=alpha_start, end_page=alpha_end
    )
    ambiguous = _auto_resolve_ambiguous(records, ambiguous)

    # Rules from writing_rules dump or live extract
    rules_path = raw / "writing_rules.txt"
    if rules_path.is_file():
        rules_text = rules_path.read_text(encoding="utf-8")
    else:
        pages = extract_mod.extract_raw_pages(pdf)
        rules_text = "\n".join(
            f"----- PAGE {p['page']} -----\n{p['text']}"
            for p in pages
            if rules_start <= p["page"] <= rules_end
        )
    rules = parse_rules_from_text(rules_text)

    dict_payload = {
        "issue": "9",
        "words": [r.model_dump(mode="json") for r in records],
    }
    rules_payload = {
        "issue": "9",
        "rules": [r.model_dump(mode="json") for r in rules],
    }

    dict_file = data / "dictionary.json"
    rules_file = data / "rules.json"
    amb_file = data / "ambiguous.md"
    dict_file.write_text(
        json.dumps(dict_payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    rules_file.write_text(
        json.dumps(rules_payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    _write_ambiguous_md(amb_file, ambiguous)

    return {
        "dictionary_path": str(dict_file),
        "rules_path": str(rules_file),
        "ambiguous_path": str(amb_file),
        "word_count": len(records),
        "rule_count": len(rules),
        "ambiguous_count": len(ambiguous),
        "approved": sum(1 for r in records if r.status == WordStatus.APPROVED),
        "unapproved": sum(1 for r in records if r.status == WordStatus.UNAPPROVED),
    }


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m ste100.dictionary.curate",
        description="Curate dictionary.json + rules.json from ASD-STE100 PDF",
    )
    p.add_argument(
        "--pdf",
        default=str(_DEFAULT_PDF),
        help="Path to ASD-STE100-ISSUE-9.pdf",
    )
    p.add_argument(
        "--data-dir",
        default=str(_DATA_DIR),
        help="Output directory for dictionary.json / rules.json / ambiguous.md",
    )
    p.add_argument(
        "--raw-dir",
        default=None,
        help="Raw extract directory (default: <data-dir>/raw)",
    )
    p.add_argument(
        "--skip-extract",
        action="store_true",
        help="Do not re-run PDF extraction (use existing raw dumps)",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    stats = curate(
        args.pdf,
        data_dir=args.data_dir,
        raw_dir=args.raw_dir,
        run_extract=not args.skip_extract,
    )
    print(
        f"Curated {stats['word_count']} words "
        f"({stats['approved']} approved, {stats['unapproved']} unapproved), "
        f"{stats['rule_count']} rules, "
        f"{stats['ambiguous_count']} ambiguous",
        file=sys.stderr,
    )
    print(f"  dictionary: {stats['dictionary_path']}", file=sys.stderr)
    print(f"  rules:      {stats['rules_path']}", file=sys.stderr)
    print(f"  ambiguous:  {stats['ambiguous_path']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

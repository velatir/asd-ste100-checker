"""Extractor smoke tests and curated dictionary load validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from ste100.core.schema import DictionaryRecord
from ste100.dictionary.engine import DictionaryEngine
from ste100.dictionary.extract import extract_raw_pages, extract_sections

ROOT = Path(__file__).resolve().parents[1]
PDF_PATH = ROOT / "ASD-STE100-ISSUE-9.pdf"
DICTIONARY_PATH = ROOT / "ste100" / "dictionary" / "data" / "dictionary.json"

pytestmark_pdf = pytest.mark.skipif(
    not PDF_PATH.is_file(),
    reason="ASD-STE100-ISSUE-9.pdf not present (CI runs offline without PDF)",
)


@pytestmark_pdf
def test_extract_raw_pages_smoke() -> None:
    pages = extract_raw_pages(PDF_PATH)
    assert len(pages) > 100
    assert pages[0]["page"] == 1
    assert isinstance(pages[0]["text"], str)
    assert any(p["text"].strip() for p in pages[:20])


@pytestmark_pdf
def test_extract_sections_smoke() -> None:
    sections = extract_sections(PDF_PATH)
    assert "writing_rules" in sections
    assert "dictionary" in sections
    assert len(sections["writing_rules"]) > 1000
    assert len(sections["dictionary"]) > 1000


def test_curated_dictionary_loads_as_records() -> None:
    assert DICTIONARY_PATH.is_file()
    engine = DictionaryEngine().load(dictionary_path=DICTIONARY_PATH)
    assert len(engine.records) > 1000
    assert all(isinstance(r, DictionaryRecord) for r in engine.records[:50])
    # Seed technical nouns may push count above curated words alone
    assert engine.lookup("the") is not None
    assert engine.lookup("utilize") is not None

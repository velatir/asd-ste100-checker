"""Dictionary quality regressions for v0.4 curation + seeds."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ste100.core.analyzer import analyze
from ste100.core.schema import WordStatus
from ste100.dictionary.engine import DictionaryEngine

_DATA = Path(__file__).resolve().parents[1] / "ste100" / "dictionary" / "data"
_DICT = _DATA / "dictionary.json"


@pytest.fixture(scope="module")
def words() -> list[dict]:
    raw = json.loads(_DICT.read_text(encoding="utf-8"))
    return list(raw["words"])


@pytest.fixture(scope="module")
def engine() -> DictionaryEngine:
    return DictionaryEngine().load()


def test_word_count_bands(words: list[dict]) -> None:
    """Curated counts stay near official Issue 9 bands (~875 / ~1274)."""
    approved = sum(1 for w in words if w["status"] == "approved")
    unapproved = sum(1 for w in words if w["status"] == "unapproved")
    total = len(words)
    assert 800 <= approved <= 950
    assert 1200 <= unapproved <= 1400
    assert 2000 <= total <= 2400


def test_known_headwords(words: list[dict], engine: DictionaryEngine) -> None:
    by_word = {w["word"]: w for w in words}
    assert by_word["utilize"]["status"] == "unapproved"
    assert "use" in by_word["utilize"]["alternatives"]

    for closed in ("the", "a", "to"):
        rec = engine.lookup(closed)
        assert rec is not None
        assert rec.status == WordStatus.APPROVED

    valve = engine.lookup("valve")
    assert valve is not None
    assert valve.status in {
        WordStatus.APPROVED,
        WordStatus.TECHNICAL_NOUN,
    }


def test_close_the_valve_compliant() -> None:
    result = analyze("Close the valve.")
    assert result.compliant is True
    assert not [
        f for f in result.findings if f.severity.value == "error"
    ]


def test_procedure_with_seed_nouns_compliant() -> None:
    text = "1. Remove the four bolts.\n2. Put the switch to ON."
    result = analyze(text, text_type="procedure")
    errors = [f for f in result.findings if f.severity.value == "error"]
    assert result.compliant is True
    assert errors == []


def test_seed_technical_verb_calibrate(engine: DictionaryEngine) -> None:
    # May already be approved in alpha dict; must resolve as allowed.
    rec = engine.lookup("calibrate")
    assert rec is not None
    assert rec.status in {
        WordStatus.APPROVED,
        WordStatus.TECHNICAL_VERB,
    }


def test_unapproved_without_alternatives_bounded(words: list[dict]) -> None:
    """Alt mining keeps empty-alternative unapproved entries in check."""
    empty = [
        w
        for w in words
        if w["status"] == "unapproved" and not w.get("alternatives")
    ]
    assert len(empty) < 80

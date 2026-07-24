"""Sentence length and one-instruction rule tests."""

from __future__ import annotations

from ste100.core.analyzer import get_nlp
from ste100.core.schema import TextType
from ste100.dictionary.engine import DictionaryEngine
from ste100.rules.context import AnalysisContext
from ste100.rules.sentence import (
    DESCRIPTION_MAX_WORDS,
    PROCEDURE_MAX_WORDS,
    RULE_LENGTH,
    RULE_ONE_INSTRUCTION,
    check_one_instruction,
    check_sentence_length,
)


def _ctx(text: str, text_type: TextType, engine: DictionaryEngine) -> AnalysisContext:
    return AnalysisContext(text=text, text_type=text_type, dictionary=engine)


def test_procedure_length_limit(dictionary_engine: DictionaryEngine) -> None:
    # 21+ words procedural sentence
    text = (
        "Remove the cover and then carefully inspect each of the internal "
        "components for any signs of damage before you continue with work."
    )
    nlp = get_nlp()
    doc = nlp(text)
    words = sum(1 for t in list(doc.sents)[0] if not t.is_space and not t.is_punct)
    assert words > PROCEDURE_MAX_WORDS
    findings = check_sentence_length(
        doc, _ctx(text, TextType.PROCEDURE, dictionary_engine)
    )
    assert any(f.rule_id == RULE_LENGTH for f in findings)
    assert findings[0].evidence["limit"] == PROCEDURE_MAX_WORDS


def test_description_length_limit(dictionary_engine: DictionaryEngine) -> None:
    text = (
        "The system gives a clear indication of the pressure value when the "
        "operator starts the secondary pump during the daily check sequence "
        "on the ground and also records the result in the log."
    )
    nlp = get_nlp()
    doc = nlp(text)
    words = sum(1 for t in list(doc.sents)[0] if not t.is_space and not t.is_punct)
    assert words > DESCRIPTION_MAX_WORDS
    findings = check_sentence_length(
        doc, _ctx(text, TextType.DESCRIPTION, dictionary_engine)
    )
    assert any(f.rule_id == RULE_LENGTH for f in findings)
    assert findings[0].evidence["limit"] == DESCRIPTION_MAX_WORDS


def test_short_sentence_ok(dictionary_engine: DictionaryEngine) -> None:
    text = "Close the valve."
    nlp = get_nlp()
    doc = nlp(text)
    findings = check_sentence_length(
        doc, _ctx(text, TextType.PROCEDURE, dictionary_engine)
    )
    assert findings == []


def test_one_instruction_flags_coordinated_imperatives(
    dictionary_engine: DictionaryEngine,
) -> None:
    text = "Remove the cover and clean the surface."
    nlp = get_nlp()
    doc = nlp(text)
    findings = check_one_instruction(
        doc, _ctx(text, TextType.PROCEDURE, dictionary_engine)
    )
    assert any(f.rule_id == RULE_ONE_INSTRUCTION for f in findings)


def test_one_instruction_skipped_for_description(
    dictionary_engine: DictionaryEngine,
) -> None:
    text = "Remove the cover and clean the surface."
    nlp = get_nlp()
    doc = nlp(text)
    findings = check_one_instruction(
        doc, _ctx(text, TextType.DESCRIPTION, dictionary_engine)
    )
    assert findings == []


def test_single_instruction_ok(dictionary_engine: DictionaryEngine) -> None:
    text = "Remove the cover."
    nlp = get_nlp()
    doc = nlp(text)
    findings = check_one_instruction(
        doc, _ctx(text, TextType.PROCEDURE, dictionary_engine)
    )
    assert findings == []

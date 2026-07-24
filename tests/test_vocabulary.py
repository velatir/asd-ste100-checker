"""Vocabulary rule and dictionary lookup tests."""

from __future__ import annotations

from ste100.core.analyzer import get_nlp
from ste100.core.schema import TextType, WordStatus
from ste100.dictionary.engine import DictionaryEngine
from ste100.rules.context import AnalysisContext
from ste100.rules.vocabulary import RULE_UNAPPROVED, check_vocabulary


def test_unapproved_utilize_lookup(dictionary_engine: DictionaryEngine) -> None:
    record = dictionary_engine.lookup("utilize")
    assert record is not None
    assert record.status is WordStatus.UNAPPROVED
    assert dictionary_engine.suggest_alternatives("utilize") == ["use"]


def test_unapproved_commence_lookup(dictionary_engine: DictionaryEngine) -> None:
    record = dictionary_engine.lookup("commence")
    assert record is not None
    assert record.status is WordStatus.UNAPPROVED
    assert "start" in dictionary_engine.suggest_alternatives("commence")


def test_forbidden_or_unapproved_flagged() -> None:
    engine = DictionaryEngine().load()
    nlp = get_nlp()
    doc = nlp("Utilize the tool.")
    ctx = AnalysisContext(text=doc.text, text_type=TextType.DESCRIPTION, dictionary=engine)
    findings = check_vocabulary(doc, ctx)
    assert any(f.rule_id == RULE_UNAPPROVED for f in findings)
    assert any("Utilize" in f.message or "utilize" in f.message.lower() for f in findings)


def test_approved_words_not_flagged(dictionary_engine: DictionaryEngine) -> None:
    nlp = get_nlp()
    text = "Close the valve."
    doc = nlp(text)
    ctx = AnalysisContext(
        text=text, text_type=TextType.PROCEDURE, dictionary=dictionary_engine
    )
    findings = check_vocabulary(doc, ctx)
    assert findings == []


def test_closed_class_words_approved(dictionary_engine: DictionaryEngine) -> None:
    for word in ("the", "a", "to", "of", "and", "or", "is", "be", "do"):
        record = dictionary_engine.lookup(word)
        assert record is not None, f"{word} missing from dictionary"
        assert record.status is WordStatus.APPROVED, f"{word} not approved"


def test_glossary_merge_technical_noun(tmp_glossary) -> None:
    engine = DictionaryEngine().load()
    engine.merge_glossary(tmp_glossary)
    widget = engine.lookup("widget")
    assert widget is not None
    assert widget.status is WordStatus.TECHNICAL_NOUN
    assert engine.is_approved("widget")


def test_glossary_preferred_term_flagged(tmp_glossary) -> None:
    engine = DictionaryEngine().load()
    engine.merge_glossary(tmp_glossary)
    nlp = get_nlp()
    doc = nlp("Please utilise the tool.")
    ctx = AnalysisContext(
        text=doc.text, text_type=TextType.DESCRIPTION, dictionary=engine
    )
    findings = check_vocabulary(doc, ctx)
    assert any(f.rule_id == RULE_UNAPPROVED for f in findings)
    assert any(
        (f.evidence or {}).get("preferred_term") == "use" for f in findings
    )


def test_seeded_technical_noun_valve(dictionary_engine: DictionaryEngine) -> None:
    record = dictionary_engine.lookup("valve")
    assert record is not None
    assert record.status is WordStatus.TECHNICAL_NOUN

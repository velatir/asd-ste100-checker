"""Tests for semicolon, contraction, nominalization rules and compliance score."""

from __future__ import annotations

from ste100.core.analyzer import _compliance_score, analyze, get_nlp
from ste100.core.schema import Finding, Severity, TextType
from ste100.dictionary.engine import DictionaryEngine
from ste100.rules.context import AnalysisContext
from ste100.rules.nominalization import RULE_NOMINALIZATION, check_nominalizations
from ste100.rules.sentence import (
    RULE_CONTRACTION,
    RULE_SEMICOLON,
    check_contractions,
    check_semicolons,
)


def _ctx(text: str, text_type: TextType, engine: DictionaryEngine) -> AnalysisContext:
    return AnalysisContext(text=text, text_type=text_type, dictionary=engine)


# ── Semicolons ──


def test_semicolon_detected(dictionary_engine: DictionaryEngine) -> None:
    text = "Open the valve; close the drain."
    nlp = get_nlp()
    doc = nlp(text)
    findings = check_semicolons(doc, _ctx(text, TextType.PROCEDURE, dictionary_engine))
    assert len(findings) == 1
    assert findings[0].rule_id == RULE_SEMICOLON
    assert findings[0].severity == Severity.ERROR


def test_no_semicolon_in_clean_text(dictionary_engine: DictionaryEngine) -> None:
    text = "Open the valve. Close the drain."
    nlp = get_nlp()
    doc = nlp(text)
    findings = check_semicolons(doc, _ctx(text, TextType.PROCEDURE, dictionary_engine))
    assert findings == []


def test_multiple_semicolons(dictionary_engine: DictionaryEngine) -> None:
    text = "Step one; step two; step three."
    nlp = get_nlp()
    doc = nlp(text)
    findings = check_semicolons(doc, _ctx(text, TextType.PROCEDURE, dictionary_engine))
    assert len(findings) == 2


# ── Contractions ──


def test_contraction_detected(dictionary_engine: DictionaryEngine) -> None:
    text = "Don't open the valve."
    nlp = get_nlp()
    doc = nlp(text)
    findings = check_contractions(doc, _ctx(text, TextType.PROCEDURE, dictionary_engine))
    assert len(findings) == 1
    assert findings[0].rule_id == RULE_CONTRACTION
    assert findings[0].suggestions[0].replacement == "Do not"


def test_no_contraction_clean(dictionary_engine: DictionaryEngine) -> None:
    text = "Do not open the valve."
    nlp = get_nlp()
    doc = nlp(text)
    findings = check_contractions(doc, _ctx(text, TextType.PROCEDURE, dictionary_engine))
    assert findings == []


def test_contraction_lowercase(dictionary_engine: DictionaryEngine) -> None:
    text = "The valve isn't open."
    nlp = get_nlp()
    doc = nlp(text)
    findings = check_contractions(doc, _ctx(text, TextType.DESCRIPTION, dictionary_engine))
    assert len(findings) == 1
    assert findings[0].suggestions[0].replacement == "is not"


# ── Nominalizations ──


def test_nominalization_detected(dictionary_engine: DictionaryEngine) -> None:
    text = "Perform an analysis of the data."
    nlp = get_nlp()
    doc = nlp(text)
    findings = check_nominalizations(doc, _ctx(text, TextType.DESCRIPTION, dictionary_engine))
    assert any(f.rule_id == RULE_NOMINALIZATION for f in findings)
    nom_finding = [f for f in findings if f.rule_id == RULE_NOMINALIZATION][0]
    assert nom_finding.evidence["preferred_verb"] == "analyze"


def test_nominalization_without_light_verb(dictionary_engine: DictionaryEngine) -> None:
    text = "The analysis showed errors."
    nlp = get_nlp()
    doc = nlp(text)
    findings = check_nominalizations(doc, _ctx(text, TextType.DESCRIPTION, dictionary_engine))
    assert not any(f.rule_id == RULE_NOMINALIZATION for f in findings)


# ── Compliance score ──


def test_compliance_score_perfect() -> None:
    score = _compliance_score([], 5)
    assert score == 1.0


def test_compliance_score_with_errors() -> None:
    findings = [
        Finding(
            rule_id="STE-TEST",
            severity=Severity.ERROR,
            message="test",
            start=0,
            end=1,
        ),
    ]
    score = _compliance_score(findings, 10)
    assert score == 0.9


def test_compliance_score_floor() -> None:
    findings = [
        Finding(
            rule_id="STE-TEST",
            severity=Severity.ERROR,
            message="test",
            start=0,
            end=1,
        )
        for _ in range(20)
    ]
    score = _compliance_score(findings, 5)
    assert score == 0.0


def test_compliance_score_warnings() -> None:
    findings = [
        Finding(
            rule_id="STE-TEST",
            severity=Severity.WARNING,
            message="test",
            start=0,
            end=1,
        ),
    ]
    score = _compliance_score(findings, 10)
    assert score == 0.95


def test_score_in_analysis_result() -> None:
    result = analyze("Close the valve.")
    assert hasattr(result, "score")
    assert 0.0 <= result.score <= 1.0

"""Tier-3 semantic rule tests: pronouns, topic sentence, POS mismatch."""

from __future__ import annotations

from ste100.core.analyzer import analyze, get_nlp
from ste100.core.schema import Severity, TextType
from ste100.core.semantic_brief import (
    TIER3_RULE_IDS,
    filter_tier3_findings,
    select_findings,
    suggest_semantic_review,
)
from ste100.dictionary.engine import DictionaryEngine
from ste100.rules.context import AnalysisContext
from ste100.rules.semantic import (
    RULE_POS,
    RULE_PRONOUN,
    RULE_TOPIC,
    check_pos_mismatch,
    check_pronoun_ambiguity,
    check_topic_sentence,
)


def _ctx(text: str, text_type: TextType, engine: DictionaryEngine) -> AnalysisContext:
    return AnalysisContext(text=text, text_type=text_type, dictionary=engine)


# --- STE-PRONOUN-AMBIG ---


def test_pronoun_ambiguous_it_multiple_candidates(
    dictionary_engine: DictionaryEngine,
) -> None:
    text = "Remove the panel from the unit. It is damaged."
    nlp = get_nlp()
    doc = nlp(text)
    findings = check_pronoun_ambiguity(
        doc, _ctx(text, TextType.DESCRIPTION, dictionary_engine)
    )
    assert findings
    assert findings[0].rule_id == RULE_PRONOUN
    assert findings[0].severity is Severity.WARNING
    assert findings[0].evidence["parse_cue"] == "multiple_antecedents"
    assert len(findings[0].evidence["candidates"]) >= 2


def test_pronoun_clear_subject_antecedent_not_flagged(
    dictionary_engine: DictionaryEngine,
) -> None:
    text = "The pump supplies pressure. It also supplies fluid."
    nlp = get_nlp()
    doc = nlp(text)
    findings = check_pronoun_ambiguity(
        doc, _ctx(text, TextType.DESCRIPTION, dictionary_engine)
    )
    assert findings == []


def test_pronoun_no_prior_sentence_warning(
    dictionary_engine: DictionaryEngine,
) -> None:
    text = "It supplies pressure to the system."
    nlp = get_nlp()
    doc = nlp(text)
    findings = check_pronoun_ambiguity(
        doc, _ctx(text, TextType.PROCEDURE, dictionary_engine)
    )
    assert findings
    assert findings[0].severity is Severity.WARNING
    assert findings[0].evidence["parse_cue"] == "no_prior_sentence"


# --- STE-TOPIC-SENTENCE ---


def test_topic_weak_pronoun_opener_description(
    dictionary_engine: DictionaryEngine,
) -> None:
    text = "It supplies pressure to the system."
    nlp = get_nlp()
    doc = nlp(text)
    findings = check_topic_sentence(
        doc, _ctx(text, TextType.DESCRIPTION, dictionary_engine)
    )
    assert findings
    assert findings[0].rule_id == RULE_TOPIC
    assert findings[0].severity is Severity.WARNING
    assert "pronoun_or_demonstrative_start" in findings[0].evidence["parse_cue"]


def test_topic_skipped_for_procedure(
    dictionary_engine: DictionaryEngine,
) -> None:
    text = "It supplies pressure to the system."
    nlp = get_nlp()
    doc = nlp(text)
    findings = check_topic_sentence(
        doc, _ctx(text, TextType.PROCEDURE, dictionary_engine)
    )
    assert findings == []


def test_topic_clear_description_not_flagged(
    dictionary_engine: DictionaryEngine,
) -> None:
    text = "The pump supplies pressure to the system."
    nlp = get_nlp()
    doc = nlp(text)
    findings = check_topic_sentence(
        doc, _ctx(text, TextType.DESCRIPTION, dictionary_engine)
    )
    assert findings == []


def test_topic_coordination_opener(
    dictionary_engine: DictionaryEngine,
) -> None:
    text = "And the pump supplies pressure."
    nlp = get_nlp()
    doc = nlp(text)
    findings = check_topic_sentence(
        doc, _ctx(text, TextType.DESCRIPTION, dictionary_engine)
    )
    assert findings
    assert "pure_coordination" in findings[0].evidence["parse_cue"]


# --- STE-POS-MISMATCH ---


def test_pos_mismatch_error_noun_used_as_verb(
    dictionary_engine: DictionaryEngine,
) -> None:
    text = "Check the pressure."
    nlp = get_nlp()
    doc = nlp(text)
    findings = check_pos_mismatch(
        doc, _ctx(text, TextType.PROCEDURE, dictionary_engine)
    )
    assert findings
    assert findings[0].rule_id == RULE_POS
    assert findings[0].severity is Severity.ERROR
    assert findings[0].evidence["approved_pos"] == "noun"
    assert findings[0].evidence["observed_pos"] == "verb"
    assert findings[0].evidence["confidence"] >= 0.8


def test_pos_mismatch_approved_noun_use_ok(
    dictionary_engine: DictionaryEngine,
) -> None:
    text = "Do a check of the pressure."
    nlp = get_nlp()
    doc = nlp(text)
    findings = check_pos_mismatch(
        doc, _ctx(text, TextType.PROCEDURE, dictionary_engine)
    )
    assert findings == []


def test_pos_mismatch_approved_verb_as_verb_ok(
    dictionary_engine: DictionaryEngine,
) -> None:
    text = "Close the valve."
    nlp = get_nlp()
    doc = nlp(text)
    findings = check_pos_mismatch(
        doc, _ctx(text, TextType.PROCEDURE, dictionary_engine)
    )
    assert findings == []


def test_pos_mismatch_skips_technical_noun(
    dictionary_engine: DictionaryEngine,
) -> None:
    text = "1. Switch the unit to ON."
    nlp = get_nlp()
    doc = nlp(text)
    findings = check_pos_mismatch(
        doc, _ctx(text, TextType.PROCEDURE, dictionary_engine)
    )
    assert not any(
        f.evidence.get("word", "").lower() == "switch" for f in findings
    )


def test_pos_mismatch_adj_used_as_noun_error(
    dictionary_engine: DictionaryEngine,
) -> None:
    text = "The flush is complete."
    nlp = get_nlp()
    doc = nlp(text)
    findings = check_pos_mismatch(
        doc, _ctx(text, TextType.DESCRIPTION, dictionary_engine)
    )
    assert findings
    assert findings[0].rule_id == RULE_POS
    assert findings[0].severity is Severity.ERROR
    assert findings[0].evidence["approved_pos"] == "adjective"
    assert findings[0].evidence["observed_pos"] == "noun"


# --- Analyzer integration / compliant ---


def test_semantic_warnings_alone_keep_compliant(
    dictionary_engine: DictionaryEngine,
) -> None:
    text = "It supplies pressure to the system."
    result = analyze(text, text_type="description", dictionary=dictionary_engine)
    assert any(f.rule_id == RULE_PRONOUN for f in result.findings)
    assert any(f.rule_id == RULE_TOPIC for f in result.findings)
    assert result.compliant is True
    assert result.summary["error"] == 0


def test_pos_error_makes_non_compliant(
    dictionary_engine: DictionaryEngine,
) -> None:
    result = analyze(
        "Check the pressure.",
        text_type="procedure",
        dictionary=dictionary_engine,
    )
    assert result.compliant is False
    assert any(
        f.rule_id == RULE_POS and f.severity is Severity.ERROR
        for f in result.findings
    )


def test_clear_compliant_description(
    dictionary_engine: DictionaryEngine,
) -> None:
    text = "The pump supplies pressure to the system."
    result = analyze(text, text_type="description", dictionary=dictionary_engine)
    tier3 = [f for f in result.findings if f.rule_id in TIER3_RULE_IDS]
    assert tier3 == []
    assert result.compliant is True


# --- Semantic brief ---


def test_suggest_semantic_review_keys_and_filter() -> None:
    payload = suggest_semantic_review(
        "Remove the panel from the unit. It is damaged.",
        text_type="description",
        max_findings=20,
    )
    assert set(payload.keys()) >= {
        "findings",
        "prompt",
        "constraints",
        "text_type",
        "compliant",
        "summary",
        "max_findings",
        "findings_total",
        "findings_included",
        "analysis",
    }
    assert "STE semantic review brief" in payload["prompt"]
    assert payload["findings"]
    assert all(f["rule_id"] in TIER3_RULE_IDS for f in payload["findings"])
    # Pronoun WARNING alone should not force compliant=false
    assert payload["compliant"] is True


def test_suggest_semantic_review_pos_error_non_compliant() -> None:
    payload = suggest_semantic_review(
        "Check the pressure.",
        text_type="procedure",
    )
    assert payload["compliant"] is False
    assert any(f["rule_id"] == RULE_POS for f in payload["findings"])


def test_select_findings_tier3_only() -> None:
    from ste100.core.schema import Finding

    findings = [
        Finding(
            rule_id="STE-VOCAB-UNAPPROVED",
            severity=Severity.ERROR,
            message="v",
            start=0,
            end=1,
        ),
        Finding(
            rule_id=RULE_PRONOUN,
            severity=Severity.WARNING,
            message="p",
            start=2,
            end=3,
        ),
        Finding(
            rule_id=RULE_POS,
            severity=Severity.ERROR,
            message="pos",
            start=4,
            end=5,
        ),
    ]
    selected = select_findings(
        findings,
        max_findings=10,
        rule_filter=lambda f: f.rule_id in TIER3_RULE_IDS,
    )
    assert [f.rule_id for f in selected] == [RULE_POS, RULE_PRONOUN]
    assert len(filter_tier3_findings(findings)) == 2

"""End-to-end analyzer tests."""

from __future__ import annotations

from ste100.core.analyzer import analyze
from ste100.core.schema import Severity
from ste100.dictionary.engine import DictionaryEngine
from ste100.rules.vocabulary import RULE_UNAPPROVED


def test_analyze_non_ste_utilize_sentence(dictionary_engine: DictionaryEngine) -> None:
    text = (
        "Utilize the system and commence the procedure when the area is ready."
    )
    result = analyze(text, dictionary=dictionary_engine)
    assert result.compliant is False
    rule_ids = {f.rule_id for f in result.findings}
    assert RULE_UNAPPROVED in rule_ids
    messages = " ".join(f.message.lower() for f in result.findings)
    assert "utilize" in messages
    assert "commence" in messages


def test_analyze_close_the_valve_zero_errors(
    dictionary_engine: DictionaryEngine,
) -> None:
    result = analyze("Close the valve.", dictionary=dictionary_engine)
    errors = [f for f in result.findings if f.severity is Severity.ERROR]
    assert errors == []
    assert result.compliant is True


def test_closed_class_words_do_not_flood(
    dictionary_engine: DictionaryEngine,
) -> None:
    result = analyze(
        "Make sure the system is safe and do the procedure.",
        dictionary=dictionary_engine,
    )
    unapproved_words = [
        (f.evidence or {}).get("word", "").lower()
        for f in result.findings
        if f.rule_id == RULE_UNAPPROVED
    ]
    for closed in ("the", "a", "to", "of", "and", "or", "is", "be", "do"):
        assert closed not in unapproved_words


def test_corpus_ste_pairs_expected_rules(
    dictionary_engine: DictionaryEngine,
    corpus_pairs: list[dict],
) -> None:
    """Non-STE sides that declare expected_rule_ids should surface those rules."""
    for pair in corpus_pairs:
        non_ste = pair.get("non_ste")
        expected = pair.get("expected_rule_ids") or []
        if not non_ste or not expected:
            continue
        text_type = pair.get("text_type", "auto")
        result = analyze(non_ste, text_type=text_type, dictionary=dictionary_engine)
        found = {f.rule_id for f in result.findings}
        missing = set(expected) - found
        assert not missing, (
            f"pair {pair['id']!r}: expected {expected}, found {sorted(found)}; "
            f"text={non_ste!r}"
        )

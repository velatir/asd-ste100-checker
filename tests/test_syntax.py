"""Tier-2 syntax rule tests: passive, imperative, verb forms, noun clusters."""

from __future__ import annotations

import os

import pytest

from ste100.core.analyzer import (
    analyze,
    clear_nlp,
    get_nlp,
    get_spacy_model_name,
    set_spacy_model,
)
from ste100.core.schema import Severity, TextType
from ste100.dictionary.engine import DictionaryEngine
from ste100.rules.context import AnalysisContext
from ste100.rules.syntax import (
    RULE_IMPERATIVE,
    RULE_NOUN_CLUSTER,
    RULE_PASSIVE,
    RULE_VERB_FORM,
    check_imperative,
    check_noun_cluster,
    check_passive,
    check_verb_form,
)


def _ctx(text: str, text_type: TextType, engine: DictionaryEngine) -> AnalysisContext:
    return AnalysisContext(text=text, text_type=text_type, dictionary=engine)


# --- STE-PASSIVE ---


def test_passive_error_on_numbered_procedural_step(
    dictionary_engine: DictionaryEngine,
) -> None:
    text = "1. The valve is closed by the operator."
    nlp = get_nlp()
    doc = nlp(text)
    findings = check_passive(doc, _ctx(text, TextType.PROCEDURE, dictionary_engine))
    assert findings
    assert findings[0].rule_id == RULE_PASSIVE
    assert findings[0].severity is Severity.ERROR
    assert findings[0].evidence["confidence"] >= 0.8
    assert "auxpass" in findings[0].evidence["parse_cue"]


def test_passive_skipped_for_description(
    dictionary_engine: DictionaryEngine,
) -> None:
    text = "The valve is closed by the operator."
    nlp = get_nlp()
    doc = nlp(text)
    findings = check_passive(doc, _ctx(text, TextType.DESCRIPTION, dictionary_engine))
    assert findings == []


def test_adjective_participle_not_flagged_as_passive(
    dictionary_engine: DictionaryEngine,
) -> None:
    text = "1. Examine all parts of the disassembled unit for damage."
    nlp = get_nlp()
    doc = nlp(text)
    findings = check_passive(doc, _ctx(text, TextType.PROCEDURE, dictionary_engine))
    assert findings == []


def test_degree_adjective_participle_not_passive(
    dictionary_engine: DictionaryEngine,
) -> None:
    text = "1. When the unit is fully disassembled, clean all the parts."
    nlp = get_nlp()
    doc = nlp(text)
    findings = check_passive(doc, _ctx(text, TextType.PROCEDURE, dictionary_engine))
    # "fully disassembled" is Rule 3.3 adjective use — must not flag
    assert not any(f.rule_id == RULE_PASSIVE for f in findings)


def test_acomp_participle_not_passive(
    dictionary_engine: DictionaryEngine,
) -> None:
    text = "1. Make sure the damaged panel is closed."
    nlp = get_nlp()
    doc = nlp(text)
    findings = check_passive(doc, _ctx(text, TextType.PROCEDURE, dictionary_engine))
    assert findings == []


# --- STE-IMPERATIVE ---


def test_imperative_compliant_numbered_step(
    dictionary_engine: DictionaryEngine,
) -> None:
    text = "1. Close the valve."
    nlp = get_nlp()
    doc = nlp(text)
    findings = check_imperative(doc, _ctx(text, TextType.PROCEDURE, dictionary_engine))
    assert findings == []


def test_imperative_error_on_non_imperative_step(
    dictionary_engine: DictionaryEngine,
) -> None:
    text = "1. The test can be continued."
    nlp = get_nlp()
    doc = nlp(text)
    findings = check_imperative(doc, _ctx(text, TextType.PROCEDURE, dictionary_engine))
    assert findings
    assert findings[0].rule_id == RULE_IMPERATIVE
    assert findings[0].severity is Severity.ERROR


def test_imperative_skipped_for_description(
    dictionary_engine: DictionaryEngine,
) -> None:
    text = "1. The test can be continued."
    nlp = get_nlp()
    doc = nlp(text)
    findings = check_imperative(
        doc, _ctx(text, TextType.DESCRIPTION, dictionary_engine)
    )
    assert findings == []


def test_do_not_imperative_ok(dictionary_engine: DictionaryEngine) -> None:
    text = "1. Do not open the door."
    nlp = get_nlp()
    doc = nlp(text)
    findings = check_imperative(doc, _ctx(text, TextType.PROCEDURE, dictionary_engine))
    assert findings == []


# --- STE-VERB-FORM ---


def test_progressive_flagged(dictionary_engine: DictionaryEngine) -> None:
    text = "The operator is adjusting the linkage."
    nlp = get_nlp()
    doc = nlp(text)
    findings = check_verb_form(
        doc, _ctx(text, TextType.DESCRIPTION, dictionary_engine)
    )
    assert any(f.rule_id == RULE_VERB_FORM for f in findings)
    hit = next(f for f in findings if f.rule_id == RULE_VERB_FORM)
    assert hit.severity is Severity.ERROR
    assert "progressive" in hit.evidence["parse_cue"]


def test_perfect_flagged(dictionary_engine: DictionaryEngine) -> None:
    text = "The operator has closed the valve."
    nlp = get_nlp()
    doc = nlp(text)
    findings = check_verb_form(
        doc, _ctx(text, TextType.DESCRIPTION, dictionary_engine)
    )
    assert any(f.rule_id == RULE_VERB_FORM for f in findings)
    hit = next(f for f in findings if f.rule_id == RULE_VERB_FORM)
    assert "perfect" in hit.evidence["parse_cue"]


def test_modal_passive_flagged(dictionary_engine: DictionaryEngine) -> None:
    text = "The temperature must be adjusted."
    nlp = get_nlp()
    doc = nlp(text)
    findings = check_verb_form(doc, _ctx(text, TextType.PROCEDURE, dictionary_engine))
    assert any(f.rule_id == RULE_VERB_FORM for f in findings)


# --- STE-NOUN-CLUSTER ---


def test_noun_cluster_four_words_error(
    dictionary_engine: DictionaryEngine,
) -> None:
    text = "Remove the fuel pump inlet pressure sensor."
    nlp = get_nlp()
    doc = nlp(text)
    findings = check_noun_cluster(
        doc, _ctx(text, TextType.PROCEDURE, dictionary_engine)
    )
    assert findings
    assert findings[0].rule_id == RULE_NOUN_CLUSTER
    assert findings[0].severity is Severity.ERROR
    assert findings[0].evidence["cluster_length"] >= 4


def test_noun_cluster_three_words_ok(
    dictionary_engine: DictionaryEngine,
) -> None:
    text = "Remove the fuel pump pressure."
    nlp = get_nlp()
    doc = nlp(text)
    findings = check_noun_cluster(
        doc, _ctx(text, TextType.PROCEDURE, dictionary_engine)
    )
    assert findings == []


# --- Analyzer integration / model config ---


def test_analyze_passive_procedural_sentence(
    dictionary_engine: DictionaryEngine,
) -> None:
    result = analyze(
        "1. The valve is closed by the operator.",
        text_type="procedure",
        dictionary=dictionary_engine,
    )
    ids = {f.rule_id for f in result.findings}
    assert RULE_PASSIVE in ids


def test_analyze_imperative_compliant_step(
    dictionary_engine: DictionaryEngine,
) -> None:
    result = analyze(
        "1. Close the valve.",
        text_type="procedure",
        dictionary=dictionary_engine,
    )
    assert not any(f.rule_id == RULE_IMPERATIVE for f in result.findings)
    # May still have vocab noise depending on dictionary; imperative itself clean
    imperative_hits = [f for f in result.findings if f.rule_id == RULE_IMPERATIVE]
    assert imperative_hits == []


def test_spacy_model_env_and_override(monkeypatch: pytest.MonkeyPatch) -> None:
    clear_nlp()
    set_spacy_model(None)
    monkeypatch.delenv("STE100_SPACY_MODEL", raising=False)
    assert get_spacy_model_name() == "en_core_web_sm"

    monkeypatch.setenv("STE100_SPACY_MODEL", "en_core_web_sm")
    clear_nlp()
    assert get_spacy_model_name() == "en_core_web_sm"
    nlp = get_nlp()
    assert nlp is not None

    set_spacy_model("en_core_web_sm")
    assert get_spacy_model_name() == "en_core_web_sm"
    set_spacy_model(None)
    monkeypatch.delenv("STE100_SPACY_MODEL", raising=False)
    clear_nlp()


def test_cli_spacy_model_flag() -> None:
    from click.testing import CliRunner

    from ste100.cli import main

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["check", "--spacy-model", "en_core_web_sm", "--text-type", "procedure"],
        input="1. Close the valve.\n",
    )
    assert result.exit_code == 0
    # Reset override so other tests are unaffected
    set_spacy_model(None)
    clear_nlp()
    os.environ.pop("STE100_SPACY_MODEL", None)

"""Structural / units formatting rule tests."""

from __future__ import annotations

from ste100.core.analyzer import get_nlp
from ste100.core.schema import Severity, TextType
from ste100.dictionary.engine import DictionaryEngine
from ste100.rules.context import AnalysisContext
from ste100.rules.structural import RULE_UNITS, check_units_format


def test_glued_unit_info_finding(dictionary_engine: DictionaryEngine) -> None:
    text = "Set the clearance to 10mm."
    nlp = get_nlp()
    doc = nlp(text)
    ctx = AnalysisContext(
        text=text, text_type=TextType.DESCRIPTION, dictionary=dictionary_engine
    )
    findings = check_units_format(doc, ctx)
    assert len(findings) >= 1
    finding = findings[0]
    assert finding.rule_id == RULE_UNITS
    assert finding.severity is Severity.INFO
    assert "10 mm" in finding.message


def test_spaced_unit_not_flagged(dictionary_engine: DictionaryEngine) -> None:
    text = "Set the clearance to 10 mm."
    nlp = get_nlp()
    doc = nlp(text)
    ctx = AnalysisContext(
        text=text, text_type=TextType.DESCRIPTION, dictionary=dictionary_engine
    )
    findings = [
        f for f in check_units_format(doc, ctx) if "10 mm" in (f.evidence or {}).get("preferred", "")
        or "10mm" in (f.evidence or {}).get("found", "")
    ]
    assert findings == []

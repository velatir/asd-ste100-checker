"""Safe 1:1 synonym fix tests."""

from __future__ import annotations

from ste100.core.fixes import apply_safe_fixes
from ste100.dictionary.engine import DictionaryEngine


def test_utilize_to_use_applied(dictionary_engine: DictionaryEngine) -> None:
    result = apply_safe_fixes("Utilize the tool.", dictionary=dictionary_engine)
    assert result["fixed"] == "Use the tool."
    assert any(
        r["from"].lower() == "utilize" and r["to"].lower() == "use"
        for r in result["replacements_applied"]
    )
    assert result["diff"]


def test_commence_single_alt_applied(dictionary_engine: DictionaryEngine) -> None:
    """commence has a single alternative (start) so it is a safe fix."""
    mapping = dictionary_engine.safe_replacements()
    assert mapping.get("commence") == "start"
    result = apply_safe_fixes("Commence the test.", dictionary=dictionary_engine)
    assert result["fixed"] == "Start the test."


def test_multi_alt_not_applied(dictionary_engine: DictionaryEngine) -> None:
    """Words with multiple alternatives must not be auto-replaced."""
    mapping = dictionary_engine.safe_replacements()
    assert "abandon" not in mapping
    result = apply_safe_fixes("Abandon the procedure.", dictionary=dictionary_engine)
    assert result["fixed"] == "Abandon the procedure."
    assert result["replacements_applied"] == []


def test_actuate_multi_alt_not_applied(dictionary_engine: DictionaryEngine) -> None:
    mapping = dictionary_engine.safe_replacements()
    assert "actuate" not in mapping
    result = apply_safe_fixes("Actuate the valve.", dictionary=dictionary_engine)
    assert "Actuate" in result["fixed"]

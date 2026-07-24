"""Serializer shape tests for JSON and SARIF output."""

from __future__ import annotations

from ste100.core.analyzer import analyze
from ste100.core.serialize import to_json, to_sarif
from ste100.dictionary.engine import DictionaryEngine


def test_to_json_shape(dictionary_engine: DictionaryEngine) -> None:
    result = analyze("Utilize the tool.", dictionary=dictionary_engine)
    payload = to_json(result)
    assert isinstance(payload, dict)
    assert "compliant" in payload
    assert "findings" in payload
    assert "summary" in payload
    assert "text_type" in payload
    assert isinstance(payload["findings"], list)
    if payload["findings"]:
        finding = payload["findings"][0]
        assert "rule_id" in finding
        assert "severity" in finding
        assert "message" in finding
        assert "start" in finding
        assert "end" in finding


def test_to_json_string(dictionary_engine: DictionaryEngine) -> None:
    result = analyze("Close the valve.", dictionary=dictionary_engine)
    text = to_json(result, as_string=True)
    assert isinstance(text, str)
    assert '"compliant"' in text


def test_to_sarif_shape(dictionary_engine: DictionaryEngine) -> None:
    result = analyze("Utilize the tool.", dictionary=dictionary_engine)
    sarif = to_sarif(result)
    assert sarif["version"] == "2.1.0"
    assert "$schema" in sarif
    assert len(sarif["runs"]) == 1
    run = sarif["runs"][0]
    assert "tool" in run
    assert "driver" in run["tool"]
    assert run["tool"]["driver"]["name"]
    assert "rules" in run["tool"]["driver"]
    assert "results" in run
    assert isinstance(run["results"], list)
    assert run["properties"]["compliant"] is False
    if run["results"]:
        item = run["results"][0]
        assert "ruleId" in item
        assert "level" in item
        assert "message" in item
        assert item["message"]["text"]

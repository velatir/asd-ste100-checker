"""Serializers: JSON and SARIF 2.1.0 output for AnalysisResult."""

from __future__ import annotations

import json
from typing import Any, Never

from ste100.core.schema import AnalysisResult, Finding, Severity
from ste100.rules.registry import get_rule_meta


def to_json(result: AnalysisResult, *, as_string: bool = False) -> dict[str, Any] | str:
    """Serialize AnalysisResult to a JSON-compatible dict (or JSON string)."""
    payload = result.model_dump(mode="json")
    if as_string:
        return json.dumps(payload, indent=2, ensure_ascii=False)
    return payload


def format_output(result: AnalysisResult, output: str) -> dict[str, Any]:
    """Serialize an AnalysisResult as json or sarif (dict form).

    Shared by the CLI and MCP adapters so the json/sarif dispatch lives once.
    """
    fmt = (output or "json").strip().lower()
    if fmt == "sarif":
        return to_sarif(result)
    if fmt == "json":
        return to_json(result)  # type: ignore[return-value]
    raise ValueError(f"Invalid output format {output!r}; expected 'json' or 'sarif'")


def _sarif_level(severity: Severity) -> str:
    if severity is Severity.ERROR:
        return "error"
    if severity is Severity.WARNING:
        return "warning"
    if severity is Severity.INFO:
        return "note"
    _exhaustive: Never = severity
    raise AssertionError(f"Unhandled Severity: {_exhaustive}")


def _sarif_rules() -> list[dict[str, Any]]:
    rules: list[dict[str, Any]] = []
    seen: set[str] = set()
    for meta in get_rule_meta():
        rid = meta["id"]
        if rid in seen:
            continue
        seen.add(rid)
        rules.append(
            {
                "id": rid,
                "shortDescription": {"text": meta["shortDescription"]},
                "defaultConfiguration": {"level": meta["defaultSeverity"]},
            }
        )
    return rules


def _finding_to_sarif_result(finding: Finding) -> dict[str, Any]:
    result: dict[str, Any] = {
        "ruleId": finding.rule_id,
        "level": _sarif_level(finding.severity),
        "message": {"text": finding.message},
        "locations": [
            {
                "physicalLocation": {
                    "region": {
                        "startOffset": finding.start,
                        "endOffset": finding.end,
                    }
                }
            }
        ],
    }
    if finding.evidence:
        result["properties"] = {"evidence": finding.evidence}
    return result


def to_sarif(
    result: AnalysisResult,
    tool_name: str = "asd-ste100-checker",
) -> dict[str, Any]:
    """Build a minimal SARIF 2.1.0 document for the analysis result."""
    return {
        "version": "2.1.0",
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": tool_name,
                        "informationUri": (
                            "https://github.com/search?q=asd-ste100-checker"
                        ),
                        "rules": _sarif_rules(),
                    }
                },
                "results": [_finding_to_sarif_result(f) for f in result.findings],
                "properties": {
                    "text_type": result.text_type.value,
                    "compliant": result.compliant,
                    "summary": result.summary,
                },
            }
        ],
    }

"""Serializers: JSON and SARIF 2.1.0 output for AnalysisResult."""

from __future__ import annotations

import json
from typing import Any, Never

from ste100.core.schema import AnalysisResult, Finding, Severity
from ste100.rules.registry import get_rule_meta


def _compact_severity_rank(severity: Severity) -> int:
    if severity is Severity.ERROR:
        return 0
    if severity is Severity.WARNING:
        return 1
    if severity is Severity.INFO:
        return 2
    _exhaustive: Never = severity
    raise AssertionError(f"Unhandled Severity: {_exhaustive}")


def to_json(
    result: AnalysisResult,
    *,
    as_string: bool = False,
    compact: bool = False,
    max_findings: int | None = None,
) -> dict[str, Any] | str:
    """Serialize AnalysisResult to a JSON-compatible dict (or JSON string)."""
    if compact:
        findings = sorted(
            result.findings,
            key=lambda f: (_compact_severity_rank(f.severity), f.start, f.end, f.rule_id),
        )
        if max_findings is not None and max_findings >= 0:
            findings = findings[:max_findings]
        payload: dict[str, Any] = {
            "text_type": result.text_type.value,
            "compliant": result.compliant,
            "findings": [[f.rule_id, f.severity.value] for f in findings],
            "summary": {
                k: result.summary.get(k, 0) for k in ("error", "warning", "info")
            },
        }
    else:
        payload = result.model_dump(mode="json")
    if as_string:
        return json.dumps(payload, indent=2, ensure_ascii=False)
    return payload


def format_output(
    result: AnalysisResult,
    output: str,
    *,
    verbosity: str = "full",
    max_findings: int | None = 30,
) -> dict[str, Any]:
    """Serialize an AnalysisResult as json or sarif (dict form).

    Shared by the CLI and MCP adapters so the json/sarif dispatch lives once.
    ``verbosity='compact'`` returns ``[rule_id, severity]`` finding pairs,
    errors-first, capped by ``max_findings`` (default 30).
    """
    fmt = (output or "json").strip().lower()
    compact = verbosity.strip().lower() == "compact"
    if fmt == "sarif":
        return to_sarif(result)
    if fmt == "json":
        return to_json(
            result,
            compact=compact,
            max_findings=max_findings if compact else None,
        )  # type: ignore[return-value]
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

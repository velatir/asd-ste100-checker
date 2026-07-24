"""Tests for ste_suggest_rewrite / rewrite_brief."""

from __future__ import annotations

from ste100.core.rewrite_brief import (
    DEFAULT_MAX_FINDINGS,
    select_findings,
    suggest_rewrite,
)
from ste100.core.schema import Finding, Severity


def test_suggest_rewrite_keys_and_ordering() -> None:
    payload = suggest_rewrite("Utilize the tool.", text_type="auto", max_findings=20)
    assert set(payload.keys()) >= {
        "findings",
        "prompt",
        "constraints",
        "safe_fix_preview",
        "text_type",
        "compliant",
        "summary",
        "max_findings",
        "findings_total",
        "findings_included",
        "analysis",
    }
    assert payload["compliant"] is False
    assert payload["findings"]
    assert isinstance(payload["prompt"], str)
    assert "STE rewrite brief" in payload["prompt"]
    assert "Utilize the tool." in payload["prompt"]
    assert payload["constraints"]
    assert any("compliance" in c.lower() for c in payload["constraints"])

    severities = [f["severity"] for f in payload["findings"]]
    # Errors must come before warnings/info in the capped list
    if "error" in severities and "warning" in severities:
        assert severities.index("error") < severities.index("warning")

    preview = payload["safe_fix_preview"]
    assert preview is not None
    assert preview["fixed"] == "Use the tool."
    assert preview["replacements_applied"]


def test_suggest_rewrite_respects_max_findings() -> None:
    # Build a long non-compliant string that yields multiple findings
    text = "Utilize the apparatus and commence the operation and utilize the system."
    limited = suggest_rewrite(text, max_findings=1)
    assert limited["findings_included"] == 1
    assert len(limited["findings"]) == 1
    assert limited["findings_total"] >= 1

    unlimited = suggest_rewrite(text, max_findings=DEFAULT_MAX_FINDINGS)
    assert unlimited["findings_included"] <= DEFAULT_MAX_FINDINGS


def test_select_findings_orders_by_severity() -> None:
    findings = [
        Finding(
            rule_id="W",
            severity=Severity.WARNING,
            message="w",
            start=5,
            end=6,
        ),
        Finding(
            rule_id="E",
            severity=Severity.ERROR,
            message="e",
            start=0,
            end=1,
        ),
        Finding(
            rule_id="I",
            severity=Severity.INFO,
            message="i",
            start=2,
            end=3,
        ),
    ]
    selected = select_findings(findings, max_findings=2)
    assert [f.rule_id for f in selected] == ["E", "W"]


def test_suggest_rewrite_can_omit_preview() -> None:
    payload = suggest_rewrite(
        "Close the valve.",
        include_safe_fix_preview=False,
    )
    assert payload["safe_fix_preview"] is None
    assert payload["compliant"] is True

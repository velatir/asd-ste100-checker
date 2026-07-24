"""LSP Finding → diagnostic mapping tests."""

from __future__ import annotations

from lsprotocol import types

from ste100.core.analyzer import analyze
from ste100.core.schema import Finding, Severity
from ste100.lsp.server import (
    finding_to_diagnostic,
    is_supported_document,
    offset_to_position,
    severity_to_lsp,
)


def test_offset_to_position_multiline() -> None:
    text = "abc\ndef"
    assert offset_to_position(text, 0) == types.Position(line=0, character=0)
    assert offset_to_position(text, 4) == types.Position(line=1, character=0)
    assert offset_to_position(text, 6) == types.Position(line=1, character=2)


def test_severity_mapping_exhaustive() -> None:
    assert severity_to_lsp(Severity.ERROR) is types.DiagnosticSeverity.Error
    assert severity_to_lsp(Severity.WARNING) is types.DiagnosticSeverity.Warning
    assert severity_to_lsp(Severity.INFO) is types.DiagnosticSeverity.Information


def test_finding_to_diagnostic_e04_sample() -> None:
    text = "1. The valve is closed by the operator."
    result = analyze(text, text_type="procedure")
    passive = next(f for f in result.findings if f.rule_id == "STE-PASSIVE")
    diag = finding_to_diagnostic(text, passive)
    assert diag.code == "STE-PASSIVE"
    assert diag.severity is types.DiagnosticSeverity.Error
    assert diag.range.start.line == 0
    assert diag.range.end.character >= diag.range.start.character


def test_supported_filetypes() -> None:
    assert is_supported_document("file:///tmp/a.md")
    assert is_supported_document("file:///tmp/a.txt")
    assert is_supported_document("file:///tmp/a.rst")
    assert is_supported_document("file:///tmp/a.adoc")
    assert not is_supported_document("file:///tmp/a.py")
    assert is_supported_document("untitled:1", language_id="markdown")


def test_finding_to_diagnostic_direct() -> None:
    finding = Finding(
        rule_id="STE-UNITS-FORMAT",
        severity=Severity.INFO,
        message="Prefer a space",
        start=0,
        end=4,
    )
    diag = finding_to_diagnostic("10mm", finding)
    assert diag.severity is types.DiagnosticSeverity.Information
    assert diag.range.start.character == 0
    assert diag.range.end.character == 4

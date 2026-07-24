"""Thin STE diagnostics LSP (Finding → publishDiagnostics). No code actions."""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Never
from urllib.parse import unquote, urlparse

from lsprotocol import types
from pygls.lsp.server import LanguageServer

from ste100 import __version__
from ste100.core.analyzer import analyze
from ste100.core.schema import Finding, Severity

SERVER_NAME = "asd-ste100-checker"
SUPPORTED_SUFFIXES = frozenset({".md", ".txt", ".rst", ".adoc"})


def offset_to_position(text: str, offset: int) -> types.Position:
    """Convert a UTF-8/Python string character offset to an LSP Position."""
    clamped = max(0, min(offset, len(text)))
    line = text.count("\n", 0, clamped)
    last_nl = text.rfind("\n", 0, clamped)
    character = clamped if last_nl < 0 else clamped - last_nl - 1
    return types.Position(line=line, character=character)


def severity_to_lsp(severity: Severity) -> types.DiagnosticSeverity:
    """Map STE Severity to LSP DiagnosticSeverity."""
    if severity is Severity.ERROR:
        return types.DiagnosticSeverity.Error
    if severity is Severity.WARNING:
        return types.DiagnosticSeverity.Warning
    if severity is Severity.INFO:
        return types.DiagnosticSeverity.Information
    _exhaustive: Never = severity
    raise AssertionError(f"Unhandled Severity: {_exhaustive}")


def finding_to_diagnostic(text: str, finding: Finding) -> types.Diagnostic:
    """Convert a Finding (character offsets) into an LSP Diagnostic."""
    start = offset_to_position(text, finding.start)
    end = offset_to_position(text, finding.end)
    if end.line < start.line or (
        end.line == start.line and end.character < start.character
    ):
        end = start
    return types.Diagnostic(
        range=types.Range(start=start, end=end),
        message=f"{finding.rule_id}: {finding.message}",
        severity=severity_to_lsp(finding.severity),
        source=SERVER_NAME,
        code=finding.rule_id,
    )


def _uri_path_suffix(uri: str) -> str:
    parsed = urlparse(uri)
    path = unquote(parsed.path or "")
    # Windows file URIs may look like /C:/...
    if path.startswith("/") and len(path) > 2 and path[2] == ":":
        path = path[1:]
    return PurePosixPath(path).suffix.lower()


def is_supported_document(uri: str, language_id: str | None = None) -> bool:
    """Return True for md/txt/rst/adoc by suffix or language id."""
    suffix = _uri_path_suffix(uri)
    if suffix in SUPPORTED_SUFFIXES:
        return True
    lang = (language_id or "").strip().lower()
    return lang in {
        "markdown",
        "plaintext",
        "text",
        "restructuredtext",
        "rst",
        "asciidoc",
        "adoc",
    }


def findings_to_diagnostics(text: str, findings: list[Finding]) -> list[types.Diagnostic]:
    return [finding_to_diagnostic(text, f) for f in findings]


def create_server() -> LanguageServer:
    """Build the diagnostics-only language server."""
    server = LanguageServer(SERVER_NAME, __version__)

    def _publish_for_uri(uri: str, text: str) -> None:
        try:
            result = analyze(text, text_type="auto")
            diagnostics = findings_to_diagnostics(text, result.findings)
        except Exception as exc:  # noqa: BLE001 — surface as a single diagnostic
            diagnostics = [
                types.Diagnostic(
                    range=types.Range(
                        start=types.Position(line=0, character=0),
                        end=types.Position(line=0, character=1),
                    ),
                    message=f"STE analysis failed: {exc}",
                    severity=types.DiagnosticSeverity.Error,
                    source=SERVER_NAME,
                )
            ]
        server.text_document_publish_diagnostics(
            types.PublishDiagnosticsParams(uri=uri, diagnostics=diagnostics)
        )

    @server.feature(types.TEXT_DOCUMENT_DID_OPEN)
    def did_open(_ls: LanguageServer, params: types.DidOpenTextDocumentParams) -> None:
        doc = params.text_document
        if not is_supported_document(doc.uri, doc.language_id):
            return
        _publish_for_uri(doc.uri, doc.text)

    @server.feature(types.TEXT_DOCUMENT_DID_CHANGE)
    def did_change(ls: LanguageServer, params: types.DidChangeTextDocumentParams) -> None:
        uri = params.text_document.uri
        if not is_supported_document(uri):
            return
        text_doc = ls.workspace.get_text_document(uri)
        _publish_for_uri(uri, text_doc.source)

    @server.feature(types.TEXT_DOCUMENT_DID_SAVE)
    def did_save(ls: LanguageServer, params: types.DidSaveTextDocumentParams) -> None:
        uri = params.text_document.uri
        if not is_supported_document(uri):
            return
        text_doc = ls.workspace.get_text_document(uri)
        _publish_for_uri(uri, text_doc.source)

    @server.feature(types.TEXT_DOCUMENT_DID_CLOSE)
    def did_close(_ls: LanguageServer, params: types.DidCloseTextDocumentParams) -> None:
        server.text_document_publish_diagnostics(
            types.PublishDiagnosticsParams(uri=params.text_document.uri, diagnostics=[])
        )

    return server


def run_server() -> None:
    """Run the LSP over stdio."""
    create_server().start_io()


def main() -> None:
    run_server()


if __name__ == "__main__":
    main()

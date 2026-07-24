"""FastMCP server exposing STE checker tools (stdio + HTTP/SSE)."""

from __future__ import annotations

import os
from typing import Any, Literal

from fastmcp import FastMCP
from fastmcp.server.auth.providers.jwt import StaticTokenVerifier

from ste100.core.agent_brief import suggest_rewrite, suggest_semantic_review
from ste100.core.analyzer import analyze
from ste100.core.explain import explain_rule
from ste100.core.fixes import apply_safe_fixes
from ste100.core.git_files import NotAGitRepositoryError, run_check_changed
from ste100.core.paths import resolve_optional_user_path, resolve_user_path
from ste100.core.serialize import format_output
from ste100.core.spacy_ready import ensure_spacy_model
from ste100.dictionary.engine import get_default_engine

TransportName = Literal["stdio", "http", "sse", "streamable-http"]

mcp = FastMCP(
    name="asd-ste100-checker",
    instructions=(
        "Unofficial ASD-STE100 Simplified Technical English checker. "
        "Not affiliated with ASD. Use ste_check_text / ste_check_file for diagnostics, "
        "ste_lookup_word for dictionary lookup, ste_explain_finding for rule metadata, "
        "ste_apply_safe_fixes for 1:1 synonym fixes, "
        "ste_suggest_rewrite for a host-agent rewrite brief (no LLM API), "
        "ste_suggest_semantic_review for Tier-3 semantic findings brief (no LLM API), "
        "and ste_check_changed_files for working-tree / branch-vs-base doc changes. "
        "Set STE100_SPACY_MODEL before starting the server to choose a spaCy model. "
        "Relative file/glossary paths require STE100_WORKSPACE (absolute root). "
        "HTTP/SSE requires STE100_MCP_TOKEN (Bearer)."
    ),
)


def _bearer_auth_from_env() -> StaticTokenVerifier:
    token = (os.environ.get("STE100_MCP_TOKEN") or "").strip()
    if not token:
        raise SystemExit(
            "error: STE100_MCP_TOKEN is required for HTTP/SSE transport. "
            "Set a shared bearer token before starting the server "
            "(clients send Authorization: Bearer <token>)."
        )
    return StaticTokenVerifier(
        tokens={
            token: {
                "client_id": "ste100",
                "scopes": [],
            }
        }
    )


@mcp.tool()
def ste_check_text(
    text: str,
    text_type: str = "auto",
    glossary: str | None = None,
    output: str = "json",
) -> dict[str, Any]:
    """Check technical text and return structured STE diagnostics."""
    glossary_path = resolve_optional_user_path(glossary)
    result = analyze(text, text_type=text_type, glossary_path=glossary_path)
    return format_output(result, output)


@mcp.tool()
def ste_check_file(
    path: str,
    text_type: str = "auto",
    glossary: str | None = None,
    output: str = "json",
) -> dict[str, Any]:
    """Check a file on disk and return structured STE diagnostics.

    Absolute paths are used as-is. Relative paths resolve under
    ``STE100_WORKSPACE``.
    """
    file_path = resolve_user_path(path)
    glossary_path = resolve_optional_user_path(glossary)
    text = file_path.read_text(encoding="utf-8")
    result = analyze(text, text_type=text_type, glossary_path=glossary_path)
    return format_output(result, output)


@mcp.tool()
def ste_lookup_word(word: str) -> dict[str, Any]:
    """Return status, meaning, alternatives, inflections, and rule_ref for a word."""
    return get_default_engine().lookup_payload(word)


@mcp.tool()
def ste_apply_safe_fixes(text: str, glossary: str | None = None) -> dict[str, Any]:
    """Apply only unambiguous 1:1 synonym replacements; return text + diff."""
    return apply_safe_fixes(text, glossary_path=resolve_optional_user_path(glossary))


@mcp.tool()
def ste_suggest_rewrite(
    text: str,
    text_type: str = "auto",
    glossary: str | None = None,
    max_findings: int = 20,
) -> dict[str, Any]:
    """Return a structured rewrite brief (prompt + findings) for the host agent.

    Runs analyze() internally. Does not call any LLM provider API — the host
    LLM should use ``prompt`` to rewrite, then recheck with ste_check_text.
    Includes ``safe_fix_preview`` of unambiguous 1:1 synonym fixes without
    applying them unless the host separately calls ste_apply_safe_fixes.
    """
    return suggest_rewrite(
        text,
        text_type=text_type,
        glossary=resolve_optional_user_path(glossary),
        max_findings=max_findings,
    )


@mcp.tool()
def ste_suggest_semantic_review(
    text: str,
    text_type: str = "auto",
    glossary: str | None = None,
    max_findings: int = 20,
) -> dict[str, Any]:
    """Return a Tier-3 semantic review brief (prompt + findings) for the host agent.

    Filters pronoun / topic-sentence / POS-mismatch findings. Does not call any
    LLM provider API — the host judges WARNINGs, clears POS ERRORs, then rechecks.
    Semantic WARNINGs alone do not make ``compliant`` false.
    """
    return suggest_semantic_review(
        text,
        text_type=text_type,
        glossary=resolve_optional_user_path(glossary),
        max_findings=max_findings,
    )


@mcp.tool()
def ste_check_changed_files(
    globs: list[str] | None = None,
    text_type: str = "auto",
    glossary: str | None = None,
    output: str = "json",
    base: str | None = None,
) -> dict[str, Any]:
    """Check locally changed doc files for STE issues.

    Default: working tree vs HEAD (staged + unstaged + untracked).
    With ``base`` (branch/ref): files changed vs ``git merge-base HEAD <base>``.
    Filters by globs (default: *.md, *.txt, *.rst, *.adoc). Requires a git repo.
    """
    fmt = (output or "json").strip().lower()
    try:
        return run_check_changed(
            output=fmt,
            globs=globs,
            text_type=text_type,
            glossary=resolve_optional_user_path(glossary),
            base=base,
        )
    except NotAGitRepositoryError as exc:
        return {
            "error": "not_a_git_repository",
            "message": str(exc),
            "compliant": False,
            "files": [],
            "files_checked": 0,
        }


@mcp.tool()
def ste_explain_finding(rule_id: str) -> dict[str, Any]:
    """Explain a checker rule_id (title, severity, STE ref, fix hints, PDF rule)."""
    return explain_rule(rule_id)


def create_server() -> FastMCP:
    """Return the configured FastMCP server instance."""
    return mcp


def run_server(
    transport: TransportName | str = "stdio",
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
    path: str = "/mcp",
) -> None:
    """Run the MCP server over stdio or HTTP/SSE (streamable).

    Eagerly verifies the configured spaCy model is loadable (no download).
    Stdio needs no auth. HTTP/SSE/streamable-http require ``STE100_MCP_TOKEN``
    and validate ``Authorization: Bearer …``.
    """
    ensure_spacy_model()
    kind = (transport or "stdio").strip().lower()
    if kind == "stdio":
        mcp.auth = None
        mcp.run(transport="stdio")
        return

    if kind in {"http", "sse", "streamable-http"}:
        mcp.auth = _bearer_auth_from_env()
        http_transport: Literal["http", "sse", "streamable-http"]
        if kind == "sse":
            http_transport = "sse"
        elif kind == "http":
            # Prefer modern streamable HTTP; "http" is an alias in FastMCP.
            http_transport = "streamable-http"
        else:
            http_transport = "streamable-http"
        mcp.run(
            transport=http_transport,
            host=host,
            port=port,
            path=path,
        )
        return

    raise SystemExit(
        f"error: unknown transport {transport!r}; "
        "expected stdio, http, sse, or streamable-http"
    )


def main() -> None:
    run_server()


if __name__ == "__main__":
    main()

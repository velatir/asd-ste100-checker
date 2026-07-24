"""MCP tool function tests (no stdio serve)."""

from __future__ import annotations

from pathlib import Path

from ste100.core.fixes import apply_safe_fixes
from ste100.mcp import server as mcp_server
from ste100.mcp.server import (
    create_server,
    ste_apply_safe_fixes,
    ste_check_changed_files,
    ste_check_text,
    ste_explain_finding,
    ste_lookup_word,
    ste_suggest_rewrite,
    ste_suggest_semantic_review,
)


def test_import_server_and_create() -> None:
    assert mcp_server.mcp is not None
    server = create_server()
    assert server is mcp_server.mcp


def test_ste_check_text_as_function() -> None:
    payload = ste_check_text("Utilize the tool.", text_type="auto", output="json")
    assert isinstance(payload, dict)
    assert payload["compliant"] is False
    assert payload["summary"]["error"] >= 1


def test_ste_lookup_word_as_function() -> None:
    payload = ste_lookup_word("utilize")
    assert payload["found"] is True
    assert payload["status"] == "unapproved"
    assert "use" in payload["alternatives"]


def test_ste_apply_safe_fixes_as_function() -> None:
    payload = ste_apply_safe_fixes("Utilize the tool.")
    assert payload["fixed"] == "Use the tool."
    assert payload["replacements_applied"]


def test_underlying_fixes_path() -> None:
    # Prefer core.fixes for hang-free coverage of the MCP tool body
    result = apply_safe_fixes("Utilize the system.")
    assert "Use" in result["fixed"]


def test_ste_explain_finding() -> None:
    payload = ste_explain_finding("STE-PASSIVE")
    assert payload["found"] is True
    assert payload["rule_id"] == "STE-PASSIVE"
    assert payload["rule_ref"] == "Rule 3.6"
    assert payload["default_severity"] == "error"
    assert payload["text_type_scope"] == "procedure"
    assert payload["fix_hints"]
    assert payload["pdf_rule"] is not None
    assert payload["pdf_rule"]["rule_id"] == "Rule 3.6"


def test_ste_explain_finding_unknown() -> None:
    payload = ste_explain_finding("STE-NOT-A-REAL-RULE")
    assert payload["found"] is False
    assert "STE-PASSIVE" in payload["known_rule_ids"]


def test_ste_suggest_rewrite_as_function() -> None:
    payload = ste_suggest_rewrite("Utilize the tool.", max_findings=5)
    assert "prompt" in payload
    assert "findings" in payload
    assert "constraints" in payload
    assert "safe_fix_preview" in payload
    assert payload["compliant"] is False


def test_ste_suggest_semantic_review_as_function() -> None:
    payload = ste_suggest_semantic_review(
        "Remove the panel from the unit. It is damaged.",
        text_type="description",
        max_findings=5,
    )
    assert "prompt" in payload
    assert "findings" in payload
    assert "constraints" in payload
    assert "STE semantic review brief" in payload["prompt"]
    assert any(f["rule_id"] == "STE-PRONOUN-AMBIG" for f in payload["findings"])
    assert payload["compliant"] is True


def test_ste_explain_finding_tier3() -> None:
    payload = ste_explain_finding("STE-POS-MISMATCH")
    assert payload["found"] is True
    assert payload["rule_id"] == "STE-POS-MISMATCH"
    assert payload["default_severity"] == "warning"
    assert payload["text_type_scope"] == "both"
    assert payload["fix_hints"]


def test_ste_check_changed_files_not_repo(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    payload = ste_check_changed_files()
    assert payload["error"] == "not_a_git_repository"
    assert payload["files_checked"] == 0

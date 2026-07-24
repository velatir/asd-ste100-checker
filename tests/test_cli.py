"""CLI tests via click CliRunner."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from click.testing import CliRunner

from ste100.cli import main


def test_check_non_compliant_exit_code() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["check"], input="Utilize the tool.\n")
    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["compliant"] is False
    assert payload["summary"]["error"] >= 1


def test_check_compliant_exit_code() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["check"], input="Close the valve.\n")
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["compliant"] is True


def test_check_file_and_sarif(tmp_path) -> None:
    path = tmp_path / "sample.txt"
    path.write_text("Utilize the tool.\n", encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(main, ["check", str(path), "--output", "sarif"])
    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["version"] == "2.1.0"
    assert payload["runs"][0]["results"]


def test_lookup_utilize() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["lookup", "utilize"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["found"] is True
    assert payload["status"] == "unapproved"
    assert "use" in payload.get("alternatives", [])


def test_lookup_unknown() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["lookup", "xyzzynotaword"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["found"] is False


def _init_git_repo(root: Path) -> None:
    subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    (root / "doc.md").write_text("Close the valve.\n", encoding="utf-8")
    subprocess.run(["git", "add", "doc.md"], cwd=root, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "baseline"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    (root / "doc.md").write_text("Utilize the tool.\n", encoding="utf-8")


def test_check_changed_cli(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    _init_git_repo(root)
    monkeypatch.chdir(root)
    runner = CliRunner()
    result = runner.invoke(main, ["check-changed"])
    assert result.exit_code == 1, result.output or result.exception
    payload = json.loads(result.output)
    assert payload["compliant"] is False
    assert payload["files_checked"] >= 1
    assert any(f["path"] == "doc.md" for f in payload["files"])


def test_check_changed_not_repo(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(main, ["check-changed"])
    assert result.exit_code == 2
    combined = (result.output or "") + (getattr(result, "stderr", None) or "")
    if result.exception and not combined:
        combined = str(result.exception)
    assert "git" in combined.lower() or "error" in combined.lower() or "repository" in combined.lower()


def test_serve_help_lists_http_transport() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["serve", "--help"])
    assert result.exit_code == 0
    assert "--transport" in result.output
    assert "http" in result.output
    assert "STE100_MCP_TOKEN" in result.output or "bearer" in result.output.lower()


def test_lsp_help() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["lsp", "--help"])
    assert result.exit_code == 0
    assert "diagnostics" in result.output.lower() or "lsp" in result.output.lower()


def test_check_changed_base_option_help() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["check-changed", "--help"])
    assert result.exit_code == 0
    assert "--base" in result.output

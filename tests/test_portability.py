"""Tests for doctor / setup CLI and spaCy readiness helpers."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from ste100.cli import main
from ste100.core.paths import WORKSPACE_ENV
from ste100.core.spacy_ready import (
    SpacyModelStatus,
    check_spacy_model,
    ensure_spacy_model,
)
from ste100.mcp import server as mcp_server
from ste100.mcp.server import ste_check_file


def test_doctor_ok_when_model_loads() -> None:
    ok = SpacyModelStatus(model="en_core_web_sm", ok=True)
    runner = CliRunner()
    with patch("ste100.cli.check_spacy_model", return_value=ok):
        result = runner.invoke(main, ["doctor"])
    assert result.exit_code == 0
    assert "spacy_model_load: ok" in result.output
    assert "en_core_web_sm" in result.output


def test_doctor_fails_without_fix_or_network() -> None:
    bad = SpacyModelStatus(model="en_core_web_sm", ok=False, error="not found")
    runner = CliRunner()
    with patch("ste100.cli.check_spacy_model", return_value=bad) as check:
        with patch("ste100.cli.download_spacy_model") as download:
            result = runner.invoke(main, ["doctor"])
    assert result.exit_code == 1
    assert "spacy_model_load: FAIL" in result.output
    assert "ste100 setup" in result.output
    check.assert_called_once()
    download.assert_not_called()


def test_doctor_fix_downloads() -> None:
    bad = SpacyModelStatus(model="en_core_web_sm", ok=False, error="not found")
    ok = SpacyModelStatus(model="en_core_web_sm", ok=True)
    runner = CliRunner()
    with patch("ste100.cli.check_spacy_model", return_value=bad):
        with patch("ste100.cli.download_spacy_model", return_value=ok) as download:
            result = runner.invoke(main, ["doctor", "--fix"])
    assert result.exit_code == 0
    assert "spacy_model_load: ok" in result.output
    download.assert_called_once()


def test_setup_skips_download_when_present() -> None:
    ok = SpacyModelStatus(model="en_core_web_sm", ok=True)
    runner = CliRunner()
    with patch("ste100.cli.check_spacy_model", return_value=ok):
        with patch("ste100.cli.download_spacy_model") as download:
            result = runner.invoke(main, ["setup"])
    assert result.exit_code == 0
    assert "already available" in result.output
    download.assert_not_called()


def test_setup_downloads_when_missing() -> None:
    bad = SpacyModelStatus(model="en_core_web_sm", ok=False, error="missing")
    ok = SpacyModelStatus(model="en_core_web_sm", ok=True)
    runner = CliRunner()
    with patch("ste100.cli.check_spacy_model", return_value=bad):
        with patch("ste100.cli.download_spacy_model", return_value=ok) as download:
            result = runner.invoke(main, ["setup"])
    assert result.exit_code == 0
    assert "installed" in result.output
    download.assert_called_once()


def test_ensure_spacy_model_raises_system_exit() -> None:
    bad = SpacyModelStatus(model="en_core_web_sm", ok=False, error="boom")
    with patch("ste100.core.spacy_ready.check_spacy_model", return_value=bad):
        try:
            ensure_spacy_model()
            raised = False
        except SystemExit as exc:
            raised = True
            assert "setup" in str(exc)
    assert raised


def test_check_spacy_model_ok_smoke() -> None:
    # Real load of the default model (CI / local env must have it).
    status = check_spacy_model()
    assert status.ok is True


def test_run_server_calls_ensure_spacy_model() -> None:
    with patch("ste100.mcp.server.ensure_spacy_model") as ensure:
        with patch.object(mcp_server.mcp, "run") as run:
            mcp_server.run_server(transport="stdio")
    ensure.assert_called_once_with()
    run.assert_called_once()


def test_run_server_aborts_when_model_missing() -> None:
    with patch(
        "ste100.mcp.server.ensure_spacy_model",
        side_effect=SystemExit("error: spaCy model missing"),
    ):
        with patch.object(mcp_server.mcp, "run") as run:
            try:
                mcp_server.run_server(transport="stdio")
                raised = False
            except SystemExit:
                raised = True
    assert raised
    run.assert_not_called()


def test_ste_check_file_uses_workspace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    doc = tmp_path / "manual.txt"
    doc.write_text("Close the valve.\n", encoding="utf-8")
    monkeypatch.setenv(WORKSPACE_ENV, str(tmp_path))
    payload = ste_check_file("manual.txt")
    assert payload["compliant"] is True

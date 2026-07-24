"""Pytest harness for engine edge cases in tests/edge_cases/cases.json."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

import pytest
import yaml

from ste100.core.analyzer import analyze
from ste100.core.schema import Severity
from ste100.rules.registry import RULES

CASES_PATH = Path(__file__).resolve().parent / "edge_cases" / "cases.json"

_SEVERITY_RANK = {
    Severity.INFO.value: 0,
    Severity.WARNING.value: 1,
    Severity.ERROR.value: 2,
}


def _load_cases() -> list[dict[str, Any]]:
    data = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    return list(data["cases"])


ENGINE_CASES = [c for c in _load_cases() if c.get("kind") == "engine"]


def _write_glossary(spec: dict[str, Any], directory: Path) -> str:
    path = directory / "glossary.yaml"
    path.write_text(yaml.safe_dump(spec, sort_keys=False), encoding="utf-8")
    return str(path)


def _finding_rule_ids(result) -> set[str]:
    return {f.rule_id for f in result.findings}


def _rule_implemented(rule_id: str) -> bool:
    """Return True when the rule is registered and can fire on some input.

    STE-VOCAB-FORBIDDEN is registered but unused while the dictionary has no
    forbidden-status headwords — treat as unimplemented for skip_if.
    """
    if rule_id not in RULES:
        return False
    if rule_id == "STE-VOCAB-FORBIDDEN":
        return False
    return True


@pytest.mark.parametrize("case", ENGINE_CASES, ids=[c["id"] for c in ENGINE_CASES])
def test_engine_edge_case(case: dict[str, Any]) -> None:
    expect = case.get("expect") or {}
    skip_rule = expect.get("skip_if_rule_unimplemented")
    if skip_rule and not _rule_implemented(str(skip_rule)):
        pytest.skip(f"{case['id']}: rule {skip_rule} not implemented / no corpus")

    glossary_path: str | None = None
    tmp: tempfile.TemporaryDirectory[str] | None = None
    try:
        if case.get("glossary"):
            tmp = tempfile.TemporaryDirectory()
            glossary_path = _write_glossary(case["glossary"], Path(tmp.name))

        result = analyze(
            case["text"],
            text_type=case.get("text_type", "auto"),
            glossary_path=glossary_path,
        )
    finally:
        if tmp is not None:
            tmp.cleanup()

    rule_ids = _finding_rule_ids(result)

    if "compliant" in expect:
        assert result.compliant is expect["compliant"], (
            f"{case['id']}: compliant={result.compliant}, "
            f"findings={[f.rule_id for f in result.findings]}"
        )

    forbid_sev = expect.get("forbid_severity") or []
    for sev in forbid_sev:
        bad = [f for f in result.findings if f.severity.value == sev]
        assert not bad, f"{case['id']}: unexpected {sev} findings: {bad}"

    for rid in expect.get("rule_ids_all") or []:
        assert rid in rule_ids, (
            f"{case['id']}: expected rule {rid} in {sorted(rule_ids)}"
        )

    any_ids = expect.get("rule_ids_any") or []
    if any_ids:
        assert rule_ids.intersection(any_ids), (
            f"{case['id']}: expected one of {any_ids} in {sorted(rule_ids)}"
        )

    for rid in expect.get("forbid_rule_ids") or []:
        assert rid not in rule_ids, (
            f"{case['id']}: did not expect {rid}; got {sorted(rule_ids)}"
        )

    sev_min = expect.get("severity_min")
    if sev_min:
        target_ids = set(expect.get("rule_ids_all") or []) | set(
            expect.get("rule_ids_any") or []
        )
        relevant = (
            [f for f in result.findings if f.rule_id in target_ids]
            if target_ids
            else list(result.findings)
        )
        assert relevant, f"{case['id']}: no findings to check severity_min"
        min_rank = _SEVERITY_RANK[sev_min]
        assert any(_SEVERITY_RANK[f.severity.value] >= min_rank for f in relevant), (
            f"{case['id']}: expected severity >= {sev_min}"
        )

    for rid, want_sev in (expect.get("severity_for_rule") or {}).items():
        matches = [f for f in result.findings if f.rule_id == rid]
        assert matches, f"{case['id']}: missing {rid}"
        assert any(f.severity.value == want_sev for f in matches), (
            f"{case['id']}: expected {rid} severity {want_sev}, "
            f"got {[f.severity.value for f in matches]}"
        )

    suggestion_any = expect.get("suggestion_any") or []
    if suggestion_any:
        got = {
            s.replacement.lower()
            for f in result.findings
            for s in f.suggestions
        }
        assert any(alt.lower() in got for alt in suggestion_any), (
            f"{case['id']}: expected suggestion in {suggestion_any}, got {got}"
        )

    preferred_any = expect.get("preferred_term_any") or []
    if preferred_any:
        got_pref = {
            str((f.evidence or {}).get("preferred_term", "")).lower()
            for f in result.findings
            if (f.evidence or {}).get("preferred_term")
        }
        assert any(p.lower() in got_pref for p in preferred_any), (
            f"{case['id']}: expected preferred_term in {preferred_any}, got {got_pref}"
        )

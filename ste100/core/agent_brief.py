"""Unified host-agent brief builders (rewrite + semantic). No LLM API."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Any, Never

from ste100.core.analyzer import analyze
from ste100.core.fixes import apply_safe_fixes
from ste100.core.schema import AnalysisResult, Finding, Severity
from ste100.rules.semantic import (
    RULE_POS,
    RULE_PRONOUN,
    RULE_TOPIC,
)

DEFAULT_MAX_FINDINGS = 10

TIER3_RULE_IDS = frozenset({RULE_PRONOUN, RULE_TOPIC, RULE_POS})

_BASE_CONSTRAINTS: list[str] = [
    "Preserve IDs, numbers/units, and Warning/Caution/Note labels.",
    "Do not claim ASD-STE100 compliance until ste_check_text recheck succeeds.",
]


def _severity_rank(severity: Severity) -> int:
    if severity is Severity.ERROR:
        return 0
    if severity is Severity.WARNING:
        return 1
    if severity is Severity.INFO:
        return 2
    _exhaustive: Never = severity
    raise AssertionError(f"Unhandled Severity: {_exhaustive}")


def select_findings(
    findings: list[Finding],
    *,
    max_findings: int = DEFAULT_MAX_FINDINGS,
    rule_filter: Callable[[Finding], bool] | None = None,
) -> list[Finding]:
    """Return findings ordered errors → warnings → info, capped."""
    filtered = findings if rule_filter is None else [f for f in findings if rule_filter(f)]
    ordered = sorted(
        filtered,
        key=lambda f: (_severity_rank(f.severity), f.start, f.end, f.rule_id),
    )
    return ordered[: max(0, max_findings)]


@dataclass(frozen=True)
class BriefSpec:
    title: str
    intro: str
    findings_heading: str
    empty_findings: str
    instructions: list[str]
    constraints: list[str]
    output: str
    rule_filter: Callable[[Finding], bool] | None = None
    include_safe_fix: bool = False
    findings_total_fn: Callable[[list[Finding]], int] | None = None


REWRITE_SPEC = BriefSpec(
    title="STE rewrite brief",
    intro="Rewrite toward ASD-STE100-style STE. Unofficial; not affiliated with ASD.",
    findings_heading="## Findings (priority)",
    empty_findings="_No findings in this brief._",
    instructions=[
        "1. Minimal rewrite; clear ERRORs first; prefer high-confidence suggestions.",
        "2. Fix easy WARNINGs; else leave with short rationale.",
        "3. Short sentences (proc ≤20 / desc ≤25 words); one instruction per procedural sentence.",
        "4. Host must recheck with ste_check_text after rewrite.",
    ],
    constraints=[
        *_BASE_CONSTRAINTS,
    ],
    output="Return only rewritten text.",
    include_safe_fix=True,
)

SEMANTIC_SPEC = BriefSpec(
    title="STE semantic review brief",
    intro=(
        "Judge Tier-3 STE clarity (pronouns, topic sentence, POS). "
        "Unofficial; not affiliated with ASD."
    ),
    findings_heading="## Tier-3 findings (priority)",
    empty_findings="_No Tier-3 semantic findings in this brief._",
    instructions=[
        "1. Fix clear Tier-3 issues; leave false positives with short rationale.",
        "2. Name nouns instead of ambiguous pronouns; topic in first descriptive sentence.",
        "3. POS ERRORs are must-fix; WARNINGs are advisory.",
        "4. Host must recheck with ste_check_text after edits.",
    ],
    constraints=[
        *_BASE_CONSTRAINTS,
    ],
    output="Return only revised text.",
    rule_filter=lambda f: f.rule_id in TIER3_RULE_IDS,
    findings_total_fn=lambda findings: sum(1 for f in findings if f.rule_id in TIER3_RULE_IDS),
)


def build_prompt(
    text: str,
    result: AnalysisResult,
    selected: list[Finding],
    spec: BriefSpec,
) -> str:
    lines = [
        f"# {spec.title}",
        "",
        *spec.intro.split("\n"),
        "",
        f"text_type=`{result.text_type.value}` compliant=`{result.compliant}` "
        f"errors={result.summary.get('error', 0)} "
        f"warnings={result.summary.get('warning', 0)} "
        f"info={result.summary.get('info', 0)}",
        "",
        "## Source text",
        "",
        "```text",
        text.rstrip("\n"),
        "```",
        "",
        spec.findings_heading,
        "",
    ]
    if selected:
        lines.append(
            f"_See `findings` array ({len(selected)} items); address in priority order._"
        )
    else:
        lines.append(spec.empty_findings)
    lines.extend(["", "## Instructions", ""])
    lines.extend(spec.instructions)
    lines.extend(["", "## Output", "", spec.output])
    return "\n".join(lines) + "\n"


def _compact_finding(finding: Finding) -> dict[str, Any]:
    return {
        "rule_id": finding.rule_id,
        "severity": finding.severity.value,
        "start": finding.start,
        "end": finding.end,
        "suggestions": [s.replacement for s in finding.suggestions[:1]],
    }


def build_brief(
    text: str,
    spec: BriefSpec,
    text_type: str = "auto",
    glossary: str | None = None,
    max_findings: int = DEFAULT_MAX_FINDINGS,
    *,
    include_prompt: bool = True,
) -> dict[str, Any]:
    """Analyze text and return a prompt-return brief for the host agent."""
    result = analyze(text, text_type=text_type, glossary_path=glossary)
    selected = select_findings(
        result.findings,
        max_findings=max_findings,
        rule_filter=spec.rule_filter,
    )
    total_fn = spec.findings_total_fn or (lambda fs: len(fs))
    payload: dict[str, Any] = {
        "findings": [_compact_finding(f) for f in selected],
        "prompt": (
            build_prompt(text, result, selected, spec)
            if include_prompt
            else f"# {spec.title}\n"
        ),
        "constraints": list(spec.constraints),
        "text_type": result.text_type.value,
        "compliant": result.compliant,
        "summary": dict(result.summary),
        "max_findings": max_findings,
        "findings_total": total_fn(result.findings),
        "findings_included": len(selected),
        "analysis": None,
    }
    if spec.include_safe_fix:
        preview = apply_safe_fixes(text, glossary_path=glossary)
        payload["safe_fix_preview"] = {
            "original": "",
            "fixed": preview["fixed"],
            "diff": "",
            "replacements_applied": preview["replacements_applied"],
        }
    return payload


def suggest_rewrite(
    text: str,
    text_type: str = "auto",
    glossary: str | None = None,
    max_findings: int = DEFAULT_MAX_FINDINGS,
    *,
    include_safe_fix_preview: bool = True,
    include_prompt: bool = True,
) -> dict[str, Any]:
    """Rewrite brief for the host agent (no LLM API)."""
    spec = REWRITE_SPEC
    if not include_safe_fix_preview:
        spec = replace(REWRITE_SPEC, include_safe_fix=False)
    payload = build_brief(
        text,
        spec,
        text_type,
        glossary,
        max_findings,
        include_prompt=include_prompt,
    )
    if not include_safe_fix_preview:
        payload["safe_fix_preview"] = None
    return payload


def suggest_semantic_review(
    text: str,
    text_type: str = "auto",
    glossary: str | None = None,
    max_findings: int = DEFAULT_MAX_FINDINGS,
    *,
    include_prompt: bool = True,
) -> dict[str, Any]:
    """Tier-3 semantic brief for the host agent (no LLM API)."""
    return build_brief(
        text,
        SEMANTIC_SPEC,
        text_type,
        glossary,
        max_findings,
        include_prompt=include_prompt,
    )


def filter_tier3_findings(findings: list[Finding]) -> list[Finding]:
    return [f for f in findings if f.rule_id in TIER3_RULE_IDS]

"""Unified host-agent brief builders (rewrite + semantic). No LLM API."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Any, Never

from ste100.core.analyzer import analyze
from ste100.core.fixes import apply_safe_fixes
from ste100.core.schema import AnalysisResult, Finding, Severity
from ste100.core.serialize import to_json
from ste100.rules.semantic import (
    RULE_POS,
    RULE_PRONOUN,
    RULE_TOPIC,
)

DEFAULT_MAX_FINDINGS = 20

TIER3_RULE_IDS = frozenset({RULE_PRONOUN, RULE_TOPIC, RULE_POS})

_BASE_CONSTRAINTS: list[str] = [
    "Preserve part numbers, serial numbers, document IDs, and software identifiers.",
    "Preserve numeric values and units (for example 5 mm, 120 °C).",
    "Preserve Warning / Caution / Note labels and safety-critical conditions.",
    "Do not claim ASD-STE100 compliance or certification.",
    "Do not claim the rewrite is compliant until ste_check_text (or equivalent) recheck succeeds.",
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


def _finding_lines(findings: list[Finding]) -> list[str]:
    lines: list[str] = []
    for i, finding in enumerate(findings, start=1):
        span = finding.evidence.get("text") if isinstance(finding.evidence, dict) else None
        span_bit = f" span={span!r}" if span else ""
        sugg = ""
        if finding.suggestions:
            alts = ", ".join(s.replacement for s in finding.suggestions[:3])
            sugg = f" suggestions=[{alts}]"
        lines.append(
            f"{i}. [{finding.severity.value}] {finding.rule_id}: {finding.message}"
            f" (chars {finding.start}-{finding.end}){span_bit}{sugg}"
        )
    return lines


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
    intro=(
        "You are rewriting technical text toward ASD-STE100-style Simplified "
        "Technical English.\nThis checker is unofficial and not affiliated with ASD."
    ),
    findings_heading="## Findings to address (priority order)",
    empty_findings="_No findings in this brief (text may already be clear of ERRORS)._",
    instructions=[
        "1. Produce a **minimal** rewrite that clears ERROR findings first.",
        "2. Prefer finding `suggestions` when present and high-confidence.",
        "3. Fix WARNINGs when straightforward; otherwise leave with a short rationale.",
        "4. Prefer short sentences (procedures ≤ 20 words; descriptions ≤ 25 words).",
        "5. Use approved dictionary alternatives; keep one instruction per procedural sentence.",
        "6. After you rewrite, the host must recheck with `ste_check_text` "
        "(or `ste_check_file` / `ste_check_changed_files`).",
    ],
    constraints=[
        *_BASE_CONSTRAINTS[:3],
        "Change only what findings require; prefer minimal edits over stylistic rewrite.",
        *_BASE_CONSTRAINTS[3:],
    ],
    output=(
        "Return only the rewritten text (no preamble). "
        "If you cannot clear an ERROR without changing safety meaning, "
        "keep the original span and note it separately."
    ),
    include_safe_fix=True,
)

SEMANTIC_SPEC = BriefSpec(
    title="STE semantic review brief",
    intro=(
        "You are reviewing technical text for ASD-STE100-style semantic clarity "
        "(pronouns, topic sentence, approved part-of-speech use).\n"
        "This checker is unofficial and not affiliated with ASD."
    ),
    findings_heading="## Tier-3 findings to judge (priority order)",
    empty_findings="_No Tier-3 semantic findings in this brief._",
    instructions=[
        "1. Judge each Tier-3 finding: fix when clearly warranted; leave with "
        "a short rationale when the heuristic is a false positive.",
        "2. Prefer naming the referent noun instead of ambiguous pronouns.",
        "3. For descriptions, put the topic in the first sentence.",
        "4. For POS mismatches, use the approved dictionary part of speech "
        "(or an approved alternative for that sense).",
        "5. ERROR-level POS mismatches are must-fix (or report unresolved).",
        "6. After edits, the host must recheck with `ste_check_text` "
        "(or `ste_check_file` / `ste_check_changed_files`).",
    ],
    constraints=[
        *_BASE_CONSTRAINTS[:3],
        "Change only what semantic findings require; prefer naming nouns over vague pronouns.",
        *_BASE_CONSTRAINTS[3:],
        "Treat Tier-3 WARNINGs as advisory judgment calls; escalate POS ERRORs as must-fix.",
    ],
    output=(
        "Return only the revised text (no preamble), or the original text "
        "unchanged if you leave all findings with rationale separately."
    ),
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
        f"**Detected text type:** `{result.text_type.value}`",
        f"**Compliant (no ERROR findings):** `{result.compliant}`",
        f"**Summary:** errors={result.summary.get('error', 0)}, "
        f"warnings={result.summary.get('warning', 0)}, "
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
        lines.extend(_finding_lines(selected))
    else:
        lines.append(spec.empty_findings)
    lines.extend(["", "## Instructions", ""])
    lines.extend(spec.instructions)
    lines.extend(["", "## Constraints", ""])
    for constraint in spec.constraints:
        lines.append(f"- {constraint}")
    lines.extend(["", "## Output", "", spec.output])
    return "\n".join(lines) + "\n"


def build_brief(
    text: str,
    spec: BriefSpec,
    text_type: str = "auto",
    glossary: str | None = None,
    max_findings: int = DEFAULT_MAX_FINDINGS,
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
        "findings": [f.model_dump(mode="json") for f in selected],
        "prompt": build_prompt(text, result, selected, spec),
        "constraints": list(spec.constraints),
        "text_type": result.text_type.value,
        "compliant": result.compliant,
        "summary": dict(result.summary),
        "max_findings": max_findings,
        "findings_total": total_fn(result.findings),
        "findings_included": len(selected),
        "analysis": to_json(result),
    }
    if spec.include_safe_fix:
        payload["safe_fix_preview"] = apply_safe_fixes(text, glossary_path=glossary)
    return payload


def suggest_rewrite(
    text: str,
    text_type: str = "auto",
    glossary: str | None = None,
    max_findings: int = DEFAULT_MAX_FINDINGS,
    *,
    include_safe_fix_preview: bool = True,
) -> dict[str, Any]:
    """Rewrite brief for the host agent (no LLM API)."""
    spec = REWRITE_SPEC
    if not include_safe_fix_preview:
        spec = replace(REWRITE_SPEC, include_safe_fix=False)
    payload = build_brief(text, spec, text_type, glossary, max_findings)
    if not include_safe_fix_preview:
        payload["safe_fix_preview"] = None
    return payload


def suggest_semantic_review(
    text: str,
    text_type: str = "auto",
    glossary: str | None = None,
    max_findings: int = DEFAULT_MAX_FINDINGS,
) -> dict[str, Any]:
    """Tier-3 semantic brief for the host agent (no LLM API)."""
    return build_brief(text, SEMANTIC_SPEC, text_type, glossary, max_findings)


def filter_tier3_findings(findings: list[Finding]) -> list[Finding]:
    return [f for f in findings if f.rule_id in TIER3_RULE_IDS]

"""Explain STE rules: join the registry with curated rules.json metadata.

Owns the rule-catalog join that was previously trapped in the MCP adapter.
The dictionary engine no longer loads rules.json; this module loads it lazily
on first explain call, so the analysis path never pays for rule metadata.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ste100.core.schema import RuleMeta
from ste100.rules.registry import RULES

_RULES_JSON = Path(__file__).resolve().parent.parent / "dictionary" / "data" / "rules.json"

_rule_meta_cache: list[RuleMeta] | None = None


def _load_rule_meta() -> list[RuleMeta]:
    global _rule_meta_cache
    if _rule_meta_cache is None:
        with _RULES_JSON.open(encoding="utf-8") as fh:
            raw = json.load(fh)
        _rule_meta_cache = [
            RuleMeta.model_validate(item) for item in raw.get("rules", [])
        ]
    return _rule_meta_cache


def _rule_meta_by_id() -> dict[str, RuleMeta]:
    return {r.rule_id: r for r in _load_rule_meta()}


def _primary_rule_ref(rule_ref: str | None) -> str | None:
    if not rule_ref:
        return None
    # "Rule 3.2 / 3.4" → look up Rule 3.2 first
    primary = rule_ref.split("/")[0].strip()
    if primary.lower().startswith("rule"):
        return primary
    return rule_ref


def explain_rule(rule_id: str) -> dict[str, Any]:
    """Explain a checker rule_id using registry metadata and rules.json."""
    key = (rule_id or "").strip()
    reg = RULES.get(key)
    if reg is None:
        lower = key.lower()
        for rid, candidate in RULES.items():
            if rid.lower() == lower:
                reg = candidate
                key = rid
                break
    if reg is None:
        return {
            "found": False,
            "rule_id": rule_id,
            "message": f"Unknown rule_id {rule_id!r}.",
            "known_rule_ids": sorted(RULES.keys()),
        }

    by_id = _rule_meta_by_id()
    pdf_meta: RuleMeta | None = None
    primary = _primary_rule_ref(reg.rule_ref)
    if primary and primary in by_id:
        pdf_meta = by_id[primary]
    elif reg.rule_ref:
        pdf_meta = by_id.get(reg.rule_ref)

    title = reg.title or (pdf_meta.title if pdf_meta else reg.rule_id)
    description = reg.description

    pdf_rule = None
    if pdf_meta:
        pdf_rule = {
            "rule_id": pdf_meta.rule_id,
            "section": pdf_meta.section,
            "title": pdf_meta.title,
            "summary": None,
            "text_type": pdf_meta.text_type.value if pdf_meta.text_type else None,
        }

    return {
        "found": True,
        "rule_id": reg.rule_id,
        "title": title,
        "description": description,
        "default_severity": reg.severity.value,
        "rule_ref": reg.rule_ref,
        "fix_hints": list(reg.fix_hints)[:3],
        "text_type_scope": reg.text_type_scope,
        "pdf_rule": pdf_rule,
    }

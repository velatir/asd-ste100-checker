"""Nominalization detection: flag noun+light-verb patterns (STE Rule 3.7)."""

from __future__ import annotations

import json
from pathlib import Path

from spacy.tokens import Doc, Token

from ste100.core.schema import Finding, Severity, Suggestion
from ste100.rules.context import AnalysisContext
from ste100.rules.spacy_util import sentence_index_for_token

RULE_NOMINALIZATION = "STE-NOMINALIZATION"

_DATA_PATH = Path(__file__).resolve().parent.parent / "dictionary" / "data" / "nominalizations.json"

_LIGHT_VERBS = frozenset({
    "perform", "make", "do", "carry", "conduct", "give", "take",
    "have", "provide", "achieve", "accomplish", "undertake", "effect",
})

_NOMINALIZATION_MAP: dict[str, str] = {}


def _ensure_loaded() -> dict[str, str]:
    if _NOMINALIZATION_MAP:
        return _NOMINALIZATION_MAP
    raw = json.loads(_DATA_PATH.read_text(encoding="utf-8"))
    for entry in raw:
        _NOMINALIZATION_MAP[entry["noun"].lower()] = entry["verb"]
    return _NOMINALIZATION_MAP


def _has_light_verb_governor(token: Token) -> Token | None:
    """Walk up the dependency tree looking for a light-verb head."""
    head = token.head
    if head.i == token.i:
        return None
    if head.pos_ == "VERB" and head.lemma_.lower() in _LIGHT_VERBS:
        return head
    if head.pos_ == "ADP" and head.head.pos_ == "VERB":
        if head.head.lemma_.lower() in _LIGHT_VERBS:
            return head.head
    return None


def check_nominalizations(doc: Doc, context: AnalysisContext) -> list[Finding]:
    """Flag light-verb + nominalization patterns (e.g. 'perform an analysis')."""
    nom_map = _ensure_loaded()
    findings: list[Finding] = []

    for token in doc:
        if token.pos_ != "NOUN":
            continue
        lemma = token.lemma_.lower()
        if lemma not in nom_map:
            continue
        light_verb = _has_light_verb_governor(token)
        if light_verb is None:
            continue

        verb_form = nom_map[lemma]
        span_start = min(light_verb.idx, token.idx)
        span_end = max(
            light_verb.idx + len(light_verb.text),
            token.idx + len(token.text),
        )

        findings.append(
            Finding(
                rule_id=RULE_NOMINALIZATION,
                severity=Severity.WARNING,
                message=(
                    f"Prefer '{verb_form}' over '{light_verb.text} … {token.text}' "
                    f"(Rule 3.7)."
                ),
                start=span_start,
                end=span_end,
                sentence=sentence_index_for_token(token),
                evidence={
                    "rule_ref": "Rule 3.7",
                    "light_verb": light_verb.text,
                    "nominalization": token.text,
                    "preferred_verb": verb_form,
                },
                suggestions=[
                    Suggestion(replacement=verb_form, confidence=0.8, automatic=False),
                ],
            )
        )

    return findings

"""Rule registry: maps rule_id to check callables and metadata."""

from __future__ import annotations

from dataclasses import dataclass, field

from ste100.core.schema import Severity
from ste100.rules.context import AnalysisContext, CheckFn
from ste100.rules.semantic import (
    check_pos_mismatch,
    check_pronoun_ambiguity,
    check_topic_sentence,
)
from ste100.rules.nominalization import check_nominalizations
from ste100.rules.sentence import (
    check_contractions,
    check_one_instruction,
    check_semicolons,
    check_sentence_length,
)
from ste100.rules.structural import check_units_format
from ste100.rules.syntax import (
    check_imperative,
    check_noun_cluster,
    check_passive,
    check_verb_form,
)
from ste100.rules.vocabulary import check_vocabulary


@dataclass(frozen=True)
class RuleRegistration:
    """Metadata + check function for a registered rule."""

    rule_id: str
    check: CheckFn
    severity: Severity
    description: str
    title: str = ""
    rule_ref: str | None = None
    fix_hints: tuple[str, ...] = field(default_factory=tuple)
    text_type_scope: str = "both"  # procedure | description | both


RULES: dict[str, RuleRegistration] = {
    "STE-VOCAB-UNAPPROVED": RuleRegistration(
        rule_id="STE-VOCAB-UNAPPROVED",
        check=check_vocabulary,
        severity=Severity.ERROR,
        description=(
            "Words not approved in the STE dictionary (Rule 1.1)."
        ),
        title="Unapproved vocabulary",
        rule_ref="Rule 1.1",
        fix_hints=(
            "Replace with an approved alternative from the finding or ste_lookup_word.",
        ),
        text_type_scope="both",
    ),
    "STE-VOCAB-FORBIDDEN": RuleRegistration(
        rule_id="STE-VOCAB-FORBIDDEN",
        check=check_vocabulary,
        severity=Severity.ERROR,
        description="Forbidden STE words or constructions (Rule 1.1).",
        title="Forbidden vocabulary",
        rule_ref="Rule 1.1",
        fix_hints=("Remove or replace the forbidden word with an approved term.",),
        text_type_scope="both",
    ),
    "STE-SENTENCE-LENGTH": RuleRegistration(
        rule_id="STE-SENTENCE-LENGTH",
        check=check_sentence_length,
        severity=Severity.ERROR,
        description=(
            "Procedural sentences max 20 words; descriptive max 25 words (Rule 2.2)."
        ),
        title="Sentence length",
        rule_ref="Rule 2.2 / 5.1 / 6.1",
        fix_hints=("Split into shorter sentences that stay within the word limit.",),
        text_type_scope="both",
    ),
    "STE-ONE-INSTRUCTION": RuleRegistration(
        rule_id="STE-ONE-INSTRUCTION",
        check=check_one_instruction,
        severity=Severity.WARNING,
        description=(
            "Procedural sentences should contain one instruction only "
            "(coordinated imperatives heuristic)."
        ),
        title="One instruction per sentence",
        rule_ref="Rule 5.2",
        fix_hints=("Split coordinated instructions into separate numbered steps.",),
        text_type_scope="procedure",
    ),
    "STE-UNITS-FORMAT": RuleRegistration(
        rule_id="STE-UNITS-FORMAT",
        check=check_units_format,
        severity=Severity.INFO,
        description=(
            "Prefer spaced units (10 mm) and flag bare measurement-like numbers."
        ),
        title="Units formatting",
        rule_ref="STE units formatting",
        fix_hints=("Insert a space between the number and the unit (e.g. 10 mm).",),
        text_type_scope="both",
    ),
    "STE-PASSIVE": RuleRegistration(
        rule_id="STE-PASSIVE",
        check=check_passive,
        severity=Severity.ERROR,
        description=(
            "Prefer active voice in procedures; verbal passive is flagged "
            "(Rule 3.6). Candidate-aware severity."
        ),
        title="Active voice (passive detected)",
        rule_ref="Rule 3.6",
        fix_hints=(
            "Rewrite in active voice.",
            "In procedures, prefer an imperative instruction.",
        ),
        text_type_scope="procedure",
    ),
    "STE-IMPERATIVE": RuleRegistration(
        rule_id="STE-IMPERATIVE",
        check=check_imperative,
        severity=Severity.ERROR,
        description=(
            "Procedural steps should use the imperative (command) form "
            "(Rule 5.3). Candidate-aware severity."
        ),
        title="Imperative instructions",
        rule_ref="Rule 5.3",
        fix_hints=(
            "Rewrite the step as an imperative (e.g. 'Close the valve.').",
        ),
        text_type_scope="procedure",
    ),
    "STE-VERB-FORM": RuleRegistration(
        rule_id="STE-VERB-FORM",
        check=check_verb_form,
        severity=Severity.ERROR,
        description=(
            "Disallowed progressive/perfect/complex verb constructions "
            "(Rules 3.2 / 3.4). Candidate-aware severity."
        ),
        title="Approved verb forms",
        rule_ref="Rule 3.2 / 3.4",
        fix_hints=(
            "Use infinitive, imperative, simple present/past/future, or past "
            "participle as adjective only.",
            "Avoid progressive, perfect, and modal+passive stacks.",
        ),
        text_type_scope="both",
    ),
    "STE-NOUN-CLUSTER": RuleRegistration(
        rule_id="STE-NOUN-CLUSTER",
        check=check_noun_cluster,
        severity=Severity.ERROR,
        description=(
            "Multi-word nouns must have at most three words (Rule 2.1)."
        ),
        title="Noun cluster length",
        rule_ref="Rule 2.1",
        fix_hints=(
            "Shorten the multi-word noun to three words or fewer.",
            "Use hyphens or a shorter approved technical noun.",
        ),
        text_type_scope="both",
    ),
    "STE-PRONOUN-AMBIG": RuleRegistration(
        rule_id="STE-PRONOUN-AMBIG",
        check=check_pronoun_ambiguity,
        severity=Severity.WARNING,
        description=(
            "Flag ambiguous pronouns (it/this/these/those/they) when the prior "
            "sentence has no clear antecedent or multiple candidates."
        ),
        title="Ambiguous pronoun",
        rule_ref="STE pronoun clarity",
        fix_hints=("Name the noun instead of using a vague pronoun.",),
        text_type_scope="both",
    ),
    "STE-TOPIC-SENTENCE": RuleRegistration(
        rule_id="STE-TOPIC-SENTENCE",
        check=check_topic_sentence,
        severity=Severity.WARNING,
        description=(
            "Description openings should state the topic; weak openers "
            "(pronoun/demonstrative start, fragment, coordination, meta-comment) "
            "are flagged."
        ),
        title="Topic sentence",
        rule_ref="STE topic sentence",
        fix_hints=("Put the topic noun in the first sentence.",),
        text_type_scope="description",
    ),
    "STE-POS-MISMATCH": RuleRegistration(
        rule_id="STE-POS-MISMATCH",
        check=check_pos_mismatch,
        severity=Severity.WARNING,
        description=(
            "Approved dictionary part of speech must match usage "
            "(verb↔noun / adj↔noun). High-confidence clashes escalate to ERROR; "
            "TN/TV and unapproved words are skipped."
        ),
        title="Approved POS mismatch",
        rule_ref="Rule 1.2 / 1.3",
        fix_hints=(
            "Use the approved part of speech.",
            "Rewrite with an approved alternative for the intended sense.",
        ),
        text_type_scope="both",
    ),
    "STE-SEMICOLON": RuleRegistration(
        rule_id="STE-SEMICOLON",
        check=check_semicolons,
        severity=Severity.ERROR,
        description="Semicolons are not permitted in STE; use separate sentences.",
        title="No semicolons",
        rule_ref="Rule 7.1",
        fix_hints=("Replace the semicolon with a period and start a new sentence.",),
        text_type_scope="both",
    ),
    "STE-CONTRACTION": RuleRegistration(
        rule_id="STE-CONTRACTION",
        check=check_contractions,
        severity=Severity.WARNING,
        description="Contractions are not permitted in STE; use the full form.",
        title="No contractions",
        rule_ref="Rule 1.5",
        fix_hints=("Expand the contraction to its full form.",),
        text_type_scope="both",
    ),
    "STE-NOMINALIZATION": RuleRegistration(
        rule_id="STE-NOMINALIZATION",
        check=check_nominalizations,
        severity=Severity.WARNING,
        description="Prefer the verb form over noun+light-verb (Rule 3.7).",
        title="Nominalization",
        rule_ref="Rule 3.7",
        fix_hints=("Use the verb directly instead of noun + light verb.",),
        text_type_scope="both",
    ),
}


def get_all_checks() -> list[CheckFn]:
    """Return unique check callables: (doc, context) -> list[Finding]."""
    seen: set[int] = set()
    checks: list[CheckFn] = []
    for reg in RULES.values():
        key = id(reg.check)
        if key in seen:
            continue
        seen.add(key)
        checks.append(reg.check)
    return checks


def get_rule_meta() -> list[dict[str, str]]:
    """SARIF / tooling metadata for registered rules."""
    return [
        {
            "id": reg.rule_id,
            "shortDescription": reg.description,
            "defaultSeverity": reg.severity.value,
        }
        for reg in RULES.values()
    ]


__all__ = [
    "AnalysisContext",
    "CheckFn",
    "RULES",
    "RuleRegistration",
    "get_all_checks",
    "get_rule_meta",
]

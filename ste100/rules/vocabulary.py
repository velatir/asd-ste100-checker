"""Vocabulary rules: approved-word lookup, forbidden/unapproved terms (Rule 1.1)."""

from __future__ import annotations

from typing import Never

from spacy.tokens import Doc

from ste100.core.schema import Finding, Severity, Suggestion, WordStatus
from ste100.dictionary.engine import is_non_vocabulary_token
from ste100.rules.context import AnalysisContext
from ste100.rules.spacy_util import sentence_index_for_token

RULE_UNAPPROVED = "STE-VOCAB-UNAPPROVED"
RULE_FORBIDDEN = "STE-VOCAB-FORBIDDEN"
STE_RULE_REF = "Rule 1.1"


def _suggestions_for(word: str, context: AnalysisContext) -> list[Suggestion]:
    alts = context.dictionary.suggest_alternatives(word)
    out: list[Suggestion] = []
    for i, alt in enumerate(alts):
        out.append(
            Suggestion(
                replacement=alt,
                confidence=1.0 if len(alts) == 1 else max(0.4, 0.9 - 0.15 * i),
                automatic=len(alts) == 1,
            )
        )
    return out


def check_vocabulary(doc: Doc, context: AnalysisContext) -> list[Finding]:
    """Flag unapproved/forbidden alphabetic tokens; respect glossary overrides."""
    findings: list[Finding] = []
    seen_spans: set[tuple[int, int]] = set()

    for token in doc:
        if token.is_space or token.is_punct:
            continue
        text = token.text
        if is_non_vocabulary_token(text):
            continue
        if not any(ch.isalpha() for ch in text):
            continue

        key = text.lower()
        preferred = context.dictionary.preferred_terms.get(key)
        record = context.dictionary.lookup(text)

        span_key = (token.idx, token.idx + len(token.text))
        if span_key in seen_spans:
            continue

        # Glossary preferred_terms: surface form should be replaced
        if preferred is not None:
            seen_spans.add(span_key)
            findings.append(
                Finding(
                    rule_id=RULE_UNAPPROVED,
                    severity=Severity.ERROR,
                    message=(
                        f"Prefer '{preferred}' instead of '{text}' "
                        f"(project glossary preferred term)."
                    ),
                    start=token.idx,
                    end=token.idx + len(token.text),
                    sentence=sentence_index_for_token(token),
                    evidence={
                        "rule_ref": STE_RULE_REF,
                        "word": text,
                        "preferred_term": preferred,
                        "source": "glossary",
                    },
                    suggestions=[
                        Suggestion(
                            replacement=preferred,
                            confidence=1.0,
                            automatic=True,
                        )
                    ],
                )
            )
            continue

        if record is None:
            # Not in dictionary and not a glossary-approved technical term
            seen_spans.add(span_key)
            findings.append(
                Finding(
                    rule_id=RULE_UNAPPROVED,
                    severity=Severity.ERROR,
                    message=f"Word '{text}' is not in the approved STE dictionary.",
                    start=token.idx,
                    end=token.idx + len(token.text),
                    sentence=sentence_index_for_token(token),
                    evidence={
                        "rule_ref": STE_RULE_REF,
                        "word": text,
                        "status": "not_in_dictionary",
                    },
                    suggestions=_suggestions_for(text, context),
                )
            )
            continue

        status = record.status
        if status in (
            WordStatus.APPROVED,
            WordStatus.TECHNICAL_NOUN,
            WordStatus.TECHNICAL_VERB,
        ):
            continue

        seen_spans.add(span_key)
        if status is WordStatus.FORBIDDEN:
            findings.append(
                Finding(
                    rule_id=RULE_FORBIDDEN,
                    severity=Severity.ERROR,
                    message=f"Forbidden word or construction '{text}'.",
                    start=token.idx,
                    end=token.idx + len(token.text),
                    sentence=sentence_index_for_token(token),
                    evidence={
                        "rule_ref": record.rule_ref or STE_RULE_REF,
                        "word": text,
                        "status": status.value,
                        "headword": record.word,
                    },
                    suggestions=_suggestions_for(text, context),
                )
            )
        elif status in (
            WordStatus.UNAPPROVED,
            WordStatus.NOT_APPROVED_TECHNICAL_VERB,
        ):
            findings.append(
                Finding(
                    rule_id=RULE_UNAPPROVED,
                    severity=Severity.ERROR,
                    message=f"Unapproved word '{text}'; use an approved alternative.",
                    start=token.idx,
                    end=token.idx + len(token.text),
                    sentence=sentence_index_for_token(token),
                    evidence={
                        "rule_ref": record.rule_ref or STE_RULE_REF,
                        "word": text,
                        "status": status.value,
                        "headword": record.word,
                    },
                    suggestions=_suggestions_for(text, context),
                )
            )
        elif status in (
            WordStatus.APPROVED,
            WordStatus.TECHNICAL_NOUN,
            WordStatus.TECHNICAL_VERB,
        ):
            continue
        else:
            _exhaustive: Never = status
            raise AssertionError(f"Unhandled WordStatus: {_exhaustive}")

    return findings

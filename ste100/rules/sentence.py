"""Sentence-level rules: length, one instruction, semicolons, contractions."""

from __future__ import annotations

import re
from typing import Never

from spacy.tokens import Doc, Span, Token

from ste100.core.schema import Finding, Severity, Suggestion, TextType
from ste100.rules.context import AnalysisContext
from ste100.rules.spacy_util import sentence_index

RULE_LENGTH = "STE-SENTENCE-LENGTH"
RULE_ONE_INSTRUCTION = "STE-ONE-INSTRUCTION"
RULE_SEMICOLON = "STE-SEMICOLON"
RULE_CONTRACTION = "STE-CONTRACTION"

PROCEDURE_MAX_WORDS = 20
DESCRIPTION_MAX_WORDS = 25


def _max_words(text_type: TextType) -> int:
    if text_type is TextType.PROCEDURE:
        return PROCEDURE_MAX_WORDS
    if text_type is TextType.DESCRIPTION:
        return DESCRIPTION_MAX_WORDS
    _exhaustive: Never = text_type
    raise AssertionError(f"Unhandled TextType: {_exhaustive}")


def _word_count(sent: Span) -> int:
    return sum(1 for t in sent if not t.is_space and not t.is_punct)


def _is_imperative_candidate(token: Token) -> bool:
    """Heuristic: base-form verb used as instruction (VB / ROOT imperative)."""
    if token.pos_ != "VERB":
        return False
    if token.tag_ == "VB":
        return True
    # spaCy sometimes tags imperatives as VBP
    if token.dep_ == "ROOT" and token.tag_ in {"VB", "VBP"}:
        return True
    return False


def _coordinated_imperatives(sent: Span) -> list[Token]:
    """Collect imperative-like verbs joined by 'and' or split by ';'."""
    candidates = [t for t in sent if _is_imperative_candidate(t)]
    if len(candidates) < 2:
        # Semicolon-separated clauses each starting with an imperative
        text = sent.text
        if ";" not in text:
            return []
        clause_starts: list[Token] = []
        # First verb of each semicolon-delimited segment
        segments = []
        current: list[Token] = []
        for token in sent:
            if token.text == ";":
                if current:
                    segments.append(current)
                current = []
            else:
                current.append(token)
        if current:
            segments.append(current)
        for seg in segments:
            for tok in seg:
                if tok.is_space or tok.is_punct:
                    continue
                if _is_imperative_candidate(tok) or (
                    tok.pos_ == "VERB" and tok.tag_ in {"VB", "VBP"}
                ):
                    clause_starts.append(tok)
                break
        return clause_starts if len(clause_starts) >= 2 else []

    # Require coordination via 'and' (conj) or presence of semicolon
    has_semicolon = any(t.text == ";" for t in sent)
    coordinated = []
    for tok in candidates:
        if tok.dep_ == "ROOT" or tok.dep_ == "conj" or has_semicolon:
            coordinated.append(tok)
        elif any(
            c.text.lower() == "and" and c.i > candidates[0].i and c.i < tok.i
            for c in sent
        ):
            coordinated.append(tok)
    # Deduplicate while preserving order
    seen: set[int] = set()
    unique: list[Token] = []
    for tok in coordinated:
        if tok.i not in seen:
            seen.add(tok.i)
            unique.append(tok)
    if len(unique) >= 2 and (
        has_semicolon
        or any(t.dep_ == "conj" for t in unique)
        or any(t.text.lower() == "and" for t in sent)
    ):
        return unique
    return []


def check_sentence_length(doc: Doc, context: AnalysisContext) -> list[Finding]:
    """Flag sentences that exceed STE Issue 9 length limits."""
    limit = _max_words(context.text_type)
    findings: list[Finding] = []
    for sent in doc.sents:
        count = _word_count(sent)
        if count <= limit:
            continue
        findings.append(
            Finding(
                rule_id=RULE_LENGTH,
                severity=Severity.ERROR,
                message=(
                    f"Sentence has {count} words; maximum for "
                    f"{context.text_type.value} text is {limit} (Rule 2.2)."
                ),
                start=sent.start_char,
                end=sent.end_char,
                sentence=sentence_index(doc, sent),
                evidence={
                    "rule_ref": "Rule 2.2",
                    "word_count": count,
                    "limit": limit,
                    "text_type": context.text_type.value,
                },
                suggestions=[],
            )
        )
    return findings


def check_one_instruction(doc: Doc, context: AnalysisContext) -> list[Finding]:
    """Procedural sentences should contain one instruction (imperative) only."""
    if context.text_type is not TextType.PROCEDURE:
        return []

    findings: list[Finding] = []
    for sent in doc.sents:
        verbs = _coordinated_imperatives(sent)
        if len(verbs) < 2:
            continue
        findings.append(
            Finding(
                rule_id=RULE_ONE_INSTRUCTION,
                severity=Severity.WARNING,
                message=(
                    "Procedural sentence appears to contain more than one instruction; "
                    "split into separate steps."
                ),
                start=sent.start_char,
                end=sent.end_char,
                sentence=sentence_index(doc, sent),
                evidence={
                    "rule_ref": "Rule 3.3",
                    "imperative_verbs": [t.text for t in verbs],
                },
                suggestions=[],
            )
        )
    return findings


def check_semicolons(doc: Doc, context: AnalysisContext) -> list[Finding]:
    """STE prohibits semicolons — use separate sentences (Rule 7.1)."""
    findings: list[Finding] = []
    text = context.text
    for match in re.finditer(r";", text):
        findings.append(
            Finding(
                rule_id=RULE_SEMICOLON,
                severity=Severity.ERROR,
                message="Semicolons are not permitted in STE; use separate sentences.",
                start=match.start(),
                end=match.end(),
                sentence=None,
                evidence={"rule_ref": "Rule 7.1"},
                suggestions=[
                    Suggestion(replacement=". ", confidence=0.7, automatic=False),
                ],
            )
        )
    return findings


_CONTRACTION_PATTERN = re.compile(
    r"\b("
    r"don't|doesn't|didn't|won't|wouldn't|can't|couldn't|shouldn't|"
    r"isn't|aren't|wasn't|weren't|hasn't|haven't|hadn't|"
    r"it's|he's|she's|that's|there's|here's|who's|what's|"
    r"I'm|I've|I'll|I'd|we're|we've|we'll|we'd|"
    r"they're|they've|they'll|they'd|you're|you've|you'll|you'd|"
    r"let's|ain't"
    r")\b",
    re.IGNORECASE,
)

_CONTRACTION_EXPANSIONS: dict[str, str] = {
    "don't": "do not", "doesn't": "does not", "didn't": "did not",
    "won't": "will not", "wouldn't": "would not",
    "can't": "cannot", "couldn't": "could not", "shouldn't": "should not",
    "isn't": "is not", "aren't": "are not",
    "wasn't": "was not", "weren't": "were not",
    "hasn't": "has not", "haven't": "have not", "hadn't": "had not",
    "it's": "it is", "he's": "he is", "she's": "she is",
    "that's": "that is", "there's": "there is", "here's": "here is",
    "who's": "who is", "what's": "what is",
    "i'm": "I am", "i've": "I have", "i'll": "I will", "i'd": "I would",
    "we're": "we are", "we've": "we have", "we'll": "we will", "we'd": "we would",
    "they're": "they are", "they've": "they have",
    "they'll": "they will", "they'd": "they would",
    "you're": "you are", "you've": "you have",
    "you'll": "you will", "you'd": "you would",
    "let's": "let us", "ain't": "is not",
}


def check_contractions(doc: Doc, context: AnalysisContext) -> list[Finding]:
    """STE prohibits contractions — use the full form."""
    findings: list[Finding] = []
    text = context.text
    for match in _CONTRACTION_PATTERN.finditer(text):
        contraction = match.group(0)
        expansion = _CONTRACTION_EXPANSIONS.get(contraction.lower(), contraction)
        if contraction[0].isupper() and not expansion[0].isupper():
            expansion = expansion[0].upper() + expansion[1:]
        findings.append(
            Finding(
                rule_id=RULE_CONTRACTION,
                severity=Severity.WARNING,
                message=f"Contraction '{contraction}' is not permitted in STE; use '{expansion}'.",
                start=match.start(),
                end=match.end(),
                sentence=None,
                evidence={"rule_ref": "Rule 1.5", "contraction": contraction},
                suggestions=[
                    Suggestion(replacement=expansion, confidence=0.95, automatic=True),
                ],
            )
        )
    return findings

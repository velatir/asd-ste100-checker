"""Shared spaCy sentence helpers for rule modules."""

from __future__ import annotations

from spacy.tokens import Doc, Span, Token


def sentence_index(doc: Doc, sent: Span) -> int:
    """1-based sentence index of ``sent`` within ``doc``."""
    for i, candidate in enumerate(doc.sents, start=1):
        if candidate.start == sent.start and candidate.end == sent.end:
            return i
    return 1


def sentence_index_for_token(token: Token) -> int:
    """1-based sentence index for a token."""
    doc = token.doc
    for i, sent in enumerate(doc.sents, start=1):
        if sent.start <= token.i < sent.end:
            return i
    return 1


def content_tokens(sent: Span) -> list[Token]:
    """Non-space, non-punct tokens in a sentence."""
    return [t for t in sent if not t.is_space and not t.is_punct]


def is_imperative_span(sent: Span) -> bool:
    """Heuristic: sentence looks like an imperative instruction."""
    tokens = content_tokens(sent)
    if not tokens:
        return False
    first = tokens[0]
    if first.pos_ == "VERB" and first.tag_ in {"VB", "VBP"}:
        return True
    root = sent.root
    if root.pos_ == "VERB" and root.tag_ in {"VB", "VBP"} and root.dep_ == "ROOT":
        has_nsubj = any(t.dep_ in {"nsubj", "nsubjpass"} for t in sent)
        return not has_nsubj
    return False


def is_heading_or_label(sent: Span) -> bool:
    """Skip ALL-CAPS headings and lone labels."""
    raw = sent.text.strip()
    if not raw:
        return True
    letters = [c for c in raw if c.isalpha()]
    if letters and all(c.isupper() for c in letters) and len(raw.split()) <= 5:
        return True
    tokens = content_tokens(sent)
    if len(tokens) == 1 and tokens[0].pos_ in {"NOUN", "PROPN"} and tokens[0].text.isupper():
        return True
    return False


def is_fragment(sent: Span) -> bool:
    """Heuristic for fragment-like / low-confidence spans."""
    tokens = content_tokens(sent)
    if len(tokens) <= 1:
        return True
    if not any(t.pos_ in {"VERB", "AUX"} for t in tokens):
        return True
    # Bare list number sentence produced by spaCy ("1.")
    if all(t.tag_ == "LS" or t.is_punct or t.is_space for t in sent):
        return True
    return False


def is_non_prose(sent: Span) -> bool:
    """True for headings, labels, and fragments — skip these in prose checks."""
    return is_heading_or_label(sent) or is_fragment(sent)

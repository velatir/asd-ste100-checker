"""Tier-3 semantic heuristics: pronouns, topic sentence, POS mismatch."""

from __future__ import annotations

from typing import Never

from spacy.tokens import Doc, Span, Token

from ste100.core.schema import Finding, Severity, Suggestion, TextType, WordStatus
from ste100.rules.context import AnalysisContext
from ste100.rules.spacy_util import (
    content_tokens,
    is_fragment,
    is_heading_or_label,
    sentence_index,
)

RULE_PRONOUN = "STE-PRONOUN-AMBIG"
RULE_TOPIC = "STE-TOPIC-SENTENCE"
RULE_POS = "STE-POS-MISMATCH"

_SINGULAR_PRONOUNS = frozenset({"it", "this"})
_PLURAL_PRONOUNS = frozenset({"these", "those", "they"})
_TARGET_PRONOUNS = _SINGULAR_PRONOUNS | _PLURAL_PRONOUNS

_COORD_STARTERS = frozenset({"and", "but", "or", "nor", "yet", "so"})
_DUMMY_IT_PREDICATES = frozenset(
    {"important", "necessary", "essential", "recommended"}
)
_META_OPENERS = frozenset(
    {
        "note",
        "notice",
        "remember",
        "important",
        "warning",
        "caution",
        "tip",
        "overview",
        "introduction",
        "summary",
        "section",
        "chapter",
        "paragraph",
    }
)

_SPACY_TO_COARSE = {
    "VERB": "verb",
    "AUX": "verb",
    "NOUN": "noun",
    "PROPN": "noun",
    "ADJ": "adjective",
}

_DICT_POS_ALIASES = {
    "verb": "verb",
    "v": "verb",
    "noun": "noun",
    "n": "noun",
    "adjective": "adjective",
    "adj": "adjective",
    "a": "adjective",
}

# Coarse conflicts we report (plan-locked).
_CONFLICT_PAIRS = frozenset(
    {
        frozenset({"verb", "noun"}),
        frozenset({"adjective", "noun"}),
    }
)

_SKIP_STATUSES = frozenset(
    {
        WordStatus.UNAPPROVED,
        WordStatus.FORBIDDEN,
        WordStatus.NOT_APPROVED_TECHNICAL_VERB,
        WordStatus.TECHNICAL_NOUN,
        WordStatus.TECHNICAL_VERB,
    }
)


def _normalize_dict_pos(raw: str | None) -> str | None:
    if not raw:
        return None
    key = raw.strip().lower()
    return _DICT_POS_ALIASES.get(key)


def _spacy_coarse(token: Token) -> str | None:
    return _SPACY_TO_COARSE.get(token.pos_)


def _is_plural_noun(token: Token) -> bool:
    if token.tag_ in {"NNS", "NNPS"}:
        return True
    if token.pos_ in {"NOUN", "PROPN"} and token.morph.get("Number") == ["Plur"]:
        return True
    return False


def _is_coordinated_plural(token: Token) -> bool:
    """True when a singular noun is coordinated (A and B → plural antecedent)."""
    if any(c.dep_ == "cc" for c in token.children):
        return True
    if token.dep_ == "conj":
        return True
    return False


def _core_noun_candidates(sent: Span, *, plural: bool) -> list[Token]:
    """Core-argument nouns that could antecede a pronoun of the given number."""
    out: list[Token] = []
    for token in sent:
        if token.pos_ not in {"NOUN", "PROPN"}:
            continue
        if token.dep_ not in {"nsubj", "nsubjpass", "dobj", "attr", "pobj", "appos"}:
            continue
        if token.dep_ == "compound":
            continue
        is_pl = _is_plural_noun(token) or _is_coordinated_plural(token)
        if plural == is_pl:
            out.append(token)
    return out


def _subject_candidates(sent: Span, *, plural: bool) -> list[Token]:
    """Subject nouns only — preferred clear antecedents for it/they."""
    out: list[Token] = []
    for token in sent:
        if token.pos_ not in {"NOUN", "PROPN"}:
            continue
        if token.dep_ not in {"nsubj", "nsubjpass"}:
            continue
        is_pl = _is_plural_noun(token) or _is_coordinated_plural(token)
        if plural == is_pl:
            out.append(token)
    return out


def _pronoun_number(lemma: str) -> bool | None:
    """Return True if plural, False if singular, None if unknown."""
    if lemma in _PLURAL_PRONOUNS:
        return True
    if lemma in _SINGULAR_PRONOUNS:
        return False
    return None


def check_pronoun_ambiguity(doc: Doc, context: AnalysisContext) -> list[Finding]:
    """Flag ambiguous it/this/these/those/they (WARNING; both text types).

    Conservative: flag when the prior sentence has no clear same-number noun
    antecedent, or has multiple same-number noun candidates.
    A single matching subject in the prior sentence is treated as clear.
    """
    text_type = context.text_type
    if text_type is TextType.PROCEDURE:
        resolved = TextType.PROCEDURE
    elif text_type is TextType.DESCRIPTION:
        resolved = TextType.DESCRIPTION
    else:
        _exhaustive: Never = text_type
        raise AssertionError(f"Unhandled TextType: {_exhaustive}")

    sents = list(doc.sents)
    findings: list[Finding] = []
    for sent_i, sent in enumerate(sents):
        if is_heading_or_label(sent):
            continue
        for token in sent:
            lemma = token.lemma_.lower()
            surface = token.text.lower()
            key = lemma if lemma in _TARGET_PRONOUNS else surface
            if key not in _TARGET_PRONOUNS:
                continue
            # Focus on subject / core argument uses (conservative).
            if token.pos_ not in {"PRON", "DET"}:
                continue
            if token.dep_ not in {"nsubj", "nsubjpass", "expl", "dobj", "pobj", "attr"}:
                continue

            # Expletive / "It is important…" — topic rule handles this.
            if key == "it" and (
                token.dep_ == "expl"
                or any(t.lemma_.lower() in _DUMMY_IT_PREDICATES for t in sent)
            ):
                continue

            plural = _pronoun_number(key)
            if plural is None:
                continue

            if sent_i == 0:
                cue = "no_prior_sentence"
                candidates: list[str] = []
            else:
                prior = sents[sent_i - 1]
                subjects = _subject_candidates(prior, plural=plural)
                if len(subjects) == 1:
                    # Clear subject antecedent — do not flag.
                    continue
                nouns = _core_noun_candidates(prior, plural=plural)
                candidates = [t.text for t in nouns]
                if len(subjects) == 0 and len(nouns) == 1:
                    continue
                if len(nouns) == 0 and len(subjects) == 0:
                    cue = "no_clear_antecedent"
                else:
                    cue = "multiple_antecedents"
                    candidates = [t.text for t in (subjects or nouns)]

            conf = 0.7 if cue == "multiple_antecedents" else 0.6
            findings.append(
                Finding(
                    rule_id=RULE_PRONOUN,
                    severity=Severity.WARNING,
                    message=(
                        f"Pronoun '{token.text}' may be ambiguous; name the noun "
                        "instead of using a vague pronoun."
                    ),
                    start=token.idx,
                    end=token.idx + len(token.text),
                    sentence=sentence_index(doc, sent),
                    evidence={
                        "confidence": conf,
                        "parse_cue": cue,
                        "text_type": resolved.value,
                        "rule_ref": "STE pronoun clarity",
                        "pronoun": token.text,
                        "candidates": candidates,
                    },
                    suggestions=[
                        Suggestion(
                            replacement=f"Name the noun instead of '{token.text}'",
                            confidence=conf,
                            automatic=False,
                        )
                    ],
                )
            )
    return findings


def _first_content_sentence(doc: Doc) -> Span | None:
    for sent in doc.sents:
        if is_heading_or_label(sent):
            continue
        if not content_tokens(sent):
            continue
        return sent
    return None


def _starts_with_pronoun_or_demonstrative(sent: Span) -> bool:
    tokens = content_tokens(sent)
    if not tokens:
        return False
    first = tokens[0]
    lemma = first.lemma_.lower()
    surface = first.text.lower()
    if lemma in _TARGET_PRONOUNS or surface in _TARGET_PRONOUNS:
        return True
    if first.pos_ == "PRON":
        return True
    if first.tag_ == "DT" and surface in {"this", "these", "those", "that"}:
        return True
    return False


def _is_pure_coordination(sent: Span) -> bool:
    tokens = content_tokens(sent)
    if not tokens:
        return False
    return tokens[0].text.lower() in _COORD_STARTERS


def _is_meta_comment_without_topic(sent: Span) -> bool:
    """Meta openers like 'Note that...' / 'This section...' without a topic noun subject."""
    tokens = content_tokens(sent)
    if not tokens:
        return False
    first = tokens[0]
    first_l = first.lemma_.lower()
    surface = first.text.lower()

    # "It is important / necessary / recommended ..."
    if surface == "it" and len(tokens) >= 2:
        if any(t.lemma_.lower() in _DUMMY_IT_PREDICATES for t in tokens[:6]):
            return True

    # "Note that...", "Remember that...", "Warning: ..."
    if first_l in _META_OPENERS or surface in _META_OPENERS:
        # ALL-CAPS WARNING/CAUTION labels glued to the next line by spaCy.
        if first.text.isupper() and any(
            t.dep_ in {"nsubj", "nsubjpass"}
            and t.pos_ in {"NOUN", "PROPN"}
            and t.i > first.i
            for t in sent
        ):
            return False
        return True

    # "This section / chapter / paragraph ..."
    if surface in {"this", "these"} and len(tokens) >= 2:
        if tokens[1].lemma_.lower() in _META_OPENERS:
            return True
    return False


def _topic_fragment(sent: Span) -> bool:
    """Structural fragment for topic checks (avoid spaCy verb/noun mis-tags)."""
    tokens = content_tokens(sent)
    if len(tokens) <= 2:
        return True
    has_noun_subj = any(
        t.dep_ in {"nsubj", "nsubjpass"} and t.pos_ in {"NOUN", "PROPN"} for t in sent
    )
    if has_noun_subj:
        return False
    if is_fragment(sent):
        return True
    return False


def check_topic_sentence(doc: Doc, context: AnalysisContext) -> list[Finding]:
    """Flag weak opening topic sentences in descriptions only (WARNING)."""
    if context.text_type is TextType.PROCEDURE:
        return []
    if context.text_type is not TextType.DESCRIPTION:
        _exhaustive: Never = context.text_type
        raise AssertionError(f"Unhandled TextType: {_exhaustive}")

    sent = _first_content_sentence(doc)
    if sent is None:
        return []

    cues: list[str] = []
    if _starts_with_pronoun_or_demonstrative(sent):
        cues.append("pronoun_or_demonstrative_start")
    if _topic_fragment(sent):
        cues.append("fragment")
    if _is_pure_coordination(sent):
        cues.append("pure_coordination")
    if _is_meta_comment_without_topic(sent):
        cues.append("meta_comment")

    if not cues:
        return []

    conf = 0.65
    start = sent.start_char
    end = sent.end_char
    return [
        Finding(
            rule_id=RULE_TOPIC,
            severity=Severity.WARNING,
            message=(
                "The first sentence should state the topic clearly; this opener "
                "looks weak (pronoun/demonstrative, fragment, coordination, or "
                "meta-comment)."
            ),
            start=start,
            end=end,
            sentence=sentence_index(doc, sent),
            evidence={
                "confidence": conf,
                "parse_cue": "+".join(cues),
                "text_type": TextType.DESCRIPTION.value,
                "rule_ref": "STE topic sentence",
            },
            suggestions=[
                Suggestion(
                    replacement="Put the topic noun in the first sentence",
                    confidence=conf,
                    automatic=False,
                )
            ],
        )
    ]


def _has_determiner(token: Token) -> bool:
    return any(c.dep_ == "det" for c in token.children)


def _pos_high_confidence(token: Token, observed: str, approved: str) -> bool:
    """High-confidence when the clash is a clear ROOT / verbal or nominal use."""
    if observed == "verb" and approved == "noun":
        if token.dep_ == "ROOT" and token.tag_ in {"VB", "VBD", "VBZ", "VBP", "VBN", "VBG"}:
            return True
        if token.pos_ == "VERB" and token.dep_ in {"ROOT", "xcomp", "ccomp", "advcl"}:
            return True
    if observed == "noun" and approved == "verb":
        # Require determiner / clear NP use — avoid 3sg verb mis-tagged as NNS.
        if not _has_determiner(token) and token.tag_ in {"NNS", "NNPS"}:
            return False
        if token.pos_ in {"NOUN", "PROPN"} and _has_determiner(token):
            if token.dep_ in {"nsubj", "nsubjpass", "dobj", "pobj", "attr", "ROOT"}:
                return True
        return False
    if observed == "noun" and approved == "adjective":
        if token.pos_ in {"NOUN", "PROPN"} and token.dep_ in {
            "nsubj",
            "dobj",
            "pobj",
            "attr",
            "ROOT",
        }:
            return True
    if observed == "adjective" and approved == "noun":
        if token.pos_ == "ADJ" and token.dep_ in {"amod", "acomp", "ROOT"}:
            return True
    return False


def _is_likely_verb_mistagged_as_noun(token: Token, approved: str) -> bool:
    """Skip common spaCy sm mis-tags of 3sg verbs (e.g. 'supplies' as NNS)."""
    if approved != "verb":
        return False
    if token.pos_ not in {"NOUN", "PROPN"}:
        return False
    if _has_determiner(token):
        return False
    # Bare finite-looking form without NP cues.
    if token.tag_ in {"NNS", "NNPS"} and token.dep_ in {"ROOT", "ccomp", "xcomp"}:
        return True
    return False


def check_pos_mismatch(doc: Doc, context: AnalysisContext) -> list[Finding]:
    """Flag approved-dictionary POS clashes (verb↔noun / adj↔noun).

    Skips unapproved vocabulary (owned by Tier-1) and TN/TV seeds.
    Default WARNING; ERROR only for high-confidence clashes.
    """
    text_type = context.text_type
    if text_type is TextType.PROCEDURE:
        resolved = TextType.PROCEDURE
    elif text_type is TextType.DESCRIPTION:
        resolved = TextType.DESCRIPTION
    else:
        _exhaustive: Never = text_type
        raise AssertionError(f"Unhandled TextType: {_exhaustive}")

    engine = context.dictionary
    findings: list[Finding] = []
    seen: set[int] = set()

    for sent in doc.sents:
        if is_heading_or_label(sent):
            continue
        fragment = is_fragment(sent)
        for token in sent:
            if token.i in seen:
                continue
            if token.is_space or token.is_punct or token.tag_ == "LS":
                continue
            observed = _spacy_coarse(token)
            if observed is None:
                continue

            record = engine.lookup(token.text)
            if record is None:
                # Try lemma for inflected forms already indexed via inflections.
                record = engine.lookup(token.lemma_)
            if record is None:
                continue
            if record.status in _SKIP_STATUSES:
                continue
            if record.status is not WordStatus.APPROVED:
                continue

            approved = _normalize_dict_pos(record.part_of_speech)
            if approved is None or approved == observed:
                continue
            if frozenset({approved, observed}) not in _CONFLICT_PAIRS:
                continue
            if _is_likely_verb_mistagged_as_noun(token, approved):
                continue

            high = _pos_high_confidence(token, observed, approved) and not fragment
            sev = Severity.ERROR if high else Severity.WARNING
            conf = 0.9 if high else (0.5 if fragment else 0.65)
            findings.append(
                Finding(
                    rule_id=RULE_POS,
                    severity=sev,
                    message=(
                        f"Word '{token.text}' is approved as {approved} but appears "
                        f"used as {observed}; use the approved part of speech "
                        "(or an approved alternative)."
                    ),
                    start=token.idx,
                    end=token.idx + len(token.text),
                    sentence=sentence_index(doc, sent),
                    evidence={
                        "confidence": conf,
                        "parse_cue": f"dict:{approved}|spacy:{observed}|{token.tag_}/{token.dep_}",
                        "text_type": resolved.value,
                        "rule_ref": "Rule 1.2 / 1.3",
                        "word": token.text,
                        "approved_pos": approved,
                        "observed_pos": observed,
                        "status": record.status.value,
                    },
                    suggestions=[
                        Suggestion(
                            replacement="Use the approved part of speech",
                            confidence=conf,
                            automatic=False,
                        )
                    ],
                )
            )
            seen.add(token.i)
    return findings


def check_semantic(doc: Doc, context: AnalysisContext) -> list[Finding]:
    """Run all Tier-3 semantic checks (convenience aggregator)."""
    findings: list[Finding] = []
    findings.extend(check_pronoun_ambiguity(doc, context))
    findings.extend(check_topic_sentence(doc, context))
    findings.extend(check_pos_mismatch(doc, context))
    return findings

"""Tier-2 deterministic syntax rules: voice, mood, verb forms, noun clusters."""

from __future__ import annotations

import re
from typing import Never

from spacy.tokens import Doc, Span, Token

from ste100.core.schema import Finding, Severity, Suggestion, TextType
from ste100.rules.context import AnalysisContext
from ste100.rules.spacy_util import (
    content_tokens,
    is_fragment,
    is_heading_or_label,
    is_non_prose,
    sentence_index,
)

RULE_PASSIVE = "STE-PASSIVE"
RULE_IMPERATIVE = "STE-IMPERATIVE"
RULE_VERB_FORM = "STE-VERB-FORM"
RULE_NOUN_CLUSTER = "STE-NOUN-CLUSTER"

MAX_NOUN_CLUSTER = 3

_NUMBERED_PREFIX = re.compile(
    r"^\s*(?:step\s+)?\d+[.)]\s+",
    re.IGNORECASE,
)
_LIST_MARKER_PREFIX = re.compile(r"^\s*[-*•]\s+")
_DEGREE_ADVERBS = frozenset(
    {
        "fully",
        "completely",
        "partially",
        "totally",
        "already",
        "still",
        "nearly",
        "almost",
    }
)
_BE_LEMMAS = frozenset({"be", "am", "is", "are", "was", "were", "been", "being"})
_HAVE_LEMMAS = frozenset({"have", "has", "had"})
_LABEL_SUBJ = frozenset({"step", "item", "section", "figure", "note", "table"})


def _line_prefix(text: str, sent: Span) -> str:
    line_start = text.rfind("\n", 0, sent.start_char) + 1
    return text[line_start : sent.end_char]


def is_numbered_or_list_step(text: str, sent: Span) -> bool:
    prefix = _line_prefix(text, sent)
    if _NUMBERED_PREFIX.match(prefix) or _NUMBERED_PREFIX.match(sent.text):
        return True
    if _LIST_MARKER_PREFIX.match(prefix) or _LIST_MARKER_PREFIX.match(sent.text):
        return True
    return False


def confidence_for(*, high: bool, fragment: bool) -> float:
    if fragment:
        return 0.45
    if high:
        return 0.9
    return 0.65


def _severity(high: bool, fragment: bool) -> Severity:
    if high and not fragment:
        return Severity.ERROR
    return Severity.WARNING


def _is_adjective_participle(token: Token) -> bool:
    """Rule 3.3: past participle used as adjective — not verbal passive."""
    if token.tag_ != "VBN" and token.pos_ != "ADJ":
        return False
    if token.dep_ in {"amod", "acomp"}:
        return True
    if token.pos_ == "ADJ":
        return True

    children = list(token.children)
    has_agent = any(c.dep_ == "agent" for c in children)
    if has_agent:
        return False
    has_modal = any(c.dep_ == "aux" and c.tag_ == "MD" for c in children)
    if has_modal:
        return False
    # Progressive passive ("is being tested") is verbal.
    if any(c.dep_ == "auxpass" and c.lemma_ == "be" and c.tag_ == "VBG" for c in children):
        return False
    # "is to be installed" — verbal complex construction.
    to_be = (
        token.dep_ in {"xcomp", "ccomp"}
        and any(c.dep_ == "auxpass" for c in children)
        and any(c.dep_ == "aux" and c.lemma_ == "to" for c in children)
    )
    if to_be:
        return False

    degree = any(
        c.dep_ == "advmod" and c.text.lower() in _DEGREE_ADVERBS for c in children
    )
    if degree:
        return True

    has_auxpass = any(c.dep_ == "auxpass" for c in children)
    has_nsubjpass = any(c.dep_ == "nsubjpass" for c in children)
    # Predicative adjective often mis-tagged as passive without nsubjpass on the VBN
    # (e.g. "Make sure the panel is closed.").
    if has_auxpass and not has_nsubjpass:
        return True
    return False


def _passive_verbs(sent: Span) -> list[tuple[Token, str, bool]]:
    """Return (verb, parse_cue, high_confidence) for verbal passives."""
    hits: list[tuple[Token, str, bool]] = []
    seen: set[int] = set()
    for token in sent:
        if token.i in seen:
            continue
        if token.tag_ != "VBN" and not (
            token.pos_ == "VERB" and any(c.dep_ == "auxpass" for c in token.children)
        ):
            continue
        if _is_adjective_participle(token):
            continue

        children = list(token.children)
        has_auxpass = any(c.dep_ == "auxpass" for c in children)
        has_nsubjpass = any(c.dep_ == "nsubjpass" for c in children)
        has_agent = any(c.dep_ == "agent" for c in children)
        has_modal = any(c.dep_ == "aux" and c.tag_ == "MD" for c in children)
        being = any(c.dep_ == "auxpass" and c.tag_ == "VBG" for c in children)
        to_be = (
            token.dep_ in {"xcomp", "ccomp"}
            and has_auxpass
            and any(c.dep_ == "aux" and c.lemma_ == "to" for c in children)
        )

        # Require verbal reading cues beyond a bare be+VBN state.
        if not (has_nsubjpass or has_agent or has_modal or being or to_be):
            continue
        if not (has_auxpass or has_nsubjpass):
            continue

        cues: list[str] = []
        if has_auxpass:
            cues.append("auxpass")
        if has_nsubjpass:
            cues.append("nsubjpass")
        if has_agent:
            cues.append("agent")
        if has_modal:
            cues.append("modal")
        if being:
            cues.append("progressive_passive")
        if to_be:
            cues.append("to_be_passive")

        high = bool(
            has_agent
            or has_modal
            or being
            or to_be
            or (has_auxpass and has_nsubjpass and token.dep_ == "ROOT")
        )

        hits.append((token, "+".join(cues) or "passive", high))
        seen.add(token.i)
    return hits


def check_passive(doc: Doc, context: AnalysisContext) -> list[Finding]:
    """Flag verbal passive voice in procedures (Rule 3.6).

    Descriptive text: skip (prefer skip when agent unknown / descriptive).
    """
    if context.text_type is TextType.DESCRIPTION:
        return []
    if context.text_type is not TextType.PROCEDURE:
        _exhaustive: Never = context.text_type
        raise AssertionError(f"Unhandled TextType: {_exhaustive}")

    findings: list[Finding] = []
    for sent in doc.sents:
        if is_non_prose(sent):
            continue
        step = is_numbered_or_list_step(context.text, sent)
        for verb, cue, high_base in _passive_verbs(sent):
            # High confidence when step context or strong verbal cues.
            high = high_base or step
            fragment = is_fragment(sent)
            # Soften unnumbered, agentless state-like passives.
            if not step and not high_base:
                # Unnumbered procedure declarative passive → warning only
                high = False
            sev = _severity(high, fragment)
            conf = confidence_for(high=high, fragment=fragment)
            findings.append(
                Finding(
                    rule_id=RULE_PASSIVE,
                    severity=sev,
                    message=(
                        "Prefer active voice in procedures; rewrite this passive "
                        f"construction ('{verb.text}') (Rule 3.6)."
                    ),
                    start=verb.idx,
                    end=verb.idx + len(verb.text),
                    sentence=sentence_index(doc, sent),
                    evidence={
                        "confidence": conf,
                        "parse_cue": cue,
                        "text_type": context.text_type.value,
                        "rule_ref": "Rule 3.6",
                        "step_context": step,
                    },
                    suggestions=[
                        Suggestion(
                            replacement="Rewrite in active voice / imperative",
                            confidence=conf,
                            automatic=False,
                        )
                    ],
                )
            )
    return findings


def _is_imperative_sentence(sent: Span) -> bool:
    tokens = content_tokens(sent)
    if not tokens:
        return False
    root = sent.root

    def _has_subject(verb: Token) -> bool:
        for t in sent:
            if t.dep_ not in {"nsubj", "nsubjpass"} or t.head.i != verb.i:
                continue
            # Ignore "Step 1:" / list markers mis-tagged as nsubj.
            if t.text.lower() in _LABEL_SUBJ or t.tag_ == "LS":
                continue
            return True
        return False

    # "Do not open..." / "Do the test..."
    if root.pos_ == "VERB" and root.tag_ in {"VB", "VBP"} and not _has_subject(root):
        return True
    # First content word is base-form verb (imperative)
    for first in tokens:
        if first.tag_ == "LS":
            continue
        if first.pos_ == "VERB" and first.tag_ in {"VB", "VBP"} and not _has_subject(first):
            return True
        break
    # Conditional-first: "... , set the switch"
    for token in tokens:
        if (
            token.dep_ == "ROOT"
            and token.pos_ == "VERB"
            and token.tag_ in {"VB", "VBP"}
            and not _has_subject(token)
        ):
            return True
    return False


def _looks_like_instruction_sentence(sent: Span) -> bool:
    """Declarative / modal lines that still read as work steps."""
    root = sent.root
    if root.pos_ == "VERB" and root.tag_ in {"VBZ", "VBD", "VBN", "VBG", "MD"}:
        return True
    if any(t.tag_ == "MD" for t in sent):
        return True
    if any(c.dep_ == "auxpass" for t in sent for c in t.children):
        return True
    return root.pos_ in {"VERB", "AUX"}


def check_imperative(doc: Doc, context: AnalysisContext) -> list[Finding]:
    """Procedural steps should use imperative mood (Rule 5.3)."""
    if context.text_type is TextType.DESCRIPTION:
        return []
    if context.text_type is not TextType.PROCEDURE:
        _exhaustive: Never = context.text_type
        raise AssertionError(f"Unhandled TextType: {_exhaustive}")

    findings: list[Finding] = []
    for sent in doc.sents:
        if is_non_prose(sent):
            continue
        if _is_imperative_sentence(sent):
            continue
        step = is_numbered_or_list_step(context.text, sent)
        if not step and not _looks_like_instruction_sentence(sent):
            continue
        # Skip pure descriptive asides inside procedures when unnumbered
        # and clearly stative ("The system is ready.") without modal/passive.
        if not step:
            root = sent.root
            if root.lemma_ in _BE_LEMMAS and not any(t.tag_ == "MD" for t in sent):
                if not any(c.dep_ == "auxpass" for t in sent for c in t.children):
                    continue

        high = step
        fragment = is_fragment(sent)
        sev = _severity(high, fragment)
        conf = confidence_for(high=high, fragment=fragment)
        root = sent.root
        findings.append(
            Finding(
                rule_id=RULE_IMPERATIVE,
                severity=sev,
                message=(
                    "Write procedural instructions in the imperative (command) "
                    f"form; found non-imperative root '{root.text}' (Rule 5.3)."
                ),
                start=root.idx,
                end=root.idx + len(root.text),
                sentence=sentence_index(doc, sent),
                evidence={
                    "confidence": conf,
                    "parse_cue": f"root:{root.tag_}/{root.dep_}",
                    "text_type": context.text_type.value,
                    "rule_ref": "Rule 5.3",
                    "step_context": step,
                },
                suggestions=[
                    Suggestion(
                        replacement="Rewrite as an imperative instruction",
                        confidence=conf,
                        automatic=False,
                    )
                ],
            )
        )
    return findings


def _verb_form_hits(sent: Span) -> list[tuple[Token, str, bool]]:
    hits: list[tuple[Token, str, bool]] = []
    seen: set[int] = set()

    for token in sent:
        if token.i in seen:
            continue

        # Progressive as main verb: (be) + VBG with nsubj, not noun/amod.
        if token.tag_ == "VBG" and token.pos_ == "VERB":
            if token.dep_ in {"amod", "compound", "acl"}:
                continue
            # Technical noun -ing as ROOT noun already excluded by pos VERB
            has_be_aux = any(
                c.dep_ == "aux" and c.lemma_ in _BE_LEMMAS for c in token.children
            )
            if token.dep_ == "ROOT" or has_be_aux:
                hits.append((token, "progressive:VBG", True))
                seen.add(token.i)
                continue

        # Perfect: have/has/had + VBN as main verb
        if token.tag_ == "VBN" and token.pos_ == "VERB":
            have_aux = [
                c
                for c in token.children
                if c.dep_ == "aux" and c.lemma_ in _HAVE_LEMMAS
            ]
            if have_aux and not _is_adjective_participle(token):
                # Exclude pure passive (auxpass) handled elsewhere unless also perfect
                hits.append((token, "perfect:have+VBN", True))
                seen.add(token.i)
                continue

        # Modal + passive stacks / "is to be installed"
        if token.tag_ == "VBN" and token.pos_ == "VERB":
            has_auxpass = any(c.dep_ == "auxpass" for c in token.children)
            has_modal = any(c.dep_ == "aux" and c.tag_ == "MD" for c in token.children)
            if has_auxpass and has_modal:
                hits.append((token, "modal+passive", True))
                seen.add(token.i)
                continue
            if has_auxpass and token.dep_ in {"xcomp", "ccomp"}:
                hits.append((token, "be+to+passive", True))
                seen.add(token.i)
                continue

    return hits


def check_verb_form(doc: Doc, context: AnalysisContext) -> list[Finding]:
    """Flag disallowed / complex verb constructions (Rules 3.2 / 3.4)."""
    text_type = context.text_type
    if text_type is TextType.PROCEDURE:
        resolved = TextType.PROCEDURE
    elif text_type is TextType.DESCRIPTION:
        resolved = TextType.DESCRIPTION
    else:
        _exhaustive: Never = text_type
        raise AssertionError(f"Unhandled TextType: {_exhaustive}")

    findings: list[Finding] = []
    for sent in doc.sents:
        if is_non_prose(sent):
            continue
        for verb, cue, high in _verb_form_hits(sent):
            fragment = is_fragment(sent)
            sev = _severity(high, fragment)
            conf = confidence_for(high=high, fragment=fragment)
            findings.append(
                Finding(
                    rule_id=RULE_VERB_FORM,
                    severity=sev,
                    message=(
                        "Use only approved STE verb forms/tenses; avoid progressive, "
                        f"perfect, or complex auxiliary stacks ('{verb.text}') "
                        "(Rules 3.2 / 3.4)."
                    ),
                    start=verb.idx,
                    end=verb.idx + len(verb.text),
                    sentence=sentence_index(doc, sent),
                    evidence={
                        "confidence": conf,
                        "parse_cue": cue,
                        "text_type": resolved.value,
                        "rule_ref": "Rule 3.2 / 3.4",
                    },
                    suggestions=[
                        Suggestion(
                            replacement=(
                                "Rewrite with an approved simple tense or imperative"
                            ),
                            confidence=conf,
                            automatic=False,
                        )
                    ],
                )
            )
    return findings


def _noun_clusters(sent: Span) -> list[tuple[list[Token], bool]]:
    """Find runs of consecutive NOUN/PROPN tokens; flag length >= 4."""
    clusters: list[tuple[list[Token], bool]] = []
    run: list[Token] = []

    def _flush() -> None:
        nonlocal run
        if len(run) >= MAX_NOUN_CLUSTER + 1:
            clusters.append((list(run), True))
        run = []

    for token in sent:
        if token.is_space or token.is_punct:
            _flush()
            continue
        if token.pos_ in {"NOUN", "PROPN"}:
            run.append(token)
        else:
            _flush()
    _flush()
    return clusters


def check_noun_cluster(doc: Doc, context: AnalysisContext) -> list[Finding]:
    """Flag multi-word noun clusters longer than three words (Rule 2.1)."""
    text_type = context.text_type
    if text_type is TextType.PROCEDURE:
        resolved = TextType.PROCEDURE
    elif text_type is TextType.DESCRIPTION:
        resolved = TextType.DESCRIPTION
    else:
        _exhaustive: Never = text_type
        raise AssertionError(f"Unhandled TextType: {_exhaustive}")

    findings: list[Finding] = []
    for sent in doc.sents:
        if is_heading_or_label(sent):
            continue
        for cluster, high in _noun_clusters(sent):
            fragment = is_fragment(sent) and len(cluster) < 5
            # Bare noun-phrase lines (titles) with 4+ nouns are still real hits.
            if len(content_tokens(sent)) == len(cluster):
                fragment = False
            sev = _severity(high, fragment)
            conf = confidence_for(high=high and not fragment, fragment=fragment)
            start = cluster[0].idx
            end = cluster[-1].idx + len(cluster[-1].text)
            phrase = " ".join(t.text for t in cluster)
            findings.append(
                Finding(
                    rule_id=RULE_NOUN_CLUSTER,
                    severity=sev,
                    message=(
                        f"Multi-word noun has {len(cluster)} words "
                        f"('{phrase}'); maximum is {MAX_NOUN_CLUSTER} "
                        "(Rule 2.1)."
                    ),
                    start=start,
                    end=end,
                    sentence=sentence_index(doc, sent),
                    evidence={
                        "confidence": conf,
                        "parse_cue": "noun_run",
                        "text_type": resolved.value,
                        "rule_ref": "Rule 2.1",
                        "cluster_length": len(cluster),
                        "max_allowed": MAX_NOUN_CLUSTER,
                        "cluster": phrase,
                    },
                    suggestions=[
                        Suggestion(
                            replacement=(
                                "Shorten the multi-word noun or rewrite with "
                                "prepositions / hyphens"
                            ),
                            confidence=conf,
                            automatic=False,
                        )
                    ],
                )
            )
    return findings


def check_syntax(doc: Doc, context: AnalysisContext) -> list[Finding]:
    """Run all Tier-2 syntax checks (convenience aggregator)."""
    findings: list[Finding] = []
    findings.extend(check_passive(doc, context))
    findings.extend(check_imperative(doc, context))
    findings.extend(check_verb_form(doc, context))
    findings.extend(check_noun_cluster(doc, context))
    return findings

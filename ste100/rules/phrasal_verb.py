"""Phrasal verb detection (STE Rule 9.3).

STE prohibits phrasal verbs because the combination creates a meaning the
individual words do not predict. A non-native reader or an LLM parsing
the text cannot reliably distinguish the idiomatic reading from the
literal one.

Detection strategy:
  1. spaCy particle dependencies (dep_ == "prt") — catches "kick out",
     "set up", "shut down" etc.
  2. A curated verb+preposition map for combinations where the preposition
     is tagged as prep rather than prt but the meaning is still idiomatic.
"""

from __future__ import annotations

from spacy.tokens import Doc, Token

from ste100.core.schema import Finding, Severity, Suggestion
from ste100.rules.context import AnalysisContext
from ste100.rules.spacy_util import is_non_prose, sentence_index

RULE_PHRASAL_VERB = "STE-PHRASAL-VERB"

_PHRASAL_VERBS: dict[tuple[str, str], str] = {
    ("kick", "out"): "remove",
    ("lock", "out"): "deny access to",
    ("spin", "up"): "start",
    ("set", "up"): "configure",
    ("carry", "out"): "execute",
    ("look", "into"): "investigate",
    ("bring", "up"): "raise",
    ("give", "up"): "stop",
    ("put", "out"): "extinguish",
    ("take", "off"): "remove",
    ("shut", "down"): "stop",
    ("turn", "on"): "activate",
    ("turn", "off"): "deactivate",
    ("find", "out"): "determine",
    ("figure", "out"): "determine",
    ("point", "out"): "identify",
    ("go", "through"): "review",
    ("pick", "up"): "collect",
    ("make", "up"): "compose",
    ("take", "over"): "replace",
    ("break", "down"): "separate",
    ("hand", "off"): "deliver",
    ("hand", "over"): "transfer",
    ("stand", "up"): "deploy",
    ("come", "up"): "occur",
    ("get", "rid"): "remove",
    ("phase", "out"): "remove gradually",
    ("switch", "over"): "change",
    ("log", "in"): "authenticate",
    ("log", "out"): "end the session",
    ("sign", "in"): "authenticate",
    ("sign", "out"): "end the session",
    ("back", "up"): "copy",
    ("opt", "in"): "enable",
    ("opt", "out"): "disable",
}

_ALLOWED_DOMAIN_TERMS: frozenset[tuple[str, str]] = frozenset({
    ("roll", "back"),
    ("fall", "back"),
})


def _find_particle(verb: Token) -> Token | None:
    for child in verb.children:
        if child.dep_ == "prt":
            return child
    return None


def _find_prep_phrasal(verb: Token) -> Token | None:
    for child in verb.children:
        if child.dep_ == "prep" and (verb.lemma_.lower(), child.lemma_.lower()) in _PHRASAL_VERBS:
            return child
    return None


def check_phrasal_verbs(doc: Doc, context: AnalysisContext) -> list[Finding]:
    """Flag phrasal verbs (verb + particle/preposition) per Rule 9.3."""
    findings: list[Finding] = []

    for sent in doc.sents:
        if is_non_prose(sent):
            continue
        for token in sent:
            if token.pos_ not in {"VERB", "AUX"}:
                continue

            particle = _find_particle(token) or _find_prep_phrasal(token)
            if particle is None:
                continue

            verb_lemma = token.lemma_.lower()
            part_text = particle.lemma_.lower()
            key = (verb_lemma, part_text)

            if key in _ALLOWED_DOMAIN_TERMS:
                continue

            replacement = _PHRASAL_VERBS.get(key)
            if replacement is None:
                continue

            start = min(token.idx, particle.idx)
            end = max(token.idx + len(token.text), particle.idx + len(particle.text))
            phrase = f"{token.text} {particle.text}"

            findings.append(
                Finding(
                    rule_id=RULE_PHRASAL_VERB,
                    severity=Severity.WARNING,
                    message=(
                        f"Phrasal verb '{phrase}' creates an idiomatic meaning. "
                        f"Prefer '{replacement}' (Rule 9.3)."
                    ),
                    start=start,
                    end=end,
                    sentence=sentence_index(doc, sent),
                    evidence={
                        "rule_ref": "Rule 9.3",
                        "verb": token.text,
                        "particle": particle.text,
                        "replacement": replacement,
                    },
                    suggestions=[
                        Suggestion(
                            replacement=replacement,
                            confidence=0.7,
                            automatic=False,
                        )
                    ],
                )
            )

    return findings

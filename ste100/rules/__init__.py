"""Tier-1 / Tier-2 / Tier-3 rules and the rule registry."""

from ste100.rules.context import AnalysisContext, CheckFn
from ste100.rules.registry import RULES, RuleRegistration, get_all_checks, get_rule_meta
from ste100.rules.semantic import (
    check_pos_mismatch,
    check_pronoun_ambiguity,
    check_semantic,
    check_topic_sentence,
)
from ste100.rules.sentence import check_one_instruction, check_sentence_length
from ste100.rules.structural import check_units_format
from ste100.rules.syntax import (
    check_imperative,
    check_noun_cluster,
    check_passive,
    check_syntax,
    check_verb_form,
)
from ste100.rules.vocabulary import check_vocabulary

__all__ = [
    "AnalysisContext",
    "CheckFn",
    "RULES",
    "RuleRegistration",
    "check_imperative",
    "check_noun_cluster",
    "check_one_instruction",
    "check_passive",
    "check_pos_mismatch",
    "check_pronoun_ambiguity",
    "check_semantic",
    "check_sentence_length",
    "check_syntax",
    "check_topic_sentence",
    "check_units_format",
    "check_verb_form",
    "check_vocabulary",
    "get_all_checks",
    "get_rule_meta",
]

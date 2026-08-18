"""Authoritative data contract for the ASD-STE100 checker engine.

This module is the single source of truth for the shapes that flow between the
analyzer, the rules, the dictionary engine, the serializers, the CLI, and the
MCP server. All downstream workers MUST code against the models defined here.

Unofficial project. ASD-STE100 is a registered European Union Trade Mark
(No. 017966390); this project is not affiliated with, endorsed by, or sponsored
by ASD and makes no claim of official compliance or certification.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict


class Severity(str, Enum):
    """Severity of a rule violation."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class TextType(str, Enum):
    """Coarse text classification driving which rules apply."""

    AUTO = "auto"
    PROCEDURE = "procedure"
    DESCRIPTION = "description"


class WordStatus(str, Enum):
    """Status of a word in the STE dictionary."""

    APPROVED = "approved"
    UNAPPROVED = "unapproved"
    FORBIDDEN = "forbidden"
    TECHNICAL_NOUN = "technical_noun"
    TECHNICAL_VERB = "technical_verbs"
    NOT_APPROVED_TECHNICAL_VERB = "not_approved_technical_verb"


class Suggestion(BaseModel):
    """A proposed replacement for a flagged span."""

    model_config = ConfigDict(extra="forbid")

    replacement: str
    confidence: float = 0.0
    automatic: bool = False


class Finding(BaseModel):
    """A single rule violation located in the source text."""

    model_config = ConfigDict(extra="forbid")

    rule_id: str
    severity: Severity
    message: str
    start: int
    end: int
    sentence: int | None = None
    evidence: dict = {}
    suggestions: list[Suggestion] = []


class AnalysisResult(BaseModel):
    """The full result of analyzing a text against the STE rules."""

    model_config = ConfigDict(extra="forbid")

    text_type: TextType
    compliant: bool
    findings: list[Finding] = []
    summary: dict = {}
    score: float = 1.0


class DictionaryRecord(BaseModel):
    """A single headword entry in the curated STE dictionary."""

    model_config = ConfigDict(extra="forbid")

    word: str
    part_of_speech: str
    status: WordStatus
    approved_meaning: str | None = None
    inflections: list[str] = []
    alternatives: list[str] = []
    category: str | None = None
    rule_ref: str | None = None
    examples_ste: list[str] = []
    examples_non_ste: list[str] = []
    notes: str | None = None


class RuleMeta(BaseModel):
    """Metadata for a single STE rule (id, title, summary, applicability)."""

    model_config = ConfigDict(extra="forbid")

    rule_id: str
    section: str | None = None
    title: str
    summary: str | None = None
    text_type: TextType | None = None


class GlossaryEntry(BaseModel):
    """A project-specific glossary entry that extends or overrides the dictionary."""

    model_config = ConfigDict(extra="forbid")

    word: str
    part_of_speech: str = "noun"
    status: WordStatus = WordStatus.TECHNICAL_NOUN
    approved_meaning: str | None = None
    inflections: list[str] = []
    preferred_term: str | None = None


class Glossary(BaseModel):
    """A project glossary / terminology profile loaded from YAML."""

    model_config = ConfigDict(extra="forbid")

    name: str
    disable_native_glossary: bool = False
    technical_nouns: list[GlossaryEntry] = []
    technical_verbs: list[GlossaryEntry] = []
    preferred_terms: dict[str, str] = {}

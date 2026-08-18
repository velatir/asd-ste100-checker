"""Dictionary engine: curated JSON + glossary, inflection indexes, lookup."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml

from ste100.core.schema import (
    DictionaryRecord,
    Glossary,
    GlossaryEntry,
    WordStatus,
)

_PACKAGE_DATA = Path(__file__).resolve().parent / "data"
_DEFAULT_DICTIONARY = _PACKAGE_DATA / "dictionary.json"
_SEED_TECHNICAL_NOUNS = _PACKAGE_DATA / "seed_technical_nouns.json"
_SEED_TECHNICAL_VERBS = _PACKAGE_DATA / "seed_technical_verbs.json"

_APPROVED_STATUSES = frozenset(
    {
        WordStatus.APPROVED,
        WordStatus.TECHNICAL_NOUN,
        WordStatus.TECHNICAL_VERB,
    }
)

_UNAPPROVED_STATUSES = frozenset(
    {
        WordStatus.UNAPPROVED,
        WordStatus.FORBIDDEN,
        WordStatus.NOT_APPROVED_TECHNICAL_VERB,
    }
)

# Tokens that are not STE vocabulary checks (labels, codes, noise).
_NON_VOCAB_RE = re.compile(r"^[\W\d_]+$", re.UNICODE)

# Spelled cardinals often appear in STE examples ("four bolts") alongside digits.
_CARDINAL_WORDS = frozenset(
    {
        "zero",
        "one",
        "two",
        "three",
        "four",
        "five",
        "six",
        "seven",
        "eight",
        "nine",
        "ten",
        "eleven",
        "twelve",
        "thirteen",
        "fourteen",
        "fifteen",
        "sixteen",
        "seventeen",
        "eighteen",
        "nineteen",
        "twenty",
        "thirty",
        "forty",
        "fifty",
        "sixty",
        "seventy",
        "eighty",
        "ninety",
        "hundred",
        "thousand",
        "million",
    }
)


def is_non_vocabulary_token(word: str) -> bool:
    """Return True for ALL-CAPS labels, numbers, and punctuation-only tokens."""
    if not word:
        return True
    stripped = word.strip()
    if not stripped:
        return True
    if _normalize_key(stripped) in _CARDINAL_WORDS:
        return True
    if _NON_VOCAB_RE.match(stripped):
        return True
    # Pure numeric / mixed alphanumerics like part numbers (ABC-123 handled below)
    if any(ch.isdigit() for ch in stripped) and not stripped.isalpha():
        return True
    # ALL-CAPS alphabetic labels (ON, OFF, APU) — not dictionary vocabulary
    if stripped.isalpha() and stripped.isupper() and len(stripped) >= 2:
        return True
    # Isolated punctuation / symbols
    if not any(ch.isalpha() for ch in stripped):
        return True
    return False


def _simple_plural(word: str) -> str | None:
    """Best-effort English plural for seed technical nouns."""
    w = word.strip().lower()
    if not w or " " in w or "-" in w:
        return None
    if w.endswith(("s", "x", "z", "ch", "sh")):
        return w + "es"
    if w.endswith("y") and len(w) > 1 and w[-2] not in "aeiou":
        return w[:-1] + "ies"
    return w + "s"


def _normalize_key(word: str) -> str:
    return word.strip().lower()


def _morphology_keys(word: str) -> list[str]:
    """Surface form plus simple lemma-ish fallbacks (utilizes → utilize)."""
    key = _normalize_key(word)
    if not key:
        return []
    keys = [key]
    if key.endswith("ies") and len(key) > 4:
        keys.append(key[:-3] + "y")
    elif key.endswith("es") and len(key) > 3:
        keys.append(key[:-2])
        keys.append(key[:-1])
    elif key.endswith("s") and len(key) > 2 and not key.endswith("ss"):
        keys.append(key[:-1])
    if key.endswith("ied") and len(key) > 4:
        keys.append(key[:-3] + "y")
    elif key.endswith("ed") and len(key) > 3:
        keys.append(key[:-2])
        keys.append(key[:-1])
    if key.endswith("ying") and len(key) > 5:
        keys.append(key[:-3] + "y")
    elif key.endswith("ing") and len(key) > 4:
        keys.append(key[:-3])
        if len(key) > 5 and key[-4] == key[-5]:
            keys.append(key[:-4])
    seen: set[str] = set()
    out: list[str] = []
    for candidate in keys:
        if candidate and candidate not in seen:
            seen.add(candidate)
            out.append(candidate)
    return out


def _load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return data


def _entry_to_record(entry: GlossaryEntry) -> DictionaryRecord:
    return DictionaryRecord(
        word=entry.word,
        part_of_speech=entry.part_of_speech,
        status=entry.status,
        approved_meaning=entry.approved_meaning,
        inflections=list(entry.inflections),
        alternatives=[],
        category=None,
        rule_ref=None,
        notes=None,
    )


class DictionaryEngine:
    """Loads STE dictionary + optional project glossary and serves lookups."""

    def __init__(self) -> None:
        self.records: list[DictionaryRecord] = []
        self.glossary: Glossary | None = None
        self.preferred_terms: dict[str, str] = {}
        self._index: dict[str, DictionaryRecord] = {}
        self._loaded = False

    def load(
        self,
        dictionary_path: str | Path | None = None,
    ) -> DictionaryEngine:
        """Load dictionary.json from package data (or an override path)."""
        dict_path = Path(dictionary_path) if dictionary_path else _DEFAULT_DICTIONARY

        raw = _load_json(dict_path)
        words = raw.get("words", [])
        self.records = [DictionaryRecord.model_validate(item) for item in words]

        self._index.clear()
        for record in self.records:
            self._index_record(record)

        # Curated alpha dictionary often omits category TNs/TVs (Rules 1.5 / 1.12).
        # Seed common STE example terms so procedure sentences stay fair.
        self._merge_seed_file(
            _SEED_TECHNICAL_NOUNS,
            list_key="technical_nouns",
            part_of_speech="noun",
            status=WordStatus.TECHNICAL_NOUN,
            rule_ref="Rule 1.5",
            notes="Seeded technical noun (curated dictionary gap fill).",
        )
        self._merge_seed_file(
            _SEED_TECHNICAL_VERBS,
            list_key="technical_verbs",
            part_of_speech="verb",
            status=WordStatus.TECHNICAL_VERB,
            rule_ref="Rule 1.12",
            notes="Seeded technical verb (curated dictionary gap fill).",
        )

        self._loaded = True
        return self

    def _merge_seed_file(
        self,
        path: Path,
        *,
        list_key: str,
        part_of_speech: str,
        status: WordStatus,
        rule_ref: str,
        notes: str,
    ) -> None:
        """Inject seed TN/TV entries for forms missing an approved index entry."""
        if not path.is_file():
            return
        raw = _load_json(path)
        items = raw.get(list_key, [])
        if not isinstance(items, list):
            raise ValueError(f"Expected {list_key} list in {path}")
        for item in items:
            if isinstance(item, str):
                word = item.strip()
                meaning = None
                category = None
                inflections: list[str] = []
            elif isinstance(item, dict):
                word = str(item.get("word", "")).strip()
                meaning = item.get("approved_meaning")
                category = item.get("category")
                raw_inf = item.get("inflections") or []
                inflections = [str(x) for x in raw_inf] if isinstance(raw_inf, list) else []
            else:
                continue
            if not word:
                continue
            if part_of_speech == "noun":
                plural = _simple_plural(word)
                if plural and plural not in {_normalize_key(i) for i in inflections}:
                    inflections = [*inflections, plural]
            key = _normalize_key(word)
            existing = self._index.get(key)
            if existing is not None and existing.status in _APPROVED_STATUSES:
                continue
            # Prefer seed TN/TV over unapproved alpha entries for the same key.
            record = DictionaryRecord(
                word=word,
                part_of_speech=part_of_speech,
                status=status,
                approved_meaning=meaning,
                inflections=inflections,
                category=category,
                rule_ref=rule_ref,
                notes=notes,
            )
            if existing is not None and existing.status in _UNAPPROVED_STATUSES:
                # Replace weaker unapproved index hit with technical allowance.
                self.records.append(record)
                self._index[key] = record
                for inflection in inflections:
                    ik = _normalize_key(inflection)
                    if ik:
                        self._index[ik] = record
            else:
                self.records.append(record)
                self._index_record(record)

    def ensure_loaded(self) -> None:
        if not self._loaded:
            self.load()

    def _index_record(self, record: DictionaryRecord) -> None:
        keys = {_normalize_key(record.word)}
        for inflection in record.inflections:
            keys.add(_normalize_key(inflection))
        for key in keys:
            if not key:
                continue
            # Prefer headword / earlier entries; do not overwrite with weaker status
            existing = self._index.get(key)
            if existing is None:
                self._index[key] = record
            elif existing.status in _UNAPPROVED_STATUSES and record.status in _APPROVED_STATUSES:
                self._index[key] = record

    def lookup(self, word: str) -> DictionaryRecord | None:
        """Case-insensitive lookup by headword or inflection."""
        self.ensure_loaded()
        if is_non_vocabulary_token(word):
            return None
        for key in _morphology_keys(word):
            record = self._index.get(key)
            if record is not None:
                return record
        return None

    def lookup_payload(
        self, word: str, *, include_examples: bool = False
    ) -> dict[str, Any]:
        """CLI/MCP-shaped dictionary lookup payload."""
        record = self.lookup(word)
        if record is None:
            return {
                "word": word,
                "found": False,
                "status": None,
                "alternatives": self.suggest_alternatives(word),
            }
        payload = record.model_dump(mode="json")
        payload["found"] = True
        payload["alternatives"] = self.suggest_alternatives(word) or payload.get(
            "alternatives", []
        )
        if not include_examples:
            payload["examples_ste"] = []
            payload["examples_non_ste"] = []
            payload["notes"] = None
        return payload

    def is_approved(self, word: str, pos: str | None = None) -> bool:
        """True if the word is an approved (or glossary technical) term."""
        self.ensure_loaded()
        if is_non_vocabulary_token(word):
            return True
        key = _normalize_key(word)
        if key in self.preferred_terms:
            return False
        if self._native_glossary_disabled:
            return True
        record = self._index.get(key)
        if record is None:
            return False
        return record.status in _APPROVED_STATUSES

    @property
    def _native_glossary_disabled(self) -> bool:
        return self.glossary is not None and self.glossary.disable_native_glossary

    def suggest_alternatives(self, word: str) -> list[str]:
        """Return approved alternatives / preferred terms for a word."""
        self.ensure_loaded()
        suggestions: list[str] = []
        for key in _morphology_keys(word):
            if key in self.preferred_terms:
                preferred = self.preferred_terms[key]
                if preferred not in suggestions:
                    suggestions.append(preferred)
            if self._native_glossary_disabled:
                continue
            record = self._index.get(key)
            if record is not None:
                for alt in record.alternatives:
                    if alt not in suggestions:
                        suggestions.append(alt)
        return suggestions

    def merge_glossary(self, path: str | Path) -> Glossary:
        """Load a project glossary YAML and merge into the lookup indexes."""
        self.ensure_loaded()
        glossary_path = Path(path)
        with glossary_path.open(encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
        if not isinstance(raw, dict):
            raise ValueError(f"Glossary YAML must be a mapping: {glossary_path}")

        # Allow minimal YAML without nested GlossaryEntry objects
        glossary = self._parse_glossary(raw)
        self.glossary = glossary

        for entry in glossary.technical_nouns:
            record = _entry_to_record(entry).model_copy(
                update={"status": WordStatus.TECHNICAL_NOUN}
            )
            self.records.append(record)
            self._index_record(record)
            if entry.preferred_term:
                self.preferred_terms[_normalize_key(entry.word)] = entry.preferred_term

        for entry in glossary.technical_verbs:
            record = _entry_to_record(entry).model_copy(
                update={"status": WordStatus.TECHNICAL_VERB}
            )
            self.records.append(record)
            self._index_record(record)
            if entry.preferred_term:
                self.preferred_terms[_normalize_key(entry.word)] = entry.preferred_term

        for src, dest in glossary.preferred_terms.items():
            self.preferred_terms[_normalize_key(src)] = dest

        return glossary

    def _parse_glossary(self, raw: dict[str, Any]) -> Glossary:
        """Parse glossary YAML; accept string lists or GlossaryEntry dicts."""
        name = str(raw.get("name", "project"))
        nouns = self._coerce_entries(
            raw.get("technical_nouns", []),
            default_pos="noun",
            default_status=WordStatus.TECHNICAL_NOUN,
        )
        verbs = self._coerce_entries(
            raw.get("technical_verbs", []),
            default_pos="verb",
            default_status=WordStatus.TECHNICAL_VERB,
        )
        preferred = raw.get("preferred_terms") or {}
        if not isinstance(preferred, dict):
            raise ValueError("preferred_terms must be a mapping of word -> preferred")
        preferred_terms = {str(k): str(v) for k, v in preferred.items()}
        disable_native = bool(raw.get("disable_native_glossary", False))
        return Glossary(
            name=name,
            disable_native_glossary=disable_native,
            technical_nouns=nouns,
            technical_verbs=verbs,
            preferred_terms=preferred_terms,
        )

    def _coerce_entries(
        self,
        items: list[Any],
        *,
        default_pos: str,
        default_status: WordStatus,
    ) -> list[GlossaryEntry]:
        entries: list[GlossaryEntry] = []
        for item in items:
            if isinstance(item, str):
                entries.append(
                    GlossaryEntry(
                        word=item,
                        part_of_speech=default_pos,
                        status=default_status,
                    )
                )
            elif isinstance(item, dict):
                payload = {
                    "part_of_speech": default_pos,
                    "status": default_status,
                    **item,
                }
                entries.append(GlossaryEntry.model_validate(payload))
            else:
                raise ValueError(f"Invalid glossary entry: {item!r}")
        return entries

    def safe_replacements(self) -> dict[str, str]:
        """Map lowercased forms -> single unambiguous approved alternative."""
        self.ensure_loaded()
        mapping: dict[str, str] = {}
        for src, dest in self.preferred_terms.items():
            mapping[_normalize_key(src)] = dest
        for record in self.records:
            if record.status not in (WordStatus.UNAPPROVED, WordStatus.FORBIDDEN):
                continue
            if len(record.alternatives) != 1:
                continue
            alt = record.alternatives[0]
            forms = [record.word, *record.inflections]
            for form in forms:
                key = _normalize_key(form)
                if key and key not in mapping:
                    mapping[key] = alt
        return mapping


_default_engine: DictionaryEngine | None = None


def get_default_engine() -> DictionaryEngine:
    """Process-wide dictionary singleton (loaded once)."""
    global _default_engine
    if _default_engine is None:
        _default_engine = DictionaryEngine().load()
    return _default_engine


def resolve_engine(
    dictionary: DictionaryEngine | None = None,
    glossary_path: str | None = None,
) -> DictionaryEngine:
    """Resolve the engine for a check/fix entry point.

    If ``dictionary`` is given, use it (merging the glossary if provided).
    Otherwise reuse the process-wide singleton when no glossary is needed, or
    build a fresh engine only when a glossary must be merged in (so the shared
    singleton stays glossary-free). Avoids a full dictionary reload on every
    glossary-free call.
    """
    if dictionary is not None:
        if glossary_path is not None:
            dictionary.merge_glossary(glossary_path)
        return dictionary
    if glossary_path is None:
        return get_default_engine()
    engine = DictionaryEngine().load()
    engine.merge_glossary(glossary_path)
    return engine


def load_dictionary(path: str | Path | None = None) -> DictionaryEngine:
    """Convenience: load a DictionaryEngine (optionally from a custom path)."""
    engine = DictionaryEngine()
    engine.load(dictionary_path=path)
    return engine


def lookup_word(word: str) -> DictionaryRecord | None:
    """Lookup against the default package dictionary."""
    return get_default_engine().lookup(word)

"""Dictionary subsystem: PDF extraction, curated data, lookup engine."""

from __future__ import annotations

from typing import Any

__all__ = [
    "DictionaryEngine",
    "get_default_engine",
    "is_non_vocabulary_token",
    "load_dictionary",
    "lookup_word",
]


def __getattr__(name: str) -> Any:
    if name in __all__:
        from ste100.dictionary import engine as _engine

        return getattr(_engine, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

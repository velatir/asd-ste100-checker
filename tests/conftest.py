"""Shared pytest fixtures for the STE checker test suite."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ste100.dictionary.engine import DictionaryEngine

ROOT = Path(__file__).resolve().parents[1]
CORPUS_PATH = Path(__file__).resolve().parent / "corpus" / "ste_pairs.json"
PDF_PATH = ROOT / "ASD-STE100-ISSUE-9.pdf"
DICTIONARY_PATH = ROOT / "ste100" / "dictionary" / "data" / "dictionary.json"


@pytest.fixture(scope="session")
def dictionary_engine() -> DictionaryEngine:
    """Fresh loaded dictionary with seed technical nouns."""
    return DictionaryEngine().load()


@pytest.fixture(scope="session")
def corpus_pairs() -> list[dict]:
    data = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    return list(data["pairs"])


@pytest.fixture
def tmp_glossary(tmp_path: Path) -> Path:
    path = tmp_path / "glossary.yaml"
    path.write_text(
        "\n".join(
            [
                "name: test-glossary",
                "technical_nouns:",
                "  - widget",
                "  - word: gizmo",
                "    approved_meaning: A project-specific part.",
                "technical_verbs:",
                "  - word: recalibrate",
                "preferred_terms:",
                "  utilise: use",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return path

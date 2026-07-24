"""spaCy model readiness checks for serve / doctor / setup."""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass

import spacy

from ste100.core.analyzer import get_spacy_model_name


@dataclass(frozen=True)
class SpacyModelStatus:
    """Result of attempting to load the configured spaCy model."""

    model: str
    ok: bool
    error: str | None = None


def check_spacy_model(model: str | None = None) -> SpacyModelStatus:
    """Try loading the configured (or named) spaCy model without downloading."""
    name = (model.strip() if model else None) or get_spacy_model_name()
    try:
        spacy.load(name)
    except Exception as exc:  # noqa: BLE001 — surface any load failure
        return SpacyModelStatus(model=name, ok=False, error=str(exc))
    return SpacyModelStatus(model=name, ok=True)


def ensure_spacy_model(model: str | None = None) -> None:
    """Fail fast if the spaCy model is missing (no auto-download).

    Intended for ``serve`` startup. On failure, raise ``SystemExit`` with a
    hint to run ``python -m ste100 setup`` (or ``ste100 doctor --fix``).
    """
    status = check_spacy_model(model)
    if status.ok:
        return
    detail = status.error or "unknown error"
    raise SystemExit(
        f"error: spaCy model {status.model!r} is not available ({detail}). "
        "Install it once with: python -m ste100 setup "
        "(or: ste100 doctor --fix). "
        "Override the model name with STE100_SPACY_MODEL if needed."
    )


def download_spacy_model(model: str | None = None) -> SpacyModelStatus:
    """Download the configured spaCy model via ``python -m spacy download``."""
    name = (model.strip() if model else None) or get_spacy_model_name()
    proc = subprocess.run(
        [sys.executable, "-m", "spacy", "download", name],
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "download failed").strip()
        return SpacyModelStatus(model=name, ok=False, error=err)
    return check_spacy_model(name)

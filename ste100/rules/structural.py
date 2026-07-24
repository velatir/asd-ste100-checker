"""Structural heuristics: units and number formatting (Tier-1, modest)."""

from __future__ import annotations

import re

from spacy.tokens import Doc

from ste100.core.schema import Finding, Severity, Suggestion
from ste100.rules.context import AnalysisContext

RULE_UNITS = "STE-UNITS-FORMAT"

# Common SI / technical units glued to numbers (prefer "10 mm")
_GLUED_UNIT = re.compile(
    r"(?P<num>\d+(?:\.\d+)?)\s*(?P<unit>mm|cm|m|km|µm|um|nm|kg|g|mg|"
    r"l|L|ml|mL|Hz|kHz|MHz|V|mV|kV|A|mA|W|kW|Pa|kPa|MPa|bar|psi|"
    r"°C|degC|°F|N|Nm|rpm)\b",
    re.IGNORECASE,
)

# Bare number after quantity-ish cue words without a nearby unit
_QUANTITY_CUES = frozenset(
    {
        "pressure",
        "temperature",
        "torque",
        "length",
        "distance",
        "weight",
        "mass",
        "voltage",
        "current",
        "speed",
        "clearance",
        "gap",
        "diameter",
        "radius",
        "height",
        "width",
        "depth",
        "thickness",
        "flow",
        "rate",
    }
)

_UNIT_WORDS = frozenset(
    {
        "mm",
        "cm",
        "m",
        "km",
        "kg",
        "g",
        "mg",
        "l",
        "ml",
        "hz",
        "v",
        "a",
        "w",
        "pa",
        "bar",
        "psi",
        "n",
        "nm",
        "rpm",
        "degrees",
        "degree",
        "celsius",
        "fahrenheit",
    }
)


def check_units_format(doc: Doc, context: AnalysisContext) -> list[Finding]:
    """Flag glued units (10mm) and lightweight bare measurement numbers."""
    findings: list[Finding] = []
    text = context.text

    for match in _GLUED_UNIT.finditer(text):
        full = match.group(0)
        num = match.group("num")
        unit = match.group("unit")
        # Already spaced correctly: "10 mm"
        if re.match(rf"{re.escape(num)}\s+{re.escape(unit)}$", full, re.IGNORECASE):
            continue
        # Glued or odd spacing
        preferred = f"{num} {unit}"
        if full.replace(" ", "") == f"{num}{unit}" or not re.search(
            rf"{re.escape(num)}\s+{re.escape(unit)}", full
        ):
            findings.append(
                Finding(
                    rule_id=RULE_UNITS,
                    severity=Severity.INFO,
                    message=(
                        f"Prefer a space between the number and unit: '{preferred}' "
                        f"(found '{full}')."
                    ),
                    start=match.start(),
                    end=match.end(),
                    sentence=None,
                    evidence={
                        "rule_ref": "STE units formatting",
                        "found": full,
                        "preferred": preferred,
                    },
                    suggestions=[
                        Suggestion(
                            replacement=preferred,
                            confidence=0.9,
                            automatic=True,
                        )
                    ],
                )
            )

    # Bare numbers after quantity cues (very lightweight)
    for i, token in enumerate(doc):
        if not token.like_num and not (token.text.replace(".", "", 1).isdigit()):
            continue
        # Skip if next token looks like a unit
        nxt = token.nbor(1) if i + 1 < len(doc) else None
        if nxt is not None and nxt.text.lower().rstrip(".") in _UNIT_WORDS:
            continue
        # Skip ordinals / list numbers / years-ish
        if token.text.endswith(("st", "nd", "rd", "th")):
            continue
        prev = token.nbor(-1) if i > 0 else None
        prev2 = token.nbor(-2) if i > 1 else None
        cue = False
        for cand in (prev, prev2):
            if cand is not None and cand.text.lower() in _QUANTITY_CUES:
                cue = True
                break
        if not cue:
            continue
        # Avoid flagging step numbers: "1. Remove" / "Step 2"
        if prev is not None and prev.text.lower() in {"step", "section", "item", "figure"}:
            continue
        findings.append(
            Finding(
                rule_id=RULE_UNITS,
                severity=Severity.INFO,
                message=(
                    f"Number '{token.text}' may be a measurement without a unit; "
                    "add the correct unit if this is a quantity."
                ),
                start=token.idx,
                end=token.idx + len(token.text),
                sentence=None,
                evidence={
                    "rule_ref": "STE units formatting",
                    "number": token.text,
                    "cue": (prev.text if prev is not None else None),
                },
                suggestions=[],
            )
        )

    return findings

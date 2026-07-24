#!/usr/bin/env python3
"""Dev-only: measure STE100 MCP schema + sample-output token cost.

Not imported by the MCP server. Uses tiktoken when available, else char/4.
Prints a per-tool breakdown and a final ``TOTAL <int>`` line (lower is better).

Also compares compact vs full ERROR findings on the fixture and prints:

- ``COVERAGE <float>`` — compact ERROR count / full ERROR count (1.0 if full has 0)
- ``SCORE <float>`` — TOTAL + 5000 * max(0, 0.8 - coverage) (lower is better)
"""

from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests" / "corpus" / "ste_pairs.json"


def _count_tokens(text: str) -> int:
    try:
        import tiktoken  # type: ignore[import-untyped]

        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except Exception:
        return max(0, len(text) // 4)


def _json_text(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, default=str)


def _load_fixture() -> str:
    data = json.loads(CORPUS.read_text(encoding="utf-8"))
    paragraphs = [
        p["non_ste"]
        for p in data.get("pairs", [])
        if isinstance(p.get("non_ste"), str) and p["non_ste"].strip()
    ]
    return "\n\n".join(paragraphs)


def _error_count(payload: Any) -> int:
    findings = payload.get("findings", []) if isinstance(payload, dict) else []
    count = 0
    for f in findings:
        if isinstance(f, dict):
            if str(f.get("severity", "")).lower() == "error":
                count += 1
        elif isinstance(f, (list, tuple)) and len(f) >= 2:
            if str(f[1]).lower() == "error":
                count += 1
    return count


def _schema_tokens(mcp: Any) -> list[tuple[str, int]]:
    rows: list[tuple[str, int]] = []
    instructions = getattr(mcp, "instructions", None) or ""
    rows.append(("mcp.instructions", _count_tokens(str(instructions))))

    tools = asyncio.run(mcp.list_tools())
    for tool in tools:
        name = getattr(tool, "name", "unknown")
        description = getattr(tool, "description", None) or ""
        parameters = getattr(tool, "parameters", None) or {}
        blob = _json_text({"name": name, "description": description, "parameters": parameters})
        rows.append((f"schema:{name}", _count_tokens(blob)))
    return rows


def _output_tokens(fixture: str, fixture_path: Path) -> list[tuple[str, int]]:
    from ste100.mcp.server import (
        ste_apply_safe_fixes,
        ste_check_changed_files,
        ste_check_file,
        ste_check_text,
        ste_explain_finding,
        ste_lookup_word,
        ste_suggest_rewrite,
        ste_suggest_semantic_review,
    )

    calls: list[tuple[str, Callable[[], Any]]] = [
        ("out:ste_check_text", lambda: ste_check_text(fixture, output="json")),
        (
            "out:ste_check_file",
            lambda: ste_check_file(str(fixture_path), output="json"),
        ),
        ("out:ste_lookup_word", lambda: ste_lookup_word("utilize")),
        ("out:ste_apply_safe_fixes", lambda: ste_apply_safe_fixes(fixture)),
        (
            "out:ste_suggest_rewrite",
            lambda: ste_suggest_rewrite(fixture, max_findings=20),
        ),
        (
            "out:ste_suggest_semantic_review",
            lambda: ste_suggest_semantic_review(fixture, max_findings=20),
        ),
        ("out:ste_check_changed_files", lambda: ste_check_changed_files()),
        ("out:ste_explain_finding", lambda: ste_explain_finding("STE-PASSIVE")),
    ]

    rows: list[tuple[str, int]] = []
    for label, fn in calls:
        result = fn()
        rows.append((label, _count_tokens(_json_text(result))))
    return rows


def _coverage(fixture: str) -> float:
    from ste100.mcp.server import ste_check_text

    full = ste_check_text(fixture, output="json", verbosity="full")
    compact = ste_check_text(fixture, output="json", verbosity="compact")
    full_errors = _error_count(full)
    if full_errors == 0:
        return 1.0
    return _error_count(compact) / full_errors


def main() -> None:
    from ste100.mcp.server import mcp

    fixture = _load_fixture()
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".txt",
        encoding="utf-8",
        delete=False,
    ) as tmp:
        tmp.write(fixture)
        fixture_path = Path(tmp.name)

    try:
        rows = _schema_tokens(mcp) + _output_tokens(fixture, fixture_path)
        coverage = _coverage(fixture)
    finally:
        fixture_path.unlink(missing_ok=True)

    total = 0
    for label, n in rows:
        print(f"{label}\t{n}")
        total += n
    print(f"TOTAL {total}")
    print(f"COVERAGE {coverage:.6f}")
    score = total + 5000 * max(0.0, 0.8 - coverage)
    if abs(score - round(score)) < 1e-9:
        print(f"SCORE {int(round(score))}")
    else:
        print(f"SCORE {score:.6f}")


if __name__ == "__main__":
    main()

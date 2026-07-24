"""PDF raw text extractor for the official ASD-STE100 Issue 9 specification.

Extracts per-page text via PyMuPDF (fitz), with an optional ``pdftotext``
subprocess fallback. Section boundaries are derived from the PDF outline
(with heuristic defaults if the TOC is missing).

Unofficial project. Not affiliated with ASD. ASD-STE100 is a registered
European Union Trade Mark (No. 017966390).
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Any

# Default section page ranges for ASD-STE100 Issue 9 (1-indexed, inclusive).
# Verified against the PDF outline; used when TOC probing fails.
_DEFAULT_SECTIONS: dict[str, tuple[int, int]] = {
    "front_matter": (1, 42),
    "writing_rules": (43, 128),
    "dictionary": (129, 434),
    "dictionary_intro": (129, 148),
    "dictionary_alpha": (149, 434),
    "examples": (43, 128),  # STE/Non-STE examples live inside writing rules
}


def _open_pdf(pdf_path: str | Path):
    try:
        import fitz  # PyMuPDF
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "pymupdf is required for PDF extraction. "
            "Install with: pip install pymupdf"
        ) from exc
    return fitz.open(str(pdf_path))


def extract_raw_pages(pdf_path: str | Path) -> list[dict[str, Any]]:
    """Extract plain text for every page.

    Returns a list of ``{"page": int, "text": str}`` with 1-indexed pages.
    Prefers PyMuPDF; falls back to ``pdftotext -layout`` if fitz fails.
    """
    path = Path(pdf_path)
    if not path.is_file():
        raise FileNotFoundError(f"PDF not found: {path}")

    try:
        return _extract_pages_fitz(path)
    except Exception as fitz_err:  # noqa: BLE001
        try:
            return _extract_pages_pdftotext(path)
        except Exception as pdftotext_err:  # noqa: BLE001
            raise RuntimeError(
                f"PDF extraction failed with PyMuPDF ({fitz_err}) "
                f"and pdftotext ({pdftotext_err})"
            ) from pdftotext_err


def _extract_pages_fitz(path: Path) -> list[dict[str, Any]]:
    doc = _open_pdf(path)
    try:
        pages: list[dict[str, Any]] = []
        for i in range(doc.page_count):
            text = doc[i].get_text("text")
            pages.append({"page": i + 1, "text": text or ""})
        return pages
    finally:
        doc.close()


def _extract_pages_pdftotext(path: Path) -> list[dict[str, Any]]:
    """Fallback: invoke poppler ``pdftotext -layout`` and split on form feeds."""
    result = subprocess.run(
        ["pdftotext", "-layout", str(path), "-"],
        check=True,
        capture_output=True,
        text=True,
    )
    chunks = result.stdout.split("\f")
    pages: list[dict[str, Any]] = []
    for i, chunk in enumerate(chunks):
        if not chunk.strip() and i == len(chunks) - 1:
            continue
        pages.append({"page": i + 1, "text": chunk})
    if not pages:
        raise RuntimeError("pdftotext returned no pages")
    return pages


def probe_section_ranges(pdf_path: str | Path) -> dict[str, tuple[int, int]]:
    """Probe the PDF outline to locate writing rules and dictionary bounds."""
    path = Path(pdf_path)
    sections = dict(_DEFAULT_SECTIONS)
    try:
        doc = _open_pdf(path)
    except Exception:  # noqa: BLE001
        return sections

    try:
        toc = doc.get_toc() or []
        page_count = doc.page_count
    finally:
        doc.close()

    def _find(title_substr: str) -> int | None:
        needle = title_substr.lower()
        for _level, title, page in toc:
            if needle in (title or "").lower().replace("\r", ""):
                return int(page)
        return None

    rules_start = _find("part 1") or _find("writing rules")
    dict_start = _find("part 2") or _find("dictionary")
    alpha_start = None
    for _level, title, page in toc:
        clean = (title or "").replace("\r", "").strip()
        if clean in {"A", "A "} or re_match_letter_a(clean):
            if dict_start is None or page >= dict_start:
                alpha_start = int(page)
                break

    if rules_start and dict_start and rules_start < dict_start:
        sections["front_matter"] = (1, rules_start - 1)
        sections["writing_rules"] = (rules_start, dict_start - 1)
        sections["examples"] = (rules_start, dict_start - 1)
        sections["dictionary"] = (dict_start, page_count)
        intro_end = (alpha_start - 1) if alpha_start else dict_start + 19
        sections["dictionary_intro"] = (dict_start, intro_end)
        sections["dictionary_alpha"] = (
            alpha_start or (dict_start + 20),
            page_count,
        )
    return sections


def re_match_letter_a(clean: str) -> bool:
    return clean == "A" or clean.startswith("A ")


def extract_sections(pdf_path: str | Path) -> dict[str, str]:
    """Extract concatenated text for major specification sections.

    Keys include ``front_matter``, ``writing_rules``, ``dictionary``,
    ``dictionary_intro``, ``dictionary_alpha``, and ``examples``.
    """
    pages = extract_raw_pages(pdf_path)
    ranges = probe_section_ranges(pdf_path)
    by_page = {p["page"]: p["text"] for p in pages}

    out: dict[str, str] = {}
    for name, (start, end) in ranges.items():
        chunks: list[str] = []
        for page_no in range(start, end + 1):
            text = by_page.get(page_no, "")
            if text.strip():
                chunks.append(f"----- PAGE {page_no} -----\n{text}")
        out[name] = "\n".join(chunks)
    return out


def extract_page_lines(
    pdf_path: str | Path,
    page_no: int,
) -> list[dict[str, Any]]:
    """Return positioned text lines for one 1-indexed page.

    Each item is ``{"y": float, "x": float, "text": str, "x1": float}``.
    """
    doc = _open_pdf(pdf_path)
    try:
        if page_no < 1 or page_no > doc.page_count:
            raise IndexError(f"page {page_no} out of range 1..{doc.page_count}")
        page = doc[page_no - 1]
        items: list[dict[str, Any]] = []
        for block in page.get_text("dict").get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                spans = line.get("spans") or []
                text = "".join(s.get("text", "") for s in spans).strip()
                if not text:
                    continue
                x0, y0, x1, _y1 = line["bbox"]
                items.append(
                    {"y": float(y0), "x": float(x0), "x1": float(x1), "text": text}
                )
        items.sort(key=lambda it: (round(it["y"] / 2.0) * 2.0, it["x"]))
        return items
    finally:
        doc.close()


def dump_sections(
    pdf_path: str | Path,
    out_dir: str | Path,
    *,
    also_raw_pages: bool = False,
) -> dict[str, Path]:
    """Write per-section ``.txt`` dumps under ``out_dir``.

    Creates ``raw/<section>.txt`` files. Returns a map of section name -> path.
    """
    out = Path(out_dir)
    raw_dir = out if out.name == "raw" else out / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    sections = extract_sections(pdf_path)
    written: dict[str, Path] = {}
    for name, text in sections.items():
        path = raw_dir / f"{name}.txt"
        path.write_text(text, encoding="utf-8")
        written[name] = path

    meta = raw_dir / "sections_meta.txt"
    ranges = probe_section_ranges(pdf_path)
    meta.write_text(
        "ASD-STE100 Issue 9 section ranges (1-indexed, inclusive)\n"
        + "\n".join(f"{k}: {v[0]}-{v[1]}" for k, v in sorted(ranges.items()))
        + "\n",
        encoding="utf-8",
    )
    written["sections_meta"] = meta

    if also_raw_pages:
        pages_dir = raw_dir / "pages"
        pages_dir.mkdir(exist_ok=True)
        for page in extract_raw_pages(pdf_path):
            p = pages_dir / f"page_{page['page']:03d}.txt"
            p.write_text(page["text"], encoding="utf-8")

    return written


def extract(pdf_path: str, out_dir: str | None = None) -> dict[str, Path]:
    """Convenience wrapper used by the curation pipeline."""
    target = out_dir or str(Path(__file__).resolve().parent / "data" / "raw")
    return dump_sections(pdf_path, target)


def _build_parser() -> argparse.ArgumentParser:
    default_out = Path(__file__).resolve().parent / "data" / "raw"
    parser = argparse.ArgumentParser(
        prog="python -m ste100.dictionary.extract",
        description=(
            "Extract raw ASD-STE100 PDF sections to text dumps "
            "(writing_rules, dictionary, …)."
        ),
    )
    parser.add_argument(
        "--pdf",
        required=True,
        help="Path to ASD-STE100-ISSUE-9.pdf",
    )
    parser.add_argument(
        "--out-dir",
        default=str(default_out),
        help=f"Output directory (default: {default_out})",
    )
    parser.add_argument(
        "--pages",
        action="store_true",
        help="Also dump one .txt file per PDF page under raw/pages/",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    written = dump_sections(args.pdf, args.out_dir, also_raw_pages=args.pages)
    print(f"Wrote {len(written)} section dumps to {args.out_dir}", file=sys.stderr)
    for name, path in sorted(written.items()):
        print(f"  {name}: {path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

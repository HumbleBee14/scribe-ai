"""Text-based page extraction using PyMuPDF (no API cost).

Drop-in alternative to ocr_vision.py. Produces the same output format
(summary, detailed_text, keywords, is_toc) but uses local text extraction
instead of Claude Vision API calls.

Pros: Free, fast, works offline
Cons: Misses visual content (diagrams, complex tables, image descriptions)

Configure via USE_OCR_EXTRACTION=false in .env to switch.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

import fitz  # PyMuPDF

from app.core import database as db

logger = logging.getLogger(__name__)

# Common TOC indicators
_TOC_PATTERNS = [
    r"table\s+of\s+contents",
    r"contents\s*$",
    r"index\s*$",
]


def _is_toc_page(text: str) -> bool:
    """Heuristic: detect if a page looks like a table of contents."""
    first_lines = text[:500].lower()
    for pattern in _TOC_PATTERNS:
        if re.search(pattern, first_lines, re.IGNORECASE):
            return True
    # Many lines with "title ... number" pattern
    dot_lines = len(re.findall(r".+[.\s]{3,}\d+", text))
    return dot_lines >= 5


def _extract_tables(page: fitz.Page) -> str:
    """Extract tables from a page using PyMuPDF's table detection."""
    try:
        tables = page.find_tables()
        if not tables or len(tables.tables) == 0:
            return ""

        parts = []
        for table in tables.tables:
            rows = table.extract()
            if not rows:
                continue
            # Convert to markdown table
            header = rows[0]
            md_lines = []
            md_lines.append("| " + " | ".join(str(c or "").strip() for c in header) + " |")
            md_lines.append("| " + " | ".join("---" for _ in header) + " |")
            for row in rows[1:]:
                md_lines.append("| " + " | ".join(str(c or "").strip() for c in row) + " |")
            parts.append("\n".join(md_lines))

        return "\n\n".join(parts)
    except Exception:
        return ""


def _build_summary(text: str, page_num: int) -> str:
    """Generate a brief summary from extracted text."""
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    if not lines:
        return f"Page {page_num}: empty or image-only page"

    # Use first non-empty lines as summary (up to 200 chars)
    summary_parts = []
    char_count = 0
    for line in lines[:5]:
        if char_count + len(line) > 200:
            break
        summary_parts.append(line)
        char_count += len(line)

    return " ".join(summary_parts)


def _extract_keywords(text: str) -> str:
    """Extract potential keywords from text content."""
    # Find capitalized phrases, numbers with units, section headers
    words = set()

    # Section headers (lines that are short and mostly uppercase or title case)
    for line in text.split("\n"):
        line = line.strip()
        if 3 < len(line) < 60 and (line.isupper() or line.istitle()):
            words.add(line.lower())

    # Numbers with units
    for match in re.finditer(r"\b\d+(?:\.\d+)?\s*(?:V|A|W|Hz|CFH|PSI|mm|inch|in|ft|lbs?|°[CF])\b", text, re.IGNORECASE):
        words.add(match.group().lower())

    # Product-like terms (uppercase abbreviations)
    for match in re.finditer(r"\b[A-Z]{2,6}\b", text):
        words.add(match.group())

    return ", ".join(sorted(words)[:30])


def analyze_page_text(
    pdf_path: Path,
    product_id: str,
    source_id: str,
    page_number: int,
    total_pages: int,
) -> dict | None:
    """Extract text from a single PDF page and store in DB.

    Returns dict with summary, detailed_text, keywords, is_toc on success.
    Returns None on failure. Same interface as ocr_vision.analyze_page().
    """
    try:
        doc = fitz.open(str(pdf_path))
        if page_number < 1 or page_number > len(doc):
            doc.close()
            return None

        page = doc[page_number - 1]

        # Extract text
        text = page.get_text("text").strip()

        # Extract tables separately for better formatting
        table_text = _extract_tables(page)

        # Combine: regular text + table markdown
        detailed_text = text
        if table_text:
            detailed_text = f"{text}\n\n{table_text}" if text else table_text

        doc.close()

        if not detailed_text:
            detailed_text = f"(Page {page_number}: image-only content, no extractable text)"

        # Build summary and keywords
        summary = _build_summary(detailed_text, page_number)
        keywords = _extract_keywords(detailed_text)
        is_toc = _is_toc_page(detailed_text)

        result = {
            "summary": summary,
            "detailed_text": detailed_text,
            "keywords": keywords,
            "is_toc": is_toc,
        }

        # Store in DB (same table as OCR results)
        db.upsert_page_analysis(
            product_id=product_id,
            source_id=source_id,
            page=page_number,
            summary=summary,
            detailed_text=detailed_text,
            keywords=keywords,
            is_toc=is_toc,
        )

        print(
            f"[TEXT] {product_id}/{source_id} page {page_number}/{total_pages}: "
            f"{len(detailed_text)} chars, toc={is_toc}",
            flush=True,
        )
        return result

    except Exception:
        logger.exception("[TEXT] Failed to extract page %d from %s", page_number, pdf_path)
        return None

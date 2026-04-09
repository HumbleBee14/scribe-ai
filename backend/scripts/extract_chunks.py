"""Extract text chunks from the manual PDF for hybrid retrieval.

Creates chunks.json with text, page number, section path, and metadata.
Uses PyMuPDF for text extraction.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import fitz

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
FILES_DIR = PROJECT_ROOT / "files"
DATA_DIR = PROJECT_ROOT / "backend" / "app" / "knowledge" / "data"

# Manual section structure (from table of contents on page 2)
SECTIONS = {
    (1, 1): "Cover",
    (2, 6): "Safety",
    (7, 7): "Specifications",
    (8, 9): "Controls",
    (10, 23): "MIG/Flux-Cored Wire Welding",
    (24, 33): "TIG/Stick Welding",
    (34, 40): "Welding Tips",
    (41, 41): "Maintenance",
    (42, 44): "Troubleshooting",
    (45, 45): "Wiring Schematic",
    (46, 47): "Parts List and Diagram",
    (48, 48): "Warranty",
}


def get_section(page_num: int) -> str:
    """Get the section name for a given page number."""
    for (start, end), name in SECTIONS.items():
        if start <= page_num <= end:
            return name
    return "Unknown"


def extract_chunks(pdf_path: Path, target_size: int = 500) -> list[dict]:
    """Extract text chunks from PDF, split by paragraphs within pages."""
    doc = fitz.open(str(pdf_path))
    chunks: list[dict] = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text").strip()
        if not text:
            continue

        human_page = page_num + 1
        section = get_section(human_page)

        # Split text into paragraphs (double newline or significant whitespace)
        paragraphs = re.split(r"\n\s*\n", text)
        paragraphs = [p.strip() for p in paragraphs if p.strip()]

        # Merge small paragraphs to reach target chunk size
        current_chunk: list[str] = []
        current_len = 0

        for para in paragraphs:
            para_len = len(para.split())
            if current_len + para_len > target_size and current_chunk:
                chunk_text = "\n\n".join(current_chunk)
                chunks.append({
                    "text": chunk_text,
                    "page": human_page,
                    "section": section,
                    "word_count": current_len,
                })
                current_chunk = [para]
                current_len = para_len
            else:
                current_chunk.append(para)
                current_len += para_len

        # Flush remaining
        if current_chunk:
            chunk_text = "\n\n".join(current_chunk)
            chunks.append({
                "text": chunk_text,
                "page": human_page,
                "section": section,
                "word_count": current_len,
            })

    doc.close()
    return chunks


def main() -> None:
    pdf_path = FILES_DIR / "owner-manual.pdf"
    print(f"Extracting chunks from {pdf_path.name}...")

    chunks = extract_chunks(pdf_path)
    print(f"  Extracted {len(chunks)} chunks")

    # Summary by section
    sections: dict[str, int] = {}
    for chunk in chunks:
        sec = chunk["section"]
        sections[sec] = sections.get(sec, 0) + 1
    for sec, count in sections.items():
        print(f"    {sec}: {count} chunks")

    output = DATA_DIR / "chunks.json"
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(output, "w", encoding="utf-8") as f:
        json.dump(chunks, f, indent=2, ensure_ascii=False)
    print(f"  Saved to {output}")


if __name__ == "__main__":
    main()

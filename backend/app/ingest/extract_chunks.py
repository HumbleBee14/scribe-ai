from __future__ import annotations

import json
import re
from pathlib import Path

import fitz

from app.packs.models import PackSource


def extract_chunks_from_pdf(
    pdf_path: Path,
    *,
    source: PackSource,
    target_size: int = 500,
) -> list[dict]:
    """Extract paragraph-based chunks from a PDF source."""
    doc = fitz.open(str(pdf_path))
    chunks: list[dict] = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text").strip()
        if not text:
            continue

        human_page = page_num + 1
        paragraphs = re.split(r"\n\s*\n", text)
        paragraphs = [paragraph.strip() for paragraph in paragraphs if paragraph.strip()]

        current_chunk: list[str] = []
        current_len = 0
        for paragraph in paragraphs:
            para_len = len(paragraph.split())
            if current_chunk and current_len + para_len > target_size:
                chunks.append({
                    "text": "\n\n".join(current_chunk),
                    "page": human_page,
                    "section": source.label or source.type.replace("_", " ").title(),
                    "source_id": source.id,
                    "word_count": current_len,
                })
                current_chunk = [paragraph]
                current_len = para_len
            else:
                current_chunk.append(paragraph)
                current_len += para_len

        if current_chunk:
            chunks.append({
                "text": "\n\n".join(current_chunk),
                "page": human_page,
                "section": source.label or source.type.replace("_", " ").title(),
                "source_id": source.id,
                "word_count": current_len,
            })

    doc.close()
    return chunks


def write_chunks(chunks: list[dict], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(chunks, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


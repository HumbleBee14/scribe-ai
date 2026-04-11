from __future__ import annotations

from pathlib import Path

import fitz  # PyMuPDF


def render_source_pages(pdf_path: Path, output_dir: Path, dpi: int = 200) -> list[Path]:
    """Render a PDF source into product-scoped page images."""
    output_dir.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(str(pdf_path))
    rendered: list[Path] = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        zoom = dpi / 72
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        output_path = output_dir / f"page_{page_num + 1:02d}.png"
        pix.save(str(output_path))
        rendered.append(output_path)

    doc.close()
    return rendered


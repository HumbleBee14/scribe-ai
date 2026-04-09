"""Render all PDF pages as PNG images at 200 DPI."""
from __future__ import annotations

import sys
from pathlib import Path

import fitz  # PyMuPDF

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
FILES_DIR = PROJECT_ROOT / "files"
IMAGES_DIR = PROJECT_ROOT / "knowledge" / "images"


def render_pages(pdf_path: Path, output_dir: Path, dpi: int = 200) -> list[Path]:
    """Render each page of a PDF as a PNG file."""
    output_dir.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(str(pdf_path))
    rendered: list[Path] = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        zoom = dpi / 72  # 72 DPI is default
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)

        filename = f"page_{page_num + 1:02d}.png"
        output_path = output_dir / filename
        pix.save(str(output_path))
        rendered.append(output_path)
        print(f"  Rendered {filename} ({pix.width}x{pix.height})")

    doc.close()
    return rendered


def main() -> None:
    print("Rendering PDF pages as PNG images...")
    print()

    # Owner manual (48 pages)
    manual_path = FILES_DIR / "owner-manual.pdf"
    if manual_path.exists():
        print(f"Processing: {manual_path.name}")
        pages = render_pages(manual_path, IMAGES_DIR)
        print(f"  -> {len(pages)} pages rendered to {IMAGES_DIR}")
    else:
        print(f"ERROR: {manual_path} not found")
        sys.exit(1)

    # Quick start guide
    qsg_path = FILES_DIR / "quick-start-guide.pdf"
    if qsg_path.exists():
        qsg_dir = IMAGES_DIR / "quick-start"
        print(f"\nProcessing: {qsg_path.name}")
        pages = render_pages(qsg_path, qsg_dir)
        print(f"  -> {len(pages)} pages rendered to {qsg_dir}")

    # Selection chart
    sc_path = FILES_DIR / "selection-chart.pdf"
    if sc_path.exists():
        sc_dir = IMAGES_DIR / "selection-chart"
        print(f"\nProcessing: {sc_path.name}")
        pages = render_pages(sc_path, sc_dir)
        print(f"  -> {len(pages)} pages rendered to {sc_dir}")

    print("\nDone!")


if __name__ == "__main__":
    main()

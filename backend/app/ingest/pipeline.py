"""Per-document ingestion pipeline with 3 independent stages.

Each PAGE is processed independently through:
  Stage 1 (render):    PDF page -> PNG image
  Stage 2 (analyze):   PNG image -> Claude Vision OCR -> summary, text, keywords
  Stage 3 (embed):     detailed_text -> sentence-transformers -> embedding vector

Status per page: pending -> rendering -> analyzing -> embedding -> done (or failed)

Each stage function works on a SINGLE page and can be called independently.
The orchestrator loops through all pages, but any single page can be re-run
without affecting others.
"""
from __future__ import annotations

import logging
from pathlib import Path

from app.core import database as db
from app.packs.models import PackSource, ProductRuntime

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Stage 1: Render a single page
# ---------------------------------------------------------------------------

def render_single_page(
    pdf_path: Path,
    page_index: int,
    output_path: Path,
    dpi: int = 200,
) -> bool:
    """Render one PDF page as a PNG. Returns True on success."""
    try:
        import fitz
        doc = fitz.open(str(pdf_path))
        if page_index >= len(doc):
            logger.error("Page index %d out of range (doc has %d pages)", page_index, len(doc))
            doc.close()
            return False
        page = doc[page_index]
        zoom = dpi / 72
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        pix.save(str(output_path))
        doc.close()
        return True
    except Exception:
        logger.exception("Failed to render page %d from %s", page_index, pdf_path)
        return False


# ---------------------------------------------------------------------------
# Stage 2: Analyze a single page (OCR or text extraction based on config)
# ---------------------------------------------------------------------------

def analyze_single_page(
    product_id: str,
    source_id: str,
    source_label: str,
    page_number: int,
    total_pages: int,
    image_path: Path,
    source_path: Path | None = None,
) -> bool:
    """Analyze a page using OCR (default) or text extraction. Returns True on success."""
    from app.core.config import settings

    if settings.use_ocr_extraction:
        # Claude Vision OCR (default) - sends page image to LLM
        from app.ingest.ocr_vision import analyze_page
        try:
            result = analyze_page(
                image_path=image_path,
                product_id=product_id,
                source_id=source_id,
                source_label=source_label,
                page_number=page_number,
                total_pages=total_pages,
            )
            return result is not None
        except Exception:
            logger.exception("OCR failed: %s/%s page %d", product_id, source_id, page_number)
            return False
    else:
        # Text extraction (free, local) - uses PyMuPDF
        from app.ingest.text_extraction import analyze_page_text
        if source_path is None:
            logger.error("Text extraction requires source_path for %s/%s page %d", product_id, source_id, page_number)
            return False
        try:
            result = analyze_page_text(
                pdf_path=source_path,
                product_id=product_id,
                source_id=source_id,
                page_number=page_number,
                total_pages=total_pages,
            )
            return result is not None
        except Exception:
            logger.exception("Text extraction failed: %s/%s page %d", product_id, source_id, page_number)
            return False


# ---------------------------------------------------------------------------
# Stage 3: Embed a single page
# ---------------------------------------------------------------------------

def embed_single_page(
    product_id: str,
    source_id: str,
    page_number: int,
) -> bool:
    """Generate embedding for one page. Returns True on success."""
    from app.ingest.build_embeddings import embed_text
    try:
        analysis = db.get_page_analysis(product_id, source_id, page_number)
        if not analysis or not analysis.get("detailed_text"):
            logger.warning("No text to embed: %s/%s page %d", product_id, source_id, page_number)
            return False

        text = analysis["detailed_text"]
        keywords = analysis.get("keywords", "")
        if keywords:
            text = f"{keywords}\n\n{text}"

        blob = embed_text(text)
        if blob is None:
            logger.warning("Embedding model not available, skipping page %d", page_number)
            return False

        db.upsert_page_embedding(product_id, source_id, page_number, blob)
        return True
    except Exception:
        logger.exception("Embedding failed: %s/%s page %d", product_id, source_id, page_number)
        return False


# ---------------------------------------------------------------------------
# Full pipeline: process all pages of a single source document
# ---------------------------------------------------------------------------

def ingest_single_source(
    runtime: ProductRuntime,
    source: PackSource,
) -> dict[str, int]:
    """Run all 3 stages for every page of a source document.

    Each page goes through: render -> analyze -> embed -> done
    Failed pages are logged and skipped. Other pages continue.
    """
    source_path = source.resolve_path(runtime.root_dir)
    if not source_path.exists():
        raise FileNotFoundError(f"Source file not found: {source_path}")
    if source_path.suffix.lower() != ".pdf":
        raise ValueError(f"Unsupported file type: {source_path.suffix}")

    product_id = runtime.id
    source_id = source.id
    source_label = source.label or source.type or source_id

    # Count total pages
    import fitz
    doc = fitz.open(str(source_path))
    total_pages = len(doc)
    doc.close()

    pages_dir = runtime.pages_dir / source_id
    pages_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*60}", flush=True)
    print(f"[PIPELINE] Starting: {product_id}/{source_id} ({total_pages} pages)", flush=True)
    print(f"{'='*60}", flush=True)

    stats = {"pages_rendered": 0, "pages_analyzed": 0, "pages_embedded": 0}

    for page_num in range(1, total_pages + 1):
        page_index = page_num - 1
        filename = f"page_{page_num:02d}.png"
        image_path = pages_dir / filename

        # Stage 1: Render
        print(f"[{product_id}/{source_id}] Page {page_num}/{total_pages} | Stage 1: Rendering...", flush=True)
        if not render_single_page(source_path, page_index, image_path):
            print(f"[{product_id}/{source_id}] Page {page_num}/{total_pages} | Stage 1: RENDER FAILED", flush=True)
            continue

        db.register_rendered_page(product_id, source_id, page_num, filename)
        stats["pages_rendered"] += 1

        # Stage 2: OCR
        print(f"[{product_id}/{source_id}] Page {page_num}/{total_pages} | Stage 2: OCR (Claude Vision)...", flush=True)
        if not analyze_single_page(product_id, source_id, source_label, page_num, total_pages, image_path, source_path=source_path):
            print(f"[{product_id}/{source_id}] Page {page_num}/{total_pages} | Stage 2: OCR FAILED", flush=True)
            continue

        db.update_page_status(product_id, source_id, page_num, "ocr")
        stats["pages_analyzed"] += 1
        print(f"[{product_id}/{source_id}] Page {page_num}/{total_pages} | Stage 2: OCR done", flush=True)

        # Stage 3: Embedding
        print(f"[{product_id}/{source_id}] Page {page_num}/{total_pages} | Stage 3: Embedding...", flush=True)
        if not embed_single_page(product_id, source_id, page_num):
            print(f"[{product_id}/{source_id}] Page {page_num}/{total_pages} | Stage 3: EMBED FAILED (non-fatal)", flush=True)
            continue

        db.update_page_status(product_id, source_id, page_num, "done")
        stats["pages_embedded"] += 1
        print(f"[{product_id}/{source_id}] Page {page_num}/{total_pages} | DONE ✓", flush=True)

    # Update source page count
    db.update_source_pages(product_id, source_id, total_pages)

    # Stage 4: Build structured TOC from tagged TOC pages (single LLM call)
    from app.ingest.build_toc import build_toc_for_source
    toc_count = build_toc_for_source(product_id, source_id, pages_dir)
    stats["toc_entries"] = toc_count

    print(f"\n{'='*60}", flush=True)
    print(f"[PIPELINE] Complete: {product_id}/{source_id}", flush=True)
    print(f"  Rendered:  {stats['pages_rendered']}/{total_pages}", flush=True)
    print(f"  Analyzed:  {stats['pages_analyzed']}/{total_pages}", flush=True)
    print(f"  Embedded:  {stats['pages_embedded']}/{total_pages}", flush=True)
    print(f"  TOC:       {stats['toc_entries']} entries", flush=True)
    print(f"{'='*60}\n", flush=True)

    return stats

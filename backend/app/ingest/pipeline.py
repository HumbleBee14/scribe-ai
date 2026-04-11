"""Per-document ingestion pipeline.

Each source document is processed independently:
  1. Render PDF pages as PNGs
  2. Extract text chunks
  3. Update per-source status in DB

Product-level status (ready/draft) is derived from individual source statuses.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from app.ingest.extract_chunks import extract_chunks_from_pdf, write_chunks
from app.ingest.render_pages import render_source_pages
from app.packs.models import PackSource, ProductRuntime

logger = logging.getLogger(__name__)


def ingest_single_source(
    runtime: ProductRuntime,
    source: PackSource,
) -> dict[str, int]:
    """Process a single source document. Returns stats."""
    source_path = source.resolve_path(runtime.root_dir)
    if not source_path.exists():
        raise FileNotFoundError(f"Source file not found: {source_path}")
    if source_path.suffix.lower() != ".pdf":
        raise ValueError(f"Unsupported file type: {source_path.suffix}")

    # Render pages into assets/pages/<source_id>/
    pages_dir = runtime.pages_dir / source.id
    pages_dir.mkdir(parents=True, exist_ok=True)
    rendered = render_source_pages(source_path, pages_dir)

    # Extract chunks into index/<source_id>/
    chunks = extract_chunks_from_pdf(source_path, source=source)
    source_index_dir = runtime.index_dir / source.id
    source_index_dir.mkdir(parents=True, exist_ok=True)
    write_chunks(chunks, source_index_dir / "chunks.json")

    return {
        "pages_rendered": len(rendered),
        "chunks_extracted": len(chunks),
    }


def rebuild_merged_index(runtime: ProductRuntime) -> int:
    """Merge all per-source chunk files into a single searchable index."""
    merged: list[dict] = []
    for source_dir in sorted(runtime.index_dir.iterdir()):
        if not source_dir.is_dir():
            continue
        chunks_path = source_dir / "chunks.json"
        if chunks_path.exists():
            try:
                chunks = json.loads(chunks_path.read_text(encoding="utf-8"))
                merged.extend(chunks)
            except (json.JSONDecodeError, OSError):
                logger.warning("Failed to read chunks from %s", chunks_path)

    merged_path = runtime.index_dir / "chunks.json"
    merged_path.write_text(
        json.dumps(merged, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return len(merged)

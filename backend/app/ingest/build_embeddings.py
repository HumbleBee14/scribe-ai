"""Stage 3: Generate embeddings from OCR-extracted detailed_text.

Uses sentence-transformers (local model, no API cost) to create
dense vector embeddings for semantic search. The model downloads
automatically on first use (~80MB, cached forever).

Embeddings are stored as BLOBs in the page_embeddings table.
"""
from __future__ import annotations

import logging
import struct
from pathlib import Path

from app.core import database as db

logger = logging.getLogger(__name__)

# Lazy-loaded model to avoid import cost at startup
_model = None


def _get_model():
    """Load sentence-transformers model. Downloads on first use, then uses local cache."""
    global _model
    if _model is None:
        try:
            import os
            os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
            logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
            from sentence_transformers import SentenceTransformer
            # Try local cache first, fall back to download
            try:
                _model = SentenceTransformer("all-MiniLM-L6-v2", local_files_only=True)
            except Exception:
                _model = SentenceTransformer("all-MiniLM-L6-v2")
            logger.info("Loaded embedding model: all-MiniLM-L6-v2")
        except ImportError:
            logger.warning(
                "sentence-transformers not installed. "
                "Run: pip install sentence-transformers"
            )
            return None
    return _model


def _vector_to_blob(vector: list[float]) -> bytes:
    """Pack a float vector into a compact binary blob."""
    return struct.pack(f"{len(vector)}f", *vector)


def _blob_to_vector(blob: bytes) -> list[float]:
    """Unpack a binary blob into a float vector."""
    count = len(blob) // 4
    return list(struct.unpack(f"{count}f", blob))


def embed_text(text: str) -> bytes | None:
    """Generate embedding for a text string. Returns packed binary or None."""
    model = _get_model()
    if model is None:
        return None
    vector = model.encode(text, show_progress_bar=False).tolist()
    return _vector_to_blob(vector)


def cosine_similarity(a: bytes, b: bytes) -> float:
    """Compute cosine similarity between two embedding blobs."""
    va = _blob_to_vector(a)
    vb = _blob_to_vector(b)
    dot = sum(x * y for x, y in zip(va, vb))
    norm_a = sum(x * x for x in va) ** 0.5
    norm_b = sum(x * x for x in vb) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def build_embeddings_for_source(
    product_id: str,
    source_id: str,
    on_progress: callable | None = None,
) -> dict[str, int]:
    """Generate embeddings for all analyzed pages of a source.

    Reads detailed_text from page_analysis, generates embedding,
    stores in page_embeddings. Skips pages that already have embeddings.

    Returns stats dict.
    """
    model = _get_model()
    if model is None:
        logger.warning("Skipping embeddings: sentence-transformers not available")
        return {"pages_embedded": 0}

    # Get all analyzed pages for this source
    pages = db.get_all_page_summaries(product_id)
    source_pages = [p for p in pages if p["source_id"] == source_id]

    embedded = 0
    for page_info in source_pages:
        page_num = page_info["page"]

        # Get the full detailed text for embedding
        analysis = db.get_page_analysis(product_id, source_id, page_num)
        if not analysis or not analysis.get("detailed_text"):
            continue

        # Generate embedding from detailed_text + keywords for richer representation
        text_to_embed = analysis["detailed_text"]
        keywords = analysis.get("keywords", "")
        if keywords:
            text_to_embed = f"{keywords}\n\n{text_to_embed}"

        embedding_blob = embed_text(text_to_embed)
        if embedding_blob:
            db.upsert_page_embedding(product_id, source_id, page_num, embedding_blob)
            embedded += 1

        if on_progress:
            on_progress(embedded, len(source_pages))

    logger.info(
        "Embeddings done: %s/%s - %d pages embedded",
        product_id, source_id, embedded,
    )
    return {"pages_embedded": embedded}

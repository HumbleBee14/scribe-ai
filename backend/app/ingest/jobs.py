"""Background ingestion job management.

Each source document is processed independently as its own background task.
Per-document status is tracked in the sources table.
Product-level status is derived: all sources done = ready.
"""
from __future__ import annotations

import logging
import threading

from fastapi import BackgroundTasks

from app.core import database as db
from app.ingest.pipeline import ingest_single_source, rebuild_merged_index
from app.packs.models import IngestionStatus, PackSource
from app.packs.registry import get_product_registry
from app.retrieval.service import reset_retrieval_service

logger = logging.getLogger(__name__)

_ingestion_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


def _get_lock(key: str) -> threading.Lock:
    with _locks_guard:
        if key not in _ingestion_locks:
            _ingestion_locks[key] = threading.Lock()
        return _ingestion_locks[key]


def enqueue_ingestion(product_id: str, background_tasks: BackgroundTasks) -> IngestionStatus:
    """Queue background processing for all pending source documents."""
    pending = db.get_pending_sources(product_id)
    if not pending:
        return IngestionStatus(
            product_id=product_id, status="ready", stage="complete",
            progress=1.0, message="All documents already processed.",
        )

    db.update_product_status(product_id, "processing")

    for source in pending:
        background_tasks.add_task(
            process_single_document,
            product_id,
            source["source_id"],
        )

    return IngestionStatus(
        product_id=product_id, status="processing", stage="queued",
        progress=0.05, message=f"Processing {len(pending)} document(s)...",
    )


def process_single_document(product_id: str, source_id: str) -> None:
    """Process one source document. Updates per-source and product-level status."""
    lock = _get_lock(f"{product_id}:{source_id}")
    if not lock.acquire(blocking=False):
        logger.info("Already processing %s/%s, skipping", product_id, source_id)
        return

    try:
        logger.info("Processing document: %s/%s", product_id, source_id)
        db.update_source_processing(product_id, source_id, "processing")

        registry = get_product_registry()
        registry._cache.pop(product_id, None)
        runtime = registry.require_product(product_id)

        # Find the source in the manifest
        source = next(
            (s for s in runtime.manifest.sources if s.id == source_id),
            None,
        )
        if source is None:
            db.update_source_processing(
                product_id, source_id, "failed",
                error=f"Source {source_id} not found in manifest",
            )
            _check_product_complete(product_id, runtime)
            return

        stats = ingest_single_source(runtime, source)

        # Update source with results
        db.update_source_processing(
            product_id, source_id, "done",
            pages_rendered=stats["pages_rendered"],
            chunks_extracted=stats["chunks_extracted"],
        )

        # Update page count in sources table
        if stats["pages_rendered"] > 0:
            conn = db._get_conn()
            conn.execute(
                "UPDATE sources SET pages = ? WHERE product_id = ? AND source_id = ?",
                (stats["pages_rendered"], product_id, source_id),
            )
            conn.commit()

        logger.info(
            "Document processed: %s/%s - %d pages, %d chunks",
            product_id, source_id, stats["pages_rendered"], stats["chunks_extracted"],
        )

    except Exception as exc:
        logger.exception("Failed to process %s/%s", product_id, source_id)
        db.update_source_processing(
            product_id, source_id, "failed",
            error=str(exc),
        )

    finally:
        lock.release()
        # After each document completes, check if all are done
        registry = get_product_registry()
        registry._cache.pop(product_id, None)
        runtime = registry.require_product(product_id)
        _check_product_complete(product_id, runtime)


def _check_product_complete(product_id: str, runtime) -> None:
    """If all sources are processed, mark product ready and rebuild merged index."""
    if db.all_sources_processed(product_id):
        total_chunks = rebuild_merged_index(runtime)
        db.update_product_status(product_id, "ready")
        reset_retrieval_service()
        logger.info(
            "Product %s ready: merged index has %d chunks",
            product_id, total_chunks,
        )
    else:
        # Still processing other documents
        pending = db.get_pending_sources(product_id)
        if not pending:
            # No pending but not all done = some failed
            sources = db.get_sources(product_id)
            failed = [s for s in sources if s["processing_status"] == "failed"]
            if failed:
                logger.warning(
                    "Product %s has %d failed sources", product_id, len(failed)
                )

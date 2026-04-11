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
from app.ingest.pipeline import ingest_single_source
from app.packs.models import IngestionStatus
from app.packs.registry import get_product_registry

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
    """Process one source document through all 3 stages."""
    lock = _get_lock(f"{product_id}:{source_id}")
    if not lock.acquire(blocking=False):
        logger.info("Already processing %s/%s, skipping", product_id, source_id)
        return

    try:
        print(f"\n[JOB] Starting document ingestion: {product_id}/{source_id}", flush=True)
        db.update_source_processing(product_id, source_id, "processing")

        registry = get_product_registry()
        registry._cache.pop(product_id, None)
        runtime = registry.require_product(product_id)

        # Find the source
        source = next(
            (s for s in runtime.manifest.sources if s.id == source_id),
            None,
        )
        if source is None:
            db.update_source_processing(
                product_id, source_id, "failed",
                error=f"Source {source_id} not found in manifest",
            )
            _check_product_complete(product_id)
            return

        # Run the 3-stage pipeline
        stats = ingest_single_source(runtime, source)

        # Mark source as done
        db.update_source_processing(
            product_id, source_id, "done",
            pages_rendered=stats["pages_rendered"],
            chunks_extracted=stats["pages_analyzed"],
        )

        print(f"[JOB] Document done: {product_id}/{source_id}", flush=True)

    except Exception as exc:
        print(f"[JOB] Document FAILED: {product_id}/{source_id} - {exc}", flush=True)
        logger.exception("Ingestion failed: %s/%s", product_id, source_id)
        db.update_source_processing(
            product_id, source_id, "failed",
            error=str(exc),
        )

    finally:
        lock.release()
        _check_product_complete(product_id)


def _check_product_complete(product_id: str) -> None:
    """If all sources are processed, mark product ready."""
    if db.all_sources_processed(product_id):
        db.update_product_status(product_id, "ready")
        logger.info("Product %s: all sources processed, status -> ready", product_id)
    else:
        pending = db.get_pending_sources(product_id)
        sources = db.get_sources(product_id)
        failed = [s for s in sources if s.get("processing_status") == "failed"]
        if not pending and failed:
            logger.warning("Product %s: %d sources failed", product_id, len(failed))

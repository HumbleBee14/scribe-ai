from __future__ import annotations

import logging
import threading
from fastapi import BackgroundTasks

from app.ingest.pipeline import ingest_product
from app.packs.models import IngestionStatus
from app.packs.registry import get_product_registry
from app.retrieval.service import reset_retrieval_service

logger = logging.getLogger(__name__)

# Per-product locks to prevent concurrent ingestion of the same product
_ingestion_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


def _get_lock(product_id: str) -> threading.Lock:
    with _locks_guard:
        if product_id not in _ingestion_locks:
            _ingestion_locks[product_id] = threading.Lock()
        return _ingestion_locks[product_id]


def enqueue_ingestion(product_id: str, background_tasks: BackgroundTasks) -> IngestionStatus:
    registry = get_product_registry()
    runtime = registry.require_product(product_id)

    lock = _get_lock(product_id)
    if not lock.acquire(blocking=False):
        return registry.load_status(product_id)

    try:
        status = registry.load_status(product_id)
        if status.status == "processing":
            return status

        status = IngestionStatus(
            product_id=product_id,
            status="processing",
            stage="queued",
            progress=0.05,
            message=f"Ingestion queued for {runtime.product_name}.",
        )
        registry.save_status(product_id, status)
        registry.update_manifest_status(product_id, "processing")
        background_tasks.add_task(run_ingestion_job, product_id)
        return status
    finally:
        lock.release()


def run_ingestion_job(product_id: str) -> None:
    registry = get_product_registry()
    try:
        registry.save_status(
            product_id,
            IngestionStatus(
                product_id=product_id,
                status="processing",
                stage="rendering",
                progress=0.25,
                message="Rendering page images and extracting chunks.",
            ),
        )
        runtime = registry.require_product(product_id)
        summary = ingest_product(runtime)
        registry.save_status(
            product_id,
            IngestionStatus(
                product_id=product_id,
                status="ready",
                stage="complete",
                progress=1.0,
                message=(
                    f"Ready: {summary['pages_rendered']} pages rendered, "
                    f"{summary['chunks']} chunks extracted."
                ),
            ),
        )
        registry.update_manifest_status(product_id, "ready")
        # Invalidate cached retrieval index so next query picks up new chunks
        reset_retrieval_service()
    except Exception as exc:
        logger.exception("Product ingestion failed for %s", product_id)
        registry.save_status(
            product_id,
            IngestionStatus(
                product_id=product_id,
                status="failed",
                stage="failed",
                progress=1.0,
                message="Ingestion failed.",
                error=str(exc),
            ),
        )
        registry.update_manifest_status(product_id, "failed")


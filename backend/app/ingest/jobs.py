"""Background ingestion job management.

Writes status to both SQLite (for fast API reads) and the registry
(for YAML-based status files used by the agent runtime).
"""
from __future__ import annotations

import logging
import threading
from fastapi import BackgroundTasks

from app.core import database as db
from app.ingest.pipeline import ingest_product
from app.packs.models import IngestionStatus
from app.packs.registry import get_product_registry
from app.retrieval.service import reset_retrieval_service

logger = logging.getLogger(__name__)

_ingestion_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


def _get_lock(product_id: str) -> threading.Lock:
    with _locks_guard:
        if product_id not in _ingestion_locks:
            _ingestion_locks[product_id] = threading.Lock()
        return _ingestion_locks[product_id]


def _save_status(product_id: str, status: str, stage: str, progress: float, message: str, error: str | None = None) -> None:
    """Write ingestion status to both database and registry YAML."""
    db.save_ingestion_status(product_id, status, stage, progress, message, error)
    registry = get_product_registry()
    registry.save_status(product_id, IngestionStatus(
        product_id=product_id, status=status, stage=stage,
        progress=progress, message=message, error=error,
    ))


def enqueue_ingestion(product_id: str, background_tasks: BackgroundTasks) -> IngestionStatus:
    registry = get_product_registry()
    runtime = registry.require_product(product_id)

    lock = _get_lock(product_id)
    if not lock.acquire(blocking=False):
        status = registry.load_status(product_id)
        return status

    try:
        status = registry.load_status(product_id)
        if status.status == "processing":
            return status

        _save_status(product_id, "processing", "queued", 0.05, f"Ingestion queued for {runtime.product_name}.")
        db.update_product_status(product_id, "processing")
        background_tasks.add_task(run_ingestion_job, product_id)
        return IngestionStatus(product_id=product_id, status="processing", stage="queued", progress=0.05, message=f"Ingestion queued for {runtime.product_name}.")
    finally:
        lock.release()


def run_ingestion_job(product_id: str) -> None:
    registry = get_product_registry()
    try:
        _save_status(product_id, "processing", "rendering", 0.25, "Rendering page images and extracting chunks.")

        runtime = registry.require_product(product_id)
        summary = ingest_product(runtime)

        msg = f"Ready: {summary['pages_rendered']} pages rendered, {summary['chunks']} chunks extracted."
        _save_status(product_id, "ready", "complete", 1.0, msg)
        db.update_product_status(product_id, "ready")
        registry.update_manifest_status(product_id, "ready")
        reset_retrieval_service()

    except Exception as exc:
        logger.exception("Product ingestion failed for %s", product_id)
        _save_status(product_id, "failed", "failed", 1.0, "Ingestion failed.", str(exc))
        db.update_product_status(product_id, "failed")
        registry.update_manifest_status(product_id, "failed")

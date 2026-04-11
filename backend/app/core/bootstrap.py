"""Application factory and startup lifecycle.

All initialization logic lives here so main.py stays clean.
"""
from __future__ import annotations

import logging
import threading
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import DATA_DIR, PRODUCTS_DIR, settings
from app.core.database import init_db

logger = logging.getLogger(__name__)


def _process_pending_products() -> None:
    """Check for products with sources but not yet processed. Run ingestion for each."""
    from app.core import database as db
    from app.ingest.jobs import run_ingestion_job

    for product in db.list_products():
        has_sources = len(product["sources"]) > 0
        status = product["status"]
        if has_sources and status not in ("ready", "processing"):
            logger.info("Auto-processing product: %s", product["id"])
            try:
                run_ingestion_job(product["id"])
            except Exception:
                logger.exception("Auto-processing failed for %s", product["id"])


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PRODUCTS_DIR.mkdir(parents=True, exist_ok=True)
    init_db()
    # Check for unprocessed products in a background thread
    threading.Thread(target=_process_pending_products, daemon=True).start()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="ProductManualQnA API",
        description="Local-first multimodal reasoning platform for product manuals",
        version="0.1.0",
        lifespan=_lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_url, "http://localhost:3000", "http://127.0.0.1:3000"],
        allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from app.api.routes import router as api_router
    from app.api.products import router as products_router
    from app.api.chat import router as chat_router

    app.include_router(api_router)
    app.include_router(products_router)
    app.include_router(chat_router)

    return app

"""Application factory and startup lifecycle.

All initialization logic lives here so main.py stays clean.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import DATA_DIR, PRODUCTS_DIR, settings
from app.core.database import init_db

logger = logging.getLogger(__name__)


def _setup_logging() -> None:
    """Configure logging to console + file so ingestion logs are visible and persisted."""
    log_fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    logging.basicConfig(level=logging.INFO, format=log_fmt)

    # Also log to file for debugging background tasks
    log_path = DATA_DIR / "server.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(str(log_path), encoding="utf-8")
    file_handler.setFormatter(logging.Formatter(log_fmt))
    file_handler.setLevel(logging.INFO)
    logging.getLogger().addHandler(file_handler)


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    _setup_logging()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PRODUCTS_DIR.mkdir(parents=True, exist_ok=True)
    init_db()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Prox API",
        description="Local-first multimodal reasoning for product manuals and workspaces",
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

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.chat import router as chat_router
from app.api.routes import router as api_router
from app.core.config import DATA_DIR, KNOWLEDGE_DIR, settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup / shutdown lifecycle."""
    # Startup: ensure local runtime directories exist.
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
    (KNOWLEDGE_DIR / "images").mkdir(exist_ok=True)
    (KNOWLEDGE_DIR / "figures").mkdir(exist_ok=True)
    yield
    # Shutdown: nothing to clean up


app = FastAPI(
    title="Prox Multimodal Agent API",
    description="Multimodal reasoning agent for the Vulcan OmniPro 220",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static file serving for knowledge assets
if KNOWLEDGE_DIR.exists():
    app.mount(
        "/assets/images",
        StaticFiles(directory=str(KNOWLEDGE_DIR / "images"), check_dir=False),
        name="page-images",
    )
    app.mount(
        "/assets/figures",
        StaticFiles(directory=str(KNOWLEDGE_DIR / "figures"), check_dir=False),
        name="figure-crops",
    )

# API routes
app.include_router(api_router)
app.include_router(chat_router)

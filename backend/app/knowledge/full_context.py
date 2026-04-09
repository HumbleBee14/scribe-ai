"""Full-context mode — load entire manual PDF into Claude's context window.

For the Vulcan OmniPro 220 challenge, the 48-page manual (~96K tokens) fits
comfortably in Claude's 1M token context window. With prompt caching enabled,
the first call pays the full input cost, but subsequent calls in the same
session get ~90% cost reduction and ~80% latency reduction.

This is the primary broad-question answering path for single-product use cases.
Structured exact-data tools still handle high-risk factual lookups.
"""
from __future__ import annotations

import base64
import logging
from pathlib import Path

from app.core.config import FILES_DIR

logger = logging.getLogger(__name__)

# Default manual filename
OWNER_MANUAL = "owner-manual.pdf"


class FullContextProvider:
    """Manages loading and caching the manual PDF for full-context injection.

    Usage:
        provider = FullContextProvider()
        if provider.is_available():
            content = provider.build_message_content("user question here")
            # Pass content as the user message to Claude
    """

    def __init__(self, files_dir: Path = FILES_DIR) -> None:
        self._files_dir = files_dir
        self._pdf_path = files_dir / OWNER_MANUAL
        self._cached_base64: str | None = None
        self._page_count: int = 0

        if self._pdf_path.exists():
            self._load_pdf()

    def _load_pdf(self) -> None:
        """Load and cache the PDF as base64."""
        with open(self._pdf_path, "rb") as f:
            pdf_bytes = f.read()
        self._cached_base64 = base64.standard_b64encode(pdf_bytes).decode("ascii")

        # Get page count via PyMuPDF
        try:
            import fitz

            doc = fitz.open(str(self._pdf_path))
            self._page_count = len(doc)
            doc.close()
        except ImportError:
            logger.warning("PyMuPDF not available; page count unknown")
            self._page_count = 0

        logger.info(
            "Full-context mode: loaded %s (%d pages, %d bytes base64)",
            self._pdf_path.name,
            self._page_count,
            len(self._cached_base64),
        )

    def is_available(self) -> bool:
        """Check if the manual PDF is loaded and ready."""
        return self._cached_base64 is not None

    @property
    def page_count(self) -> int:
        return self._page_count

    def build_document_block(self) -> dict:
        """Build the document content block for Claude's messages API.

        Returns a dict suitable for inclusion in a message content array:
        {
            "type": "document",
            "source": {"type": "base64", "media_type": "application/pdf", "data": "..."},
            "citations": {"enabled": True},
            "cache_control": {"type": "ephemeral"}
        }
        """
        if not self.is_available():
            raise FileNotFoundError(
                f"Manual PDF not found at {self._pdf_path}. "
                f"Cannot use full-context mode."
            )
        return {
            "type": "document",
            "source": {
                "type": "base64",
                "media_type": "application/pdf",
                "data": self._cached_base64,
            },
            "citations": {"enabled": True},
            "cache_control": {"type": "ephemeral"},
        }

    def build_message_content(self, user_text: str) -> list[dict]:
        """Build complete message content with PDF + user question.

        Returns a list of content blocks:
        [
            { document block with PDF },
            { text block with user question }
        ]
        """
        return [
            self.build_document_block(),
            {"type": "text", "text": user_text},
        ]

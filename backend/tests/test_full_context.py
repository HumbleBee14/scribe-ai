"""Tests for full-context mode — loading manual PDF into Claude context."""
from pathlib import Path

import pytest

from app.knowledge.full_context import FullContextProvider


def test_full_context_provider_loads_pdf() -> None:
    provider = FullContextProvider()
    assert provider.is_available()
    assert provider.page_count == 48


def test_full_context_builds_document_block() -> None:
    provider = FullContextProvider()
    block = provider.build_document_block()
    assert block["type"] == "document"
    assert block["source"]["type"] == "base64"
    assert block["source"]["media_type"] == "application/pdf"
    assert len(block["source"]["data"]) > 0  # base64 data exists
    assert block["citations"]["enabled"] is True
    assert block["cache_control"]["type"] == "ephemeral"


def test_full_context_builds_message_content() -> None:
    provider = FullContextProvider()
    content = provider.build_message_content("What is the duty cycle for MIG?")
    assert len(content) == 2
    assert content[0]["type"] == "document"
    assert content[1]["type"] == "text"
    assert content[1]["text"] == "What is the duty cycle for MIG?"


def test_full_context_unavailable_when_pdf_missing(tmp_path: Path) -> None:
    provider = FullContextProvider(files_dir=tmp_path)
    assert not provider.is_available()


def test_full_context_raises_when_forced_but_unavailable(tmp_path: Path) -> None:
    provider = FullContextProvider(files_dir=tmp_path)
    with pytest.raises(FileNotFoundError):
        provider.build_document_block()

"""Tests for full-context mode — loading manual PDF into Claude context."""
from pathlib import Path

import pytest

from app.knowledge.full_context import OWNER_MANUAL, FullContextProvider


def _write_sample_pdf(tmp_path: Path) -> Path:
    pdf_path = tmp_path / OWNER_MANUAL
    pdf_path.write_bytes(b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n")
    return pdf_path


def test_full_context_provider_loads_pdf(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _write_sample_pdf(tmp_path)
    monkeypatch.setattr(FullContextProvider, "_detect_page_count", lambda self: 3)

    provider = FullContextProvider(files_dir=tmp_path)

    assert provider.is_available()
    assert provider.page_count == 3


def test_full_context_builds_document_block(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _write_sample_pdf(tmp_path)
    monkeypatch.setattr(FullContextProvider, "_detect_page_count", lambda self: 1)

    provider = FullContextProvider(files_dir=tmp_path)
    block = provider.build_document_block()

    assert block["type"] == "document"
    assert block["source"]["type"] == "base64"
    assert block["source"]["media_type"] == "application/pdf"
    assert len(block["source"]["data"]) > 0
    assert block["citations"]["enabled"] is True
    assert block["cache_control"]["type"] == "ephemeral"


def test_full_context_builds_message_content(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _write_sample_pdf(tmp_path)
    monkeypatch.setattr(FullContextProvider, "_detect_page_count", lambda self: 1)

    provider = FullContextProvider(files_dir=tmp_path)
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


def test_full_context_load_failure_degrades_gracefully(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _write_sample_pdf(tmp_path)

    def boom(self: Path) -> bytes:
        raise OSError("cannot read pdf")

    monkeypatch.setattr(Path, "read_bytes", boom)

    provider = FullContextProvider(files_dir=tmp_path)

    assert not provider.is_available()
    assert provider.page_count == 0

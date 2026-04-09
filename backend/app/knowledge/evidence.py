"""Evidence model — typed citation and payload objects for grounded answers."""
from __future__ import annotations

from pydantic import BaseModel, Field


class Citation(BaseModel):
    """A single piece of evidence backing an answer."""

    document: str
    page: int
    type: str  # text_block, table, figure, page_region, structured_fact
    bbox: list[float] | None = None
    crop_url: str | None = None
    exactness: str | None = None  # native_pdf, vision_ocr
    confidence: float | None = None
    source_refs: list[dict] | None = None


class ArtifactSpec(BaseModel):
    """Specification for a generated artifact."""

    # diagram, calculator, configurator, flowchart, comparison-table, step-guide, annotated-image
    type: str
    renderer: str  # svg, react, mermaid, html
    spec: dict = Field(default_factory=dict)
    source_pages: list[dict] = Field(default_factory=list)


class EvidencePayload(BaseModel):
    """Complete answer payload with grounded evidence and optional artifact."""

    answer: str
    citations: list[Citation] = Field(default_factory=list)
    artifact: dict | None = None
    follow_ups: list[str] = Field(default_factory=list)

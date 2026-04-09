"""Evidence model: typed citation and payload objects for grounded answers."""
from __future__ import annotations

from pydantic import BaseModel, Field


class SourceRef(BaseModel):
    """A reference to a specific manual page that grounds a claim."""

    page: int
    description: str = ""


class Citation(BaseModel):
    """A single piece of evidence backing an answer."""

    document: str
    page: int
    type: str  # text_block, table, figure, page_region, structured_fact
    bbox: list[float] | None = None
    crop_url: str | None = None
    exactness: str | None = None  # native_pdf, vision_ocr
    confidence: float | None = None
    source_refs: list[SourceRef] | None = None


class ArtifactSpec(BaseModel):
    """Specification for a generated artifact.

    This model defines the contract between the backend (tool results)
    and the frontend (artifact rendering). Fields:

    - id: unique identifier for the artifact
    - renderer: which frontend viewer to use (mermaid, svg, html, table)
    - title: display title
    - code: the renderable content string
    - source_pages: manual pages this artifact is grounded in
    """

    id: str = ""
    renderer: str  # mermaid, svg, html, table
    title: str = ""
    code: str = ""
    source_pages: list[SourceRef] = Field(default_factory=list)


class EvidencePayload(BaseModel):
    """Complete answer payload with grounded evidence and optional artifact."""

    answer: str
    citations: list[Citation] = Field(default_factory=list)
    artifact: ArtifactSpec | None = None
    follow_ups: list[str] = Field(default_factory=list)

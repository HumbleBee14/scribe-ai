from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class PackSource:
    id: str
    path: str
    type: str
    pages: int | None = None
    label: str | None = None

    def resolve_path(self, base_dir: Path) -> Path:
        return (base_dir / self.path).resolve()


@dataclass(slots=True)
class ProductManifest:
    id: str
    product_name: str
    description: str = ""
    logo_path: str | None = None
    manufacturer: str | None = None
    item_number: str | None = None
    domain: str = "generic"
    status: str = "ready"
    primary_source_id: str | None = None
    categories: list[str] = field(default_factory=list)
    processes: list[str] = field(default_factory=list)
    voltages: list[str] = field(default_factory=list)
    quick_actions: list[dict[str, str]] = field(default_factory=list)
    sources: list[PackSource] = field(default_factory=list)

    @property
    def subtitle(self) -> str:
        return self.description or "Manual Q&A assistant"

    def source_by_id(self, source_id: str | None) -> PackSource | None:
        if source_id is None:
            source_id = self.primary_source_id
        for source in self.sources:
            if source.id == source_id:
                return source
        return None


@dataclass(slots=True)
class ProductRuntime:
    manifest: ProductManifest
    root_dir: Path
    manifest_path: Path
    pages_dir: Path

    @property
    def id(self) -> str:
        return self.manifest.id

    @property
    def product_name(self) -> str:
        return self.manifest.product_name

    @property
    def status(self) -> str:
        return self.manifest.status

    @property
    def domain(self) -> str:
        return self.manifest.domain

    @property
    def processes(self) -> list[str]:
        return list(self.manifest.processes)

    @property
    def voltages(self) -> list[str]:
        return list(self.manifest.voltages)

    @property
    def primary_source(self) -> PackSource | None:
        return self.manifest.source_by_id(self.manifest.primary_source_id)

    @property
    def primary_source_id(self) -> str | None:
        source = self.primary_source
        return source.id if source else None

    @property
    def manual_path(self) -> Path | None:
        source = self.primary_source
        if source is None:
            return None
        return source.resolve_path(self.root_dir)

    @property
    def allowed_tool_names(self) -> list[str]:
        if self.domain == "welding":
            return [
                "lookup_specifications",
                "lookup_duty_cycle",
                "lookup_polarity",
                "lookup_troubleshooting",
                "lookup_safety_warnings",
                "clarify_question",
                "get_page_image",
                "diagnose_weld",
                "search_manual",
            ]
        return [
            "clarify_question",
            "get_page_image",
            "search_manual",
        ]

    def page_image_path(self, page: int, source_id: str | None = None) -> Path:
        source = self.manifest.source_by_id(source_id) or self.primary_source
        if source is None:
            raise FileNotFoundError("No source document registered for this product")
        filename = f"page_{page:02d}.png"
        candidate = self.pages_dir / source.id / filename
        if candidate.exists():
            return candidate
        legacy_candidate = self.pages_dir / filename
        if legacy_candidate.exists():
            return legacy_candidate
        return candidate

    def page_image_url(self, page: int, source_id: str | None = None) -> str:
        resolved_source_id = source_id or self.primary_source_id or "default"
        return (
            f"/api/products/{self.id}/assets/pages/"
            f"{resolved_source_id}/page_{page:02d}.png"
        )


@dataclass(slots=True)
class IngestionStatus:
    product_id: str
    status: str = "idle"
    stage: str = "idle"
    progress: float = 0.0
    message: str = ""
    error: str | None = None


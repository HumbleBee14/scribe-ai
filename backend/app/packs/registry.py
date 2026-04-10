from __future__ import annotations

import re
import shutil
from contextlib import contextmanager
from contextvars import ContextVar, Token
from pathlib import Path
from typing import Iterator

import yaml

from app.core.config import (
    BACKEND_DIR,
    DATA_DIR,
    FILES_DIR,
    KNOWLEDGE_DIR,
    PROJECT_ROOT,
    settings,
)
from app.packs.models import IngestionStatus, PackSource, ProductManifest, ProductRuntime

SEEDED_PACKS_DIR = DATA_DIR / "document-packs"
USER_PRODUCTS_DIR = DATA_DIR / "products"

_active_runtime: ContextVar[ProductRuntime | None] = ContextVar("active_product_runtime", default=None)


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "product"


def _derive_source_id(raw: dict, index: int) -> str:
    if raw.get("id"):
        return _slugify(str(raw["id"]))
    if raw.get("type"):
        return _slugify(str(raw["type"]))
    path = raw.get("path", f"source-{index + 1}")
    return _slugify(Path(str(path)).stem)


def _default_quick_actions(domain: str) -> list[dict[str, str]]:
    if domain == "welding":
        return [
            {
                "label": "Set up MIG",
                "message": "I want to set up MIG welding. Walk me through it step by step.",
            },
            {
                "label": "Set up TIG",
                "message": "I want to set up TIG welding. What do I need to do?",
            },
            {
                "label": "Troubleshoot",
                "message": "I'm having a problem with my welder. Can you help me troubleshoot?",
            },
            {
                "label": "View specs",
                "message": "What are the specifications for all welding processes on this machine?",
            },
        ]
    return [
        {
            "label": "Summarize manual",
            "message": "Give me a concise overview of this product manual and what topics it covers.",
        },
        {
            "label": "Find setup steps",
            "message": "Walk me through the main setup steps from this manual.",
        },
        {
            "label": "Show a diagram",
            "message": "Show me the most relevant diagram or visual reference from this manual.",
        },
        {
            "label": "Search a feature",
            "message": "Help me find the section in this manual that explains a key feature.",
        },
    ]


class ProductRegistry:
    def __init__(
        self,
        seeded_dir: Path = SEEDED_PACKS_DIR,
        user_dir: Path = USER_PRODUCTS_DIR,
    ) -> None:
        self._seeded_dir = seeded_dir
        self._user_dir = user_dir
        self._cache: dict[str, ProductRuntime] = {}

    def ensure_storage(self) -> None:
        self._user_dir.mkdir(parents=True, exist_ok=True)

    def list_products(self) -> list[ProductRuntime]:
        runtimes: list[ProductRuntime] = []
        manifests = sorted(self._seeded_dir.glob("*/pack.yaml")) + sorted(
            self._user_dir.glob("*/pack.yaml")
        )
        for manifest_path in manifests:
            runtime = self.load_product(manifest_path.parent.name)
            if runtime is not None:
                runtimes.append(runtime)
        return sorted(runtimes, key=lambda runtime: (runtime.seeded is False, runtime.product_name.lower()))

    def load_product(self, product_id: str | None) -> ProductRuntime | None:
        if product_id is None:
            product_id = settings.default_product_id
        if product_id in self._cache:
            return self._cache[product_id]

        manifest_path = self._find_manifest_path(product_id)
        if manifest_path is None:
            return None

        runtime = self._build_runtime(manifest_path)
        self._cache[product_id] = runtime
        return runtime

    def require_product(self, product_id: str | None) -> ProductRuntime:
        runtime = self.load_product(product_id)
        if runtime is None:
            raise KeyError(f"Unknown product: {product_id}")
        return runtime

    def create_product(self, name: str, description: str = "") -> ProductRuntime:
        product_id = _slugify(name)
        root_dir = self._user_dir / product_id
        suffix = 2
        while root_dir.exists():
            product_id = f"{_slugify(name)}-{suffix}"
            root_dir = self._user_dir / product_id
            suffix += 1

        (root_dir / "sources").mkdir(parents=True, exist_ok=True)
        (root_dir / "assets" / "pages").mkdir(parents=True, exist_ok=True)
        (root_dir / "assets" / "figures").mkdir(parents=True, exist_ok=True)
        (root_dir / "structured").mkdir(parents=True, exist_ok=True)
        (root_dir / "index").mkdir(parents=True, exist_ok=True)
        (root_dir / "graph").mkdir(parents=True, exist_ok=True)
        (root_dir / "jobs").mkdir(parents=True, exist_ok=True)
        (root_dir / "conversations").mkdir(parents=True, exist_ok=True)

        manifest = {
            "id": product_id,
            "product_name": name,
            "description": description,
            "logo_path": None,
            "domain": "generic",
            "status": "draft",
            "sources": [],
            "quick_actions": _default_quick_actions("generic"),
        }
        manifest_path = root_dir / "pack.yaml"
        manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
        self._cache.pop(product_id, None)
        return self.require_product(product_id)

    def _storage_root(self, runtime: ProductRuntime) -> Path:
        if runtime.seeded:
            return self._user_dir / runtime.id
        return runtime.root_dir

    def _write_manifest(self, runtime: ProductRuntime, manifest: dict) -> None:
        runtime.manifest_path.write_text(
            yaml.safe_dump(manifest, sort_keys=False),
            encoding="utf-8",
        )
        self._cache.pop(runtime.id, None)

    def _source_dir(self, runtime: ProductRuntime, source_id: str) -> Path:
        return self._storage_root(runtime) / "sources" / source_id

    def _clear_source_dir(self, runtime: ProductRuntime, source_id: str) -> None:
        source_dir = self._source_dir(runtime, source_id)
        if source_dir.exists():
            shutil.rmtree(source_dir)

    def _remove_source_artifacts(self, runtime: ProductRuntime, source_id: str) -> None:
        pages_dir = runtime.pages_dir / source_id
        if pages_dir.exists():
            shutil.rmtree(pages_dir)

    def _upsert_source_document(
        self,
        runtime: ProductRuntime,
        *,
        source_id: str,
        filename: str,
        content: bytes,
        source_type: str,
        replace_only: bool,
    ) -> ProductRuntime:
        manifest = self._load_manifest(runtime.manifest_path)
        sources = manifest.setdefault("sources", [])
        existing_index = next(
            (index for index, source in enumerate(sources) if _derive_source_id(source, index) == source_id),
            None,
        )
        if existing_index is None and replace_only:
            raise KeyError(f"Unknown source: {source_id}")
        if existing_index is None and len(sources) >= settings.max_documents_per_product:
            raise ValueError(
                f"Maximum of {settings.max_documents_per_product} documents allowed per product."
            )

        target_dir = self._source_dir(runtime, source_id)
        self._clear_source_dir(runtime, source_id)
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / Path(filename).name
        target_path.write_bytes(content)
        relative_path = str(target_path.relative_to(runtime.root_dir)).replace("\\", "/")

        payload = {
            "id": source_id,
            "path": relative_path,
            "type": source_type,
            "label": Path(filename).name,
        }
        if existing_index is None:
            sources.append(payload)
        else:
            sources[existing_index].update(payload)

        if not manifest.get("primary_source_id"):
            manifest["primary_source_id"] = source_id
        manifest["status"] = "processing"
        self._remove_source_artifacts(runtime, source_id)
        self._write_manifest(runtime, manifest)
        return self.require_product(runtime.id)

    def add_source_document(
        self,
        product_id: str,
        filename: str,
        content: bytes,
        source_type: str = "manual",
    ) -> ProductRuntime:
        runtime = self.require_product(product_id)
        source_id = _slugify(Path(filename).stem)
        return self._upsert_source_document(
            runtime,
            source_id=source_id,
            filename=filename,
            content=content,
            source_type=source_type,
            replace_only=False,
        )

    def replace_source_document(
        self,
        product_id: str,
        source_id: str,
        filename: str,
        content: bytes,
        source_type: str = "manual",
    ) -> ProductRuntime:
        runtime = self.require_product(product_id)
        return self._upsert_source_document(
            runtime,
            source_id=source_id,
            filename=filename,
            content=content,
            source_type=source_type,
            replace_only=True,
        )

    def remove_source_document(self, product_id: str, source_id: str) -> ProductRuntime:
        runtime = self.require_product(product_id)
        manifest = self._load_manifest(runtime.manifest_path)
        sources = manifest.get("sources", [])
        remaining = [
            source
            for index, source in enumerate(sources)
            if _derive_source_id(source, index) != source_id
        ]
        if len(remaining) == len(sources):
            raise KeyError(f"Unknown source: {source_id}")

        manifest["sources"] = remaining
        if manifest.get("primary_source_id") == source_id:
            manifest["primary_source_id"] = remaining[0]["id"] if remaining else None
        manifest["status"] = "processing" if remaining else "draft"

        self._clear_source_dir(runtime, source_id)
        self._remove_source_artifacts(runtime, source_id)
        self._write_manifest(runtime, manifest)
        return self.require_product(product_id)

    def save_logo(self, product_id: str, filename: str, content: bytes) -> ProductRuntime:
        runtime = self.require_product(product_id)
        assets_dir = self._storage_root(runtime) / "assets"
        assets_dir.mkdir(parents=True, exist_ok=True)
        extension = Path(filename).suffix.lower() or ".png"
        target_path = assets_dir / f"logo{extension}"
        target_path.write_bytes(content)

        manifest = self._load_manifest(runtime.manifest_path)
        manifest["logo_path"] = str(target_path.relative_to(runtime.root_dir)).replace("\\", "/")
        self._write_manifest(runtime, manifest)
        return self.require_product(product_id)

    def save_status(self, product_id: str, status: IngestionStatus) -> None:
        runtime = self.require_product(product_id)
        runtime.jobs_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "product_id": status.product_id,
            "status": status.status,
            "stage": status.stage,
            "progress": status.progress,
            "message": status.message,
            "error": status.error,
        }
        (runtime.jobs_dir / "ingestion-status.yaml").write_text(
            yaml.safe_dump(payload, sort_keys=False),
            encoding="utf-8",
        )

    def load_status(self, product_id: str) -> IngestionStatus:
        runtime = self.require_product(product_id)
        path = runtime.jobs_dir / "ingestion-status.yaml"
        if not path.exists():
            return IngestionStatus(product_id=product_id, status=runtime.status, stage="idle")
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return IngestionStatus(
            product_id=product_id,
            status=str(data.get("status", runtime.status)),
            stage=str(data.get("stage", "idle")),
            progress=float(data.get("progress", 0.0)),
            message=str(data.get("message", "")),
            error=data.get("error"),
        )

    def update_manifest_status(self, product_id: str, status: str) -> None:
        runtime = self.require_product(product_id)
        manifest = self._load_manifest(runtime.manifest_path)
        manifest["status"] = status
        runtime.manifest_path.write_text(
            yaml.safe_dump(manifest, sort_keys=False),
            encoding="utf-8",
        )
        self._cache.pop(product_id, None)

    def _find_manifest_path(self, product_id: str) -> Path | None:
        seeded = self._seeded_dir / product_id / "pack.yaml"
        if seeded.exists():
            return seeded
        user = self._user_dir / product_id / "pack.yaml"
        if user.exists():
            return user
        return None

    def _build_runtime(self, manifest_path: Path) -> ProductRuntime:
        manifest_data = self._load_manifest(manifest_path)
        seeded = self._seeded_dir in manifest_path.parents
        root_dir = manifest_path.parent if not seeded else PROJECT_ROOT
        manifest = self._parse_manifest(manifest_data)

        if seeded and manifest.id == "vulcan-omnipro-220":
            structured_dir = BACKEND_DIR / "app" / "knowledge" / "data"
            index_dir = structured_dir
            pages_dir = KNOWLEDGE_DIR / "images"
            figures_dir = KNOWLEDGE_DIR / "figures"
            graph_dir = DATA_DIR / "products" / manifest.id / "graph"
            jobs_dir = DATA_DIR / "products" / manifest.id / "jobs"
            conversations_dir = DATA_DIR / "products" / manifest.id / "conversations"
        else:
            structured_dir = manifest_path.parent / "structured"
            index_dir = manifest_path.parent / "index"
            pages_dir = manifest_path.parent / "assets" / "pages"
            figures_dir = manifest_path.parent / "assets" / "figures"
            graph_dir = manifest_path.parent / "graph"
            jobs_dir = manifest_path.parent / "jobs"
            conversations_dir = manifest_path.parent / "conversations"

        return ProductRuntime(
            manifest=manifest,
            root_dir=root_dir,
            manifest_path=manifest_path,
            structured_dir=structured_dir,
            index_dir=index_dir,
            graph_dir=graph_dir,
            pages_dir=pages_dir,
            figures_dir=figures_dir,
            jobs_dir=jobs_dir,
            conversations_dir=conversations_dir,
            seeded=seeded,
        )

    def _load_manifest(self, manifest_path: Path) -> dict:
        return yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}

    def _parse_manifest(self, data: dict) -> ProductManifest:
        sources = [
            PackSource(
                id=_derive_source_id(raw_source, index),
                path=str(raw_source.get("path", "")),
                type=str(raw_source.get("type", "manual")),
                pages=raw_source.get("pages"),
                label=raw_source.get("label"),
            )
            for index, raw_source in enumerate(data.get("sources", []))
        ]
        primary_source_id = data.get("primary_source_id")
        if primary_source_id is None and sources:
            owner_manual = next((source for source in sources if source.type == "owner_manual"), None)
            primary_source_id = owner_manual.id if owner_manual else sources[0].id

        domain = str(data.get("domain") or ("welding" if data.get("processes") else "generic"))
        return ProductManifest(
            id=str(data["id"]),
            product_name=str(data.get("product_name") or data["id"]),
            description=str(data.get("description", "")),
            logo_path=data.get("logo_path"),
            manufacturer=data.get("manufacturer"),
            item_number=data.get("item_number"),
            domain=domain,
            status=str(data.get("status", "ready")),
            primary_source_id=primary_source_id,
            processes=[str(value) for value in data.get("processes", [])],
            voltages=[str(value) for value in data.get("voltages", [])],
            quick_actions=data.get("quick_actions") or _default_quick_actions(domain),
            sources=sources,
        )


_registry: ProductRegistry | None = None


def get_product_registry() -> ProductRegistry:
    global _registry
    if _registry is None:
        _registry = ProductRegistry()
        _registry.ensure_storage()
    return _registry


def get_active_product() -> ProductRuntime:
    runtime = _active_runtime.get()
    if runtime is not None:
        return runtime
    return get_product_registry().require_product(settings.default_product_id)


@contextmanager
def use_product_runtime(runtime: ProductRuntime) -> Iterator[None]:
    token: Token[ProductRuntime | None] = _active_runtime.set(runtime)
    try:
        yield
    finally:
        _active_runtime.reset(token)


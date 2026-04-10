from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.core.config import settings
from app.ingest.jobs import enqueue_ingestion
from app.packs.registry import get_product_registry

router = APIRouter(prefix="/api/products", tags=["products"])


class CreateProductRequest(BaseModel):
    name: str
    description: str = ""


def _serialize_product(product_id: str) -> dict[str, object]:
    registry = get_product_registry()
    runtime = registry.require_product(product_id)
    status = registry.load_status(product_id)
    return {
        "id": runtime.id,
        "name": runtime.product_name,
        "description": runtime.manifest.description,
        "manufacturer": runtime.manifest.manufacturer,
        "item_number": runtime.manifest.item_number,
        "logo_url": (
            f"/api/products/{runtime.id}/assets/logo"
            if runtime.manifest.logo_path
            else None
        ),
        "domain": runtime.domain,
        "status": runtime.status,
        "processes": runtime.processes,
        "voltages": runtime.voltages,
        "seeded": runtime.seeded,
        "primary_source_id": runtime.primary_source_id,
        "document_count": len(runtime.manifest.sources),
        "max_documents": settings.max_documents_per_product,
        "sources": [
            {
                "id": source.id,
                "type": source.type,
                "label": source.label or source.type,
                "pages": source.pages,
            }
            for source in runtime.manifest.sources
        ],
        "quick_actions": runtime.manifest.quick_actions,
        "ingestion": {
            "status": status.status,
            "stage": status.stage,
            "progress": status.progress,
            "message": status.message,
            "error": status.error,
        },
    }


@router.get("")
def list_products() -> dict[str, object]:
    registry = get_product_registry()
    return {
        "products": [_serialize_product(runtime.id) for runtime in registry.list_products()],
        "default_product_id": registry.require_product(None).id,
    }


@router.get("/{product_id}")
def get_product(product_id: str) -> dict[str, object]:
    registry = get_product_registry()
    try:
        registry.require_product(product_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _serialize_product(product_id)


@router.post("")
def create_product(request: CreateProductRequest) -> dict[str, object]:
    registry = get_product_registry()
    runtime = registry.create_product(request.name, request.description)
    return _serialize_product(runtime.id)


@router.post("/{product_id}/documents")
async def upload_product_documents(
    product_id: str,
    files: list[UploadFile] = File(...),
    source_type: str = Form("manual"),
) -> dict[str, object]:
    registry = get_product_registry()
    try:
        registry.require_product(product_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    try:
        for upload in files:
            content = await upload.read()
            registry.add_source_document(
                product_id,
                filename=upload.filename or "document.pdf",
                content=content,
                source_type=source_type,
            )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _serialize_product(product_id)


@router.post("/{product_id}/documents/{source_id}/replace")
async def replace_product_document(
    product_id: str,
    source_id: str,
    file: UploadFile = File(...),
    source_type: str = Form("manual"),
) -> dict[str, object]:
    registry = get_product_registry()
    try:
        registry.require_product(product_id)
        content = await file.read()
        registry.replace_source_document(
            product_id,
            source_id=source_id,
            filename=file.filename or "document.pdf",
            content=content,
            source_type=source_type,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _serialize_product(product_id)


@router.delete("/{product_id}/documents/{source_id}")
def delete_product_document(product_id: str, source_id: str) -> dict[str, object]:
    registry = get_product_registry()
    try:
        registry.remove_source_document(product_id, source_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _serialize_product(product_id)


@router.post("/{product_id}/logo")
async def upload_product_logo(
    product_id: str,
    file: UploadFile = File(...),
) -> dict[str, object]:
    registry = get_product_registry()
    try:
        registry.require_product(product_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    content = await file.read()
    registry.save_logo(
        product_id,
        filename=file.filename or "logo.png",
        content=content,
    )
    return _serialize_product(product_id)


@router.post("/{product_id}/ingest")
def start_ingestion(product_id: str, background_tasks: BackgroundTasks) -> dict[str, object]:
    registry = get_product_registry()
    try:
        registry.require_product(product_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    status = enqueue_ingestion(product_id, background_tasks)
    return {
        "product_id": product_id,
        "status": status.status,
        "stage": status.stage,
        "progress": status.progress,
        "message": status.message,
    }


@router.get("/{product_id}/ingest/status")
def get_ingestion_status(product_id: str) -> dict[str, object]:
    registry = get_product_registry()
    try:
        registry.require_product(product_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    status = registry.load_status(product_id)
    return {
        "product_id": product_id,
        "status": status.status,
        "stage": status.stage,
        "progress": status.progress,
        "message": status.message,
        "error": status.error,
    }


def _safe_resolve(base: Path, *parts: str) -> Path:
    """Resolve a path and ensure it stays inside the base directory."""
    resolved = (base / Path(*parts).name if len(parts) == 1 else base.joinpath(*parts)).resolve()
    if not str(resolved).startswith(str(base.resolve())):
        raise HTTPException(status_code=400, detail="Invalid path")
    return resolved


@router.get("/{product_id}/assets/pages/{source_id}/{filename}")
def get_page_asset(product_id: str, source_id: str, filename: str) -> FileResponse:
    registry = get_product_registry()
    try:
        runtime = registry.require_product(product_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    safe_name = Path(filename).name
    safe_source = Path(source_id).name  # strip traversal from source_id
    path = (runtime.pages_dir / safe_source / safe_name).resolve()
    if not str(path).startswith(str(runtime.pages_dir.resolve())):
        raise HTTPException(status_code=400, detail="Invalid path")
    if not path.exists() and safe_source == (runtime.primary_source_id or ""):
        legacy_path = runtime.pages_dir / safe_name
        if legacy_path.exists():
            path = legacy_path
    if not path.exists():
        raise HTTPException(status_code=404, detail="Page image not found")
    return FileResponse(path)


@router.get("/{product_id}/assets/figures/{filename}")
def get_figure_asset(product_id: str, filename: str) -> FileResponse:
    registry = get_product_registry()
    try:
        runtime = registry.require_product(product_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    path = (runtime.figures_dir / Path(filename).name).resolve()
    if not str(path).startswith(str(runtime.figures_dir.resolve())):
        raise HTTPException(status_code=400, detail="Invalid path")
    if not path.exists():
        raise HTTPException(status_code=404, detail="Figure not found")
    return FileResponse(path)


@router.get("/{product_id}/assets/logo")
def get_logo_asset(product_id: str) -> FileResponse:
    registry = get_product_registry()
    try:
        runtime = registry.require_product(product_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if not runtime.manifest.logo_path:
        raise HTTPException(status_code=404, detail="Logo not found")
    path = runtime.root_dir / runtime.manifest.logo_path
    if not path.exists():
        raise HTTPException(status_code=404, detail="Logo not found")
    return FileResponse(path)


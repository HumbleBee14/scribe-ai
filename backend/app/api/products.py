"""Product CRUD and asset-serving API.

Metadata lives in SQLite (fast reads, easy deletes).
Files live on disk under data/products/<id>/ (PDFs, images, indexes).
The registry builds ProductRuntime for the agent from the filesystem.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.core.config import PRODUCTS_DIR, settings
from app.core import database as db
from app.ingest.jobs import enqueue_ingestion
from app.packs.registry import get_product_registry, _slugify, _ensure_product_dirs, _default_quick_actions

router = APIRouter(prefix="/api/products", tags=["products"])




class CreateProductRequest(BaseModel):
    name: str
    description: str = ""
    categories: list[str] = []


class UpdateProductRequest(BaseModel):
    description: str | None = None
    categories: list[str] | None = None
    custom_prompt: str | None = None


def _serialize_product(product_id: str) -> dict[str, object]:
    """Build the full product response from the database."""
    row = db.get_product(product_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Unknown product: {product_id}")
    return {
        "id": row["id"],
        "name": row["name"],
        "description": row["description"],
        "manufacturer": row.get("manufacturer"),
        "item_number": row.get("item_number"),
        "logo_url": (
            f"/api/products/{row['id']}/assets/logo"
            if row.get("logo_path")
            else None
        ),
        "domain": row["domain"],
        "status": row["status"],
        "categories": row["categories"],
        "custom_prompt": row.get("custom_prompt", ""),
        "seeded": False,
        "primary_source_id": row["sources"][0]["source_id"] if row["sources"] else None,
        "document_count": len(row["sources"]),
        "max_documents": settings.max_documents_per_product,
        "sources": [
            {
                "id": s["source_id"],
                "type": s["type"],
                "label": s.get("label") or s["type"],
                "pages": s.get("pages"),
                "processing_status": s.get("processing_status", "pending"),
                "pages_rendered": s.get("pages_rendered", 0),
                "chunks_extracted": s.get("chunks_extracted", 0),
                "processing_error": s.get("processing_error"),
            }
            for s in row["sources"]
        ],
        "processes": [],
        "voltages": [],
        "quick_actions": row["quick_actions"],
        "ingestion": {
            **row["ingestion"],
            "status": row["status"],  # product status is the single source of truth
        },
    }


# ---------------------------------------------------------------------------
# List / Get / Create / Delete
# ---------------------------------------------------------------------------

@router.get("")
def list_products_api() -> dict[str, object]:
    products = db.list_products()
    return {
        "products": [_serialize_product(p["id"]) for p in products],
        "default_product_id": settings.default_product_id,
    }


@router.get("/{product_id}")
def get_product_api(product_id: str) -> dict[str, object]:
    return _serialize_product(product_id)


@router.patch("/{product_id}")
def update_product_api(product_id: str, request: UpdateProductRequest) -> dict[str, object]:
    row = db.get_product(product_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Unknown product: {product_id}")

    updates: dict = {}
    if request.description is not None:
        updates["description"] = request.description.strip()
    if request.custom_prompt is not None:
        updates["custom_prompt"] = request.custom_prompt.strip()
    if updates:
        db.update_product(product_id, **updates)
    if request.categories is not None:
        db.set_categories(product_id, request.categories[:3])

    return _serialize_product(product_id)


@router.post("")
def create_product_api(request: CreateProductRequest) -> dict[str, object]:
    # Generate stable ID from name
    product_id = _slugify(request.name)
    root_dir = PRODUCTS_DIR / product_id
    suffix = 2
    while root_dir.exists():
        product_id = f"{_slugify(request.name)}-{suffix}"
        root_dir = PRODUCTS_DIR / product_id
        suffix += 1

    # Create filesystem structure
    _ensure_product_dirs(root_dir)

    # Write minimal pack.yaml for the registry
    import yaml
    domain = "generic"
    manifest = {
        "id": product_id,
        "product_name": request.name,
        "description": request.description,
        "domain": domain,
        "status": "draft",
        "sources": [],
        "quick_actions": _default_quick_actions(domain),
    }
    (root_dir / "pack.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")

    # Create in database
    db.create_product(
        product_id=product_id,
        name=request.name.strip(),
        description=request.description.strip(),
        domain=domain,
        status="draft",
    )
    db.set_categories(product_id, request.categories[:3])
    db.set_quick_actions(product_id, _default_quick_actions(domain))

    # Clear registry cache so it picks up the new product
    registry = get_product_registry()
    registry._cache.pop(product_id, None)

    return _serialize_product(product_id)


@router.delete("/{product_id}")
def delete_product_api(product_id: str) -> dict[str, object]:
    """Delete a product and all its files."""
    row = db.get_product(product_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Unknown product: {product_id}")

    # Remove from database (cascade deletes categories, sources, jobs, actions)
    db.delete_product(product_id)

    # Remove filesystem
    product_dir = PRODUCTS_DIR / product_id
    if product_dir.exists():
        shutil.rmtree(product_dir)

    # Clear registry cache
    registry = get_product_registry()
    registry._cache.pop(product_id, None)

    return {"deleted": True, "product_id": product_id}


# ---------------------------------------------------------------------------
# Document upload / replace / delete
# ---------------------------------------------------------------------------

@router.post("/{product_id}/documents")
async def upload_documents_api(
    product_id: str,
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    source_type: str = Form("manual"),
) -> dict[str, object]:
    row = db.get_product(product_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Unknown product: {product_id}")

    current_count = len(row["sources"])
    if current_count + len(files) > settings.max_documents_per_product:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {settings.max_documents_per_product} documents per product. Currently {current_count}.",
        )

    product_dir = PRODUCTS_DIR / product_id
    files_dir = product_dir / "files"
    files_dir.mkdir(parents=True, exist_ok=True)

    for upload in files:
        content = await upload.read()
        filename = upload.filename or "document.pdf"
        safe_name = Path(filename).name
        source_id = _slugify(Path(safe_name).stem)

        target_path = files_dir / safe_name
        target_path.write_bytes(content)

        db.add_source(
            product_id=product_id,
            source_id=source_id,
            filename=safe_name,
            path=f"files/{safe_name}",
            source_type=source_type,
            label=safe_name,
        )

    registry = get_product_registry()
    registry._cache.pop(product_id, None)

    # Auto-trigger ingestion in the background
    enqueue_ingestion(product_id, background_tasks)

    return _serialize_product(product_id)


@router.post("/{product_id}/documents/{source_id}/replace")
async def replace_document_api(
    product_id: str,
    source_id: str,
    file: UploadFile = File(...),
    source_type: str = Form("manual"),
) -> dict[str, object]:
    row = db.get_product(product_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Unknown product: {product_id}")

    existing = next((s for s in row["sources"] if s["source_id"] == source_id), None)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"Unknown source: {source_id}")

    content = await file.read()
    filename = file.filename or "document.pdf"
    safe_name = Path(filename).name

    # Remove old file if path differs
    old_path = PRODUCTS_DIR / product_id / existing["path"]
    if old_path.exists():
        old_path.unlink()

    files_dir = PRODUCTS_DIR / product_id / "files"
    files_dir.mkdir(parents=True, exist_ok=True)
    target_path = files_dir / safe_name
    target_path.write_bytes(content)

    db.add_source(
        product_id=product_id,
        source_id=source_id,
        filename=safe_name,
        path=f"files/{safe_name}",
        source_type=source_type,
        label=safe_name,
    )
    registry = get_product_registry()
    registry._cache.pop(product_id, None)
    return _serialize_product(product_id)


@router.delete("/{product_id}/documents/{source_id}")
def delete_document_api(product_id: str, source_id: str) -> dict[str, object]:
    row = db.get_product(product_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Unknown product: {product_id}")

    # Get file path before removing from DB
    source_info = next((s for s in row["sources"] if s["source_id"] == source_id), None)

    if not db.remove_source(product_id, source_id):
        raise HTTPException(status_code=404, detail=f"Unknown source: {source_id}")

    # Remove all artifacts associated with this source
    product_dir = PRODUCTS_DIR / product_id
    if source_info and source_info.get("path"):
        file_path = product_dir / source_info["path"]
        if file_path.exists():
            file_path.unlink()

    # Remove rendered page images for this source
    pages_dir = product_dir / "assets" / "pages" / source_id
    if pages_dir.exists():
        shutil.rmtree(pages_dir)

    # Remove page analysis and embeddings from DB for this source
    db.delete_page_analysis_for_source(product_id, source_id)
    db.delete_toc_for_source(product_id, source_id)

    # Reset status
    remaining = db.get_source_count(product_id)
    db.update_product_status(product_id, "draft" if remaining == 0 else "ready")

    registry = get_product_registry()
    registry._cache.pop(product_id, None)
    return _serialize_product(product_id)


# ---------------------------------------------------------------------------
# Logo
# ---------------------------------------------------------------------------

@router.post("/{product_id}/logo")
async def upload_logo_api(
    product_id: str,
    file: UploadFile = File(...),
) -> dict[str, object]:
    row = db.get_product(product_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Unknown product: {product_id}")

    content = await file.read()
    filename = file.filename or "logo.png"
    extension = Path(filename).suffix.lower() or ".png"

    files_dir = PRODUCTS_DIR / product_id / "files"
    files_dir.mkdir(parents=True, exist_ok=True)
    target_path = files_dir / f"logo{extension}"
    target_path.write_bytes(content)

    logo_path = f"files/logo{extension}"
    db.update_product(product_id, logo_path=logo_path)

    registry = get_product_registry()
    registry._cache.pop(product_id, None)
    return _serialize_product(product_id)


# ---------------------------------------------------------------------------
# Ingestion
# ---------------------------------------------------------------------------

@router.post("/{product_id}/ingest")
def start_ingestion_api(product_id: str, background_tasks: BackgroundTasks) -> dict[str, object]:
    row = db.get_product(product_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Unknown product: {product_id}")

    status = enqueue_ingestion(product_id, background_tasks)
    return {
        "product_id": product_id,
        "status": status.status,
        "stage": status.stage,
        "progress": status.progress,
        "message": status.message,
    }


@router.get("/{product_id}/ingest/status")
def get_ingestion_status_api(product_id: str) -> dict[str, object]:
    row = db.get_product(product_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Unknown product: {product_id}")
    return row["ingestion"]


# ---------------------------------------------------------------------------
# Static asset serving (pages, figures, logo)
# ---------------------------------------------------------------------------

@router.get("/{product_id}/assets/pages/{source_id}/{filename}")
def get_page_asset(product_id: str, source_id: str, filename: str) -> FileResponse:
    registry = get_product_registry()
    try:
        runtime = registry.require_product(product_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    safe_name = Path(filename).name
    safe_source = Path(source_id).name
    path = (runtime.pages_dir / safe_source / safe_name).resolve()
    if not str(path).startswith(str(runtime.pages_dir.resolve())):
        raise HTTPException(status_code=400, detail="Invalid path")
    if not path.exists():
        # Fallback: search all source subfolders for the file
        for subdir in runtime.pages_dir.iterdir():
            if subdir.is_dir():
                candidate = subdir / safe_name
                if candidate.exists():
                    path = candidate
                    break
    if not path.exists():
        raise HTTPException(status_code=404, detail="Page image not found")
    return FileResponse(path)



@router.get("/{product_id}/assets/logo")
def get_logo_asset(product_id: str) -> FileResponse:
    row = db.get_product(product_id)
    if row is None or not row.get("logo_path"):
        raise HTTPException(status_code=404, detail="Logo not found")
    path = PRODUCTS_DIR / product_id / row["logo_path"]
    if not path.exists():
        raise HTTPException(status_code=404, detail="Logo not found")
    return FileResponse(path)


@router.get("/{product_id}/assets/uploads/{filename}")
def get_upload_asset(product_id: str, filename: str) -> FileResponse:
    safe_name = Path(filename).name
    path = PRODUCTS_DIR / product_id / "uploads" / safe_name
    if not path.exists():
        raise HTTPException(status_code=404, detail="Upload not found")
    return FileResponse(path)

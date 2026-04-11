from __future__ import annotations

from fastapi import APIRouter

from app.packs.registry import get_product_registry

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/api/config")
def get_config() -> dict[str, object]:
    """Return non-sensitive config for frontend."""
    runtime = get_product_registry().require_product(None)
    products = [
        {
            "id": product.id,
            "name": product.product_name,
            "status": product.status,
            "domain": product.domain,
        }
        for product in get_product_registry().list_products()
    ]
    return {
        "product": runtime.product_name,
        "product_id": runtime.id,
        "item_number": runtime.manifest.item_number,
        "processes": runtime.processes,
        "voltages": runtime.voltages,
        "products": products,
    }

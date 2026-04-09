from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/api/config")
def get_config() -> dict[str, object]:
    """Return non-sensitive config for frontend."""
    return {
        "product": "Vulcan OmniPro 220",
        "item_number": "57812",
        "processes": ["mig", "flux_cored", "tig", "stick"],
        "voltages": ["120v", "240v"],
    }

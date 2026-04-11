"""Seed the SQLite database from existing product pack.yaml manifests.

Run once after init_db() to populate products that already exist on disk.
Safe to run multiple times (uses INSERT OR IGNORE).
"""
from __future__ import annotations

import logging
from pathlib import Path

import yaml

from app.core.config import PRODUCTS_DIR
from app.core import database as db

logger = logging.getLogger(__name__)


def seed_from_disk(products_dir: Path = PRODUCTS_DIR) -> int:
    """Scan data/products/**/pack.yaml and seed each into the database.

    Returns the number of products seeded.
    """
    count = 0
    for manifest_path in sorted(products_dir.glob("*/pack.yaml")):
        try:
            data = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
        except Exception:
            logger.warning("Skipping invalid manifest: %s", manifest_path)
            continue

        product_id = str(data.get("id") or manifest_path.parent.name)
        existing = db.get_product(product_id)
        if existing is not None:
            count += 1
            continue

        # Derive status from sources: has docs = ready, no docs = draft
        sources = data.get("sources", [])
        status = "ready" if sources else "draft"

        db.create_product(
            product_id=product_id,
            name=str(data.get("product_name") or product_id),
            description=str(data.get("description", "")),
            domain=str(data.get("domain", "generic")),
            status=status,
            manufacturer=data.get("manufacturer"),
            item_number=str(data.get("item_number", "")) or None,
            logo_path=data.get("logo_path"),
        )

        # Categories
        categories = data.get("categories", [])
        if not categories and data.get("domain"):
            categories = [data["domain"]]
        db.set_categories(product_id, [str(c) for c in categories])

        # Sources
        for i, source in enumerate(data.get("sources", [])):
            source_id = str(source.get("id") or f"source-{i + 1}")
            db.add_source(
                product_id=product_id,
                source_id=source_id,
                filename=Path(str(source.get("path", ""))).name,
                path=str(source.get("path", "")),
                source_type=str(source.get("type", "manual")),
                label=source.get("label"),
                pages=source.get("pages"),
            )

        # Quick actions
        actions = data.get("quick_actions", [])
        if actions:
            db.set_quick_actions(product_id, actions)

        logger.info("Seeded product: %s", product_id)
        count += 1

    return count

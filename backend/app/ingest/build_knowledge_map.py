from __future__ import annotations

import json
from pathlib import Path

from app.packs.models import ProductRuntime


def build_placeholder_knowledge_map(runtime: ProductRuntime, chunk_count: int) -> Path:
    """Persist a simple product-scoped knowledge map placeholder."""
    runtime.graph_dir.mkdir(parents=True, exist_ok=True)
    output_path = runtime.graph_dir / "knowledge-map.json"
    payload = {
        "product_id": runtime.id,
        "product_name": runtime.product_name,
        "domain": runtime.domain,
        "sources": [
            {
                "id": source.id,
                "type": source.type,
                "label": source.label,
                "path": source.path,
            }
            for source in runtime.manifest.sources
        ],
        "chunk_count": chunk_count,
        "status": "placeholder",
    }
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return output_path


from __future__ import annotations

import json
from pathlib import Path

from app.ingest.build_knowledge_map import build_placeholder_knowledge_map
from app.ingest.extract_chunks import extract_chunks_from_pdf, write_chunks
from app.ingest.render_pages import render_source_pages
from app.packs.models import ProductRuntime


def ingest_product(runtime: ProductRuntime) -> dict[str, int]:
    """Run the local-first ingestion steps for a product."""
    runtime.pages_dir.mkdir(parents=True, exist_ok=True)
    runtime.figures_dir.mkdir(parents=True, exist_ok=True)
    runtime.index_dir.mkdir(parents=True, exist_ok=True)
    runtime.structured_dir.mkdir(parents=True, exist_ok=True)
    runtime.graph_dir.mkdir(parents=True, exist_ok=True)

    all_chunks: list[dict] = []
    rendered_pages = 0

    for source in runtime.manifest.sources:
        source_path = source.resolve_path(runtime.root_dir)
        if not source_path.exists():
            continue
        if source_path.suffix.lower() != ".pdf":
            continue

        output_dir = runtime.pages_dir / source.id
        rendered = render_source_pages(source_path, output_dir)
        rendered_pages += len(rendered)
        all_chunks.extend(extract_chunks_from_pdf(source_path, source=source))

    write_chunks(all_chunks, runtime.index_dir / "chunks.json")
    if not any(runtime.structured_dir.glob("*.json")):
        (runtime.structured_dir / "structured-placeholder.json").write_text(
            json.dumps(
                {
                    "product_id": runtime.id,
                    "status": "placeholder",
                    "note": "No domain-specific structured facts extracted yet.",
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    build_placeholder_knowledge_map(runtime, chunk_count=len(all_chunks))
    return {
        "sources": len(runtime.manifest.sources),
        "pages_rendered": rendered_pages,
        "chunks": len(all_chunks),
    }


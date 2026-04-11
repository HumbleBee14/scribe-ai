"""Generic agent tools for product manual Q&A.

These tools work for ANY product - they use the database and page analysis
built during ingestion. Domain-specific tools can be added as product
adapters later.
"""
from __future__ import annotations

import json
import logging

from app.core import database as db
from app.packs.registry import get_active_product

logger = logging.getLogger(__name__)


def get_active_tools() -> list[dict]:
    """Return tool definitions for the current product."""
    return TOOL_DEFINITIONS


TOOL_DEFINITIONS: list[dict] = [
    {
        "name": "search_manual",
        "description": (
            "Search across all product manual pages using keywords and semantic similarity. "
            "Returns page summaries ranked by relevance. "
            "Use this FIRST to find which pages contain information about a topic. "
            "Example queries: 'specifications', 'setup steps', 'troubleshooting', 'safety warnings'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query. Use specific terms the manual would contain.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_page_text",
        "description": (
            "Get the full detailed text content of specific manual pages. "
            "Use after search_manual identifies relevant pages, or when the document map "
            "in the system prompt tells you which pages cover a topic. "
            "You can request a single page or multiple pages at once. "
            "Examples: get_page_text('owner-manual', [7]) for specs page, "
            "get_page_text('owner-manual', [10, 11, 12]) for MIG setup steps across pages."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source_id": {
                    "type": "string",
                    "description": "Document source ID from the document map (e.g. 'owner-manual', 'quick-start-guide')",
                },
                "pages": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "Page numbers to retrieve. Single page: [7]. Multiple: [10, 11, 12].",
                },
            },
            "required": ["source_id", "pages"],
        },
    },
    {
        "name": "get_page_image",
        "description": (
            "Get a manual page image. Returns a file_path and a display URL. "
            "The image is shown to the user inline in the chat. "
            "If YOU need to visually analyze the page (circuit diagrams, schematics, wiring layouts, "
            "parts diagrams), use the Read tool on the returned file_path to see the image yourself. "
            "Example: get_page_image('owner-manual', 7) to show the specifications page."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source_id": {
                    "type": "string",
                    "description": "Document source ID",
                },
                "page": {
                    "type": "integer",
                    "description": "Page number to display to the user",
                },
            },
            "required": ["source_id", "page"],
        },
    },
    {
        "name": "clarify_question",
        "description": (
            "Ask the user a clarifying question when their query is ambiguous or missing details. "
            "Example: if the user's question could apply to multiple sections or topics, "
            "ask them to specify which one they mean."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "The clarifying question to ask the user",
                },
                "options": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional choices to make it easy for the user to answer",
                },
            },
            "required": ["question"],
        },
    },
]


def _hybrid_search(product_id: str, query: str, limit: int = 8) -> list[dict]:
    """Combine FTS5 keyword search + embedding vector search into a single ranked list.

    FTS score (0.10–0.50):  rank-normalized BM25 from weighted columns.
      keywords column weight=5.0, summary=3.0, detailed_text=1.0.
      Best FTS result → 0.50.  Proportional decay, floor 0.10.
      Multi-word matches in keywords automatically outscore single-word
      matches in a large blob because BM25 sums per-term IDF*TF scores.
      Stop words contribute ~0 via IDF — no explicit filter needed.

    Vec score (0.0–0.50):   max(0, 1 - distance/2) * 0.5
      all-MiniLM-L6-v2 produces unit-normalized vectors; sqlite-vec
      returns L2 distances in [0, 2]: 0=identical, ~1.4=orthogonal.

    Combined score examples:
      FTS only (top BM25)         → 0.50  (strong keyword match)
      FTS only (weak/partial)     → 0.10  (floor, noise)
      Vec only (distance≈0.1)     → 0.45  (very strong semantic)
      Vec only (distance≈0.5)     → 0.35  (good semantic)
      FTS top + great vec         → 0.95
      FTS top + mediocre vec      → 0.65

    Deduplicates by (source_id, page).
    """
    seen: dict[tuple[str, int], dict] = {}

    # FTS5 keyword search — rank-normalized scoring
    # BM25 rank from FTS5 is negative (more negative = better match).
    # Normalize within result set: best hit → 0.50, proportional decay, floor 0.10.
    fts_results = db.search_pages_fts(product_id, query, limit=limit * 2)
    best_abs_rank = abs(fts_results[0]["fts_rank"]) if fts_results else 1.0
    if best_abs_rank < 1e-9:
        best_abs_rank = 1.0  # guard against zero-rank edge case
    for r in fts_results:
        key = (r["source_id"], r["page"])
        if key not in seen:
            abs_rank = abs(r.get("fts_rank") or 0.0)
            # Scale proportionally: top result → 0.50, floor at 0.10
            fts_score = max(0.10, (abs_rank / best_abs_rank) * 0.50)
            seen[key] = {
                "source_id": r["source_id"],
                "page": r["page"],
                "summary": r["summary"],
                "fts_hit": True,
                "vec_distance": None,
                "score": fts_score,
            }

    # Embedding vector search
    try:
        from app.ingest.build_embeddings import embed_text
        query_blob = embed_text(query)
        if query_blob:
            vec_results = db.search_by_embedding(product_id, query_blob, limit=limit * 2)
            for r in vec_results:
                key = (r["source_id"], r["page"])
                # L2 distance on unit vectors: range [0, 2].
                # 0 = identical, √2 ≈ 1.41 = orthogonal, 2 = opposite direction.
                distance = r.get("distance", 2.0)
                vec_score = max(0.0, 1.0 - distance / 2.0)
                if key in seen:
                    seen[key]["vec_distance"] = distance
                    seen[key]["score"] += vec_score * 0.5
                else:
                    seen[key] = {
                        "source_id": r["source_id"],
                        "page": r["page"],
                        "summary": r.get("summary", ""),
                        "fts_hit": False,
                        "vec_distance": distance,
                        "score": vec_score * 0.5,
                    }
    except Exception as exc:
        logger.warning("Embedding search failed (non-fatal): %s", exc)

    # Sort by combined score, return top results
    ranked = sorted(seen.values(), key=lambda x: x["score"], reverse=True)
    return ranked[:limit]


def _log_result(name: str, result: dict) -> dict:
    """Log tool result summary and return it."""
    if "error" in result:
        print(f"[TOOL] {name} -> ERROR: {result['error']}", flush=True)
    elif name == "search_manual":
        hits = result.get("results", [])
        pages = [(r["source_id"], r["page"]) for r in hits[:5]]
        print(f"[TOOL] {name} -> {len(hits)} results: {pages}", flush=True)
    elif name == "get_page_text":
        pages = [(p["source_id"], p["page"]) for p in result.get("pages", [])]
        chars = sum(len(p.get("text", "")) for p in result.get("pages", []))
        print(f"[TOOL] {name} -> {len(pages)} pages, {chars} chars: {pages}", flush=True)
    elif name == "get_page_image":
        print(f"[TOOL] {name} -> {result.get('source_id')}/page {result.get('page')}", flush=True)
    elif name == "clarify_question":
        print(f"[TOOL] {name} -> \"{result.get('question', '')}\"", flush=True)
    else:
        print(f"[TOOL] {name} -> {json.dumps(result, default=str)[:200]}", flush=True)
    return result


def execute_tool(name: str, params: dict) -> dict:
    """Execute a tool by name with given parameters."""
    print(f"\n[TOOL CALL] {name} args={json.dumps(params, default=str)}", flush=True)

    runtime = get_active_product()
    product_id = runtime.id

    if name == "search_manual":
        query = params.get("query", "")
        results = _hybrid_search(product_id, query, limit=8)
        if not results:
            return _log_result(name, {"results": [], "message": "No matching pages found."})
        return _log_result(name, {
            "results": [
                {
                    "source_id": r["source_id"],
                    "page": r["page"],
                    "summary": r["summary"],
                    "score": round(r.get("score", 0), 3),
                }
                for r in results
            ]
        })

    if name == "get_page_text":
        source_id = params.get("source_id", "")
        pages = params.get("pages", [])
        results = db.get_page_detailed_text(product_id, source_id, pages)
        if not results:
            return _log_result(name, {"error": "No page content found."})
        return _log_result(name, {
            "pages": [
                {
                    "source_id": r["source_id"],
                    "page": r["page"],
                    "text": r["detailed_text"],
                }
                for r in results
            ]
        })

    if name == "get_page_image":
        source_id = params.get("source_id", "")
        page = params.get("page", 1)
        # Return file path so agent can Read it for vision analysis,
        # plus URL for frontend display
        image_path = runtime.pages_dir / source_id / f"page_{page:02d}.png"
        return _log_result(name, {
            "page": page,
            "source_id": source_id,
            "file_path": str(image_path),
            "url": f"/api/products/{product_id}/assets/pages/{source_id}/page_{page:02d}.png",
            "note": "Use the Read tool on file_path if you need to visually analyze this page (diagrams, schematics, circuits). The image will also be shown to the user in the chat.",
        })

    if name == "clarify_question":
        return _log_result(name, {
            "question": params.get("question", ""),
            "options": params.get("options"),
        })

    return _log_result(name, {"error": f"Unknown tool: {name}"})

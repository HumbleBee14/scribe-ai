"""Generic agent tools for product manual Q&A.

These tools work for ANY product - they use the database and page analysis
built during ingestion. Domain-specific tools can be added as product
adapters later.
"""
from __future__ import annotations

import base64
import json
import logging

from app.agent.tools.calculator import safe_calculate
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
            "Returns pages ranked by relevance, each with a summary, relevance score, "
            "match_type (keyword+semantic / keyword-only / semantic-only), and matched keywords. "
            "Use match_type to decide next step: 'keyword+semantic' = high confidence, read text; "
            "'semantic-only' = paraphrase match, consider get_page_image for visual verification. "
            "Optionally filter to a single source document with source_id. "
            "Use this FIRST to find which pages contain information about a topic."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query. Use specific terms the manual would contain.",
                },
                "source_id": {
                    "type": "string",
                    "description": (
                        "Optional: restrict search to a single source document "
                        "(e.g. 'owner-manual', 'quick-start-guide'). "
                        "Omit to search across all sources."
                    ),
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
            "Maximum 5 pages per call. If you need more, make multiple calls. "
            "Examples: get_page_text('owner-manual', [7]) for one page, "
            "get_page_text('owner-manual', [10, 11, 12]) for a range."
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
            "Get a manual page as an image. The page image is delivered DIRECTLY into your context "
            "AND shown to the user in the chat — you do NOT need to call Read separately. "
            "Use this when visual content matters: specification tables, diagrams, charts, "
            "labeled illustrations, panel/layout photos, or any page where the visual layout "
            "carries meaning that plain text cannot capture accurately. "
            "Especially useful when generating precise artifacts (SVG, HTML tables, Mermaid diagrams) "
            "where exact numbers, labels, or spatial relationships must be correct."
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
                    "description": "Page number to retrieve",
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
    {
        "name": "calculate",
        "description": (
            "Evaluate a mathematical expression and return the result. "
            "Operators: +, -, *, /, //, %, ** (power). "
            "Functions: sqrt, abs, round, min, max, sin, cos, tan, log, log10, pow, ceil, floor. "
            "Constants: pi, e. "
            "Examples: '175 * 0.30', 'sqrt(144)', '(240 * 30) / 100', 'round(3.14159, 2)', "
            "'ceil(7.3)', 'log10(1000)', 'sin(pi / 2)', '2 ** 10'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "Math expression to evaluate. Example: '175 * 0.30'",
                },
            },
            "required": ["expression"],
        },
    },
    {
        "name": "update_memory",
        "description": (
            "Add or delete a user preference/context from memory for this product. "
            "Memories persist across conversations and are injected into every future chat. "
            "Use 'add' when the user mentions their setup, preferences, or recurring context. "
            "Use 'delete' when the user says to forget something or remove a preference. "
            "Examples to add: 'Uses 240V input', 'Primarily does MIG on mild steel', 'Beginner welder'. "
            "Maximum 5 memories per product. Keep each memory brief (under 100 chars)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["add", "delete"],
                    "description": "Whether to add or delete a memory.",
                },
                "content": {
                    "type": "string",
                    "description": "For 'add': the preference to remember. For 'delete': the text of the memory to remove (exact or partial match).",
                },
            },
            "required": ["action", "content"],
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
        source_filter = params.get("source_id")  # optional: search within one document
        results = _hybrid_search(product_id, query, limit=8)
        if source_filter:
            results = [r for r in results if r["source_id"] == source_filter]
        if not results:
            return _log_result(name, {"results": [], "message": "No matching pages found."})

        def _match_type(r: dict) -> str:
            fts = r.get("fts_hit", False)
            vec = r.get("vec_distance") is not None
            if fts and vec:
                return "keyword+semantic"
            if fts:
                return "keyword-only"
            return "semantic-only"

        return _log_result(name, {
            "results": [
                {
                    "source_id": r["source_id"],
                    "page": r["page"],
                    "summary": r["summary"],
                    "score": round(r.get("score", 0), 3),
                    "match_type": _match_type(r),
                    "keywords": r.get("keywords", ""),
                }
                for r in results
            ]
        })

    if name == "get_page_text":
        source_id = params.get("source_id", "")
        pages = params.get("pages", [])
        if len(pages) > 5:
            pages = pages[:5]
            print(f"[TOOL] get_page_text: capped to 5 pages (requested {len(params.get('pages', []))})", flush=True)
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
        image_path = runtime.pages_dir / source_id / f"page_{page:02d}.png"
        url = f"/api/products/{product_id}/assets/pages/{source_id}/page_{page:02d}.png"
        # Encode image as base64 so MCP can deliver it inline to the agent.
        # The agent sees the image DIRECTLY — no Read tool needed.
        image_b64: str | None = None
        if image_path.exists():
            try:
                image_b64 = base64.b64encode(image_path.read_bytes()).decode()
            except Exception as exc:
                logger.warning("Could not encode page image %s: %s", image_path, exc)
        return _log_result(name, {
            "page": page,
            "source_id": source_id,
            "url": url,
            # Internal keys (prefixed _) consumed by _mcp_result, not sent as text
            "_image_b64": image_b64,
            "_mime_type": "image/png",
        })

    if name == "clarify_question":
        return _log_result(name, {
            "question": params.get("question", ""),
            "options": params.get("options"),
        })

    if name == "calculate":
        expression = params.get("expression", "")
        return _log_result(name, safe_calculate(expression))

    if name == "update_memory":
        action = params.get("action", "add")
        content = params.get("content", "").strip()
        if not content:
            return _log_result(name, {"error": "Content cannot be empty"})

        if action == "add":
            result = db.add_memory(product_id, content, source="agent")
            if result is None:
                return _log_result(name, {"error": "Maximum 5 memories reached. Delete one first."})
            return _log_result(name, {"saved": True, "content": content})

        if action == "delete":
            # Find matching memory by partial content match
            memories = db.get_memories(product_id)
            matched = next((m for m in memories if content.lower() in m["content"].lower()), None)
            if matched is None:
                return _log_result(name, {"error": f"No memory matching '{content}' found."})
            db.delete_memory(matched["id"])
            return _log_result(name, {"deleted": True, "content": matched["content"]})

        return _log_result(name, {"error": f"Unknown action: {action}. Use 'add' or 'delete'."})

    return _log_result(name, {"error": f"Unknown tool: {name}"})

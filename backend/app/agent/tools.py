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
            "Search across all product manual pages using keywords. "
            "Returns page summaries ranked by relevance. "
            "Use this to find which pages contain information about a topic."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query - use specific terms from the manual",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_page_text",
        "description": (
            "Get the full detailed text content of specific manual pages. "
            "Use this after search_manual identifies relevant pages, "
            "or when you need the complete text from specific page numbers."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source_id": {
                    "type": "string",
                    "description": "Document source ID (e.g. 'owner-manual')",
                },
                "pages": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "List of page numbers to retrieve",
                },
            },
            "required": ["source_id", "pages"],
        },
    },
    {
        "name": "get_page_image",
        "description": (
            "Get a rendered page image to show diagrams, tables, or visual content. "
            "Use when the user asks about a diagram, schematic, or visual reference, "
            "or when you need to show the actual manual page."
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
                    "description": "Page number to show",
                },
            },
            "required": ["source_id", "page"],
        },
    },
    {
        "name": "clarify_question",
        "description": (
            "Ask the user a clarifying question when their query is ambiguous. "
            "Use when you need more information before you can give an accurate answer."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "The clarifying question to ask",
                },
                "options": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional list of choices for the user",
                },
            },
            "required": ["question"],
        },
    },
]


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
        results = db.search_pages_fts(product_id, query, limit=8)
        if not results:
            return _log_result(name, {"results": [], "message": "No matching pages found."})
        return _log_result(name, {
            "results": [
                {
                    "source_id": r["source_id"],
                    "page": r["page"],
                    "summary": r["summary"],
                    "keywords": r["keywords"],
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
        return _log_result(name, {
            "page": page,
            "source_id": source_id,
            "url": f"/api/products/{product_id}/assets/pages/{source_id}/page_{page:02d}.png",
        })

    if name == "clarify_question":
        return _log_result(name, {
            "question": params.get("question", ""),
            "options": params.get("options"),
        })

    return _log_result(name, {"error": f"Unknown tool: {name}"})

"""MCP tool wrappers for the Claude Agent SDK.

Each tool wraps the existing execution logic from tools.py with the @tool
decorator and returns results in MCP CallToolResult format. This is the
bridge between our knowledge engine and the Agent SDK's tool system.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from claude_agent_sdk import create_sdk_mcp_server, tool

from app.agent.tools import execute_tool

logger = logging.getLogger(__name__)

MCP_SERVER_NAME = "welding-knowledge"


def _mcp_result(data: Any) -> dict[str, Any]:
    """Wrap tool output in MCP CallToolResult format."""
    if isinstance(data, str):
        text = data
    else:
        text = json.dumps(data, default=str)
    return {"content": [{"type": "text", "text": text}]}


def _mcp_error(message: str) -> dict[str, Any]:
    """Return an MCP error result."""
    return {"content": [{"type": "text", "text": message}], "is_error": True}


def _run_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Execute a tool via our existing engine and wrap in MCP format."""
    try:
        result = execute_tool(name, args)
        if isinstance(result, dict) and "error" in result:
            return _mcp_error(result["error"])
        return _mcp_result(result)
    except Exception:
        logger.exception("Tool %s failed with args %s", name, args)
        return _mcp_error(f"Internal error executing {name}")


# ---------------------------------------------------------------------------
# MCP tool definitions (wrapping existing tool handlers)
# ---------------------------------------------------------------------------

@tool(
    "lookup_specifications",
    (
        "Look up exact technical specifications for a welding process at a given voltage. "
        "Returns current range, input amperage, duty cycle rating, "
        "max OCV, and weldable materials. "
        "USE when the user asks about specs, capabilities, or technical data for a process."
    ),
    {
        "type": "object",
        "properties": {
            "process": {
                "type": "string",
                "enum": ["mig", "flux_cored", "tig", "stick"],
            },
            "voltage": {
                "type": "string",
                "enum": ["120v", "240v"],
            },
        },
        "required": ["process", "voltage"],
    },
)
async def mcp_lookup_specifications(args: dict[str, Any]) -> dict[str, Any]:
    return _run_tool("lookup_specifications", args)


@tool(
    "lookup_duty_cycle",
    (
        "Look up the exact duty cycle for a welding process at a given voltage. "
        "Returns rated duty cycle percentage, amperage, weld minutes, rest minutes, "
        "and continuous use amperage. NEVER interpolate. Return exact manual values only."
    ),
    {
        "type": "object",
        "properties": {
            "process": {
                "type": "string",
                "enum": ["mig", "flux_cored", "tig", "stick"],
            },
            "voltage": {
                "type": "string",
                "enum": ["120v", "240v"],
            },
        },
        "required": ["process", "voltage"],
    },
)
async def mcp_lookup_duty_cycle(args: dict[str, Any]) -> dict[str, Any]:
    return _run_tool("lookup_duty_cycle", args)


@tool(
    "lookup_polarity",
    (
        "Look up the exact polarity and cable setup for a welding process. "
        "Returns polarity type (DCEP/DCEN), which cable goes in which socket "
        "(positive/negative), gas requirements, and additional connections."
    ),
    {
        "type": "object",
        "properties": {
            "process": {
                "type": "string",
                "enum": ["mig", "flux_cored", "tig", "stick", "spool_gun"],
            },
        },
        "required": ["process"],
    },
)
async def mcp_lookup_polarity(args: dict[str, Any]) -> dict[str, Any]:
    return _run_tool("lookup_polarity", args)


@tool(
    "lookup_troubleshooting",
    (
        "Look up troubleshooting information for welding problems. "
        "If a problem description is provided, fuzzy-matches against known problems "
        "and returns possible causes and solutions."
    ),
    {
        "type": "object",
        "properties": {
            "problem": {
                "type": "string",
                "description": (
                    "Description of the problem "
                    "(e.g., 'porosity', 'wire jamming', 'arc unstable')"
                ),
            },
            "process": {
                "type": "string",
                "enum": ["mig_flux", "tig_stick"],
            },
        },
        "required": ["process"],
    },
)
async def mcp_lookup_troubleshooting(args: dict[str, Any]) -> dict[str, Any]:
    return _run_tool("lookup_troubleshooting", args)


@tool(
    "lookup_safety_warnings",
    (
        "Look up safety warnings for a specific category. "
        "Categories: general, electrical, fumes_gas, arc_ray, "
        "fire, gas_cylinder, asphyxiation. "
        "USE proactively when the user asks about setup or operational procedures."
    ),
    {
        "type": "object",
        "properties": {
            "category": {
                "type": "string",
                "enum": [
                    "general", "electrical", "fumes_gas",
                    "arc_ray", "fire", "gas_cylinder", "asphyxiation",
                ],
            },
        },
        "required": ["category"],
    },
)
async def mcp_lookup_safety_warnings(args: dict[str, Any]) -> dict[str, Any]:
    return _run_tool("lookup_safety_warnings", args)


@tool(
    "clarify_question",
    (
        "Ask the user a clarifying question before answering. "
        "USE when the question is ambiguous, missing process type, voltage, "
        "material, or other critical information."
    ),
    {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "The clarifying question to ask the user",
            },
            "options": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional multiple-choice options",
            },
        },
        "required": ["question"],
    },
)
async def mcp_clarify_question(args: dict[str, Any]) -> dict[str, Any]:
    return _run_tool("clarify_question", args)


@tool(
    "get_page_image",
    (
        "Get a specific page image from the manual as a visual reference. "
        "USE when the answer involves a diagram, schematic, labeled photo, "
        "or when the user asks to 'show' something from the manual."
    ),
    {
        "type": "object",
        "properties": {
            "page": {
                "type": "integer",
                "description": "Page number from the manual",
            },
        },
        "required": ["page"],
    },
)
async def mcp_get_page_image(args: dict[str, Any]) -> dict[str, Any]:
    return _run_tool("get_page_image", args)


@tool(
    "diagnose_weld",
    (
        "Diagnose a weld based on its appearance or symptoms. "
        "Returns matching diagnosis with reference images from the manual."
    ),
    {
        "type": "object",
        "properties": {
            "weld_type": {
                "type": "string",
                "enum": ["wire", "stick"],
            },
            "symptoms": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Observed symptoms (e.g., 'porosity', 'spatter')",
            },
        },
        "required": ["weld_type", "symptoms"],
    },
)
async def mcp_diagnose_weld(args: dict[str, Any]) -> dict[str, Any]:
    return _run_tool("diagnose_weld", args)


@tool(
    "render_artifact",
    (
        "Generate an interactive visual artifact (diagram, calculator, flowchart). "
        "USE when a visual explanation would be clearer than text. "
        "ALWAYS include source_pages to ground the artifact in manual evidence."
    ),
    {
        "type": "object",
        "properties": {
            "type": {
                "type": "string",
                "enum": ["mermaid", "svg", "table", "html"],
            },
            "title": {
                "type": "string",
            },
            "code": {
                "type": "string",
                "description": "The renderable content (Mermaid, SVG markup, HTML)",
            },
            "source_pages": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "page": {"type": "integer"},
                        "description": {"type": "string"},
                    },
                },
                "description": "Manual pages this artifact is grounded in. REQUIRED.",
            },
        },
        "required": ["type", "title", "code", "source_pages"],
    },
)
async def mcp_render_artifact(args: dict[str, Any]) -> dict[str, Any]:
    return _run_tool("render_artifact", args)


@tool(
    "search_manual",
    (
        "Search the product manual for relevant information using text search. "
        "USE for open-ended questions not covered by exact-data lookup tools. "
        "Returns ranked text chunks with page numbers and section titles."
    ),
    {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query",
            },
            "max_results": {
                "type": "integer",
                "description": "Max results to return (default 5)",
            },
        },
        "required": ["query"],
    },
)
async def mcp_search_manual(args: dict[str, Any]) -> dict[str, Any]:
    return _run_tool("search_manual", args)


# ---------------------------------------------------------------------------
# MCP Server factory
# ---------------------------------------------------------------------------

ALL_MCP_TOOLS = [
    mcp_lookup_specifications,
    mcp_lookup_duty_cycle,
    mcp_lookup_polarity,
    mcp_lookup_troubleshooting,
    mcp_lookup_safety_warnings,
    mcp_clarify_question,
    mcp_get_page_image,
    mcp_diagnose_weld,
    mcp_render_artifact,
    mcp_search_manual,
]


def create_knowledge_mcp_server():
    """Create the MCP server with all active welding knowledge tools."""
    return create_sdk_mcp_server(
        name=MCP_SERVER_NAME,
        tools=ALL_MCP_TOOLS,
    )

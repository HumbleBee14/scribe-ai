"""MCP tool wrappers for the Claude Agent SDK.

Generic tools that work for any product. Each wraps execute_tool()
from tools.py with the @tool decorator for the Agent SDK.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from claude_agent_sdk import create_sdk_mcp_server, tool

from app.agent.tools import execute_tool, TOOL_DEFINITIONS

logger = logging.getLogger(__name__)

MCP_SERVER_NAME = "product-knowledge"


def _mcp_result(data: Any) -> dict[str, Any]:
    """Wrap tool output in MCP CallToolResult format."""
    if isinstance(data, str):
        text = data
    elif isinstance(data, dict):
        text = json.dumps(data, indent=2, default=str)
    else:
        text = str(data)
    return {"type": "text", "text": text}


def _make_tool(name: str, description: str, schema: dict):
    """Create an MCP tool function bound to a specific tool name."""
    def handler(**kwargs: Any) -> dict[str, Any]:
        return _mcp_result(execute_tool(name, kwargs))

    return tool(name=name, description=description, input_schema=schema)(handler)


# Build MCP tools from generic TOOL_DEFINITIONS
ALL_MCP_TOOLS = [
    _make_tool(_d["name"], _d["description"], _d["input_schema"])
    for _d in TOOL_DEFINITIONS
]


def create_knowledge_mcp_server():
    """Create the MCP server with all active product knowledge tools."""
    return create_sdk_mcp_server(
        name=MCP_SERVER_NAME,
        tools=ALL_MCP_TOOLS,
    )

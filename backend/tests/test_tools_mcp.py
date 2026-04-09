"""Tests for MCP tool wrappers."""
import json

from app.agent.tools_mcp import (
    ALL_MCP_TOOLS,
    MCP_SERVER_NAME,
    _mcp_error,
    _mcp_result,
    _run_tool,
    create_knowledge_mcp_server,
)


def test_mcp_result_wraps_dict() -> None:
    result = _mcp_result({"value": 42})
    assert result["content"][0]["type"] == "text"
    data = json.loads(result["content"][0]["text"])
    assert data["value"] == 42


def test_mcp_result_wraps_string() -> None:
    result = _mcp_result("hello")
    assert result["content"][0]["text"] == "hello"


def test_mcp_error_format() -> None:
    result = _mcp_error("Something went wrong")
    assert result["is_error"] is True
    assert "Something went wrong" in result["content"][0]["text"]


def test_all_mcp_tools_count() -> None:
    assert len(ALL_MCP_TOOLS) == 9


def test_create_knowledge_mcp_server() -> None:
    server = create_knowledge_mcp_server()
    assert server is not None


def test_run_tool_duty_cycle_mcp_format() -> None:
    """Verify _run_tool returns correct MCP CallToolResult format."""
    result = _run_tool("lookup_duty_cycle", {"process": "mig", "voltage": "240v"})
    assert "content" in result
    assert result["content"][0]["type"] == "text"
    data = json.loads(result["content"][0]["text"])
    assert data["rated"]["duty_cycle_percent"] == 25


def test_run_tool_polarity_mcp_format() -> None:
    result = _run_tool("lookup_polarity", {"process": "tig"})
    assert "content" in result
    data = json.loads(result["content"][0]["text"])
    assert data["polarity_type"] == "DCEN"


def test_run_tool_safety_mcp_format() -> None:
    result = _run_tool("lookup_safety_warnings", {"category": "electrical"})
    assert "content" in result
    data = json.loads(result["content"][0]["text"])
    assert data["level"] == "danger"


def test_run_tool_invalid_returns_mcp_error() -> None:
    result = _run_tool("lookup_duty_cycle", {"process": "plasma", "voltage": "240v"})
    assert result.get("is_error") is True


def test_mcp_server_name() -> None:
    assert MCP_SERVER_NAME == "welding-knowledge"

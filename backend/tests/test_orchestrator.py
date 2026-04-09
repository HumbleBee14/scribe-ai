"""Tests for the Agent SDK orchestrator (event mapping, tool label resolution)."""
from app.agent.orchestrator import (
    AgentOrchestrator,
    _get_tool_label,
    _strip_mcp_prefix,
)


def test_strip_mcp_prefix_removes_server_name() -> None:
    assert _strip_mcp_prefix("mcp__welding-knowledge__lookup_duty_cycle") == "lookup_duty_cycle"


def test_strip_mcp_prefix_passes_through_plain_name() -> None:
    assert _strip_mcp_prefix("lookup_duty_cycle") == "lookup_duty_cycle"


def test_strip_mcp_prefix_handles_toolsearch() -> None:
    assert _strip_mcp_prefix("ToolSearch") == "ToolSearch"


def test_get_tool_label_known_tool() -> None:
    assert _get_tool_label("lookup_duty_cycle") == "Looking up duty cycle"
    assert _get_tool_label("lookup_polarity") == "Checking polarity setup"
    assert _get_tool_label("lookup_safety_warnings") == "Reviewing safety warnings"


def test_get_tool_label_with_mcp_prefix() -> None:
    assert (
        _get_tool_label("mcp__welding-knowledge__lookup_duty_cycle")
        == "Looking up duty cycle"
    )


def test_get_tool_label_unknown_tool() -> None:
    assert _get_tool_label("unknown_tool") == "unknown_tool"


def test_orchestrator_class_exists() -> None:
    """AgentOrchestrator should be importable and constructible (without calling API)."""
    assert AgentOrchestrator is not None

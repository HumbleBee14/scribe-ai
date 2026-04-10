"""Tests for the orchestrator (fallback, event mapping, tool resolution, session)."""
import pytest

from app.agent.orchestrator import (
    AgentOrchestrator,
    _get_tool_label,
    _strip_mcp_prefix,
)
from app.session.manager import Session


def test_strip_mcp_prefix_removes_server_name() -> None:
    assert (
        _strip_mcp_prefix("mcp__welding-knowledge__lookup_duty_cycle")
        == "lookup_duty_cycle"
    )


def test_strip_mcp_prefix_passes_through_plain_name() -> None:
    assert _strip_mcp_prefix("lookup_duty_cycle") == "lookup_duty_cycle"


def test_strip_mcp_prefix_handles_toolsearch() -> None:
    assert _strip_mcp_prefix("ToolSearch") == "ToolSearch"


def test_get_tool_label_known_tool() -> None:
    assert _get_tool_label("lookup_duty_cycle") == "Looking up duty cycle"
    assert _get_tool_label("lookup_polarity") == "Checking polarity setup"
    assert _get_tool_label("lookup_safety_warnings") == "Reviewing safety warnings"
    assert _get_tool_label("Read") == "Reading from manual"


def test_get_tool_label_with_mcp_prefix() -> None:
    assert (
        _get_tool_label("mcp__welding-knowledge__lookup_duty_cycle")
        == "Looking up duty cycle"
    )


def test_get_tool_label_unknown_tool() -> None:
    assert _get_tool_label("unknown_tool") == "unknown_tool"


def test_orchestrator_class_exists() -> None:
    assert AgentOrchestrator is not None


def test_session_stores_sdk_session_id() -> None:
    """Session should be able to store SDK session ID for resume."""
    session = Session(id="test")
    assert session.sdk_session_id is None
    session.sdk_session_id = "sdk-abc-123"
    assert session.sdk_session_id == "sdk-abc-123"


def test_emit_tool_specific_events_safety() -> None:
    """Safety warnings should update session and emit events."""
    orch = AgentOrchestrator()
    session = Session(id="test")

    events = orch._emit_tool_specific_events(
        "lookup_safety_warnings",
        {"category": "electrical"},
        session,
    )

    assert "electrical" in session.safety_warnings_shown
    event_types = [e["event"] for e in events]
    assert "session_update" in event_types
    assert "tool_end" in event_types


def test_emit_tool_specific_events_clarification() -> None:
    """Clarification tool should emit clarification event."""
    orch = AgentOrchestrator()
    session = Session(id="test")

    events = orch._emit_tool_specific_events(
        "clarify_question",
        {"question": "Which process?", "options": ["MIG", "TIG"]},
        session,
    )

    clarification = [e for e in events if e["event"] == "clarification"]
    assert len(clarification) == 1
    assert clarification[0]["data"]["question"] == "Which process?"
    assert clarification[0]["data"]["options"] == ["MIG", "TIG"]


def test_emit_tool_specific_events_page_image() -> None:
    """get_page_image should emit image event with correct URL."""
    orch = AgentOrchestrator()
    session = Session(id="test")

    events = orch._emit_tool_specific_events(
        "get_page_image",
        {"page": 13},
        session,
    )

    image_events = [e for e in events if e["event"] == "image"]
    assert len(image_events) == 1
    assert image_events[0]["data"]["page"] == 13
    assert "page_13" in image_events[0]["data"]["url"]


def test_render_artifact_removed_from_tools() -> None:
    """render_artifact is no longer an active tool (artifacts are inline tags now)."""
    from app.agent.tools import get_active_tools

    active_names = [t["name"] for t in get_active_tools()]
    assert "render_artifact" not in active_names


@pytest.mark.asyncio
async def test_run_falls_back_to_anthropic_when_sdk_startup_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    orch = AgentOrchestrator()
    session = Session(id="test")

    async def fake_sdk(user_message: str, session: Session, images=None):
        raise RuntimeError("sdk unavailable")
        yield  # pragma: no cover

    async def fake_anthropic(user_message: str, session: Session, images=None):
        yield {"event": "done", "data": {"status": "completed", "turns": 1}}

    monkeypatch.setattr(orch, "_should_use_agent_sdk", lambda: True)
    monkeypatch.setattr(orch, "_run_with_agent_sdk", fake_sdk)
    monkeypatch.setattr(orch, "_run_with_anthropic_loop", fake_anthropic)

    events = [event async for event in orch.run("hello", session)]

    assert events == [{"event": "done", "data": {"status": "completed", "turns": 1}}]

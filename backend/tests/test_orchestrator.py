"""Tests for the SDK-only orchestrator event mapping and runtime behavior."""
import pytest

from app.agent.orchestrator import (
    AgentOrchestrator,
    _coerce_page_number,
    _get_tool_label,
    _strip_mcp_prefix,
)
from app.packs.registry import get_product_registry
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


def test_coerce_page_number_accepts_ints_and_numeric_strings() -> None:
    assert _coerce_page_number(13) == 13
    assert _coerce_page_number("13") == 13
    assert _coerce_page_number(" 07 ") == 7


def test_coerce_page_number_rejects_invalid_values() -> None:
    assert _coerce_page_number(None) is None
    assert _coerce_page_number("") is None
    assert _coerce_page_number("page 7") is None
    assert _coerce_page_number(0) is None


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
    runtime = get_product_registry().require_product(session.product_id)

    events = orch._emit_tool_specific_events(
        "lookup_safety_warnings",
        {"category": "electrical"},
        session,
        runtime,
    )

    assert "electrical" in session.safety_warnings_shown
    event_types = [e["event"] for e in events]
    assert "session_update" in event_types
    assert "tool_end" in event_types


def test_emit_tool_specific_events_clarification() -> None:
    """Clarification tool should emit clarification event."""
    orch = AgentOrchestrator()
    session = Session(id="test")
    runtime = get_product_registry().require_product(session.product_id)

    events = orch._emit_tool_specific_events(
        "clarify_question",
        {"question": "Which process?", "options": ["MIG", "TIG"]},
        session,
        runtime,
    )

    clarification = [e for e in events if e["event"] == "clarification"]
    assert len(clarification) == 1
    assert clarification[0]["data"]["question"] == "Which process?"
    assert clarification[0]["data"]["options"] == ["MIG", "TIG"]


def test_emit_tool_specific_events_page_image() -> None:
    """get_page_image should emit image event with correct URL."""
    orch = AgentOrchestrator()
    session = Session(id="test")
    runtime = get_product_registry().require_product(session.product_id)

    events = orch._emit_tool_specific_events(
        "get_page_image",
        {"page": 13},
        session,
        runtime,
    )

    image_events = [e for e in events if e["event"] == "image"]
    assert len(image_events) == 1
    assert image_events[0]["data"]["page"] == 13
    assert "page_13" in image_events[0]["data"]["url"]


def test_emit_tool_specific_events_page_image_accepts_string_page() -> None:
    orch = AgentOrchestrator()
    session = Session(id="test")
    runtime = get_product_registry().require_product(session.product_id)

    events = orch._emit_tool_specific_events(
        "get_page_image",
        {"page": "14"},
        session,
        runtime,
    )

    image_events = [e for e in events if e["event"] == "image"]
    assert len(image_events) == 1
    assert image_events[0]["data"]["page"] == 14
    assert image_events[0]["data"]["url"].endswith("page_14.png")


def test_emit_tool_specific_events_page_image_ignores_invalid_page() -> None:
    orch = AgentOrchestrator()
    session = Session(id="test")
    runtime = get_product_registry().require_product(session.product_id)

    events = orch._emit_tool_specific_events(
        "get_page_image",
        {"page": "page fourteen"},
        session,
        runtime,
    )

    assert [e["event"] for e in events] == ["tool_end"]


def test_render_artifact_removed_from_tools() -> None:
    """render_artifact is no longer an active tool (artifacts are inline tags now)."""
    from app.agent.tools import get_active_tools

    active_names = [t["name"] for t in get_active_tools()]
    assert "render_artifact" not in active_names


@pytest.mark.asyncio
async def test_run_delegates_to_sdk_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    orch = AgentOrchestrator()
    session = Session(id="test")

    async def fake_sdk(user_message: str, session: Session, runtime, images=None):
        assert user_message == "hello"
        assert runtime.id == "vulcan-omnipro-220"
        assert images is None
        yield {"event": "done", "data": {"status": "completed", "turns": 1}}

    monkeypatch.setattr(orch, "_run_with_agent_sdk", fake_sdk)

    events = [event async for event in orch.run("hello", session)]

    assert events == [{"event": "done", "data": {"status": "completed", "turns": 1}}]


@pytest.mark.asyncio
async def test_run_surfaces_sdk_error_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    orch = AgentOrchestrator()
    session = Session(id="test")

    async def fake_sdk(user_message: str, session: Session, runtime, images=None):
        assert runtime.id == "vulcan-omnipro-220"
        yield {"event": "error", "data": {"message": "Agent runtime error. Please try again."}}

    monkeypatch.setattr(orch, "_run_with_agent_sdk", fake_sdk)

    events = [event async for event in orch.run("hello", session)]

    assert events == [
        {"event": "error", "data": {"message": "Agent runtime error. Please try again."}}
    ]


@pytest.mark.asyncio
async def test_build_multimodal_prompt_includes_base64_images() -> None:
    orch = AgentOrchestrator()

    prompt = orch._build_multimodal_prompt(
        "diagnose this weld",
        [{"media_type": "image/png", "data": "abc123"}],
    )

    chunks = [chunk async for chunk in prompt]
    assert len(chunks) == 1
    message = chunks[0]["message"]
    assert message["role"] == "user"
    assert message["content"][0]["type"] == "image"
    assert message["content"][0]["source"]["media_type"] == "image/png"
    assert message["content"][0]["source"]["data"] == "abc123"
    assert message["content"][1] == {"type": "text", "text": "diagnose this weld"}

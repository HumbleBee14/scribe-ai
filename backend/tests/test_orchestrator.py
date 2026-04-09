"""Tests for agent orchestrator runtime behavior."""
from __future__ import annotations

from typing import Any

import pytest

import app.agent.orchestrator as orchestrator_module
from app.agent.orchestrator import AgentOrchestrator
from app.agent.provider import ContentBlock, LLMProvider, ModelResponse
from app.session.manager import Session


class FakeProvider(LLMProvider):
    """Test double that returns pre-configured responses."""

    def __init__(self, responses: list[ModelResponse]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    async def create_message(self, **kwargs: Any) -> ModelResponse:
        self.calls.append(kwargs)
        return self._responses.pop(0)


class FakeFullContext:
    def __init__(self, available: bool = False) -> None:
        self._available = available

    def is_available(self) -> bool:
        return self._available

    def build_document_block(self) -> dict:
        return {"type": "document", "source": {"type": "base64", "data": "abc"}}


def _text_response(text: str) -> ModelResponse:
    return ModelResponse(
        content=[ContentBlock(type="text", text=text)],
        stop_reason="end_turn",
        input_tokens=10,
        output_tokens=5,
    )


def _tool_response(tool_id: str, name: str, tool_input: dict) -> ModelResponse:
    return ModelResponse(
        content=[ContentBlock(type="tool_use", id=tool_id, name=name, input=tool_input)],
        stop_reason="tool_use",
        input_tokens=10,
        output_tokens=5,
    )


@pytest.mark.asyncio
async def test_orchestrator_stops_after_clarification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = FakeProvider([
        _tool_response("tool-1", "clarify_question", {"question": "Which process?"}),
    ])
    orchestrator = AgentOrchestrator(
        provider=provider,
        model="test-model",
        full_context=FakeFullContext(),
    )
    orchestrator._tools = [{"name": "clarify_question"}]

    monkeypatch.setattr(
        orchestrator_module,
        "execute_tool",
        lambda name, params: {"question": params["question"], "options": ["MIG", "TIG"]},
    )

    session = Session(id="s1")
    events = [event async for event in orchestrator.run("What's the duty cycle?", session)]

    event_types = [event["event"] for event in events]
    assert event_types == ["tool_start", "tool_end", "clarification", "done"]
    assert events[-1]["data"]["status"] == "clarification_required"
    assert len(provider.calls) == 1


@pytest.mark.asyncio
async def test_orchestrator_tracks_safety_warning_and_completes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = FakeProvider([
        _tool_response("tool-1", "lookup_safety_warnings", {"category": "electrical"}),
        _text_response("Use proper grounding."),
    ])
    orchestrator = AgentOrchestrator(
        provider=provider,
        model="test-model",
        full_context=FakeFullContext(),
    )
    orchestrator._tools = [{"name": "lookup_safety_warnings"}]

    monkeypatch.setattr(
        orchestrator_module,
        "execute_tool",
        lambda _name, _params: {"level": "danger", "items": ["Ground the machine"]},
    )

    session = Session(id="s2")
    events = [event async for event in orchestrator.run("How do I wire this safely?", session)]

    assert "electrical" in session.safety_warnings_shown
    event_types = [event["event"] for event in events]
    assert event_types == [
        "tool_start",
        "tool_end",
        "safety_warning",
        "session_update",
        "text_delta",
        "done",
    ]
    assert events[0]["data"]["label"] == "Reviewing safety warnings"
    assert events[-1]["data"]["status"] == "completed"


def test_inject_full_context_handles_string_history() -> None:
    provider = FakeProvider([])
    orchestrator = AgentOrchestrator(
        provider=provider,
        model="test-model",
        full_context=FakeFullContext(available=True),
    )

    messages = [
        {"role": "user", "content": "Earlier question"},
        {"role": "assistant", "content": "Earlier answer"},
    ]

    result = orchestrator._inject_full_context(messages)

    assert result[0]["content"][0]["type"] == "document"
    assert result[0]["content"][1]["type"] == "text"

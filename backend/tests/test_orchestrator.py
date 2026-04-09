"""Tests for agent orchestrator runtime behavior."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

import app.agent.orchestrator as orchestrator_module
from app.agent.orchestrator import AgentOrchestrator
from app.session.manager import Session


class FakeMessagesAPI:
    def __init__(self, responses: list[object]) -> None:
        self._responses = responses
        self.calls: list[dict] = []

    async def create(self, **kwargs):  # type: ignore[no-untyped-def]
        self.calls.append(kwargs)
        return self._responses.pop(0)


class FakeClient:
    def __init__(self, responses: list[object]) -> None:
        self.messages = FakeMessagesAPI(responses)


class FakeFullContext:
    def __init__(self, available: bool = False) -> None:
        self._available = available

    def is_available(self) -> bool:
        return self._available

    def build_document_block(self) -> dict:
        return {"type": "document", "source": {"type": "base64", "data": "abc"}}


def _make_text_block(text: str) -> object:
    return SimpleNamespace(type="text", text=text)


def _make_tool_block(block_id: str, name: str, tool_input: dict) -> object:
    return SimpleNamespace(type="tool_use", id=block_id, name=name, input=tool_input)


def _make_response(content: list[object], stop_reason: str = "end_turn") -> object:
    return SimpleNamespace(
        content=content,
        stop_reason=stop_reason,
        usage=SimpleNamespace(input_tokens=10, output_tokens=5),
    )


@pytest.mark.asyncio
async def test_orchestrator_stops_after_clarification(monkeypatch: pytest.MonkeyPatch) -> None:
    orchestrator = object.__new__(AgentOrchestrator)
    orchestrator._client = FakeClient(
        [
            _make_response(
                [_make_tool_block("tool-1", "clarify_question", {"question": "Which process?"})],
                stop_reason="tool_use",
            )
        ]
    )
    orchestrator._model = "test-model"
    orchestrator._tools = [{"name": "clarify_question"}]
    orchestrator._full_context = FakeFullContext()

    monkeypatch.setattr(
        orchestrator_module,
        "execute_tool",
        lambda name, params: {"question": params["question"], "options": ["MIG", "TIG"]},
    )

    session = Session(id="s1")
    events = [event async for event in orchestrator.run("What's the duty cycle?", session)]

    assert [event["event"] for event in events] == ["tool_start", "tool_end", "clarification", "done"]
    assert events[-1]["data"]["status"] == "clarification_required"
    assert len(orchestrator._client.messages.calls) == 1


@pytest.mark.asyncio
async def test_orchestrator_tracks_safety_warning_and_completes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    orchestrator = object.__new__(AgentOrchestrator)
    orchestrator._client = FakeClient(
        [
            _make_response(
                [_make_tool_block("tool-1", "lookup_safety_warnings", {"category": "electrical"})],
                stop_reason="tool_use",
            ),
            _make_response([_make_text_block("Use proper grounding.")]),
        ]
    )
    orchestrator._model = "test-model"
    orchestrator._tools = [{"name": "lookup_safety_warnings"}]
    orchestrator._full_context = FakeFullContext()

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


def test_build_messages_with_context_handles_string_history() -> None:
    orchestrator = object.__new__(AgentOrchestrator)
    orchestrator._full_context = FakeFullContext(available=True)

    messages = [
        {"role": "user", "content": "Earlier question"},
        {"role": "assistant", "content": "Earlier answer"},
    ]

    result = orchestrator._build_messages_with_context(messages)

    assert result[0]["content"][0]["type"] == "document"
    assert result[0]["content"][1]["type"] == "text"
